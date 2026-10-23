"""Configuration and serialisable compiler diagnostics."""

from dataclasses import asdict, dataclass, field


PASS_DESCRIPTIONS = {
    "tuple-adjacent-iterator": "Iterate owned exact tuples with a previous-item local and explicit cleanup instead of pair allocation/unpacking.",
    "tuple-insertion-buffer": "Yield tuple insertion variants using an owned buffer with explicit generator cleanup and exact-tuple fallback.",
    "native-index-guard": "Use native exact-sequence bounds checks with original reduction fallback on IndexError.",
    "wide-helper-limit": "Extend measured guarded reduction and adjacency helpers through sixteen indices.",
    "helper-loop-shape": "Hoist invariant integer bounds and track extremum initialization with a local boolean.",
    "helper-builtin-cache": "Bind stable builtins as private helper defaults while preserving source function signatures.",
    "adjacent-extend": "Incrementally extend exact lists over guarded primitive tuple adjacency with original fallback.",
    "tuple-adjacent": "Use native pairwise for exact tuples with a stable local owner and original fallback.",
    "scalar-extremum": "Inline two-argument min/max with stable ties and explicit temporary cleanup.",
    "extremum-loop": "Use direct min/max expression loops with exact-sequence fallback and explicit exception cleanup.",
    "record-inline-return": "Inline cached fresh-record allocation at a proven terminal return without deferring allocation.",
    "short-circuit-loop": "Use guarded direct loops for any/all element comparisons, preserving iterator and exception fallbacks.",
    "short-int-reductions": "Fuse three indexed reductions of up to eight rows after exact container, record and integer guards.",
    "deferred-record": "Compatibility disable switch for the archived, rejected deferred-record prototype (inactive).",
    "record-call": "Use cached-allocation factories for resolved four-to-twenty-field frozen records.",
    "record-allocator-cache": "Prebind the immutable builtin allocator used by small-record factories.",
    "constant-facts": "Infer stable module integer constants across acyclic imports.",
    "loop-integer-facts": "Retain exact-int facts for already-bound locals with integer-preserving loop writes.",
    "integer-mod-mask": "Replace exact-int modulo a proven small positive power of two with a bit mask.",
    "return-shape": "Infer exact immutable/SDK return shapes from straight-line source wrappers across modules.",
    "small-record-call": "Specialise resolved two/three-field frozen-record construction without changing public constructors.",
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
    "record-bulk-init": "Initialise eligible frozen records with allocation-free direct dictionary stores.",
    "scalar-record": "Eliminate a temporary record used only by an immediate return expression.",
    "integer-membership": "Use a frozen constant set for exact-integer membership in literal integer tables.",
    "sdk-state-expression": "Share champion state queries inside callback-free boolean expressions.",
    "sdk-state-mask": "Use precomputed native flag masks for grouped champion state predicates.",
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
