"""New movement checkpoint -> saved arrays and personal-PRE serving proof."""
from collections import defaultdict
from pathlib import Path
import gzip,json,sys
import numpy as np
import torch
from . import reliable_train as rt
from .fundamental_audit import ROOT,WORK,REPORTS,arrays,log
from .priority_fit_v3 import BASE,VAL,read,load_base,context_directory
from .priority_residual_fit import VOCAB
from .movement_study import infer
from .movement_mixture import MovementMixture,previous_direction
from .movement_predictor import MovementMixturePredictor
from .more_replays import frozen,sha
from .rich_data import read_turns,SPATIAL
from .observation_data import compact_supplement
from .audit import cursor

@torch.no_grad()
def run(identifier):
    rt.setup(26);info=read(REPORTS/(identifier+'.json'));plan=read(REPORTS/(identifier+'-plan.json'));directory=WORK/'runs'/identifier;cp=directory/'model.pt'
    assert sha(cp)==info['checkpoint_sha256'] and sha(directory/'validation-predictions.npz')==info['predictions_sha256']
    for path,digest in plan['sources'].items():assert sha(path)==digest
    assert sha(REPORTS/(identifier+'-plan.json'))==info['plan_sha256']
    saved=torch.load(cp,weights_only=True,map_location='cpu');teacher,base=load_base();model=MovementMixture(teacher,saved['specialized']);model.load_state_dict(saved['state_dict']);model.eval()
    raw=arrays(VAL);data,_=rt.model_data(raw,base['config'],(saved['mean'],saved['std']));context=torch.from_numpy(np.load(context_directory()/'validation.npy'));baseline=arrays(BASE.parent/'v8/runs/P05/validation-predictions.npz');stored=arrays(directory/'validation-predictions.npz')
    fresh,_=infer(model,data,baseline,context)
    for key in stored:np.testing.assert_array_equal(fresh[key],stored[key],err_msg='Saved array reproduction: '+key)
    # Retain batched reference probabilities of the actual proposed family.
    probabilities=[]
    for a in range(0,len(raw['y']),256):
        b=min(a+256,len(raw['y']));encoded=model.encode(data['x'][a:b],data['history'][a:b],context[a:b]);family=torch.from_numpy(stored['prediction'][a:b]);grid=data['grid'][a:b].float();lp,_,_=model.parameter_log_probs(encoded,grid,data['valid'][a:b],family,data['rules'][a:b])
        retained=teacher.parameter_logits(encoded[0],grid,data['valid'][a:b],family,data['rules'][a:b]).log_softmax(-1);changed=(family==8)|(family==3);probabilities.append(torch.where(changed[:,None],lp,retained).exp())
    reference=torch.cat(probabilities);prob_path=directory/'validation-proposed-probabilities.npy'
    if prob_path.exists():np.testing.assert_array_equal(np.load(prob_path),reference.numpy())
    else:np.save(prob_path,reference.numpy())
    legacy=BASE.parent/'v8';jobs=[j for j in read(BASE.parent/'v7/jobs.json') if j['split']=='validation'];norm=context_directory()/'extra-normalization.npz';vocab=read(VOCAB);maximum=0.;cases=0;movement_cases=0;missing=0
    for job in jobs:
        digest=job['record']['raw_sha256'];events=defaultdict(list)
        with (Path(job['manifest']['source'])/'extracted'/digest/'index.jsonl').open() as stream:
            for line in stream:
                t=json.loads(line)
                if t.get('record')=='turn':
                    for root in t['roots']:events[t['actor']].append((root,t['round']))
        for roots in events.values():roots.sort(key=lambda p:cursor(p[0]['event']))
        states={};supplements={};route=None
        with gzip.open(legacy/'priority'/digest/'pre.jsonl.gz','rt') as stream:
            for line in stream:
                row=json.loads(line)
                if row['record']=='priority_pre':states[row['event']]=row
        with (Path(job['work'])/'supplement'/digest/'pre.jsonl').open() as stream:
            for line in stream:
                row=json.loads(line)
                if row['record']=='map':route=row['route']
                elif row['record']=='pre':supplements[row['id']]=compact_supplement(row)
        targets=[(t,d) for t in read_turns(job['manifest'],job['record']) for d in t['decisions']]
        # Index-only cases plus the first proposed move/blocked per game ensure
        # the changed path is exercised; never select by correctness or labels.
        selected={0,len(targets)//2,len(targets)-1}
        guessed=np.flatnonzero(np.isin(stored['prediction'][job['offset']:job['offset']+job['rows']],[8,3]))
        if len(guessed):selected.add(int(guessed[0]))
        for local in sorted(selected):
            turn,d=targets[local];idx=job['offset']+local;predictor=MovementMixturePredictor(BASE/'runs/M01/model.pt',norm,vocab,legacy/'runs/P05/model.pt',cp,info['checkpoint_sha256'],turn['actor'])
            for root,rnd in events[turn['actor']]:
                if cursor(root['event'])>cursor(d['pre_cursor']):break
                predictor.observe(root['event'],root['header']['step'],rnd)
            args=(d['observation'],supplements[d['id']],route,turn['round'],d['pre_cursor'],states[d['event_cursor']]);actual=predictor.inputs(*args)
            for key in ('x','history','valid','rules'):assert torch.equal(actual[key],data[key][idx:idx+1]),(idx,key)
            assert torch.equal(actual['grid'],data['grid'][idx:idx+1].float())
            output=predictor.distributions(actual);family=int(output['action'].argmax());assert family==int(stored['prediction'][idx])
            assert int(output['coordinate'].argmax())==int(stored['proposed_coordinate'][idx])
            assert int(predictor.head.integer(output['priority_raw'],actual['priority_values'])[0])==int(stored['priority'][idx])
            if family in (8,3):
                error=float((output['coordinate']-reference[idx:idx+1]).abs().max());maximum=max(maximum,error);assert error<=2e-6
                movement_cases+=1;missing+=int(not bool(output['prior_offset_available'][0]))
            cases+=1
    result=dict(report_sha256=sha(REPORTS/(identifier+'.json')),checkpoint_sha256=info['checkpoint_sha256'],sources={str(Path(__file__).resolve()):sha(__file__),str(Path(__file__).with_name('movement_predictor.py').resolve()):sha(Path(__file__).with_name('movement_predictor.py'))},cases=cases,games=25,movement_serving_cases=movement_cases,missing_history_cases=missing,inputs_exact=True,all_eight_saved_arrays_reproduced=True,saved_array_scope='Fresh checkpoint via retained frozen fitter inference function; serving independently builds raw personal PRE/action memory inputs. Not a separate implementation of expert math.',batched_reference_probabilities_sha256=sha(prob_path),single_row_vs_batch_probability_max_error=maximum,tolerance=2e-6,case_selection='First/middle/last row and first model-proposed movement/blocked per game; never correctness or future-label selected.',reserved_opened=0,new_fits=0)
    frozen(REPORTS/(identifier+'-causal-roundtrip.json'),result)
    for path,digest in result['sources'].items():(REPORTS/(identifier+'-'+digest+'-'+Path(path).name+'.txt')).write_bytes(Path(path).read_bytes())
    print('Movement saved arrays and raw-PRE serving proof passed',cases,'cases;',movement_cases,'movement cases; max error',maximum)

if __name__=='__main__':log([sys.executable,'-m','tools.action_predictor.movement_roundtrip',*sys.argv[1:]]);run(sys.argv[1])
