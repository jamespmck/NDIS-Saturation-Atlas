from __future__ import annotations

import pandas as pd

from . import config


def build_housing() -> pd.DataFrame:
    """Return a schema-valid housing context table when local sources are absent."""

    return pd.DataFrame(
        columns=[
            "geography_type",
            "geography_code",
            "reference_period",
            "housing_indicator",
            "indicator_count",
            "denominator_count",
            "indicator_rate",
            "source_name",
            "reliability_flag",
            "limitation_note",
        ]
    )


def housing_source_gap_quality_rows() -> list[dict]:
    return [
        {
            "dataset": "housing_and_sda_context",
            "period": "latest available",
            "geography": "source geography",
            "field": "",
            "issue_type": "missing_source",
            "issue_severity": "warning",
            "missingness": 1,
            "suppression": "",
            "mapping_status": "not_processed",
            "reliability_flag": config.RELIABILITY_FLAGS["unavailable"],
            "explanatory_note": "No official housing/SDA context extract beyond existing NDIA support-type payment context is available locally.",
        }
    ]

