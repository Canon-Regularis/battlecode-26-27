"""Stage 1 camp, capture, respawn and altar navigation policy."""

import cambc
from cambc import game_map


def distance(a, b):
    return a.chebyshev_distance(b)


def distance_to_bounds(position, bounds):
    min_x, min_y, max_x, max_y = bounds
    dx = max(min_x - position.x, 0, position.x - max_x)
    dy = max(min_y - position.y, 0, position.y - max_y)
    return max(dx, dy)


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
        self.group_masks = {}
        self.group_values = {}
        self.group_bounds = {}
        self.all_spawn_tiles = cambc.Bitboard()
        self.approach_fields = {}
        self.approach_candidates = {}
        self.nav_fail_logged = set()
        self.at_approach_root = False
        self.last_approach_key = None
        self.failed_approach_roots = {}
        self.static_blocked = None
        self.slot = None
        self.target_id = None
        self.failed_until = {}
        self.previous_states = {}
        self.respawn_until = {}
        self.pending_capture = None
        self.capture_seen_round = None
        self.no_progress = 0
        self.last_position = None
        self.last_progress_round = None
        self.respawn_tiles = cambc.Bitboard()
        self.respawn_positions = []

    def set_slot(self, slot):
        self.slot = slot if slot is not None and 0 <= slot < cambc.shared_memory.size() else None

    def _assignments(self):
        values = bytearray(min(8, cambc.shared_memory.size()))
        cambc.shared_memory.read(0, values)
        return values

    def _save_assignments(self, values):
        cambc.shared_memory.write(0, values)

    def release_assignment(self):
        if self.slot is None:
            return
        values = self._assignments()
        values[self.slot] = 0
        self._save_assignments(values)
        self.target_id = None

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
            self.group_masks = {
                group_key(group): group.spawn_tiles()
                for group in self.groups
            }
            self.group_values = {
                group_key(group): group.gem_value()
                for group in self.groups
            }
            self.group_bounds = {
                group_key(group): (
                    min(tile.x for tile in self.group_tiles[group_key(group)]),
                    min(tile.y for tile in self.group_tiles[group_key(group)]),
                    max(tile.x for tile in self.group_tiles[group_key(group)]),
                    max(tile.y for tile in self.group_tiles[group_key(group)]),
                )
                for group in self.groups
            }
            for mask in self.group_masks.values():
                self.all_spawn_tiles |= mask
        groups = self.groups
        statuses = {}
        self.respawn_tiles = cambc.Bitboard()
        self.respawn_positions = []
        round_number = cambc.round_number()
        for group in groups:
            key = group_key(group)
            in_vision = not (self.group_masks[key] & visible).is_empty()
            if in_vision:
                try:
                    state = group.state()
                except cambc.Error:
                    state = None
            else:
                state = None
            if isinstance(state, game_map.CampGroupRespawning):
                self.respawn_until[key] = round_number + max(1, state.timer) + 1
                status = "respawning"
            elif isinstance(state, game_map.CampGroupAlive):
                self.respawn_until.pop(key, None)
                status = "alive"
            elif isinstance(state, game_map.CampGroupRewardAvailable):
                self.respawn_until.pop(key, None)
                status = "capture"
            else:
                status = "unknown"
                if self.respawn_until.get(key, -1) >= round_number:
                    status = "respawning"
                elif key in self.respawn_until:
                    self.respawn_until.pop(key, None)
            statuses[key] = status
            if status != "unknown":
                self._record_state(group, status)
            if status == "respawning":
                self.respawn_tiles |= group.spawn_tiles()
                self.respawn_positions.extend(self.group_tiles[key])
                if group.spawn_tiles().is_set(me.position()):
                    print(f"LARP_EVENT|{round_number}|respawn_block_risk|{key}", flush=True)
        if self.slot is not None and self.target_id is not None:
            if statuses.get(self.target_id) == "respawning":
                self.release_assignment()
        return groups, statuses

    def visible_camps(self, groups=None):
        """Use the native visible-camp list, falling back around stale handles."""
        try:
            candidates = cambc.vision.camps()
        except cambc.Error:
            candidates = None
        if candidates is not None:
            result = []
            for camp in candidates:
                try:
                    if camp.is_visible() and camp.health() > 0:
                        result.append(camp)
                except cambc.Error:
                    continue
            return result

        result = []
        for group in groups if groups is not None else (self.groups or ()):
            for camp in group.camps():
                try:
                    if camp.is_visible():
                        result.append(camp)
                except cambc.Error:
                    continue
        return result

    def _nearest_group(self, me, groups, statuses, wanted, excluded=None):
        current = me.position()
        options = []
        for group in groups:
            key = group_key(group)
            status = statuses[key]
            if status not in wanted or (excluded and key in excluded):
                continue
            tiles = self.group_tiles[key]
            if not tiles:
                continue
            nearest = distance_to_bounds(current, self.group_bounds[key])
            # Prefer nearer work. Reward value breaks equal-distance ties only.
            options.append((nearest, -group.gem_value(), key, group))
        return min(options)[3] if options else None

    def choose_group(self, me, groups, statuses):
        round_number = cambc.round_number()
        for key, expiry in list(self.failed_until.items()):
            if expiry < round_number:
                self.failed_until.pop(key, None)
        by_id = {group_key(group): group for group in groups}
        assignments = self._assignments() if self.slot is not None else bytearray()
        if self.slot is not None and self.target_id is None and assignments[self.slot]:
            remembered = assignments[self.slot] - 1
            if statuses.get(remembered) != "respawning" and remembered in by_id:
                self.target_id = remembered

        if self.target_id in by_id:
            current = by_id[self.target_id]
            status = statuses[self.target_id]
            if status != "respawning":
                return current
            self.release_assignment()

        failed = {key for key, expiry in self.failed_until.items()
                  if expiry >= round_number}
        teammate_claims = set()
        if self.slot is not None:
            for index, value in enumerate(assignments):
                if index != self.slot and value:
                    key = value - 1
                    if statuses.get(key) != "respawning":
                        teammate_claims.add(key)

        # Score each camp once; the old priority passes scanned every group as
        # many as three times on maps such as Lanes with dozens of groups.
        best_free_capture = None
        best_free_farm = None
        best_capture = None
        best_farm = None
        current_position = me.position()
        for group in groups:
            key = group_key(group)
            status = statuses[key]
            if status not in {"capture", "alive", "unknown"} or key in failed:
                continue
            tiles = self.group_tiles[key]
            if not tiles:
                continue
            nearest = distance_to_bounds(current_position, self.group_bounds[key])
            option = (nearest, -self.group_values[key], key, group)
            if status == "capture":
                if best_capture is None or option[:3] < best_capture[:3]:
                    best_capture = option
                if key not in teammate_claims and (best_free_capture is None
                                                   or option[:3] < best_free_capture[:3]):
                    best_free_capture = option
            else:
                if best_farm is None or option[:3] < best_farm[:3]:
                    best_farm = option
                if key not in teammate_claims and (best_free_farm is None
                                                   or option[:3] < best_free_farm[:3]):
                    best_free_farm = option
        if best_free_capture is not None:
            target = best_free_capture[3]
        elif best_free_farm is not None:
            target = best_free_farm[3]
        elif best_capture is not None:
            target = best_capture[3]
        elif best_farm is not None:
            target = best_farm[3]
        else:
            target = None
        self.target_id = group_key(target) if target is not None else None
        if self.slot is not None:
            assignments[self.slot] = self.target_id + 1 if self.target_id is not None else 0
            self._save_assignments(assignments)
        return target

    def _safe_move_towards(self, me, goal, blocked):
        """Use SDK navigation except when its next step could block a respawn."""
        current = me.position()
        adjacent_respawn = any(distance(current, tile) <= 2
                               for tile in self.respawn_positions)
        if self.respawn_tiles.is_empty() or not adjacent_respawn:
            try:
                return me.move_towards(goal)
            except cambc.Error:
                # SDK routes can become blocked by a newly visible occupant.
                return False

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
        if not candidates:
            return False
        # The common path finds one closest goal in linear time. Only after a
        # failed route do we sort the small candidate set to rotate alternatives.
        if self.no_progress:
            ordered = sorted(candidates, key=lambda p: (distance(current, p), p.y, p.x))
            tile = ordered[self.no_progress % len(ordered)]
        else:
            tile = min(candidates, key=lambda p: (distance(current, p), p.y, p.x))
        if tile == current:
            return True
        if blocked.is_set(tile):
            return False
        return self._safe_move_towards(me, tile, blocked)

    def _approach_field(self, group, attack_range, current):
        key = (group_key(group), int(attack_range))
        self.last_approach_key = key
        cached = self.approach_fields.get(key)
        if cached is not None:
            return cached
        if self.static_blocked is None:
            blocked = (game_map.walls() | game_map.holes() | game_map.altars()
                       | game_map.spawn_region(cambc.Team.ENEMY))
            self.static_blocked = blocked

        candidates = self.approach_candidates.get(key)
        if candidates is None:
            candidates = []
            radius = int(attack_range)
            group_mask = self.group_masks[key[0]]
            for spawn in self.group_tiles[key[0]]:
                for dy in range(-radius, radius + 1):
                    for dx in range(-radius, radius + 1):
                        distance_from_spawn = max(abs(dx), abs(dy))
                        if distance_from_spawn == 0 or distance_from_spawn > attack_range:
                            continue
                        tile = cambc.Vec2(spawn.x + dx, spawn.y + dy)
                        if (game_map.is_in_bounds(tile) and not self.all_spawn_tiles.is_set(tile)
                                and not self.static_blocked.is_set(tile)):
                            candidates.append(tile)
            self.approach_candidates[key] = candidates
        excluded = self.failed_approach_roots.get(key[0], set())
        roots = cambc.Bitboard()
        for tile in candidates:
            if (tile.x, tile.y) not in excluded:
                roots.set(tile)
        if roots.is_empty():
            return None
        field = cambc.DistanceField()
        destinations = cambc.Bitboard()
        destinations.set(current)
        # Cap optional path expansion; a farther or partitioned camp is skipped
        # after one cheap failed attempt instead of consuming most turn fuel.
        field.compute_to(self.static_blocked, roots, destinations, cambc.Bitboard(), 64)
        self.approach_fields[key] = field
        return field

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
        # Reuse one native distance field per group/range. The SDK convenience
        # navigator recomputes a whole-map field on every call, which profiling
        # showed can consume 1.6M fuel per turn on Rows.
        current = me.position()
        attack_range = max(1, me.attack_range())
        key = (group_key(group), int(attack_range))
        self.at_approach_root = False
        blocked = blocked_tiles(me)
        blocked |= self.respawn_tiles
        if cambc.fuel_remaining() < 1_200_000:
            # Preserve a large fuel reserve on crowded maps. A local legal step
            # toward the camp is cheaper than expanding another distance field.
            current_distance = distance_to_bounds(current, self.group_bounds[key[0]])
            reachable = blocked.reachable_tiles(
                current, me.base_stats().base_move_speed
            ).positions()
            best = min(reachable, key=lambda tile: (
                distance_to_bounds(tile, self.group_bounds[key[0]]), tile.y, tile.x
            ), default=None)
            if best is None or distance_to_bounds(best, self.group_bounds[key[0]]) >= current_distance:
                return False
            try:
                return me.move_absolute(best)
            except cambc.Error:
                return False
        field = self._approach_field(group, attack_range, current)
        if field is None:
            return False
        current_distance = field.get(current)
        self.at_approach_root = current_distance == 0
        reachable = blocked.reachable_tiles(
            current, me.base_stats().base_move_speed
        ).positions()
        best = min([current, *reachable], key=field.get)
        if field.get(best) < current_distance:
            try:
                return me.move_absolute(best)
            except cambc.Error:
                return False
        # Being on an approach tile is not useful if no target can be acted on;
        # report no progress so the caller can abandon stale/hidden objectives.
        if key not in self.nav_fail_logged:
            self.nav_fail_logged.add(key)
            print(f"LARP_NAV_FAIL|{key[0]}|{current.x},{current.y}|{current_distance}|"
                  f"{field.get(best)}|{len(reachable)}", flush=True)
        return False

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

    def vacate_respawning_tile(self, me):
        """Leave an occupied respawn tile before banking or pursuing work."""
        current = me.position()
        if not self.respawn_tiles.is_set(current) or not me.can_move():
            return False
        blocked = blocked_tiles(me)
        steps = []
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                tile = cambc.Vec2(current.x + dx, current.y + dy)
                if (game_map.is_in_bounds(tile) and not self.respawn_tiles.is_set(tile)
                        and not blocked.is_set(tile)):
                    steps.append(tile)
        # Prefer the least congested local exit; stable coordinates break ties.
        steps.sort(key=lambda tile: (
            -sum(1 for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                if game_map.is_in_bounds(cambc.Vec2(tile.x + dx, tile.y + dy))
                and not blocked.is_set(cambc.Vec2(tile.x + dx, tile.y + dy))),
            tile.y, tile.x))
        for tile in steps:
            try:
                if me.move_absolute(tile):
                    print(f"LARP_EVENT|{cambc.round_number()}|vacate_respawn|{self.target_id}", flush=True)
                    return True
            except cambc.Error:
                continue
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
            for camp in self.visible_camps()
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
        self.release_assignment()
        self.no_progress = 0

    def mark_unreachable(self, target_id):
        if target_id is not None:
            self.failed_until[target_id] = cambc.round_number() + 20

    def exclude_approach_root(self, target_id, position):
        if self.last_approach_key is None or self.last_approach_key[0] != target_id:
            return
        roots = self.failed_approach_roots.setdefault(target_id, set())
        roots.add((position.x, position.y))
        self.approach_fields.pop(self.last_approach_key, None)

