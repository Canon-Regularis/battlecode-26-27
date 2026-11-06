"""Bounded native checks for the unfinished LOCAL economic-owner construction.

No official build, game, mailbox mutation, server upload or promotion.
"""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys
from party_feature_load import gentle_run

ROOT = Path(__file__).resolve().parents[1]
BOT = ROOT / 'bots/local_economic_core_01'
OUT = ROOT / '.cambc/campaign-2026-11-05/economic-core-construction-native-01'
CXX = Path('C:/msys64/mingw64/bin/g++.exe')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    receipt = {'implementation_origin': 'local_pc', 'release_ready': False,
               'games': 0, 'commands': [], 'files': {}, 'selected_checks': sys.argv[1:] or 'all',
               'tool_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               'sdk_sha256': {name: hashlib.sha256((ROOT/'sdk/cpp'/name).read_bytes()).hexdigest()
                              for name in ('cambc.h', 'imports.h')}}
    for path in sorted(BOT.rglob('*')):
        if path.is_file():
            receipt['files'][str(path.relative_to(BOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    def run(argv):
        result = subprocess.run([str(x) for x in argv], cwd=ROOT, capture_output=True,
                                text=True, encoding='utf-8', errors='replace', timeout=120)
        receipt['commands'].append({'argv': [str(x) for x in argv], 'returncode': result.returncode,
                                    'stdout': result.stdout, 'stderr': result.stderr})
        (OUT / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
        if result.returncode:
            print(result.stdout + result.stderr)
            raise RuntimeError('Native construction check failed; receipt retained')
        if result.stdout:
            print(result.stdout.strip(), flush=True)
    with gentle_run(ROOT / '.cambc/features'):
        for name, sources in [
            ('ledger', [BOT/'tests/turn_ledger.cpp', BOT/'src/turn_ledger.cpp']),
            ('recovery', [BOT/'tests/recovery_scenarios.cpp', BOT/'src/recovery.cpp']),
            ('live-turn', [BOT/'tests/live_turn.cpp', BOT/'src/live_turn.cpp', BOT/'src/turn_ledger.cpp']),
            ('economic-owner', [BOT/'tests/economic_owner.cpp', BOT/'src/economic_owner.cpp']),
            ('economic-access', [BOT/'tests/economic_access.cpp', BOT/'src/economic_access.cpp']),
            ('economic-candidates', [BOT/'tests/economic_candidates.cpp', BOT/'src/economic_candidates.cpp', BOT/'src/economic_owner.cpp']),
            ('economic-route', [BOT/'tests/economic_route.cpp', BOT/'src/economic_route.cpp']),
            ('economic-service', [BOT/'tests/economic_service.cpp', BOT/'src/economic_service.cpp', BOT/'src/service_work.cpp', BOT/'src/turn_ledger.cpp']),
            ('service-work', [BOT/'tests/service_work.cpp', BOT/'src/service_work.cpp']),
            ('service-sdk', [BOT/'tests/economic_service_sdk.cpp', BOT/'src/economic_service_sdk.cpp', BOT/'src/economic_service.cpp', BOT/'src/service_work.cpp', BOT/'src/live_turn.cpp', BOT/'src/turn_ledger.cpp']),
            ('capture-sdk', [BOT/'tests/economic_capture_sdk.cpp', BOT/'src/economic_scene_sdk.cpp', BOT/'src/economic_fields_sdk.cpp', BOT/'src/economic_candidates.cpp', BOT/'src/economic_ranking_sdk.cpp', BOT/'src/economic_plan_sdk.cpp', BOT/'src/economic_runtime_sdk.cpp', BOT/'src/economic_optional_sdk.cpp', BOT/'src/economic_owner.cpp', BOT/'src/economic_route.cpp', BOT/'src/economic_service_sdk.cpp', BOT/'src/economic_service.cpp', BOT/'src/service_work.cpp', BOT/'src/live_turn.cpp', BOT/'src/turn_ledger.cpp']),
            ('optional-sdk', [BOT/'tests/economic_optional_sdk.cpp', BOT/'src/economic_optional_sdk.cpp', BOT/'src/live_turn.cpp', BOT/'src/turn_ledger.cpp']),
        ]:
            if len(sys.argv) > 1 and name not in sys.argv[1:]:
                continue
            executable = OUT / (name + '.exe')
            flags = ['-fpermissive', '-w'] if name in ('live-turn', 'service-sdk', 'capture-sdk', 'optional-sdk') else ['-Wall', '-Wextra', '-Werror']
            if name == 'capture-sdk' and (BOT/'src/economic_bank_sdk.cpp').exists():
                sources.append(BOT/'src/economic_bank_sdk.cpp')
                flags.append('-DLP_TEST_REAL_BANK=1')
            if name == 'capture-sdk':
                sources.append(BOT/'src/economic_access.cpp')
            if name in ('service-sdk', 'capture-sdk', 'optional-sdk'):
                fixture = sources[0].read_text()
                imports = (ROOT/'sdk/cpp/imports.h').read_text()
                stubs = ['namespace cambc::detail {extern "C" {']
                for result, symbol, args in re.findall(r'(std::int32_t|std::int64_t|void|int)\s+(sdk_\w+)\s*\(([^;{}]*)\)\s*;', imports):
                    if not re.search(r'\b' + symbol + r'\s*\(', fixture):
                        stubs.append(f'{result} {symbol}({args}) {{ throw std::runtime_error("Unmocked host call: {symbol}"); }}')
                stubs.append('}}')
                stub_file = {'service-sdk': 'service_sdk_unused.inc', 'capture-sdk': 'capture_sdk_unused.inc', 'optional-sdk': 'optional_sdk_unused.inc'}[name]
                (OUT/stub_file).write_text('\n'.join(stubs), encoding='utf-8')
            run([CXX, '-std=c++20', '-O2', *flags, '-I', BOT/'src', '-I', ROOT/'sdk/cpp', '-I', OUT, *sources, '-o', executable])
            run([executable])
            if name == 'service-work':
                run([sys.executable, BOT/'tests/check_service_work.py', executable])
        run([CXX, '-std=c++20', '-fpermissive', '-w', '-fsyntax-only', '-I', ROOT/'sdk/cpp', *sorted((BOT/'src').glob('*.cpp'))])
    receipt['native_passed'] = True
    encoded = (json.dumps(receipt, indent=2) + '\n').encode('utf-8')
    digest = hashlib.sha256(encoded).hexdigest()
    archive = OUT / 'receipts'
    archive.mkdir(exist_ok=True)
    (archive / (digest + '.json')).write_bytes(encoded)
    (OUT/'receipt.json').write_bytes(encoded)
    print('Native receipt SHA256: ' + digest)
    print('PASS: selected native construction checks and complete production syntax. No strength claim.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
