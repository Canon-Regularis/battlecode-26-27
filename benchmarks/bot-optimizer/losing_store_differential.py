"""Future shared-key/finalizer witnesses for omitted losing-record stores."""

import argparse
import hashlib
import json
from pathlib import Path
import random


def observe(prefill, instances, width, losses, order, omit, omit_dict=False):
    class Record:
        pass
    logs = []
    class Watch:
        def __init__(self, key):
            self.key = key
        def __del__(self):
            logs.append(self.key)
    seeds = []
    for index in range(instances):
        seed = Record()
        for field in range(prefill):
            setattr(seed, f'prior{field}', index)
        seeds.append(seed)
    keys = [f'field{index}' for index in range(width)]
    winner = object.__new__(Record)
    namespace = winner.__dict__
    for index, key in enumerate(keys):
        namespace[key] = index
    del namespace
    for loss in range(losses):
        item = object.__new__(Record)
        if omit_dict and omit and loss % 7 != 6:
            del item
            continue
        namespace = item.__dict__
        if not omit or loss % 7 == 6:
            for index, key in enumerate(keys):
                namespace[key] = index
        del namespace, item
    # Later externally visible growth and deletion must see the same key history.
    for key in ('later_a', 'later_b', 'later_c'):
        winner.__dict__[key] = 1
    del winner.__dict__['later_b']
    winner.__dict__['later_b'] = 2
    visible = list(winner.__dict__.items())
    probe = Record()
    for key in order:
        setattr(probe, key, Watch(key))
    del probe
    assert len(logs) == len(order)
    return visible, logs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--omit-dict', action='store_true')
    args = parser.parse_args()
    rng, digest, cases = random.Random(8076), hashlib.sha256(), 0
    for prefill in range(41):
        for instances in (0, 1, 10, 40):
            for width in (4, 12, 16):
                for losses in (1, 2, 20, 50):
                    order = ([f'prior{i}' for i in range(prefill)] + [f'field{i}' for i in range(width)]
                             + ['later_a', 'later_b', 'later_c', 'extra'])
                    rng.shuffle(order)
                    expected = observe(prefill, instances, width, losses, order, False)
                    actual = observe(prefill, instances, width, losses, order, True, omit_dict=args.omit_dict)
                    assert actual == expected, (prefill, instances, width, losses, expected, actual)
                    cases += 1
                    digest.update(repr(actual).encode())
    report = dict(status='complete', cases=cases, future_key_growth_deletion_and_field_finalizers_equal=True,
                  allocation_preserved=True, dict_materialization_preserved=not args.omit_dict,
                  observations_sha256=digest.hexdigest())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
