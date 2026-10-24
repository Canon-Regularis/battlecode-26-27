"""Archive selected actual Wasm disassembly and static instruction inventories.

Requires wasm-objdump (WABT); disassembly is static evidence, not a fuel profile.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re


TARGETS = {'builtin_sum', 'gen_iternext', 'gen_send_ex2', '_PyEval_EvalFrameDefault',
           '_PyDict_LoadGlobal', '_PyEvalFramePushAndInit', 'dict_subscript',
           'list_extend_iter_lock_held', 'pairwise_next', 'float_div',
           'list_item', 'list_subscript', 'tupleitem', 'tuplesubscript',
           'min_max', 'PyObject_RichCompareBool', 'float_add', 'float_mul', '_PyObject_MakeTpCall',
           'PyObject_GetAttr', '_PyObject_GenericGetAttrWithDict', 'PyObject_Vectorcall',
           'type_call', 'object_new', 'dict_new', 'insertdict', 'long_add', 'map_next',
           'attrgetter_call', 'PyObject_GenericSetAttr', '_PyObject_GenericSetAttrWithDict'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('wasm', type=Path)
    parser.add_argument('disassembly', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False, parents=True)
    functions = {}
    current = None
    with args.disassembly.open() as stream:
        for line in stream:
            match = re.match(r'([0-9a-f]+) func\[(\d+)\] <(.+)>:', line)
            if match:
                address, index, name = match.groups()
                current = None
                if name in TARGETS:
                    current = {'index': int(index), 'address': address, 'instructions': Counter(),
                               'direct_calls': Counter(), 'excerpt': []}
                    functions[name] = current
            if current is None:
                continue
            if len(current['excerpt']) < 180:
                current['excerpt'].append(line)
            if '|' in line:
                instruction = line.split('|', 1)[1].strip()
                if instruction and not instruction.startswith('local['):
                    current['instructions'][instruction.split()[0]] += 1
                    call = re.match(r'call \d+ <(.+)>', instruction)
                    if call:
                        current['direct_calls'][call[1]] += 1
    for name, function in functions.items():
        (args.output / f'{name}.txt').write_text(''.join(function.pop('excerpt')))
        function['static_instruction_count'] = sum(function['instructions'].values())
    data = args.wasm.read_bytes()
    report = {'status': 'complete', 'wasm': str(args.wasm), 'wasm_bytes': len(data),
              'wasm_sha256': hashlib.sha256(data).hexdigest(), 'dynamic_fuel_profile': False,
              'functions': functions}
    (args.output / 'results.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    for name, function in functions.items():
        print(name, function['static_instruction_count'], 'static instructions;',
              sum(function['direct_calls'].values()), 'direct call sites')


if __name__ == '__main__':
    main()
