"""Basic camp attack and documented champion ability handling."""

import cambc


def group_key(group):
    return int(group)


def _attackable(me, camp):
    return (camp.is_visible() and camp.health() > 0
            and me.attack_tiles().is_set(camp.position()))


def _best_basic_target(me, camps, preferred_group=None):
    attackable = [camp for camp in camps if _attackable(me, camp)]
    if not attackable:
        return None

    is_varg = me.champion_name() == cambc.ChampionType.VARG
    if is_varg:
        def score(camp):
            position = camp.position()
            splash = sum(
                1 for other in camps
                if other != camp and other.is_visible() and other.health() > 0
                and position.chebyshev_distance(other.position()) <= cambc.constants.VARG_SPLASH_RADIUS
            )
            group_bonus = int(preferred_group is not None
                              and group_key(camp.camp_group()) == preferred_group)
            return (splash, group_bonus, -camp.health(), -int(camp))
        return max(attackable, key=score)

    if preferred_group is not None:
        preferred = [camp for camp in attackable
                     if group_key(camp.camp_group()) == preferred_group]
        if preferred:
            attackable = preferred
    return min(attackable, key=lambda camp: (camp.health(), int(camp)))


def _cast_damage(me, camps, preferred_group):
    if not me.can_cast():
        return False
    for ability in me.abilities():
        if not ability.is_ready() or not (ability.is_damage() or ability.is_aoe_damage()):
            continue
        can_unit_target = ability.can_target_camps()
        can_ground_target = ability.can_target_ground()
        for camp in camps:
            if not camp.is_visible() or camp.health() <= 0:
                continue
            if (preferred_group is not None
                    and group_key(camp.camp_group()) != preferred_group):
                continue
            position = camp.position()
            if not ability.valid_tiles().is_set(position):
                continue
            if can_unit_target:
                target = camp
            elif can_ground_target:
                target = position
            else:
                continue
            try:
                if ability.use(target):
                    return True
            except cambc.Error:
                # A hidden obstruction or phase change must not derail the loop.
                continue
    return False


def _reset_and_attack(me, camps, preferred_group):
    if not me.can_cast():
        return False
    for ability in me.abilities():
        if not ability.is_attack_reset() or not ability.is_ready():
            continue
        try:
            if not ability.use():
                continue
        except cambc.Error:
            continue
        # Only attempt the follow-up if the SDK says the reset restored the
        # basic attack. This safely handles champions/action states where it did not.
        if me.can_attack():
            target = _best_basic_target(me, camps, preferred_group)
            if target is not None:
                me.attack(target)
        return True
    return False


def _shield_varg(me, camps):
    if (me.champion_name() != cambc.ChampionType.VARG
            or me.health() > me.max_health() * 0.60
            or not me.can_cast()):
        return False
    threatened = any(
        camp.is_visible() and camp.health() > 0
        and me.position().chebyshev_distance(camp.position()) <= 3
        for camp in camps
    )
    if not threatened:
        return False
    for ability in me.abilities():
        if ability.is_shield() and ability.is_ready():
            try:
                return ability.use()
            except cambc.Error:
                return False
    return False


def clear_turn(me, visible_camps, preferred_group):
    """Use an in-range camp spell/basic attack and supported resets/shield."""
    camps = list(visible_camps)
    acted = False

    # A damage spell can start the clear from range. It does not assume that a
    # cast also permits a walk; the caller still checks the SDK movement flag.
    if _cast_damage(me, camps, preferred_group):
        acted = True

    if me.can_attack():
        target = _best_basic_target(me, camps, preferred_group)
        if target is not None:
            me.attack(target)
            acted = True
            # Protect a weakened Varg before spending this turn's cast on a reset.
            if not _shield_varg(me, camps):
                _reset_and_attack(me, camps, preferred_group)
    elif not acted:
        # Shield before the next camp retaliation if already badly hurt.
        acted = _shield_varg(me, camps)
    return acted

