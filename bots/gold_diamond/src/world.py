"""Static map catalog, canonical camp IDs and observed mutable camp state."""

import cambc
from cambc import game_map, vision
from strategy_config import (BASE_FOCUS, BASE_STRENGTH, GOLD_EQUIV,
                             MONOLITH_MIN_ROUND, RANGED_TYPES)


def distance(a, b):
    return max(abs(a.x - b.x), abs(a.y - b.y))


def bbox_distance(point, bounds):
    left, top, right, bottom = bounds
    dx = max(left - point.x, 0, point.x - right)
    dy = max(top - point.y, 0, point.y - bottom)
    return max(dx, dy)


class Group:
    def __init__(self, group_id, handle):
        self.id = group_id
        self.handle = handle
        self.mask = handle.spawn_tiles()
        self.cells = tuple(sorted(self.mask.positions(), key=lambda p: (p.y, p.x)))
        self.health = sum(camp.base_stats().base_health for camp in handle)
        self.gems = handle.gem_value()
        self.gold = handle.gold_value()
        self.monsters = len(handle)
        self.monolith = any(camp.is_monolith() for camp in handle)
        self.respawn = handle.max_respawn_timer()
        self.cluster = sum(
            1 for a in self.cells for b in self.cells
            if (a.x, a.y) < (b.x, b.y) and distance(a, b) <= 1
        )


class World:
    def __init__(self):
        self.static_blocked = (game_map.walls() | game_map.holes()
                               | game_map.altars()
                               | game_map.spawn_region(cambc.Team.ENEMY))
        self.own_spawn = game_map.spawn_region(cambc.Team.ALLY)
        self.enemy_spawn = game_map.spawn_region(cambc.Team.ENEMY)
        self.own_cells = self.own_spawn.positions()
        self.enemy_cells = self.enemy_spawn.positions()
        own_bounds = (min(p.x for p in self.own_cells), min(p.y for p in self.own_cells),
                      max(p.x for p in self.own_cells), max(p.y for p in self.own_cells))
        enemy_bounds = (min(p.x for p in self.enemy_cells), min(p.y for p in self.enemy_cells),
                        max(p.x for p in self.enemy_cells), max(p.y for p in self.enemy_cells))
        self.altars = tuple(sorted(game_map.altars().positions(),
                                   key=lambda p: (p.y, p.x)))
        raw = game_map.camp_groups()

        def key(group):
            cells = tuple(sorted((p.y, p.x) for p in group.spawn_tiles().positions()))
            return cells

        self.groups = tuple(Group(index, group)
                            for index, group in enumerate(sorted(raw, key=key)))
        self.respawn_until = {}
        for group in self.groups:
            group.from_spawn = min(bbox_distance(p, own_bounds) for p in group.cells)
            group.from_enemy = min(bbox_distance(p, enemy_bounds) for p in group.cells)
            group.to_altar = min((distance(p, a) - 1 for p in group.cells
                                  for a in self.altars), default=10000)

    def status(self, group, visible=None):
        if visible is None:
            visible = vision.visible_tiles()
        round_number = cambc.round_number()
        if not (group.mask & visible).is_empty():
            try:
                state = group.handle.state()
                if isinstance(state, game_map.CampGroupRespawning):
                    self.respawn_until[group.id] = round_number + max(1, state.timer) + 1
                    return "respawning"
                self.respawn_until.pop(group.id, None)
                if isinstance(state, game_map.CampGroupRewardAvailable):
                    return "capture"
                if isinstance(state, game_map.CampGroupAlive):
                    return "alive"
            except cambc.Error:
                pass
        if self.respawn_until.get(group.id, -1) >= round_number:
            return "respawning"
        return "unknown"

    def statuses(self):
        visible = vision.visible_tiles()
        return tuple(self.status(group, visible) for group in self.groups)

    def spawn_distance(self, group):
        return group.from_spawn

    def enemy_distance(self, group):
        return group.from_enemy

    def altar_distance(self, group):
        return group.to_altar

    def opening_score(self, champion_type, group):
        """Common-input first-cycle estimate; never uses current champion vision."""
        if group.monolith or group.gems + group.gold == 0:
            return -1.0
        approach = self.spawn_distance(group)
        if approach >= 10000:
            return -1.0
        strength = BASE_STRENGTH[champion_type]
        focus = BASE_FOCUS[champion_type]
        spell_bonus = (focus * (0.19 if champion_type in (3, 5, 11) else 0.10))
        damage = strength + spell_bonus
        if champion_type == 10 and group.cluster:
            damage += strength * min(1.8, 0.6 * group.cluster)
        if champion_type == 5 and group.cluster:
            damage += focus * min(0.35, 0.11 * group.cluster)
        clear = group.health / max(1.0, damage)
        # Ranged units often spend movement turns without a basic attack.
        if champion_type in RANGED_TYPES:
            clear += min(approach, 4) * 0.25
        bank = self.altar_distance(group)
        enemy_distance = self.enemy_distance(group)
        risk = 0.54 if enemy_distance < approach + 2 else 1.0
        if champion_type in (3, 4) and risk < 1:
            risk *= 0.55
        gold_weight = 0.42 if group.gold else GOLD_EQUIV
        value = group.gems + gold_weight * group.gold
        if champion_type == 11 and group.gold >= 30:
            value += 20.0
        distance_penalty = 1.0 if approach <= 18 else (18.0 / approach) ** 2
        return (risk * distance_penalty * value
                / max(1.0, 2 * approach + clear + 6 + bank + max(1, group.gems // 10)))

    def opening_assignments(self, roster):
        """Greedy deterministic one-to-one matching from the common spawn."""
        assignments = [None] * len(roster)
        pairs = []
        for slot, kind in enumerate(roster):
            local = sorted(((self.opening_score(kind, group), group.id)
                            for group in self.groups), reverse=True)
            for score, group_id in local[:8]:
                if score > 0:
                    pairs.append((-score, slot, group_id))
        used = set()
        for _, slot, group_id in sorted(pairs):
            if assignments[slot] is None and group_id not in used:
                assignments[slot] = group_id
                used.add(group_id)
        return tuple(assignments)

    def group_score(self, me, group, state, claimed=False):
        if state == "respawning":
            return -1.0
        if group.monolith and (cambc.round_number() < MONOLITH_MIN_ROUND
                               or me.strength() < 90):
            return -1.0
        current = me.position()
        steps = min(distance(current, p) for p in group.cells)
        if state == "capture":
            value = (group.gems + GOLD_EQUIV * group.gold) / max(1.0, steps + 5)
            return value * (0.28 if claimed else 1.0)
        health = group.health
        if state == "alive":
            observed = 0.0
            for camp in group.handle:
                try:
                    if camp.is_visible() and camp.health() > 0:
                        observed += camp.health()
                except cambc.Error:
                    pass
            if observed:
                health = observed
        damage = me.strength() + me.focus() * 0.12
        if me.champion_name() == cambc.ChampionType.VARG and group.cluster:
            damage += me.strength() * min(1.8, 0.6 * group.cluster)
        clear = health / max(1.0, damage)
        early_gold = (cambc.round_number() < 300 and me.gold_count() < 150)
        gold_weight = 0.38 if early_gold else GOLD_EQUIV
        value = group.gems + gold_weight * group.gold
        if early_gold and me.champion_name() == cambc.ChampionType.TAVI and group.gold >= 30:
            value += 18.0
        risk = 0.50 if self.enemy_distance(group) < steps + 2 else 1.0
        if int(me.champion_name()) in (3, 4) and risk < 1:
            risk *= 0.55
        result = risk * value / max(1.0, steps + clear + 6 + self.altar_distance(group))
        if claimed:
            result *= 0.28
        return result

