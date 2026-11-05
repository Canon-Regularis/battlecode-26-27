"""Mechanical removable-hook normalization, NOT a WASM identity test."""
from pathlib import Path
import re
import subprocess
BOT = Path(__file__).resolve().parents[1]
ROOT = BOT.parents[1]
PARENT = 'd378591a722eed9ebb6b1c407e748c9ecad9274a'

def strip(text):
    text = text.replace('#include "phase_profile.h"\n', '')
    pattern = re.compile(r'\bPPFX(?:_[A-Z0-9_]+)?\(')
    while (match := pattern.search(text)):
        pos = match.end(); start = pos; depth = 1
        while depth:
            depth += (text[pos] == '(') - (text[pos] == ')')
            pos += 1
        replacement = text[start:pos-1] if match[0].startswith('PPFX_STATUS_') else ''
        text = text[:match.start()] + replacement + text[pos:]
    return text

def tokens(text):
    # Preserve literal contents, discard only comments and inter-token whitespace.
    pattern = r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//[^\n]*|/\*[\s\S]*?\*/|\w+|[^\s]'
    return [t for t in re.findall(pattern, text) if not t.startswith(('//', '/*'))]

def check():
    for path in sorted((BOT/'src').glob('*')):
        if path.name in {'phase_profile.h', 'phase_profile.cpp'}:
            continue
        parent = subprocess.check_output(['git','show',f'{PARENT}:bots/pi_actor-scene-epoch-01/src/{path.name}'],cwd=ROOT).decode()
        assert tokens(strip(path.read_text())) == tokens(parent), path.name
    for name in ('recovery_scenarios.cpp','decisions.cpp','strategy_contracts.cpp','adapter_scene.cpp','adapter_epochs.h'):
        parent = subprocess.check_output(['git','show',f'{PARENT}:bots/pi_actor-scene-epoch-01/tests/{name}'],cwd=ROOT)
        assert (BOT/'tests'/name).read_bytes() == parent, name
    print('PASS: normalized OFF tokens against exact ase01 parent; gameplay/revision fixtures byte-preserved (not WASM identity)')
if __name__ == '__main__':
    check()
