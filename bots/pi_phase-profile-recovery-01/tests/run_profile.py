"""Native diagnostic checks only; no engine or artifact-identity claim."""
from pathlib import Path
import os
import subprocess
import tempfile
from profile_preservation import BOT, ROOT, PARENT, tokens
CXX=os.environ.get('CXX','g++')
def run(args, **kw):
    return subprocess.run([str(x) for x in args],check=True,**kw)
with tempfile.TemporaryDirectory(prefix='ppfx-') as tmp:
    out=Path(tmp)
    for mask in ('0x1ffu','0u','0x155u'):
        exe=out/'profile'
        run([CXX,'-std=c++20','-O2','-Wall','-Wextra','-Werror','-DPPFX_ENABLED=1',f'-DPPFX_PHASE_MASK={mask}','-I',BOT/'src',BOT/'tests/phase_profile.cpp','-o',exe])
        run([exe])
    # OFF hooks must not even require valid names/types, nor pull in headers.
    off=out/'off.cpp'
    off.write_text('#include "phase_profile.h"\nPPFX(unavailable bad;)\n'+''.join(f'PPFX_{i}(unavailable bad;)\n' for i in range(9))+'int main(){}\n')
    run([CXX,'-std=c++20','-I',BOT/'src',off,'-o',out/'off'])
    run([out/'off'])
    run([CXX,'-std=c++20','-I',BOT/'src','-c',BOT/'src/phase_profile.cpp','-o',out/'off.o'])
    assert not subprocess.check_output(['nm','--defined-only',out/'off.o']).strip()
    # Compare actual compiler OFF preprocessing, independently of hook stripping.
    for name in ('bot.cpp','recovery.cpp','recovery_sdk.cpp'):
        parent=out/name
        parent.write_bytes(subprocess.check_output(['git','show',f'{PARENT}:bots/pi_actor-scene-epoch-01/src/{name}'],cwd=ROOT))
        def preprocess(path):
            return subprocess.check_output([CXX,'-std=c++20','-E','-P','-I',str(BOT/'src'),'-I',str(ROOT/'sdk/cpp'),str(path)]).decode()
        assert tokens(preprocess(parent))==tokens(preprocess(BOT/'src'/name)), name
    run([CXX,'-std=c++20','-fpermissive','-w','-DPPFX_ENABLED=1','-DPPFX_PHASE_MASK=0x1ffu','-fsyntax-only','-I',ROOT/'sdk/cpp',*sorted((BOT/'src').glob('*.cpp'))])
run(['python3',BOT/'tests/run_adapter.py','--profile'])
print('PASS: OFF compiler tokens, empty profiler object, ON SDK syntax; PC WASM hash gate still required')
