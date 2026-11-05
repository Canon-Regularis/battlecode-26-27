"""Stage 1 turn orchestration; policy modules can be replaced independently."""

import cambc
from cambc import game_map

from combat import clear_turn
from objectives import ObjectivePolicy


class Bot:
    def __init__(self):
        self.objectives = ObjectivePolicy()
        self.peak_fuel_used = 0
        self.peak_fuel_round = 0
        self.last_fuel_report = -1
        self.retreating = False

    @staticmethod
    def _buy_strength(me):
        item = cambc.ItemType.POWER_SHARD_OF_STRENGTH
        count = me.gold_count() // item.cost()
        if count > 0 and me.can_buy(item, count):
            me.buy(item, count)

    def _report_fuel(self, round_number, fuel_at_start):
        used = max(0, fuel_at_start - cambc.fuel_remaining())
        if used > self.peak_fuel_used:
            self.peak_fuel_used = used
            self.peak_fuel_round = round_number
        if round_number // 100 != self.last_fuel_report:
            self.last_fuel_report = round_number // 100
            print(
                f"LARP_FUEL|{round_number}|{cambc.me().champion_name()}|"
                f"turn={used}|peak={self.peak_fuel_used}|peak_round={self.peak_fuel_round}",
                flush=True,
            )

    def play_turn(self):
        fuel_at_start = cambc.fuel_remaining()
        me = cambc.me()
        round_number = cambc.round_number()

        if not me.is_alive():
            self._buy_strength(me)
            self._report_fuel(round_number, fuel_at_start)
            return

        # Channels resolve at the start of the champion's turn. Do not cancel
        # a tribute/recall/teleport just to run ordinary policy code.
        if me.is_recalling() or me.is_submitting_gems() or me.is_teleporting():
            self._report_fuel(round_number, fuel_at_start)
            return

        at_spawn = game_map.spawn_region(cambc.Team.ALLY).is_set(me.position())
        if at_spawn or me.champion_name() == cambc.ChampionType.TAVI:
            self._buy_strength(me)

        groups, statuses = self.objectives.group_snapshot(me)
        after_snapshot = cambc.fuel_remaining()

        # Stage 1 banks the complete current bag before starting another camp.
        if me.gem_count() > 0:
            self.objectives.bank(me)
            self._report_fuel(round_number, fuel_at_start)
            return

        if self.retreating or me.health() <= me.max_health() * 0.45:
            self.retreating = True
            if at_spawn:
                if me.health() >= me.max_health() * 0.99:
                    self.retreating = False
            else:
                self.objectives.go_home(me)
            self._report_fuel(round_number, fuel_at_start)
            return

        target = self.objectives.choose_group(me, groups, statuses)
        if target is None:
            self.objectives.vacate_camps(me, groups)
            self._report_fuel(round_number, fuel_at_start)
            return

        target_id = int(target)
        status = statuses[target_id]
        if status == "capture":
            self.objectives.capture(me, target)
            self._report_fuel(round_number, fuel_at_start)
            return

        # Attack first. Melee champions retain their attack after moving; ranged
        # champions generally do not. The engine's action flags decide.
        visible_camps = list(cambc.vision.camps())
        clear_turn(me, visible_camps, target_id)
        after_combat = cambc.fuel_remaining()

        if me.can_move():
            start_position = me.position()
            moved = self.objectives.approach(me, target)
            if not moved:
                self.objectives.no_progress += 1
                if self.objectives.no_progress >= 3:
                    print(f"LARP_EVENT|{round_number}|stuck|{target_id}", flush=True)
                    self.objectives.clear_target()
            elif me.position() != start_position:
                self.objectives.no_progress = 0
                self.objectives.last_position = me.position()
                self.objectives.last_progress_round = round_number

            # Refresh vision after movement. This is especially useful for a
            # melee farmer, which can move and attack in the same turn.
            if me.can_attack():
                clear_turn(me, list(cambc.vision.camps()), target_id)

        fuel_used = fuel_at_start - cambc.fuel_remaining()
        if fuel_used > 1_500_000:
            print(
                f"LARP_COST|{round_number}|{me.champion_name()}|"
                f"snapshot={fuel_at_start-after_snapshot}|combat={after_snapshot-after_combat}|"
                f"rest={after_combat-cambc.fuel_remaining()}|total={fuel_used}",
                flush=True,
            )
        self._report_fuel(round_number, fuel_at_start)
