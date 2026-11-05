"""Focused Pi checks. Extract actual policy bodies; mock SDK/field results only.
All generated files and executables stay in a temporary directory.
"""
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / 'src'
source = (SRC / 'objectives.cpp').read_text()
start = source.index('int choose_camp(')
end = source.index('\nint choose_altar(', start)
sort_line = next(line for line in source.splitlines() if 'std::sort(camps.begin()' in line)
metadata_line = '    dominant_gem_camp=find_dominant_gem_camp(camps);'
assert sort_line + '\n' + metadata_line in source
assert source.count(metadata_line) == 1
with tempfile.TemporaryDirectory(prefix='dg01-') as temporary:
    folder = Path(temporary)
    (folder / 'choose-camp-under-test.h').write_text(source[start:end])
    (folder / 'canonical-metadata-under-test.h').write_text(sort_line + '\n' + metadata_line + '\n')
    for name, inputs in [
        ('dominant', [HERE / 'dominant_gems.cpp']),
        ('decisions', [HERE / 'decisions.cpp', SRC / 'state_machine.cpp']),
    ]:
        executable = folder / name
        subprocess.run(['g++', '-std=c++20', '-O2', '-Wall', '-Wextra', '-Werror',
                        '-I', str(SRC), '-I', str(folder), *map(str, inputs),
                        '-o', str(executable)], check=True)
        subprocess.run([str(executable)], check=True)
