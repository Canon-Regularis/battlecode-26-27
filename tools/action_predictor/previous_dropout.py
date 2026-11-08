"""Training-only grouped dropout of previous-vector features; matched Z01 control."""
import argparse,hashlib,json,subprocess,sys,time
import numpy as np
import torch
from .gradient_routing.data import ROOT,load_subset
from .gradient_routing.engine import update_window
from .gradient_routing.assessment import evaluate,comparison
from .gradient_routing.fit import checked_elapsed,publish_result
from .history_horizon.model import Policy as BasePolicy
from .history_horizon.data import chunks
from .reliable_train import setup
from .priority_broad.guard import committed_sources
from .priority_regularized.safety import dependency_files
from .audit import immutable_json
from .data import digest

REPORT=ROOT/'tools/action_predictor/experiments/v41'
WORK=ROOT/'.cambc/action-predictor/v41'
CONTROL=ROOT/'.cambc/action-predictor/v40/runs/Z01'
CONTROL_REPORT=ROOT/'tools/action_predictor/experiments/v40'
TESTS=('tools.action_predictor.test_previous_dropout','tools.action_predictor.test_neutral_bias','tools.action_predictor.gradient_routing.test_contract',
       'tools.action_predictor.history_horizon.test_contract','tools.action_predictor.movement_diagnosis.test_audit')


MASK_SEED=270041


def corrupt_grid(grid,family,keep):
    move=family==8
    if keep.shape!=(int(move.sum()),):raise ValueError('Mask size mismatch')
    changed=grid.clone()
    # Inverted grouped dropout: both channels and all candidates share one draw.
    changed[move,:,18:20]*=keep[:,None,None].to(grid.dtype)*2
    return changed


class Policy(BasePolicy):
    def __init__(self):
        super().__init__()
        self.mask_generator=torch.Generator().manual_seed(MASK_SEED)
        self.mask_draws=0;self.mask_dropped=0;self.mask_hash=hashlib.sha256()

    def spatial(self,step,grid,valid,rules,family):
        if self.training and bool((family==8).any()):
            n=int((family==8).sum())
            keep=torch.rand(n,generator=self.mask_generator)>=.5
            self.mask_draws+=n;self.mask_dropped+=int((~keep).sum())
            self.mask_hash.update(keep.numpy().astype(np.uint8).tobytes())
            grid=corrupt_grid(grid,family,keep)
        return super().spatial(step,grid,valid,rules,family)


def build():
    model=Policy()
    with torch.no_grad():model.execution.offset_bias.weight[8,:289].zero_()
    return model


def initial_parity(model,reference):
    for name,value in model.state_dict().items():
        if not torch.equal(value,reference[name]):raise ValueError('Unmatched initialization: '+name)


def sources():
    return committed_sources(ROOT,dependency_files(ROOT,('tools.action_predictor.previous_dropout',*TESTS)))


def freeze():
    REPORT.mkdir(parents=True,exist_ok=True)
    commit,code=sources();prior=json.loads((CONTROL_REPORT/'protocol.json').read_text())
    inputs=dict(prior['inputs'])
    for key,value in {**prior['inputs'],**prior['sources']}.items():
        if digest(ROOT/key)!=value:raise ValueError('Control provenance changed: '+key)
    control=json.loads((CONTROL_REPORT/'Z01.json').read_text());verification=json.loads((CONTROL_REPORT/'Z01-verification.json').read_text())
    if verification['result_sha256']!=digest(CONTROL_REPORT/'Z01.json') or not verification['comparison_reproduced_exactly']:
        raise ValueError('Parent-verified control changed')
    for key,value in control['bindings'].items():
        if digest(ROOT/key)!=value:raise ValueError('Control archive changed')
        inputs[key]=value
    for p in (CONTROL_REPORT/'protocol.json',CONTROL_REPORT/'Z01.json',CONTROL_REPORT/'Z01-verification.json',
              ROOT/'tools/action_predictor/experiments/v39/audit.json',ROOT/'tools/action_predictor/experiments/v39/supported-offsets.json',
              REPORT/'review-policy.json'):
        inputs[str(p.relative_to(ROOT))]=digest(p)
    setup(27);model=build();initial=torch.load(CONTROL/'initial.pt',map_location='cpu',weights_only=False)
    initial_parity(model,initial['state'])
    if not torch.equal(torch.get_rng_state(),initial['torch_rng']):raise ValueError('Initialization RNG differs')
    immutable_json(REPORT/'protocol.json',dict(source_commit=commit,sources=code,inputs=inputs,
        question='Does training-only grouped dropout of direct previous-vector grid channels improve clean-input movement without sacrificing continuations?' ,
        hypothesis='The saved scorer depends strongly on previous-vector channels. Label-independent training corruption may encourage other causal evidence; destructive posthoc erasure does not establish benefit.',
        treatment='D01 fresh seed27 neutral-bias Policy, exactly Z01 initial tensors/global RNG. Only during training movement spatial likelihood: one Bernoulli(.5) per movement row, shared over channels18:20 and289candidates; dropped group zero, kept group scaled2 (inverted dropout). Separate mask generator seed270041 independent of sampler/global RNG. No direction/error-conditioned masks. Explicit actual command/observation histories remain unchanged. Evaluation disables corruption and uses original inputs.',
        control='Reuse parent-verified completed V40 Z01, no repeat. Identical original unprojected R00 engine, three gradient parts summed, whole-batch denominators, reset/detach8 and update order. Also retain R00 original reference guards.',
        data='Exact1085fitwindows/34720rows/40groups; no tuning, assessment, originalDEV or reserved payloads.',
        optimization='Eightpasses/272updates/277760rowpresentations;32roots xupto32lanes,1024or928rows. Identical saved permutations and RNG. AdamW lr.0003 decay.01 clip5. Final8only; no extra checkpoint choice/repeats/extensions.',
        budget=dict(new_fits=1,combined_seconds=7200,control_seconds=control['seconds']),
        acceptance=prior['acceptance'],required_references=['Z01','R00'],
        review='User now explicitly requests no subagents. Parent performs code/data/result verification and interpretation directly. No delegated review or approval is invented.',
        limits='Exposed fitting-only one-seed training-corruption contrast. Rate .5 and seed fixed once, no rate sweep. Online loss is on corrupted inputs; final scores use clean inputs. No pretrained warm start. Passing only motivates transfer work; strong-reference/category90/reliability/three-seed and existing data limits remain. No strategy/generalization/promotion.',
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
        all_delegation_skipped_by_explicit_user_request=True)


def run():
    plan,gate=preflight();directory=WORK/'runs/D01'
    if directory.exists():raise FileExistsError('Preserve prior attempt; no restart')
    setup(27);data=load_subset();model=build()
    initial_control=torch.load(CONTROL/'initial.pt',map_location='cpu',weights_only=False)
    initial_parity(model,initial_control['state'])
    if not torch.equal(torch.get_rng_state(),initial_control['torch_rng']):raise ValueError('RNG mismatch')
    directory.mkdir(parents=True);immutable_json(directory/'preflight.json',gate)
    optimizer=torch.optim.AdamW(model.parameters(),lr=.0003,weight_decay=.01)
    if optimizer.state:raise ValueError('Nonempty initial optimizer')
    rng=np.random.default_rng(27);updates=0;trace=[];tick=time.perf_counter()
    schedules=json.loads((ROOT/'tools/action_predictor/experiments/v36/construction-probe.json').read_text())['schedules']
    def budget():return checked_elapsed(tick,gate['prior_seconds'])
    def save(name,epoch):
        torch.save(dict(state=model.state_dict(),optimizer=optimizer.state_dict(),round=epoch,updates=updates,
            torch_rng=torch.get_rng_state(),numpy_rng=rng.bit_generator.state,arm='D01',protocol_sha256=gate['protocol_sha256'],mask_rng=model.mask_generator.get_state(),
            mask_draws=model.mask_draws,mask_dropped=model.mask_dropped,mask_sha256=model.mask_hash.hexdigest()),directory/name)
    save('initial.pt',0);initial_prediction,initial=evaluate(model,data,directory,'initial');budget()
    with np.load(CONTROL/'initial-predictions.npz') as z:
        for k,v in initial_prediction.items():
            if not np.array_equal(v,z[k],equal_nan=True):raise ValueError('Initial forecast mismatch')
    if model.mask_draws:raise ValueError('Evaluation consumed masks')
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
        if model.mask_draws!=epoch*5472:raise ValueError('Movement mask exposure mismatch')
        save(f'round-{epoch:02d}.pt',epoch)
        measurement=dict(round=epoch,updates=updates,row_presentations=34720,online_nll=total/34720,
            schedule_sha256=schedule.hexdigest(),coverage=dict(min=int(seen.min()),max=int(seen.max())),steps=records,mask_draws=model.mask_draws,mask_dropped=model.mask_dropped,mask_sha256=model.mask_hash.hexdigest())
        trace.append(measurement);immutable_json(directory/f'round-{epoch:02d}.json',measurement)
        print('D01 pass',epoch,'updates',updates,'online_NLL',total/34720,flush=True)
    budget();mask_before=model.mask_generator.get_state().clone();prediction,final=evaluate(model,data,directory,'final');budget()
    if not torch.equal(mask_before,model.mask_generator.get_state()):raise ValueError('Evaluation consumed masks')
    with np.load(CONTROL/'final-predictions.npz') as z:reference={k:z[k] for k in z.files}
    comparisons={'Z01':comparison(data,prediction,reference)}
    with np.load(ROOT/'.cambc/action-predictor/v36/runs/R00/final-predictions.npz') as z:original={k:z[k] for k in z.files}
    comparisons['R00']=comparison(data,prediction,original)
    records=[s for row in trace for s in row['steps']]
    bindings={str(p.relative_to(ROOT)):digest(p) for p in directory.rglob('*') if p.is_file()}
    publish_result(REPORT/'D01.json',dict(arm='D01',protocol_sha256=gate['protocol_sha256'],source_commit=gate['source_commit'],
        bindings=bindings,initial=initial,final=final,comparisons=comparisons,trace=trace,
        selected_round=8,completed_rounds=8,completed_updates=updates,row_presentations=277760,
        clipping=dict(steps=len(records),clipped=sum(s['clipped'] for s in records)),
        mask_draws=model.mask_draws,mask_dropped=model.mask_dropped,mask_sha256=model.mask_hash.hexdigest(),
        all_checks_pass=all(c['all_checks_pass'] for c in comparisons.values()),new_fits=1,optimizer_updates=updates,promoted=False,reserved_opened=0),tick,gate['prior_seconds'])
    print('D01 completed; parent verification and result interpretation next',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=('freeze','run'))
    args=parser.parse_args();freeze() if args.command=='freeze' else run()
