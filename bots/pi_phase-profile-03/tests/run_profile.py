#!/usr/bin/env python3
"""Focused native checks; all outputs use a temporary directory."""
from pathlib import Path
import json
import re
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[3]
BOT = Path(__file__).resolve().parents[1]
def run(*args):
    subprocess.run([str(a) for a in args], cwd=ROOT, check=True)
with tempfile.TemporaryDirectory(prefix='ppfx-') as temp:
    for enabled in (0, 1):
        out = Path(temp) / f'profile-{enabled}'
        run('g++', '-std=c++20', '-O2', '-Wall', '-Wextra', '-Werror',
            f'-DPPFX_ENABLED={enabled}', '-I', BOT/'src', BOT/'tests/phase_profile.cpp', '-o', out)
        run(out)
        run('g++', '-std=c++20', '-fpermissive', '-w', '-include', 'cmath',
            '-fsyntax-only', f'-DPPFX_ENABLED={enabled}', '-I', ROOT/'sdk/cpp',
            *sorted((BOT/'src').glob('*.cpp')))
    out = Path(temp)/'mask'
    run('g++', '-std=c++20', '-O2', '-DPPFX_ENABLED=1', '-DPPFX_MASK_TEST',
        '-DPPFX_PHASE_MASK=1', '-I', BOT/'src', BOT/'tests/phase_profile.cpp', '-o', out)
    run(out)
    for source in sorted((BOT/'src').glob('*.cpp')):
        args = ['g++', '-std=c++20', '-E', '-P', '-I', str(ROOT/'sdk/cpp')]
        original = ROOT/'bots/leader_party_tuned/src'/source.name
        a = subprocess.check_output(args+[str(original)], cwd=ROOT)
        b = subprocess.check_output(args+[str(source)], cwd=ROOT)
        assert a.split() == b.split(), source.name
    out = Path(temp)/'output'
    run('g++', '-std=c++20', '-O2', '-Wall', '-Wextra', '-Werror',
        '-DPPFX_ENABLED=1', '-I', BOT/'tests/profile_sdk', '-I', BOT/'src',
        BOT/'tests/profile_output.cpp', '-o', out)
    lines = subprocess.check_output([str(out)], cwd=ROOT, text=True).splitlines()
    expected = [[0, 1, 0, 2, 1, 1, 100000, 100000, 0],
                [1, 1, 0, 2, 1, 101, 100000, 90000, 9],
                [2, 1, 0, 2, 1, 101, 100000, 90000, 9]]
    for phase in range(11):
        active = int(phase == 2)
        expected.append([3, phase, active, 0, active, 0, 0, 0, 0] + [0]*18)
    expected.append([4, 1, 0, 0, 0, 0])
    for index, actor in enumerate((17, 4294967295)):
        marker = index*len(expected)
        assert lines.pop(marker) == f'WINDOW_END {actor}', lines
    assert len(lines) == 2*len(expected), lines
    # Independent VMs reuse scope 1; every record must carry its own actor.
    for line, (actor, payload) in zip(lines, [(actor, payload)
            for actor in (17, 4294967295) for payload in expected]):
        match = re.fullmatch(r'PPFX (\d+) (\[.*\])', line)
        assert match and int(match[1]) == actor, line
        assert json.loads(match[2]) == payload, line
    out = Path(temp)/'decisions'
    run('g++', '-std=c++20', '-O2', '-I', BOT/'src', BOT/'tests/decisions.cpp',
        BOT/'src/state_machine.cpp', '-o', out)
    run(out)
print('PASS profiler ON/OFF, SDK syntax (native workarounds), OFF token identity, actor output contract, decisions')
