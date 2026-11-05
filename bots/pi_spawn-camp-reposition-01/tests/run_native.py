"""Focused Pi checks; writes build artifacts only to a temporary directory."""
from pathlib import Path
import re
import subprocess
import tempfile

BOT = Path(__file__).resolve().parents[1]
ROOT = BOT.parents[1]
SDK = ROOT / 'sdk/cpp'
HOST = BOT / 'tests/spawn_camp_reposition.cpp'

def run(args):
    subprocess.run([str(a) for a in args], check=True)

with tempfile.TemporaryDirectory(prefix='scp01-') as temp:
    temp = Path(temp)
    # Unused host APIs fail loudly, including any accidentally introduced action.
    declared = re.findall(r'BC_IMPORT\("[^" ]+"\)\s+([\w:]+)\s+(sdk_\w+)\((.*?)\);',
                          (SDK / 'imports.h').read_text(), re.S)
    implemented = set(re.findall(r'\b(sdk_\w+)\(', HOST.read_text()))
    stubs = temp / 'unused_host.cpp'
    stubs.write_text('#include <cambc.h>\n#include <cstdlib>\nnamespace cambc::detail { extern "C" {\n' +
                     '\n'.join(f'{ret} {name}({args}) {{ std::fprintf(stderr,"Unexpected host API: {name}\\n"); std::abort(); }}'
                               for ret, name, args in declared if name not in implemented) + '\n}}\n')
    common = ['g++', '-std=c++20', '-O1', '-fpermissive', '-Wno-changes-meaning', '-I', SDK, '-I', BOT/'src']
    run(common + [HOST, stubs, *[BOT/'src'/f'{name}.cpp' for name in ['combat','observations','bot','state_machine']], '-o', temp/'spawn-test'])
    run([temp/'spawn-test'])
    run(['g++', '-std=c++20', '-O2', '-Wall', '-Wextra', '-I', BOT/'src', BOT/'tests/decisions.cpp', BOT/'src/state_machine.cpp', '-o', temp/'decisions'])
    run([temp/'decisions'])
    run(common + ['-include', 'cmath', '-fsyntax-only', *sorted((BOT/'src').glob('*.cpp'))])
    print('PASS: all production translation units parse against unchanged real SDK (GCC -fpermissive, forced cmath for inherited includes)')
