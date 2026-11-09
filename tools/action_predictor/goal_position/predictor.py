"""Experimental inference interface; deliberately not enabled in the playing bot."""
import json
import torch
from . import model
from .study import OUT,RUN,ROOT,check
from ..data import digest


class GoalPredictor:
    def __init__(self):
        self.protocol=json.loads((OUT/'protocol.json').read_text());check(self.protocol)
        result=json.loads((OUT/'result.json').read_text())
        expected=result['bindings'][str((RUN/'final.pt').relative_to(ROOT))]
        if digest(RUN/'final.pt')!=expected:raise ValueError('Goal weights changed')
        checkpoint=torch.load(RUN/'final.pt',map_location='cpu',weights_only=False)
        if checkpoint['protocol_sha256']!=digest(OUT/'protocol.json'):raise ValueError('Checkpoint protocol mismatch')
        self.keys=self.protocol['schema'];self.net=model.GoalMap(self.keys).eval();self.net.load_state_dict(checkpoint['model'])

    @torch.no_grad()
    def predict(self,observation,supplement,route):
        row=dict(observation=observation,supplement=supplement)
        encoded=model.encode(row,route,self.keys);logits=self.net(**model.batch([encoded])).flatten()
        probabilities=logits.softmax(0);index=int(probabilities.argmax());goal=(index%route['width'],index//route['width'])
        return dict(goal=goal,probability=float(probabilities[index]),movement=model.goal_guided_move(route,row,goal),
                    unencoded_fields=encoded['unencoded_fields'],goal_kind='replay-inferred approach position')
