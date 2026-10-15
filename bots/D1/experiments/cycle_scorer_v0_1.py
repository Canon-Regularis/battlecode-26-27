"""D1's resource-cycle policy: clear, capture, and convert gems safely."""

import cambc
from cambc import game_map


CAPTURE_TURNS = 5
UNKNOWN_HP = 0


def _distance(a, b):
    return a.chebyshev_distance(b)


def _nearest(position, points):
    if not points:
        return None, 10**6
    best = min(points, key=lambda p: (_distance(position, p), p.y, p.x))
    return best, _distance(position, best)


def _safe_targets(mask, blocked, current=None):
    return [tile for tile in mask.positions()
            if tile == current or not blocked.is_set(tile)]


def _blocked(me):
    return (game_map.walls() | game_map.holes() | game_map.altars()
            | game_map.spawn_region(cambc.Team.ENEMY)
            | cambc.vision.champion_tiles() | cambc.vision.camp_tiles()
            | cambc.vision.teleport_tiles())


def _path_field(me, blocked):
    origin = cambc.Bitboard()
    origin.set(me.position())
    field = cambc.DistanceField()
    field.compute(blocked & ~origin, origin, cambc.Bitboard())
    return field


def _path_distance(field, position):
    distance = field.get(position)
    # Native distance fields leave unreachable cells at a large sentinel.
    if distance < 0 or distance > game_map.width() * game_map.height():
        return 10**6
    return distance


class D1:
    """One-turn-at-a-time cycle optimizer with visibility-safe memory."""

    def __init__(self):
        self.groups = None
        self.spawn_positions = {}
        self.respawn_until = {}
        self.objective_handle = None

    def _load_groups(self):
        if self.groups is not None:
            return
        self.groups = game_map.camp_groups()
        for group in self.groups:
            self.spawn_positions[int(group)] = group.spawn_tiles().positions()

    def _observed_state(self, group):
        handle = int(group)
        round_no = cambc.round_number()
        mask = group.spawn_tiles()
        if not (mask & cambc.vision.visible_tiles()).is_empty():
            try:
                state = group.state()
                if isinstance(state, game_map.CampGroupRespawning):
                    until = round_no + max(1, state.timer) + 1
                    self.respawn_until[handle] = until
                    return "respawning", state.timer
                if isinstance(state, game_map.CampGroupRewardAvailable):
                    self.respawn_until.pop(handle, None)
                    return "reward", 0
                if isinstance(state, game_map.CampGroupAlive):
                    self.respawn_until.pop(handle, None)
                    return "alive", 0
            except cambc.Error:
                pass
        if self.respawn_until.get(handle, -1) >= round_no:
            return "respawning", self.respawn_until[handle] - round_no
        return "unknown", 0

    def _camp_goals(self, me, group, state, blocked):
        positions = self.spawn_positions[int(group)]
        if state == "reward":
            goals = cambc.Bitboard()
            for position in positions:
                goals.set(position)
            return _safe_targets(goals, blocked, me.position())

        live_positions = []
        for camp in group.camps():
            try:
                if camp.is_visible() and camp.health() <= 0:
                    continue
                live_positions.append(camp.spawn_position())
            except cambc.Error:
                live_positions.append(camp.spawn_position())
        if live_positions:
            positions = live_positions

        radius = max(1, me.attack_range())
        mask = cambc.Bitboard()
        for position in positions:
            mask.draw_chebyshev(position, radius)
        current = me.position()
        attack_tiles = me.attack_tiles()
        can_hit_group = False
        for camp in group.camps():
            try:
                if camp.is_visible() and camp.health() > 0 and attack_tiles.is_set(camp.position()):
                    can_hit_group = True
                    break
            except cambc.Error:
                continue
        # A geometric range tile is not progress if no living member is visible.
        return _safe_targets(mask, blocked, current if can_hit_group else None)

    def _clear_turns(self, me, group, state):
        if state == "reward":
            return 0
        total_hp = 0
        for camp in group.camps():
            try:
                if camp.is_visible():
                    hp = camp.health()
                    if hp > 0:
                        total_hp += hp
                else:
                    total_hp += camp.base_stats().base_health
            except cambc.Error:
                total_hp += UNKNOWN_HP
        # A modest throughput estimate: one attack action per turn, with a
        # bounded bonus for ready damage abilities. It intentionally avoids
        # champion-specific paper-DPS assumptions.
        strength = max(1.0, me.strength())
        clear_turns = max(1, int((total_hp + strength - 1) // strength))
        if me.can_cast():
            ready_damage = any(
                ability.is_ready() and (ability.is_damage() or ability.is_aoe_damage())
                for ability in me.abilities()
            )
            if ready_damage:
                clear_turns = max(1, clear_turns - 1)
        return clear_turns

    def _bank_options(self, me, field, blocked):
        altars = game_map.altars().positions()
        targets = []
        visible = cambc.vision.visible_tiles()
        for altar in altars:
            if visible.is_set(altar):
                try:
                    if cambc.vision.has_altar_lock(altar):
                        continue
                except cambc.Error:
                    pass
            if _distance(me.position(), altar) <= 1:
                return altar, 0, [altar]
            adjacent = cambc.Bitboard()
            adjacent.draw_chebyshev(altar, 1)
            adjacent.set(altar, False)
            blocked = (game_map.walls() | game_map.holes() | game_map.altars()
                       | game_map.spawn_region(cambc.Team.ENEMY)
                       | cambc.vision.champion_tiles()
                       | cambc.vision.camp_tiles())
            legal = _safe_targets(adjacent, blocked)
            ranked = [(_path_distance(field, point), point) for point in legal]
            distance, point = min(ranked, key=lambda row: (row[0], row[1].y, row[1].x)) if ranked else (10**6, None)
            if point is not None:
                targets.append((distance, altar, point))
        if not targets:
            return None, 10**6, []
        distance, altar, point = min(targets, key=lambda row: (row[0], row[1].y, row[1].x))
        return altar, distance, [point]

    def _threat(self, me):
        # Bounded, visibility-only estimate. Unknown opponents are not treated
        # as present, and visible local threats sharply increase bank urgency.
        risk = 0.015
        enemies = cambc.vision.champions(cambc.Team.ENEMY)
        for enemy in enemies:
            try:
                if not enemy.is_visible() or not enemy.is_alive():
                    continue
                distance = _distance(me.position(), enemy.position())
                reach = enemy.attack_range() + 1
                if distance <= reach:
                    risk += 0.16
                elif distance <= reach + 3:
                    risk += 0.06
            except cambc.Error:
                continue
        if me.health() < me.max_health() * 0.35:
            risk += 0.07
        return min(0.55, risk)

    def _invest(self, me):
        # Strength buys are useful only when the champion can shop: Tavi can
        # shop in the field; other farmers buy on spawn during a natural visit.
        if me.champion_name() != cambc.ChampionType.TAVI:
            if not game_map.spawn_region(cambc.Team.ALLY).is_set(me.position()):
                return False
        item = cambc.ItemType.POWER_SHARD_OF_STRENGTH
        count = me.gold_count() // item.cost()
        if count > 0 and me.can_buy(item, count):
            try:
                me.buy(item, count)
                return True
            except cambc.Error:
                return False
        return False

    def _select_cycle(self, me, field, blocked, bank_data, enemies):
        self._load_groups()
        candidates = []
        _, bank_distance, _ = bank_data
        group_count = max(1, len(self.groups))
        ally_positions = []
        for ally in cambc.vision.champions(cambc.Team.ALLY):
            try:
                if int(ally) != int(me) and ally.is_alive():
                    ally_positions.append(ally.position())
            except cambc.Error:
                continue
        for group in self.groups:
            state, _ = self._observed_state(group)
            if state == "respawning":
                continue
            goals = self._camp_goals(me, group, state, blocked)
            ranked = [(_path_distance(field, point), point) for point in goals]
            travel, target = min(ranked, key=lambda row: (row[0], row[1].y, row[1].x)) if ranked else (10**6, None)
            if target is None:
                continue
            clear = self._clear_turns(me, group, state)
            capture = 0 if state == "alive" else CAPTURE_TURNS
            gems = max(0, group.gem_value())
            channel = max(1, int((me.gem_count() + gems + 9) // 10))
            full_cycle = max(1, travel + clear + capture + bank_distance + channel)

            # Penalise only high-confidence risk: visible enemy proximity and
            # access to the enemy spawn side. Unseen threats are uncertainty,
            # not fabricated positions.
            risk_multiplier = 1.0
            enemy_spawns = game_map.spawn_region(cambc.Team.ENEMY).positions()
            _, enemy_side_dist = _nearest(target, enemy_spawns)
            if enemy_side_dist <= 5:
                risk_multiplier *= 0.72
            # Softly deconflict visible allied farmers. This is a preference,
            # not a hard partition: an excellent shared target remains viable.
            if any(
                min(_distance(ally_pos, spawn) for spawn in self.spawn_positions[int(group)]) <= 3
                for ally_pos in ally_positions
            ):
                risk_multiplier *= 0.58
            for enemy in enemies:
                try:
                    if enemy.is_visible() and enemy.is_alive():
                        d = _distance(target, enemy.position())
                        if d <= enemy.attack_range() + 2:
                            risk_multiplier *= 0.65
                except cambc.Error:
                    pass
            value = (gems * risk_multiplier) / full_cycle
            role_tie = (int(group) - int(me)) % group_count
            candidates.append((value, -travel, -role_tie, group, target,
                               state, gems, full_cycle))
        if not candidates:
            self.objective_handle = None
            return None
        best = max(candidates, key=lambda row: row[:3])
        selected = best
        if self.objective_handle is not None:
            for candidate in candidates:
                if int(candidate[3]) == self.objective_handle:
                    # Preserve a useful route to prevent turn-by-turn target
                    # churn. Switch when the new option is materially better.
                    if candidate[0] >= best[0] * 0.78:
                        selected = candidate
                    break
        self.objective_handle = int(selected[3])
        return (selected[3], selected[4], selected[5], selected[6],
                selected[0], selected[7])

    def _attack_group(self, me, group):
        camps = cambc.vision.camps()
        group_id = int(group)
        targets = []
        for camp in camps:
            try:
                if int(camp.camp_group()) != group_id or not camp.is_visible():
                    continue
                if camp.health() > 0 and me.attack_tiles().is_set(camp.position()):
                    targets.append((camp.health(), int(camp), camp))
            except cambc.Error:
                continue
        if me.can_attack() and targets:
            target = min(targets, key=lambda row: (row[0], row[1]))[2]
            try:
                me.attack(target)
                return True
            except cambc.Error:
                pass

        if me.can_cast():
            for ability in me.abilities():
                if not ability.is_ready() or not (ability.is_damage() or ability.is_aoe_damage()):
                    continue
                if not (ability.can_target_camps() or ability.can_target_ground()):
                    continue
                legal = ability.valid_tiles()
                for camp in camps:
                    try:
                        if (int(camp.camp_group()) != group_id or not camp.is_visible()
                                or camp.health() <= 0):
                            continue
                        pos = camp.position()
                        if not legal.is_set(pos):
                            continue
                        target = camp if ability.can_target_camps() else pos
                        if ability.use(target):
                            return True
                    except cambc.Error:
                        continue
        return False

    def _execute_bank(self, me, altar, goals):
        if altar is None or me.gem_count() <= 0:
            return False
        if _distance(me.position(), altar) <= 1:
            try:
                me.submit_gems(altar)
                return True
            except cambc.Error:
                pass
        if me.can_move() and goals:
            target, _ = _nearest(me.position(), goals)
            if target is not None:
                try:
                    return me.move_towards(target)
                except cambc.Error:
                    return False
        return False

    def turn(self):
        me = cambc.me()
        if (not me.is_alive() or me.is_recalling() or me.is_submitting_gems()
                or me.is_teleporting()):
            return

        self._load_groups()
        self._invest(me)
        blocked = _blocked(me)
        field = _path_field(me, blocked)
        bank_data = self._bank_options(me, field, blocked)
        altar, bank_distance, bank_goals = bank_data
        enemies = cambc.vision.champions(cambc.Team.ENEMY)
        cycle = self._select_cycle(me, field, blocked, bank_data, enemies)
        bag = me.gem_count()

        # Banking any collected gems is the controlled low-risk ablation. The
        # prior adaptive hold rule did not beat the simpler score conversion
        # behavior in the first local Packs comparison.
        if bag and altar is not None:
            if self._execute_bank(me, altar, bank_goals):
                return

        if cycle is not None:
            group, target, state, _, _, _ = cycle
            self._attack_group(me, group)
            # Melee champions may attack and move in one turn; ranged champions
            # are protected by their live action state.
            if me.can_move():
                try:
                    me.move_towards(target)
                except cambc.Error:
                    pass
            # Claim a reward-ready group as soon as an eligible tile is reached.
            if state == "reward" and not me.is_submitting_gems():
                for spawn in self.spawn_positions[int(group)]:
                    if me.position() == spawn:
                        break
            return

        if bag and altar is not None:
            self._execute_bank(me, altar, bank_goals)
