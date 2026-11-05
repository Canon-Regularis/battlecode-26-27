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
        # Static map queries are cached lazily because the API documentation
        # disagrees about camp-group access during drafting.
        self.groups = None
        self.group_tiles = {}
        self.target_id = None
        self.previous_states = {}
        self.pending_capture = None
        self.capture_seen_round = None
        self.no_progress = 0
        self.last_position = None
        self.last_progress_round = None
        self.respawn_tiles = cambc.Bitboard()
        self.respawn_positions = []

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
        self.previous_states[key] = status

    def group_snapshot(self, me):
        visible = cambc.vision.visible_tiles()
        if self.groups is None:
            self.groups = game_map.camp_groups()
            self.group_tiles = {
                group_key(group): group.spawn_tiles().positions()
                for group in self.groups
            }
        groups = self.groups
        statuses = {}
        self.respawn_tiles = cambc.Bitboard()
        self.respawn_positions = []
        for group in groups:
            key = group_key(group)
            in_vision = any(visible.is_set(tile) for tile in self.group_tiles[key])
            status = self._status(group, visible) if in_vision else "unknown"
            statuses[key] = status
            if status != "unknown":
                self._record_state(group, status)
            if status == "respawning":
                self.respawn_tiles |= group.spawn_tiles()
                self.respawn_positions.extend(self.group_tiles[key])
        return groups, statuses

    def _nearest_group(self, me, groups, statuses, wanted):
        current = me.position()
        options = []
        for group in groups:
            key = group_key(group)
            status = statuses[key]
            if status not in wanted:
                continue
            tiles = self.group_tiles[key]
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

    def _safe_move_towards(self, me, goal, blocked):
        """Use SDK navigation except when its next step could block a respawn."""
        current = me.position()
        adjacent_respawn = any(distance(current, tile) <= 1
                               for tile in self.respawn_positions)
        if self.respawn_tiles.is_empty() or not adjacent_respawn:
            return me.move_towards(goal)

        # The built-in navigator cannot accept caller-supplied forbidden tiles.
        # Only at the immediate hazard, try legal adjacent steps that avoid the
        # respawn region. This local detour keeps normal routes on move_towards.
        if not me.can_move() or self.respawn_tiles.is_set(goal):
            return False
        steps = []
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                step = cambc.Vec2(current.x + dx, current.y + dy)
                if (not game_map.is_in_bounds(step) or self.respawn_tiles.is_set(step)
                        or blocked.is_set(step)):
                    continue
                steps.append(step)
        steps.sort(key=lambda tile: (distance(tile, goal), tile.y, tile.x))
        for step in steps:
            try:
                if me.move_absolute(step):
                    return True
            except cambc.Error:
                # Visible occupants can change between the mask and this action.
                continue
        return False

    def _move_to_any(self, me, candidates, current, blocked):
        ordered = sorted(candidates, key=lambda p: (distance(current, p), p.y, p.x))
        if not ordered:
            return False
        # A failed move_towards can trigger a full map search. Try one stable
        # candidate per turn and rotate after failure instead of scanning all.
        tile = ordered[self.no_progress % len(ordered)]
        if tile == current:
            return True
        if blocked.is_set(tile):
            return False
        return self._safe_move_towards(me, tile, blocked)

    def capture(self, me, group):
        current = me.position()
        spawn_tiles = group.spawn_tiles()
        if spawn_tiles.is_set(current):
            self.pending_capture = group_key(group)
            if self.capture_seen_round is None:
                self.capture_seen_round = cambc.round_number()
            elif (self.pending_capture == group_key(group)
                  and cambc.round_number() - self.capture_seen_round > 10):
                print(f"LARP_EVENT|{cambc.round_number()}|capture_stalled|{group_key(group)}", flush=True)
                self.capture_seen_round = cambc.round_number()
            return True
        blocked = blocked_tiles(me)
        candidates = [tile for tile in self.group_tiles[group_key(group)]
                      if not blocked.is_set(tile)]
        moved = self._move_to_any(me, candidates, current, blocked)
        if not moved:
            self.no_progress += 1
        return moved

    def approach(self, me, group):
        # Move to legal tiles within basic-attack range, never onto any tile in
        # this group's spawn mask. The SDK handles actual terrain navigation.
        current = me.position()
        attack_range = max(1, me.attack_range())
        spawn_tiles = group.spawn_tiles()
        blocked = blocked_tiles(me)
        preferred, fallback = [], []
        radius = int(attack_range)
        for spawn in self.group_tiles[group_key(group)]:
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    d = max(abs(dx), abs(dy))
                    if d == 0 or d > attack_range:
                        continue
                    tile = cambc.Vec2(spawn.x + dx, spawn.y + dy)
                    if (not game_map.is_in_bounds(tile) or spawn_tiles.is_set(tile)
                            or blocked.is_set(tile)):
                        continue
                    if d == attack_range:
                        preferred.append(tile)
                    else:
                        fallback.append(tile)
        return self._move_to_any(me, preferred or fallback, current, blocked)

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

    def go_home(self, me):
        """Retreat to spawn for survival and healing using SDK pathfinding."""
        spawns = game_map.spawn_region(cambc.Team.ALLY).positions()
        if not spawns:
            return False
        if game_map.spawn_region(cambc.Team.ALLY).is_set(me.position()):
            return True

        threatened = any(
            camp.is_visible() and camp.health() > 0
            and distance(me.position(), camp.position()) <= 3
            for camp in cambc.vision.camps()
        ) or bool(cambc.vision.champions(cambc.Team.ENEMY))
        if not threatened:
            try:
                me.recall()
                return True
            except cambc.Error:
                pass

        current = me.position()
        blocked = blocked_tiles(me)
        for spawn in sorted(spawns, key=lambda tile: distance(current, tile)):
            if self._safe_move_towards(me, spawn, blocked):
                return True
        return False

    def clear_target(self):
        self.target_id = None
        self.no_progress = 0

