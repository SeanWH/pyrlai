# ====================================
# File: main.py
# Project: pyrlai
# Version: 1.0.0
# Created by SHennessey on 2026-10-02
# ====================================

import random
from typing import List, Tuple, Optional
import numpy as np
import tcod

# ===================================================================
# CONSTANTS & CONFIGURATION
# ===================================================================

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


# ===================================================================
# GAME DATA STRUCTURES
# ===================================================================

class Rect:
    """Helper class to define rectangular rooms"""

    def __init__(self, x: int, y: int, width: int, height: int):
        self.x1 = x
        self.y1 = y
        self.x2 = x + width
        self.y2 = y + height

    @property
    def center(self) -> Tuple[int, int]:
        center_x = int((self.x1 + self.x2) / 2)
        center_y = int((self.y1 + self.y2) / 2)
        return center_x, center_y

    def intersects(self, rect: Rect) -> bool:
        return (self.x1 <= rect.x2 and self.x2 >= rect.x1 and
                self.y1 <= rect.y2 and self.y2 >= rect.y1)


class Entity:
    """Generic class to represent a player, monster, item, or stairs"""

    def __init__(self, x: int, y: int, symbol: str, color: Tuple[int, int, int], name: str, is_blocking: bool = False,
                 fighter: Optional['Fighter'] = None, ai: Optional['BasicMonster'] = None,
                 item: Optional['Item'] = None, is_stairs: bool = False):
        self.x = x
        self.y = y
        self.symbol = symbol
        self.color = color
        self.name = name
        self.is_blocking = is_blocking
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
    """Component handling combat statistics and actions"""

    def __init__(self, hp: int, defense: int, power: int):
        self.hp = hp
        self.max_hp = hp
        self.defense = defense
        self.power = power

    def take_damage(self, damage: int, game_map: "GameMap") -> List[str]:
        results = []
        self.hp -= damage
        if self.hp <= 0:
            self.hp = 0
            results.append(f'death_{self.owner.name}')
        return results

    def heal(self, amount: int):
        self.hp += amount
        if self.hp > self.max_hp:
            self.hp = self.max_hp


class BasicMonster:
    """Component handling simple enemy movement and AI targeting."""

    def __init__(self):
        self.owner: Optional['Entity'] = None

    def take_turn(self, target: Entity, game_map: "GameMap", entities: List['Entity']) -> List[str]:
        results = []
        monster = self.owner
        if game_map.fov[monster.y, monster.x] and monster.fighter.hp > 0:
            if abs(target.x - monster.x) <= 1 and abs(target.y - monster.y) <= 1:
                results.extend(attack(monster, target, game_map))
            else:
                dx = target.x - monster.x
                dy = target.y - monster.y
                distance = np.sqrt(dx ** 2 + dy ** 2)
                dx = int(round(dx / distance))
                dy = int(round(dy / distance))

                if not game_map.is_blocked(monster.x + dx, monster.y + dy, entities):
                    monster.x += dx
                    monster.y += dy
        return results


class Item: pass


class Stairs: pass


class GameMap:
    """Manages map data, tile properties, and procedural generation"""

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.tiles_transparent = np.zeros((height, width), dtype=bool, order='F')
        self.tiles_walkable = np.zeros((height, width), dtype=bool, order='F')
        self.explored = np.zeros((height, width), dtype=bool, order='F')
        self.fov = np.zeros((height, width), dtype=bool, order='F')

    def is_blocked(self, x: int, y: int, entities: List['Entity']) -> bool:
        """Is the tile blocked (not passable)"""
        if not self.tiles_walkable[y, x]:
            return True
        for entity in entities:
            if entity.is_blocking and entity.x == x and entity.y == y:
                return True

        return False

    def create_room(self, room: Rect):
        """Creates a rectangular room"""
        self.tiles_transparent[room.y1 + 1:room.y2, room.x1 + 1:room.x2] = True
        self.tiles_walkable[room.y1 + 1:room.y2, room.x1 + 1:room.x2] = True

    def create_h_tunnel(self, x1: int, x2: int, y: int):
        """Creates a horizontal tunnel"""
        for x in range(min(x1, x2), max(x1, x2) + 1):
            self.tiles_transparent[y, x] = True
            self.tiles_walkable[y, x] = True

    def create_v_tunnel(self, y1: int, y2: int, x: int):
        """Creates a vertical tunnel"""
        for y in range(min(y1, y2), max(y1, y2) + 1):
            self.tiles_transparent[y, x] = True
            self.tiles_walkable[y, x] = True

    def generate(self, entities: List['Entity'], player: Entity) -> Tuple[int, int]:
        """Generates the game map"""
        rooms: List[Rect] = []
        center_x = 0
        center_y = 0

        # Clear map
        self.tiles_transparent[:] = False
        self.tiles_walkable[:] = False
        self.explored[:] = False

        for room in range(MAX_ROOMS):
            w = random.randint(ROOM_MIN_SIZE, ROOM_MAX_SIZE)
            h = random.randint(ROOM_MIN_SIZE, ROOM_MAX_SIZE)
            x = random.randint(0, self.width - w - 1)
            y = random.randint(1, self.height - h - 1)

            new_room = Rect(x, y, w, h)
            if any(new_room.intersects(other) for other in rooms):
                continue

            self.create_room(new_room)
            (new_x, new_y) = new_room.center

            if len(rooms) == 0:
                player.x = new_x
                player.y = new_y
                center_x = new_x
                center_y = new_y
            else:
                (prev_x, prev_y) = rooms[-1].center
                if (random.randint(0, 1) == 1):
                    self.create_h_tunnel(prev_x, new_x, prev_y)
                    self.create_v_tunnel(prev_y, new_y, new_x)
                else:
                    self.create_v_tunnel(prev_y, new_y, prev_x)
                    self.create_h_tunnel(prev_x, new_x, prev_y)

            self.place_entities(new_room, entities, player)
            rooms.append(new_room)

        # Put exit stairs in last room generated
        stairs = Entity(center_x, center_y, '>', COLOR_WHITE, "Stairs Down", is_stairs=True)
        entities.append(stairs)

        return center_x, center_y

    def place_entities(self, room: Rect, entities: List['Entity'], player: Entity):
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
                    monster = Entity(x, y, "o", COLOR_DESATURATED_GREEN, "Orc", is_blocking=True, fighter=fighter_comp,
                                     ai=ai_comp)
                else:
                    fighter_comp = Fighter(hp=16, defense=1, power=4)
                    ai_comp = BasicMonster()
                    monster = Entity(x, y, "T", (0, 127, 0), "Troll", is_blocking=True, fighter=fighter_comp,
                                     ai=ai_comp)
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
        self.fov[:] = tcod.map.compute_fov(self.tiles_transparent, (player.x, player.y), radius=8, light_walls=True,
                                           algorithm=tcod.FOV_BASIC)
        self.explored |= self.fov


# ===================================================================
# GAMEPLAY MECHANICS
# ===================================================================

def cast_heal(target: Entity, amount: int) -> List[dict]:
    """Healing payload logic"""
    if target.fighter.hp == target.fighter.max_hp:
        return [{'msg': 'You are already at full health.', 'color': COLOR_ORANGE, 'consumed': False}]
    target.fighter.heal(amount)
    return [
        {'msg': f'Your wounds close up! You heal for {amount} HP.', 'color': COLOR_DESATURATED_GREEN, 'consumed': True}]


def attack(attacker: Entity, defender: Entity, game_map: "GameMap") -> List[str]:
    """Attack logic"""
    results = []
    damage = attacker.fighter.power - defender.fighter.defense

    if damage > 0:
        results.append(f"msg_{attacker.name.capitalize()} attacks {defender.name} for {damage} hit points.")
        results.extend(defender.fighter.take_damage(damage, game_map))
    else:
        results.append(f"msg_{attacker.name.capitalize()} attacks {defender.name} but does no damage.")

    return results
