#!/usr/bin/env python3
"""Pi checks; temporary artifacts only. Does not build a release or run games."""
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
BOT = HERE.parent
ROOT = BOT.parents[1]


def run(args):
    subprocess.run([str(a) for a in args], cwd=ROOT, check=True)


def extract(text, signature):
    start = text.index(signature)
    i = text.index('{', start) + 1
    depth = 1
    while depth:
        depth += (text[i] == '{') - (text[i] == '}')
        i += 1
    return text[start:i]


run(['python3', HERE / 'run_retreat.py'])
# The stock SDK uses a team type and team() member name GCC diagnoses.
# Existing objectives/route_plan rely on a transitive cmath include. Supply it
# only to this native check; leave production/SDK files unchanged.
run(['g++', '-std=c++20', '-Wno-changes-meaning', '-include', 'cmath',
     '-fsyntax-only', '-I', ROOT / 'sdk/cpp', *sorted((BOT / 'src').glob('*.cpp'))])
print('PASS: all 11 production translation units, real SDK syntax (native accommodations documented)', flush=True)
with tempfile.TemporaryDirectory(prefix='rrr01-inherited-') as directory:
    tmp = Path(directory)
    flags = ['g++', '-std=c++20', '-O2', '-Wall', '-Wextra', '-I', BOT / 'src']
    run([*flags, HERE / 'decisions.cpp', BOT / 'src/state_machine.cpp', '-o', tmp / 'decisions'])
    run([tmp / 'decisions'])
    geometry = (BOT / 'src/objectives.cpp').read_text()
    header = ('namespace lp { struct vec2 {int x,y;}; '
              'struct World { int width,height,columns,rows; '
              'int chunk(vec2) const; vec2 center(int) const; };\n')
    header += extract(geometry, 'int World::chunk(') + '\n'
    header += extract(geometry, 'vec2 World::center(') + '\n}\n'
    (tmp / 'geometry-under-test.h').write_text(header)
    run([*flags, '-I', tmp, HERE / 'strategy_contracts.cpp', BOT / 'src/state_machine.cpp', '-o', tmp / 'contracts'])
    run([tmp / 'contracts'])
    # Execute the inherited differential test with only output paths/compiler
    # adapted in memory; the original Windows script remains byte-identical.
    source = (HERE / 'verify_translation.py').read_text()
    source = source.replace("ROOT/'.cambc/subhan-translation-reference'", repr(str(tmp / 'translation')))
    source = source.replace("folder=" + repr(str(tmp / 'translation')), "folder=Path(" + repr(str(tmp / 'translation')) + ")")
    source = source.replace("ROOT/'.cambc/subhan-planner-test.exe'", repr(str(tmp / 'planner')))
    source = source.replace('C:/msys64/mingw64/bin/g++.exe', 'g++')
    exec(compile(source, str(HERE / 'verify_translation.py'), 'exec'), {'__file__': str(HERE / 'verify_translation.py'), '__name__': '__main__'})
