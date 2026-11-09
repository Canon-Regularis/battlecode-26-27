"""Trained E01 set-order, padding and value-path checks, without fitting."""
from pathlib import Path
import sys
import numpy as np
import torch
from .fundamental_audit import ROOT,REPORTS,WORK,arrays,log
from .priority_fit_v3 import BASE,VAL,read,load_base
from .priority_residual_fit import head as priority_head
from .priority_head import flatten
from .action_priority_head import classifier_features
from .entity_model import EntityMovementModel
from .entity_set import EntityBank
from .entity_cache import DIRECTORY
from .more_replays import frozen,sha
from . import reliable_train as rt

@torch.no_grad()
def run():
    rt.setup(26);report=read(REPORTS/'E01.json');path=WORK/'runs/E01/model.pt';assert sha(path)==report['checkpoint_sha256']
    saved=torch.load(path,weights_only=True,map_location='cpu');teacher,base=load_base();priority=priority_head(teacher.priority)
    model=EntityMovementModel(teacher,priority,saved['config']['dimension'],True);model.load_state_dict(saved['state_dict']);model.eval()
    with np.load(VAL) as z:raw={k:z[k] for k in z.files}
    data,_=rt.model_data(raw,base['config'],(base['mean'],base['std']))
    with np.load(BASE.parent/'v8/priority-validation.npz') as z:
        values=torch.from_numpy(z['values']);extra=torch.from_numpy((flatten(z['values'],z['history']).astype(np.float32)-saved['priority_mean'].numpy())/saved['priority_std'].numpy())
    features=classifier_features(extra,values);bank=EntityBank(DIRECTORY,'validation',saved['config']['dimension']);rows=np.linspace(0,len(raw['y'])-1,64,dtype=np.int64);entities,mask=bank.batch(rows)
    def forecast(e,m):
        logits,movement,context=model(data['x'][rows],data['history'][rows],e,m,features[rows]);family=logits.argmax(-1)
        coordinate=model.parameter_logits(movement,context,data['grid'][rows].float(),data['valid'][rows],family,data['rules'][rows]).softmax(-1)
        return logits.softmax(-1),coordinate
    original=forecast(entities,mask);rng=np.random.default_rng(20261107);permutation=torch.from_numpy(np.stack([rng.permutation(mask.shape[1]) for _ in rows]));reordered=forecast(entities.gather(1,permutation[:,:,None].expand_as(entities)),mask.gather(1,permutation))
    padding=torch.from_numpy(rng.normal(0,100,(len(rows),11,entities.shape[-1])).astype(np.float32));padded=forecast(torch.cat((entities,padding),1),torch.cat((mask,torch.zeros((len(rows),11),dtype=torch.bool)),1))
    changed=forecast(torch.zeros_like(entities),mask)
    order_error=max(float((a-b).abs().max()) for a,b in zip(original,reordered));padding_error=max(float((a-b).abs().max()) for a,b in zip(original,padded))
    assert order_error<=2e-6 and padding_error<=2e-6
    sensitivity=max(float((a-b).abs().max()) for a,b in zip(original,changed))
    assert sensitivity>0,'Actual entity path unexpectedly inactive'
    result=dict(checkpoint_sha256=report['checkpoint_sha256'],source_sha256=sha(__file__),rows=rows.tolist(),permutation_max_probability_error=order_error,masked_padding_max_probability_error=padding_error,tolerance=2e-6,zero_value_sensitivity_max_probability_change=sensitivity,scope='Actual selected E01 checkpoint,64 fixed development inputs. Set order and masked synthetic padding invariance; zero-token sensitivity is a pathway check without accuracy evaluation or model selection, not a quality gain.',new_fits=0,reserved_opened=0)
    frozen(REPORTS/'E01-attention-checks.json',result);(REPORTS/'E01-attention-checks-source.txt').write_bytes(Path(__file__).read_bytes());print(result)

if __name__=='__main__':log([sys.executable,'-m','tools.action_predictor.entity_attention_checks']);run()
