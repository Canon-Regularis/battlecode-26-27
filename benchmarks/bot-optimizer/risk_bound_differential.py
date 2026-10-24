"""Stress the research weighted-average score bound over its guarded domain."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import struct


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rng, digest = random.Random(807582), hashlib.sha256()
    epsilon, cap = 2.0**-40, 2**40
    risks = [0.0, -0.0, 1.0, math.nextafter(1.0, 0.0), 0.5, math.nextafter(0.5, 1.0),
             2.0**-1074, 2.0**-1022, 2.0**-53]
    risks.extend(struct.unpack('>d', struct.pack('>Q', rng.randrange(0x3ff0000000000001)))[0] for _ in range(1000))
    strict = 0
    for case in range(20000):
        count = rng.randrange(1, 17)
        weights = [rng.choice(risks) if case % 2 else rng.random() for _ in range(count)]
        altar = rng.choice(risks) if case % 2 else rng.random()
        duration = lambda: rng.choice([0, 1, cap, cap-1]) if case % 3 == 0 else rng.randrange(cap)
        legs, service = [duration() for _ in range(count+1)], [duration() for _ in range(count)]
        gems, gold = rng.randrange(16*cap), rng.randrange(16*cap)
        tribute = math.ceil(gems/10)
        active = sum(legs)+sum(service)+tribute
        period = max(active, 1, rng.randrange(2*cap))
        initial = legs[0]*(altar+weights[0])/2
        exposure = initial + legs[1]*(weights[-1]+altar)/2
        for index in range(count-1):
            exposure += legs[index+2]*(weights[index]+weights[index+1])/2
        exposure += sum(value*weight for value, weight in zip(service, weights))
        exposure += (tribute+period-active)*altar
        risk = min(1.0, max(0.0, exposure/period))
        tolerance = rng.choice(risks) if case % 2 else rng.random()
        factor = 1-(1-tolerance)*risk
        minimum = min(altar, *weights)
        lower = max(0.0, minimum-epsilon)
        upper = min(1.0, 1-(1-tolerance)*lower+epsilon)
        first_deposit = active-legs[0]+duration()
        base = (gems+rng.uniform(0, 1e6)*gold)/(period+rng.uniform(0, 1e6)*first_deposit)
        score, bound = base*factor, base*upper
        assert risk >= lower and factor <= upper and score <= bound, (case, risk, lower, factor, upper, score, bound)
        strict += bound < base
        digest.update(repr((risk.hex(), score.hex(), bound.hex())).encode())
    report = dict(status='complete', cases=20000, strict_improvements_over_base=strict,
                  lower_risk_and_upper_score_bounds_hold=True,
                  domain='1..16 terms, nonnegative integer durations<=2**40, risks/tolerance in [0,1]',
                  observations_sha256=digest.hexdigest())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
