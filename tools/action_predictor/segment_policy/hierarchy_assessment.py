"""Same command assessment, corrected previous-transition hazard diagnostics."""
import numpy as np
from .assessment import assess as preserved_assess


def assess(arm, data, forecasts):
    # Skip the original prospective hazard summary, retaining command metrics.
    view = {split: {k: v for k, v in p.items() if k != 'expected_age'} for split, p in forecasts.items()}
    results, comparisons = preserved_assess(arm, data, view)
    for split, p in forecasts.items():
        nonreset = np.asarray(p['reset']) == 0
        memory = results[split]['memory']
        memory.update(mean_current_state_conditional_age=p['expected_age'].mean(0).tolist(),
            assessed_consecutive_transitions=int(nonreset.sum()),
            mean_transition_exit_probability=float(p['transition_exit_probability'][nonreset].mean()) if nonreset.any() else None,
            mean_previous_state_conditional_hazard=[float(v[np.isfinite(v)].mean()) if np.isfinite(v).any() else None
                for v in np.asarray(p['previous_state_hazard'])[nonreset].T],
            mean_previous_state_exit_mass=p['state_exit_mass'][nonreset].mean(0).tolist() if nonreset.any() else None,
            diagnostic_timepoint='Previous posterior weighted by hazards applied to this transition; reset boundaries are unassessed NaN. Current expected age describes a different, explicitly labeled current prior.')
    return results, comparisons
