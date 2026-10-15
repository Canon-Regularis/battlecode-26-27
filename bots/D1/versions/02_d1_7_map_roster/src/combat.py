"""Basic camp attack and documented champion ability handling."""

import cambc


def group_key(group):
    return int(group)


def _attackable(me, camp):
    try:
        return (camp.is_visible() and camp.health() > 0
                and me.attack_tiles().is_set(camp.position()))
    except cambc.Error:
        # A visibility boundary can invalidate a camp handle mid-turn.
        return False


def _health(camp):
    try:
        return camp.health() if camp.is_visible() else 10**9
    except cambc.Error:
        return 10**9


def _best_basic_target(me, camps, preferred_group=None):
    attack_tiles = me.attack_tiles()
    records = []
    for camp in camps:
        try:
            position = camp.position()
            health = camp.health()
            if health > 0 and attack_tiles.is_set(position):
                records.append((camp, position, health, group_key(camp.camp_group())))
        except cambc.Error:
            continue
    if not records:
        return None

    is_varg = me.champion_name() == cambc.ChampionType.VARG
    if is_varg:
        all_positions = {(position.x, position.y) for _, position, _, _ in records}
        best = None
        best_score = None
        for camp, position, health, group in records:
            splash = sum(
                (position.x + dx, position.y + dy) in all_positions
                for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                if dx or dy
            )
            group_bonus = int(preferred_group is not None and group == preferred_group)
            score = (splash, group_bonus, -health, -int(camp))
            if best_score is None or score > best_score:
                best, best_score = camp, score
        return best

    if preferred_group is not None:
        preferred = [record[0] for record in records if record[3] == preferred_group]
        if preferred:
            records = [record for record in records if record[3] == preferred_group]
    return min(records, key=lambda record: (record[2], int(record[0])))[0]


def _attack(me, target):
    try:
        me.attack(target)
        return True
    except cambc.Error:
        # State can change after target selection; losing this attack is safer
        # than aborting the champion's entire turn.
        return False


def _cast_damage(me, camps, preferred_group):
    if not me.can_cast():
        return False
    for ability in me.abilities():
        if not ability.is_ready() or not (ability.is_damage() or ability.is_aoe_damage()):
            continue
        can_unit_target = ability.can_target_camps()
        can_ground_target = ability.can_target_ground()
        valid_tiles = ability.valid_tiles()
        for camp in camps:
            try:
                if not camp.is_visible() or camp.health() <= 0:
                    continue
                if (preferred_group is not None
                        and group_key(camp.camp_group()) != preferred_group):
                    continue
                position = camp.position()
            except cambc.Error:
                continue
            if not valid_tiles.is_set(position):
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
                _attack(me, target)
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
    """Prioritise the basic-attack reset cycle, then use range spells."""
    camps = list(visible_camps)
    attacked = False
    if me.can_attack():
        target = _best_basic_target(me, camps, preferred_group)
        if target is not None:
            attacked = _attack(me, target)
    if attacked:
        # Attack-reset abilities are only useful after the first basic attack.
        # In particular, checking can_attack() here would skip the reset because
        # the first attack has just consumed that allowance.
        if not _shield_varg(me, camps):
            _reset_and_attack(me, camps, preferred_group)
        return True

    # Ranged spells start a clear when no basic attack is available. The caller
    # still checks the movement allowance after this cast.
    if _cast_damage(me, camps, preferred_group):
        return True

    # Shield before the next camp retaliation if Varg is already badly hurt.
    return _shield_varg(me, camps)

