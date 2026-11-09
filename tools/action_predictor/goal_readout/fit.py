"""One matched frozen-upstream readout fit; every round retained."""
import argparse
import json
import subprocess
import time
import numpy as np
import torch
from .protocol import ROOT, LOCAL, OUT, SEED, ARMS, freeze
from .model import FrozenGoalReadout
from .data import load, inputs, geometry, targets, geometry_reference
from .inference import infer
from ..learned_policy.pathway_reference import load_model
from ..learned_policy.data import chunks
from ..audit import immutable_json
from ..data import digest
from .. import reliable_train as rt


def run(identifier):
    freeze()
    rt.setup(SEED)
    directory = LOCAL / f'runs/{identifier}'
    assert not directory.exists(), 'Preserve attempted fit'
    directory.mkdir(parents=True)
    upstream, _, checkpoint = load_model('L02')
    model = FrozenGoalReadout(upstream, geometry_reference(), ARMS[identifier])
    initial = {key: value.detach().clone() for key, value in model.state_dict().items()}
    torch.save(initial, directory / 'initial-state.pt')
    d = {split: load(split) for split in ('train', 'validation')}
    trainable = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(trainable, lr=.0003, weight_decay=.01)
    rng = np.random.default_rng(SEED)
    trace, best, selected, updates = [], float('inf'), 0, 0
    commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    tick = time.perf_counter()
    for epoch in range(1, 36):
        model.train()
        seen = np.zeros(len(d['train']['raw']['y']), np.uint8)
        total = 0.
        start = time.perf_counter()
        for rows in chunks(d['train']['sequences'], rng):
            ix = rows[rows >= 0]
            optimizer.zero_grad()
            step = model.begin(**inputs(d['train'], ix))
            losses = model.command_loss(step, **geometry(d['train'], ix), **targets(d['train'], ix))
            losses.mean().backward()
            torch.nn.utils.clip_grad_norm_(trainable, 5)
            optimizer.step()
            updates += 1
            total += float(losses.detach().sum())
            seen[ix] += 1
        assert np.all(seen == 1)
        prediction, _ = infer(model, d['validation'], decode=False)
        nll = float(prediction['nll'].mean())
        trace.append(dict(round=epoch, train_command_nll=total / len(seen),
                          DEV_command_nll=nll, updates=updates, seconds=time.perf_counter() - start))
        torch.save(dict(state=model.state_dict(), optimizer=optimizer.state_dict(),
                        dynamic=model.dynamic, round=epoch, source_commit=commit,
                        torch_rng=torch.get_rng_state(), numpy_rng=rng.bit_generator.state,
                        upstream_checkpoint_sha256=digest(checkpoint),
                        protocol_sha256=digest(OUT / 'protocol.json')),
                   directory / f'round-{epoch:02d}.pt')
        print(identifier, trace[-1], flush=True)
        if nll < best - .0001:
            best, selected = nll, epoch
        if epoch - selected >= 6:
            break
    saved = torch.load(directory / f'round-{selected:02d}.pt', weights_only=False)
    model.load_state_dict(saved['state'])
    prediction_hashes = {}
    for split, data in d.items():
        prediction, diagnostics = infer(model, data)
        np.savez_compressed(directory / f'{split}-predictions.npz', **prediction)
        np.savez_compressed(directory / f'{split}-diagnostics.npz', **diagnostics)
        prediction_hashes[split] = digest(directory / f'{split}-predictions.npz')
    frozen = {key: value for key, value in model.named_parameters() if not value.requires_grad}
    assert all(torch.equal(value.detach(), initial[key]) for key, value in frozen.items())
    immutable_json(OUT / f'{identifier}.json', dict(identifier=identifier,
        dynamic=model.dynamic, source_commit=commit, selected_round=selected, trace=trace,
        selected_updates=trace[selected - 1]['updates'], completed_updates=updates,
        trainable_parameters=sum(p.numel() for p in trainable),
        resident_parameters=sum(p.numel() for p in model.parameters()),
        frozen_parameters_unchanged=True, initial_state_sha256=digest(directory / 'initial-state.pt'),
        checkpoint_sha256=digest(directory / f'round-{selected:02d}.pt'),
        predictions_sha256=prediction_hashes, protocol_sha256=digest(OUT / 'protocol.json'),
        upstream_receipt_sha256=digest(OUT / 'upstream-ready.json'),
        seconds=time.perf_counter() - tick,
        timing_scope='After loading through optimization, DEV selection, final inference and serialization; '
                     'not pure optimization time or full experiment cost.',
        new_fits=1, reserved_opened=0, promoted=False, three_seed_confirmed=False))
    print('Completed', identifier, 'fresh Sol xhigh review required', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('identifier', choices=ARMS)
    run(parser.parse_args().identifier)
