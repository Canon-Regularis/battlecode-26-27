"""Measure trained GRU input-weight contributions; no parameter updates."""
import json
import numpy as np
import torch
from .data import REPORT,WORK,load
from .model import SegmentPolicy,encode_window
from .study import check
from ..audit import immutable_json
from ..data import digest


def run():
    torch.set_num_threads(4);plan=json.loads((REPORT/'protocol.json').read_text());check(plan)
    net=SegmentPolicy(plan['schema'],plan['codes']).eval();net.load_state_dict(torch.load(WORK/'S01-run/final.pt',map_location='cpu',weights_only=False)['model'])
    inputs=[]
    handle=net.memory.register_forward_pre_hook(lambda module,args:inputs.append(args[0].detach()))
    windows,maps=load();all_x=[]
    with torch.no_grad():
        for w in windows:
            if w['partition']!='fit':continue
            inputs.clear();args,_=encode_window(w,maps[w['payload']],plan['schema']);net(**args)
            all_x.append(torch.cat(inputs)[args['observed'].bool()])
    handle.remove();x=torch.cat(all_x);weight=net.memory.weight_ih.detach();parts={};total=torch.zeros(len(x),144)
    for name,a,b in [('map_context',0,32),('history_values',32,55),('history_masks',55,78),('round_and_presence',78,80)]:
        p=x[:,a:b]@weight[:,a:b].T;total+=p
        parts[name]=dict(weight_rms=float(weight[:,a:b].square().mean().sqrt()),projected_rms=float(p.square().mean().sqrt()),
            centered_projected_rms=float((p-p.mean(0)).square().mean().sqrt()))
    torch.testing.assert_close(total,x@weight.T,rtol=1e-5,atol=1e-6)
    immutable_json(REPORT/'weight-input-probe.json',dict(source_sha256=digest(__file__),checkpoint_sha256=digest(WORK/'S01-run/final.pt'),
        fitting_rows=len(x),parts=parts,linear_reconstruction_passed=True,optimizer_updates=0))
    print(json.dumps(parts,indent=2))


if __name__=='__main__':run()
