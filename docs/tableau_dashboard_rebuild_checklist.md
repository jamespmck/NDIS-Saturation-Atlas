# Tableau Dashboard Rebuild Checklist

Use this workbook as the rebuild source:

- `outputs/tableau/NDIS-Saturation-Atlas.twb`

The workbook includes generated dashboard tabs that use normal fixed-size dashboards, not Tableau device layouts. The current implementation follows the Streamlit-style flow: standalone atlas, national summary, service-area detail and opportunities/advocacy.

## Website-Ready Acceptance Criteria

Treat this workbook as publication-ready only when it demonstrates the full project story, not merely when the tabs open. The Tableau experience should show the NDIS Saturation Atlas as:

- a portfolio-grade data science case study built from public NDIS data;
- a geospatial decision tool for service-area exploration;
- a benchmarking tool for organisations and consumer groups comparing local funding, funded plans, utilisation, provider saturation and support-type payment mix against national medians and remoteness means;
- an opportunity triage tool that surfaces possible provider opportunities, under-served markets, under-funded areas and advocacy priorities;
- a quarterly trend tool that lets readers inspect how these signals change over time;
- a cautious projection tool that labels future metrics as simple momentum proxies, not statistical forecasts.

The website version should make the standalone atlas the first view. The standalone atlas dashboards should be map-only: no KPI strip, rankings, opportunity tables or surrounding blank cells. The atlas geometry should include metro inset panels and should exclude Lord Howe Island and Norfolk Island if they appear in a future source. Selecting a service area should load or reveal the service-area dashboard filtered to that area. Opportunities dashboards should support review by utilisation, saturation, provider activity, business opportunity, advocacy opportunity, under-funding and service type.

## Current Generated Dashboards

| Dashboard | Size | Main purpose |
| --- | --- | --- |
| `NDIS Saturation Atlas Monitor` | `1600 x 940` | Standalone map-only atlas. |
| `NDIS Saturation Atlas Tablet` | `900 x 760` | Tablet map-only atlas. |
| `NDIS Saturation Atlas Phone` | `390 x 520` | Mobile map-only atlas. |
| `NDIS Saturation National Monitor` | `1600 x 1120` | National KPI, trend, support mix, remoteness and quality context. |
| `NDIS Saturation National Tablet` | `900 x 1580` | Tablet national summary. |
| `NDIS Saturation National Phone` | `390 x 2260` | Mobile national summary. |
| `NDIS Saturation Service Area Monitor` | `1600 x 1180` | Click-through detail view for one selected service area. |
| `NDIS Saturation Service Area Tablet` | `900 x 1780` | Tablet service-area detail view. |
| `NDIS Saturation Service Area Phone` | `390 x 2500` | Mobile service-area detail view. |
| `NDIS Saturation Opportunities Monitor` | `1600 x 1280` | Opportunity, advocacy, service-type and evidence review. |
| `NDIS Saturation Opportunities Tablet` | `900 x 1960` | Tablet opportunity view. |
| `NDIS Saturation Opportunities Phone` | `390 x 2760` | Mobile opportunity view. |

## Required Worksheets

- `Atlas Map`
- `Headline KPIs`
- `Market Position`
- `Ranked Service Areas`
- `Support Type Mix`
- `Benchmark Gaps`
- `Provider Data Availability`
- `Market Classification`
- `Remoteness Summary`
- `Utilisation Trend`
- `Funded Plan Saturation Trend`
- `Evidence Table`
- `Data Quality Flags`

## QA Steps

- Rebuild the dashboard implementation if needed:
  `python -m src.rebuild_tableau_workbook --promote`
- Run the automated implementation review:
  `python -m src.tableau_workbook_review --fail-on-critical`
- Open `outputs/tableau/NDIS-Saturation-Atlas.twb` in Tableau Public.
- Confirm the atlas and original dashboard worksheets render.
- Confirm the standalone atlas dashboards contain only the atlas map, with no blank cells around the map.
- Confirm the opportunity worksheets render inside the dashboard shells.
- Confirm the final dashboard set satisfies the website-ready acceptance criteria above.
- Confirm each dashboard tab opens without `2805CF18`.
- Confirm Presentation Mode opens on the atlas, national, detail and opportunities monitor dashboards.
- Do not add Tableau device layouts; publish the separate monitor, tablet and phone dashboard tabs.
- After publishing, test atlas click-through on `gmdata.au`.

## Rebuild Notes

- Generated TWBs must use dashboard windows in the `viewpoints`, `active`, `device-preview`, `simple-id` shape.
- Use fixed-size dashboards, not Tableau device layouts.
- The website handles atlas-to-detail click-through with Tableau's Embedding API after publication.
- After regenerating, test opening the dashboard tabs and entering Presentation Mode before publishing.
