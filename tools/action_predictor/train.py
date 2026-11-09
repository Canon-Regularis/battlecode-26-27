"""Prepare: python -m tools.action_predictor.train prepare --source PATH --out PATH
Train: python -m tools.action_predictor.train train --data PATH --out PATH
"""
import argparse
import copy
import json
import random
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset

from .data import digest, prepare
from .model import ActionGRU


class Turns(Dataset):
    def __init__(self, data, split, mean, std, classes):
        self.x = (torch.from_numpy(data[f'{split}_x']) - mean) / std
        self.y = torch.from_numpy(data[f'{split}_y'])
        self.offsets = data[f'{split}_offsets']
        self.classes = classes

    def __len__(self):
        return len(self.offsets) - 1

    def __getitem__(self, i):
        if i < 0 or i >= len(self):
            raise IndexError(i)
        a, b = self.offsets[i:i+2]
        x, y = self.x[a:b], self.y[a:b]
        previous = torch.cat((torch.tensor([self.classes]), y[:-1]))
        return x, y, previous


def collate(rows):
    pad = nn.utils.rnn.pad_sequence
    return (pad([r[0] for r in rows], batch_first=True),
            pad([r[1] for r in rows], batch_first=True, padding_value=-100),
            pad([r[2] for r in rows], batch_first=True))


def metrics(confusion, loss=None, top3=None):
    support = confusion.sum(1)
    precision = confusion.diag() / confusion.sum(0).clamp_min(1)
    recall = confusion.diag() / support.clamp_min(1)
    f1 = 2 * precision * recall / (precision+recall).clamp_min(1e-12)
    result = dict(accuracy=float(confusion.diag().sum() / support.sum()),
                  macro_f1=float(f1[support > 0].mean()),
                  per_class=[dict(support=int(support[i]), precision=float(precision[i]),
                                  recall=float(recall[i]), f1=float(f1[i])) for i in range(len(support))],
                  confusion_matrix=confusion.tolist())
    if loss is not None:
        result['cross_entropy'] = loss / int(support.sum())
    if top3 is not None:
        result['top3_accuracy'] = top3 / int(support.sum())
    return result


@torch.no_grad()
def evaluate(model, loader, classes):
    model.eval()
    confusion = torch.zeros(classes, classes, dtype=torch.int64)
    loss, top3 = 0., 0
    for x, y, previous in loader:
        logits, _ = model(x, previous)
        valid = y != -100
        target, scores = y[valid], logits[valid]
        loss += float(nn.functional.cross_entropy(scores, target, reduction='sum'))
        predicted = scores.argmax(-1)
        confusion += torch.bincount(target * classes + predicted, minlength=classes**2).reshape(classes, classes)
        top3 += int((scores.topk(min(3, classes), dim=-1).indices == target[:, None]).any(-1).sum())
    return metrics(confusion, loss, top3)


def baseline(train, test, classes, transition=False):
    counts = torch.bincount(train.y, minlength=classes)
    table = torch.zeros(classes+1, classes, dtype=torch.int64)
    for _, y, previous in train:
        table += torch.bincount(previous * classes + y, minlength=(classes+1)*classes).reshape(classes+1, classes)
    # Unobserved transition rows fall back to global majority.
    table[table.sum(1) == 0] = counts
    confusion = torch.zeros(classes, classes, dtype=torch.int64)
    for _, y, previous in test:
        prediction = table[previous].argmax(-1) if transition else counts.argmax().expand_as(y)
        confusion += torch.bincount(y * classes + prediction, minlength=classes**2).reshape(classes, classes)
    return metrics(confusion)


def train(args):
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.set_num_threads(args.threads)
    torch.use_deterministic_algorithms(True)
    out = args.out
    if any((out/name).exists() for name in ('model.pt', 'metrics.json')):
        raise FileExistsError('Preserve existing experiments; choose a fresh output directory')
    out.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((args.data/'dataset.json').read_text())
    if digest(args.data/'data.npz') != manifest['data_sha256']:
        raise ValueError('Prepared data checksum mismatch')
    data = np.load(args.data/'data.npz', allow_pickle=False)
    classes = len(manifest['labels'])
    raw = torch.from_numpy(data['train_x'])
    mean, std = raw.mean(0), raw.std(0).clamp_min(.01)
    datasets = {s: Turns(data, s, mean, std, classes) for s in ('train', 'validation', 'test')}
    loaders = {s: DataLoader(d, batch_size=args.batch_size, shuffle=s == 'train', collate_fn=collate)
               for s, d in datasets.items()}
    model = ActionGRU(raw.shape[1], classes, args.hidden)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=.0001)
    best, best_epoch, state, history = float('inf'), 0, None, []
    for epoch in range(1, args.epochs+1):
        model.train()
        total, count = 0., 0
        for x, y, previous in loaders['train']:
            optimizer.zero_grad(set_to_none=True)
            logits, _ = model(x, previous)
            loss = nn.functional.cross_entropy(logits.flatten(0, 1), y.flatten(), ignore_index=-100)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.)
            optimizer.step()
            n = int((y != -100).sum())
            total += float(loss.detach()) * n
            count += n
        val = evaluate(model, loaders['validation'], classes)
        history.append(dict(epoch=epoch, train_cross_entropy=total/count,
                            validation_cross_entropy=val['cross_entropy'], validation_accuracy=val['accuracy']))
        print(json.dumps(history[-1]), flush=True)
        if val['cross_entropy'] < best - .0001:
            best, best_epoch, state = val['cross_entropy'], epoch, copy.deepcopy(model.state_dict())
        elif epoch - best_epoch >= args.patience:
            break
    model.load_state_dict(state)
    checkpoint = dict(state_dict=state, mean=mean, std=std, hidden=args.hidden,
                      labels=manifest['labels'], features=manifest['features'],
                      dataset_sha256=digest(args.data/'dataset.json'))
    torch.save(checkpoint, out/'model.pt')
    # Test is touched only once, after validation selects the checkpoint.
    report = dict(schema=1, model='Linear/ReLU + previous-action embedding + one-layer causal GRU + classifier',
                  torch_version=str(torch.__version__), device='cpu', seed=args.seed,
                  hidden=args.hidden, parameters=sum(p.numel() for p in model.parameters()),
                  best_epoch=best_epoch, labels=manifest['labels'], statistics=manifest['statistics'], history=history,
                  validation=evaluate(model, loaders['validation'], classes),
                  test=evaluate(model, loaders['test'], classes),
                  majority_baseline=baseline(datasets['train'], datasets['test'], classes),
                  transition_baseline=baseline(datasets['train'], datasets['test'], classes, True),
                  dataset_sha256=digest(args.data/'dataset.json'), checkpoint_sha256=digest(out/'model.pt'),
                  limitations=[manifest['scope'], manifest['sampling'], manifest['evaluation'],
                               'One-step prediction with observed history, not an autonomous rollout or evidence of playing strength.',
                               'Hidden state resets every sampled turn; gaps between sampled turns are not treated as adjacent.',
                               'Personal visible state only; no map terrain, path plan, private memory or full SDK legality.',
                               'Historical engine versions 2/3; deployment on engine 4 is unvalidated.'])
    (out/'metrics.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(dict(best_epoch=best_epoch, test_accuracy=report['test']['accuracy'],
                          test_macro_f1=report['test']['macro_f1'],
                          majority_accuracy=report['majority_baseline']['accuracy'],
                          transition_accuracy=report['transition_baseline']['accuracy'])), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    commands = p.add_subparsers(dest='command', required=True)
    prep = commands.add_parser('prepare')
    prep.add_argument('--source', type=Path, required=True)
    prep.add_argument('--out', type=Path, required=True)
    prep.add_argument('--seed', type=int, default=26)
    fit = commands.add_parser('train')
    fit.add_argument('--data', type=Path, required=True)
    fit.add_argument('--out', type=Path, required=True)
    fit.add_argument('--epochs', type=int, default=40)
    fit.add_argument('--patience', type=int, default=6)
    fit.add_argument('--hidden', type=int, default=96)
    fit.add_argument('--batch-size', type=int, default=128)
    fit.add_argument('--lr', type=float, default=.001)
    fit.add_argument('--threads', type=int, default=4)
    fit.add_argument('--seed', type=int, default=26)
    args = p.parse_args()
    if args.command == 'prepare':
        prepare(args.source, args.out, args.seed)
    else:
        train(args)


if __name__ == '__main__':
    main()
