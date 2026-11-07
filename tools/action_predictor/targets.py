"""Recorded coordinate labels and PRE-only spatial candidates. No intent labels."""
import numpy as np

FAMILIES = ['move', 'attack', 'cast_0', 'cast_1']
RADIUS = 8
OFFSETS = np.array([(x, y) for y in range(-RADIUS, RADIUS+1)
                    for x in range(-RADIUS, RADIUS+1)], dtype=np.int64)


def point(p):
    return isinstance(p, dict) and all(type(p.get(k)) is int for k in ('x', 'y'))


def spatial_candidates(obs, family, width, height):
    """All in-map offsets for move/ground aim; visible compatible cells for units.

    Candidate construction never receives a recorded destination or future state.
    Terrain and full SDK legality are unavailable and are not inferred.
    """
    own = obs['own']
    pos = own.get('position')
    if not point(pos):
        raise ValueError('Unknown own position')
    coords = OFFSETS + np.array([pos['x'], pos['y']])
    valid = ((coords[:, 0] >= 0) & (coords[:, 0] < width)
             & (coords[:, 1] >= 0) & (coords[:, 1] < height))
    grid = np.zeros((len(OFFSETS), 10), dtype=np.float32)
    grid[:, :2] = OFFSETS / RADIUS
    grid[:, 2] = np.abs(OFFSETS).max(1) / RADIUS
    grid[:, 3] = (OFFSETS == 0).all(1)
    mask = 3 if family == 'attack' else 31
    if family.startswith('cast_'):
        props = own.get('abilityProps', [])
        if len(props) != 2 or type(props[int(family[-1])].get('target')) is not int:
            return grid, np.zeros(len(OFFSETS), dtype=bool), {}
        mask = props[int(family[-1])]['target']
    occupants = {}
    compatible = np.zeros(len(OFFSETS), dtype=bool)
    for e in [own, *obs.get('entities', [])]:
        if not e.get('known', 0) & 1 or not point(e.get('position')) or e.get('health', 0) <= 0:
            continue
        kind = e['entity']['kind']
        if kind == 1 and e.get('alive') is not True:
            continue
        if kind not in (1, 2):
            continue
        bit = 1 if kind == 2 else (8 if e['entity'] == own['entity'] else 4 if e['team'] == own['team'] else 2)
        dx, dy = e['position']['x']-pos['x'], e['position']['y']-pos['y']
        if max(abs(dx), abs(dy)) > RADIUS:
            continue
        i = (dy+RADIUS)*(2*RADIUS+1) + dx+RADIUS
        channel = 2 if kind == 2 else (1 if e['team'] == own['team'] else 0)
        grid[i, 4+channel] += 1
        grid[i, 7+channel] += e['health'] / max(e.get('maxHealth', 1), 1)
        if bit & mask:
            compatible[i] = True
            occupants.setdefault(i, []).append(e['entity'])
    if family == 'attack' or (family.startswith('cast_') and not mask & 16):
        valid &= compatible
    return grid, valid, occupants


def recorded_target(decision, family, width, height):
    """Return offset ID only when recorded geometry and PRE evidence agree."""
    obs, label = decision['observation'], decision['label']
    origin = obs['own'].get('position')
    # Non-movement ability events may leave the event's from field at (0,0).
    # The personal PRE position is the origin; the recorded to is the label.
    if not point(origin) or (family == 'move' and label['from'] != origin):
        return None, 'origin_mismatch', None
    if family == 'move' and decision['audit']['post_move_matches'] is not True:
        return None, 'unverified_move', None
    target = label.get('to')
    if not point(target) or not (0 <= target['x'] < width and 0 <= target['y'] < height):
        return None, 'invalid_coordinate', None
    dx = target['x'] - origin['x']
    dy = target['y'] - origin['y']
    if max(abs(dx), abs(dy)) > RADIUS:
        return None, 'outside_fixed_offset_window', None
    i = (dy+RADIUS)*(2*RADIUS+1) + dx+RADIUS
    _, mask, occupants = spatial_candidates(obs, family, width, height)
    if not mask[i]:
        return None, 'no_visible_compatible_target', None
    candidates = occupants.get(i, [])
    # This is a coordinate-to-visible-entity resolution, NOT an original ID label.
    entity = candidates[0] if len(candidates) == 1 else None
    return i, 'supported', entity
