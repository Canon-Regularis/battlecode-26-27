"""Independent NumPy inference for exported weights (no Torch dependency).

This is a portable host runtime, not a claim that NumPy exists in the game's
WASI Python sandbox. The eventual sandbox bot still needs a native build and
live personal-SDK encoding. No manual strategic choice is implemented here.
"""
import numpy as np

SPATIAL = (1, 2, 3, 5, 6, 8, 12, 13, 14)


def lse(x, axis=-1, keepdims=False):
    m = x.max(axis=axis, keepdims=True)
    y = m + np.log(np.exp(x - m).sum(axis=axis, keepdims=True))
    return y if keepdims else np.squeeze(y, axis=axis)


def logsoftmax(x):
    return x - lse(x, keepdims=True)


def sigmoid(x):
    return np.exp(-np.logaddexp(np.float32(0), -x))


class PortablePolicy:
    def __init__(self, weights, config, persistent):
        self.w = weights
        self.config = config
        self.persistent = persistent
        self.goals = len(weights['objectives'])

    def linear(self, key, x):
        return x @ self.w[key + '.weight'].T + self.w[key + '.bias']

    def gru(self, key, x):
        n = self.w[key + '.weight_hh_l0'].shape[1]
        h = np.zeros((len(x), n), np.float32)
        for t in range(x.shape[1]):
            i = x[:, t] @ self.w[key + '.weight_ih_l0'].T + self.w[key + '.bias_ih_l0']
            q = h @ self.w[key + '.weight_hh_l0'].T + self.w[key + '.bias_hh_l0']
            ir, iz, inn = np.split(i, 3, -1)
            hr, hz, hn = np.split(q, 3, -1)
            r, z = sigmoid(ir + hr), sigmoid(iz + hz)
            h = (1 - z) * np.tanh(inn + r * hn) + z * h
        return h

    def empty(self, n):
        return dict(belief=np.full((n, self.goals), 1 / self.goals, np.float32),
                    world=np.zeros((n, self.goals, 2), np.float32),
                    known=np.zeros((n, self.goals), bool),
                    age=np.zeros((n, self.goals), np.float32))

    def base_context(self, x, history):
        current = np.maximum(self.linear('execution.current.0', x), 0)
        current = np.maximum(self.linear('execution.current.2', current), 0)
        if self.config['history']:
            h = self.gru('execution.history', history[:, -self.config['history']:])
            return np.maximum(self.linear('execution.combine.0', np.concatenate((current, h), -1)), 0)
        base = np.maximum(self.linear('execution.combine.0', current), 0)
        return np.maximum(self.linear('execution.combine.2', base), 0)

    def begin(self, *, x, history, observations, history_gaps, transition_gap,
              position, position_known, entities, entity_mask, public_tokens,
              public_mask, state):
        initial = transition_gap[:, 2] > .5
        use_past = (~initial) & self.persistent
        old_known = state['known'] & use_past[:, None]
        usable_old = old_known & position_known[:, None]
        old_relative = (state['world'] - position[:, None]) * usable_old[:, :, None]
        old_age = state['age'] * use_past[:, None]
        memory = np.concatenate((old_relative, np.log1p(old_age)[:, :, None] / 8,
                                 usable_old[:, :, None].astype(np.float32)), -1)
        base = self.base_context(x, history)
        encoded = np.tanh(self.linear('observation.0', observations)) * history_gaps[:, :, 1:2]
        h = self.gru('observation_history', np.concatenate((history[:, -16:], encoded, history_gaps), -1))
        entity = self.linear('entity.2', np.tanh(self.linear('entity.0', entities)))
        public = self.linear('public.2', np.tanh(self.linear('public.0', public_tokens)))
        tokens = np.concatenate((entity, public), 1)
        mask = np.concatenate((entity_mask, public_mask), 1)
        mean = (tokens * mask[:, :, None]).sum(1) / mask.sum(1).clip(1)[:, None].astype(np.float32)
        context = base + self.linear('history_projection', h) + self.linear('global_entities', mean)
        inputs = np.concatenate((context, transition_gap), -1)
        proposal = np.exp(logsoftmax(self.linear('proposal.2', np.tanh(self.linear('proposal.0', inputs)))))
        roots = np.expm1(transition_gap[:, 0] * 8)
        remembered = (memory * state['belief'][:, :, None]).sum(1)
        retain = np.exp(-np.logaddexp(0, -self.linear('retention', np.concatenate((inputs, remembered), -1))[:, 0]) * roots) if self.persistent else np.zeros(len(x), np.float32)
        retain = np.where(initial, np.float32(0), retain)
        prior = retain[:, None] * state['belief'] + (1 - retain[:, None]) * proposal
        logprior = logsoftmax(np.log(prior.clip(1e-30)))
        query = self.linear('entity_query', np.concatenate((context[:, None] + self.w['objectives'][None], memory), -1))
        attention = query @ tokens.transpose(0, 2, 1) / np.sqrt(np.float32(32))
        attention = np.exp(logsoftmax(np.where(mask[:, None], attention, np.float32(-1e4))))
        latent = context[:, None] + self.w['objectives'][None] + self.linear('objective_entities', attention @ tokens)
        raw_goal = self.linear('goal_prediction', latent)
        new_world = position[:, None] + raw_goal[:, :, :2] + self.w['initial_offsets'][None]
        new_known = np.broadcast_to(position_known[:, None], old_known.shape)
        blend = np.where(old_known & new_known, retain[:, None], old_known.astype(np.float32))
        world = blend[:, :, None] * state['world'] + (1 - blend[:, :, None]) * new_world
        known = old_known | new_known
        relative = (world - position[:, None]) * position_known[:, None, None]
        logscale = raw_goal[:, :, 2:].clip(-4, 2)
        usable = known & position_known[:, None]
        age = retain[:, None] * (old_age + roots[:, None])
        context = latent + self.linear('goal_condition', np.concatenate((relative, logscale, usable[:, :, None].astype(np.float32)), -1))
        return dict(context=context, logprior=logprior, world=world, known=known,
                    age=age, logscale=logscale, retain=retain)

    def types(self, step):
        return logsoftmax(self.linear('execution.action', step['context']))

    def spatial_log_probs(self, step, grid, valid, rules, family):
        # Unlike the fitter, encode tile features once and broadcast across goals.
        original = grid
        if not self.config['spatial']:
            grid = grid[:, :, [0, 1, 2, 3, 17]]
        elif not self.config['history']:
            grid = grid.copy(); grid[:, :, 18:20] = 0
        candidate = self.linear('execution.candidate.2', np.tanh(self.linear('execution.candidate.0', grid)))
        query = self.linear('execution.query', step['context']) + self.w['execution.family.weight'][family][:, None]
        bias = self.w['execution.offset_bias.weight'][family]
        logits = np.einsum('nks,nts->nkt', query, candidate) / np.float32(5.657) + bias[:, None, :289]
        logits = np.where(valid[:, None], logits, np.float32(-1e4))
        special = self.linear('execution.special', step['context']) + bias[:, None, 289:]
        logits = np.concatenate((logits, special), -1)
        if self.config.get('constrain'):
            allowed = valid.copy()
            move = family == 8
            allowed[move] &= original[move, :, 5] > 0
            for code, slot in ((2, -1), (5, 0), (6, 1)):
                selected = family == code
                if not selected.any():
                    continue
                bits = np.full(selected.sum(), 3, np.int64) if slot < 0 else rules[selected, 3 + slot].astype(np.int64)
                radius = rules[selected, 0] if slot < 0 else rules[selected, 1 + slot]
                units = np.zeros((selected.sum(), 289), bool)
                for bit, col in ((1, 12), (2, 10), (4, 11), (8, 17)):
                    units |= ((bits & bit) != 0)[:, None] & (original[selected, :, col] > 0)
                units |= ((bits & 16) != 0)[:, None]
                allowed[selected] &= units & (original[selected, :, 2] * 8 <= radius[:, None] + 1e-5)
            complete = np.concatenate((allowed, np.zeros((len(allowed), 2), bool)), -1)
            complete[~allowed.any(-1)] = True
            full = logsoftmax(logits)
            restricted = logsoftmax(np.where(complete[:, None], logits, np.float32(-1e4)))
            logits = np.logaddexp(restricted + np.log(np.float32(.9999)), full + np.log(np.float32(.0001)))
        return logsoftmax(logits)

    def observed(self, step, grid, valid, rules, y, py, priority_parameter_nll):
        typ = self.types(step)
        component = typ[np.arange(len(y)), :, y].copy()
        for family in SPATIAL:
            rows = y == family
            if rows.any():
                sub = {k: v[rows] for k, v in step.items()}
                lp = self.spatial_log_probs(sub, grid[rows], valid[rows], rules[rows], y[rows])
                component[rows] += lp[np.arange(rows.sum()), :, py[rows]]
        rows = y == 9
        component[rows] -= priority_parameter_nll[rows, None]
        joint = step['logprior'] + component
        return -lse(joint), dict(belief=np.exp(logsoftmax(joint)), world=step['world'],
                                known=step['known'], age=step['age'])

    def decode(self, step, grid, valid, rules, priority_mode, priority_mode_logp):
        typ = self.types(step)
        marginal = lse(step['logprior'][:, :, None] + typ, axis=1)
        n = len(typ); coordinates = np.full((n, 15), -1, np.int64)
        scores = marginal.copy(); parameters = {}
        for family in SPATIAL:
            lp = self.spatial_log_probs(step, grid, valid, rules, np.full(n, family, np.int64))
            joint = lse(step['logprior'][:, :, None] + typ[:, :, family, None] + lp, axis=1)
            coordinates[:, family] = joint.argmax(-1)
            scores[:, family] = joint.max(-1)
            parameters[family] = joint - marginal[:, family, None]
        scores[:, 9] += priority_mode_logp
        prediction = scores.argmax(-1)
        return dict(prediction=prediction, coordinate=coordinates[np.arange(n), prediction],
                    priority=priority_mode, type_logp=marginal,
                    parameter_logp=parameters, goal_prior=np.exp(step['logprior']),
                    goal_world=step['world'], goal_known=step['known'], retention=step['retain'])
