"""Causal GRU plus inference API. Reset hidden state at each sampled turn."""
import torch
from torch import nn

from .data import features


class ActionGRU(nn.Module):
    def __init__(self, inputs, classes, hidden=96):
        super().__init__()
        self.encoder = nn.Sequential(nn.Linear(inputs, hidden), nn.ReLU())
        self.previous = nn.Embedding(classes + 1, 16)  # final entry is START
        self.gru = nn.GRU(hidden + 16, hidden, batch_first=True)
        self.head = nn.Linear(hidden, classes)

    def forward(self, x, previous, hidden=None):
        output, hidden = self.states(x, previous, hidden)
        return self.head(output), hidden

    def states(self, x, previous, hidden=None):
        encoded = torch.cat((self.encoder(x), self.previous(previous)), dim=-1)
        output, hidden = self.gru(encoded, hidden)
        return output, hidden


class ActionMLP(nn.Module):
    """Comparable parameter count to V1, with no history or prior-action input."""
    def __init__(self, inputs, classes):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(inputs, 192), nn.ReLU(), nn.Linear(192, 192),
                                 nn.ReLU(), nn.Linear(192, classes))

    def forward(self, x, previous=None):
        return self.net(x), None


class CoordinateHead(nn.Module):
    """Score PRE-only spatial candidates, conditional on recorded action family."""
    def __init__(self, inputs):
        super().__init__()
        self.query = nn.Sequential(nn.Linear(inputs, 64), nn.ReLU(), nn.Linear(64, 64))
        self.family = nn.Embedding(4, 64)
        self.candidate = nn.Sequential(nn.Linear(10, 64), nn.Tanh(), nn.Linear(64, 64))

    def forward(self, context, family, grid, mask):
        query = self.query(context) + self.family(family)
        logits = (self.candidate(grid) * query[:, None, :]).sum(-1) / 8
        return logits.masked_fill(~mask, -1e9)


class Predictor:
    def __init__(self, checkpoint):
        saved = torch.load(checkpoint, map_location='cpu', weights_only=True)
        self.labels = saved['labels']
        self.mean, self.std = saved['mean'], saved['std']
        self.model = ActionGRU(len(self.mean), len(self.labels), saved['hidden'])
        self.model.load_state_dict(saved['state_dict'])
        self.model.eval()
        self.reset()

    def reset(self):
        self.hidden = None
        self.previous = len(self.labels)

    @torch.no_grad()
    def predict(self, observation, previous_action=None):
        """Call once per decision, with the last actually observed action type."""
        if previous_action is not None:
            self.previous = self.labels.index(previous_action) if previous_action in self.labels else 0
        elif self.hidden is not None:
            raise ValueError('Supply the previous observed action or reset for a new turn')
        x, _ = features(observation)
        x = (torch.from_numpy(x) - self.mean) / self.std
        logits, self.hidden = self.model(x[None, None], torch.tensor([[self.previous]]), self.hidden)
        probs = logits[0, 0].softmax(-1).tolist()
        return dict(sorted(zip(self.labels, probs), key=lambda pair: -pair[1]))


class StructuredPredictor(Predictor):
    """Frozen action GRU with a learned conditional coordinate head.

    Forecasts recorded destinations/aim cells; does not claim legal commands or
    recover original target IDs. Call reset at every turn as with Predictor.
    """
    def __init__(self, baseline, target_checkpoint):
        super().__init__(baseline)
        saved = torch.load(target_checkpoint, map_location='cpu', weights_only=True)
        from .data import digest
        if saved['baseline_checkpoint_sha256'] != digest(baseline):
            raise ValueError('Target head was trained with a different baseline GRU')
        self.supported_families = saved['supported_families']
        self.target = CoordinateHead(self.model.gru.hidden_size)
        self.target.load_state_dict(saved['state_dict'])
        self.target.eval()

    @torch.no_grad()
    def predict(self, observation, width, height, previous_action=None, family=None):
        from .targets import FAMILIES, OFFSETS, spatial_candidates
        actions = super().predict(observation, previous_action)
        family = family or next(iter(actions))
        result = dict(actions=actions, conditional_family=family, targets=[])
        if family not in self.supported_families:
            return result
        grid, mask, occupants = spatial_candidates(observation, family, width, height)
        if not mask.any():
            return result
        logits = self.target(self.hidden[-1], torch.tensor([FAMILIES.index(family)]),
                             torch.from_numpy(grid)[None], torch.from_numpy(mask)[None])
        probabilities = logits[0].softmax(-1)
        pos = observation['own']['position']
        for i in probabilities.argsort(descending=True)[:min(5, int(mask.sum()))].tolist():
            entities = occupants.get(i, [])
            result['targets'].append(dict(position={'x': pos['x']+int(OFFSETS[i, 0]), 'y': pos['y']+int(OFFSETS[i, 1])},
                                          probability=float(probabilities[i]),
                                          unique_visible_occupant=entities[0] if len(entities) == 1 else None))
        return result
