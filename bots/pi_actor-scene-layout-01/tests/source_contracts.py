"""Narrow structural integration checks; dynamic controller behavior lives in recovery_scenarios.cpp."""
from pathlib import Path
import subprocess

bot = Path(__file__).resolve().parents[1]
root = bot.parents[1]
base = '2f0f534e8311ee597e516b11c2afca1bbf608060'
# Every inherited gameplay source except the two explicit dispatch/ownership files stays byte-identical.
for path in sorted((bot/'src').glob('*')):
    if path.name in {'bot.cpp', 'bot.h'} or path.name.startswith('recovery'):
        continue
    original = subprocess.check_output(['git', 'show', f'{base}:bots/leader_party_tuned/src/{path.name}'], cwd=root)
    actual = path.read_bytes()
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

# This experiment freezes every parent production file except the SDK conversion adapter.
parent = '21f464db747069b7dc360710e5ddfc1bf2a49bc7'
for path in sorted((bot/'src').glob('*')):
    if path.name in {'recovery_sdk.cpp', 'recovery_tiles.h'}:
        continue
    original = subprocess.check_output(['git', 'show', f'{parent}:bots/pi_actor-turn-core-01/src/{path.name}'], cwd=root)
    assert path.read_bytes() == original, path.name
sdk = (bot/'src/recovery_sdk.cpp').read_text()
assert sdk.count('.positions()') == 1
assert sdk.count('scalar(') == 7  # one boundary, all six mask consumers
assert sdk.count('.export_linear_buffer()') == 1
assert 'terrain->home=field.export_linear_buffer();' in sdk
assert 'int(s.visible.size())!=cells||int(s.occupied.size())!=cells' in sdk
assert sdk.index('cache.terrain=std::move(terrain);') > sdk.index('terrain->home.size()!=')
print('PASS: exact parent source preservation and all six coordinate consumers; scalar admission guards retained')
