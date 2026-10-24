"""Compare actual emitted integer-reduction blocks, including partial errors."""

import argparse
import ast
import builtins
import hashlib
import json
from pathlib import Path
import random


def extract(path, candidate):
    tree = ast.parse(path.read_text())
    consumer, = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                 and n.name.startswith('_bcopt_region_consumer_')]
    version = next(n for n in ast.walk(consumer) if isinstance(n, ast.If)
                   and isinstance(n.test, ast.Name) and n.test.id == '_bcopt_entry_prepared_ready_0')
    region = ast.Module(body=version.body, type_ignores=[])
    if candidate:
        sequence, = [body for parent in ast.walk(region) for _, body in ast.iter_fields(parent)
                     if isinstance(body, list) and body and isinstance(body[0], ast.If)
                     and isinstance(body[0].test, ast.Compare) and isinstance(body[0].test.left, ast.Name)
                     and body[0].test.left.id.startswith(('_bcopt_totals80_valid', '_bcopt_base_total_valid'))]
        statements = sequence[:2]
    else:
        loop, = [n for n in ast.walk(region) if isinstance(n, ast.For)
                 and isinstance(n.target, ast.Name) and n.target.id == '_bcopt_entry_local_11'
                 and isinstance(n.iter, ast.Name) and n.iter.id == 'route']
        statements = [loop]
    return compile(ast.fix_missing_locations(ast.Module(body=statements, type_ignores=[])), '<actual-integer-reduction>', 'exec')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    original, changed = extract(args.baseline, False), extract(args.candidate, True)
    candidate_names = {n.id for n in ast.walk(ast.parse(args.candidate.read_text())) if isinstance(n, ast.Name)}
    generic_initial = {name: None for name in candidate_names if name.startswith('_bcopt_base_total_valid')}
    generic_initial.update({name: False for name in candidate_names if name.startswith('_bcopt_base_total_ready')})
    generic_initial.update({name: builtins for name in candidate_names if name.startswith('_bcopt_base_total_builtins')})
    rng, digest, cases, errors = random.Random(80105), hashlib.sha256(), 0, 0
    outputs = ('_bcopt_entry_local_37', '_bcopt_entry_local_38', '_bcopt_entry_local_46',
               '_bcopt_entry_local_4', '_bcopt_entry_local_11', '_bcopt_entry_local_24', '_bcopt_entry_local_25')
    for trial in range(1000):
        n = rng.randrange(1, 9)
        rows = tuple(((i, i), *(rng.randrange(-10**40, 10**40) if trial % 2 else rng.randrange(-5, 6)
                               for _ in range(4))) for i in range(n))
        peaks = tuple(row[3]+row[4] for row in rows)
        if trial % 9 == 0:
            peaks = peaks[:-1]
        for width in (2, 3, 5, 12):
            base = tuple(rng.randrange(-n, n) for _ in range(width-1))
            if trial % 11 == 0:
                base = (*base[:-1], n)
            environment = dict(_bcopt_entry_local_32=rows, _bcopt_entry_local_5=peaks,
                               _bcopt_fused_route=base, _bcopt_region_builtins_1=builtins)
            candidate = dict(environment, _bcopt_totals80_valid=None, _bcopt_totals80_ready=False)
            candidate.update(generic_initial)
            for item in (-1, 0, n):
                for position in range(width):
                    route = base[:position]+(item,)+base[position:]
                    initial = dict(_bcopt_entry_local_37=0, _bcopt_entry_local_38=0,
                                   _bcopt_entry_local_46=0, _bcopt_entry_local_4=None,
                                   _bcopt_entry_local_11=None, _bcopt_entry_local_24=None, _bcopt_entry_local_25=None,
                                   route=route, _bcopt_fused_camp_index=item)
                    baseline = dict(environment, **initial)
                    candidate.update(initial)
                    outcomes = []
                    for code, namespace in ((original, baseline), (changed, candidate)):
                        error = None
                        try:
                            exec(code, namespace)
                        except IndexError as failure:
                            error = type(failure).__name__, str(failure)
                        outcomes.append((tuple(namespace[name] for name in outputs), error))
                    assert outcomes[0] == outcomes[1], (trial, width, item, position, outcomes)
                    cases += 1
                    errors += outcomes[0][1] is not None
                    digest.update(repr(outcomes[1]).encode())
    report = dict(status='complete', cases=cases, errors=errors, exact_outputs_partial_errors_and_final_loop_locals_equal=True,
                  observations_sha256=digest.hexdigest(), baseline_sha256=hashlib.sha256(args.baseline.read_bytes()).hexdigest(),
                  candidate_sha256=hashlib.sha256(args.candidate.read_bytes()).hexdigest())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
