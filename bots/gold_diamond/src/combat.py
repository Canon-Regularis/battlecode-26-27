"""Small legal combat sequences around the current economic objective."""

import cambc
from cambc import vision
from world import distance


def _live_camps(group):
    result = []
    for camp in group.handle:
        try:
            if camp.is_visible() and camp.health() > 0:
                result.append(camp)
        except cambc.Error:
            continue
    return result


def _basic_target(me, camps, require_ready=True):
    if require_ready and not me.can_attack():
        return None
    mask = me.attack_tiles()
    options = []
    for camp in camps:
        try:
            if mask.is_set(camp.position()):
                health = camp.health()
                damage = min(me.strength(), health)
                if me.champion_name() == cambc.ChampionType.VARG:
                    damage += sum(min(me.strength(), other.health()) for other in camps
                                  if other != camp and distance(other.position(), camp.position()) <= 1)
                options.append((-damage, health, int(camp), camp))
        except cambc.Error:
            continue
    return min(options)[3] if options else None


def _try_attack(me, target):
    if target is None or not me.can_attack():
        return False
    try:
        me.attack(target)
        return True
    except cambc.Error:
        return False


def _try_reset(me, group):
    if not me.can_cast():
        return False
    for ability in me.abilities():
        if not ability.is_attack_reset() or not ability.is_ready():
            continue
        if _basic_target(me, _live_camps(group), require_ready=False) is None:
            return False
        if me.can_attack():
            # A ready attack means the reset does not improve this action.
            return False
        try:
            if ability.use():
                target = _basic_target(me, _live_camps(group))
                return _try_attack(me, target)
        except cambc.Error:
            pass
    return False


def _try_spell(me, group, moved):
    if not me.can_cast():
        return False
    camps = _live_camps(group)
    if not camps:
        return False
    options = []
    for ability in me.abilities():
        if not ability.is_ready() or not (ability.is_damage() or ability.is_aoe_damage()
                                          or ability.is_cc()):
            continue
        info = ability.info()
        if moved and info.exclusive_with_movement:
            continue
        if not (ability.can_target_camps() or ability.can_target_ground()):
            continue
        mask = ability.valid_tiles()
        try:
            damage = max(0.0, ability.damage_amount())
        except cambc.Error:
            damage = 0.0
        for camp in camps:
            try:
                centre = camp.position()
                if not mask.is_set(centre):
                    continue
                if ability.is_aoe_damage():
                    score = sum(min(damage, other.health()) for other in camps
                                if distance(centre, other.position()) <= info.radius)
                else:
                    score = min(damage, camp.health())
                if ability.is_cc() and camp.strength() > 0:
                    score += 35
                if score > 0:
                    target = centre if ability.can_target_ground() else camp
                    options.append((-score, ability.slot(), centre.y, centre.x,
                                    ability, target))
            except cambc.Error:
                continue
    for *_, ability, target in sorted(options):
        try:
            if ability.use(target):
                return True
        except cambc.Error:
            continue
    return False


def clear_group(me, group, moved=False):
    """Attack, then reset or cast; consult fresh action flags after each step."""
    camps = _live_camps(group)
    if not camps:
        return False
    target = _basic_target(me, camps)
    attacked = _try_attack(me, target)
    if attacked:
        _try_reset(me, group)
        return True
    return _try_spell(me, group, moved)


def interrupt_or_kill_enemy(me):
    """Only take local, high-confidence combat with economic value."""
    enemies = []
    for enemy in vision.champions(cambc.Team.ENEMY):
        try:
            if enemy.is_visible() and enemy.is_alive():
                gems = enemy.gem_count()
                urgent = enemy.is_submitting_gems()
                enemies.append((enemy, gems, urgent))
        except cambc.Error:
            continue
    if not enemies:
        return False
    if me.can_attack():
        tiles = me.attack_tiles()
        options = []
        for enemy, gems, urgent in enemies:
            try:
                if tiles.is_set(enemy.position()):
                    lethal = enemy.health() <= me.strength()
                    if lethal and gems or urgent:
                        options.append((-int(urgent), -int(lethal), -gems,
                                        enemy.health(), int(enemy), enemy))
            except cambc.Error:
                continue
        if options and _try_attack(me, min(options)[-1]):
            return True
    if not me.can_cast():
        return False
    for enemy, gems, urgent in sorted(enemies,
                                      key=lambda value: (-int(value[2]), -value[1], int(value[0]))):
        if not urgent and gems < 35:
            continue
        for ability in me.abilities():
            if not ability.is_ready() or not ability.can_target_enemies():
                continue
            if not (ability.is_cc() or ability.is_damage()):
                continue
            try:
                if ability.valid_tiles().is_set(enemy.position()) and ability.use(enemy):
                    return True
            except cambc.Error:
                continue
    return False


def shield_if_needed(me, incoming):
    if me.champion_name() != cambc.ChampionType.VARG or not me.can_cast():
        return False
    if incoming < me.health() * 0.35:
        return False
    for ability in me.abilities():
        if ability.is_shield() and ability.is_ready():
            try:
                return ability.use()
            except cambc.Error:
                return False
    return False

