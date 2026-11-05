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
parser.add_argument('--profile', action='store_true', help='Run real adapter paths with ON profiling and assert collected labels')
options = parser.parse_args()
assert not (options.profile and options.parent_control)
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
    if options.profile:
        fixture = fixture.replace('#include "../src/recovery_sdk.cpp"', '#include "'+str(BOT/'src/recovery_sdk.cpp')+'"')
        fixture = fixture.replace('int main(){', 'int fixture_main(){')
        end = fixture.rfind('}')
        fixture = fixture[:end]+'return 0;\n'+fixture[end:]
        fixture += r"""
int main(){fixture_main();using namespace lp::ppfx;
    assert(store.active==0&&!store.done);
    for(int i=0;i<8;++i)assert(store.scopes[i].entries>0&&store.scopes[i].entries==store.scopes[i].completed);
    assert(store.scopes[7].exit[sdk]>=2);
    assert(store.scopes[2].exit[halt]>0&&store.scopes[2].halt_status[int(Status::incomplete)]>0);
    assert(store.context[queries].n==store.scopes[2].entries);
    assert(store.context[plan_raw].n>0&&store.context[moves].sum>0&&store.context[recalls].sum>0);
    assert(store.context[member_cold].n>0&&store.context[member_warm].n>0);
    assert(store.context[capture_status].n>0&&store.context[halt_status].n>0);
    // A committed action followed by an escaping capture error retains work
    // counters without inventing a normal returned recovery status.
    struct Interrupted final:Backend {
        LiveBackend& live;int captures=0;
        explicit Interrupted(LiveBackend& b):live(b){}
        Epoch epoch()override{return live.epoch();}bool current(Epoch e)override{return live.current(e);}
        Status prepare(Epoch e)override{return live.prepare(e);}
        Status capture(Scene& scene)override{if(++captures==2)throw cambc::error(error_code::api_not_found,"scripted after move");return live.capture(scene);}
        bool issue(const Scene& scene,Action a)override{return live.issue(scene,a);}
        bool defend(const Scene& scene)override{return live.defend(scene);}
    };
    {EpochFixture f;LiveBackend live(f.world,f.memory,f.budget,f.cache);Interrupted backend(live);
     auto before=store.context[moves].sum,results=store.context[result].n;
     Scope scope(0);RecoveryAdmission admission(scope.admitted);
     try{execute(Intent::health,f.memory,backend);assert(false);}catch(const cambc::error&){scope.close(sdk);}
     assert(store.context[moves].sum==before+1&&store.context[result].n==results);}
    std::puts("PASS: ON production hooks, Halt/SDK exits, returned statuses, query/cache/plan/recovery context");}
"""
        fixture_path = out/'profile_fixture.cpp'
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
               *shlex.split(os.environ.get('ADAPTER_CXXFLAGS', '')),
               *(['-DPPFX_ENABLED=1', '-DPPFX_PHASE_MASK=0x1ffu'] if options.profile else []), '-I', str(ROOT/'sdk/cpp'), '-I', str(out), '-I', str(HERE), '-I', str(BOT/'src'), str(fixture_path),
               str(BOT/'src/recovery.cpp'), str(BOT/'src/phase_profile.cpp'), '-o', str(out/'adapter')]
    subprocess.run(command, check=True)
    if options.parent_control:
        result = subprocess.run([str(out/'adapter')], cwd=out)
        assert result.returncode == 23, result.returncode
    else:
        subprocess.run([str(out/'adapter')], check=True)
