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
        self._assignment_initialized = False

    def _initialize_assignment(self, me):
        data = bytes(cambc.draft_memory)
        slot = None
        if len(data) >= 4 and data[:3] == b"LB2":
            count = data[3]
            roster = data[4:4 + count]
            try:
                slot = roster.index(int(me.champion_name()))
            except ValueError:
                pass
        self.objectives.set_slot(slot)
        self._assignment_initialized = True
        print(f"LARP_SLOT|{int(me.champion_name())}|{slot}", flush=True)

    @staticmethod
    def _buy_strength(me):
        item = cambc.ItemType.POWER_SHARD_OF_STRENGTH
        count = me.gold_count() // item.cost()
        if count > 0 and me.can_buy(item, count):
            me.buy(item, count)

    def _report_fuel(self, round_number, fuel_at_start, stages=None):
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
        if used >= 1_500_000:
            details = "|".join(f"{name}={cost}" for name, cost in (stages or {}).items())
            print(f"LARP_PROFILE|{round_number}|{me_name(cambc.me())}|total={used}|{details}", flush=True)

    def play_turn(self):
        fuel_at_start = cambc.fuel_remaining()
        me = cambc.me()
        round_number = cambc.round_number()
        stages = {}

        def mark(stage):
            stages[stage] = max(0, fuel_at_start - cambc.fuel_remaining() - sum(stages.values()))

        if not self._assignment_initialized:
            self._initialize_assignment(me)

        if not me.is_alive():
            self.objectives.release_assignment()
            self._buy_strength(me)
            self._report_fuel(round_number, fuel_at_start, stages)
            return

        # Channels resolve at the start of the champion's turn. Do not cancel
        # a tribute/recall/teleport just to run ordinary policy code.
        if me.is_recalling() or me.is_submitting_gems() or me.is_teleporting():
            self._report_fuel(round_number, fuel_at_start, stages)
            return

        at_spawn = game_map.spawn_region(cambc.Team.ALLY).is_set(me.position())
        if at_spawn or me.champion_name() == cambc.ChampionType.TAVI:
            self._buy_strength(me)

        groups, statuses = self.objectives.group_snapshot(me)
        mark("snapshot")

        if self.objectives.vacate_respawning_tile(me):
            mark("evacuate")
            self._report_fuel(round_number, fuel_at_start, stages)
            return

        # Stage 1 banks the complete current bag before starting another camp.
        if me.gem_count() > 0:
            self.objectives.bank(me)
            mark("bank")
            self._report_fuel(round_number, fuel_at_start, stages)
            return

        if self.retreating or me.health() <= me.max_health() * 0.45:
            self.retreating = True
            if at_spawn:
                if me.health() >= me.max_health() * 0.99:
                    self.retreating = False
            else:
                self.objectives.go_home(me)
            mark("retreat")
            self._report_fuel(round_number, fuel_at_start, stages)
            return

        target = self.objectives.choose_group(me, groups, statuses)
        mark("selection")
        if target is None:
            self.objectives.vacate_camps(me, groups)
            mark("vacate")
            self._report_fuel(round_number, fuel_at_start, stages)
            return

        target_id = int(target)
        status = statuses[target_id]
        if status == "capture":
            self.objectives.capture(me, target)
            mark("capture")
            self._report_fuel(round_number, fuel_at_start, stages)
            return

        # Attack first. Melee champions retain their attack after moving; ranged
        # champions generally do not. The engine's action flags decide.
        visible_camps = self.objectives.visible_camps(groups)
        acted = clear_turn(me, visible_camps, target_id)
        mark("combat")

        if me.can_move():
            start_position = me.position()
            moved = self.objectives.approach(me, target)
            if not moved and not acted:
                self.objectives.no_progress = (
                    3 if self.objectives.at_approach_root
                    else self.objectives.no_progress + 1
                )
                if self.objectives.no_progress >= 3:
                    print(f"LARP_EVENT|{round_number}|stuck|{target_id}", flush=True)
                    if self.objectives.at_approach_root:
                        self.objectives.exclude_approach_root(target_id, me.position())
                    else:
                        self.objectives.mark_unreachable(target_id)
                    self.objectives.clear_target()
            elif me.position() != start_position:
                self.objectives.no_progress = 0
                self.objectives.last_position = me.position()
                self.objectives.last_progress_round = round_number
            elif acted:
                self.objectives.no_progress = 0

            # Refresh vision after movement. This is especially useful for a
            # melee farmer, which can move and attack in the same turn.
            if moved and me.can_attack() and cambc.fuel_remaining() >= 1_000_000:
                if clear_turn(me, self.objectives.visible_camps(groups), target_id):
                    self.objectives.no_progress = 0
                mark("followup")

        mark("navigation")
        self._report_fuel(round_number, fuel_at_start, stages)


def me_name(me):
    return int(me.champion_name())
