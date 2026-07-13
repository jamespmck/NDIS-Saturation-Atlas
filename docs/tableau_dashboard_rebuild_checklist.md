# Tableau Dashboard Rebuild Checklist

Use this workbook as the rebuild source:

- `outputs/tableau/NDIS-Saturation-Atlas.twb`

The workbook includes generated dashboard tabs that use normal fixed-size dashboards, not Tableau device layouts. The current implementation embeds the atlas, service-area detail, ranking, opportunity, advocacy, provider and service-type worksheets in the dashboard shells.

## Website-Ready Acceptance Criteria

Treat this workbook as publication-ready only when it demonstrates the full project story, not merely when the tabs open. The Tableau experience should show the NDIS Saturation Atlas as:

- a portfolio-grade data science case study built from public NDIS data;
- a geospatial decision tool for service-area exploration;
- a benchmarking tool for organisations and consumer groups comparing local funding, funded plans, utilisation, provider saturation and support-type payment mix against national medians and remoteness means;
- an opportunity triage tool that surfaces possible provider opportunities, under-served markets, under-funded areas and advocacy priorities;
- a quarterly trend tool that lets readers inspect how these signals change over time;
- a cautious projection tool that labels future metrics as simple momentum proxies, not statistical forecasts.

The website version should make the standalone atlas the first view. The standalone atlas dashboards should be map-only: no KPI strip, rankings, opportunity tables or surrounding blank cells. Selecting a service area should load or reveal the service-area dashboard filtered to that area. Ranking dashboards should support review by utilisation, saturation, provider activity, business opportunity, advocacy opportunity, under-funding and service type.

## Current Generated Dashboards

| Dashboard | Size | Main purpose |
| --- | --- | --- |
| `NDIS Saturation Monitor` | `1600 x 1068` | Overview: atlas, market position, funded-plan saturation, utilisation trend, ranked service areas and support mix. |
| `NDIS Saturation Tablet` | `900 x 1222` | Tablet overview using the same stable worksheet sequence. |
| `NDIS Saturation Phone` | `390 x 1774` | Mobile overview using a stacked worksheet sequence. |
| `NDIS Saturation Atlas Monitor` | `1600 x 940` | Standalone map-only atlas. |
| `NDIS Saturation Atlas Tablet` | `900 x 760` | Tablet map-only atlas. |
| `NDIS Saturation Atlas Phone` | `390 x 520` | Mobile map-only atlas. |
| `NDIS Saturation Service Area Monitor` | `1600 x 1208` | Click-through detail view for one selected service area. |
| `NDIS Saturation Service Area Tablet` | `900 x 1856` | Tablet service-area detail view. |
| `NDIS Saturation Service Area Phone` | `390 x 2470` | Mobile service-area detail view. |
| `NDIS Saturation Rankings Monitor` | `1600 x 1268` | Rankings for utilisation gaps, saturation, provider activity, market position, evidence and quality. |
| `NDIS Saturation Rankings Tablet` | `900 x 1976` | Tablet rankings view. |
| `NDIS Saturation Rankings Phone` | `390 x 2720` | Mobile rankings view. |

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
- Confirm Presentation Mode opens on the atlas, detail and rankings monitor dashboards.
- Do not add Tableau device layouts; publish the separate monitor, tablet and phone dashboard tabs.
- After publishing, test atlas click-through on `gmdata.au`.

<!-- Historical pre-opportunity layout kept only for repository context.

Use this workbook as the rebuild source:

- `outputs/tableau/NDIS-Saturation-Atlas.twb`

It contains the polished worksheets only. Recreate dashboards inside Tableau Public using the UI, then save the workbook under a new name.

## Dashboard 1: NDIS Saturation Monitor

Fixed size: `1600 x 1068`

| Sheet | X | Y | W | H |
| --- | ---: | ---: | ---: | ---: |
| Headline KPIs | 24 | 24 | 1552 | 112 |
| Atlas Map | 24 | 160 | 952 | 560 |
| Market Position | 1000 | 160 | 576 | 268 |
| Funded Plan Saturation Trend | 1000 | 452 | 576 | 268 |
| Utilisation Trend | 24 | 744 | 756 | 300 |
| Ranked Service Areas | 804 | 744 | 374 | 300 |
| Support Type Mix | 1202 | 744 | 374 | 300 |

## Dashboard 2: NDIS Saturation Tablet

Fixed size: `900 x 1222`

| Sheet | X | Y | W | H |
| --- | ---: | ---: | ---: | ---: |
| Headline KPIs | 20 | 20 | 860 | 126 |
| Atlas Map | 20 | 166 | 860 | 420 |
| Market Position | 20 | 606 | 420 | 288 |
| Funded Plan Saturation Trend | 460 | 606 | 420 | 288 |
| Utilisation Trend | 20 | 914 | 420 | 288 |
| Ranked Service Areas | 460 | 914 | 420 | 288 |

## Dashboard 3: NDIS Saturation Phone

Fixed size: `390 x 1774`

| Sheet | X | Y | W | H |
| --- | ---: | ---: | ---: | ---: |
| Headline KPIs | 14 | 14 | 362 | 150 |
| Atlas Map | 14 | 180 | 362 | 330 |
| Market Position | 14 | 526 | 362 | 270 |
| Utilisation Trend | 14 | 812 | 362 | 280 |
| Funded Plan Saturation Trend | 14 | 1108 | 362 | 280 |
| Ranked Service Areas | 14 | 1404 | 362 | 356 |

## Dashboard 4: NDIS Saturation Service Area Monitor

Fixed size: `1600 x 1208`

| Sheet | X | Y | W | H |
| --- | ---: | ---: | ---: | ---: |
| Headline KPIs | 24 | 24 | 1552 | 112 |
| Utilisation Trend | 24 | 160 | 756 | 310 |
| Funded Plan Saturation Trend | 804 | 160 | 772 | 310 |
| Benchmark Gaps | 24 | 494 | 504 | 310 |
| Support Type Mix | 552 | 494 | 504 | 310 |
| Provider Data Availability | 1080 | 494 | 496 | 310 |
| Evidence Table | 24 | 828 | 1032 | 356 |
| Data Quality Flags | 1080 | 828 | 496 | 356 |

## Dashboard 5: NDIS Saturation Service Area Tablet

Fixed size: `900 x 1856`

| Sheet | X | Y | W | H |
| --- | ---: | ---: | ---: | ---: |
| Headline KPIs | 20 | 20 | 860 | 126 |
| Utilisation Trend | 20 | 166 | 860 | 300 |
| Funded Plan Saturation Trend | 20 | 486 | 860 | 300 |
| Benchmark Gaps | 20 | 806 | 420 | 310 |
| Support Type Mix | 460 | 806 | 420 | 310 |
| Provider Data Availability | 20 | 1136 | 420 | 300 |
| Data Quality Flags | 460 | 1136 | 420 | 300 |
| Evidence Table | 20 | 1456 | 860 | 380 |

## Dashboard 6: NDIS Saturation Service Area Phone

Fixed size: `390 x 2470`

| Sheet | X | Y | W | H |
| --- | ---: | ---: | ---: | ---: |
| Headline KPIs | 14 | 14 | 362 | 150 |
| Utilisation Trend | 14 | 180 | 362 | 290 |
| Funded Plan Saturation Trend | 14 | 486 | 362 | 290 |
| Benchmark Gaps | 14 | 792 | 362 | 318 |
| Support Type Mix | 14 | 1126 | 362 | 318 |
| Provider Data Availability | 14 | 1460 | 362 | 286 |
| Data Quality Flags | 14 | 1762 | 362 | 286 |
| Evidence Table | 14 | 2064 | 362 | 392 |

## Dashboard 7: NDIS Saturation Atlas Monitor

Fixed size: `1600 x 1248`

| Sheet | X | Y | W | H |
| --- | ---: | ---: | ---: | ---: |
| Headline KPIs | 24 | 24 | 1552 | 112 |
| Atlas Map | 24 | 160 | 1552 | 780 |
| Market Classification | 24 | 964 | 500 | 260 |
| Remoteness Summary | 548 | 964 | 500 | 260 |
| Data Quality Flags | 1072 | 964 | 504 | 260 |

## Dashboard 8: NDIS Saturation Atlas Tablet

Fixed size: `900 x 1406`

| Sheet | X | Y | W | H |
| --- | ---: | ---: | ---: | ---: |
| Headline KPIs | 20 | 20 | 860 | 126 |
| Atlas Map | 20 | 166 | 860 | 620 |
| Market Classification | 20 | 806 | 420 | 300 |
| Remoteness Summary | 460 | 806 | 420 | 300 |
| Data Quality Flags | 20 | 1126 | 860 | 260 |

## Dashboard 9: NDIS Saturation Atlas Phone

Fixed size: `390 x 1558`

| Sheet | X | Y | W | H |
| --- | ---: | ---: | ---: | ---: |
| Headline KPIs | 14 | 14 | 362 | 150 |
| Atlas Map | 14 | 180 | 362 | 430 |
| Market Classification | 14 | 626 | 362 | 300 |
| Remoteness Summary | 14 | 942 | 362 | 300 |
| Data Quality Flags | 14 | 1258 | 362 | 286 |

## Dashboard 10: NDIS Saturation Rankings Monitor

Fixed size: `1600 x 1268`

| Sheet | X | Y | W | H |
| --- | ---: | ---: | ---: | ---: |
| Headline KPIs | 24 | 24 | 1552 | 112 |
| Ranked Service Areas | 24 | 160 | 500 | 760 |
| Benchmark Gaps | 548 | 160 | 500 | 360 |
| Provider Data Availability | 1072 | 160 | 504 | 360 |
| Market Position | 548 | 544 | 500 | 376 |
| Market Classification | 1072 | 544 | 504 | 376 |
| Evidence Table | 24 | 944 | 1032 | 300 |
| Data Quality Flags | 1080 | 944 | 496 | 300 |

## Dashboard 11: NDIS Saturation Rankings Tablet

Fixed size: `900 x 1976`

| Sheet | X | Y | W | H |
| --- | ---: | ---: | ---: | ---: |
| Headline KPIs | 20 | 20 | 860 | 126 |
| Ranked Service Areas | 20 | 166 | 860 | 420 |
| Benchmark Gaps | 20 | 606 | 420 | 330 |
| Provider Data Availability | 460 | 606 | 420 | 330 |
| Market Position | 20 | 956 | 420 | 330 |
| Market Classification | 460 | 956 | 420 | 330 |
| Evidence Table | 20 | 1306 | 860 | 360 |
| Data Quality Flags | 20 | 1686 | 860 | 270 |

## Dashboard 12: NDIS Saturation Rankings Phone

Fixed size: `390 x 2720`

| Sheet | X | Y | W | H |
| --- | ---: | ---: | ---: | ---: |
| Headline KPIs | 14 | 14 | 362 | 150 |
| Ranked Service Areas | 14 | 180 | 362 | 430 |
| Benchmark Gaps | 14 | 626 | 362 | 330 |
| Provider Data Availability | 14 | 972 | 362 | 320 |
| Market Position | 14 | 1308 | 362 | 320 |
| Market Classification | 14 | 1644 | 362 | 320 |
| Evidence Table | 14 | 1980 | 362 | 390 |
| Data Quality Flags | 14 | 2386 | 362 | 320 |

## Rebuild Notes

- Generated TWBs must use dashboard windows in the `viewpoints`, `active`, `device-preview`, `simple-id` shape. Do not use worksheet-style dashboard windows with `cards` and a single `viewpoint`.
- Use fixed-size dashboards.
- Set dashboard background to `#f5f7fb` or a similarly soft off-white.
- The website handles atlas-to-detail click-through with Tableau's Embedding API after publication.
- After regenerating, test opening the dashboard tabs and entering Presentation Mode before publishing.
-->
