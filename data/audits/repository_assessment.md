# Repository Assessment

## Reusable

- `data/published/master_ndis_service_area_quarter_all_available_scoped.csv`: current local service-area-quarter source.
- `data/published/master_ndis_service_area_quarter_service_type_custom.csv`: current local service-type payment source.
- `data/processed/historical_ndis_service_area_quarter_2022q4_2025q2_extracted.csv`: historical participant and plan-value context for overlapping quarters.
- `data/processed/service_area_population_2025_erp.csv`: 2025 ERP service-area denominator.
- `data/processed/service_area_geography_context_2021_2025.csv` and remoteness tables: local geography context.
- `outputs/powerbi_map/ndis_service_area_boundaries_simplified.geojson`: Tableau geometry source.
- `app/gm_benchmarks.py`, `app/gm_data.py`, `app/gm_validation.py`: legacy calculation references.

## Obsolete Or Presentation-Specific

- Streamlit files in `app/` remain preserved but are no longer the primary publication layer.
- Notebook analysis remains exploratory and is not the production pipeline.
- Existing `data/published/` outputs are reused as local inputs where reliable, but the pipeline rebuilds Tableau outputs and validation artefacts from them.

## Missing Local Source Domains

Census, SEIFA, DSS, PHIDU, workforce and broader housing/SDA context inputs are not present locally. The pipeline records these gaps in `tableau_data_quality.csv` and `metadata/source_register.csv`.

