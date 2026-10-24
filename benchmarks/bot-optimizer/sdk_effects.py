"""Archive the pinned guest SDK's fuel-read implementation for effect analysis."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.bot_optimizer.runtime import executable, run_command, replay_logs, check_logs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    src = args.output.resolve() / 'bot/src'
    src.mkdir(parents=True)
    source = '''import cambc
import inspect
import dis
import io
CASES=('noop',)
def noop():
    return None
def runtime_info():
    function=cambc.fuel_remaining
    result={'module_file':cambc.__file__, 'callable_type':type(function).__name__,
            'doc':function.__doc__}
    try:
        result['source']=inspect.getsource(function)
    except (OSError,TypeError) as error:
        result['source_error']=str(error)
    if hasattr(function,'__code__'):
        stream=io.StringIO()
        dis.dis(function,file=stream)
        result['bytecode']=stream.getvalue()
        result['names']=function.__code__.co_names
    return result
'''
    for name in ('original', 'optimized'):
        (src / f'{name}.py').write_text(source)
    (src / 'main.py').write_text(Path(__file__).with_name('src').joinpath('main.py').read_text())
    replay_dir = args.output.resolve() / 'collision'
    run_command([executable(), 'run', str(src.parent), str(src.parent), '--release',
                 '--rounds', '1', '--fuel', '1000000000', '--map', 'collision',
                 '--out-dir', str(replay_dir)], timeout=300)
    replay, = replay_dir.glob('*.repl26a')
    logs = replay_logs(replay)
    check_logs(logs)
    (args.output / 'logs.json').write_text(json.dumps(logs, indent=2)+'\n')
    print(json.dumps(logs, indent=2))


if __name__ == '__main__':
    main()
