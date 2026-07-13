from __future__ import annotations

import pandas as pd

from . import config


def build_phidu() -> pd.DataFrame:
    """Return a schema-valid PHIDU indicator table when local sources are absent."""

    return pd.DataFrame(
        columns=[
            "source_geography_type",
            "source_geography_code",
            "reference_period",
            "indicator",
            "indicator_count",
            "denominator_count",
            "indicator_rate",
            "source_name",
            "reliability_flag",
            "limitation_note",
        ]
    )


def phidu_source_gap_quality_rows() -> list[dict]:
    return [
        {
            "dataset": "phidu_social_health_atlas",
            "period": "latest available",
            "geography": "PHIDU source geography",
            "field": "",
            "issue_type": "missing_source",
            "issue_severity": "warning",
            "missingness": 1,
            "suppression": "",
            "mapping_status": "not_processed",
            "reliability_flag": config.RELIABILITY_FLAGS["unavailable"],
            "explanatory_note": "No PHIDU Social Health Atlas extract is available locally; PHIDU geography is not treated as equivalent to NDIA Service Area.",
        }
    ]

