"""Shared helpers: project paths, logging, CSV I/O and numeric cleaning.

Everything else in src/ imports paths from here rather than recomputing
`Path(__file__)...` or hardcoding absolute paths.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

# --- Paths -----------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
OUTPUTS_DIR = ROOT / "outputs"
CHARTS_DIR = OUTPUTS_DIR / "charts"
TABLES_DIR = OUTPUTS_DIR / "tables"
LOGS_DIR = ROOT / "logs"


def ensure_dirs() -> None:
    """Create the output directories if they don't exist yet."""
    for d in (PROCESSED_DIR, CHARTS_DIR, TABLES_DIR, LOGS_DIR):
        d.mkdir(parents=True, exist_ok=True)


# --- Logging ---------------------------------------------------------------
def get_logger(name: str = "hjellegjerde") -> logging.Logger:
    """Return a module logger that logs to stderr once (no duplicate handlers)."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s | %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


# --- CSV I/O ---------------------------------------------------------------
def save_csv(df: pd.DataFrame, path: Path, index: bool = False) -> Path:
    """Save a DataFrame to CSV, creating the parent directory if needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=index)
    return path


def load_csv(path: Path, **kwargs) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Expected input file not found: {path}. "
            "Run `python src/build_inputs.py` first to generate the processed CSVs."
        )
    return pd.read_csv(path, **kwargs)


# --- Numeric cleaning ------------------------------------------------------
def to_float(value, default: float = np.nan) -> float:
    """Coerce a possibly-None / string value to float, returning default on failure."""
    if value is None:
        return default
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    if np.isnan(f) or np.isinf(f):
        return default
    return f


def clip(value: float, lo: float, hi: float) -> float:
    """Clip a scalar to [lo, hi]; NaN passes through unchanged."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return np.nan
    return max(lo, min(hi, value))


def is_number(value) -> bool:
    """True if value is a finite real number."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return False
    return not (np.isnan(f) or np.isinf(f))
