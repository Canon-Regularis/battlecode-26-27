"""Personal observation/action adapter shared by replay checks and host execution.

No recorded current answer, future waypoint, sampled row number, or game ID is
an input. Call observe only after an own action has actually happened. Mark a
policy action only after its execution; other observed own roots remain gaps.
"""
import copy
import math
import numpy as np
import torch
from ..audit import cursor
from ..observation_data import compact_supplement, encode, safe_observation
from ..observation_predictor import label_for
from ..entity_set import encode_entities
from . import public_inputs


class PersonalInputs:
    def __init__(self, frozen_priority, actor):
        self.priority = frozen_priority
        self.actor = actor
        self.frames = []
        self.roots = 0
        self.last_policy_ordinal = None
        self.last_policy_round = None
        self.intervening = np.zeros(15, np.int64)

    def observe(self, event, pre, step, round_number, own_turn,
                observation=None, supplement=None, route=None):
        if step['actor'] != dict(kind=1, index=self.actor):
            raise ValueError('Different personal actor')
        if cursor(pre) >= cursor(event):
            raise ValueError('PRE must precede the observed action')
        if self.frames and cursor(event) <= self.frames[-1]['at']:
            raise ValueError('Actions must be assimilated in order, once')
        vector = None
        if observation is not None:
            s = compact_supplement(supplement)
            if s['pre'] != pre:
                raise ValueError('Historical PRE mismatch')
            safe_observation(observation, self.actor, observation['own']['team'], s)
            vector = encode(observation, s, route, round_number).copy()
        family = label_for(step, self.priority.labels)
        self.priority.observe(event, copy.deepcopy(step), round_number)
        self.frames.append(dict(at=cursor(event), ordinal=self.roots,
                                round=round_number, turn=own_turn,
                                observation=vector))
        self.frames = self.frames[-16:]
        self.intervening[family] += 1
        self.roots += 1

    def mark_policy_action(self, event):
        """This already-observed root was the policy's most recent decision."""
        if not self.frames or self.frames[-1]['at'] != cursor(event):
            raise ValueError('Mark only the most recently executed own action')
        f = self.frames[-1]
        self.last_policy_ordinal = f['ordinal']
        self.last_policy_round = f['round']
        self.intervening[:] = 0

    @torch.no_grad()
    def prepare(self, observation, supplement, route, round_number, own_turn,
                pre, priority_state):
        s = compact_supplement(supplement)
        if self.frames and self.frames[-1]['at'] > cursor(pre):
            raise ValueError('Future own action cannot enter prediction')
        raw = self.priority.inputs(observation, s, route, round_number, pre,
                                   priority_state)
        previous = self.frames[-16:]
        obs = np.zeros((16, 253), np.float32)
        gaps = np.zeros((16, 5), np.float32)
        for j, f in enumerate(previous):
            i = 16 - len(previous) + j
            following = previous[j + 1] if j + 1 < len(previous) else dict(
                round=round_number, turn=own_turn)
            elapsed = following['round'] - f['round']
            age = round_number - f['round']
            if min(elapsed, age) < 0:
                raise ValueError('Personal time went backwards')
            if f['observation'] is not None:
                obs[i] = f['observation']
            gaps[i] = [1, float(f['observation'] is not None),
                       min(elapsed, 100) / 100,
                       float(following['turn'] != f['turn']),
                       min(age, 100) / 100]
        initial = self.last_policy_ordinal is None
        delta = self.roots + 1 if initial else self.roots - self.last_policy_ordinal
        elapsed = 0 if initial else round_number - self.last_policy_round
        transition = np.r_[math.log1p(delta) / 8,
                           math.log1p(elapsed) / 8, int(initial),
                           np.log1p(self.intervening) / 8].astype(np.float32)
        pos = observation['own'].get('position')
        known = np.array([pos is not None], bool)
        position = np.array([[pos['x'] / 32, pos['y'] / 32] if pos else [0, 0]],
                            np.float32)
        points, kinds = [], []
        for a in route['altars']:
            points.append([a['x'] / 32, a['y'] / 32]); kinds.append(0)
        for side in (0, 1):
            r = route['spawns'][side]
            for y in range(r['minY'], r['maxY']):
                for x in range(r['minX'], r['maxX']):
                    points.append([x / 32, y / 32])
                    kinds.append(1 if side == observation['own']['team'] else 2)
        public, public_mask = public_inputs.batch(
            dict(starts=[0], world=[points], kind=[kinds]), [0], position, known)
        entities = encode_entities(observation).astype(np.float32)
        inputs = dict(x=raw['x'], history=raw['history'],
                      observations=((torch.from_numpy(obs) - self.priority.mean)
                                    / self.priority.std)[None],
                      history_gaps=torch.from_numpy(gaps)[None],
                      transition_gap=torch.from_numpy(transition)[None],
                      position=torch.from_numpy(position),
                      position_known=torch.from_numpy(known),
                      entities=torch.from_numpy(entities)[None],
                      entity_mask=torch.ones((1, len(entities)), dtype=torch.bool),
                      public_tokens=public, public_mask=public_mask)
        _, context = self.priority.model(raw['x'], raw['history'])
        priority_raw = self.priority.head(context, raw['extra'])
        values = raw['priority_values'].clone()
        mode = self.priority.head.integer(priority_raw, values)
        mode_lp = self.priority.head.log_mass(priority_raw, mode, values)
        # Capture this PRE distribution, never query later state for its mass.
        def log_mass(value):
            return float(self.priority.head.log_mass(
                priority_raw, torch.tensor([value], dtype=torch.int64), values)[0])
        geometry = {key: raw[key] for key in ('grid', 'valid', 'rules')}
        return dict(inputs=inputs, geometry=geometry, priority_mode=mode,
                    priority_mode_logp=mode_lp, priority_log_mass=log_mass)
