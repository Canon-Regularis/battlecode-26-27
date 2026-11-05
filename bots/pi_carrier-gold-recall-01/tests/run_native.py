#!/usr/bin/env python3
"""Focused Pi checks; uses real SDK, writes build products only to a temp directory."""
from pathlib import Path
import os
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
BOT = HERE.parent
ROOT = BOT.parent.parent
BASE = '2f0f534e8311ee597e516b11c2afca1bbf608060'
CXX = os.environ.get('CXX', 'g++')


def run(args):
    subprocess.run([str(a) for a in args], check=True)


def original(name):
    return subprocess.check_output(['git', 'show', f'{BASE}:bots/leader_party_tuned/src/{name}'], cwd=ROOT)


def body(text, signature):
    start = text.index(signature)
    opening = text.index('{', start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


# Audit the production scope against the frozen original, not another experiment.
names = subprocess.check_output(['git', 'ls-tree', '--name-only', f'{BASE}:bots/leader_party_tuned/src'], cwd=ROOT).decode().splitlines()
assert sorted(names) == sorted(p.name for p in (BOT / 'src').iterdir())
for name in names:
    expected = original(name)
    if name == 'bot.cpp':
        before = b'!s.spawn&&s.bag==0&&s.foes.empty()&&me.gold_count()>=Config::recall_gold'
        assert expected.count(before) == 1
        expected = expected.replace(before, b'!s.spawn&&s.foes.empty()&&me.gold_count()>=Config::recall_gold')
    assert (BOT / 'src' / name).read_bytes() == expected, name
print('PASS exact production source scope against frozen base', flush=True)

with tempfile.TemporaryDirectory(prefix='cgr01-') as tmp:
    out = Path(tmp)
    common = [CXX, '-std=c++20', '-O2', '-Wall', '-Wextra', '-Wno-misleading-indentation', '-I', BOT / 'src']
    run([*common, HERE / 'decisions.cpp', BOT / 'src/state_machine.cpp', '-o', out / 'decisions'])
    run([out / 'decisions'])

    # Keep the existing exhaustive geometry/protocol/state contracts meaningful:
    # geometry method bodies come from the actual candidate source, without SDK mocks.
    source = (BOT / 'src/objectives.cpp').read_text()
    geometry = ('#pragma once\nnamespace lp {\nstruct Point { int x,y; };\n'
                'struct World { int width,height,columns,rows; int chunk(Point) const; Point center(int) const; };\n')
    geometry += body(source, 'int World::chunk(').replace('vec2', 'Point') + '\n'
    geometry += body(source, 'vec2 World::center(').replace('vec2', 'Point') + '\n}\n'
    (out / 'geometry-under-test.h').write_text(geometry)
    run([*common, '-I', out, HERE / 'strategy_contracts.cpp', BOT / 'src/state_machine.cpp', '-o', out / 'contracts'])
    run([out / 'contracts'])

    # GCC diagnostic workaround for existing SDK team() declarations. No SDK edits.
    sdk = ['-Wno-changes-meaning', '-I', ROOT / 'sdk/cpp']
    recovery = [*common, *sdk, '-fno-access-control', '-ffunction-sections', '-fdata-sections',
                HERE / 'recovery.cpp', BOT / 'src/state_machine.cpp', '-Wl,--gc-sections']
    run([*recovery, BOT / 'src/bot.cpp', '-o', out / 'recovery'])
    run([out / 'recovery'])

    # Negative control: same tests must reject the original bag restriction.
    (out / 'bot.cpp').write_bytes(original('bot.cpp'))
    run([*recovery, out / 'bot.cpp', '-o', out / 'original'])
    result = subprocess.run([out / 'original'], capture_output=True, text=True)
    assert result.returncode == 1 and 'FAIL gold recovery admission matrix' in result.stderr, result
    print('PASS original source rejected at positive-bag admission (expected negative control)', flush=True)

    for source in sorted((BOT / 'src').glob('*.cpp')):
        run([*common, *sdk, '-include', 'cmath', '-fsyntax-only', source])
    print('PASS real-SDK syntax checks for every production translation unit', flush=True)
