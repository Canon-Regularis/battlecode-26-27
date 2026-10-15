"""Per-body economic cycle with safe local tactical preemption."""

import cambc
from cambc import game_map, vision

from comm import TeamSignals, slot_for, unpack_roster, encode_objective
from combat import clear_group, interrupt_or_kill_enemy, shield_if_needed
from navigation import (best_retreat_step, move_to_goals, occupied_blocked,
                        ring_goals)
from strategy_config import (BANK_CONSIDER_GEMS, BANK_NEAR_ALTAR_STEPS,
                             ENABLE_ALTAR_LOCK, ENABLE_WARDS, FAILED_TARGET_COOLDOWN,
                             FUEL_EMERGENCY, FUEL_LOW, LINKED_TYPES, LOW_HEALTH_RATIO,
                             MISSION_MIN_COMMITMENT, NO_PROGRESS_LIMIT,
                             PAIR_EXTRA_MARGIN_RATIO, STATUS_BANK, STATUS_BLOCKED,
                             STATUS_DEAD, STATUS_RECALL, STATUS_RETREAT,
                             STATUS_TELEPORT, STATUS_TRIBUTE, STATUS_UNKNOWN,
                             SURVIVAL_MARGIN_RATIO, SWITCH_GAIN)
from world import World, distance


def safe_call(action, *args):
    try:
        return action(*args)
    except (cambc.Error, ValueError, IndexError):
        return None


class Bot:
    def __init__(self):
        self.world = World()
        self.roster = unpack_roster(cambc.draft_memory)
        self.slot = slot_for(self.roster, cambc.me().champion_name())
        self.signals = TeamSignals(self.slot)
        self.opening = self.world.opening_assignments(self.roster) if self.roster else ()
        self.target_id = self.opening[self.slot] if self.slot is not None else None
        self.target_since = cambc.round_number()
        self.banking = False
        self.healing = False
        self.failed_until = {}
        self.last_position = None
        self.last_gems = 0
        self.last_status = None
        self.no_progress = 0
        self.last_fuel_report = -1
        self.respawn_mask = cambc.Bitboard()
        first = self.world.groups[self.target_id] if self.target_id is not None else None
        print(f"GD_INIT|{cambc.round_number()}|{int(cambc.me().champion_name())}|{self.slot}|"
              f"{self.target_id}|{len(self.world.groups)}|"
              f"{self.world.spawn_distance(first) if first else -1}|"
              f"{first.gems if first else -1}|{first.gold if first else -1}", flush=True)

    def publish(self, value):
        self.signals.publish(value)

    def release(self):
        self.target_id = None
        self.last_status = None
        self.no_progress = 0
        self.publish(STATUS_UNKNOWN)

    def _shop(self, me):
        if me.gold_count() < 30:
            return
        kind = int(me.champion_name())
        items = me.item_count()
        item = cambc.ItemType.MONSTER_SHARD_OF_STRENGTH
        if kind == 5:
            item = cambc.ItemType.MONSTER_SHARD_OF_FOCUS
        elif kind in LINKED_TYPES and (me.max_health() < 1000 or self._enemy_near(me, 6)):
            item = cambc.ItemType.DURABILITY_SHARD_OF_HEALTH
        elif kind == 9 and self._enemy_near(me, 5):
            item = cambc.ItemType.DURABILITY_SHARD_OF_HEALTH
        if items[int(item.result())] > 0:
            if item == cambc.ItemType.MONSTER_SHARD_OF_STRENGTH:
                item = cambc.ItemType.POWER_SHARD_OF_STRENGTH
            elif item == cambc.ItemType.MONSTER_SHARD_OF_FOCUS:
                item = cambc.ItemType.POWER_SHARD_OF_FOCUS
            else:
                item = cambc.ItemType.POWER_SHARD_OF_HEALTH
        for _ in range(5):
            if not me.can_buy(item):
                break
            me.buy(item)

    def _enemy_near(self, me, radius):
        position = me.position()
        for enemy in vision.champions(cambc.Team.ENEMY):
            try:
                if enemy.is_visible() and enemy.is_alive() and distance(position, enemy.position()) <= radius:
                    return True
            except cambc.Error:
                continue
        return False

    def _enemies(self):
        enemies = []
        for enemy in vision.champions(cambc.Team.ENEMY):
            try:
                if enemy.is_visible() and enemy.is_alive():
                    enemies.append(enemy)
            except cambc.Error:
                continue
        return enemies

    def _incoming(self, me, enemies):
        incoming = 0.0
        current = me.position()
        for enemy in enemies:
            try:
                if distance(current, enemy.position()) <= enemy.attack_range() + 1:
                    incoming += enemy.strength() * 2.0 + enemy.focus() * 1.4
            except cambc.Error:
                continue
        for camp in vision.camps():
            try:
                if camp.health() > 0 and distance(current, camp.position()) <= 3:
                    incoming += camp.strength()
            except cambc.Error:
                continue
        return incoming

    def _retreat_if_needed(self, me, enemies):
        incoming = self._incoming(me, enemies)
        extra = PAIR_EXTRA_MARGIN_RATIO if int(me.champion_name()) in LINKED_TYPES else 0
        reserve = me.max_health() * (SURVIVAL_MARGIN_RATIO + extra)
        if incoming < me.health() - reserve:
            return False
        if shield_if_needed(me, incoming) and me.health() + 200 > incoming + reserve:
            return False
        if enemies:
            interrupt_or_kill_enemy(me)
            if best_retreat_step(me, self.world, enemies):
                self.publish(STATUS_RETREAT)
                return True
        if me.health() <= me.max_health() * LOW_HEALTH_RATIO:
            self.healing = True
            self.publish(STATUS_RETREAT)
            return self._go_home(me, enemies)
        return False

    def _go_home(self, me, enemies):
        current = me.position()
        if self.world.own_spawn.is_set(current):
            return True
        if not enemies and not self._enemy_near(me, 8):
            near_camp = any(distance(current, camp.position()) <= 3
                            for camp in vision.camps() if camp.is_visible())
            home_steps = min(distance(current, p) for p in self.world.own_cells)
            if not near_camp and home_steps > 5:
                if safe_call(me.recall) is None and me.is_recalling():
                    self.publish(STATUS_RECALL)
                    return True
        return move_to_goals(me, self.world, self.world.own_spawn,
                             enemies, self.respawn_mask)

    def _altar_locked(self, altar):
        for lock in vision.altar_locks(cambc.Team.ENEMY):
            if lock.position() == altar:
                return lock
        return None

    def _altar_choice(self, me, enemies):
        current = me.position()
        choices = []
        for index, altar in enumerate(self.world.altars):
            lock = self._altar_locked(altar)
            if lock is not None:
                continue
            steps = max(0, distance(current, altar) - 1)
            exposure = 0
            for enemy in enemies:
                try:
                    if enemy.is_visible() and enemy.is_alive():
                        exposure += max(0, 6 - distance(altar, enemy.position()))
                except cambc.Error:
                    continue
            choices.append((steps + 3 * exposure, steps, index, altar))
        return min(choices)[-1] if choices else None

    def _bank(self, me, enemies):
        altar = self._altar_choice(me, enemies)
        if altar is None:
            return False
        if distance(me.position(), altar) <= 1:
            try:
                me.submit_gems(altar)
                self.publish(STATUS_TRIBUTE)
                return True
            except cambc.Error:
                return False
        goals = ring_goals((altar,), 1)
        goals.set(altar, False)
        moved = move_to_goals(me, self.world, goals, enemies, self.respawn_mask)
        self.publish(STATUS_BANK)
        return moved

    def _should_bank(self, me, enemies):
        bag = me.gem_count()
        if bag <= 0:
            return False
        if self.banking or bag >= BANK_CONSIDER_GEMS:
            return True
        if cambc.global_submitted_gems(cambc.Team.ALLY) + bag >= 1000:
            return True
        altar = self._altar_choice(me, enemies)
        if altar is not None and distance(me.position(), altar) <= BANK_NEAR_ALTAR_STEPS + 1:
            return bag >= 10
        return me.health() < me.max_health() * 0.48 or bool(enemies)

    def _group_held_by_ally(self, group, me):
        for ally in vision.champions(cambc.Team.ALLY):
            try:
                if int(ally) != int(me) and ally.is_alive() and group.mask.is_set(ally.position()):
                    return True
            except cambc.Error:
                continue
        return False

    def _choose_target(self, me, statuses):
        round_number = cambc.round_number()
        for group_id, until in list(self.failed_until.items()):
            if until < round_number:
                del self.failed_until[group_id]
        if self.target_id is not None:
            group = self.world.groups[self.target_id]
            state = statuses[self.target_id]
            if state == "respawning" or (state == "capture" and self._group_held_by_ally(group, me)):
                self.release()
            elif round_number - self.target_since < MISSION_MIN_COMMITMENT or state == "capture":
                return group
        claims = self.signals.statuses() if round_number > 2 else ()
        best = None
        old = None
        for group in self.world.groups:
            if group.id in self.failed_until:
                continue
            claimed = any(slot != self.slot and slot < len(self.roster) and value == group.id
                          for slot, value in enumerate(claims))
            score = self.world.group_score(me, group, statuses[group.id], claimed)
            if score < 0:
                continue
            record = (score, -group.id, group)
            if best is None or record[:2] > best[:2]:
                best = record
            if group.id == self.target_id:
                old = record
        if self.target_id is not None and old is not None and best is not None:
            if best[0] <= old[0] * SWITCH_GAIN:
                return self.world.groups[self.target_id]
        if best is None:
            self.release()
            return None
        selected = best[2]
        if selected.id != self.target_id:
            self.target_id = selected.id
            self.target_since = round_number
            self.no_progress = 0
            print(f"GD_TARGET|{round_number}|{self.slot}|{selected.id}", flush=True)
        self.publish(encode_objective(selected.id))
        return selected

    def _vacate_respawn(self, me, statuses, enemies):
        for group in self.world.groups:
            if statuses[group.id] != "respawning" or not group.mask.is_set(me.position()):
                continue
            goals = ring_goals((me.position(),), 1) & ~group.mask
            if self._should_bank(me, enemies):
                altar = self._altar_choice(me, enemies)
                if altar is not None:
                    goals |= ring_goals((altar,), 1) & ~group.mask
            moved = move_to_goals(me, self.world, goals, enemies, group.mask)
            if moved:
                print(f"GD_VACATE|{cambc.round_number()}|{self.slot}|{group.id}", flush=True)
            return True
        return False

    def _farm(self, me, group, state, enemies):
        if state == "capture":
            if group.mask.is_set(me.position()):
                self.publish(encode_objective(group.id))
                return True
            goals = group.mask & ~occupied_blocked(self.world, me)
            moved = move_to_goals(me, self.world, goals, enemies,
                                  self.respawn_mask)
            self.publish(encode_objective(group.id))
            return moved
        acted = clear_group(me, group)
        if me.can_move():
            camps = []
            for camp in group.handle:
                try:
                    if camp.is_visible() and camp.health() > 0:
                        camps.append(camp.position())
                except cambc.Error:
                    continue
            centres = camps if camps else group.cells
            radius = me.attack_range() if camps else max(1, me.attack_range() - 1)
            goals = ring_goals(centres, radius)
            moved = move_to_goals(me, self.world, goals, enemies,
                                  self.respawn_mask)
            if moved:
                acted = True
                clear_group(me, group, moved=True)
        self.publish(encode_objective(group.id))
        return acted

    def _ward(self, me, group):
        if not ENABLE_WARDS or me.ward_cooldown() != 0 or cambc.fuel_remaining() < FUEL_LOW:
            return
        old = me.ward_positions()
        if old and min(distance(me.position(), p) for p in old) <= 5:
            return
        available = me.ward_placement_tiles() & ~occupied_blocked(self.world, me)
        candidates = [p for p in available.positions() if game_map.bushes().is_set(p)]
        if not candidates:
            return
        centre = group.cells[0] if group is not None else me.position()
        for point in sorted(candidates, key=lambda p: (distance(p, centre), p.y, p.x))[:3]:
            try:
                if me.place_ward(point):
                    return
            except cambc.Error:
                continue

    def _record_progress(self, me, group, state, acted):
        current = me.position()
        if state == "capture" and group.mask.is_set(current):
            self.no_progress = 0
        elif acted or current != self.last_position:
            self.no_progress = 0
        else:
            self.no_progress += 1
        self.last_position = current
        if self.no_progress >= NO_PROGRESS_LIMIT:
            self.failed_until[group.id] = cambc.round_number() + FAILED_TARGET_COOLDOWN
            self.publish(STATUS_BLOCKED)
            self.release()

    def _report_fuel(self, start):
        interval = cambc.round_number() // 100
        if interval != self.last_fuel_report:
            self.last_fuel_report = interval
            print(f"GD_FUEL|{cambc.round_number()}|{self.slot}|{start - cambc.fuel_remaining()}",
                  flush=True)

    def play_turn(self):
        start = cambc.fuel_remaining()
        me = cambc.me()
        round_number = cambc.round_number()
        self.signals.clear_stale(round_number)
        if not me.is_alive():
            self.release()
            self.publish(STATUS_DEAD)
            self._shop(me)
            self._report_fuel(start)
            return
        if me.is_submitting_gems():
            self.publish(STATUS_TRIBUTE)
            return
        if me.is_recalling():
            self.publish(STATUS_RECALL)
            return
        if me.is_teleporting():
            self.publish(STATUS_TELEPORT)
            return
        if cambc.fuel_remaining() < FUEL_EMERGENCY:
            return
        enemies = self._enemies()
        if self.world.own_spawn.is_set(me.position()):
            self._shop(me)
            if me.health() < me.max_health():
                self.healing = True
                self.publish(STATUS_RECALL)
                return
            self.healing = False
        elif me.champion_name() == cambc.ChampionType.TAVI:
            self._shop(me)

        statuses = self.world.statuses()
        self.respawn_mask = cambc.Bitboard()
        for group, status in zip(self.world.groups, statuses):
            if status == "respawning":
                self.respawn_mask |= group.mask
        if self.target_id is not None and self.last_status == "capture" and statuses[self.target_id] == "respawning":
            print(f"GD_CAPTURE|{round_number}|{self.slot}|{self.target_id}|{me.gem_count()}", flush=True)
            self.release()
        if self._vacate_respawn(me, statuses, enemies):
            self._report_fuel(start)
            return
        if self._retreat_if_needed(me, enemies):
            self._report_fuel(start)
            return
        if (self.target_id is not None and statuses[self.target_id] == "capture"
                and self.world.groups[self.target_id].mask.is_set(me.position())):
            self.publish(encode_objective(self.target_id))
            self.last_status = "capture"
            self._report_fuel(start)
            return
        if me.health() < me.max_health() * LOW_HEALTH_RATIO and me.gem_count() == 0:
            self.healing = True
        if self.healing:
            self.publish(STATUS_RETREAT)
            self._go_home(me, enemies)
            self._report_fuel(start)
            return
        if self._should_bank(me, enemies):
            self.banking = True
            self.release()
            self._bank(me, enemies)
            self._report_fuel(start)
            return
        self.banking = False
        if interrupt_or_kill_enemy(me):
            self._report_fuel(start)
            return
        group = self._choose_target(me, statuses)
        if group is None:
            self.publish(STATUS_UNKNOWN)
            self._ward(me, None)
            self._report_fuel(start)
            return
        state = statuses[group.id]
        acted = self._farm(me, group, state, enemies)
        self.last_status = state
        self._record_progress(me, group, state, acted)
        self._ward(me, group)
        self._report_fuel(start)

