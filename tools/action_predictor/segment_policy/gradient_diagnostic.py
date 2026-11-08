"""Read-only pre-clipping gradient scales; never modifies optimization."""
import torch


def gradient_summary(model, update, epoch):
    modules = dict(transitions=model.filter.transition, hazards=model.filter.termination,
        conditioning=model.condition, action=model.execution.action, current=model.execution.current,
        spatial_candidate=model.execution.candidate, spatial_query=model.execution.query)
    values = {k: [p.grad for p in m.parameters() if p.grad is not None] for k, m in modules.items()}
    values['duration_age'] = [model.filter.age_logits.grad]
    transition = model.filter.transition.weight.grad
    hazard = model.filter.termination.weight.grad
    values['transition_command_columns'] = [transition[:, 128:]] if transition is not None else []
    values['hazard_command_columns'] = [hazard[:, 128:]] if hazard is not None else []
    result = {}
    for name, arrays in values.items():
        parts = [a.detach().double().reshape(-1) for a in arrays if a is not None]
        vector = torch.cat(parts) if parts else torch.zeros(0, dtype=torch.float64)
        finite = bool(torch.isfinite(vector).all())
        result[name] = dict(scalars=len(vector), nonzero=int(torch.count_nonzero(vector)),
            finite=finite, L2=float(vector.norm()) if finite else None,
            max_absolute=float(vector.abs().max()) if len(vector) and finite else None)
    return dict(update=update, round=epoch, pre_clipping=True, gradients=result,
        interpretation='Observed current training gradient scales, not realized Adam update influence or proof that a component learned useful behavior.')
