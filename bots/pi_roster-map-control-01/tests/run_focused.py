"""Pi/native checks; all generated files stay in a temporary directory.

Production source bodies are used verbatim with deterministic host substitutes.
SDK enums are extracted, never renumbered. Real SDK syntax is checked separately.
"""
from pathlib import Path
import os
import re
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
BOT = HERE.parent
ROOT = BOT.parents[1]
CXX = os.environ.get('CXX', 'g++')

def run(args, **kwargs):
    subprocess.run([str(x) for x in args], check=True, **kwargs)

with tempfile.TemporaryDirectory(prefix='rm01-') as temp:
    out = Path(temp)
    sdk = (ROOT/'sdk/cpp/cambc.h').read_text()
    enums = '\n'.join(re.search(r'enum class '+name+r'\b[^}]+};', sdk).group()
                      for name in ['champion_draft', 'champion_type'])
    (out/'cambc.h').write_text('#pragma once\n#include <cstdint>\nnamespace cambc {\n'+enums+'\n}\n')
    common = [CXX, '-std=c++20', '-O2', '-Wall', '-Wextra', '-I', BOT/'src']
    # Static mapping assertions are compiled against both actual SDK and fixture enums.
    run(common+['-fpermissive', '-fsyntax-only', '-I', ROOT/'sdk/cpp', HERE/'roster_contracts.cpp'])
    pieces = ['#include "producer_fixture.h"', '#include "roster.h"',
              (HERE/'roster_contracts.cpp').read_text()]
    for name in ['draft.cpp', 'route_plan.cpp']:
        pieces.append('\n'.join(line for line in (BOT/'src'/name).read_text().splitlines()
                                if not line.startswith('#include')))
    pieces.append((HERE/'producer_checks.cpp').read_text())
    (out/'producer.cpp').write_text('\n'.join(pieces))
    run(common+['-I', out, '-I', HERE, out/'producer.cpp', '-o', out/'producer'])
    candidate_output = subprocess.check_output([str(out/'producer')])
    print(candidate_output.decode(), end='')
    # Run the identical assertions against the exact original producer sources.
    original = pieces[:3]
    for name in ['draft.cpp', 'route_plan.cpp']:
        body = subprocess.check_output(['git', 'show',
            '2f0f534e8311ee597e516b11c2afca1bbf608060:bots/leader_party_tuned/src/'+name], cwd=ROOT).decode()
        original.append('\n'.join(line for line in body.splitlines() if not line.startswith('#include')))
    original.append(pieces[-1])
    (out/'original.cpp').write_text('\n'.join(original))
    run(common+['-I', out, '-I', HERE, out/'original.cpp', '-o', out/'original'])
    assert subprocess.check_output([str(out/'original')]) == candidate_output
    print('PASS: exact base producers pass identical fixtures and output comparison')
    run(common+[HERE/'decisions.cpp', BOT/'src/state_machine.cpp', '-o', out/'decisions'])
    run([out/'decisions'])
    geometry = (BOT/'src/objectives.cpp').read_text()
    chunk = geometry[geometry.index('int World::chunk('):geometry.index('void World::refresh(')]
    (out/'geometry-under-test.h').write_text(
        '#pragma once\nnamespace lp {struct vec2 {int x,y;};'
        'struct World {int width,height,columns,rows;int chunk(vec2) const;vec2 center(int) const;};'
        +chunk+'}\n')
    run(common+['-I', out, HERE/'strategy_contracts.cpp', BOT/'src/state_machine.cpp', '-o', out/'strategy'])
    run([out/'strategy'])
    # Existing differential test uses Windows compiler/output paths. Adapt only
    # those paths in a temporary copy; all 240 cases and assertions are unchanged.
    source = (HERE/'verify_translation.py').read_text()
    source = source.replace("ROOT=Path(__file__).resolve().parents[3]", 'ROOT=Path('+repr(str(ROOT))+')')
    source = source.replace('HERE=Path(__file__).resolve().parent', 'HERE=Path('+repr(str(HERE))+')')
    source = source.replace("folder=ROOT/'.cambc/subhan-translation-reference'", 'folder=Path('+repr(str(out/'reference'))+')')
    source = source.replace("executable=ROOT/'.cambc/subhan-planner-test.exe'", 'executable=Path('+repr(str(out/'planner'))+')')
    source = source.replace('C:/msys64/mingw64/bin/g++.exe', CXX)
    exec(compile(source, str(HERE/'verify_translation.py'), 'exec'), {'__file__': str(HERE/'verify_translation.py')})
    # GCC requires permissive mode for pre-existing SDK team() declarations;
    # cmath is normally supplied by the bot build environment.
    run(common+['-fpermissive', '-include', 'cmath', '-fsyntax-only', '-I', ROOT/'sdk/cpp']+
        sorted((BOT/'src').glob('*.cpp')))
print('PASS: real-SDK syntax, roster contracts, production fixtures, state and planner checks')
