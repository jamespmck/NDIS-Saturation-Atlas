from src.analyse_tableau_outputs import run_analysis


def test_analysis_outputs_include_typed_website_kpis():
    outputs = run_analysis()
    kpis = outputs["analysis_website_kpis"]
    assert {"kpi", "value_number", "value_text", "unit"}.issubset(kpis.columns)
    assert "latest_quarter" in set(kpis["kpi"])
    assert "funded_plan_count" in set(kpis["kpi"])
    assert not outputs["analysis_latest_market_rankings"].empty

