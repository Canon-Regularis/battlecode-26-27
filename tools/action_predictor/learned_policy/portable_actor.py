"""Executing learned-policy core without Torch; SDK and PRE encoder injected.

The live SDK observation bridge and sandbox integration are deliberately not
replaced by a replay reader. This actor can dispatch real SDK calls when those
capabilities are supplied, but this research invokes only read-only parity and
call-recording checks. It implements no hand-designed objective or fallback.
"""
import json
from pathlib import Path
import numpy as np
from .portable import PortablePolicy
from .portable_priority import PortablePriority
from .execution import Command


class PortableActor:
    def __init__(self, policy, priority, labels, actor_key):
        expected = ['<unknown>', 'altar', 'attack', 'blocked', 'cancel', 'cast_0',
                    'cast_1', 'end', 'move', 'priority', 'recall', 'shop',
                    'submit', 'teleport', 'ward']
        if list(labels) != expected:
            raise ValueError('Frozen command-family order mismatch')
        self.policy = policy; self.priority = priority; self.labels = labels
        self.actor_key = actor_key; self.state = policy.empty(1); self.pending = None

    @classmethod
    def load(cls, policy_directory, priority_directory, actor_key):
        # The caller verifies the immutable export manifest before starting.
        pd, qd = Path(policy_directory), Path(priority_directory)
        p = json.loads((pd / 'policy.json').read_text())
        q = json.loads((qd / 'priority.json').read_text())
        import hashlib
        for path, expected in ((pd / 'policy.npz', p['weights_sha256']),
                               (qd / 'priority.npz', q['weights_sha256'])):
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise ValueError('Exported policy weights changed')
        with np.load(pd / 'policy.npz') as z: pw = {k:z[k] for k in z.files}
        with np.load(qd / 'priority.npz') as z: qw = {k:z[k] for k in z.files}
        if p['mean'] != q['mean'] or p['std'] != q['std']:
            raise ValueError('Policy/priority PRE normalization mismatch')
        return cls(PortablePolicy(pw, p['config'], p['persistent']),
                   PortablePriority(qw, q['config']), p['labels'], actor_key)

    def decide(self, inputs, geometry, priority_values, priority_history, *, actor_key):
        if actor_key != self.actor_key:
            raise ValueError('Different personal game/actor; identity is never a feature')
        if self.pending is not None:
            raise RuntimeError('Previous proposal must execute or be rejected first')
        if len(inputs['x']) != 1:
            raise ValueError('One actor per stateful controller')
        values = priority_values.copy()
        raw = self.priority.raw(inputs['x'], inputs['history'], values, priority_history)
        mode, mode_lp = self.priority.modes(raw, values)
        step = self.policy.begin(**inputs, state=self.state)
        prediction = self.policy.decode(step, **geometry, priority_mode=mode,
                                        priority_mode_logp=mode_lp)
        family = int(prediction['prediction'][0]); coordinate = int(prediction['coordinate'][0])
        position = None
        if 0 <= coordinate < 289 and bool(inputs['position_known'][0]):
            origin = np.rint(inputs['position'][0] * 32).astype(np.int64)
            position = (int(origin[0] + coordinate % 17 - 8),
                        int(origin[1] + coordinate // 17 - 8))
        command = Command(self.labels[family], position=position,
                          priority=int(mode[0]) if family == 9 else None)
        self.pending = dict(step=step, geometry=geometry, command=command,
                            coordinate=coordinate, priority_raw=raw,
                            priority_values=values)
        return command

    def commit(self, execution):
        if self.pending is None or execution.requested != self.pending['command']:
            raise ValueError('No matching actual execution')
        family = self.labels.index(execution.actual_action)
        priority_nll = np.zeros(1, np.float64)
        if family == 9:
            priority_nll = -self.priority.log_mass(
                self.pending['priority_raw'],
                np.array([execution.requested.priority], np.int64),
                self.pending['priority_values'])
        _, state = self.policy.observed(
            self.pending['step'], **self.pending['geometry'],
            y=np.array([family], np.int64),
            py=np.array([self.pending['coordinate']], np.int64),
            priority_parameter_nll=priority_nll)
        self.state = state; self.pending = None

    def reject(self):
        self.pending = None

    def act(self, inputs, geometry, priority_values, priority_history,
            executor, compatible_targets=(), *, actor_key):
        command = self.decide(inputs, geometry, priority_values, priority_history,
                              actor_key=actor_key)
        try:
            execution = executor.execute(command, compatible_targets)
        except Exception:
            self.reject(); raise
        self.commit(execution)
        return execution
