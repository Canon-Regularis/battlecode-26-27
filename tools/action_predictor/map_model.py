"""Public local-terrain and global-objective CNN encoders alongside the GRU."""
import torch
from torch import nn

from .reliable_model import JointModel


class MapCandidate(nn.Module):
    def __init__(self, base):
        super().__init__()
        self.base = base
        self.extra = nn.Linear(8, 32, bias=False)
        nn.init.zeros_(self.extra.weight)

    def forward(self, grid):
        return self.base(grid[..., :20]) + self.extra(grid[..., 20:])


class MapJointModel(JointModel):
    def __init__(self, inputs, history_features, classes, config):
        super().__init__(inputs, history_features, classes, config)
        assert config['history'] == 16 and config['spatial']
        shuffle_state = torch.get_rng_state()
        self.candidate = MapCandidate(self.candidate)
        # 23 -> 21 -> 17. Each output aligns with one existing destination cell.
        self.local_map = nn.Sequential(
            nn.Conv2d(8, 8, 3, groups=8), nn.ReLU(),
            nn.Conv2d(8, 8, 1), nn.ReLU(),
            nn.Conv2d(8, 8, 3, dilation=2, groups=8), nn.ReLU(),
            nn.Conv2d(8, 8, 1), nn.ReLU())
        self.global_map = nn.Sequential(
            nn.Conv2d(9, 9, 3, stride=2, padding=1, groups=9),
            nn.Conv2d(9, 8, 1), nn.ReLU(),
            nn.Conv2d(8, 8, 3, stride=2, padding=1, groups=8),
            nn.Conv2d(8, 8, 1), nn.ReLU(),
            nn.AdaptiveAvgPool2d((4, 4)), nn.Flatten(), nn.Linear(128, 32), nn.ReLU())
        self.map_fusion = nn.Sequential(nn.Linear(176, 128), nn.ReLU(), nn.Linear(128, 128))
        nn.init.zeros_(self.map_fusion[-1].weight)
        nn.init.zeros_(self.map_fusion[-1].bias)
        # Extra-layer initialization must not change the baseline's shuffle stream.
        torch.set_rng_state(shuffle_state)

    def forward(self, x, history, local_map, global_map):
        _, base = super().forward(x, history)
        if self.config.get('zero_map'):
            local_map = torch.zeros_like(local_map)
            global_map = torch.zeros_like(global_map)
        spatial = self.local_map(local_map)
        local = torch.cat((spatial.mean((2, 3)), spatial[:, :, 8, 8]), -1)
        context = base + self.map_fusion(torch.cat((base, local, self.global_map(global_map)), -1))
        return self.action(context), context, spatial.flatten(2).transpose(1, 2)

    def parameter_logits(self, context, grid, valid, family, rules=None, map_features=None):
        if map_features is None:
            raise ValueError('Map candidate features are required')
        return super().parameter_logits(context, torch.cat((grid, map_features), -1), valid, family, rules)
