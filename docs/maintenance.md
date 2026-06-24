# Maintenance Guide

This project is a case-study app rather than a packaged software library, but it should still be maintained with clear boundaries.

## Active Runtime Path

The Streamlit app currently runs through:

```text
app/ndis_service_area_dashboard.py
```

That file is responsible for page composition and the current calculation flow. It imports:

- `gm_app_utils.py` for formatting, interpretation labels and chart styling.
- `gm_map.py` for the custom SVG atlas.

## Refactor Rules

Use these rules when moving code out of the dashboard file:

1. Move presentation-only helpers first. They are low risk and easy to test.
2. Move data-loading functions only after tests cover the expected columns and row counts.
3. Move benchmark functions only with tests for sign convention and weighting.
4. Keep Streamlit calls out of pure helper modules where possible.
5. Avoid retaining duplicate implementations after a refactor has passed tests.

## Calculation Conventions

- Benchmark gaps are `benchmark - observed`.
- Positive benchmark gaps mean the observed value is below the selected benchmark.
- Change measures are `selected quarter - reference quarter`.
- Service-category filtering is a payment-share proxy and must not be described as unique participant analysis.
- Australia in the service-area selector means the current national/filter scope, not an individual service-area record.

## Cleanup Rules

Move questionable files to `for_deletion/` before deleting them. Keep their original relative path under that folder so they can be restored.

Do not quarantine these without checking the app and notebook first:

- `app/ndis_service_area_dashboard.py`
- `app/gm_app_utils.py`
- `app/gm_map.py`
- `data/published/master_ndis_service_area_quarter_all_available_scoped.csv`
- `data/published/master_ndis_service_area_quarter_service_type_custom.csv`
- `outputs/powerbi_map/ndis_service_area_boundaries_simplified.geojson`
- `tests/`
- `notebooks/02_market_saturation_analysis.ipynb`
