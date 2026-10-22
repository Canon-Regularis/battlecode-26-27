"""Configuration and serialisable compiler diagnostics."""

from dataclasses import asdict, dataclass, field


PASS_DESCRIPTIONS = {
    "integer-square": "Replace exact-integer local x**2 with x*x.",
    "native-map": "Replace a pure integer generator callback with native map.",
    "bounded-sum": "Materialise a bounded pure integer sum generator.",
    "mask-count": "Count a Bitboard without constructing positions.",
    "mask-empty": "Test Bitboard existence without constructing positions.",
    "mask-filter": "Intersect Bitboards before materialising positions.",
    "mask-intersection-count": "Count an intersection without materialising positions.",
    "native-key": "Remove a lambda forwarding to a native SDK method.",
    "native-itemgetter": "Precompute native keys for fixed-index lambda callbacks.",
    "native-attrgetter": "Precompute native keys for attribute-only lambda callbacks.",
    "identity-reduction": "Remove identity generators from streaming built-in reductions.",
    "bounded-reduction": "Materialise bounded pure integer reductions over immutable tuples.",
    "call-positional": "Use positional arguments at statically resolved call sites.",
    "inline-integer-helper": "Inline resolved small arithmetic helpers with exact integer inputs.",
    "record-bulk-init": "Initialise eligible frozen records with one native dictionary update.",
    "scalar-record": "Eliminate a temporary record used only by an immediate return expression.",
}


@dataclass(frozen=True)
class Options:
    target: str = "3.0.4"
    trust_annotations: bool = False
    max_materialize: int = 4096
    min_bulk_fields: int = 4
    disabled: frozenset[str] = frozenset()

    def __post_init__(self):
        if self.target != "3.0.4":
            raise ValueError("Only the researched cambc 3.0.4 runtime is supported")
        if self.max_materialize < 0:
            raise ValueError("max_materialize must be non-negative")
        if self.min_bulk_fields < 1:
            raise ValueError("min_bulk_fields must be positive")
        unknown = self.disabled - PASS_DESCRIPTIONS.keys()
        if unknown:
            raise ValueError(f"Unknown passes: {', '.join(sorted(unknown))}")

    def to_dict(self):
        return {**asdict(self), "disabled": sorted(self.disabled)}


@dataclass
class Change:
    pass_name: str
    line: int
    before: str
    after: str


@dataclass
class SourceResult:
    source: str
    changes: list[Change] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def diagnostics(self):
        return {
            "changes": [asdict(change) for change in self.changes],
            "warnings": self.warnings,
        }
