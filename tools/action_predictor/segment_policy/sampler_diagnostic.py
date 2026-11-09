"""Exact no-optimizer reconstruction of the executed variable-stream sampler."""
import json
import numpy as np
import torch
from ..audit import immutable_json
from ..data import digest
from ..learned_policy.data import chunks
from .data import BASE, WORK, REPORT
from .protocol import SEED


def run():
    with np.load(BASE.parent/'v16/train-sequences.npz') as z:
        order, offsets = z['order'], z['offsets']
    sequences = [order[a:b] for a, b in zip(offsets[:-1], offsets[1:])]
    with np.load(BASE/'combined-train.npz') as z: group = z['group']; y = z['y']
    groups = np.unique(group)
    rng = np.random.default_rng(SEED)
    records = []
    destination = WORK/'sampler-diagnostic'
    destination.mkdir(parents=True, exist_ok=False)
    paths = sorted((WORK/'runs/H00').glob('round-*.pt'))
    for path in paths:
        saved = torch.load(path, weights_only=False, map_location='cpu')
        coefficient = np.zeros(len(group), np.float64)
        sizes = []; group_rows = []; action_rows = []
        seen = np.zeros(len(group), np.uint8)
        for block in chunks(sequences, rng):
            ids = block[block >= 0]
            n = len(ids)
            coefficient[ids] += 1/n
            seen[ids] += 1
            sizes.append(n)
            group_rows.append(np.array([(group[ids] == g).sum() for g in groups]))
            action_rows.append(np.bincount(y[ids], minlength=15))
        sizes = np.array(sizes)
        group_rows = np.stack(group_rows); action_rows = np.stack(action_rows)
        archive = destination/(path.stem+'.npz')
        # Preserve the actual reconstructed schedule before validating it.
        np.savez_compressed(archive, sizes=sizes, group_rows=group_rows, action_rows=action_rows,
                            row_mean_loss_coefficients=coefficient, groups=groups)
        if not np.all(seen == 1): raise RuntimeError('Sampler coverage differs')
        if rng.bit_generator.state != saved['numpy_rng']: raise RuntimeError('Executed permutation RNG differs')
        nominal = len(sizes)/len(group)
        ratios = {str(int(g)): float(coefficient[group == g].mean()/nominal) for g in groups}
        tail = group_rows[-128:]
        counts = tail.sum(0)
        weighted = (tail/sizes[-128:, None]).sum(0)
        leaders = np.argsort(weighted)[-5:][::-1]
        records.append(dict(round=saved['round'], updates=len(sizes), checkpoint_updates=saved['updates'],
            batch_rows_quantiles=np.quantile(sizes, [0, .1, .5, .9, 1]).tolist(),
            batches_under64=int((sizes < 64).sum()), rows_in_batches_under64=int(sizes[sizes < 64].sum()),
            final128_updates_groups=int((counts > 0).sum()),
            final128_top_groups=[dict(group=int(groups[i]), rows=int(counts[i]),
                mean_batch_gradient_coefficient_share=float(weighted[i]/len(tail))) for i in leaders],
            group_mean_row_coefficient_relative_to_uniform=ratios,
            minimum_relative_group_coefficient=min(ratios.values()), maximum_relative_group_coefficient=max(ratios.values()),
            schedule_sha256=digest(archive), rng_exact=True))
    if not records: raise RuntimeError('No retained round checkpoints')
    if np.cumsum([r['updates'] for r in records]).tolist() != [r['checkpoint_updates'] for r in records]:
        raise RuntimeError('Executed optimizer counters differ from sampler reconstruction')
    immutable_json(REPORT/'H00-sampler-diagnostic.json', dict(rounds=records,
        source_sha256=digest(__file__), sampler_source_sha256=digest(__file__.replace('segment_policy/sampler_diagnostic.py', 'learned_policy/data.py')),
        interpretation='Exact per-row coefficients in each minibatch mean before shared clipping/AdamW. These are not realized optimizer influence: gradients, clipping, adaptive moments and row correlations matter. Nonuniform coefficients or tail concentration do not establish the cause of DEV deterioration. All original rows remain included.',
        source_checkpoint_count=len(records), new_fits=0, optimizer_updates=0, reserved_opened=0))


if __name__ == '__main__': run()
