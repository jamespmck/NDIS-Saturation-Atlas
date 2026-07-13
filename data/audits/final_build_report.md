# Final Build Report

## Sources Successfully Processed

- ndia_service_area_quarter_curated
- ndia_service_type_quarter_curated
- ndia_historical_quarter_extract
- service_area_population_2025_erp
- service_area_remoteness_2021

## Sources Unavailable

- census_2021_community_indicators
- seifa_2021
- dss_payment_data
- phidu_social_health_atlas
- workforce_public_sources
- housing_and_sda_context

## Outputs Created

- `tableau_market_quarter.csv`: 640 rows
- `tableau_support_type_quarter.csv`: 7,680 rows
- `tableau_participant_profile.csv`: 0 rows
- `tableau_community_context.csv`: 93 rows
- `tableau_market_classification.csv`: 640 rows
- `tableau_geography_lookup.csv`: 93 rows
- `tableau_data_quality.csv`: 59 rows

Parquet equivalents were written beside the Tableau CSV outputs.

## Row Counts

```csv
dataset,stage,row_count,column_count,notes
tableau_market_quarter,tableau,640,86,Tableau CSV and Parquet output
tableau_support_type_quarter,tableau,7680,57,Tableau CSV and Parquet output
tableau_participant_profile,tableau,0,13,Tableau CSV and Parquet output
tableau_community_context,tableau,93,9,Tableau CSV and Parquet output
tableau_market_classification,tableau,640,21,Tableau CSV and Parquet output
tableau_geography_lookup,tableau,93,12,Tableau CSV and Parquet output
tableau_data_quality,tableau,59,11,Validation and source-gap audit rows
```

## Validation Results

- Validation passed: `True`
- Critical or failing issues: 0
- Warnings: 7

## Known Limitations

- The build uses existing curated local CSVs as source inputs because raw NDIA extracts are not present.
- Participant counts are only available for quarters that overlap the historical local extract; later rows retain funded-plan context without pretending it is a participant count.
- Population is currently static 2025 ERP, not quarterly interpolation from annual series.
- Census, SEIFA, DSS, PHIDU, workforce and broader housing/SDA datasets are documented but unavailable locally.
- Low utilisation is not interpreted as proof of provider shortage, and need-for-assistance indicators are not treated as NDIS eligibility.

## Recommended Next Data Acquisitions

- Official NDIA quarterly source extracts backing participant, funding, payment, provider and profile tables.
- Official ABS annual ERP series by LGA/SA2/SA3/SA4 for interpolation.
- 2021 Census counts and denominators for disability, carers, labour, income, housing and CALD indicators.
- ABS SEIFA 2021 indexes.
- DSS geographic payment-recipient tables.
- PHIDU Social Health Atlas extracts with original geography preserved.
- Official workforce and SDA/housing context sources with stable provenance.
