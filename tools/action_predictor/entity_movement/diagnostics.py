"""Read-only gradient accounting for the new execution path."""
import torch
from ..segment_policy.gradient_diagnostic import gradient_summary as inherited_summary


def gradient_summary(model, update, epoch):
    result = inherited_summary(model, update, epoch)
    for name in ('entity_query', 'destination_query', 'entity_key', 'entity_value', 'movement_readout'):
        parts = [p.grad.detach().double().flatten() for p in getattr(model, name).parameters() if p.grad is not None]
        vector = torch.cat(parts) if parts else torch.zeros(0, dtype=torch.float64)
        finite = bool(torch.isfinite(vector).all())
        result['gradients'][name] = dict(scalars=len(vector), nonzero=int(torch.count_nonzero(vector)),
            finite=finite, L2=float(vector.norm()) if finite else None)
    return result
