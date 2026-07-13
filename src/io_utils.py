from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from . import config


LOGGER = logging.getLogger(__name__)


def configure_logging() -> None:
    """Configure a compact pipeline logger."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        datefmt="%H:%M:%S",
    )


def ensure_directories() -> None:
    """Create the expected data and metadata directories."""

    for path in config.REQUIRED_DIRS:
        path.mkdir(parents=True, exist_ok=True)


def clean_field_name(value: object) -> str:
    """Return a Tableau-friendly snake_case field name."""

    text = str(value).strip().lower()
    text = text.replace("%", " pct ")
    text = re.sub(r"[^0-9a-zA-Z]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


def clean_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with normalised column names."""

    out = frame.copy()
    out.columns = [clean_field_name(col) for col in out.columns]
    return out


def read_csv(path: Path, *, required: bool = True) -> pd.DataFrame:
    """Read a CSV file, returning an empty frame when optional and missing."""

    if not path.exists():
        if required:
            raise FileNotFoundError(path)
        LOGGER.warning("Optional source missing: %s", path)
        return pd.DataFrame()
    LOGGER.info("Reading %s", path)
    return clean_columns(pd.read_csv(path, low_memory=False))


def numeric(series: pd.Series | object) -> pd.Series:
    """Convert a Series to numeric with infinities treated as missing."""

    values = series if isinstance(series, pd.Series) else pd.Series([series])
    return pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan)


def safe_divide(numerator: pd.Series | float, denominator: pd.Series | float) -> pd.Series:
    """Divide while returning missing values for zero or missing denominators."""

    num = pd.Series(numerator) if not isinstance(numerator, pd.Series) else numeric(numerator)
    den = pd.Series(denominator) if not isinstance(denominator, pd.Series) else numeric(denominator)
    den = den.where(den != 0)
    return num / den


def write_dataset(frame: pd.DataFrame, csv_path: Path, parquet_path: Path | None = None) -> None:
    """Write a dataset as CSV and optionally Parquet."""

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    out = frame.copy()
    out.columns = [clean_field_name(col) for col in out.columns]
    LOGGER.info("Writing %s rows to %s", len(out), csv_path)
    out.to_csv(csv_path, index=False)
    if parquet_path is not None:
        parquet_path.parent.mkdir(parents=True, exist_ok=True)
        out.to_parquet(parquet_path, index=False)


def write_audit(frame: pd.DataFrame, name: str) -> Path:
    """Write an audit CSV under data/audits and return its path."""

    path = config.AUDIT_DIR / name
    write_dataset(frame, path)
    return path


def row_count_frame(rows: Iterable[dict]) -> pd.DataFrame:
    """Build a row-count audit frame from dictionaries."""

    return pd.DataFrame(list(rows), columns=["dataset", "stage", "row_count", "column_count", "notes"])
