from __future__ import annotations

import pandas as pd

from . import config


def build_workforce() -> pd.DataFrame:
    """Return a schema-valid workforce table when local sources are absent."""

    return pd.DataFrame(
        columns=[
            "geography_type",
            "geography_code",
            "source_year",
            "occupation",
            "workforce_count",
            "workforce_per_10000_population",
            "workforce_growth_rate",
            "shortage_indicator",
            "source_name",
            "reliability_flag",
            "limitation_note",
        ]
    )


def workforce_source_gap_quality_rows() -> list[dict]:
    return [
        {
            "dataset": "workforce_public_sources",
            "period": "latest available",
            "geography": "source geography",
            "field": "",
            "issue_type": "missing_source",
            "issue_severity": "warning",
            "missingness": 1,
            "suppression": "",
            "mapping_status": "not_processed",
            "reliability_flag": config.RELIABILITY_FLAGS["unavailable"],
            "explanatory_note": "No official workforce extract is available locally; broad occupation counts will not be presented as NDIS-only workforce.",
        }
    ]

