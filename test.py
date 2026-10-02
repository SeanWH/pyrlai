# ====================================
# File: test
# Project: pyrlai
# Version: 1.0.0
# Created by SHennessey on 2026-10-02
# ====================================

# !/usr/bin/env python3

import random
from typing import List, Tuple, Optional
from unittest import case

import numpy as np
import tcod
from tcod.map import Map

# =============================================================================# CONSTANTS & CONFIGURATION# =============================================================================

SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50
MAP_WIDTH = 80
MAP_HEIGHT = 43
ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 30
MAX_MONSTERS_PER_ROOM = 2
MAX_ITEMS_PER_ROOM = 1

# Color Definitions

COLOR_WHITE = (255, 255, 255)
COLOR_BLACK = (0, 0, 0)
COLOR_DARK_WALL = (0, 0, 100)
COLOR_LIGHT_WALL = (130, 110, 50)
COLOR_DARK_GROUND = (50, 50, 150)
COLOR_LIGHT_GROUND = (200, 180, 50)
COLOR_DESATURATED_GREEN = (63, 127, 63)
COLOR_ORANGE = (255, 127, 0)
COLOR_RED = (255, 0, 0)


# =============================================================================# GAME DATA STRUCTURES# =============================================================================

class Rect:
    """Helper class to define rectangular rooms."""

    def __init__(self, x: int, y: int, w: int, h: int):
        self.x1 = x
        self.y1 = y
        self.x2 = x + w
        self.y2 = y + h

    @property
    def center(self) -> Tuple[int, int]:
        center_x = int((self.x1 + self.x2) / 2)
        center_y = int((self.y1 + self.y2) / 2)
        return center_x, center_y

    def intersect(self, other: "Rect") -> bool:
        return (self.x1 <= other.x2 and self.x2 >= other.x1 and
                self.y1 <= other.y2 and self.y2 >= other.y1)


class Entity:
    """Generic class representing players, monsters, items, or stairs."""

    def __init__(self, x: int, y: int, char: str, color: Tuple[int, int, int],
                 name: str, blocks: bool = False, fighter: Optional["Fighter"] = None,
                 ai: Optional["BasicMonster"] = None, item: Optional["Item"] = None,
                 is_stairs: bool = False):
        self.x = x
        self.y = y
        self.char = char
        self.color = color
        self.name = name
        self.blocks = blocks
        self.fighter = fighter
        self.ai = ai
        self.item = item
        self.is_stairs = is_stairs

        if self.fighter:
            self.fighter.owner = self
        if self.ai:
            self.ai.owner = self
        if self.item:
            self.item.owner = self


class Fighter:
    """Component handling combat statistics and actions."""

    def __init__(self, hp: int, defense: int, power: int):
        self.max_hp = hp
        self.hp = hp
        self.defense = defense
        self.power = power

    def take_damage(self, amount: int, game_map: "GameMap") -> List[str]:
        results = []
        self.hp -= amount
        if self.hp <= 0:
            self.hp = 0
            results.append(f"death_{self.owner.name}")
        return results

    def heal(self, amount: int):
        self.hp += amount
        if self.hp > self.max_hp:
            self.hp = self.max_hp


class BasicMonster:
    """Component handling simple enemy movement and AI targeting."""

    def __init__(self):
        self.owner: Optional[Entity] = None

    def take_turn(self, target: Entity, game_map: "GameMap", entities: List[Entity]) -> List[str]:
        results = []
        monster = self.owner
        if game_map.fov[monster.y, monster.x] and monster.fighter.hp > 0:
            if abs(target.x - monster.x) <= 1 and abs(target.y - monster.y) <= 1:
                results.extend(attack(monster, target, game_map))
            else:
                dx, dy = target.x - monster.x, target.y - monster.y
                distance = np.sqrt(dx ** 2 + dy ** 2)
                dx, dy = int(round(dx / distance)), int(round(dy / distance))
                if not game_map.is_blocked(monster.x + dx, monster.y + dy, entities):
                    monster.x += dx
                    monster.y += dy
        return results


class Item:
    """Component managing consumable payload execution."""

    def __init__(self, use_function=None, **kwargs):
        self.use_function = use_function
        self.function_kwargs = kwargs
        self.owner: Optional[Entity] = None

    def use(self, **kwargs) -> List[dict]:
        if not self.use_function:
            return [{"msg": f"The {self.owner.name} cannot be used.", "color": COLOR_WHITE, "consumed": False}]
        return self.use_function(self.owner, **self.function_kwargs, **kwargs)


def cast_heal(entity: Entity, amount: int) -> List[dict]:
    """Healing payload logic."""
    if entity.fighter.hp == entity.fighter.max_hp:
        return [{"msg": "You are already at full health.", "color": COLOR_ORANGE, "consumed": False}]
    entity.fighter.heal(amount)
    return [
        {"msg": f"Your wounds close up! You heal for {amount} HP.", "color": COLOR_DESATURATED_GREEN, "consumed": True}]


# =============================================================================# GAMEPLAY MECHANICS# =============================================================================
def attack(attacker: Entity, defender: Entity, game_map: "GameMap") -> List[str]:
    results = []
    damage = attacker.fighter.power - defender.fighter.defense

    if damage > 0:
        results.append(f"msg_{attacker.name.capitalize()} attacks {defender.name} for {damage} hit points.")
        results.extend(defender.fighter.take_damage(damage, game_map))
    else:
        results.append(f"msg_{attacker.name.capitalize()} attacks {defender.name} but does no damage.")

    return results


class GameMap:
    """Manages map data, tile properties, and procedural generation."""

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.tiles_transparent = np.zeros((height, width), dtype=bool, order="F")
        self.tiles_walkable = np.zeros((height, width), dtype=bool, order="F")
        self.explored = np.zeros((height, width), dtype=bool, order="F")
        self.fov = np.zeros((height, width), dtype=bool, order="F")

    def is_blocked(self, x: int, y: int, entities: List[Entity]) -> bool:
        if not self.tiles_walkable[y, x]:
            return True
        for entity in entities:
            if entity.blocks and entity.x == x and entity.y == y:
                return True
        return False

    def create_room(self, room: Rect):
        self.tiles_transparent[room.y1 + 1:room.y2, room.x1 + 1:room.x2] = True
        self.tiles_walkable[room.y1 + 1:room.y2, room.x1 + 1:room.x2] = True

    def create_h_tunnel(self, x1: int, x2: int, y: int):
        for x in range(min(x1, x2), max(x1, x2) + 1):
            self.tiles_transparent[y, x] = True
            self.tiles_walkable[y, x] = True

    def create_v_tunnel(self, y1: int, y2: int, x: int):
        for y in range(min(y1, y2), max(y1, y2) + 1):
            self.tiles_transparent[y, x] = True
            self.tiles_walkable[y, x] = True

    def generate_dungeon(self, entities: List[Entity], player: Entity) -> Tuple[int, int]:
        rooms: List[Rect] = []
        center_x, center_y = 0, 0

        # Wipe map clean
        self.tiles_transparent[:] = False
        self.tiles_walkable[:] = False
        self.explored[:] = False

        for r in range(MAX_ROOMS):
            w = random.randint(ROOM_MIN_SIZE, ROOM_MAX_SIZE)
            h = random.randint(ROOM_MIN_SIZE, ROOM_MAX_SIZE)
            x = random.randint(0, self.width - w - 1)
            y = random.randint(0, self.height - h - 1)

            new_room = Rect(x, y, w, h)
            if any(new_room.intersect(other) for other in rooms):
                continue

            self.create_room(new_room)
            (new_x, new_y) = new_room.center

            if len(rooms) == 0:
                player.x = new_x
                player.y = new_y
                center_x, center_y = new_x, new_y
            else:
                (prev_x, prev_y) = rooms[-1].center
                if random.randint(0, 1) == 1:
                    self.create_h_tunnel(prev_x, new_x, prev_y)
                    self.create_v_tunnel(prev_y, new_y, new_x)
                else:
                    self.create_v_tunnel(prev_y, new_y, prev_x)
                    self.create_h_tunnel(prev_x, new_x, new_y)

            self.place_entities(new_room, entities, player)
            rooms.append(new_room)

        # Put exit stairs down in the very last room generated
        stairs = Entity(center_x, center_y, ">", COLOR_WHITE, "Stairs Down", is_stairs=True)
        entities.append(stairs)

        return center_x, center_y

    def place_entities(self, room: Rect, entities: List[Entity], player: Entity):
        num_monsters = random.randint(0, MAX_MONSTERS_PER_ROOM)
        num_items = random.randint(0, MAX_ITEMS_PER_ROOM)

        # Place Monsters
        for _ in range(num_monsters):
            x = random.randint(room.x1 + 1, room.x2 - 1)
            y = random.randint(room.y1 + 1, room.y2 - 1)

            if not any(e.x == x and e.y == y for e in entities) and (x != player.x or y != player.y):
                if random.randint(0, 100) < 80:
                    fighter_comp = Fighter(hp=10, defense=0, power=3)
                    ai_comp = BasicMonster()
                    monster = Entity(x, y, "o", COLOR_DESATURATED_GREEN, "Orc", blocks=True, fighter=fighter_comp,
                                     ai=ai_comp)
                else:
                    fighter_comp = Fighter(hp=16, defense=1, power=4)
                    ai_comp = BasicMonster()
                    monster = Entity(x, y, "T", (0, 127, 0), "Troll", blocks=True, fighter=fighter_comp, ai=ai_comp)
                entities.append(monster)

        # Place Items
        for _ in range(num_items):
            x = random.randint(room.x1 + 1, room.x2 - 1)
            y = random.randint(room.y1 + 1, room.y2 - 1)
            if not any(e.x == x and e.y == y for e in entities) and (x != player.x or y != player.y):
                item_comp = Item(use_function=cast_heal, amount=8)
                potion = Entity(x, y, "!", (127, 0, 255), "Healing Potion", item=item_comp)
                entities.append(potion)

    def update_fov(self, player: Entity):
        self.fov[:] = tcod.map.compute_fov(self.tiles_transparent, (player.y, player.x), radius=8, light_walls=True,
                                           algorithm=tcod.FOV_BASIC)
        self.explored |= self.fov


## =============================================================================## RENDERING & INTERFACE## =============================================================================
def render_bar(console: tcod.Console, x: int, y: int, total_width: int, name: str, value: int, maximum: int,
               bar_color: Tuple[int, int, int], back_color: Tuple[int, int, int]):
    bar_width = int(float(value) / maximum * total_width)
    console.draw_rect(x, y, total_width, 1, ord(" "), bg=back_color)
    if bar_width > 0:
        console.draw_rect(x, y, bar_width, 1, ord(" "), bg=bar_color)

    console.print(x + 1, y, f"{name}: {value}/{maximum}", fg=COLOR_WHITE)


def render_all(console: tcod.Console, entities: List[Entity], game_map: GameMap,
               message_log: List[Tuple[str, Tuple[int, int, int]]], player: Entity, dungeon_level: int):
    # Render map tiles
    for y in range(game_map.height):
        for x in range(game_map.width):
            visible = game_map.fov[y, x]
            explored = game_map.explored[y, x]
            if visible:
                if game_map.tiles_walkable[y, x]:
                    console.rgb[y, x] = (ord("."), COLOR_LIGHT_GROUND, COLOR_BLACK)
                else:
                    console.rgb[y, x] = (ord("#"), COLOR_LIGHT_WALL, COLOR_BLACK)
            elif explored:
                if game_map.tiles_walkable[y, x]:
                    console.rgb[y, x] = (ord("."), COLOR_DARK_GROUND, COLOR_BLACK)
                else:
                    console.rgb[y, x] = (ord("#"), COLOR_DARK_WALL, COLOR_BLACK)
            else:
                console.rgb[y, x] = (ord(" "), COLOR_BLACK, COLOR_BLACK)

            # Render entities
            for entity in entities:
                if game_map.fov[entity.y, entity.x] or (entity.is_stairs and game_map.explored[entity.y, entity.x]):
                    if entity.fighter and entity.fighter.hp <= 0:
                        console.print(entity.x, entity.y, "%", fg=COLOR_RED)
                    else:
                        console.print(entity.x, entity.y, entity.char, fg=entity.color)

            # Render HUD Panel Layout
            console.draw_rect(0, MAP_HEIGHT, SCREEN_WIDTH, SCREEN_HEIGHT - MAP_HEIGHT, ord(" "), bg=(15, 15, 15))
            render_bar(console, 1, MAP_HEIGHT + 1, 20, "HP", player.fighter.hp, player.fighter.max_hp, COLOR_RED,
                       (100, 0, 0))
            console.print(1, MAP_HEIGHT + 3, f"Dungeon Level: {dungeon_level}", fg=COLOR_WHITE)
            console.print(1, MAP_HEIGHT + 5, "[G] Get Item [D] Descend Stairs", fg=(150, 150, 150))

            # Print log messages
            y_offset = 1
            for msg, color in message_log[-5:]:
                console.print(25, MAP_HEIGHT + y_offset, msg, fg=color)
                y_offset += 1


# ===========================================================================
# MAIN GAME LOOP
# ===========================================================================
def main():
    tileset = tcod.tileset.load_tilesheet("assets\\fonts\\dejavu10x10_gs_tc.png", 32, 8, tcod.tileset.CHARMAP_TCOD)
    player_fighter = Fighter(hp=30, defense=2, power=5)
    player = Entity(0, 0, "@", COLOR_WHITE, "Player", blocks=True, fighter=player_fighter)
    entities: List[Entity] = [player]
    game_map = GameMap(MAP_WIDTH, MAP_HEIGHT)
    dungeon_level = 1
    game_map.generate_dungeon(entities, player)
    game_map.update_fov(player)
    message_log: List[Tuple[str, Tuple[int, int, int]]] = [
        ("Welcome to the dungeon, adventurer!", COLOR_ORANGE)
    ]

    # Initialize window context
    with tcod.context.new_terminal(SCREEN_WIDTH, SCREEN_HEIGHT, tileset=tileset, title="TCOD Roguelike Core",
                                   vsync=True) as context:
        root_console = tcod.console.Console(SCREEN_WIDTH, SCREEN_HEIGHT, order="F")
        game_state = "PLAYING"
        while True:
            root_console.clear()
            render_all(root_console, entities, game_map, message_log, player, dungeon_level)
            context.present(root_console)
            player_turn = False
            action_descend = False
            action_pickup = False
            dx, dy = 0, 0

            # Event/Input handling hook
            for event in tcod.event.wait():
                match event:
                    case tcod.event.Quit:
                        raise SystemExit()
                    case tcod.event.KeyDown:
                        match event.sym:
                            case tcod.event.KeySym.ESCAPE:
                                if game_state == 'DEAD':
                                    raise SystemExit()
                                    continue
                            case tcod.event.KeySym.UP:
                                dx = 0
                                dy = -1
                                player_turn = True
                            case tcod.event.KeySym.DOWN:
                                dx = 0
                                dy = 1
                                player_turn = True
                            case tcod.event.KeySym.LEFT:
                                dx = -1
                                dy = 0
                                player_turn = True
                            case tcod.event.KeySym.RIGHT:
                                dx = 1
                                dy = 0
                                player_turn = True
                            case tcod.event.KeySym.g:
                                action_pickup = True
                                player_turn = True
                            case tcod.event.KeySym.d:
                                action_descend = True
                                player_turn = True
                            case tcod.event.KeySym.ESCAPE:
                                raise SystemExit()

                if player_turn and game_state == 'PLAYING':
                    if dx != 0 or dy != 0:
                        destination_x = player.x + dx
                        destination_y = player.y + dy
                        if 0 <= destination_x < MAP_WIDTH and 0 <= destination_y < MAP_HEIGHT:
                            target = next(
                                (e for e in entities if e.x == destination_x and e.y == destination_y and e.fighter),
                                None)
                            if target:
                                # Attack monster
                                combat_results = attack(player, target, game_map)
                                for combat_result in combat_results:
                                    if combat_result.startswith('msg_'):
                                        message_log.append((combat_result[:4], COLOR_WHITE))
                                    elif combat_result.startswith('death_'):
                                        name = combat_result[6:]
                                        message_log.append(f'The {name} dies!', COLOR_ORANGE)
                                    elif not game_map.is_blocked(destination_x, destination_y, entities):
                                        player.x = destination_x
                                        player.y = destination_y
                                        game_map.update_fov(player)
                                # 2. Pick up item
                                if action_pickup:
                                    item_ent = next(
                                        (e for e in entities if e.x == player.x and e.y == player.y and e.item), None)
                                if item_ent:
                                    res = item_ent.item.use(player)
                                for r in res:
                                    message_log.append((r["msg"], r["color"]))
                                if r.get("consumed", False):
                                    entities.remove(item_ent)
                                else:
                                    message_log.append(("There is nothing here to pick up.", COLOR_WHITE))
                                # 3. Descend stairs
                                if action_descend:
                                    stairs_ent = next(
                                        (e for e in entities if e.x == player.x and e.y == player.y and e.is_stairs),
                                        None)
                                    if stairs_ent:
                                        dungeon_level += 1
                                        message_log.append(("You descend deeper into the dark...", COLOR_ORANGE))
                                        entities = [player]
                                        game_map.generate_dungeon(entities, player)
                                        game_map.update_fov(player)
                                    else:
                                        message_log.append(("There are no stairs here to descend.", COLOR_WHITE))
                    # Enemy turn phase execution
                    for entity in entities:
                        if entity.ai and entity.fighter and entity.fighter.hp > 0:
                            ai_results = entity.ai.take_turn(player, game_map, entities)
                    for res in ai_results:
                        if res.startswith("msg_"):
                            message_log.append((res[4:], COLOR_RED))
                        elif res == "death_Player":
                            message_log.append(("You have been slain! Game Over.", COLOR_RED))
                            game_state = "DEAD"
                            player.char = "%"
                            player.color = COLOR_RED


if __name__ == '__main__':
    main()
