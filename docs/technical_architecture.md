# Technical Architecture

## Overview

The project is organised as a small analytical product: curated CSV data, tested transformation logic, a Streamlit dashboard and a reproducible notebook. The architecture favours inspectability over abstraction because the project is a case-study prototype.

## Pipeline

```text
Public NDIS source extracts
        |
        v
Schema harmonisation and quarter alignment
        |
        v
Service-area-quarter master table
        |
        +----> Service-category payment table
        |
        v
Benchmark construction
        |
        v
Baseline change measures
        |
        v
Market-position typology
        |
        +----> Reproducible notebook analysis
        |
        +----> Streamlit dashboard
        |
        v
Geospatial join and SVG atlas rendering
```

## Key Files

- `app/ndis_service_area_dashboard.py`: active Streamlit application and calculation path used by the dashboard.
- `app/gm_app_utils.py`: presentation helpers for formatting, sign-convention interpretation, dynamic context labels and Altair styling.
- `app/gm_map.py`: SVG atlas renderer and metropolitan inset layout.
- `data/published/master_ndis_service_area_quarter_all_available_scoped.csv`: curated service-area-quarter dataset used by the app.
- `data/published/master_ndis_service_area_quarter_service_type_custom.csv`: curated service-category payment mix dataset.
- `notebooks/02_market_saturation_analysis.ipynb`: notebook version of the core analysis.
- `tests/test_metrics.py`: regression tests for key calculations.
- `tests/test_dashboard_logic.py`: regression tests for dashboard interpretation and payment-mix benchmark helpers.

## Module Boundaries

The active app follows a pragmatic modular structure:

- Data loading, benchmark calculation and view filtering live in the dashboard file while the data contract is still evolving.
- Presentation-only helpers live in `gm_app_utils.py` so chart labels and interpretation rules can be tested without Streamlit.
- The custom map renderer lives in `gm_map.py`, isolated from the rest of the app because geospatial rendering has different dependencies and failure modes.
- Notebook analysis uses the same curated published CSVs so exploratory review and dashboard behaviour remain aligned.

The remaining `gm_*` modules are retained as refactor candidates. They should either be adopted into the active app or removed in a future cleanup once the dashboard design stabilises.

## Design Principles

- Keep the app and notebook aligned around the same published data files.
- Prefer explicit benchmark definitions over black-box scores.
- Preserve service-area labels in visualisations where comparison is the analytical task.
- Treat service-category calculations as payment-share proxies rather than participant counts.
- Keep generated repair scripts, backups and rendered outputs outside the clean project surface.

## Known Refactor Opportunity

The next useful refactor would be to move active data-loading and benchmark functions from `ndis_service_area_dashboard.py` into a tested `gm_data_active.py` or equivalent module. That should be done carefully because the app currently contains the most up-to-date benchmark semantics.
