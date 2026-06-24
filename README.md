# NDIS Market Saturation Atlas

Applied data science and geospatial evidence prototype for Good Measure.

This repository demonstrates how public NDIS service-area data can be converted into a transparent market-saturation atlas. The project combines quarterly administrative data, population denominators, benchmark construction, service-category payment-mix analysis and geospatial rendering into a Streamlit decision-support app.

The intended audience is policy, strategy and service-design teams who need to identify places where plan coverage, utilisation or service-category mix appears materially different from an interpretable benchmark.

## Analytical Question

Where do NDIS service areas appear below, near or above selected benchmarks for plan coverage, plan utilisation and service-category payment mix?

The atlas is exploratory. It highlights areas for further local interpretation; it does not prove unmet need, provider shortage, oversupply, service quality or causal impact.

## Analytical Positioning

This is written as an applied postgraduate data science project: the work is explicit about data grain, benchmark definitions, proxy measures and limitations. The goal is not to optimise a predictive model, but to demonstrate a defensible evidence workflow from public administrative data to a usable analytical product.

The main judgement call is methodological rather than technical: service-area saturation cannot be observed directly from the available public data. The project therefore uses transparent proxy measures and keeps the interpretation cautious.

## What The Project Shows

- Schema harmonisation across quarterly NDIS service-area extracts.
- Construction of service-area-quarter analysis tables.
- National, remoteness-category and historical benchmark comparisons.
- Baseline change measures for plan coverage and utilisation.
- Payment-share proxy modelling for service-category analysis.
- Geospatial joining and SVG atlas rendering for Australian service areas.
- Interactive Streamlit views for atlas, trends, ranked areas, service-area detail and data QA.
- Unit tests for the key benchmark and proxy calculations.

## Repository Layout

```text
app/
  ndis_service_area_dashboard.py   Streamlit application entry point.
  gm_app_utils.py                  Formatting, interpretation and chart-theme helpers.
  gm_map.py                        Custom SVG atlas renderer.
  gm_*.py                          Modular helpers retained for ongoing refactor work.

data/published/
  master_ndis_service_area_quarter_all_available_scoped.csv
  master_ndis_service_area_quarter_service_type_custom.csv

docs/
  method.md                        Analytical method and limitations.
  technical_architecture.md        Pipeline architecture.
  maintenance.md                   Refactor and cleanup conventions.
  cleanup_plan.md                  Junk-file quarantine and future cleanup guidance.
  *_audit.csv                      Build and QA audit outputs.

notebooks/
  02_market_saturation_analysis.ipynb

tests/
  test_metrics.py                  Calculation tests.
```

## Review Path

For a fast review of the project, read the files in this order:

1. `README.md` for the project question and operating assumptions.
2. `docs/method.md` for definitions, benchmark logic and limitations.
3. `docs/reproducibility.md` for the run and artefact policy.
4. `docs/maintenance.md` for refactor and cleanup conventions.
5. `notebooks/02_market_saturation_analysis.ipynb` for the reproducible analysis flow.
6. `tests/test_metrics.py` for calculation safeguards.
7. `app/ndis_service_area_dashboard.py` for the interactive product implementation.

## Run Locally

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Run the dashboard:

```powershell
python -m streamlit run app\ndis_service_area_dashboard.py
```

Run tests:

```powershell
python -m pytest -q
```

## Reproducible Analysis

The notebook [notebooks/02_market_saturation_analysis.ipynb](notebooks/02_market_saturation_analysis.ipynb) provides a non-Streamlit walkthrough of the data model:

1. Load the curated published datasets.
2. Validate expected columns and quarters.
3. Recreate benchmark gaps.
4. Summarise service-area and remoteness patterns.
5. Inspect service-category payment mix.
6. Export compact review tables for further analysis.

## Method Summary

Plan coverage is calculated as funded plans per 1,000 people using 2025 estimated resident population. Utilisation is retained as the published mean utilisation measure for the service area. Benchmark gaps are reported as benchmark value minus observed value, so positive gaps indicate an area is below the selected benchmark.

Service-category analysis uses payment share as a proxy for support intensity. It should not be interpreted as a unique participant count or the percentage of plans containing a support category.

## Interpretation Discipline

The dashboard uses simple visual language because the evidence is already layered: geography, quarter, benchmark, remoteness and service category. A high benchmark gap should be read as a prompt for investigation, not as a conclusion. Appropriate follow-up would include local provider context, participant demographics, plan-management patterns, workforce availability and qualitative service intelligence.

## Current Status

This is a case-study prototype, not a production statistical release. The core analytical calculations are test-covered, while the app remains intentionally transparent and inspectable for review.
