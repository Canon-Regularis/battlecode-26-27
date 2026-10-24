"""Shared-key history and future field-finalizer witnesses for dict merging."""

import argparse
import hashlib
import json
from pathlib import Path
import random


def observe(prefill, instances, width, order, mapping):
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
            setattr(seed, f'key{field}', index)
        seeds.append(seed)
    item = Record()
    namespace = item.__dict__
    keys = [f'key{field}' for field in range(width)]
    if mapping:
        dict.update(namespace, {key: index for index, key in enumerate(keys)})
    else:
        for index, key in enumerate(keys):
            namespace[key] = index
    fields = list(namespace.items())
    del namespace, item
    probe = Record()
    for key in order:
        setattr(probe, key, Watch(key))
    del probe
    assert len(logs) == len(order)
    return fields, logs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    observations = []
    rng = random.Random(7317)
    for prefill in range(41):
        for instances in (0, 1, 10, 40):
            for width in (1, 4, 12, 16):
                order = [f'key{index}' for index in range(max(prefill, width))] + ['extra_a', 'extra_b']
                rng.shuffle(order)
                expected = observe(prefill, instances, width, order, False)
                actual = observe(prefill, instances, width, order, True)
                assert actual == expected, (prefill, instances, width, expected, actual)
                observations.append((prefill, instances, width, actual))
    report = dict(status='complete', cases=len(observations),
                  dictionary_order_and_future_field_finalizers_equal=True,
                  observations_sha256=hashlib.sha256(json.dumps(observations).encode()).hexdigest())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
