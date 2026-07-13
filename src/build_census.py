from __future__ import annotations

import pandas as pd

from . import config


def build_census() -> pd.DataFrame:
    """Return a schema-valid Census indicator table when local sources are absent."""

    return pd.DataFrame(
        columns=[
            "geography_type",
            "geography_code",
            "reference_year",
            "indicator",
            "indicator_count",
            "denominator_count",
            "indicator_rate",
            "source_name",
            "reliability_flag",
            "limitation_note",
        ]
    )


def census_source_gap_quality_rows() -> list[dict]:
    """Describe the missing local Census source in quality output format."""

    return [
        {
            "dataset": "census_2021_community_indicators",
            "period": "2021",
            "geography": "source geography",
            "field": "",
            "issue_type": "missing_source",
            "issue_severity": "warning",
            "missingness": 1,
            "suppression": "",
            "mapping_status": "not_processed",
            "reliability_flag": config.RELIABILITY_FLAGS["unavailable"],
            "explanatory_note": "No official 2021 Census indicator extract is available locally; counts and denominators are not fabricated.",
        }
    ]

