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
combat = (SRC / 'combat.cpp').read_text()
fight_start = combat.index('bool fight(')
fight_end = combat.index('\nvoid optional_ward(', fight_start)
fight = combat[fight_start:fight_end]
prior_loop = '    if(!target&&!travel&&task>=0)for(const auto& c:w.camps[task].group.camps())if(c.is_visible()&&c.is_alive()&&reachable(c,false)&&c.health()<hp){selected_camp=c;hp=c.health();}'
pruned_loop = '''    if(!target&&!travel&&task>=0)for(const auto& c:w.camps[task].group.camps())if(c.is_visible()&&c.is_alive()) {
        const float candidate_hp=c.health();
        if(candidate_hp<hp&&reachable(c,false)){selected_camp=c;hp=candidate_hp;}
    }'''
assert fight.count(pruned_loop) == 1
reference = fight.replace(pruned_loop, prior_loop).replace('bool fight(', 'bool fight_reference(', 1)
with tempfile.TemporaryDirectory(prefix='dp01-') as temporary:
    folder = Path(temporary)
    (folder / 'choose-camp-under-test.h').write_text(source[start:end])
    (folder / 'canonical-metadata-under-test.h').write_text(sort_line + '\n' + metadata_line + '\n')
    (folder / 'fight-under-test.h').write_text(fight)
    (folder / 'fight-reference.h').write_text(reference)
    for name, inputs in [
        ('dominant', [HERE / 'dominant_gems.cpp']),
        ('decisions', [HERE / 'decisions.cpp', SRC / 'state_machine.cpp']),
        ('combat', [HERE / 'combat_selection.cpp']),
    ]:
        executable = folder / name
        subprocess.run(['g++', '-std=c++20', '-O2', '-Wall', '-Wextra', '-Werror',
                        '-I', str(SRC), '-I', str(folder), *map(str, inputs),
                        '-o', str(executable)], check=True)
        subprocess.run([str(executable)], check=True)
