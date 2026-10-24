"""SDK-driven experiments. Game-dependent setup happens only inside run_*()."""
import array
import bisect
import collections
import json
import operator
import struct
import sys

import cambc as bc
from cambc import game_map as gm


def measure(name, fn, repeats=30):
    for _ in range(20):
        result = fn()
    samples = []
    fuel = bc.fuel_remaining
    for _ in range(5):
        start = fuel()
        for _ in range(repeats):
            result = fn()
        spent = start - fuel()
        assert spent > 0, "measurement crossed a turn boundary"
        samples.append(spent / repeats)
    median = sorted(samples)[2]
    print("BENCH " + json.dumps({"name": name, "fuel_per_call": median, "samples": samples}), flush=True)
    return median


def pair(name, baseline, alternative, snapshot=lambda x: x, repeats=30):
    left = snapshot(baseline())
    right = snapshot(alternative())
    assert left == right, (name, repr(left)[:200], repr(right)[:200])
    old = measure(name + "/baseline", baseline, repeats)
    new = measure(name + "/alternative", alternative, repeats)
    print("PAIR " + json.dumps({"name": name, "baseline": old, "alternative": new, "ratio": old / new}), flush=True)


def board_bytes(board):
    return board.export_linear_buffer()


def run_draft():
    width, height = gm.width(), gm.height()
    points = tuple(bc.Vec2(x, y) for y in range(height) for x in range(width))
    center = bc.Vec2(width // 2, height // 2)
    n = width * height
    boards = []
    for step in (3, 5, 7, 11):
        board = bc.Bitboard()
        for i, p in enumerate(points):
            if i % step < 2:
                board.set(p)
        boards.append(board)
    a, b, c, d = boards
    work = bc.Bitboard()
    empty = bc.Bitboard()
    print("META " + json.dumps({"phase": "draft", "version": sys.version,
        "width": width, "height": height, "bool_empty_bitboard": bool(empty),
        "field_copy_from": hasattr(bc.DistanceField, "copy_from"),
        "bitboard_linear_bytes": len(empty.export_linear_buffer()),
        "bitboard_linear_size": empty.linear_buffer_size()}), flush=True)

    def loop_intersection():
        return sum(1 for p in a.positions() if b.is_set(p))

    pair("intersection_count", loop_intersection, lambda: (a & b).count())
    pair("filter_positions", lambda: [p for p in a.positions() if b.is_set(p)],
         lambda: (a & b).positions())
    cached_points = tuple(a.positions())
    pair("overlap_any_early_cached_points", lambda: any(b.is_set(p) for p in cached_points),
         lambda: not (a & b).is_empty(), repeats=200)
    pair("overlap_any_none_cached_points", lambda: any(empty.is_set(p) for p in cached_points),
         lambda: not (a & empty).is_empty())

    def union_copy():
        out = a.copy()
        out |= b
        out |= c
        out |= d
        return out

    def union_reuse():
        out = work
        out.clear()
        out |= a
        out |= b
        out |= c
        out |= d
        return out

    pair("union_chain_vs_copy_inplace", lambda: a | b | c | d, union_copy, board_bytes)
    pair("union_chain_vs_reuse", lambda: a | b | c | d, union_reuse, board_bytes)
    static_blocked = gm.walls() | gm.holes() | gm.altars() | gm.spawn_region(bc.Team.ENEMY)
    pair("cache_static_terrain_union",
         lambda: gm.walls() | gm.holes() | gm.altars() | gm.spawn_region(bc.Team.ENEMY) | a | b | c,
         lambda: static_blocked | a | b | c, board_bytes)

    for radius in (3, 8):
        shape_points = tuple(p for p in points if p.chebyshev_distance(center) <= radius)

        def draw_loop():
            work.clear()
            for p in shape_points:
                work.set(p)
            return work

        def draw_native():
            work.clear()
            work.draw_chebyshev(center, radius)
            return work

        pair("draw_chebyshev_r" + str(radius), draw_loop, draw_native, board_bytes)

    integers = tuple(int.from_bytes(board.export_raw_buffer(), "little") for board in boards)

    def board_scores():
        return [(a & mask).count() for mask in boards]

    def int_scores():
        value = integers[0]
        return [(value & mask).bit_count() for mask in integers]

    def int_scores_with_conversion():
        values = tuple(int.from_bytes(board.export_raw_buffer(), "little") for board in boards)
        value = values[0]
        return [(value & mask).bit_count() for mask in values]

    pair("mask_scores_preconverted_int", board_scores, int_scores)
    pair("mask_scores_conversion_included", board_scores, int_scores_with_conversion)

    roots = bc.Bitboard()
    roots.set(center)
    field = bc.DistanceField()
    field.compute(empty, roots, work)
    near = bc.Vec2(center.x + 2, center.y)
    destinations = bc.Bitboard()
    destinations.set(near)
    output = bc.DistanceField()
    visited = bc.Bitboard()

    def full_search():
        output.compute(empty, roots, visited)
        return output.get(near)

    def target_search():
        output.compute_to(empty, roots, destinations, visited)
        return output.get(near)

    def bounded_search():
        output.compute(empty, roots, visited, 3)
        return output.get(near)

    pair("distance_search_target_two_tiles_away", full_search, target_search)
    pair("distance_search_bound_three", full_search, bounded_search)
    pair("next_move_single", lambda: field.next_moves_from(near)[0], lambda: field.next_move_from(near), repeats=200)

    root_boards = []
    multi_roots = bc.Bitboard()
    for p in (points[0], points[width-1], points[-width], points[-1]):
        root = bc.Bitboard()
        root.set(p)
        multi_roots.set(p)
        root_boards.append(root)

    def nearest_separate_searches():
        distances = []
        for root in root_boards:
            output.compute(empty, root, visited)
            distances.append(output.get(center))
        return min(distances)

    def nearest_multisource():
        output.compute(empty, multi_roots, visited)
        return output.get(center)

    pair("distance_multisource_four_goals", nearest_separate_searches, nearest_multisource)

    source_data = array.array("H", ((i * 17) % 500 for i in range(n)))
    field.import_linear_buffer(source_data)
    exported = field.export_linear_buffer()
    print("META " + json.dumps({"export_type": type(exported).__name__, "export_length": len(exported),
        "linear_size": field.linear_buffer_size(), "export_first": list(exported[:8])}), flush=True)
    assert len(exported) == n
    assert list(exported) == list(source_data)
    linear_out = bytearray(2 * n)

    for count in (1, 8, 32, 128, n):
        query_points = points[:count]
        indexes = tuple(p.y * width + p.x for p in query_points)

        def scalar_queries():
            return [field.get(p) for p in query_points]

        def exported_queries():
            values = field.export_linear_buffer()
            return [values[i] for i in indexes]

        def exported_into_queries():
            field.export_linear_buffer_into(linear_out)
            values = memoryview(linear_out).cast("H")
            return [values[i] for i in indexes]

        def exported_list_queries():
            values = field.export_linear_buffer().tolist()
            return [values[i] for i in indexes]

        pair("distance_export_q" + str(count), scalar_queries, exported_queries)
        pair("distance_export_list_q" + str(count), scalar_queries, exported_list_queries)
        if count in (32, n):
            pair("distance_export_into_q" + str(count), scalar_queries, exported_into_queries)

    pair("distance_vec2_creation", lambda: [field.get(bc.Vec2(i % width, i // width)) for i in range(128)],
         lambda: [field.get(p) for p in points[:128]])
    view = field.export_linear_buffer()
    pair("distance_frozen_dense_cache_128", lambda: [field.get(p) for p in points[:128]],
         lambda: [view[i] for i in range(128)])
    cached_list = view.tolist()
    pair("distance_frozen_list_cache_128", lambda: [field.get(p) for p in points[:128]],
         lambda: [cached_list[i] for i in range(128)])
    pair("distance_row_sum", lambda: sum(field.get(p) for p in points[:128]),
         lambda: sum(cached_list[:128]))

    def copy_loop():
        for p in points:
            output.set(p, field.get(p))
        return output

    def copy_native():
        output.copy_from(field)
        return output

    def masked_loop():
        output.copy_from(field)
        for p in a.positions():
            output.set(p, 13)
        return output

    const_field = bc.DistanceField()
    const_field.import_linear_buffer(array.array("H", [13]) * n)

    def masked_native():
        output.copy_from(field)
        output.copy_from(const_field, a)
        return output

    pair("distance_copy_from", copy_loop, copy_native, lambda f: f.export_linear_buffer(), repeats=10)
    pair("distance_copy_reuse", lambda: field.copy(), copy_native, lambda f: f.export_linear_buffer())
    pair("distance_masked_copy", masked_loop, masked_native, lambda f: f.export_linear_buffer(), repeats=10)

    def import_loop():
        for p, value in zip(points, source_data):
            output.set(p, value)
        return output

    def import_native():
        output.import_linear_buffer(source_data)
        return output

    pair("distance_bulk_import", import_loop, import_native, lambda f: f.export_linear_buffer(), repeats=10)

    # Real open-grid path distances are small, unlike the artificial values above.
    field.compute(empty, roots, work)
    for count in (128, n):
        query_points = points[:count]

        def scalar_path_distances():
            return [field.get(p) for p in query_points]

        def list_path_distances():
            values = field.export_linear_buffer().tolist()
            return [values[i] for i in range(count)]

        pair("real_distance_export_list_q" + str(count), scalar_path_distances, list_path_distances)

    cached_path_distances = field.export_linear_buffer().tolist()
    pair("real_distance_frozen_list_cache_128", lambda: [field.get(p) for p in points[:128]],
         lambda: [cached_path_distances[i] for i in range(128)])

    old_view = field.export_linear_buffer()
    old_value = old_view[0]
    field.set(points[0], 123)
    print("META " + json.dumps({"export_view_tracks_mutation": old_view[0] != old_value,
        "field_mutated_value": field.get(points[0]), "view_format": old_view.format,
        "view_itemsize": old_view.itemsize, "view_nbytes": old_view.nbytes}), flush=True)

    # Compare an eight-neighbour Python BFS with the SDK reachable-mask operation.
    blocked = gm.walls() | gm.holes()
    blocked.set(center, False)
    packed_blocked = blocked.export_linear_buffer()
    blocked_data = tuple(bool(packed_blocked[i >> 3] & (1 << (i & 7))) for i in range(n))
    frontier, scratch = bc.Bitboard(), bc.Bitboard()

    def bfs_python(radius):
        seen = bytearray(n)
        origin = center.y * width + center.x
        seen[origin] = 1
        queue = collections.deque([(origin, 0)])
        while queue:
            index, depth = queue.popleft()
            if depth == radius:
                continue
            x, y = index % width, index // width
            for dy in (-1, 0, 1):
                yy = y + dy
                if not 0 <= yy < height:
                    continue
                for dx in (-1, 0, 1):
                    xx = x + dx
                    if not 0 <= xx < width:
                        continue
                    nxt = yy * width + xx
                    if not seen[nxt] and not blocked_data[nxt]:
                        seen[nxt] = 1
                        queue.append((nxt, depth + 1))
        return seen

    def reachable_snapshot(result):
        if isinstance(result, bc.Bitboard):
            return tuple(result.is_set(p) for p in points)
        return tuple(bool(value) for value in result)

    for radius in (4, 12):
        pair("reachable_bfs_r" + str(radius), lambda: bfs_python(radius),
             lambda: blocked.reachable_tiles(center, radius), reachable_snapshot, repeats=10)

        def reachable_reuse():
            blocked.reachable_tiles_into(center, radius, work, frontier, scratch)
            return work

        pair("reachable_scratch_r" + str(radius),
             lambda: blocked.reachable_tiles(center, radius),
             reachable_reuse, board_bytes)

    pair("field_min_native_callback", lambda: min(points[:128], key=lambda p: field.get(p)),
         lambda: min(points[:128], key=field.get))

    records = tuple((i, (i * 71) % 149) for i in range(128))
    pair("min_itemgetter", lambda: min(records, key=lambda row: row[1]),
         lambda: min(records, key=operator.itemgetter(1)))
    pair("min_vs_sorted", lambda: sorted(records, key=operator.itemgetter(1))[0],
         lambda: min(records, key=operator.itemgetter(1)))
    needles = tuple(range(64, 128))
    sorted_values = tuple(range(256))

    def lower_bound_loop():
        return [next(i for i, value in enumerate(sorted_values) if value >= target) for target in needles]

    pair("bisect_lower_bound", lower_bound_loop,
         lambda: [bisect.bisect_left(sorted_values, target) for target in needles])

    p, q = bc.Vec2(12, 13), bc.Vec2(4, 5)
    pair("vector_dot", lambda: p.x*q.x + p.y*q.y, lambda: p.dot(q), repeats=200)
    pair("vector_length_squared", lambda: p.x*p.x + p.y*p.y, lambda: p.length_squared(), repeats=200)

    numbers = tuple(range(128))
    packed = struct.pack("<128H", *numbers)
    pair("binary_unpack_batch", lambda: tuple(int.from_bytes(packed[i:i+2], "little") for i in range(0, len(packed), 2)),
         lambda: struct.unpack("<128H", packed))
    pair("binary_iter_unpack", lambda: [struct.unpack_from("<HH", packed, i) for i in range(0, len(packed), 4)],
         lambda: list(struct.iter_unpack("<HH", packed)))
    pack_out1, pack_out2 = bytearray(4 * len(numbers)), bytearray(4 * len(numbers))
    record = struct.Struct("<I")

    def pack_slices():
        for i, value in enumerate(numbers):
            pack_out1[4*i:4*i+4] = struct.pack("<I", value)
        return pack_out1

    def pack_into():
        for i, value in enumerate(numbers):
            record.pack_into(pack_out2, 4*i, value)
        return pack_out2

    pair("binary_pack_into", pack_slices, pack_into, bytes)
    print("DONE draft", flush=True)


def run_game():
    me = bc.me()
    pos = me.position()
    print("META " + json.dumps({"phase": "game", "champion": int(me),
        "visible_camps": len(bc.vision.camps()), "shared_size": len(bc.shared_memory)}), flush=True)

    def repeated_state():
        return me.can_move(), me.can_attack(), me.can_cast(), me.is_recalling(), me.is_teleporting()

    flags = (bc.ChampionState.CAN_MOVE, bc.ChampionState.CAN_ATTACK, bc.ChampionState.CAN_CAST,
             bc.ChampionState.RECALLING, bc.ChampionState.TELEPORTING)
    move, attack, cast, recall, teleport = flags

    def once_state():
        state = me.state()
        return move in state, attack in state, cast in state, recall in state, teleport in state

    pair("champion_state_snapshot_five", repeated_state, once_state, repeats=200)
    state = me.state()
    combined = move | attack | cast
    for sample in (bc.ChampionState.empty(), move, attack, combined):
        assert sample.intersects(combined) == bool(sample & combined)
        assert (combined in sample) == ((sample & combined) == combined)
    pair("flags_any_intersects", lambda: bool(state & combined), lambda: state.intersects(combined), repeats=200)
    pair("flags_all_contains", lambda: (state & combined) == combined, lambda: combined in state, repeats=200)
    def once_position():
        p = me.position()
        return p.x, p.y

    pair("champion_position_xy", lambda: (me.position().x, me.position().y), once_position, repeats=200)

    def reacquire_abilities():
        fresh = bc.vision.champion_at(pos)
        return tuple(a.info() for a in fresh.abilities())

    pair("retain_champion_ability_cache", reacquire_abilities,
         lambda: tuple(a.info() for a in me.abilities()))

    def repeated_buffs():
        return me.buffs().has_shield(), me.buffs().has_stun(), me.buffs().has_enhanced_attack()

    def once_buffs():
        buffs = me.buffs()
        return buffs.has_shield(), buffs.has_stun(), buffs.has_enhanced_attack()

    pair("buff_snapshot_three", repeated_buffs, once_buffs)

    slots = me.abilities()

    def readiness_snapshot():
        can_cast = me.can_cast()
        return tuple(a.info() is not None and a.cooldown() == 0 and can_cast for a in slots)

    pair("ability_readiness_two", lambda: tuple(a.is_ready() for a in slots), readiness_snapshot)
    ability = slots[0]
    targets = (bc.AbilityTargetMask.CAMPS, bc.AbilityTargetMask.ENEMIES, bc.AbilityTargetMask.ALLIES,
               bc.AbilityTargetMask.SELF, bc.AbilityTargetMask.GROUND)

    def target_snapshot():
        mask = ability.valid_targets()
        return tuple(target in mask for target in targets)

    pair("ability_target_mask_five", lambda: (ability.can_target_camps(), ability.can_target_enemies(),
         ability.can_target_allies(), ability.can_target_self(), ability.can_target_ground()), target_snapshot)

    camp_work = bc.Bitboard()

    def awake_loop():
        camp_work.clear()
        for camp in bc.vision.camps():
            if camp.is_awake():
                camp_work.set(camp.position())
        return camp_work

    pair("awake_camp_bulk_mask", awake_loop, bc.vision.awake_camp_tiles, board_bytes)
    pair("enemy_champion_prefilter", lambda: [c for c in bc.vision.champions() if c.is_enemy()],
         lambda: bc.vision.champions(bc.Team.ENEMY))
    visible = bc.vision.visible_tiles()
    occupied = bc.vision.champion_tiles() | bc.vision.camp_tiles()
    empty_tile = next(p for p in visible.positions() if not occupied.is_set(p))

    def exists_by_exception():
        try:
            bc.vision.champion_at(empty_tile)
        except bc.Error:
            return False
        return True

    pair("existence_empty_tile", exists_by_exception, lambda: bc.vision.has_champion(empty_tile), repeats=200)
    pair("existence_occupied_tile", lambda: bc.vision.champion_at(pos) is not None,
         lambda: bc.vision.has_champion(pos), repeats=200)
    pair("vision_single_query", lambda: bc.vision.visible_tiles().is_set(pos),
         lambda: bc.vision.in_vision(pos), repeats=200)
    view_points = tuple(visible.positions())
    for count in (1, 8, 32, 128):
        queries = (view_points * (1 + count // len(view_points)))[:count]

        def direct_queries():
            return [bc.vision.in_vision(p) for p in queries]

        def mask_queries():
            mask = bc.vision.visible_tiles()
            return [mask.is_set(p) for p in queries]

        pair("vision_batched_q" + str(count), direct_queries, mask_queries)

    for count in sorted({min(8, len(bc.shared_memory)), min(128, len(bc.shared_memory))}):
        data = bytes(i % 256 for i in range(count))
        out = bytearray(count)

        def write_scalar():
            for i, value in enumerate(data):
                bc.shared_memory[i] = value

        def write_bulk():
            bc.shared_memory.write(0, data)

        pair("shared_write_" + str(count), write_scalar, write_bulk)
        assert bytes(bc.shared_memory[i] for i in range(count)) == data

        def read_scalar():
            for i in range(count):
                out[i] = bc.shared_memory[i]
            return out

        def read_bulk():
            bc.shared_memory.read(0, out)
            return out

        pair("shared_read_" + str(count), read_scalar, read_bulk, bytes)

    table = {me: 7}
    ids = {int(me): 7}
    handle = int(me)
    pair("champion_dict_id_conversion", lambda: table[me], lambda: ids[int(me)], repeats=200)
    pair("champion_dict_preextracted_id", lambda: table[me], lambda: ids[handle], repeats=200)
    print("DONE game", flush=True)
