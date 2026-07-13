# Methodology Notes

## Multidimensional Saturation

The Tableau data model treats market saturation as multidimensional. Participant density or funded-plan density is only one context measure. The prepared outputs separately retain demand, funded demand, purchasing, utilisation, provider activity, support-type mix, population context and data-quality flags.

## Geographic Conversions

The current local evidence is strongest at NDIA Service Area. The pipeline preserves source geography and does not force all data into a single geography. Service-area context derived from LGA 2021 inputs is retained separately from analytical tables. Rates must be aggregated from numerators and denominators, not averaged.

## Population

The available local population denominator is 2025 ERP. Annual source series for defensible quarterly interpolation are not present locally, so the pipeline records a static 2025 denominator and documents that limitation.

## Benchmarks

National and remoteness benchmarks are retained from the local curated source where available. Gap fields use benchmark minus observed value, so positive utilisation gaps mean the local value is below the benchmark.

## Support-Type Aggregation

Support-type location quotients use local support payment share divided by national support payment share. Remoteness peer shares are calculated from summed support payments divided by summed area payment totals. This preserves numerator/denominator logic and avoids averaging rates.

## Suppressed Data

Suppressed values are not replaced with zero. Suppression counts from the service-type source are carried into the Tableau support-type output and data-quality flags.

## Reliability Flags

Rows are flagged where sources are derived from existing curated local assets, where suppression is present, where only funded-plan context is available, or where history is insufficient for a classification.

## Known Limitations

Census, SEIFA, DSS, PHIDU, workforce and broad housing/SDA context sources are not available locally in this repository. The pipeline creates metadata and quality warnings for those gaps rather than fabricating indicators.
