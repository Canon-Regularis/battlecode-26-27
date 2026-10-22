"""Tuning knobs for the draft-only planner. Safe to import outside the game."""

from dataclasses import dataclass

# Strategy: 0 strongly penalizes exposed loops; 1 ignores positional risk.
RISK_TOLERANCE = 0.2
GOLD_WEIGHT = 0.02
OPENING_WEIGHT = 0.15

# Squad: these are SDK ChampionDraft names, not numeric champion/body IDs.
PREFERRED_PICKS = (
    "VARG", "WILLOW", "VENDETTA", "MARCELLA", "TAVI", "RYTH",
    "VESPER_VALE", "STELLAR", "PRISM", "REN", "CASSI_AND_ISSAC",
)

# Search and draft compute budget.
CANDIDATE_LIMIT = 24
ALTAR_LIMIT = 4
REPORT_LIMIT = 5
BEAM_WIDTH = 8
MAX_CAMPS_PER_LOOP = 10
MAX_EXPANSIONS = 20_000
FUEL_RESERVE = 4_000_000
# Named distance lookups are cheaper than the old tuple/generator wrappers.
# Keep that saving for route expansion instead of widening BFS at its expense.
PRECOMPUTE_RESERVE = 11_500_000
FUEL_CHECK_INTERVAL = 8

# Combat approximations, not engine rules. Capture time comes from the SDK.
ABILITY_UTILIZATION = 0.7
HEALING_UTILIZATION = 0.7
DAMAGE_UTILIZATION = 0.8
SPLASH_EXTRA_TARGET_WEIGHT = 0.5
MAX_EXTRA_SPLASH_TARGETS = 2
MAX_AOE_TARGETS = 2
MAX_HEALTH_LOSS_FRACTION = 0.65
CAPTURE_REPOSITION_TURNS = 2

# Drawing and local inspection.
LOOP_COLORS = (
    ("green", 0x00DD88), ("cyan", 0x00BBFF), ("orange", 0xFFAA22),
    ("purple", 0xCC66FF), ("pink", 0xFF5588),
)
ROUNDS_PER_LOOP = 8
REPORT_MARKER = "SQUAD_LOOPS_DATA "
DRAFT_MEMORY_LIMIT = 1024


@dataclass(frozen=True)
class SearchConfig:
    """Immutable defaults; tests can override individual search settings."""

    beam_width: int = BEAM_WIDTH
    max_camps: int = MAX_CAMPS_PER_LOOP
    max_expansions: int = MAX_EXPANSIONS
    gold_weight: float = GOLD_WEIGHT
    opening_weight: float = OPENING_WEIGHT
    risk_tolerance: float = RISK_TOLERANCE

    def __post_init__(self):
        if not 0 <= self.risk_tolerance <= 1:
            raise ValueError("risk tolerance must be between 0 and 1")


DEFAULT_SEARCH_CONFIG = SearchConfig()
