import pandas as pd

from src.build_features import build_market_classification
from src.build_ndia import build_market_quarter, build_support_type_quarter
from src.build_tableau_outputs import build_tableau_outputs


def test_market_quarter_has_unique_tableau_key():
    market = build_market_quarter()
    assert not market.empty
    assert not market.duplicated(["quarter", "geography_type", "geography_code"]).any()
    assert {"funding_conversion_rate", "unspent_committed_funding", "supply_response_gap"}.issubset(market.columns)


def test_support_type_location_quotient_formula():
    support = build_support_type_quarter()
    sample = support.loc[
        support["local_support_share"].notna()
        & support["national_support_share"].notna()
        & (support["national_support_share"] != 0)
    ].head(50)
    calculated = sample["local_support_share"] / sample["national_support_share"]
    pd.testing.assert_series_equal(
        sample["support_location_quotient"].reset_index(drop=True).round(10),
        calculated.reset_index(drop=True).round(10),
        check_names=False,
    )


def test_market_classification_preserves_market_key():
    market = build_market_quarter()
    classification = build_market_classification(market)
    assert len(classification) == len(market)
    assert not classification.duplicated(["quarter", "geography_type", "geography_code"]).any()
    assert "persistent_utilisation_classification" in classification.columns


def test_tableau_outputs_include_opportunity_scores():
    market = build_market_quarter()
    support = build_support_type_quarter()
    outputs, _ = build_tableau_outputs(market, support)

    market_out = outputs["tableau_market_quarter"]
    support_out = outputs["tableau_support_type_quarter"]
    assert {
        "business_opportunity_score",
        "advocacy_opportunity_score",
        "underfunded_advocacy_score",
        "underserviced_provider_score",
        "opportunity_segment",
    }.issubset(market_out.columns)
    assert {
        "support_payment_gap_from_remoteness_benchmark",
        "support_undersupply_score",
        "service_type_opportunity_score",
        "service_type_opportunity_segment",
    }.issubset(support_out.columns)

    for field in [
        "business_opportunity_score",
        "advocacy_opportunity_score",
        "combined_opportunity_score",
        "support_undersupply_score",
        "service_type_opportunity_score",
    ]:
        frame = market_out if field in market_out.columns else support_out
        values = pd.to_numeric(frame[field], errors="coerce").dropna()
        assert not values.empty
        assert values.between(0, 1).all()
