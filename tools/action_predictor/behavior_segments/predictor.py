"""Experimental streaming inference; separate state for each champion is required."""
import json
import torch
from .data import REPORT,WORK,ROOT,FEATURES
from . import model
from .study import check
from ..data import digest
from ..goal_position.model import goal_guided_move


class BehaviorPredictor:
    def __init__(self,arm='S01'):
        if arm not in ('S00','S01'):raise ValueError('Unknown arm')
        self.plan=json.loads((REPORT/'protocol.json').read_text());check(self.plan)
        result=json.loads((REPORT/(arm+'.json')).read_text());path=WORK/(arm+'-run')/'final.pt'
        if digest(path)!=result['bindings'][str(path.relative_to(ROOT))]:raise ValueError('Checkpoint binding changed')
        saved=torch.load(path,map_location='cpu',weights_only=False)
        if saved['protocol_sha256']!=digest(REPORT/'protocol.json'):raise ValueError('Protocol mismatch')
        self.net=model.SegmentPolicy(self.plan['schema'],self.plan['codes']).eval();self.net.load_state_dict(saved['model'])

    @torch.no_grad()
    def predict(self,current,route,round_number,previous=None,previous_mask=None,state=None):
        """At the first nonadministrative query each own turn; current may be None.

        previous describes only the completed prior turn, ending at current PRE.
        state is an opaque dictionary returned here; reset at actor/window gaps
        and after32turns to match training. It must never be shared across actors.
        """
        if (previous is None)!=(previous_mask is None):raise ValueError('Supply history and its mask together')
        actor=None if current is None else current['observation']['own']['entity']
        if state is not None and actor is not None and state.get('actor') is not None and actor!=state['actor']:
            state=None
        if state is not None and state['turns']>=32:state=None
        if state is None:previous=[0.]*len(FEATURES);previous_mask=[0.]*len(FEATURES)
        elif previous is None:previous=[0.]*len(FEATURES);previous_mask=[0.]*len(FEATURES)
        step=dict(observed=current is not None,input=current,previous=previous,previous_mask=previous_mask,
            round=round_number,movement=None)
        args,_=model.encode_window(dict(steps=[step]),route,self.plan['schema'])
        output=self.net(**args,state=None if state is None else state['hidden']);probabilities=output['code'][0].softmax(-1)
        code=int(probabilities.argmax());goal=None;movement=None
        if current is not None and current['observation']['own'].get('position') is not None:
            index=int(output['goal'][0].flatten().argmax());goal=(index%route['width'],index//route['width'])
            movement=goal_guided_move(route,current,goal)
        return dict(code=code,code_probabilities=probabilities.tolist(),goal=goal,astar_movement=movement,
            interpretation='Predicted unnamed behavior code; not verified Fish intent.',
            state=dict(hidden=output['state'].detach(),turns=1 if state is None else state['turns']+1,
                actor=actor if actor is not None else None if state is None else state.get('actor')))
