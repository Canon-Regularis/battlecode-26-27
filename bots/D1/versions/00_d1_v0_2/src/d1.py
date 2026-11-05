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
        self.respawn_until = {}

    def _refresh_groups(self):
        goals = cambc.Bitboard()
        respawning = cambc.Bitboard()
        round_no = cambc.round_number()
        visible = cambc.vision.visible_tiles()
        for group in self.groups:
            key = int(group)
            mask = self.masks[key]
            if not (mask & visible).is_empty():
                try:
                    state = group.state()
                    if isinstance(state, game_map.CampGroupRespawning):
                        self.respawn_until[key] = round_no + max(1, state.timer) + 1
                        respawning |= mask
                        continue
                    if isinstance(state, (game_map.CampGroupAlive,
                                          game_map.CampGroupRewardAvailable)):
                        self.respawn_until.pop(key, None)
                except cambc.Error:
                    pass
            if self.respawn_until.get(key, -1) >= round_no:
                respawning |= mask
            else:
                goals |= mask
        goals &= ~respawning
        return goals, respawning

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

    def _bank(self, me):
        if me.gem_count() <= 0:
            return False
        altars = game_map.altars().positions()
        visible = cambc.vision.visible_tiles()
        options = []
        for altar in altars:
            if visible.is_set(altar):
                try:
                    if cambc.vision.has_altar_lock(altar):
                        continue
                except cambc.Error:
                    pass
            distance = me.position().chebyshev_distance(altar)
            options.append((distance, altar.y, altar.x, altar))
        if not options:
            return False
        altar = min(options)[3]
        if me.position().chebyshev_distance(altar) <= 1:
            try:
                me.submit_gems(altar)
                return True
            except cambc.Error:
                return False
        goals = _nearby_positions(altar, cambc.constants.SUBMIT_GEMS_RANGE)
        goals.set(altar, False)
        return self._step_toward(me, goals)

    def _attack_camp(self, me):
        camps = cambc.vision.camps()
        attack_tiles = me.attack_tiles()
        records = []
        live_positions = set()
        for camp in camps:
            try:
                if not camp.is_visible() or camp.health() <= 0:
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
        if self._bank(me):
            return

        goals, respawning = self._refresh_groups()
        if respawning.is_set(me.position()):
            self._step_toward(me, goals)
            return

        if self._attack_enemy(me):
            return
        self._attack_camp(me)
        self._step_toward(me, goals)
        # Melee champions may still attack after moving. Ranged champions will
        # report no attack allowance, so this naturally preserves their action.
        if me.can_attack():
            self._attack_camp(me)
        # Rotate deterministic within-team processing order each round.
        me.set_priority(1 + ((cambc.round_number() * 17 + int(me) * 13) % 100))
