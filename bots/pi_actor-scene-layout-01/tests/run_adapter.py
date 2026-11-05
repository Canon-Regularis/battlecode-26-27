#!/usr/bin/env python3
"""Real public SDK + actual adapter, with strict host mocks; no game execution."""
from pathlib import Path
import os
import re
import shlex
import subprocess
import tempfile
HERE = Path(__file__).resolve().parent
BOT = HERE.parent
ROOT = BOT.parents[1]
with tempfile.TemporaryDirectory(prefix='asl01-adapter-') as directory:
    out = Path(directory)
    fixture = (HERE/'adapter_scene.cpp').read_text()
    # Supply fail-fast definitions for unused host calls required by SDK vtables.
    # Exercised calls must have explicit mocks in the fixture; no silent defaults.
    declarations = (ROOT/'sdk/cpp/imports.h').read_text()
    signatures = re.findall(r'(std::int32_t|std::int64_t|void|int)\s+(sdk_\w+)\s*\(([^;{}]*)\)\s*;', declarations)
    stubs = ['namespace cambc::detail { extern "C" {']
    for result, name, args in signatures:
        if re.search(r'\b'+name+r'\s*\(', fixture):
            continue
        stubs.append(f'{result} {name}({args}) {{ throw std::runtime_error("Unmocked host call: {name}"); }}')
    stubs.append('}}')
    (out/'adapter_unused_imports.inc').write_text('\n'.join(stubs))
    command = [os.environ.get('CXX', 'g++'), '-std=c++20', '-O2', '-fpermissive', '-w',
               *shlex.split(os.environ.get('ADAPTER_CXXFLAGS', '')), '-I', str(ROOT/'sdk/cpp'), '-I', str(out), str(HERE/'adapter_scene.cpp'),
               str(BOT/'src/recovery.cpp'), '-o', str(out/'adapter')]
    subprocess.run(command, check=True)
    subprocess.run([str(out/'adapter')], check=True)
