"""One frozen contrast arm per invocation; never chains another fit."""
import argparse
import json
import time
import numpy as np
import torch
from .protocol import SEED, ARMS, preflight
from .model import SegmentPolicy
from .data import ROOT, WORK, REPORT, BASE, load, causal_inputs, geometry, targets, chunks
from .inference import infer, take, put
from .assessment import assess
from ..priority_fit_v3 import load_base
from .. import reliable_train as rt
from ..audit import immutable_json
from ..data import digest


def run(arm):
    if arm not in ARMS: raise ValueError('Unknown registered arm')
    # Every prerequisite must pass before optimizer construction or run output.
    plan, gate = preflight()
    directory = WORK/'runs'/arm
    if directory.exists(): raise FileExistsError('Preserve every prior fit attempt: '+str(directory))
    rt.setup(SEED)
    teacher, saved = load_base()
    model = SegmentPolicy(teacher, arm == 'H01')
    trainable = [p for p in model.parameters() if p.requires_grad]
    if sum(p.numel() for p in trainable) != plan['parameters'][arm]['trainable']:
        raise RuntimeError('Trainable capacity changed')
    data = {s: load(s, saved) for s in ('train', 'validation')}
    if [len(data[s]['raw']['y']) for s in data] != [433071, 14439]:
        raise RuntimeError('Original evaluation denominator changed')
    # Exercise the actual cached interface before optimizer construction; no
    # update, re-extraction, held partition or selected-answer routing.
    with torch.no_grad():
        model.eval()
        ids = np.array([s[0] for s in data['train']['sequences'][:32]])
        step = model.begin(**causal_inputs(data['train'], ids), state=model.empty(len(ids)))
        loss, _ = model.observed(step, **geometry(data['train'], ids), **targets(data['train'], ids))
        if not bool(torch.isfinite(loss).all()): raise RuntimeError('Actual TRAIN interface failed')
    if arm == 'H01':
        reference_path = REPORT/'H00.json'
        reference = json.loads(reference_path.read_text())
        control_path = WORK/'runs/H00/validation-predictions.npz'
        key = str(control_path.relative_to(ROOT))
        if digest(control_path) != reference['bindings'][key]: raise RuntimeError('Direct control predictions changed')
        gate['matched_direct_control'] = {str(reference_path.relative_to(ROOT)): digest(reference_path),
                                         key: digest(control_path)}
    directory.mkdir(parents=True)
    immutable_json(directory/'preflight.json', gate)
    opt = torch.optim.AdamW(trainable, lr=.0003, weight_decay=.01)
    if {id(p) for g in opt.param_groups for p in g['params']} != {id(p) for p in trainable}:
        raise RuntimeError('Optimizer omits trainable parameters')
    rng = np.random.default_rng(SEED)
    def save(path, epoch, updates):
        torch.save(dict(state=model.state_dict(), optimizer=opt.state_dict(), mean=saved['mean'],
            std=saved['std'], config=saved['config'], arm=arm, round=epoch, updates=updates,
            torch_rng=torch.get_rng_state(), numpy_rng=rng.bit_generator.state,
            source_commit=gate['source_commit'], protocol_sha256=gate['protocol_sha256']), path)
    save(directory/'initial.pt', 0, 0)
    trace = []
    best = float('inf')
    selected = updates = 0
    tick = time.perf_counter()
    for epoch in range(1, 36):
        state = model.empty(32)
        model.train()
        seen = np.zeros(433071, np.uint8)
        total = 0.
        start = time.perf_counter()
        for rows in chunks(data['train']['sequences'], rng):
            opt.zero_grad(set_to_none=True)
            losses = []
            denominator = 0
            for row in rows:
                active = torch.from_numpy(np.flatnonzero(row >= 0))
                ids = row[row >= 0]
                if not len(ids): continue
                step = model.begin(**causal_inputs(data['train'], ids), state=take(state, active))
                loss, post = model.observed(step, **geometry(data['train'], ids), **targets(data['train'], ids))
                if not bool(torch.isfinite(loss).all()): raise RuntimeError('Nonfinite training loss')
                state = put(state, active, post)
                losses.append(loss.sum())
                denominator += len(ids)
                seen[ids] += 1
            objective = torch.stack(losses).sum()/denominator
            objective.backward()
            norm = torch.nn.utils.clip_grad_norm_(trainable, 5, error_if_nonfinite=True)
            opt.step()
            updates += 1
            total += float(objective.detach())*denominator
            state = {k: v.detach() for k, v in state.items()}
            if updates % 250 == 0:
                print(arm, 'round', epoch, 'update', updates, 'seconds', round(time.perf_counter()-tick, 1), flush=True)
        if not np.all(seen == 1): raise RuntimeError('Training row coverage changed')
        # Weights survive even a subsequent validation failure.
        checkpoint = directory/f'round-{epoch:02d}.pt'
        save(checkpoint, epoch, updates)
        forecast = infer(model, data['validation'], directory/f'round-{epoch:02d}-validation', decode=False)
        nll = float(forecast['nll'].mean())
        trace.append(dict(round=epoch, train_online_command_nll=total/len(seen), DEV_command_nll=nll,
            updates=updates, seconds=time.perf_counter()-start, checkpoint_sha256=digest(checkpoint)))
        immutable_json(directory/f'round-{epoch:02d}-measurement.json', trace[-1])
        print(arm, trace[-1], flush=True)
        if nll < best-.0001: best, selected = nll, epoch
        if epoch-selected >= 6: break
    chosen = torch.load(directory/f'round-{selected:02d}.pt', map_location='cpu', weights_only=False)
    model.load_state_dict(chosen['state'])
    forecasts = {}
    for split, d in data.items():
        forecasts[split] = infer(model, d, directory/f'{split}-raw', decode=True)
        np.savez_compressed(directory/f'{split}-predictions.npz', **forecasts[split])
    # Entire raw/decoded forecast package exists before aggregate assessment.
    results, comparisons = assess(arm, data, forecasts)
    bindings = dict(plan['inputs'])
    bindings.update(gate.get('matched_direct_control', {}))
    for path in directory.rglob('*'):
        if path.is_file(): bindings[str(path.relative_to(ROOT))] = digest(path)
    value = dict(arm=arm, selected_round=selected, completed_rounds=len(trace), trace=trace,
        selected_updates=trace[selected-1]['updates'], completed_updates=updates,
        parameters=plan['parameters'][arm], source_commit=gate['source_commit'], sources=gate['sources'],
        protocol_sha256=gate['protocol_sha256'], results=results, comparisons=comparisons,
        seconds_after_setup_through_assessment=time.perf_counter()-tick,
        bindings=bindings, checkpoint_sha256=digest(directory/f'round-{selected:02d}.pt'),
        new_fits=1, reserved_opened=0, promoted=False, three_seed_confirmed=False)
    immutable_json(REPORT/f'{arm}.json', value)
    print(arm, 'completed; fresh Sol xhigh review required', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('arm', choices=ARMS)
    run(parser.parse_args().arm)
