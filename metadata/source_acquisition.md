# Source Acquisition Notes

Use existing local files first. Where a domain is missing, add official source extracts under `data/raw/<domain>/` and update `metadata/source_register.csv` with provenance before extending builders.

## Missing Official Inputs

- ABS 2021 Census DataPacks or TableBuilder extracts for disability, carers, labour force, income, housing, CALD, Indigenous population and age structure indicators.
- ABS SEIFA 2021 indexes for IRSD, IRSAD, IER and IEO.
- DSS payment-recipient datasets for Disability Support Pension, Carer Payment, Carer Allowance, Commonwealth Rent Assistance, JobSeeker, Youth Allowance and Age Pension.
- PHIDU Social Health Atlas extracts, preserving PHIDU source geography unless a defensible concordance is supplied.
- Official workforce sources for relevant disability and allied-health occupations. Do not describe broad occupation counts as NDIS-only workforce.
- Official SDA and housing context sources for enrolled dwellings, demand, vacancies, dwelling type, tenure, overcrowding and housing stress.

Do not add scraped or unstable URLs. Do not convert suppressed values to zero. Do not force incompatible geographies into NDIA Service Area.

