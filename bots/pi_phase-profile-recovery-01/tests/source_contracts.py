"""Narrow structural integration checks; dynamic controller behavior lives in recovery_scenarios.cpp."""
from pathlib import Path
import subprocess
from profile_preservation import strip, check

bot = Path(__file__).resolve().parents[1]
root = bot.parents[1]
base = '2f0f534e8311ee597e516b11c2afca1bbf608060'
# Every inherited gameplay source except the two explicit dispatch/ownership files stays byte-identical.
for path in sorted((bot/'src').glob('*')):
    if path.name in {'bot.cpp', 'bot.h'} or path.name.startswith(('recovery', 'phase_profile')):
        continue
    original = subprocess.check_output(['git', 'show', f'{base}:bots/leader_party_tuned/src/{path.name}'], cwd=root)
    actual = strip(path.read_text()).encode()
    if path.name in {"objectives.cpp", "route_plan.cpp"}:
        actual = actual.removeprefix(b"#include <cmath>\n")
    assert actual == original, path.name
code = (bot/'src/bot.cpp').read_text()
start = code.index('if(recovery::routes(memory.state,memory.recovering))')
end = code.index('switch(memory.state)', start)
adapter = code[start:end]
assert 'Facts.recovery' not in adapter and 'f.recovery' not in adapter
assert 'cancel_recall' not in adapter
assert 'outcome.stop_dispatch()' in adapter
assert adapter.rfind('return;') > adapter.index('recover(')
assert 'stats.banks' not in adapter and 'stats.captures' not in adapter and 'progressed' not in adapter
assert 'case State::recall:if(!self().is_recalling())self().recall();break;' in code
assert 'retreat(' not in code
recovery = (bot/'src/recovery.cpp').read_text() + (bot/'src/recovery_sdk.cpp').read_text()
assert 'move_to(' not in recovery and 'retreat(' not in recovery
assert 'compute_to(' not in recovery and 'field.compute(blocked,spawn,visited)' in recovery
assert 'is_set(' not in recovery and 'valid_tiles()' not in (bot/'src/recovery.cpp').read_text()
assert 'camp_group()' not in recovery.replace('// Public cached World groups own membership. This makes no camp_group() calls.', '')
assert 'optional_ward' not in recovery and 'fight(' not in recovery
assert 'std::cout' not in recovery and 'std::cerr' not in recovery
print('PASS: source preservation, exact routing, field ownership, no recovery legacy fallback/ward/live endpoint query')

# The scalar-only byte gate belonged to ase01. This profiling candidate explicitly
# replaces it with removable-hook token preservation against ase01 itself.
# Keep the earlier scalar repair assertion on the exact profiling parent.
parent = 'd378591a722eed9ebb6b1c407e748c9ecad9274a'
previous = subprocess.check_output(['git','show','914cf67173be7c5231ccaa2878e4292d236b71e4:bots/pi_actor-scene-layout-01/src/recovery_sdk.cpp'],cwd=root)
expected = previous.replace(
    b'        scalar_cells(width,height); // Reject unsupported dimensions before any export.',
    b'        check();const Epoch conversion=epoch();\n        scalar_cells(width,height); // Reject unsupported dimensions before any export.'
).replace(b'check();if(!current(turn))throw Halt{Status::stale};',
          b'check();if(!current(conversion))throw Halt{Status::stale};')
assert expected != previous
assert subprocess.check_output(['git','show',f'{parent}:bots/pi_actor-scene-epoch-01/src/recovery_sdk.cpp'],cwd=root) == expected
check()
sdk = (bot/'src/recovery_sdk.cpp').read_text()
assert sdk.count('.positions()') == 1
assert sdk.count('scalar(') == 7  # one boundary, all six mask consumers
assert sdk.count('.export_linear_buffer()') == 1
assert 'terrain->home=field.export_linear_buffer();' in sdk
assert 'int(s.visible.size())!=cells||int(s.occupied.size())!=cells' in sdk
assert sdk.index('cache.terrain=std::move(terrain);') > sdk.index('terrain->home.size()!=')
print('PASS: inherited scalar repair and all six coordinate consumers; scalar admission guards retained')
