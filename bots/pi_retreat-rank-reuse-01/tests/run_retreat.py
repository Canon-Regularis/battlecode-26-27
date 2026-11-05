#!/usr/bin/env python3
"""Extract real bodies, check the exact production delta, compile/run native fixture.
No checkout files outside this candidate are written. Generated files live in /tmp.
"""
from pathlib import Path
import hashlib
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
BOT = HERE.parent
ROOT = BOT.parents[1]
BASE = '2f0f534e8311ee597e516b11c2afca1bbf608060'


def extract(text, signature):
    start = text.index(signature)
    opening = text.index('{', start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


def parent(name):
    return subprocess.check_output(['git', 'show', f'{BASE}:bots/leader_party_tuned/src/{name}'], cwd=ROOT).decode()


nav = (BOT / 'src/navigation.cpp').read_text()
original = parent('navigation.cpp')
old_loop = 'for(auto p:s.blocked.reachable_tiles(s.pos,1).positions()) if(rank(p)<score){best=p;score=rank(p);}'
new_loop = 'for(auto p:s.blocked.reachable_tiles(s.pos,1).positions()) {const auto candidate_score=rank(p);if(candidate_score<score){best=p;score=candidate_score;}}'
old_move = 'if(best!=s.pos) {bool moved=move_checked(best);'
new_move = 'if(best!=s.pos) {if(!budget.current())return false;bool moved=move_checked(best);'
assert original.count(old_loop) == original.count(old_move) == 1
assert nav == original.replace(old_loop, new_loop).replace(old_move, new_move), 'production change exceeds contract'
# Enforce unchanged inherited production, including helpers and headers.
for path in (BOT / 'src').iterdir():
    assert path.read_bytes() == (nav if path.name == 'navigation.cpp' else parent(path.name)).encode(), path
obs = (BOT / 'src/observations.cpp').read_text()
move_helper = extract(obs, 'bool move_checked(')
incoming_helper = extract(obs, 'float incoming_at(')
cheb = extract((BOT / 'src/observations.h').read_text(), 'inline int cheb(')
budget = extract((BOT / 'src/navigation.h').read_text(), 'struct TurnBudget ') + ';'
with tempfile.TemporaryDirectory(prefix='rrr01-') as tmp:
    tmp = Path(tmp)
    generated = cheb + '\n' + budget + '\n'
    for label, source in [('parent', original), ('candidate', nav)]:
        body = extract(source, 'bool retreat(')
        print(f'{label} retreat SHA256 {hashlib.sha256(body.encode()).hexdigest()}', flush=True)
        generated += (f'namespace {label} {{\n{move_helper}\n'
                      f'namespace incoming_impl {{\n{incoming_helper}\n}}\n'
                      'float incoming_at(vec2 p,const std::vector<champion>& enemies) {'
                      '++incoming_calls;return incoming_impl::incoming_at(p,enemies); }\n'
                      f'{body}\n}}\n')
    (tmp / 'retreat-under-test.h').write_text(generated)
    subprocess.run(['g++', '-std=c++20', '-O2', '-Wall', '-Wextra', '-Werror', '-I', str(tmp), '-I', str(BOT / 'src'), str(HERE / 'retreat.cpp'), '-o', str(tmp / 'retreat')], check=True)
    subprocess.run([str(tmp / 'retreat')], check=True)
