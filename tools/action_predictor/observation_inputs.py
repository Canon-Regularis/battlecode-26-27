"""Indexed immutable observation bank: frame IDs are lookups, never model inputs."""
import numpy as np
import torch

from .observation_study import WORK


class ObservationInputs:
    def __init__(self,split,normalizer,work=WORK):
        self.table=torch.from_numpy(np.load(work/'observations.npy',mmap_mode='c'))
        self.sequence=torch.from_numpy(np.load(work/(split+'-sequence.npy'),mmap_mode='c')).long()
        self.gaps=torch.from_numpy(np.load(work/(split+'-gaps.npy'),mmap_mode='c'))
        self.mean,self.std=normalizer
        assert self.sequence.shape[1]==16 and self.gaps.shape[1:]==(16,5)
        assert torch.equal(self.sequence>0,self.gaps[:,:,1]>0)
        assert bool((self.gaps[:,:,1]<=self.gaps[:,:,0]).all())

    def batch(self,indices):
        values=self.table[self.sequence[indices]]
        return (values-self.mean)/self.std,self.gaps[indices]
