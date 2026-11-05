#!/usr/bin/env python3
"""Pi/native checks. All generated binaries are temporary; no engine/tournament invocation."""
from pathlib import Path
import os
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
BOT = HERE.parent
ROOT = BOT.parents[1]
CXX = os.environ.get('CXX', 'g++')

def run(args):
    subprocess.run([str(a) for a in args], check=True)

with tempfile.TemporaryDirectory(prefix='actor-scene-layout-01-') as out:
    out = Path(out)
    for name, sources in [
        ('recovery', [HERE/'recovery_scenarios.cpp', BOT/'src/recovery.cpp']),
        ('decisions', [HERE/'decisions.cpp', BOT/'src/state_machine.cpp']),
    ]:
        run([CXX, '-std=c++20', '-O2', '-Wall', '-Wextra', '-Werror', '-I', BOT/'src', *sources, '-o', out/name])
        run([out/name])
    # SDK 4.0.0's team team() declarations require GCC -fpermissive on this Pi.
    # Do not change the shared SDK to work around it; check every inherited/new source.
    run([CXX, '-std=c++20', '-fpermissive', '-w', '-fsyntax-only', '-I', ROOT/'sdk/cpp', *sorted((BOT/'src').glob('*.cpp'))])
    run(['python3', HERE/'source_contracts.py'])
    run(['python3', HERE/'run_adapter.py'])
    run(['python3', HERE/'run_profile.py'])
print('PASS: focused recovery, inherited decisions, all production source syntax, integration contracts, actual adapter fixture')
