"""Starter-derived Stage 1 policy used as a controlled challenger.

This deliberately keeps the objective loop small: attack visible camps, move to
the nearest available camp tiles with the SDK navigator, and bank any gems.
The module is independent from the persistent ObjectivePolicy so benchmark
results can separate navigation/state-machine effects from champion picks.
"""

import cambc
from cambc import game_map
from randomness import below

from combat import clear_turn


Team = cambc.Team
Item = cambc.ItemType
PURCHASE_SHARD = Item.POWER_SHARD_OF_STRENGTH


def tiles_around(position, radius):
    tiles = cambc.Bitboard()
    tiles.draw_chebyshev(position, radius)
    return tiles


def blocked_tiles(me):
    blocked = (game_map.walls() | game_map.holes() | game_map.altars()
               | game_map.spawn_region(Team.ENEMY) | cambc.vision.champion_tiles()
               | cambc.vision.camp_tiles() | cambc.vision.teleport_tiles())
    blocked.set(me.position(), False)
    return blocked


def move_towards_closest(me, goals):
    origin = me.position()
    if not me.can_move() or goals.is_set(origin):
        return False
    blocked = blocked_tiles(me)
    camp_tiles = cambc.vision.camp_tiles()
    goals &= ~blocked | camp_tiles
    if goals.is_empty():
        return False
    if goals.count() == 1:
        goal = goals.positions()[0]
        if not blocked.is_set(goal):
            try:
                return me.move_towards(goal)
            except cambc.Error:
                return False

    field = cambc.DistanceField()
    origin_mask = cambc.Bitboard()
    origin_mask.set(origin)
    field.compute_to(blocked & ~goals, goals, origin_mask, cambc.Bitboard())
    reachable = blocked.reachable_tiles(origin, me.base_stats().base_move_speed)
    step = min([origin, *reachable.positions()], key=field.get)
    if step == origin:
        return False
    try:
        return me.move_absolute(step)
    except cambc.Error:
        return False


class Bot:
    """Small benchmark challenger with starter turn ordering."""

    def __init__(self):
        self.groups = None
        self.group_masks = {}
        self.all_spawn_tiles = cambc.Bitboard()
        self.respawn_until = {}

    def ensure_groups(self):
        if self.groups is not None:
            return
        self.groups = game_map.camp_groups()
        self.group_masks = {int(group): group.spawn_tiles() for group in self.groups}
        for mask in self.group_masks.values():
            self.all_spawn_tiles |= mask

    def buy_shard(self, me):
        item = PURCHASE_SHARD
        count = me.gold_count() // item.cost()
        if count and me.can_buy(item, count):
            me.buy(item, count)

    def available_camp_goals(self):
        self.ensure_groups()
        goals = cambc.Bitboard()
        respawning_tiles = cambc.Bitboard()
        visible = cambc.vision.visible_tiles()
        round_number = cambc.round_number()
        for group in self.groups:
            key = int(group)
            mask = self.group_masks[key]
            status = None
            if not (mask & visible).is_empty():
                try:
                    status = group.state()
                except cambc.Error:
                    status = None
            if isinstance(status, game_map.CampGroupRespawning):
                self.respawn_until[key] = round_number + max(1, status.timer) + 1
                respawning_tiles |= mask
                continue
            if isinstance(status, (game_map.CampGroupAlive, game_map.CampGroupRewardAvailable)):
                self.respawn_until.pop(key, None)
            elif self.respawn_until.get(key, -1) >= round_number:
                # Keep a previously observed respawn out of navigation goals
                # after vision is lost, so we do not stand on its spawn tiles.
                respawning_tiles |= mask
                continue
            else:
                self.respawn_until.pop(key, None)
            goals |= mask
        goals &= ~respawning_tiles
        return goals, respawning_tiles

    def current_respawning_tiles(self, me):
        """Refresh only camp state relevant to our current tile before banking."""
        self.ensure_groups()
        current = me.position()
        if not self.all_spawn_tiles.is_set(current):
            return cambc.Bitboard()
        visible = cambc.vision.visible_tiles()
        round_number = cambc.round_number()
        result = cambc.Bitboard()
        for group in self.groups:
            key = int(group)
            mask = self.group_masks[key]
            known_until = self.respawn_until.get(key, -1)
            if mask.is_set(current) and not (mask & visible).is_empty():
                try:
                    status = group.state()
                except cambc.Error:
                    status = None
                if isinstance(status, game_map.CampGroupRespawning):
                    known_until = round_number + max(1, status.timer) + 1
                    self.respawn_until[key] = known_until
                elif isinstance(status, (game_map.CampGroupAlive, game_map.CampGroupRewardAvailable)):
                    self.respawn_until.pop(key, None)
                    known_until = -1
            if known_until >= round_number:
                result |= mask
        return result

    def vacate_respawning_tile(self, me, respawning_tiles, goals):
        current = me.position()
        if not me.can_move() or not respawning_tiles.is_set(current):
            return False
        blocked = blocked_tiles(me) | respawning_tiles
        candidates = []
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                tile = cambc.Vec2(current.x + dx, current.y + dy)
                if (game_map.is_in_bounds(tile) and not blocked.is_set(tile)):
                    candidates.append(tile)
        if not candidates:
            return False
        goal_positions = goals.positions()
        if not goal_positions:
            candidates.sort(key=lambda tile: (tile.y, tile.x))
        else:
            candidates.sort(key=lambda tile: (
                min(tile.chebyshev_distance(goal) for goal in goal_positions),
                tile.y, tile.x
            ))
        try:
            return me.move_absolute(candidates[0])
        except cambc.Error:
            return False

    def farm(self, me, goals):

        camps = cambc.vision.camps()
        if clear_turn(me, camps, None):
            return
        if move_towards_closest(me, goals):
            # Melee champions can move and attack in one turn; refresh vision
            # after the move and take the newly available attack when possible.
            if me.can_attack():
                clear_turn(me, cambc.vision.camps(), None)

    def bank(self, me):
        current = me.position()
        goals = cambc.Bitboard()
        for altar in game_map.altars().positions():
            if cambc.vision.has_altar_lock(altar):
                continue
            if current.chebyshev_distance(altar) <= cambc.constants.SUBMIT_GEMS_RANGE:
                try:
                    return me.submit_gems(altar)
                except cambc.Error:
                    return False
            goals |= tiles_around(altar, cambc.constants.SUBMIT_GEMS_RANGE)
        return move_towards_closest(me, goals)

    def hunt_carrier(self, me, enemies):
        """Spend a turn pursuing a nearby visible gem carrier after safe attacks."""
        if me.gem_count() > 0 or me.health() <= me.max_health() * 0.45:
            return False
        candidates = []
        for enemy in enemies:
            try:
                if not enemy.is_visible() or enemy.health() <= 0:
                    continue
                gems = enemy.gem_count()
                if gems <= 0:
                    continue
                distance = me.position().chebyshev_distance(enemy.position())
                if distance <= 8:
                    candidates.append((-gems, distance, int(enemy), enemy.position()))
            except cambc.Error:
                continue
        if not candidates:
            return False
        _, _, _, target = min(candidates)
        # The occupied champion tile is not a legal path goal. Route to its
        # legal attack perimeter so the chase can actually make progress.
        goals = tiles_around(target, max(1, me.attack_range()))
        goals.set(target, False)
        return move_towards_closest(me, goals)

    def play_turn(self):
        me = cambc.me()
        if not me.is_alive() or me.is_recalling() or me.is_submitting_gems() or me.is_teleporting():
            return

        at_spawn = game_map.spawn_region(Team.ALLY).is_set(me.position())
        carrying_gems = me.gem_count() > 0
        needs_retreat = not at_spawn and me.health() < me.max_health() * 0.35
        if carrying_gems or needs_retreat:
            respawning_tiles = self.current_respawning_tiles(me)
            if respawning_tiles.is_set(me.position()):
                route_goals = cambc.Bitboard()
                if carrying_gems:
                    for altar in game_map.altars().positions():
                        if not cambc.vision.has_altar_lock(altar):
                            route_goals.set(altar)
                else:
                    route_goals = game_map.spawn_region(Team.ALLY)
                if self.vacate_respawning_tile(me, respawning_tiles, route_goals):
                    return
                # Do not start tribute or recall on a respawn tile if every
                # local exit is temporarily blocked; retry the exit next turn.
                return

        if at_spawn or me.champion_name() == cambc.ChampionType.TAVI:
            self.buy_shard(me)

        # A shallow retreat threshold matches the starter's demonstrated
        # survival behavior while avoiding larpbot's earlier 45% retreat loop.
        if needs_retreat:
            try:
                me.recall()
                return
            except cambc.Error:
                pass

        if me.gem_count() > 0:
            self.bank(me)
            return

        enemies = cambc.vision.champions(Team.ENEMY)
        if me.can_attack():
            attack_tiles = me.attack_tiles()
            lethal_carriers = []
            for enemy in enemies:
                try:
                    if (enemy.is_visible() and enemy.health() > 0
                            and enemy.gem_count() > 0
                            and enemy.health() <= me.strength()
                            and attack_tiles.is_set(enemy.position())):
                        lethal_carriers.append((enemy, enemy.gem_count(), enemy.health()))
                except cambc.Error:
                    continue
            if lethal_carriers:
                target = min(lethal_carriers,
                             key=lambda item: (-item[1], item[2], int(item[0])))
                try:
                    me.attack(target[0])
                    return
                except cambc.Error:
                    pass

            # Preserve the established target order unless a gem carrier can
            # actually be killed by this attack.
            for enemy in enemies:
                try:
                    if (enemy.is_visible() and enemy.health() > 0
                            and attack_tiles.is_set(enemy.position())):
                        me.attack(enemy)
                        return
                except cambc.Error:
                    continue

        if self.hunt_carrier(me, enemies):
            return

        camp_goals, _ = self.available_camp_goals()
        self.farm(me, camp_goals)
        # Match the starter's randomized intra-team processing order. With
        # several champions selecting the same nearby camp, rotating priority
        # avoids a fixed roster-order advantage every round.
        me.set_priority(1 + below(100))
