"""Estimate squad clearing time and survivability from static SDK designs.

This is an approximation for route selection, not a combat simulator or action
controller. Multipliers live in settings.py so their assumptions are visible.
"""

from dataclasses import dataclass
from math import ceil

import cambc
import settings


@dataclass(frozen=True)
class CombatEstimate:
    service_turns: int  # Fighting + capture + repositioning.
    survivable: bool


def estimate_squad_power(squad, monster_count: int) -> tuple[float, float]:
    """Return effective damage and healing per turn for this group size."""
    damage_per_turn = 0.0
    healing_per_turn = 0.0
    for champion in squad:
        stats = champion.base_stats()
        camp_multiplier = stats.camp_damage_multiplier
        basic_damage = stats.base_strength * camp_multiplier
        ability_damage_rates = []

        for ability in champion.abilities():
            info = ability.info()
            if info is None:
                continue
            cooldown = max(1, info.max_cooldown)
            if ability.is_attack_reset():
                ability_damage_rates.append(stats.base_strength * camp_multiplier / cooldown)
            elif ability.is_heal():
                healing_per_turn += (
                    stats.base_focus * info.modifier / cooldown * settings.HEALING_UTILIZATION
                )
            elif (ability.can_target_camps() or ability.can_target_ground()) and (
                ability.is_damage() or ability.is_aoe_damage() or ability.is_cc()
            ):
                targets_hit = min(settings.MAX_AOE_TARGETS, monster_count) if ability.is_aoe_damage() else 1
                ability_damage_rates.append(
                    stats.base_focus * info.modifier * targets_hit * camp_multiplier / cooldown
                )

        if champion.passive() == cambc.PassiveType.SPLASH_ATTACK:
            extra_targets = min(settings.MAX_EXTRA_SPLASH_TARGETS, monster_count - 1)
            basic_damage *= 1 + settings.SPLASH_EXTRA_TARGET_WEIGHT * extra_targets
        damage_per_turn += basic_damage + sum(ability_damage_rates) * settings.ABILITY_UTILIZATION

    # Not every body can deal full damage while moving or surrounding a camp.
    return max(1, damage_per_turn * settings.DAMAGE_UTILIZATION), healing_per_turn


def monster_clear_priority(monster):
    camp, stats = monster
    threat_per_health = stats.base_strength / max(1, stats.base_health)
    return -threat_per_health, int(camp)


def estimate_camp_clear(group, squad) -> CombatEstimate:
    """Focus dangerous monsters first; reject excessive estimated health loss."""
    monsters = [(camp, camp.base_stats()) for camp in group]
    damage_per_turn, healing_per_turn = estimate_squad_power(squad, len(monsters))
    monsters.sort(key=monster_clear_priority)

    fighting_turns = 0
    incoming_damage = 0.0
    remaining_monster_damage = sum(stats.base_strength for _, stats in monsters)
    for _, stats in monsters:
        turns_to_kill = max(1, ceil(stats.base_health / damage_per_turn))
        incoming_damage += remaining_monster_damage * turns_to_kill
        remaining_monster_damage -= stats.base_strength
        fighting_turns += turns_to_kill

    net_health_loss = max(0, incoming_damage - healing_per_turn * fighting_turns)
    squad_health = sum(champion.base_stats().base_health for champion in squad)
    service_turns = (
        fighting_turns + cambc.constants.CAPTURE_TIME + settings.CAPTURE_REPOSITION_TURNS
    )
    return CombatEstimate(
        service_turns=service_turns,
        survivable=net_health_loss < squad_health * settings.MAX_HEALTH_LOSS_FRACTION,
    )
