"""Native production-interface checks; all generated outputs live under /tmp."""
from pathlib import Path
import re
import subprocess
import tempfile

here = Path(__file__).resolve().parent
root = here.parents[2]
src = here.parent / 'src'

def run(*args):
    subprocess.run(list(map(str, args)), check=True)

with tempfile.TemporaryDirectory(prefix='bge01-') as directory:
    tmp = Path(directory)
    # Any unimplemented SDK import aborts if executed: no silent fake success.
    fixture = (here / 'bank_egress.cpp').read_text()
    implemented = set(re.findall(r'\b(sdk_\w+)\s*\(', fixture))
    imports = (root / 'sdk/cpp/imports.h').read_text()
    stubs = ['namespace cambc::detail { extern "C" {']
    for ret, name, args in re.findall(r'BC_IMPORT\("[^"]+"\)\s+([\w:]+)\s+(sdk_\w+)\(([^;]*)\);', imports):
        if name not in implemented:
            stubs.append(f'{ret} {name}({args}) {{ std::fprintf(stderr, "Unexpected import: {name}\\n"); std::abort(); }}')
    stubs.append('}}')
    (tmp / 'unused-host-imports.h').write_text('\n'.join(stubs))
    flags = ['g++', '-std=c++20', '-O1', '-g', '-Wno-changes-meaning', '-I', root / 'sdk/cpp', '-I', tmp]
    run(*flags, here / 'bank_egress.cpp', '-o', tmp / 'bank-egress')
    run(tmp / 'bank-egress')
    run('g++', '-std=c++20', '-O2', '-Wall', '-Wextra', '-I', src,
        here / 'decisions.cpp', src / 'state_machine.cpp', '-o', tmp / 'decisions')
    run(tmp / 'decisions')
    # The inherited objectives/route_plan files use ceil without <cmath>.
    # Supply it for this GCC-only check without changing unrelated production code.
    run(*flags, '-include', 'cmath', '-fsyntax-only', *sorted(src.glob('*.cpp')))
    print('PASS all production translation units against checkout SDK (GCC naming diagnostic suppressed)')
