# Reproducibility Note

This project is organised so the analytical claims can be reviewed without running the full raw-data acquisition pipeline.

## Curated Inputs

The dashboard and notebook use two curated published files:

- `data/published/master_ndis_service_area_quarter_all_available_scoped.csv`
- `data/published/master_ndis_service_area_quarter_service_type_custom.csv`

These files are treated as the stable modelling layer for the case study.

## Main Reproducibility Checks

Run the unit tests:

```powershell
python -m pytest
```

Open or execute the notebook:

```text
notebooks/02_market_saturation_analysis.ipynb
```

Run the app:

```powershell
python -m streamlit run app\ndis_service_area_dashboard.py
```

## Generated Outputs

Files under `outputs/` are generated artefacts. They can be useful for inspection but should not be treated as primary source code. The exception is the simplified boundary GeoJSON used by the atlas renderer:

```text
outputs/powerbi_map/ndis_service_area_boundaries_simplified.geojson
```

## What Has Been Deliberately Excluded

Local repair scripts, app backups, failed render attempts, bytecode caches and temporary Streamlit logs have been removed or ignored. They were useful during development but obscure the final analytical workflow.
