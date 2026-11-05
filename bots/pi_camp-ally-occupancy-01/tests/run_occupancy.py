"""Compile real module and extract unmodified candidate integration bodies."""
from pathlib import Path
import subprocess
import tempfile
here = Path(__file__).resolve().parent
src = here.parent / 'src'
with tempfile.TemporaryDirectory(prefix='cao01-') as tmp:
    folder = Path(tmp)
    for source, start, end, output in [
        ('observations.cpp', 'occupancy::Attempt prepare_camp_occupancy(', '\nnamespace {Snapshot', 'prepare-under-test.h'),
        ('observations.cpp', 'const Snapshot& observe()', '\n}\n}', 'observe-under-test.h'),
        ('navigation.h', 'enum class RouteStatus', '\n}', 'navigation-types-under-test.h'),
        ('navigation.cpp', 'RouteStatus move_to(', '\nbool retreat(', 'move-under-test.h'),
        ('bot.cpp', 'void Bot::camp_action(', '\nvoid Bot::play_turn(', 'camp-action-under-test.h'),
    ]:
        text = (src / source).read_text()
        first = text.index(start)
        last = text.index(end, first)
        body = text[first:last]
        if output == 'observe-under-test.h':
            body += '\n}'
        (folder / output).write_text(body)
    for name in ['occupancy', 'occupancy_integration', 'occupancy_adapter']:
        binary = folder / name
        subprocess.run(['g++', '-std=c++20', '-O2', '-Wall', '-Wextra', '-Werror',
                        '-I', str(src), '-I', str(folder), str(here / (name + '.cpp')),
                        '-o', str(binary)], check=True)
        if name != 'occupancy_adapter':
            subprocess.run([str(binary)], check=True)
        else:
            result = subprocess.run([str(binary)], input='roster 1 2 1 2\nkey 1 0 20\nbatch 20 1 1 8 8 1 1 2 2 1 0 0\nbatch 21 2 1 8 8 1 0 0 1 2 1\nfeedback 1 21 2 1\nbatch 22 3 1 8 8 1 0 0 1 2 1\n', text=True, capture_output=True, check=True)
            assert result.stdout.splitlines()[0] == 'mask 1 0 0'
            assert result.stdout.splitlines()[1].startswith('mask 1 1 1 2 2 1 20 1 ')
            assert result.stdout.splitlines()[2] == 'mask 1 1 0'
            print('PASS native adapter streaming smoke check')
