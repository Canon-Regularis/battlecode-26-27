#!/usr/bin/env python3
"""Build actual candidate combat.cpp and the complete extracted camp_action body."""
from pathlib import Path
import hashlib
import subprocess

bot = Path(__file__).resolve().parents[1]
repo = bot.parents[1]
build = bot / 'tests' / '.kill-reset-build'
build.mkdir(exist_ok=True)
source = (bot / 'src/bot.cpp').read_text()
start = source.index('void Bot::camp_action(')
end = source.index('\nvoid Bot::play_turn()', start)
body = source[start:end]
original = subprocess.check_output(['git', 'show',
    '2f0f534e8311ee597e516b11c2afca1bbf608060:bots/leader_party_tuned/src/bot.cpp'], cwd=repo).decode()
assert body == original[original.index('void Bot::camp_action('):original.index('\nvoid Bot::play_turn()')], 'caller changed'
(build / 'camp_action.inc').write_text(body + '\n')
print('complete camp_action SHA256:', hashlib.sha256(body.encode()).hexdigest(), flush=True)
flags = ['g++', '-std=c++20', '-O2', '-fpermissive', '-Wall', '-Wextra',
         '-Wno-misleading-indentation', '-include', 'cmath', '-ffunction-sections', '-fdata-sections',
         '-I', str(repo / 'sdk/cpp'), '-I', str(bot / 'src')]
cmd = flags + [str(bot / 'tests/kill_reset_native.cpp'), '-Wl,--gc-sections', '-o', str(build / 'kill_reset_native')]
print(' '.join(cmd), flush=True)
subprocess.run(cmd, check=True)
subprocess.run([str(build / 'kill_reset_native')], check=True)
# All actual production translation units against the real, unchanged SDK.
for source in sorted((bot / 'src').glob('*.cpp')):
    subprocess.run(flags + ['-c', str(source), '-o', str(build / (source.stem + '.o'))], check=True)
print('all production translation units: SDK object compilation passed', flush=True)
for path in [bot / 'src/combat.cpp', bot / 'src/bot.cpp', bot / 'tests/kill_reset_native.cpp', repo / 'sdk/cpp/cambc.h', repo / 'sdk/cpp/imports.h']:
    print(hashlib.sha256(path.read_bytes()).hexdigest(), path.relative_to(repo), flush=True)
