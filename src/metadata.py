from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import config
from .io_utils import write_dataset


def write_metadata(outputs: dict[str, pd.DataFrame], data_quality: pd.DataFrame) -> None:
    """Write source register, field dictionary, geography dictionary and notes."""

    write_source_register()
    write_field_dictionary(outputs, data_quality)
    write_geography_dictionary()
    write_methodology_notes()


def write_source_register() -> None:
    rows = []
    for spec in config.SOURCE_SPECS:
        rows.append(
            {
                "source_name": spec.source_name,
                "publisher": spec.publisher,
                "dataset_name": spec.dataset_name,
                "source_url": spec.source_url,
                "local_file": str(spec.local_file.relative_to(config.PROJECT_ROOT)) if spec.local_file and spec.local_file.exists() else "",
                "date_downloaded": spec.date_downloaded,
                "reference_period": spec.reference_period,
                "release_date": spec.release_date,
                "update_frequency": spec.update_frequency,
                "geography": spec.geography,
                "geography_vintage": spec.geography_vintage,
                "licence": spec.licence,
                "notes": spec.notes if not spec.local_file or spec.local_file.exists() else f"Expected local file missing: {spec.local_file}. {spec.notes}",
            }
        )
    write_dataset(pd.DataFrame(rows), config.METADATA_DIR / "source_register.csv")


def write_field_dictionary(outputs: dict[str, pd.DataFrame], data_quality: pd.DataFrame) -> None:
    rows: list[dict] = []
    output_frames = dict(outputs)
    output_frames["tableau_data_quality"] = data_quality
    for output_file, frame in output_frames.items():
        for field_name in frame.columns:
            rows.append(
                {
                    "output_file": f"{output_file}.csv",
                    "field_name": field_name,
                    "field_label": _label(field_name),
                    "description": FIELD_DESCRIPTIONS.get(field_name, "Prepared Tableau field. See methodology notes and source register for provenance."),
                    "source": FIELD_SOURCES.get(field_name, "derived pipeline output"),
                    "source_field": SOURCE_FIELDS.get(field_name, ""),
                    "calculation": FIELD_CALCULATIONS.get(field_name, ""),
                    "unit": _unit(field_name),
                    "denominator": _denominator(field_name),
                    "geography": "as identified by geography_type and geography_code",
                    "time_period": "quarter, reference_year or reference_period as supplied in output",
                    "limitations": FIELD_LIMITATIONS.get(field_name, "Interpret with source-specific limitations; missing and suppressed values are not converted to zero."),
                }
            )
    write_dataset(pd.DataFrame(rows), config.METADATA_DIR / "field_dictionary.csv")


def write_geography_dictionary() -> None:
    rows = [
        {
            "geography_type": "ndia_service_area",
            "geography_label": "NDIA Service Area",
            "geography_code_format": "official service area name retained as code where no stable numeric code is present locally",
            "geography_vintage": "NDIA source geography with LGA 2021 context",
            "source": "existing local curated service-area context and simplified GeoJSON",
            "conversion_policy": "Preserve source geography. Do not force conversion to SA2/LGA/PHIDU geographies without official concordance.",
            "known_limitations": "Service areas assembled from LGAs can involve one-to-many relationships and boundary mismatch; crosswalk tables are separate from analytical outputs.",
        },
        {
            "geography_type": "lga_2021",
            "geography_label": "Local Government Area 2021",
            "geography_code_format": "five-character ABS LGA code as string",
            "geography_vintage": "2021",
            "source": "existing local LGA population and remoteness tables",
            "conversion_policy": "Use official concordances and aggregate numerators/denominators before calculating rates.",
            "known_limitations": "LGA sources are currently retained as processed denominator/context assets, not forced into every output table.",
        },
    ]
    write_dataset(pd.DataFrame(rows), config.METADATA_DIR / "geography_dictionary.csv")


def write_methodology_notes() -> None:
    text = """# Methodology Notes

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
"""
    path = config.METADATA_DIR / "methodology_notes.md"
    path.write_text(text, encoding="utf-8")


def write_final_build_report(
    outputs: dict[str, pd.DataFrame],
    data_quality: pd.DataFrame,
    row_counts: pd.DataFrame,
    validation_passed: bool,
) -> Path:
    """Write the final build report requested by the publication workflow."""

    processed_sources = [
        spec.source_name for spec in config.SOURCE_SPECS if spec.local_file is not None and spec.local_file.exists()
    ]
    unavailable_sources = [
        spec.source_name for spec in config.SOURCE_SPECS if spec.local_file is None or not spec.local_file.exists()
    ]
    output_lines = [f"- `{name}.csv`: {len(frame):,} rows" for name, frame in outputs.items()]
    output_lines.append(f"- `tableau_data_quality.csv`: {len(data_quality):,} rows")
    critical_count = int(data_quality["issue_severity"].isin(["critical", "fail"]).sum()) if not data_quality.empty else 0
    warning_count = int(data_quality["issue_severity"].eq("warning").sum()) if not data_quality.empty else 0

    row_count_table = row_counts.to_csv(index=False, lineterminator="\n") if not row_counts.empty else "No row counts recorded."

    text = f"""# Final Build Report

## Sources Successfully Processed

{_bullet_list(processed_sources)}

## Sources Unavailable

{_bullet_list(unavailable_sources)}

## Outputs Created

{chr(10).join(output_lines)}

Parquet equivalents were written beside the Tableau CSV outputs.

## Row Counts

```csv
{row_count_table.strip()}
```

## Validation Results

- Validation passed: `{validation_passed}`
- Critical or failing issues: {critical_count}
- Warnings: {warning_count}

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
"""
    path = config.AUDIT_DIR / "final_build_report.md"
    path.write_text(text, encoding="utf-8")
    return path


def _bullet_list(items: list[str]) -> str:
    if not items:
        return "- None"
    return "\n".join(f"- {item}" for item in items)


def _label(field_name: str) -> str:
    return field_name.replace("_", " ").title()


def _unit(field_name: str) -> str:
    if field_name.endswith("_count"):
        return "count"
    if field_name.endswith("_rate") or field_name.endswith("_share") or field_name.endswith("_pct"):
        return "decimal"
    if field_name.endswith("_per_1000"):
        return "per 1,000 population or funded plans as named"
    if field_name.endswith("_per_10000"):
        return "per 10,000 population"
    if "payment" in field_name or "funding" in field_name or "supports" in field_name:
        return "AUD"
    if field_name.endswith("_date"):
        return "ISO date"
    return ""


def _denominator(field_name: str) -> str:
    if "per_1000_population" in field_name or field_name in {"funded_plans_per_1000", "participants_per_1000"}:
        return "population_count"
    if "per_funded_plan" in field_name:
        return "funded_plan_count"
    if "per_participant" in field_name:
        return "participant_count"
    if field_name.endswith("_share"):
        return "relevant local, national or remoteness total"
    return ""


FIELD_DESCRIPTIONS = {
    "funding_conversion_rate": "Payments divided by committed supports.",
    "unspent_committed_funding": "Committed supports minus payments.",
    "unspent_funding_per_funded_plan": "Unspent committed funding divided by funded plans.",
    "supply_response_gap": "Participant growth rate minus provider growth rate. This is a market-density indicator, not a caseload measure.",
    "support_location_quotient": "Local support payment share divided by national support payment share.",
    "business_opportunity_score": "Quarter-relative proxy score for commercial opportunity, combining market scale, payment intensity, utilisation friction, provider load and unspent funding signals.",
    "advocacy_opportunity_score": "Quarter-relative proxy score for advocacy priority, combining under-funding, under-service and utilisation-barrier signals.",
    "underfunded_advocacy_score": "Quarter-relative proxy score for funding or access gaps, based on funded-plan coverage, mean plan funding and payment-intensity gaps against remoteness peers.",
    "utilisation_barrier_score": "Quarter-relative proxy score for utilisation friction, based on below-peer utilisation, unspent committed funding and funding-conversion gaps.",
    "underserviced_provider_score": "Quarter-relative proxy score for potential under-service, based on provider load, supply response and utilisation gap indicators.",
    "combined_opportunity_score": "Mean of business and advocacy opportunity proxy scores.",
    "funded_plans_per_1000_delta_from_national_mean": "Funded plans per 1,000 population minus the national mean for the same quarter.",
    "mean_plan_utilisation_delta_from_national_median": "Mean plan utilisation minus the national median service-area utilisation for the same quarter.",
    "provider_saturation_delta_from_national_mean": "Funded plans per active provider minus the national mean for the same quarter. Higher values indicate higher provider load.",
    "active_provider_rate_delta_from_national_mean": "Active providers per 1,000 funded plans minus the national mean for the same quarter.",
    "atlas_default_metric_value": "Default atlas colour metric combining funded-plan coverage gaps, utilisation gaps and provider saturation signals.",
    "atlas_service_type_filter": "Support type copied into the service-type table for Tableau atlas filtering.",
    "opportunity_rank": "Quarter-specific rank by combined opportunity score, where 1 is the highest-ranked service area.",
    "opportunity_segment": "Readable service-area opportunity segment derived from the proxy scores.",
    "support_payment_gap_from_remoteness_benchmark": "Estimated support-type payment dollars below or above the remoteness peer payment-share benchmark.",
    "support_payment_gap_from_national_benchmark": "Estimated support-type payment dollars below or above the national payment-share benchmark.",
    "support_undersupply_score": "Quarter-relative proxy score for support-type under-supply, based on remoteness benchmark payment, share and location-quotient gaps.",
    "support_business_opportunity_score": "Quarter-relative support-type proxy score combining support under-supply, growth, payment scale, payment intensity and area business opportunity.",
    "support_advocacy_opportunity_score": "Quarter-relative support-type proxy score combining support under-supply with area advocacy, under-funding and under-service signals.",
    "service_type_opportunity_score": "Mean of support business and support advocacy opportunity proxy scores.",
    "service_type_opportunity_rank": "Quarter and support-type rank by service-type opportunity score, where 1 is the highest-ranked area for that support type.",
    "service_type_opportunity_segment": "Readable support-type opportunity segment derived from the proxy scores.",
    "projected_next_quarter_payments": "Simple one-quarter momentum projection using clipped payment growth. This is a demand proxy, not a statistical forecast.",
    "ndis_to_assistance_ratio": "Relative access or participation-context indicator, not an unmet-need rate.",
}

FIELD_SOURCES = {
    "population_count": "local processed ABS ERP denominator",
    "funded_plan_count": "local curated NDIA service-area-quarter source",
    "payment_amount": "local curated NDIA service-area-quarter source",
    "payments": "local curated NDIA service-type source",
}

SOURCE_FIELDS = {
    "funded_plan_count": "funded_plans_count",
    "payment_amount": "service_area_payment_amount",
    "payments": "service_type_payment_amount",
}

FIELD_CALCULATIONS = {
    "funding_conversion_rate": "payment_amount / committed_supports",
    "unspent_committed_funding": "committed_supports - payment_amount",
    "unspent_funding_per_funded_plan": "unspent_committed_funding / funded_plan_count",
    "support_location_quotient": "local_support_share / national_support_share",
    "support_payment_gap_from_remoteness_benchmark": "area_total_payments * remoteness_benchmark - payments",
    "support_payment_gap_from_national_benchmark": "area_total_payments * national_benchmark - payments",
    "funded_plans_per_1000_delta_from_national_mean": "funded_plans_per_1000 - benchmark_national_funded_plans_per_1000",
    "mean_plan_utilisation_delta_from_national_median": "mean_plan_utilisation - benchmark_national_median_plan_utilisation",
    "provider_saturation_delta_from_national_mean": "funded_plans_per_active_provider - benchmark_national_provider_saturation",
    "active_provider_rate_delta_from_national_mean": "active_providers_per_1000_funded_plans - benchmark_national_active_providers_per_1000_funded_plans",
    "atlas_default_metric_value": "mean of quarter-relative funded-plan coverage gap, utilisation gap and provider saturation proxy scores",
    "projected_next_quarter_payments": "payments * (1 + clipped payment_growth_rate)",
}

FIELD_LIMITATIONS = {
    "participant_count": "Available only where the historical local extract contains active participant counts.",
    "participant_growth_rate": "Unavailable where participant_count is missing.",
    "population_count": "Current denominator is static 2025 ERP; quarterly interpolation requires annual source series.",
    "business_opportunity_score": "Proxy score for triage and prioritisation only. It does not prove unmet demand, provider shortage or future revenue.",
    "advocacy_opportunity_score": "Proxy score for triage and prioritisation only. It should be interpreted with local evidence and participant/community context.",
    "atlas_default_metric_value": "Composite visual priority score only; inspect the individual delta fields before drawing conclusions.",
    "projected_next_quarter_payments": "Simple momentum proxy only. It is not a causal forecast and clips growth rates to avoid extreme projections.",
}
