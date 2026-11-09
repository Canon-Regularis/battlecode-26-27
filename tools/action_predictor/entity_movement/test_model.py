import copy
import unittest
import torch
from ..segment_policy.test_model import fixture
from ..segment_policy.history_model import HistorySegmentPolicy
from .model import EntityMovementPolicy


def models():
    old, inputs, geo, target = fixture(True)
    torch.manual_seed(31)
    control = EntityMovementPolicy(old.execution, False)
    torch.manual_seed(31)
    treatment = EntityMovementPolicy(old.execution, True)
    return control, treatment, inputs, geo, target


class EntityMovementContracts(unittest.TestCase):
    def test_matching_and_initial_executor_parity(self):
        a, b, inputs, geo, target = models()
        for key, value in a.state_dict().items():
            torch.testing.assert_close(value, b.state_dict()[key], rtol=0, atol=0)
        for model in (a, b):
            step = model.begin(**inputs, state=model.empty(3))
            for family in (1, 2, 5, 6, 8, 12, 13, 14):
                codes = torch.full((3,), family)
                actual = model.spatial_log_probs(step, **geo, family=codes)
                old = HistorySegmentPolicy.spatial_log_probs(model, step, **geo, family=codes)
                torch.testing.assert_close(actual, old, rtol=0, atol=2e-6)

    def test_masks_permutation_and_empty_entities(self):
        _, model, inputs, geo, _ = models()
        with torch.no_grad(): model.movement_readout[-1].weight.fill_(.1)
        inputs['entity_mask'][0] = False
        inputs['entity_mask'][1, 2:] = False
        def forecast(values):
            step = model.begin(**values, state=model.empty(3))
            return model.spatial_log_probs(step, **geo, family=torch.full((3,), 8))
        expected = forecast(inputs)
        modified = copy.deepcopy(inputs)
        modified['entities'][~inputs['entity_mask']] = 900
        torch.testing.assert_close(forecast(modified), expected, rtol=0, atol=0)
        perm = torch.tensor([3, 1, 0, 2])
        modified['entities'] = modified['entities'][:, perm]
        modified['entity_mask'] = modified['entity_mask'][:, perm]
        torch.testing.assert_close(forecast(modified), expected, rtol=0, atol=2e-6)
        self.assertTrue(bool(torch.isfinite(expected).all()))
        inputs['entities'] = inputs['entities'][:, :0]
        inputs['entity_mask'] = inputs['entity_mask'][:, :0]
        self.assertTrue(bool(torch.isfinite(forecast(inputs)).all()))

    def test_attention_changes_destination_distribution_and_has_gradients(self):
        a, b, inputs, geo, _ = models()
        with torch.no_grad():
            a.movement_readout[-1].weight.normal_(0, .2)
        b.load_state_dict(a.state_dict())
        outputs = []
        for model in (a, b):
            step = model.begin(**inputs, state=model.empty(3))
            lp = model.spatial_log_probs(step, **geo, family=torch.full((3,), 8))
            outputs.append(lp)
            (-lp[:, :, 144].mean()).backward()
            for name in ('entity_query.weight', 'destination_query.weight', 'entity_key.weight',
                         'entity_value.weight', 'movement_readout.0.weight', 'execution.candidate.0.weight'):
                gradient = dict(model.named_parameters())[name].grad
                self.assertTrue(bool(torch.isfinite(gradient).all()), name)
                self.assertGreater(float(gradient.norm()), 1e-10, name)
        self.assertGreater(float((outputs[0] - outputs[1]).abs().max().detach()), 1e-7)

    def test_likelihood_decoder_and_history_contract(self):
        _, model, inputs, geo, target = models()
        with torch.no_grad(): model.movement_readout[-1].weight.normal_(0, .1)
        state = model.empty(3)
        for t in range(3):
            inputs['transition_gap'][:, 2] = int(t == 0)
            step = model.begin(**inputs, state=state)
            p = model.decode(step, **geo, priority_mode=target['priority_value'],
                             priority_mode_logp=torch.full((3,), -4., dtype=torch.float64))
            loss, state = model.observed(step, **geo, **target)
            for family, lp in p['parameter_logp'].items():
                torch.testing.assert_close(lp.exp().sum(-1), torch.ones(3).double(), rtol=0, atol=2e-12)
            observed = p['type_logp'][0, 8] + p['parameter_logp'][8][0, 144]
            torch.testing.assert_close(observed, -loss[0], rtol=0, atol=2e-12)
            self.assertTrue(bool((-loss <= p['family_mode_logp'].max(-1).values + 1e-12).all()))
        inputs['transition_gap'][:, 2] = 1
        a = model.begin(**inputs, state=state)
        b = model.begin(**inputs, state=model.empty(3))
        torch.testing.assert_close(a['context'], b['context'], rtol=0, atol=0)
        torch.testing.assert_close(a['logprior'], b['logprior'], rtol=0, atol=0)
        with self.assertRaises(TypeError): model.begin(**inputs, state=state, current_command=target)


if __name__ == '__main__': unittest.main()
