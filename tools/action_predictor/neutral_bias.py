"""Matched neutral movement-bias initialization; reuse the completed R00 control."""
import argparse,hashlib,json,subprocess,sys,time
import numpy as np
import torch
from .gradient_routing.data import ROOT,load_subset
from .gradient_routing.engine import update_window
from .gradient_routing.assessment import evaluate,comparison
from .gradient_routing.fit import checked_elapsed,publish_result
from .history_horizon.model import Policy
from .history_horizon.data import chunks
from .reliable_train import setup
from .priority_broad.guard import committed_sources
from .priority_regularized.safety import dependency_files
from .audit import immutable_json
from .data import digest

REPORT=ROOT/'tools/action_predictor/experiments/v40'
WORK=ROOT/'.cambc/action-predictor/v40'
CONTROL=ROOT/'.cambc/action-predictor/v36/runs/R00'
CONTROL_REPORT=ROOT/'tools/action_predictor/experiments/v36'
TESTS=('tools.action_predictor.test_neutral_bias','tools.action_predictor.gradient_routing.test_contract',
       'tools.action_predictor.history_horizon.test_contract','tools.action_predictor.movement_diagnosis.test_audit')


def build():
    model=Policy()
    with torch.no_grad():model.execution.offset_bias.weight[8,:289].zero_()
    return model


def initial_parity(model,reference):
    for name,value in model.state_dict().items():
        expected=reference[name].clone()
        if name=='execution.offset_bias.weight':expected[8,:289]=0
        if not torch.equal(value,expected):raise ValueError('Unmatched initialization: '+name)


def sources():
    return committed_sources(ROOT,dependency_files(ROOT,('tools.action_predictor.neutral_bias',*TESTS)))


def freeze():
    REPORT.mkdir(parents=True,exist_ok=True)
    commit,code=sources();prior=json.loads((CONTROL_REPORT/'protocol.json').read_text())
    inputs=dict(prior['inputs'])
    for key,value in {**prior['inputs'],**prior['sources']}.items():
        if digest(ROOT/key)!=value:raise ValueError('Control provenance changed: '+key)
    control=json.loads((CONTROL_REPORT/'R00.json').read_text());review=json.loads((CONTROL_REPORT/'R00-review.json').read_text())
    if review['verdict']!='APPROVE' or review['result_sha256']!=digest(CONTROL_REPORT/'R00.json'):
        raise ValueError('Control approval changed')
    for key,value in control['bindings'].items():
        if digest(ROOT/key)!=value:raise ValueError('Control archive changed')
        inputs[key]=value
    for p in (CONTROL_REPORT/'protocol.json',CONTROL_REPORT/'R00.json',CONTROL_REPORT/'R00-review.json',
              ROOT/'tools/action_predictor/experiments/v39/audit.json',ROOT/'tools/action_predictor/experiments/v39/supported-offsets.json',
              REPORT/'review-policy.json'):
        inputs[str(p.relative_to(ROOT))]=digest(p)
    setup(27);model=build();initial=torch.load(CONTROL/'initial.pt',map_location='cpu',weights_only=False)
    initial_parity(model,initial['state'])
    if not torch.equal(torch.get_rng_state(),initial['torch_rng']):raise ValueError('Initialization RNG differs')
    immutable_json(REPORT/'protocol.json',dict(source_commit=commit,sources=code,inputs=inputs,
        question='Does neutral movement destination-bias initialization improve learning compared with the completed matched R00 random-bias control?',
        hypothesis='Persistent random movement offset preferences may impede alternative ranking during learning. The weak posthoc deletion effect does not establish benefit from retraining.',
        treatment='Z01 fresh seed27 Policy: only execution.offset_bias.weight[8,:289] starts at zero. Special movement biases and every other tensor exactly match R00 initial; RNG identical. All139292 parameters remain trainable.',
        control='Reuse reviewed completed V36 R00, no repeat. Same original unprojected R00 engine, three gradient parts summed, whole-batch denominators, reset/detach8 and update order.',
        data='Exact1085fitwindows/34720rows/40groups; no tuning, assessment, originalDEV or reserved payloads.',
        optimization='Eightpasses/272updates/277760rowpresentations;32roots xupto32lanes,1024or928rows. Identical saved permutations and RNG. AdamW lr.0003 decay.01 clip5. Final8only; no extra checkpoint choice/repeats/extensions.',
        budget=dict(new_fits=1,combined_seconds=7200,control_seconds=control['seconds']),
        acceptance=prior['diagnostic_allocation'],
        review='User explicitly requested continuing without code review. Parent tests/checks replace the code-review wait, not fabricated approval. Negative training results still follow requested Astra high review.',
        limits='Exposed fitting-only one-seed initialization contrast. No pretrained warm start. Passing only motivates transfer work; strong-reference/category90/reliability/three-seed and existing data limits remain. No strategy/generalization/promotion.',
        initial_nonintervention_tensors_exact=True,initial_rng_exact=True,new_fits=0))


def preflight():
    commit,code=sources();plan=json.loads((REPORT/'protocol.json').read_text())
    if code!=plan['sources']:raise ValueError('Frozen source changed')
    for key,value in plan['inputs'].items():
        if digest(ROOT/key)!=value:raise ValueError('Frozen input changed: '+key)
    test=subprocess.run([sys.executable,'-m','unittest',*TESTS,'-v'],cwd=ROOT,capture_output=True,text=True)
    if test.returncode:raise RuntimeError(test.stdout+test.stderr)
    return plan,dict(source_commit=commit,protocol_sha256=digest(REPORT/'protocol.json'),
        prior_seconds=plan['budget']['control_seconds'],tests_stdout=test.stdout,tests_stderr=test.stderr,
        code_review_skipped_by_explicit_user_request=True)


def run():
    plan,gate=preflight();directory=WORK/'runs/Z01'
    if directory.exists():raise FileExistsError('Preserve prior attempt; no restart')
    setup(27);data=load_subset();model=build()
    initial_control=torch.load(CONTROL/'initial.pt',map_location='cpu',weights_only=False)
    initial_parity(model,initial_control['state'])
    if not torch.equal(torch.get_rng_state(),initial_control['torch_rng']):raise ValueError('RNG mismatch')
    directory.mkdir(parents=True);immutable_json(directory/'preflight.json',gate)
    optimizer=torch.optim.AdamW(model.parameters(),lr=.0003,weight_decay=.01)
    if optimizer.state:raise ValueError('Nonempty initial optimizer')
    rng=np.random.default_rng(27);updates=0;trace=[];tick=time.perf_counter()
    schedules=json.loads((CONTROL_REPORT/'construction-probe.json').read_text())['schedules']
    def budget():return checked_elapsed(tick,gate['prior_seconds'])
    def save(name,epoch):
        torch.save(dict(state=model.state_dict(),optimizer=optimizer.state_dict(),round=epoch,updates=updates,
            torch_rng=torch.get_rng_state(),numpy_rng=rng.bit_generator.state,arm='Z01',protocol_sha256=gate['protocol_sha256']),directory/name)
    save('initial.pt',0);_,initial=evaluate(model,data,directory,'initial');budget()
    for epoch in range(1,9):
        model.train();seen=np.zeros(34720,np.uint8);schedule=hashlib.sha256();total=0.;records=[]
        for rows in chunks(data['sequences'],rng,unroll=32):
            budget();loss,steps=update_window(model,data,rows,optimizer,'R00')
            updates+=len(steps);records.extend(steps);total+=loss;seen[rows[rows>=0]]+=1
            schedule.update(rows.astype('<i8').tobytes())
        expected=schedules[epoch-1]
        if not np.all(seen==1) or updates!=epoch*34:raise ValueError('Coverage/update mismatch')
        if schedule.hexdigest()!=expected['schedule_sha256'] or rng.bit_generator.state!=expected['numpy_rng']:raise ValueError('Schedule/RNG mismatch')
        if [s['rows'] for s in records]!=expected['denominators']:raise ValueError('Denominator mismatch')
        if any(s['projected'] for s in records):raise ValueError('Unexpected gradient projection')
        save(f'round-{epoch:02d}.pt',epoch)
        measurement=dict(round=epoch,updates=updates,row_presentations=34720,online_nll=total/34720,
            schedule_sha256=schedule.hexdigest(),coverage=dict(min=int(seen.min()),max=int(seen.max())),steps=records)
        trace.append(measurement);immutable_json(directory/f'round-{epoch:02d}.json',measurement)
        print('Z01 pass',epoch,'updates',updates,'online_NLL',total/34720,flush=True)
    budget();prediction,final=evaluate(model,data,directory,'final');budget()
    with np.load(CONTROL/'final-predictions.npz') as z:reference={k:z[k] for k in z.files}
    comparisons={'R00':comparison(data,prediction,reference)}
    records=[s for row in trace for s in row['steps']]
    bindings={str(p.relative_to(ROOT)):digest(p) for p in directory.rglob('*') if p.is_file()}
    publish_result(REPORT/'Z01.json',dict(arm='Z01',protocol_sha256=gate['protocol_sha256'],source_commit=gate['source_commit'],
        bindings=bindings,initial=initial,final=final,comparisons=comparisons,trace=trace,
        selected_round=8,completed_rounds=8,completed_updates=updates,row_presentations=277760,
        clipping=dict(steps=len(records),clipped=sum(s['clipped'] for s in records)),
        all_checks_pass=comparisons['R00']['all_checks_pass'],new_fits=1,optimizer_updates=updates,promoted=False,reserved_opened=0),tick,gate['prior_seconds'])
    print('Z01 completed; parent verification and result interpretation next',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=('freeze','run'))
    args=parser.parse_args();freeze() if args.command=='freeze' else run()
