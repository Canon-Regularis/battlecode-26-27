#!/usr/bin/env python3
"""Run unchanged production bodies against a deterministic native scenario host.
Only unrelated SDK setup/observation refresh and shop are replaced. No selector,
application, model, dispatch or camp executor decisions are copied into the test.
"""
from pathlib import Path
import subprocess
import tempfile
HERE = Path(__file__).resolve().parent
SRC = HERE.parent / 'src'

def omit(text, signature):
    start = text.index(signature)
    opening = text.index('{', start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[:start] + text[end:]

with tempfile.TemporaryDirectory(prefix='bwa01-') as tmp:
    out = Path(tmp)
    # Expose private diagnostic state only in this test build.
    (out / 'bot.h').write_text((SRC / 'bot.h').read_text().replace('class Bot {', 'class Bot {\npublic:'))
    (out / 'bot.cpp').write_text((SRC / 'bot.cpp').read_text())
    objectives = (SRC / 'objectives.cpp').read_text()
    for signature in ['void World::init()', 'void World::refresh(']:
        objectives = omit(objectives, signature)
    (out / 'objectives.cpp').write_text(objectives)
    (out / 'economy.cpp').write_text(omit((SRC / 'economy.cpp').read_text(), 'void shop('))
    flags = ['g++', '-std=c++20', '-O0', '-g', '-Wall', '-Wextra', '-Wno-misleading-indentation',
             '-I'+str(out), '-I'+str(HERE / 'mock'), '-I'+str(SRC)]
    subprocess.run(flags + [str(out / f) for f in ['bot.cpp', 'objectives.cpp', 'economy.cpp']] +
                   [str(SRC / 'state_machine.cpp'), str(HERE / 'bank_admission.cpp'), '-o', str(out / 'checks')], check=True)
    subprocess.run([str(out / 'checks')], check=True)
    subprocess.run(['g++', '-std=c++20', '-O2', '-I'+str(SRC), str(HERE / 'decisions.cpp'),
                    str(SRC / 'state_machine.cpp'), '-o', str(out / 'decisions')], check=True)
    subprocess.run([str(out / 'decisions')], check=True)
