# Method

## Purpose

The NDIS Market Saturation Atlas is an exploratory data science case study. It converts public NDIS service-area data into interpretable benchmark, trend, service-category and geospatial evidence for strategic review.

The central analytical question is:

> Which service areas appear materially below, near or above selected benchmarks for NDIS plan coverage, plan utilisation and service-category payment mix?

The project is designed for transparent exploration, not for formal statistical inference.

## Unit Of Analysis

The primary modelling grain is:

```text
service area x quarter
```

A secondary service-category table is used at:

```text
service area x quarter x service category
```

The Streamlit app filters and benchmarks these grains interactively.

## Core Measures

The measures are deliberately simple and auditable. A more complex index could be built from these ingredients, but doing so would introduce judgement weights that are harder to defend from public data alone.

### Funded Plan Coverage

Funded plan coverage is expressed as funded plans per 1,000 people:

```text
funded plans per 1,000 = funded plans count / 2025 ERP population x 1,000
```

This is a population-adjusted saturation measure. It is not an estimate of disability prevalence.

### Mean Plan Utilisation

Mean plan utilisation is retained as the published whole-service-area utilisation measure. It is not scaled by service-category payment share because doing so would create a hybrid measure that is no longer an interpretable utilisation rate.

### Benchmark Gaps

Benchmark gaps are calculated as:

```text
gap = benchmark value - observed value
```

Positive values indicate that the observed service-area value is below the selected benchmark. Negative values indicate that the observed value is above the selected benchmark.

Supported benchmark bases are:

- National mean for the selected quarter.
- Remoteness-category mean for the selected quarter.
- The same service area's value in a selected historical quarter.
- A fixed service-area disability estimate benchmark for plan coverage.

### Baseline Change

Change measures are calculated as:

```text
change = selected quarter value - reference quarter value
```

The default reference quarter is 2024Q2.

## Service-Category Payment Mix

Service-category analysis uses payment share as a proxy for the relative intensity of different support categories in a service area. This is useful for comparing market composition, but it should be interpreted carefully.

The service-category payment benchmark is shown as a percentage-point gap:

```text
payment-share gap = observed category share - benchmark category share
```

For all-service-area views, a heatmap is used so every service area can remain visible and labelled. For a single selected area or Australia, a diverging bar chart is used to show category-level gaps from the selected benchmark.

## Analytical Assumptions

- The service-area-quarter table is treated as the authoritative modelling frame for the dashboard.
- Population denominators are used to make service areas more comparable, but they do not adjust for age structure, disability prevalence or socioeconomic context.
- National and remoteness-category benchmarks are descriptive comparators, not normative targets.
- Historical-quarter benchmarks are useful for change detection, but they can reflect reporting changes as well as market change.
- Payment shares are useful for comparing composition, but they cannot identify how many participants use a service category.

## Geospatial Rendering

The atlas joins the service-area-quarter table to an NDIS service-area boundary file. A custom SVG renderer separates dense metropolitan areas into insets for readability while preserving click-through links to service-area dashboards.

## Quality Assurance

Quality checks are surfaced through three layers:

- Build audit CSVs in `docs/`.
- Unit tests in `tests/test_metrics.py` for benchmark and proxy calculations.
- App-level data quality views for current filtered data.

## Limitations

The atlas identifies patterns that warrant local interpretation. It does not prove unmet need, access barriers, provider shortage, provider oversupply, service quality, causal impact or future demand. Public administrative data can also reflect policy settings, reporting rules, population denominators, suppressed records and historical service-market development.

## Suggested Extensions

- Add demographic standardisation if suitable service-area age and disability-prevalence denominators become available.
- Add uncertainty or sensitivity analysis for small-population service areas.
- Compare benchmark gaps with provider location, workforce and thin-market indicators.
- Convert selected notebook outputs into a short static analytical report for non-technical readers.
