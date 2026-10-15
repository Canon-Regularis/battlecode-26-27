"""Stage 1 camp, capture, respawn and altar navigation policy."""

import cambc
from cambc import game_map


def distance(a, b):
    return a.chebyshev_distance(b)


def group_key(group):
    return int(group)


def visible_group_state(group, visible):
    if (group.spawn_tiles() & visible).is_empty():
        return None
    try:
        return group.state()
    except cambc.Error:
        # Vision can change between the mask query and the engine state query.
        return None


def blocked_tiles(me):
    blocked = (game_map.walls() | game_map.holes() | game_map.altars()
               | game_map.spawn_region(cambc.Team.ENEMY)
               | cambc.vision.champion_tiles()
               | cambc.vision.camp_tiles()
               | cambc.vision.teleport_tiles())
    blocked.set(me.position(), False)
    return blocked


class ObjectivePolicy:
    """Owns a champion's current group and avoids occupying respawn tiles."""

    def __init__(self):
        self.target_id = None
        self.previous_states = {}
        self.pending_capture = None
        self.capture_seen_round = None
        self.no_progress = 0
        self.last_position = None
        self.last_progress_round = None

    def _status(self, group, visible):
        state = visible_group_state(group, visible)
        if state is None:
            return "unknown"
        if isinstance(state, game_map.CampGroupRespawning):
            return "respawning"
        if isinstance(state, game_map.CampGroupRewardAvailable):
            return "capture"
        if isinstance(state, game_map.CampGroupAlive):
            return "alive"
        return "unknown"

    def _record_state(self, group, status):
        key = group_key(group)
        old = self.previous_states.get(key)
        round_number = cambc.round_number()
        if old == "capture" and status == "respawning":
            print(f"LARP_EVENT|{round_number}|capture_success|{key}", flush=True)
            self.pending_capture = None
        elif old == "capture" and status == "alive":
            print(f"LARP_EVENT|{round_number}|capture_reset|{key}", flush=True)
            self.pending_capture = None
        if status == "capture" and old != "capture":
            self.pending_capture = key
            self.capture_seen_round = round_number
        if (status == "capture" and key == self.pending_capture
                and self.capture_seen_round is not None
                and round_number - self.capture_seen_round > 10):
            print(f"LARP_EVENT|{round_number}|capture_stalled|{key}", flush=True)
            self.capture_seen_round = round_number
        self.previous_states[key] = status

    def group_snapshot(self, me):
        visible = cambc.vision.visible_tiles()
        groups = game_map.camp_groups()
        statuses = {}
        for group in groups:
            status = self._status(group, visible)
            statuses[group_key(group)] = status
            if status != "unknown":
                self._record_state(group, status)
        return groups, statuses

    def _nearest_group(self, me, groups, statuses, wanted):
        current = me.position()
        options = []
        for group in groups:
            key = group_key(group)
            status = statuses[key]
            if status not in wanted:
                continue
            tiles = group.spawn_tiles().positions()
            if not tiles:
                continue
            nearest = min(distance(current, tile) for tile in tiles)
            # Prefer nearer work. Reward value breaks equal-distance ties only.
            options.append((nearest, -group.gem_value(), key, group))
        return min(options)[3] if options else None

    def choose_group(self, me, groups, statuses):
        by_id = {group_key(group): group for group in groups}
        if self.target_id in by_id:
            current = by_id[self.target_id]
            status = statuses[self.target_id]
            if status != "respawning":
                return current
            self.target_id = None

        # Finish visible cleared camps before beginning more work.
        target = self._nearest_group(me, groups, statuses, {"capture"})
        if target is None:
            target = self._nearest_group(me, groups, statuses, {"alive", "unknown"})
        self.target_id = group_key(target) if target is not None else None
        return target

    @staticmethod
    def _move_to_any(me, candidates, current, blocked):
        ordered = sorted(candidates, key=lambda p: (distance(current, p), p.y, p.x))
        for tile in ordered:
            if tile == current:
                return True
            if blocked.is_set(tile):
                continue
            if me.move_towards(tile):
                return True
        return False

    def capture(self, me, group):
        current = me.position()
        spawn_tiles = group.spawn_tiles()
        if spawn_tiles.is_set(current):
            self.pending_capture = group_key(group)
            if self.capture_seen_round is None:
                self.capture_seen_round = cambc.round_number()
            return True
        blocked = blocked_tiles(me)
        candidates = [tile for tile in spawn_tiles.positions() if not blocked.is_set(tile)]
        if self._move_to_any(me, candidates, current, blocked):
            return True
        self.no_progress += 1
        return False

    def approach(self, me, group):
        # Move to legal tiles within basic-attack range, never onto any tile in
        # this group's spawn mask. The SDK handles actual terrain navigation.
        current = me.position()
        attack_range = max(1, me.attack_range())
        spawn_tiles = group.spawn_tiles()
        blocked = blocked_tiles(me)
        preferred, fallback = [], []
        for spawn in spawn_tiles.positions():
            area = cambc.Bitboard()
            area.draw_chebyshev(spawn, attack_range)
            for tile in area.positions():
                if spawn_tiles.is_set(tile) or blocked.is_set(tile):
                    continue
                d = distance(spawn, tile)
                if d == attack_range:
                    preferred.append(tile)
                elif d < attack_range:
                    fallback.append(tile)
        if self._move_to_any(me, preferred or fallback, current, blocked):
            return True
        # If all nearby approaches are blocked, try a free empty spawn tile as
        # a discovery waypoint; the move API safely rejects hidden blockers.
        empty_spawns = [tile for tile in spawn_tiles.positions() if not blocked.is_set(tile)]
        return self._move_to_any(me, empty_spawns, current, blocked)

    def vacate_camps(self, me, groups):
        """Move off spawn tiles if no objective is presently available."""
        current = me.position()
        all_spawn_tiles = cambc.Bitboard()
        for group in groups:
            all_spawn_tiles |= group.spawn_tiles()
        if not all_spawn_tiles.is_set(current):
            return False
        blocked = blocked_tiles(me)
        nearby = cambc.Bitboard()
        nearby.draw_chebyshev(current, 1)
        exits = [tile for tile in nearby.positions()
                 if not all_spawn_tiles.is_set(tile) and not blocked.is_set(tile)]
        if self._move_to_any(me, exits, current, blocked):
            print(f"LARP_EVENT|{cambc.round_number()}|vacate_spawn|{self.target_id}", flush=True)
            return True
        return False

    def bank(self, me):
        if me.gem_count() <= 0:
            return False
        current = me.position()
        altars = game_map.altars().positions()
        if not altars:
            return False
        locks = [cambc.vision.has_altar_lock(altar) for altar in altars]
        ranked = sorted(zip(locks, altars), key=lambda item: (item[0], distance(current, item[1])))

        for locked, altar in ranked:
            if distance(current, altar) <= cambc.constants.SUBMIT_GEMS_RANGE:
                # A tribute attempt against a lock is documented to attack it.
                me.submit_gems(altar)
                return True

        blocked = blocked_tiles(me)
        for _, altar in ranked:
            goals = cambc.Bitboard()
            goals.draw_chebyshev(altar, cambc.constants.SUBMIT_GEMS_RANGE)
            goals.set(altar, False)
            candidates = [tile for tile in goals.positions() if not blocked.is_set(tile)]
            if self._move_to_any(me, candidates, current, blocked):
                return True
        return False

    def clear_target(self):
        self.target_id = None
        self.no_progress = 0

