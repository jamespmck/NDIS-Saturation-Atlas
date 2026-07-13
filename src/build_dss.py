from __future__ import annotations

import pandas as pd

from . import config


def build_dss() -> pd.DataFrame:
    """Return a schema-valid DSS payment table when local sources are absent."""

    return pd.DataFrame(
        columns=[
            "geography_type",
            "geography_code",
            "reference_period",
            "payment_type",
            "recipient_count",
            "population_denominator_count",
            "recipient_rate",
            "source_name",
            "reliability_flag",
            "limitation_note",
        ]
    )


def dss_source_gap_quality_rows() -> list[dict]:
    return [
        {
            "dataset": "dss_payment_data",
            "period": "latest available",
            "geography": "source geography",
            "field": "",
            "issue_type": "missing_source",
            "issue_severity": "warning",
            "missingness": 1,
            "suppression": "",
            "mapping_status": "not_processed",
            "reliability_flag": config.RELIABILITY_FLAGS["unavailable"],
            "explanatory_note": "No official DSS payment-recipient extract is available locally.",
        }
    ]

