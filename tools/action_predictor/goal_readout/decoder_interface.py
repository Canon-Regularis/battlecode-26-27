"""Adapt unused GoalPolicy diagnostic outputs without changing command math."""
from .model import FrozenGoalReadout
from ..learned_policy.model import GoalPolicy


class ReadoutDecoderInterface(FrozenGoalReadout):
    def decode(self, step, **kwargs):
        # The readout cache intentionally stores only causal execution inputs.
        # These fields are returned, but never read in GoalPolicy.decode's
        # probability/MAP calculation. Explicit None means not supplied here;
        # it must not be interpreted as a forecast of world/known/retention.
        diagnostic_step = dict(step, world=None, known=None, retain=None)
        return GoalPolicy.decode(self, diagnostic_step, **kwargs)
