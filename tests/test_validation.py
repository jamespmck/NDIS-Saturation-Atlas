import pandas as pd
import pytest

from src.validation import raise_for_critical_failures, validate_outputs


def test_duplicate_tableau_keys_are_critical():
    frame = pd.DataFrame(
        {
            "quarter": ["2025Q4", "2025Q4"],
            "geography_type": ["ndia_service_area", "ndia_service_area"],
            "geography_code": ["ACT", "ACT"],
            "population_count": [1, 1],
            "funded_plan_count": [1, 1],
            "mean_plan_utilisation": [0.7, 0.7],
        }
    )
    quality = validate_outputs({"tableau_market_quarter": frame})
    duplicate = quality.loc[quality["issue_type"].eq("duplicate_keys")].iloc[0]
    assert duplicate["issue_severity"] == "critical"
    with pytest.raises(ValueError):
        raise_for_critical_failures(quality)


def test_negative_counts_are_critical():
    frame = pd.DataFrame(
        {
            "quarter": ["2025Q4"],
            "geography_type": ["ndia_service_area"],
            "geography_code": ["ACT"],
            "population_count": [100],
            "funded_plan_count": [-1],
            "mean_plan_utilisation": [0.7],
        }
    )
    quality = validate_outputs({"tableau_market_quarter": frame})
    negative = quality.loc[
        (quality["field"].eq("funded_plan_count")) & (quality["issue_type"].eq("negative_value"))
    ].iloc[0]
    assert negative["issue_severity"] == "critical"

