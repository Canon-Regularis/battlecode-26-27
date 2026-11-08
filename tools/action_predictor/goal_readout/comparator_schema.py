"""Separate chosen-command archives from true-family parameter diagnostics."""
import numpy as np
from ..learned_policy.model import SPATIAL
from ..observation_metrics import correctness


def conditional_reference(raw, prediction):
    if 'family_commands' not in prediction:
        return prediction
    result = dict(prediction)
    family = prediction['family_commands']
    assert family.shape == (len(raw['y']), 15, 3)
    rows = np.arange(len(raw['y']))
    result['coordinate'] = family[rows, raw['y'], 1]
    result['priority'] = family[:, 9, 2]
    typed = prediction['prediction'] == raw['y']
    spatial = typed & np.isin(raw['y'], SPATIAL)
    np.testing.assert_array_equal(result['coordinate'][spatial], prediction['coordinate'][spatial])
    priority = typed & (raw['y'] == 9)
    np.testing.assert_array_equal(result['priority'][priority], prediction['priority'][priority])
    # Reconstructing diagnostics must preserve actual complete-command scores.
    np.testing.assert_array_equal(correctness(raw, result)[1], correctness(raw, prediction)[1])
    return result
