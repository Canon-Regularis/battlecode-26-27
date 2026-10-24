"""Bitwise checks of actual emitted base-edge/prefix blocks and error order."""

import argparse
import ast
import hashlib
import json
from pathlib import Path
import random
import struct


def blocks(path):
    tree = ast.parse(path.read_text())
    consumer, = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                 and n.name.startswith('_bcopt_region_consumer_')]
    result = {}
    for wrapper in ast.walk(consumer):
        if not (isinstance(wrapper, ast.For) and isinstance(wrapper.target, ast.Name)
                and wrapper.target.id == '_bcopt_position_once'):
            continue
        route = wrapper.body[0].value
        width = len(route.elts)
        position, = [i for i, n in enumerate(route.elts) if n.id == '_bcopt_fused_camp_index']
        prepared, = [n for n in ast.walk(wrapper) if isinstance(n, ast.If)
                      and isinstance(n.test, ast.Name) and n.test.id == '_bcopt_entry_prepared_ready_0']
        found = []
        for parent in ast.walk(prepared.body[0]):
            for _, body in ast.iter_fields(parent):
                if not isinstance(body, list):
                    continue
                ends = [i for i, n in enumerate(body) if isinstance(n, ast.Assign)
                        and len(n.targets) == 1 and isinstance(n.targets[0], ast.Tuple)
                        and [getattr(x, 'id', None) for x in n.targets[0].elts]
                        == ['_bcopt_entry_local_19', '_bcopt_entry_local_14']]
                if not ends:
                    continue
                end, = ends
                starts = [i for i, n in enumerate(body[:end])
                          if (isinstance(n, ast.Assign) and len(n.targets) == 1
                              and isinstance(n.targets[0], ast.Name) and n.targets[0].id == '_bcopt_entry_local_16')
                          or (isinstance(n, ast.If) and isinstance(n.test, ast.Compare)
                              and isinstance(n.test.left, ast.Name)
                              and n.test.left.id.startswith(('_bcopt_baseedge80_prefix_', '_bcopt_base_prefix')))]
                start, = starts
                found.append(compile(ast.fix_missing_locations(ast.Module(body=body[start:end+1], type_ignores=[])),
                                     '<actual-emitted-risk-fold>', 'exec'))
        kernel, = found
        result[width, position] = kernel
    assert len(result) == 77
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    before, after = blocks(args.baseline), blocks(args.candidate)
    cache_names = {n.id for n in ast.walk(ast.parse(args.candidate.read_text())) if isinstance(n, ast.Name)
                   and n.id.startswith(('_bcopt_base_edge', '_bcopt_base_prefix'))}
    rng, digest, cases, errors = random.Random(8099), hashlib.sha256(), 0, 0
    special = [0.0, -0.0, float('inf'), float('-inf'), float('nan'),
               struct.unpack('d', struct.pack('Q', 0x7ff8000000000042))[0]]
    for trial in range(1000):
        n = 4
        def value():
            return rng.choice(special) if trial % 5 == 0 else rng.uniform(-1, 1)*2.0**rng.randrange(-1000, 1001)
        pair = tuple(tuple(value() for _ in range(n)) for _ in range(n))
        start = tuple(tuple(value() for _ in range(2)) for _ in range(n))
        finish = tuple(tuple(value() for _ in range(2)) for _ in range(n))
        for width in range(2, 13):
            base = tuple(rng.randrange(-n, n) for _ in range(width-1))
            if trial % 13 == 0:
                base = (n, *base[1:])
            common = dict(_bcopt_entry_local_6=start, _bcopt_entry_local_7=finish,
                          _bcopt_entry_local_8=pair, altar_index=trial % 2)
            common.update({f'_bcopt_direct_item_{i}': x for i, x in enumerate(base)})
            candidate = dict(common)
            candidate.update({f'_bcopt_baseedge80_{i}': None for i in range(11)})
            candidate.update({f'_bcopt_baseedge80_prefix_{i}': None for i in range(1, 12)})
            candidate.update({name: None for name in cache_names})
            for item in (-1, n if trial % 7 == 0 else 1, 0):
                # Skip selected positions to exercise lazy/nonconsecutive reuse.
                for position in range(width):
                    if trial % 3 == 0 and position % 2:
                        continue
                    route = base[:position]+(item,)+base[position:]
                    original = dict(common, route=route, _bcopt_fused_camp_index=item)
                    candidate.update(route=route, _bcopt_fused_camp_index=item)
                    outcomes = []
                    for code, namespace in ((before[width, position], original), (after[width, position], candidate)):
                        try:
                            exec(code, namespace)
                            outcome = (struct.pack('d', namespace['_bcopt_entry_local_16']).hex(),
                                       namespace['_bcopt_entry_local_19'], namespace['_bcopt_entry_local_14'])
                        except (IndexError, OverflowError) as error:
                            outcome = (type(error).__name__, str(error))
                        outcomes.append(outcome)
                    assert outcomes[0] == outcomes[1], (trial, width, item, position, outcomes)
                    errors += outcomes[0][0] == 'IndexError'
                    cases += 1
                    digest.update(repr(outcomes[1]).encode())
    report = dict(status='complete', cases=cases, errors=errors, bitwise_folds_and_errors_equal=True,
                  observations_sha256=digest.hexdigest(),
                  baseline_sha256=hashlib.sha256(args.baseline.read_bytes()).hexdigest(),
                  candidate_sha256=hashlib.sha256(args.candidate.read_bytes()).hexdigest())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
