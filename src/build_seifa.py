from __future__ import annotations

import pandas as pd

from . import config


def build_seifa() -> pd.DataFrame:
    """Return a schema-valid SEIFA table when local sources are absent."""

    return pd.DataFrame(
        columns=[
            "geography_type",
            "geography_code",
            "reference_year",
            "seifa_index",
            "score",
            "national_decile",
            "state_decile",
            "percentile",
            "source_name",
            "reliability_flag",
            "limitation_note",
        ]
    )


def seifa_source_gap_quality_rows() -> list[dict]:
    return [
        {
            "dataset": "seifa_2021",
            "period": "2021",
            "geography": "source geography",
            "field": "",
            "issue_type": "missing_source",
            "issue_severity": "warning",
            "missingness": 1,
            "suppression": "",
            "mapping_status": "not_processed",
            "reliability_flag": config.RELIABILITY_FLAGS["unavailable"],
            "explanatory_note": "No official ABS SEIFA 2021 extract is available locally.",
        }
    ]

