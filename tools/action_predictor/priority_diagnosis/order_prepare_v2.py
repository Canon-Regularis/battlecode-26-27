"""Preserve v1 failure; repeat identical availability cases with explicit endianness."""
import copy
import json
from pathlib import Path

from ..audit import immutable_json
from ..data import digest
from .trajectory import ROOT,OUT


def run():
    parent=OUT/'PD03-api-plan.json'
    plan=copy.deepcopy(json.loads(parent.read_text()))
    for name,expected in plan['bindings'].items():
        if digest(name)!=expected:
            raise RuntimeError('Original availability dependency changed: '+name)
    source=Path(__file__).with_name('order_availability_v2.cjs')
    plan['bindings'][str(source)]=digest(source)
    plan['bindings'][str(Path(__file__))]=digest(Path(__file__))
    plan['output']=str(ROOT/'.cambc/action-predictor/v23/order-availability-v2.json')
    plan['raw_output']=str(ROOT/'.cambc/action-predictor/v23/order-availability-v2-events.jsonl')
    plan['parent_plan_sha256']=digest(parent)
    plan['change']='Only explicit little-endian int32 output reading. Cases, scoped API, inputs and controls unchanged; no models fitted.'
    immutable_json(OUT/'PD03-api-v2-plan.json',plan)
    print('Frozen v2 availability plan; unchanged cases and historical API.')


if __name__=='__main__':
    run()
