"""Choose a farming squad and publish its shared loop on the first draft turn."""
from math import ceil

import cambc
from cambc import game_map

from navigation import around, distance_field, distance_to, enemy_spawn_field, terrain
from planner import Camp, RiskProfile, SearchConfig, find_loops, positional_risk
from protocol import Plan
from visualization import draw_plan


# Includes a healer even on three-pick maps. IDs here are draft IDs, not body IDs.
PICK_ORDER = (9, 7, 2, 6, 10, 0, 1, 4, 5, 8, 3)
CANDIDATE_LIMIT = 24
ALTAR_LIMIT = 4
FUEL_RESERVE = 4000000
PRECOMPUTE_RESERVE = 10000000
REPORT_LIMIT = 5


def bodies(picks):
    result = []
    for pick in picks:
        if pick == 3:
            result.extend((3, 4))
        else:
            result.append(pick if pick < 3 else pick + 1)
    return tuple(result)


def expected_picks(chosen):
    return tuple(chosen) + tuple(p for p in PICK_ORDER if p not in chosen)[
        :cambc.draft.team_size() - len(chosen)]


def combat_estimate(group, squad):
    """Approximate effective DPS, overkill, incoming damage and sustain.

    Uses SDK designs, not handbook numbers (the installed rules may differ).
    Ability DPS is discounted for movement, cooldowns and the one-cast limit.
    """
    monsters = [(camp, camp.base_stats()) for camp in group]
    dps, healing = 0.0, 0.0
    for champion in squad:
        stats = champion.base_stats()
        multiplier = stats.camp_damage_multiplier
        damage = stats.base_strength * multiplier
        spells = []
        for ability in champion.abilities():
            info = ability.info()
            if info is None:
                continue
            cooldown = max(1, info.max_cooldown)
            if ability.is_attack_reset():
                spells.append(stats.base_strength * multiplier / cooldown)
            elif ability.is_heal():
                healing += stats.base_focus * info.modifier / cooldown * 0.7
            elif (ability.can_target_camps() or ability.can_target_ground()) and (
                    ability.is_damage() or ability.is_aoe_damage() or ability.is_cc()):
                hits = min(2, len(monsters)) if ability.is_aoe_damage() else 1
                spells.append(stats.base_focus * info.modifier * hits * multiplier / cooldown)
        if champion.passive() == cambc.PassiveType.SPLASH_ATTACK:
            damage *= 1 + 0.5 * min(2, len(monsters) - 1)
        dps += damage + sum(spells) * 0.7
    dps = max(1, dps * 0.8)  # Space to surround the camp is not guaranteed.
    ordered = sorted(monsters, key=lambda item: (
        -item[1].base_strength / max(1, item[1].base_health), int(item[0])))
    clear, incoming = 0, 0.0
    remaining_damage = sum(stats.base_strength for _, stats in ordered)
    for _, stats in ordered:
        turns = max(1, ceil(stats.base_health / dps))
        incoming += remaining_damage * turns
        remaining_damage -= stats.base_strength
        clear += turns
    net_damage = max(0, incoming - healing * clear)
    health = sum(champion.base_stats().base_health for champion in squad)
    return clear + cambc.constants.CAPTURE_TIME + 2, net_damage < health * 0.65


def report(loops, camps, altars, roster, config=SearchConfig()):
    print(f"Squad loop candidates (approximate; risk tolerance {config.risk_tolerance:.2f}):")
    for rank, loop in enumerate(loops, 1):
        e = loop.evaluation
        altar = altars[loop.altar][1]
        order = " -> ".join(str(camps[i].anchor) for i in loop.camps)
        print(f"#{rank}: altar ({altar.x}, {altar.y}) -> {order} -> altar")
        print(f"  {e.gems} gems + {e.gold} gold | travel {e.travel_turns}, "
              f"clear/capture {e.service_turns}, tribute {e.tribute_turns}, "
              f"respawn wait {e.period - e.active_turns}")
        print(f"  period {e.period}, first deposit ~{e.first_deposit}, "
              f"gems/turn {e.gems / e.period:.3f}, adjusted score {e.score:.3f}")
        print(f"  risk {e.risk:.1%}, multiplier {e.risk_multiplier:.3f}, "
              f"base score {e.base_score:.3f}")
    # Machine-readable output lets inspect_loops.py extract results from the
    # binary-framed stdout stream inside a replay without gameplay code.
    # repr of numeric/list/dict data avoids importing the heavyweight JSON
    # encoder into the fuel-metered bot. The host helper uses literal_eval.
    print("SQUAD_LOOPS_DATA " + repr({
        "roster": list(roster),
        "risk_tolerance": config.risk_tolerance,
        "loops": [{
            "altar": [altars[loop.altar][1].x, altars[loop.altar][1].y],
            "camps": [list(camps[i].anchor) for i in loop.camps],
            "gems": loop.evaluation.gems,
            "gold": loop.evaluation.gold,
            "travel": loop.evaluation.travel_turns,
            "clear_capture": loop.evaluation.service_turns,
            "tribute": loop.evaluation.tribute_turns,
            "respawn_wait": loop.evaluation.period - loop.evaluation.active_turns,
            "period": loop.evaluation.period,
            "first_deposit": loop.evaluation.first_deposit,
            "gems_per_turn": loop.evaluation.gems / loop.evaluation.period,
            "score": loop.evaluation.score,
            "risk": loop.evaluation.risk,
            "risk_multiplier": loop.evaluation.risk_multiplier,
            "base_score": loop.evaluation.base_score,
        } for loop in loops],
    }), flush=True)


def fallback_plan(roster):
    """Publish a cheap valid route before doing any fuel-heavy work."""
    spawn = game_map.spawn_region(cambc.Team.ALLY).positions()[0]
    altars = game_map.altars().positions()
    if not altars:
        raise ValueError("map has no altar")
    altar = min(altars, key=spawn.chebyshev_distance)
    groups = [group for group in game_map.camp_groups() if group.gem_value()]
    if groups:
        group = min(groups, key=lambda g: (
            sum(c.base_stats().base_health for c in g)
            / g.gem_value() + min(spawn.chebyshev_distance(c.spawn_position()) for c in g)))
        point = min(group.spawn_tiles().positions(), key=lambda p: (p.y, p.x))
        route = ((point.x, point.y),)
    else:
        route = ()
    return Plan((altar.x, altar.y), route, roster)


def map_risk(position, ally_field, enemy_field):
    ally = distance_to(ally_field, [position])
    enemy = distance_to(enemy_field, [position])
    # The enemy field ends on a legal adjacent tile, not the forbidden spawn.
    return positional_risk(ally, enemy + 1 if enemy >= 0 else -1)


def make_plan(roster):
    config = SearchConfig()
    squad = [cambc.Champion.design(kind) for kind in roster]
    blocked = terrain()
    spawn = game_map.spawn_region(cambc.Team.ALLY)
    spawn_field = distance_field(spawn, blocked)
    enemy_field = enemy_spawn_field(blocked)
    groups = game_map.camp_groups()
    reachable = []
    camp_risks = {}
    for group in groups:
        service, feasible = combat_estimate(group, squad)
        positions = group.spawn_tiles().positions()
        anchor = min(positions, key=lambda p: (p.y, p.x))
        distance = distance_to(spawn_field, [anchor])
        if distance >= 0 and feasible:
            risk = sum(map_risk(p, spawn_field, enemy_field) for p in positions) / len(positions)
            camp_risks[(anchor.x, anchor.y)] = risk
            value = group.gem_value() + config.gold_weight * group.gold_value()
            priority = value / (service + distance + 1)
            priority *= 1 - (1 - config.risk_tolerance) * risk
            reachable.append((priority, group, anchor, service, distance))
    # Select by spawn access first, then evaluate altar proximity with actual BFS.
    reachable.sort(key=lambda item: item[0], reverse=True)
    reachable = reachable[:CANDIDATE_LIMIT]
    altars = []
    for altar in game_map.altars().positions():
        goals = around(altar, cambc.constants.SUBMIT_GEMS_RANGE) & ~blocked
        distance = distance_to(spawn_field, goals.positions())
        if distance >= 0:
            altars.append((distance, altar, goals))
    altars.sort(key=lambda item: (item[0], item[1].y, item[1].x))
    altars = altars[:ALTAR_LIMIT]
    if not altars:
        raise ValueError("no reachable altar")
    if not reachable:
        report([], [], altars, roster, config)
        return Plan((altars[0][1].x, altars[0][1].y), (), roster)

    print(f"Searching {len(reachable)} of {len(groups)} camp groups and {len(altars)} altars",
          flush=True)

    camps = [Camp((p.x, p.y), group.gem_value(), group.gold_value(), service,
                  group.max_respawn_timer()) for _, group, p, service, _ in reachable]
    points = [p for _, _, p, _, _ in reachable]
    altar_distances = []
    for _, _, goals in altars:
        if altar_distances and cambc.fuel_remaining() < PRECOMPUTE_RESERVE:
            break
        field = distance_field(goals, blocked)
        altar_distances.append([distance_to(field, [p]) for p in points])
    altars = altars[:len(altar_distances)]
    altar_risks = []
    for _, _, goals in altars:
        positions = [p for p in goals.positions() if spawn_field[1].is_set(p)]
        altar_risks.append(sum(map_risk(p, spawn_field, enemy_field) for p in positions)
                           / len(positions))
    distances = []
    for point in points:
        # Large-map native BFS also consumes fuel. Reserve a useful search and
        # reporting budget rather than exhausting the whole turn on the matrix.
        if cambc.fuel_remaining() < PRECOMPUTE_RESERVE:
            break
        field = distance_field(around(point, 0), blocked)
        distances.append([distance_to(field, [p]) for p in points])
    count = len(distances)
    if not count:
        # A singleton needs only its zero self-distance; altar fields are ready.
        count, distances = 1, [[0]]
    if count < len(camps):
        print(f"BFS fuel limit: retaining {count} candidate camps and {len(altars)} altars",
              flush=True)
    camps = camps[:count]
    distances = [row[:count] for row in distances]
    altar_distances = [row[:count] for row in altar_distances]
    spawn_distances = [d for _, _, _, _, d in reachable]
    spawn_distances = spawn_distances[:count]
    risk = RiskProfile(tuple(camp_risks[camp.anchor] for camp in camps), tuple(altar_risks))
    # A small valid plan is available even if the search fuel guard fires early.
    fallback = min(range(len(camps)), key=lambda i: (
        not bool(camps[i].gems), spawn_distances[i] + camps[i].service))

    def should_stop():
        if cambc.fuel_remaining() >= FUEL_RESERVE:
            return False
        print("Search stopped at the draft fuel reserve; reporting best candidates so far.", flush=True)
        return True

    loops = find_loops(camps, distances, altar_distances, spawn_distances,
                      config, should_stop, REPORT_LIMIT, risk)
    report(loops, camps, altars, roster, config)
    if not loops:
        altar_index, route = 0, (fallback,)
    else:
        loop = loops[0]
        altar_index, route = loop.altar, loop.camps
    altar = altars[altar_index][1]
    alternatives = tuple(
        ((altars[loop.altar][1].x, altars[loop.altar][1].y),
         tuple(camps[i].anchor for i in loop.camps)) for loop in loops[1:])
    return Plan((altar.x, altar.y), tuple(camps[i].anchor for i in route), roster, alternatives)


def play():
    chosen = cambc.draft.current_draft(cambc.Team.ALLY)
    picks = expected_picks(chosen)
    # Only the first draft turn has the large planning budget. Every champion
    # receives this same immutable plan; later draft turns just make their pick.
    if not chosen:
        roster = bodies(picks)
        print("Planning squad body types:", roster, flush=True)
        cambc.draft_memory.submit(fallback_plan(roster).encode())
        plan = make_plan(roster)
        cambc.draft_memory.submit(plan.encode())
        draw_plan(plan)
    # A successful pick ends this draft invocation in the engine.
    cambc.draft.pick(picks[len(chosen)])
