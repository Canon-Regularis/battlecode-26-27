#!/usr/bin/env python3
"""Real public SDK + actual adapter, with strict host mocks; no game execution."""
from pathlib import Path
import argparse
import os
import re
import shlex
import subprocess
import tempfile
HERE = Path(__file__).resolve().parent
BOT = HERE.parent
ROOT = BOT.parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--parent-control', action='store_true',
                    help='Expect exact asl01 parent to reject the first refreshed motion capture')
options = parser.parse_args()
with tempfile.TemporaryDirectory(prefix='ase01-adapter-') as directory:
    out = Path(directory)
    fixture = (HERE/'adapter_scene.cpp').read_text()
    fixture_path = HERE/'adapter_scene.cpp'
    if options.parent_control:
        parent = '914cf67173be7c5231ccaa2878e4292d236b71e4'
        (out/'parent_sdk.cpp').write_bytes(subprocess.check_output([
            'git', 'show', f'{parent}:bots/pi_actor-scene-layout-01/src/recovery_sdk.cpp'], cwd=ROOT))
        fixture = fixture.replace('#include "../src/recovery_sdk.cpp"', '#include "parent_sdk.cpp"')
        fixture = fixture.replace('int main(){', 'int inherited_main(){')
        fixture += """
int main(){try{epoch_regressions();assert(false);}catch(Halt h){
    assert(h.status==Status::stale&&fake::log==std::vector<Kind>({Kind::step}));
    std::cout<<"EXPECTED: exact parent rejects fresh capture after one committed step"<<std::endl;
    return 23;}}
"""
        fixture_path = out/'fixture.cpp'
        fixture_path.write_text(fixture)
    # Mechanically compile the production cache state and exact epoch functions.
    observations = (BOT/'src/observations.cpp').read_text()
    lines = [re.search(pattern, observations).group(0) for pattern in (
        r'namespace \{Snapshot cached;bool valid_cache=false;unsigned revision=1;\}',
        r'void invalidate_observations\(\)\{[^\n]+\}',
        r'unsigned observation_version\(\)\{[^\n]+\}',
    )]
    (out/'observation_epoch.inc').write_text('namespace lp {\n'+'\n'.join(lines)+'\n}\n')

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
               *shlex.split(os.environ.get('ADAPTER_CXXFLAGS', '')), '-I', str(ROOT/'sdk/cpp'), '-I', str(out), '-I', str(HERE), '-I', str(BOT/'src'), str(fixture_path),
               str(BOT/'src/recovery.cpp'), '-o', str(out/'adapter')]
    subprocess.run(command, check=True)
    if options.parent_control:
        result = subprocess.run([str(out/'adapter')], cwd=out)
        assert result.returncode == 23, result.returncode
    else:
        subprocess.run([str(out/'adapter')], check=True)
