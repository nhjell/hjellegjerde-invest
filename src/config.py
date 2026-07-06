"""Load config/*.yaml so nothing else in src/ hardcodes tickers or assumptions."""

from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


def load_universe() -> list[dict]:
    with open(CONFIG_DIR / "universe.yaml") as f:
        return yaml.safe_load(f)["banks"]


def load_assumptions() -> dict:
    with open(CONFIG_DIR / "assumptions.yaml") as f:
        return yaml.safe_load(f)
