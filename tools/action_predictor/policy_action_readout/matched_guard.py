"""Pin AB01's science to AB00; permit only explicit continuation-gate repairs."""
import ast
import hashlib
import subprocess
from pathlib import Path
from ..audit import immutable_json
from ..data import digest
from ..order_information.anchored import committed_manifest

ROOT=Path(__file__).resolve().parents[3]
CONTROL_COMMIT='4241a829d5283f852822abaf8eea29801942c8e5'
GUARDS={
    'tools/action_predictor/policy_action_readout/protocol.py',
    'tools/action_predictor/policy_action_readout/review_gate.py',
    'tools/action_predictor/policy_action_readout/test_review.py'}
NEW={'tools/action_predictor/policy_action_readout/matched_guard.py'}


def current_bytes(relative):return (ROOT/relative).read_bytes()


def protocol_science(source):
    tree=ast.parse(source.decode('utf-8-sig'))
    tree.body=[node for node in tree.body if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) or node.name!='source_gate']
    return ast.dump(tree,include_attributes=False)


def verify_scientific_contract(current_sources):
    report,_=committed_manifest(CONTROL_COMMIT,'tools/action_predictor/experiments/v28/AB00.json')
    frozen=report['sources'];changed=[]
    for name,expected in frozen.items():
        actual=current_bytes(name)
        if hashlib.sha256(actual).hexdigest()!=expected:
            if name not in GUARDS:raise RuntimeError('MATCHED_SCIENCE_CHANGED: '+name)
            changed.append(name)
    extras=set(current_sources)-set(frozen)
    if not extras<=NEW:raise RuntimeError('MATCHED_SCIENCE_CHANGED: unexpected executable dependencies '+str(sorted(extras-NEW)))
    name='tools/action_predictor/policy_action_readout/protocol.py'
    old=subprocess.run(['git','show',report['source_commit']+':'+name],cwd=ROOT,check=True,capture_output=True).stdout
    if hashlib.sha256(old).hexdigest()!=frozen[name]:raise RuntimeError('Original protocol source binding changed')
    if protocol_science(old)!=protocol_science(current_bytes(name)):
        raise RuntimeError('MATCHED_SCIENCE_CHANGED: protocol outside source_gate')
    return dict(control_scientific_commit=CONTROL_COMMIT,control_fit_commit=report['source_commit'],
        identical_scientific_sources=[name for name in frozen if name not in GUARDS],
        changed_guard_files=changed,new_guard_dependencies=sorted(extras),protocol_outside_source_gate_AST_identical=True,
        scope='Only source/review/input continuation guards and their tests may differ. Entire fit.py,model.py,data.py,assessment.py, initialization,sampling,optimization,decodingandassessmentbytesremainoriginalAB00. Frozen AB-plan/data-ready/checkpoints untouched.')


def main():
    from .protocol import source_gate,OUT
    commit,sources=source_gate();proof=verify_scientific_contract(sources)
    immutable_json(OUT/'AB-continuation-implementation.json',dict(proof,source_commit=commit,sources=sources,new_fits=0,reserved_opened=0))
    print(proof)


if __name__=='__main__':main()
