"""Independent existing-P05 integer distribution, not a new priority strategy."""
import numpy as np
from .portable import PortablePolicy, logsoftmax


class PortablePriority(PortablePolicy):
    def __init__(self, weights, config):
        self.w = weights
        self.config = config

    def raw(self, x, history, values, priority_history):
        if values.dtype != np.int64 or priority_history.dtype != np.int64:
            raise ValueError('Priority evidence must retain exact integers')
        features = np.concatenate((values, priority_history.reshape(len(values), -1)), -1).astype(np.float32)
        features = (features - self.w['extra_mean']) / self.w['extra_std']
        context = self.base_context(x, history)
        return self.linear('priority', np.concatenate((context, features), -1))

    def components(self, raw, values):
        if values.dtype != np.int64 or values.shape != (len(raw), 7):
            raise ValueError('Exact causal priority evidence required')
        if not np.isin(values[:, 5], [0, 1]).all():
            raise ValueError('Invalid last-priority availability')
        if (values[values[:, 5] == 0, 4] != 0).any():
            raise ValueError('Unavailable last priority must be masked')
        anchor = -values[:, 4]
        if not ((values[:, 4] >= -(2**31)) & (values[:, 4] < 2**31)).all():
            raise ValueError('Historical input priority outside signed int32')
        absolute, residual = self.w['absolute'], self.w['residual']
        points = np.concatenate((np.broadcast_to(absolute, (len(raw), len(absolute))),
                                 anchor[:, None] + residual[None]), -1)
        logits = raw[:, :-2].astype(np.float64).copy()
        logits[:, len(absolute):-1] = np.where(values[:, 5:6] == 0, -np.inf,
                                              logits[:, len(absolute):-1])
        return points, logsoftmax(logits)

    @staticmethod
    def logistic_mass(raw, target):
        raw = raw.astype(np.float64); target = target.astype(np.float64)
        mean = raw[..., 0]; scale = np.exp(raw[..., 1].clip(-6, 5))
        while mean.ndim < target.ndim:
            mean = mean[..., None]; scale = scale[..., None]
        hi = (target / 100 + .005 - mean) / scale
        lo = (target / 100 - .005 - mean) / scale
        return -np.logaddexp(0, -hi) - np.logaddexp(0, lo) + np.log(-np.expm1(-.01 / scale))

    def log_mass(self, raw, target, values):
        if target.dtype != np.int64 or target.shape != (len(raw),):
            raise ValueError('One exact integer target per distribution')
        points, mix = self.components(raw, values)
        mass = np.logaddexp.reduce(np.where(points == target[:, None], mix[:, :-1], -np.inf), -1)
        return np.logaddexp(mass, mix[:, -1] + self.logistic_mass(raw[:, -2:], target))

    def modes(self, raw, values):
        points, mix = self.components(raw, values)
        modes, logps = [], []
        for i in range(len(raw)):
            center = float(raw[i, -2]) * 100
            if not np.isfinite(center) or abs(center) >= 2**62:
                raise ValueError('Invalid logistic center')
            candidates = np.r_[points[i], int(np.floor(center)), int(np.ceil(center))]
            unique, inverse = np.unique(candidates, return_inverse=True)
            mass = np.full(len(unique), -np.inf, np.float64)
            np.logaddexp.at(mass, inverse[:-2], mix[i, :-1])
            mass = np.logaddexp(mass, mix[i, -1] + self.logistic_mass(raw[i, -2:], unique))
            winner = int(mass.argmax())  # unique is sorted, matching P05 ties.
            modes.append(int(unique[winner])); logps.append(float(mass[winner]))
        return np.asarray(modes, np.int64), np.asarray(logps, np.float64)
