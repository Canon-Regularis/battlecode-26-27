"""Small SDK substitutes shared by host-side tests; no WASM bindings needed."""

import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch


SOURCE = Path(__file__).resolve().parents[1] / "src"


def fake_sdk():
    sdk = ModuleType("cambc")
    sdk.game_map = SimpleNamespace()
    sdk.constants = SimpleNamespace(CAPTURE_TIME=5)
    sdk.PassiveType = SimpleNamespace(SPLASH_ATTACK=4)
    sdk.Team = SimpleNamespace(ALLY=0, ENEMY=1)
    draft_names = (
        "RYTH", "VESPER_VALE", "VENDETTA", "CASSI_AND_ISSAC", "STELLAR",
        "PRISM", "MARCELLA", "WILLOW", "REN", "VARG", "TAVI",
    )
    body_names = (
        "RYTH", "VESPER_VALE", "VENDETTA", "CASSI", "ISSAC", "STELLAR",
        "PRISM", "MARCELLA", "WILLOW", "REN", "VARG", "TAVI",
    )
    sdk.ChampionDraft = SimpleNamespace(**dict(zip(draft_names, range(len(draft_names)))))
    sdk.ChampionType = SimpleNamespace(**dict(zip(body_names, range(len(body_names)))))
    sdk.draft = SimpleNamespace(team_size=lambda: 3, current_draft=lambda team: [], pick=MagicMock())
    sdk.draft_memory = SimpleNamespace(submit=MagicMock())
    sdk.fuel_remaining = MagicMock(return_value=100_000_000)
    return sdk


def load_game_modules(sdk):
    """Load fresh SDK adapters together, then restore the host's module table."""
    modules = {}
    with patch.dict(sys.modules, {"cambc": sdk}):
        for name in ("navigation", "combat", "draft_planner", "draft"):
            spec = importlib.util.spec_from_file_location(name, SOURCE / f"{name}.py")
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module  # Dataclass annotations need a registered module.
            spec.loader.exec_module(module)
            modules[name] = module
    return SimpleNamespace(**modules)


def fake_champion():
    champion = MagicMock()
    champion.base_stats.return_value = SimpleNamespace(
        base_strength=100, base_focus=0, camp_damage_multiplier=1, base_health=1000,
    )
    champion.abilities.return_value = ()
    champion.passive.return_value = 0
    return champion


def fake_camp(health, strength=0):
    camp = MagicMock()
    camp.base_stats.return_value = SimpleNamespace(base_health=health, base_strength=strength)
    return camp
