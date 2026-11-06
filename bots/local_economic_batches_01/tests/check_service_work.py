"""Check actual C++ arithmetic against independent Fraction binary32 meanings."""
import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
REFERENCE = ROOT / '.cambc/campaign-2026-11-05/service-work-oracle-v1'


def atom(raw):
    if raw is None:
        raise ValueError('unknown')
    value = struct.unpack('<f', bytes.fromhex(raw)[::-1])[0]
    if not math.isfinite(value) or value < 0:
        raise ValueError('unsupported')
    return Fraction.from_float(value)


def units(value):
    scaled = value * (1 << 149)
    assert scaled.denominator == 1
    return scaled.numerator


def domain(values):
    spans = []
    for x in values:
        if x:
            numerator, denominator = x.as_integer_ratio()
            exponent = -(denominator.bit_length() - 1)
            spans.append((exponent + (numerator & -numerator).bit_length() - 1,
                          exponent + numerator.bit_length() - 1))
    q = min((a for a, _ in spans), default=0)
    high = max((b for _, b in spans), default=0)
    return [int(not spans or high - q + 1 + 8 <= 64), q, high]


def limbs(value):
    return [(value >> (64 * i)) & ((1 << 64) - 1) for i in range(5)]


def main():
    inputs = (REFERENCE / 'inputs.json').read_bytes()
    frozen = json.loads((REFERENCE / 'frozen-inputs.json').read_text())
    assert hashlib.sha256(inputs).hexdigest() == frozen['inputs_sha256']
    data = json.loads(inputs)
    commands, expected = [], []

    def atoms(raw):
        commands.append('A ' + str(len(raw)) + ' ' + ' '.join(x or 'unknown' for x in raw))
        try:
            values = [atom(x) for x in raw]
        except ValueError:
            expected.append(('U', []))
        else:
            expected.append(('S', domain(values) + [v for x in values for v in limbs(units(x))]))

    for case in data['atoms']:
        atoms([case['bits']])
    for case in data['dirty_transitions']:
        atoms(case['before'])
        atoms(case['after'])
    victims = 0
    for case in data['scenes']:
        rows = case['victims']
        commands.append('F ' + str(len(rows)) + ' ' + ' '.join(
            ' '.join([r['hp'] or 'unknown', r['first'] or 'unknown', r['second'] or 'unknown',
                      str(int(r['first_applies'])), str(int(r['second_applies']))]) for r in rows))
        try:
            values = [atom(r[k]) for r in rows for k in ('hp', 'first', 'second')]
        except ValueError:
            expected.append(('U', []))
            continue
        total, removals, details = Fraction(0), 0, []
        for row in rows:
            hp, a, b = (atom(row[k]) for k in ('hp', 'first', 'second'))
            if not row['first_applies']:
                a = Fraction(0)
            if not row['second_applies']:
                b = Fraction(0)
            initial = min(hp, a)
            remaining = hp - initial
            marginal = min(b, remaining)
            work = initial + marginal
            total += work
            removals += int(hp > 0 and hp == work)
            details.extend(v for x in (initial, remaining, marginal, work) for v in limbs(units(x)))
        victims += len(rows)
        expected.append(('S', domain(values) + [removals] + limbs(units(total)) + details))
    for case in data['limb_algebra']:
        a, b = int(case['a']), int(case['b'])
        commands.append('L ' + ' '.join(map(str, limbs(a) + limbs(b))))
        added, subtracted = a + b < (1 << 320), a >= b
        expected.append(('L', [int(added)] + limbs(a + b if added else 0) +
                         [int(subtracted)] + limbs(a - b if subtracted else 0)))
    result = subprocess.run([sys.argv[1], '--probe'], input='\n'.join(commands) + '\n',
                            text=True, capture_output=True, timeout=20, check=True)
    lines = result.stdout.splitlines()
    assert len(lines) == len(expected), (len(lines), len(expected), result.stderr)
    for i, (line, (kind, values)) in enumerate(zip(lines, expected)):
        tokens = line.split()
        assert tokens[0] == kind and list(map(int, tokens[1:])) == values, (i, commands[i][:200], line[:200])
    print(f'PASS: actual C++ exact work against frozen Fraction reference; {len(lines)} cases, '
          f'{victims} supported victim rows, signed zeros/invalids, W56/W57, dirty domains, 320-bit carry/borrow')


if __name__ == '__main__':
    main()
