"""Personally observed identity memory; IDs are keys, never neural features.

Not a selector, strategy, candidate command generator or fitted policy. This
interface is preparatory for a separately controlled grounding experiment.
"""
import copy
import math
import numpy as np
from ..entity_set import token


class PersonalEntityMemory:
    def __init__(self):
        self.reset()

    def reset(self, prefix_unavailable=True):
        self.entries = {}
        self.current = set()
        self.ordinal = None
        self.prefix_unavailable = bool(prefix_unavailable)
        self.last_gap = None

    @staticmethod
    def key(entity):
        return (int(entity['entity']['kind']), int(entity['entity']['index']))

    def observe_pre(self, observation, own_root_ordinal):
        """Consume only an available personal PRE, before action prediction.

        Missing roots remain missing. Neither goal continuity nor entity life,
        movement, respawn or effects are simulated between observations.
        """
        if not isinstance(own_root_ordinal, int) or own_root_ordinal < 0:
            raise ValueError('Exact nonnegative own-root ordinal required')
        if self.ordinal is not None and own_root_ordinal <= self.ordinal:
            raise ValueError('Personal PREs must be strictly forward within one actor/episode')
        own = observation['own']
        if not own.get('known', 0) & 1: raise ValueError('Own personal observation unavailable')
        actor = self.key(own)
        if hasattr(self, 'actor') and self.ordinal is not None and actor != self.actor:
            raise ValueError('Reset memory before a different actor/episode')
        self.actor = actor
        self.last_gap = None if self.ordinal is None else own_root_ordinal-self.ordinal
        self.ordinal = own_root_ordinal
        self.current = set()
        for entity in [own, *observation.get('entities', [])]:
            key = self.key(entity)
            if key[0] not in (1, 2) or not entity.get('known', 0) & 1:
                continue  # Never ingest dynamic fields on unknown entries.
            self.current.add(key)
            # Refresh ALL personally observed identities, not a ranked goal list.
            self.entries[key] = dict(entity=copy.deepcopy(entity), seen_at=own_root_ordinal)

    def snapshot(self, own):
        """Return explicit null/unknown slots and every previously seen entity.

        Features119reuse the reviewed token encoder. Additional fields are
        null/unknown/entity flags, currently_personal, log1p_age/8,
        prefix_unavailable, missing_roots_since_last_PRE, last_observed_dead.
        Old attributes/positions are memories, never asserted current facts.
        Keys must stay outside learned tensors and positional embeddings.
        """
        if self.ordinal is None: raise ValueError('Observe a personal PRE first')
        keys = [None, 'unknown', *sorted(self.entries)]
        vectors = []
        for key in keys:
            extra = np.zeros(8, np.float32)
            extra[0 if key is None else 1 if key == 'unknown' else 2] = 1
            extra[5] = self.prefix_unavailable
            extra[6] = self.last_gap is None or self.last_gap != 1
            if key is None or key == 'unknown':
                encoded = np.zeros(119, np.float32)
            else:
                entry = self.entries[key]; entity = entry['entity']
                encoded = token(entity, own, key == self.actor).astype(np.float32)
                extra[3] = key in self.current
                extra[4] = math.log1p(self.ordinal-entry['seen_at'])/8
                extra[7] = entity.get('alive') is False or entity.get('health', 1) <= 0
            vectors.append(np.concatenate((encoded, extra)))
        return keys, np.stack(vectors)
