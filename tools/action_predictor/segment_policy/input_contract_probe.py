"""No-update probe of prior-command information in the two architectures."""
import torch
from ..audit import immutable_json
from ..data import digest
from .test_model import fixture
from .data import REPORT


@torch.no_grad()
def run():
    results = {}
    for hierarchy in (False, True):
        model, inputs, geo, target = fixture(hierarchy)
        model.eval()
        first = model.begin(**inputs, state=model.empty(3))
        target.update(y=torch.full((3,), 9, dtype=torch.long), py=torch.full((3,), -1, dtype=torch.long))
        target['priority_value'] = torch.tensor([0, 100, 200])
        _, a = model.observed(first, **geo, **target)
        target['priority_value'] = torch.tensor([1000, -1000, 900])
        # A different fixed integer likelihood is constant across latent states.
        target['priority_parameter_nll'] += 2
        _, b = model.observed(first, **geo, **target)
        inputs['transition_gap'][:, 2] = 0
        sa = model.begin(**inputs, state=a)
        sb = model.begin(**inputs, state=b)
        results['hierarchy' if hierarchy else 'direct'] = dict(
            max_next_type_probability_difference=float((model.types(sa).exp()-model.types(sb).exp()).abs().max()),
            max_next_state_prior_difference=float((sa['logprior'].exp()-sb['logprior'].exp()).abs().max()))
    immutable_json(REPORT/'prior-command-information-probe.json', dict(
        results=results, source_sha256=digest(__file__),
        model_sha256=digest(__file__.replace('input_contract_probe.py', 'model.py')),
        finding='Direct recurrence explicitly encodes earlier integer values. In the original H01 prototype, the fixed integer likelihood is common to states and cancels from the Bayes posterior; its separate priority_value argument is unused. Both use causal evidence, but the effective prior-integer interface differs.',
        consequence='H00 remains a valid direct policy fit. Resolve or explicitly control this effective-input difference BEFORE treating H01-minus-H00 as a matched duration-structure result. H01 is unrun. No current fit or frozen artifact is silently changed.',
        limits='Synthetic no-update mechanism test, not a measured contribution to Fish movement errors. It does not justify blaming priority information or abandoning the movement study.',
        new_fits=0, optimizer_updates=0, reserved_opened=0))


if __name__ == '__main__': run()
