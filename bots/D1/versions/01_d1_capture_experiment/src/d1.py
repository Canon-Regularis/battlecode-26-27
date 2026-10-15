"""D1 v0.2: a compact, path-aware camp/capture/deposit loop."""

import cambc
from cambc import game_map


def _blocked():
    return (game_map.walls() | game_map.holes() | game_map.altars()
            | game_map.spawn_region(cambc.Team.ENEMY)
            | cambc.vision.champion_tiles() | cambc.vision.camp_tiles()
            | cambc.vision.teleport_tiles())


def _nearby_positions(position, radius):
    result = cambc.Bitboard()
    result.draw_chebyshev(position, radius)
    return result


class D1:
    """Greedy resource cycle with native pathfinding and minimal state."""

    def __init__(self):
        self.groups = game_map.camp_groups()
        self.masks = {int(group): group.spawn_tiles() for group in self.groups}
        self.by_key = {int(group): group for group in self.groups}
        self.group_health = {
            int(group): sum(camp.base_stats().base_health for camp in group)
            for group in self.groups
        }
        self.respawn_until = {}
        self.objective_handle = None
        self.objective_since = -1
        memory = bytes(cambc.draft_memory)
        self.team_size = memory[2] if len(memory) >= 3 and memory[:2] == b"D1" else 5

    def _refresh_groups(self):
        goals = cambc.Bitboard()
        respawning = cambc.Bitboard()
        states = {}
        round_no = cambc.round_number()
        visible = cambc.vision.visible_tiles()
        for group in self.groups:
            key = int(group)
            mask = self.masks[key]
            state = None
            if not (mask & visible).is_empty():
                try:
                    state = group.state()
                    if isinstance(state, game_map.CampGroupRespawning):
                        self.respawn_until[key] = round_no + max(1, state.timer) + 1
                        respawning |= mask
                        states[key] = "respawning"
                        continue
                    if isinstance(state, (game_map.CampGroupAlive,
                                          game_map.CampGroupRewardAvailable)):
                        self.respawn_until.pop(key, None)
                except cambc.Error:
                    pass
            if self.respawn_until.get(key, -1) >= round_no:
                respawning |= mask
                states[key] = "respawning"
            else:
                goals |= mask
                if isinstance(state, game_map.CampGroupRewardAvailable):
                    states[key] = "reward"
                elif isinstance(state, game_map.CampGroupAlive):
                    states[key] = "alive"
                else:
                    states[key] = "unknown"
        goals &= ~respawning
        return goals, respawning, states

    def _claim_slot(self, me):
        return int(me) % max(1, min(self.team_size, cambc.shared_memory.size()))

    def _write_claim(self, me, key):
        try:
            cambc.shared_memory[self._claim_slot(me)] = 0 if key is None else min(255, key + 1)
        except (cambc.Error, IndexError, ValueError):
            pass

    def _other_claims(self, me):
        claims = set()
        own_slot = self._claim_slot(me)
        for slot in range(max(1, min(self.team_size, cambc.shared_memory.size()))):
            if slot == own_slot:
                continue
            try:
                value = cambc.shared_memory[slot]
                if value:
                    claims.add(value - 1)
            except (cambc.Error, IndexError):
                pass
        return claims

    def _select_group(self, me, states):
        """Choose one camp cycle and hold it through clear and capture."""
        current = me.position()
        round_no = cambc.round_number()
        claims = self._other_claims(me)

        # Never walk away from a cleared group while already occupying its
        # capture region. One body is enough; the others can keep farming.
        for key, state in states.items():
            if state == "reward" and self.masks[key].is_set(current):
                self.objective_handle = key
                self.objective_since = round_no
                self._write_claim(me, key)
                return self.by_key[key]

        # A cleared, unclaimed group is the highest-value immediate objective.
        rewards = []
        for key, state in states.items():
            if state != "reward" or key in claims:
                continue
            distance = min(current.chebyshev_distance(pos)
                           for pos in self.masks[key].positions())
            rewards.append((distance, -self.by_key[key].gem_value(), key))
        if rewards:
            key = min(rewards)[2]
            self.objective_handle = key
            self.objective_since = round_no
            self._write_claim(me, key)
            return self.by_key[key]

        # Retain a live/unknown cycle long enough to finish it. A known respawn
        # or an excessively stale route releases the claim.
        key = self.objective_handle
        if (key in self.by_key and states.get(key) != "respawning"
                and round_no - self.objective_since <= 80):
            self._write_claim(me, key)
            return self.by_key[key]

        strength = max(1.0, me.strength())
        candidates = []
        for group in self.groups:
            key = int(group)
            if states.get(key) == "respawning":
                continue
            distance = min(current.chebyshev_distance(pos)
                           for pos in self.masks[key].positions())
            clear_turns = self.group_health[key] / strength
            value = group.gem_value() + group.gold_value() * 0.08
            score = value / max(1.0, distance + 5.0 + clear_turns)
            if key in claims:
                score *= 0.32
            candidates.append((-score, distance, key))
        if not candidates:
            self.objective_handle = None
            self._write_claim(me, None)
            return None
        key = min(candidates)[2]
        self.objective_handle = key
        self.objective_since = round_no
        self._write_claim(me, key)
        return self.by_key[key]

    def _capture_group(self, me, states):
        """Commit one nearby champion to a cleared group without splitting farmers."""
        current = me.position()
        rewards = [key for key, state in states.items() if state == "reward"]
        for key in rewards:
            if self.masks[key].is_set(current):
                return self.by_key[key]

        occupied = set()
        for ally in cambc.vision.champions(cambc.Team.ALLY):
            try:
                if int(ally) == int(me) or not ally.is_alive():
                    continue
                for key in rewards:
                    if self.masks[key].is_set(ally.position()):
                        occupied.add(key)
            except cambc.Error:
                continue

        candidates = []
        for key in rewards:
            if key in occupied:
                continue
            distance = min(current.chebyshev_distance(pos)
                           for pos in self.masks[key].positions())
            candidates.append((distance, -self.by_key[key].gem_value(), key))
        return self.by_key[min(candidates)[2]] if candidates else None

    def _step_toward(self, me, goals):
        if not me.can_move() or goals.is_empty():
            return False
        origin = me.position()
        blocked = _blocked()
        camp_tiles = cambc.vision.camp_tiles()
        goals &= (~blocked | camp_tiles)
        if goals.is_empty():
            return False
        if goals.count() == 1:
            target = goals.positions()[0]
            if not blocked.is_set(target):
                try:
                    return me.move_towards(target)
                except cambc.Error:
                    return False

        origin_mask = cambc.Bitboard()
        origin_mask.set(origin)
        movable = blocked & ~origin_mask
        field = cambc.DistanceField()
        field.compute_to(movable & ~goals, goals, origin_mask, cambc.Bitboard())
        reachable = movable.reachable_tiles(origin, me.base_stats().base_move_speed)
        candidates = [origin, *reachable.positions()]
        best = min(candidates, key=field.get)
        if field.get(best) >= field.get(origin):
            return False
        try:
            return me.move_absolute(best)
        except cambc.Error:
            return False

    def _altar_goals(self, me, submit_if_in_range=True):
        """Return every currently viable tribute approach tile."""
        goals = cambc.Bitboard()
        current = me.position()
        for altar in game_map.altars().positions():
            try:
                if cambc.vision.has_altar_lock(altar):
                    continue
            except cambc.Error:
                pass
            if (submit_if_in_range
                    and current.chebyshev_distance(altar) <= cambc.constants.SUBMIT_GEMS_RANGE):
                try:
                    if me.submit_gems(altar):
                        return None
                except cambc.Error:
                    continue
            approach = _nearby_positions(altar, cambc.constants.SUBMIT_GEMS_RANGE)
            approach.set(altar, False)
            goals |= approach
        return goals

    def _bank(self, me):
        if me.gem_count() <= 0:
            return False
        goals = self._altar_goals(me)
        if goals is None:
            return True
        return self._step_toward(me, goals)

    def _vacate_respawning_tile(self, me, respawning, route_goals):
        """Leave a known respawn tile without asking the global pathfinder to cross it."""
        current = me.position()
        if not me.can_move() or not respawning.is_set(current):
            return False
        blocked = _blocked() | respawning
        blocked.set(current, False)
        candidates = []
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                tile = cambc.Vec2(current.x + dx, current.y + dy)
                if game_map.is_in_bounds(tile) and not blocked.is_set(tile):
                    candidates.append(tile)
        if not candidates:
            return False
        route_positions = route_goals.positions()
        if route_positions:
            candidates.sort(key=lambda tile: (
                min(tile.chebyshev_distance(goal) for goal in route_positions),
                tile.y, tile.x
            ))
        else:
            candidates.sort(key=lambda tile: (tile.y, tile.x))
        try:
            return me.move_absolute(candidates[0])
        except cambc.Error:
            return False

    def _attack_camp(self, me, preferred_group=None):
        camps = cambc.vision.camps()
        attack_tiles = me.attack_tiles()
        records = []
        live_positions = set()
        preferred_key = int(preferred_group) if preferred_group is not None else None
        for camp in camps:
            try:
                if not camp.is_visible() or camp.health() <= 0:
                    continue
                if preferred_key is not None and int(camp.camp_group()) != preferred_key:
                    continue
                position = camp.position()
                live_positions.add((position.x, position.y))
                if attack_tiles.is_set(position):
                    records.append((camp, position, camp.health()))
            except cambc.Error:
                continue

        attacked = False
        if me.can_attack() and records:
            is_varg = me.champion_name() == cambc.ChampionType.VARG
            def rank(record):
                camp, position, health = record
                splash = 0
                if is_varg:
                    splash = sum((position.x + dx, position.y + dy) in live_positions
                                 for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                                 if dx or dy)
                return (-splash, health, int(camp))
            target = min(records, key=rank)[0]
            try:
                me.attack(target)
                attacked = True
            except cambc.Error:
                pass

        # Spend an attack-reset cast before an ordinary damage cast; doing it
        # in the opposite order loses the reset's extra camp hit.
        if attacked and me.can_cast():
            for ability in me.abilities():
                if not ability.is_attack_reset() or not ability.is_ready():
                    continue
                try:
                    if not ability.use():
                        continue
                    if me.can_attack():
                        current_tiles = me.attack_tiles()
                        for camp, position, _ in records:
                            if current_tiles.is_set(position):
                                me.attack(camp)
                                break
                    break
                except cambc.Error:
                    continue

        # Varg can trade a shield for another safe capture cycle; use it only
        # when health is low and a live camp can retaliate at close range.
        if (me.champion_name() == cambc.ChampionType.VARG
                and me.health() <= me.max_health() * 0.60 and me.can_cast()):
            threatened = any(
                camp.is_visible() and camp.health() > 0
                and me.position().chebyshev_distance(camp.position()) <= 3
                for camp in camps
            )
            if threatened:
                for ability in me.abilities():
                    if ability.is_shield() and ability.is_ready():
                        try:
                            return ability.use()
                        except cambc.Error:
                            break

        # Use documented damage abilities when they can hit a visible camp.
        if me.can_cast():
            for ability in me.abilities():
                if not ability.is_ready() or not (ability.is_damage() or ability.is_aoe_damage()):
                    continue
                if not (ability.can_target_camps() or ability.can_target_ground()):
                    continue
                legal = ability.valid_tiles()
                for camp in camps:
                    try:
                        if not camp.is_visible() or camp.health() <= 0:
                            continue
                        if preferred_key is not None and int(camp.camp_group()) != preferred_key:
                            continue
                        position = camp.position()
                        if not legal.is_set(position):
                            continue
                        target = camp if ability.can_target_camps() else position
                        if ability.use(target):
                            attacked = True
                            break
                    except cambc.Error:
                        continue
                if attacked:
                    break

        return attacked

    def _attack_enemy(self, me):
        if not me.can_attack():
            return False
        attack_tiles = me.attack_tiles()
        targets = []
        carriers = []
        for enemy in cambc.vision.champions(cambc.Team.ENEMY):
            try:
                if not enemy.is_visible() or not enemy.is_alive():
                    continue
                if not attack_tiles.is_set(enemy.position()):
                    continue
                item = (enemy.health(), int(enemy), enemy)
                targets.append(item)
                if enemy.gem_count() > 0 and enemy.health() <= me.strength():
                    carriers.append((enemy.gem_count(), *item))
            except cambc.Error:
                continue
        if carriers:
            target = min(carriers, key=lambda item: (-item[0], item[1], item[2]))[3]
        elif targets:
            target = min(targets, key=lambda item: (item[0], item[1]))[2]
        else:
            return False
        try:
            me.attack(target)
            return True
        except cambc.Error:
            return False

    def _invest(self, me):
        if (me.champion_name() != cambc.ChampionType.TAVI
                and not game_map.spawn_region(cambc.Team.ALLY).is_set(me.position())):
            return
        item = cambc.ItemType.POWER_SHARD_OF_STRENGTH
        count = me.gold_count() // item.cost()
        if count and me.can_buy(item, count):
            try:
                me.buy(item, count)
            except cambc.Error:
                pass

    def turn(self):
        me = cambc.me()
        if (not me.is_alive() or me.is_recalling() or me.is_submitting_gems()
                or me.is_teleporting()):
            return
        self._invest(me)
        goals, respawning, states = self._refresh_groups()
        if respawning.is_set(me.position()):
            route_goals = self._altar_goals(me, False) if me.gem_count() > 0 else goals
            if route_goals is None:
                return
            self._vacate_respawning_tile(me, respawning, route_goals)
            return

        if self._bank(me):
            return

        group = self._capture_group(me, states)
        group_goals = self.masks[int(group)] if group is not None else goals

        if self._attack_enemy(me):
            return
        self._attack_camp(me)
        self._step_toward(me, group_goals)
        # Melee champions may still attack after moving. Ranged champions will
        # report no attack allowance, so this naturally preserves their action.
        if me.can_attack():
            self._attack_camp(me)
        # Rotate deterministic within-team processing order each round.
        me.set_priority(1 + ((cambc.round_number() * 17 + int(me) * 13) % 100))
