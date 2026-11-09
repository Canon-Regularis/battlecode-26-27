"""Additive RC00 review response, exact feature corruption and artifact scope."""
import ast
import json
import subprocess
import numpy as np

from ..audit import immutable_json
from ..data import digest
from ..order_information.anchored import committed_manifest
from ..priority_broad.guard import committed_sources
from ..priority_regularized.safety import dependency_files,reject_optimized_python
from .data import load
from .protocol import ROOT,OUT,LOCAL

REVIEWED='1d9fb6b3b715cab36b3db2ff4e8acad6a616fe6f'


def run():
    reject_optimized_python()
    commit,sources=committed_sources(ROOT,dependency_files(ROOT,('tools.action_predictor.relational_priority.review_addendum',)))
    bank=load();bindings=dict(bank.bindings)
    review,more=committed_manifest(commit,'tools/action_predictor/experiments/v24/RC00-review.json');bindings.update(more)
    delegation,more=committed_manifest(commit,'tools/action_predictor/experiments/v24/RC00-review-delegation.json');bindings.update(more)
    info,more=committed_manifest(REVIEWED,'tools/action_predictor/experiments/v24/RC00.json');bindings.update(more)
    completion,more=committed_manifest(REVIEWED,'tools/action_predictor/experiments/v24/RC00-completion.json');bindings.update(more)
    analysis,more=committed_manifest(REVIEWED,'tools/action_predictor/experiments/v24/RC00-analysis.json');bindings.update(more)
    changed=np.zeros(len(bank.fit_mask),bool)
    for start in range(0,len(changed),256):
        sl=slice(start,start+256)
        changed[sl]=(bank.real[sl]!=bank.shuffled[sl]).any((1,2))
    metadata=bank.metadata;donors=metadata['donors']
    raw_changed=((metadata['priorities'][donors]!=metadata['priorities'])&metadata['available']).any((1,2))
    path=LOCAL/'review-addendum/corruption.npz'
    if path.exists():raise FileExistsError('Preserve feature corruption diagnostic')
    path.parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(path,index=bank.broad['index'].numpy(),fit_mask=bank.fit_mask,
                        raw_changed=raw_changed,features_changed=changed)
    bindings[str(path.relative_to(ROOT))]=digest(path)
    counts={name:dict(rows=int(mask.sum()),raw_values_changed=int((raw_changed&mask).sum()),
                     model_relation_features_changed=int((changed&mask).sum()),
                     model_relation_features_unchanged=int((~changed&mask).sum()))
            for name,mask in (('fit',bank.fit_mask),('held',~bank.fit_mask),('all',np.ones(len(changed),bool)))}
    # Training and decoding bodies must remain exactly the registered RC00 implementation.
    old=subprocess.run(['git','show',info['source_commit']+':tools/action_predictor/relational_priority/fit.py'],
                       cwd=ROOT,check=True,capture_output=True).stdout.decode('utf-8')
    new=(ROOT/'tools/action_predictor/relational_priority/fit.py').read_text(encoding='utf-8')
    def bodies(text):return {x.name:ast.dump(x,include_attributes=False) for x in ast.parse(text).body if isinstance(x,ast.FunctionDef)}
    a,b=bodies(old),bodies(new)
    preserved={name:a[name]==b[name] for name in ('execute','raw_forecast','predictions','gradient_contract','penalty','summary','base_fingerprint')}
    if not all(preserved.values()):raise RuntimeError('Treatment optimization/arithmetic differs from control')
    checkpoint=LOCAL/'runs/RC00/step-2000.pt'
    expected=info['bindings'][str(checkpoint.relative_to(ROOT))]
    if digest(checkpoint)!=expected:raise RuntimeError('Reviewed checkpoint changed')
    scope=dict(reviewed_commit=REVIEWED,checkpoint_sha256=expected,protocol_sha256=digest(OUT/'RC-plan.json'),
        reviewed_completion_sha256=digest(OUT/'RC00-completion.json'),reviewed_report_sha256=digest(OUT/'RC00.json'),
        reviewed_sources=info['sources'],raw_review_sha256=digest(OUT/'RC00-review.json'),
        delegation_sha256=digest(OUT/'RC00-review-delegation.json'),
        binding_basis='Parent-derived machine scope from the exact original delegation brief, reviewed commit and '
                      'reviewer confirmation of all166 completion bindings. Not a reviewer-authored structured '
                      'hash manifest. Raw task/review text and terminal model/effort receipt remain unchanged.')
    immutable_json(OUT/'RC00-review-scope.json',scope)
    response=dict(reviewed_checkpoint_sha256=expected,review_sha256=digest(OUT/'RC00-review.json'),
        delegation_sha256=digest(OUT/'RC00-review-delegation.json'),review_scope_sha256=digest(OUT/'RC00-review-scope.json'),
        ready_for_registered_treatment=True,
        authorization='Parent continuation under existing user authorization; not reviewer approval of RC01. '
                      'Actual fitter must still pass committed-source, input and all no-update prerequisite '
                      'tests before optimizer construction. This flag cannot bypass those tests.',
        responses=dict(review_gate='Require substantive fresh completed child/run, exact checkpoint in original task, '
            'reviewed commit and completion/source/protocol bindings, xhigh terminal delegation receipt and '
            'response bound to exact review/delegation/scope. Actual-entrypoint rejection tripwires added.',
            fixed_configuration='Preserve763certified/338unresolved held errors, zero-target-feature199to167 '
            'and nonzero213to400. No more updates/seeds/strength variants allocated against these ceilings.',
            corruption='Append exact feature-level counts, preserving unchanged and singleton rows and registered corruption.',
            calibration='ECE and binary mode-correctness Brier move in opposite directions. Each Brier concerns '
            'its own selected label, not a common-event multiclass Brier. No blanket calibration or large-error claim.',
            policy='Conditional family supplied; no policy gain or untouched generalization claim. Registered RC01 '
            'remains informative and retains identical fit math; full-policy work requires every-decision inputs and joint decoding.'),
        preserved_function_AST=preserved,new_fits=0,reserved_opened=0)
    immutable_json(OUT/'RC00-review-response.json',response)
    for name in ('RC00-review-scope.json','RC00-review-response.json'):
        p=OUT/name;bindings[str(p.relative_to(ROOT))]=digest(p)
    immutable_json(OUT/'RC00-review-addendum.json',dict(source_commit=commit,sources=sources,bindings=bindings,
        corruption=counts,held_reliability=analysis['conditional_reliability']['held'],
        held_scores=analysis['results']['held']['all']['models'],preserved_function_AST=preserved,
        interpretation='Exploratory diagnostic on previously exposed TRAIN. Shared active parameterization '
        'and shuffled training, not own-only or information-free control. Fixed-weight V25 interventions '
        'remain separate later evidence, not a replacement. Original targets unmet.',
        command='python -m tools.action_predictor.relational_priority.review_addendum',new_fits=0,reserved_opened=0))
    print('Corruption',counts,'preserved execution',preserved,flush=True)


if __name__=='__main__':run()
