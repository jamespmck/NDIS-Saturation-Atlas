# gmdata.au Publication Guide

This guide covers the handoff from local Tableau Public authoring to publishing on `gmdata.au`.

## Publication Standard

The public page should present the NDIS Saturation Atlas as both a data science project and a practical decision-support tool. A website-ready version must show:

- the geospatial atlas as the primary first view;
- service-area click-through into a filtered detail dashboard;
- quarter-by-quarter benchmarking of funding, funded plans, utilisation and provider activity;
- support-type views that compare local demand and payment mix with national and remoteness benchmarks;
- rankings that identify potential business opportunities, under-served areas, under-funded areas and advocacy priorities;
- simple projected future metrics, clearly labelled as momentum proxies rather than forecasts;
- visible methodology and limitation notes so readers can understand what the public data can and cannot prove.

## Publication Flow

1. Rebuild the data:

   ```powershell
   python -m src.run_pipeline --stage all
   python -m src.rebuild_tableau_workbook --promote
   python -m src.tableau_workbook_review --fail-on-critical
   python -m pytest -q
   ```

2. Open Tableau Public and open the regenerated workbook:

   ```text
   outputs/tableau/NDIS-Saturation-Atlas.twb
   ```

3. QA the generated dashboard tabs using `docs/tableau_authoring_guide.md`.

4. Publish the workbook to Tableau Public.

5. Copy the published workbook URL base from Tableau Public.

6. Replace `REPLACE_WITH_PUBLISHED_WORKBOOK` in the `gmdata.au` project page or in `docs/gmdata_tableau_embed_snippet.html`.

## Responsive Publication Workaround

If Tableau Public raises `Error Code: 2805CF18` while adding phone layouts, do not use Device Preview for this workbook. Publish separate monitor, tablet and phone dashboards instead.

Generated Tableau dashboards:

- Atlas monitor dashboard: `NDIS Saturation Atlas Monitor`, fixed size around `1600 x 940`, map-only.
- Atlas tablet dashboard: `NDIS Saturation Atlas Tablet`, fixed size around `900 x 760`, map-only.
- Atlas phone dashboard: `NDIS Saturation Atlas Phone`, fixed size around `390 x 520`, map-only.
- National monitor dashboard: `NDIS Saturation National Monitor`, fixed size around `1600 x 1120`.
- National tablet dashboard: `NDIS Saturation National Tablet`, fixed size around `900 x 1580`.
- National phone dashboard: `NDIS Saturation National Phone`, fixed size around `390 x 2260`.
- Monitor service-area dashboard: `NDIS Saturation Service Area Monitor`, fixed size around `1600 x 1180`.
- Tablet service-area dashboard: `NDIS Saturation Service Area Tablet`, fixed size around `900 x 1780`.
- Phone service-area dashboard: `NDIS Saturation Service Area Phone`, fixed size around `390 x 2500`.
- Opportunities monitor dashboard: `NDIS Saturation Opportunities Monitor`, fixed size around `1600 x 1280`.
- Opportunities tablet dashboard: `NDIS Saturation Opportunities Tablet`, fixed size around `900 x 1960`.
- Opportunities phone dashboard: `NDIS Saturation Opportunities Phone`, fixed size around `390 x 2760`.
- Build each as a normal dashboard, not as a Tableau device layout.
- The standalone atlas dashboards should contain only `Atlas Map`.
- Keep KPI, opportunity, advocacy and service-type worksheets in the overview, service-area and rankings dashboards:
  - `Headline KPIs`
  - `Atlas Map`
  - `Opportunity Matrix`
  - `Opportunity Priority`
  - `Advocacy Gaps`
  - `Provider Underservice`
  - `Service Type Opportunities`
  - `Utilisation Trend`
  - `Funded Plan Saturation Trend`
  - `Evidence Table`
  - `Data Quality Flags`

The embed snippet switches between the monitor, tablet and phone Tableau views with CSS. This avoids Tableau's failing device-layout generator and gives `gmdata.au` explicit control over the responsive presentation.

## Website Copy

Short title:

```text
NDIS Saturation Atlas
```

Short description:

```text
A multidimensional atlas of NDIS business opportunity, advocacy priority, funded demand, purchasing, utilisation, provider activity, support-type mix and market-performance signals across Australian service areas.
```

Portfolio positioning:

```text
This project demonstrates an end-to-end public-data workflow: source assessment, reproducible transformation, benchmark design, geospatial analysis, opportunity scoring, Tableau publication and web embedding. It is designed to help providers, peak bodies and consumer groups explore where funding, utilisation, provider activity and service-type demand diverge from national and remoteness peers.
```

Interpretation note:

```text
The atlas is exploratory. It highlights places where NDIS market indicators differ from national or remoteness benchmarks, but it does not prove unmet need, provider shortage, oversupply, service quality or causation.
```

## Recommended Page Structure

- Introductory paragraph and interpretation note.
- Embedded Tableau Public dashboard.
- Method summary with link to `metadata/methodology_notes.md`.
- Data freshness and limitations.
- Download links for selected CSVs or a repository link, if appropriate.

## Refresh Checklist

- Run `python -m src.run_pipeline --stage all`.
- Run `python -m src.rebuild_tableau_workbook --promote`.
- Run `python -m src.tableau_workbook_review --fail-on-critical`.
- Check `data/audits/final_build_report.md`.
- Check `data/audits/tableau_dashboard_implementation_review.md`.
- Check warnings in `data/tableau/tableau_data_quality.csv`.
- Reopen Tableau Public workbook and refresh data sources.
- Republish to Tableau Public.
- Confirm the embedded dashboard on `gmdata.au` still loads.

## Notes On Tableau Public Embedding

The `gmdata.au` project page now uses Tableau's Embedding API v3 through `assets/js/ndis-tableau.js`.

The page is inert while `data-tableau-base` contains `REPLACE_WITH_PUBLISHED_WORKBOOK`. After publishing, replace the placeholder with the Tableau Public workbook URL base, for example:

```text
https://public.tableau.com/views/YourPublishedWorkbookName
```

The website embed presents:

- the standalone geospatial atlas first;
- a national dashboard for headline KPIs, national trends, support mix, remoteness and quality context;
- a hidden service-area detail panel that appears after a map mark is selected;
- an opportunities dashboard for utilisation, saturation, provider activity, opportunity signals, advocacy signals, service-type demand and evidence checks.

The embed script listens for a mark selection in the desktop atlas view and applies the selected service-area value to the detail dashboard views where Tableau exposes a matching `Geography Name`, `Ndis Service Area`, `NDIS Service Area` or `Name` field.
