"""Common causal upstream cache; labels read only after each PRE is saved."""
import json
import subprocess
import numpy as np
import torch
from .protocol import ROOT, LOCAL, OUT, V16, V16_REPORT, freeze
from ..learned_policy.pathway_reference import load_model, command_targets
from ..learned_policy.pathway_inputs import features
from ..learned_policy.data import load, chunks, causal_inputs, geometry
from ..learned_policy.inference import select_state
from ..learned_policy.retention_gradients import fingerprint
from ..audit import immutable_json
from ..data import digest


@torch.no_grad()
def run():
    freeze()
    torch.set_num_threads(4)
    model, saved, checkpoint = load_model('L02')
    before = fingerprint(model)
    captured = {}
    def capture(module, args):
        captured['latent'] = args[0].detach()
    hook = model.goal_prediction.register_forward_pre_hook(capture)
    results = {}
    for split in ('train', 'validation'):
        directory = LOCAL / f'upstream/{split}'
        assert not directory.exists(), 'Preserve attempted cache'
        directory.mkdir(parents=True)
        d = load(split, saved)
        n = len(d['raw']['y'])
        shapes = {'latent': (n, 4, 128), 'features': (n, 4, 5), 'logprior': (n, 4), 'position_known': (n,)}
        banks = {key: np.lib.format.open_memmap(directory / f'{key}.npy', mode='w+',
                 dtype=np.bool_ if key == 'position_known' else np.float32, shape=shape)
                 for key, shape in shapes.items()}
        state = model.empty(32)
        seen = np.zeros(n, np.uint8)
        with np.load(V16 / f'runs/L02/{split}-goals.npz') as z:
            oldworld, oldretain = z['world'], z['retention']
        context_difference = world_difference = retain_difference = 0.
        for rows in chunks(d['sequences']):
            for ids in rows:
                valid = ids >= 0
                ix = np.maximum(ids, 0)
                inputs = causal_inputs(d, ix)
                step = model.begin(**inputs, state=state)
                f = features(step, inputs)
                latent = captured['latent']
                context_difference = max(context_difference, float((latent + model.goal_condition(f) - step['context']).abs().max()))
                if valid.any():
                    for key, value in dict(latent=latent, features=f, logprior=step['logprior'],
                                           position_known=inputs['position_known']).items():
                        banks[key][ids[valid]] = value.numpy()[valid]
                    world_difference = max(world_difference, float(np.abs(step['world'].numpy()[valid] - oldworld[ids[valid]]).max()))
                    retain_difference = max(retain_difference, float(np.abs(step['retain'].numpy()[valid] - oldretain[ids[valid]]).max()))
                # Only now read the current recorded action to update the frozen
                # baseline filter for subsequent PREs. No trained readout involved.
                target = command_targets(d, ix)
                _, post = model.observed(step, **geometry(d, ix), **target)
                state = select_state(state, post, torch.from_numpy(valid))
                seen[ids[valid]] += 1
        assert np.all(seen == 1)
        assert context_difference == world_difference == retain_difference == 0
        files = {}
        for key, bank in banks.items():
            bank.flush()
            files[key] = digest(directory / f'{key}.npy')
        results[split] = dict(rows=n, files=files, context_reconstruction_max_difference=context_difference,
                              original_world_max_difference=world_difference,
                              original_retention_max_difference=retain_difference)
        print('Common frozen upstream ready', split, n, flush=True)
        del d, banks, oldworld, oldretain
    hook.remove()
    assert fingerprint(model) == before
    immutable_json(OUT / 'upstream-ready.json', dict(results=results,
        checkpoint_sha256=digest(checkpoint), protocol_sha256=digest(OUT / 'protocol.json'),
        source_commit=subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip(),
        source_sha256=digest(__file__), input_receipt_sha256=digest(V16_REPORT / 'policy-input-bindings.json'),
        weights_unchanged=True, new_fits=0, reserved_opened=0))


if __name__ == '__main__':
    run()
