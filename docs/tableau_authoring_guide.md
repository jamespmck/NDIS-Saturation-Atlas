# Tableau Authoring Guide

This guide translates the pipeline outputs in `data/tableau/` into a Tableau Public workbook.

## Data Sources

Local Tableau Public executable found on this machine:

```powershell
& "C:\Program Files\Tableau\Tableau Public 2026.2\bin\tabpublic.exe"
```

Connect to these CSV files:

- `data/tableau/tableau_market_quarter.csv`
- `data/tableau/tableau_support_type_quarter.csv`
- `data/tableau/tableau_community_context.csv`
- `data/tableau/tableau_market_classification.csv`
- `data/tableau/tableau_geography_lookup.csv`
- `data/tableau/tableau_data_quality.csv`

Connect to this spatial file separately:

- `data/tableau/geometry_ndia_service_area.geojson`

## Relationships

Use relationships, not physical joins, so Tableau can preserve each table's grain.

| Left table | Right table | Relationship fields |
| --- | --- | --- |
| `tableau_market_quarter` | `tableau_geography_lookup` | `geography_type`, `geography_code` |
| `tableau_market_quarter` | `tableau_market_classification` | `quarter`, `geography_type`, `geography_code` |
| `tableau_market_quarter` | `tableau_community_context` | `geography_type`, `geography_code` |
| `tableau_market_quarter` | `tableau_support_type_quarter` | `quarter`, `geography_type`, `geography_code` |
| `geometry_ndia_service_area` | `tableau_geography_lookup` | `ndis_service_area` or `map_key` to `geography_code` |

Keep `tableau_data_quality` as a separate QA sheet source unless you need dashboard-visible quality flags.

## Core Calculated Fields

Most important calculations are already exported. If recreated in Tableau, use these definitions:

```text
Funding Conversion Rate = SUM([payment_amount]) / SUM([committed_supports])
Unspent Funding Per Funded Plan = SUM([unspent_committed_funding]) / SUM([funded_plan_count])
Active Providers Per 1,000 Funded Plans = SUM([active_provider_count]) / SUM([funded_plan_count]) * 1000
Support Location Quotient = SUM([payments]) / SUM([area_total_payments]) / ATTR([national_support_share])
Support Payment Gap From Remoteness Benchmark = SUM([area_total_payments]) * AVG([remoteness_benchmark]) - SUM([payments])
```

Avoid averaging rates across geographies. Aggregate numerators and denominators first.

Opportunity scores are exported by the pipeline and should normally be used directly:

- `business_opportunity_score`
- `advocacy_opportunity_score`
- `underfunded_advocacy_score`
- `underserviced_provider_score`
- `combined_opportunity_score`
- `support_undersupply_score`
- `service_type_opportunity_score`

These scores are quarter-relative 0-1 proxy scores. They are ranking and triage signals, not proof of unmet need or a revenue forecast.

## Suggested Workbook Structure

1. Atlas Map
   - Geography: service-area geometry.
   - Colour: `opportunity_segment`.
   - Tooltip: funded plans, utilisation, payments per funded plan, business opportunity score, advocacy opportunity score, provider activity, remoteness, data-quality note.

2. Opportunity Overview
   - KPIs: funded plans, funded plans per 1,000, payments, payments per funded plan, weighted utilisation, active providers.
   - Opportunity matrix: under-funded advocacy score by under-serviced provider score.
   - Service-area opportunity priority ranking.

3. Advocacy And Under-Service
   - Advocacy opportunity score by service area.
   - Provider under-service score by service area.
   - Unspent committed funding and funding conversion context.

4. Service-Type Opportunity
   - Service-type opportunity score.
   - Support payment gap from remoteness benchmark.
   - Projected next-quarter payments as a simple momentum demand proxy.

5. Service-Area Detail
   - Utilisation and funded-plan trends.
   - Service-type opportunities filtered to the selected area.
   - Evidence and quality views.

6. Data Quality
   - Missing-source warnings.
   - Suppression flags.
   - Geography matching status.

## Filters

Recommended global filters:

- `quarter_label`
- `state`
- `remoteness`
- `persistent_utilisation_classification`
- `support_type`

## Atlas Click-Through

The generated workbook keeps dashboard XML deliberately simple so Tableau Public opens the file reliably. The atlas-to-detail behavior is handled on `gmdata.au` through Tableau's Embedding API v3 rather than internal `.twb` dashboard-action XML.

Website behavior:

1. The page embeds the standalone atlas dashboards first:
   - `NDIS Saturation Atlas Monitor`
   - `NDIS Saturation Atlas Tablet`
   - `NDIS Saturation Atlas Phone`
2. The standalone atlas dashboards are map-only. Keep `Headline KPIs`, opportunity tables and service-type charts out of these views so the atlas behaves like the original Streamlit atlas route.
3. The page listens for a selected service-area mark on the atlas.
4. The service-area detail panel is revealed.
5. The selected service area is applied to the detail dashboards where Tableau exposes a matching `Geography Name`, `Ndis Service Area`, `NDIS Service Area` or `Name` field.

After publishing to Tableau Public, replace the `data-tableau-base` placeholder in `gmdata.au/projects/ndis-saturation-atlas.html` with the published workbook URL base.

## Responsive Dashboard Recovery

If Tableau raises `Error Code: 2805CF18` when adding phone layouts, do not use Tableau Device Preview for this workbook. Use the responsive workbook or the clean worksheet workbook:

- `outputs/tableau/NDIS-Saturation-Atlas.twb`
- `outputs/tableau/NDIS-Saturation-Atlas.presentation-safe.twb`

The main workbook now includes generated dashboard tabs again, using the simple dashboard/window XML shape that Tableau Public has been able to open reliably. If Tableau raises `2805CF18` in Presentation Mode, publish the standalone monitor/tablet/phone dashboard tabs rather than adding Tableau device layouts.

Use `docs/tableau_dashboard_rebuild_checklist.md` as a compact QA checklist for the generated tabs.

Responsive dashboards:

1. `NDIS Saturation Atlas Monitor`
   - Size: fixed, `1600 x 940`.
   - Standalone map-only atlas with metro inset geometry and benchmark-delta tooltips.

2. `NDIS Saturation Atlas Tablet`
   - Size: fixed, `900 x 760`.
   - Tablet-first map-only version of the standalone atlas.

3. `NDIS Saturation Atlas Phone`
   - Size: fixed, `390 x 520`.
   - Mobile map-only version of the standalone atlas.

4. `NDIS Saturation National Monitor`
   - Size: fixed, `1600 x 1120`.
   - National KPI surface: headline KPIs, utilisation trend, funded-plan trend, support mix, remoteness summary and quality.

5. `NDIS Saturation National Tablet`
   - Size: fixed, `900 x 1580`.
   - Tablet national summary.

6. `NDIS Saturation National Phone`
   - Size: fixed, `390 x 2260`.
   - Mobile national summary.

7. `NDIS Saturation Service Area Monitor`
   - Size: fixed, `1600 x 1180`.
   - Service-area detail: utilisation/funded-plan trends, benchmark/support/provider diagnostics, evidence and data quality.

8. `NDIS Saturation Service Area Tablet`
   - Size: fixed, `900 x 1780`.
   - Stacked service-area detail flow.

9. `NDIS Saturation Service Area Phone`
   - Size: fixed, `390 x 2500`.
   - Fully stacked service-area detail flow for mobile viewing.

10. `NDIS Saturation Opportunities Monitor`
    - Size: fixed, `1600 x 1280`.
    - Opportunity and advocacy surface for ranked service areas, service-type demand, provider underservice and evidence.

11. `NDIS Saturation Opportunities Tablet`
    - Size: fixed, `900 x 1960`.
    - Tablet opportunity surface.

12. `NDIS Saturation Opportunities Phone`
    - Size: fixed, `390 x 2760`.
    - Mobile stacked opportunity surface.

Publish each dashboard as a separate Tableau Public view and let `gmdata.au` switch between the views with CSS.

## Interpretation Guardrails

- Low utilisation is a prompt for investigation, not proof of provider shortage.
- Registered or active provider counts are provider-activity context, not workforce capacity.
- Census need for assistance must not be described as NDIS eligibility when those sources are added.
- Support-type payment share is purchasing mix, not a unique participant count.
- Opportunity scores are prioritisation signals only; use local intelligence before describing an area as under-funded, under-serviced or commercially attractive.
