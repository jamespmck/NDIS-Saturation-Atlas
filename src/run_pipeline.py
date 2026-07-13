from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from . import config
from .build_census import census_source_gap_quality_rows
from .build_dss import dss_source_gap_quality_rows
from .build_features import participant_profile_quality_rows
from .build_housing import housing_source_gap_quality_rows
from .build_ndia import build_market_quarter, build_support_type_quarter, write_ndia_intermediates
from .build_phidu import phidu_source_gap_quality_rows
from .build_population import build_population, write_population_outputs
from .build_seifa import seifa_source_gap_quality_rows
from .build_tableau_outputs import build_tableau_outputs, write_tableau_outputs
from .build_workforce import workforce_source_gap_quality_rows
from .geography import build_geography_lookup, geography_audit
from .io_utils import configure_logging, ensure_directories, row_count_frame, write_audit
from .metadata import write_final_build_report, write_metadata
from .validation import raise_for_critical_failures, validate_outputs


STAGES = {"all", "ndia", "population", "census", "community", "features", "tableau", "analysis", "review"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Tableau-ready NDIS Saturation Atlas datasets.")
    parser.add_argument("--stage", choices=sorted(STAGES), default="all")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    configure_logging()
    ensure_directories()

    if args.validate_only:
        outputs = _read_existing_tableau_outputs()
        quality = validate_outputs(outputs)
        raise_for_critical_failures(quality)
        write_audit(quality, "validate_only_data_quality.csv")
        return

    if args.stage in {"all", "ndia", "features", "tableau"}:
        market = build_market_quarter()
        support_type = build_support_type_quarter()
        write_ndia_intermediates(market, support_type)
    else:
        market = pd.DataFrame()
        support_type = pd.DataFrame()

    if args.stage in {"all", "population", "community"}:
        population_outputs = build_population()
        write_population_outputs(population_outputs)

    if args.stage in {"all", "tableau", "features"}:
        outputs, geometry_quality = build_tableau_outputs(market, support_type)
        extra_quality = _source_gap_quality_rows() + geometry_quality
        geography_lookup = outputs["tableau_geography_lookup"]
        extra_quality.extend(
            geography_audit("tableau_market_quarter", outputs["tableau_market_quarter"], "geography_code", geography_lookup).rename(
                columns={
                    "source_dataset": "dataset",
                    "source_geography": "geography",
                    "known_limitations": "explanatory_note",
                }
            ).assign(
                period="",
                field="geography_code",
                issue_type="geography_matching",
                issue_severity="info",
                missingness=lambda df: df["unmatched_records"],
                suppression="",
                mapping_status=lambda df: df["percentage_matched"].map(lambda x: f"{x:.3f}" if pd.notna(x) else "not_available"),
                reliability_flag=config.RELIABILITY_FLAGS["derived"],
            )[["dataset", "period", "geography", "field", "issue_type", "issue_severity", "missingness", "suppression", "mapping_status", "reliability_flag", "explanatory_note"]].to_dict("records")
        )
        data_quality = validate_outputs(outputs, extra_quality)
        raise_for_critical_failures(data_quality)
        write_tableau_outputs(outputs, data_quality)
        write_metadata(outputs, data_quality)
        row_counts = _row_counts(outputs, data_quality)
        write_audit(row_counts, "row_counts.csv")
        write_audit(data_quality, "data_quality_audit.csv")
        write_final_build_report(outputs, data_quality, row_counts, validation_passed=True)

    if args.stage in {"all", "analysis"}:
        from .analyse_tableau_outputs import run_analysis

        run_analysis()

    if args.stage in {"all", "review"}:
        from .tableau_workbook_review import write_review

        write_review()


def _read_existing_tableau_outputs() -> dict[str, pd.DataFrame]:
    outputs = {}
    for name, path in config.TABLEAU_OUTPUTS.items():
        if name == "tableau_data_quality":
            continue
        if path.exists():
            outputs[name] = pd.read_csv(path, low_memory=False)
    return outputs


def _source_gap_quality_rows() -> list[dict]:
    rows: list[dict] = []
    rows.extend(census_source_gap_quality_rows())
    rows.extend(seifa_source_gap_quality_rows())
    rows.extend(dss_source_gap_quality_rows())
    rows.extend(phidu_source_gap_quality_rows())
    rows.extend(workforce_source_gap_quality_rows())
    rows.extend(housing_source_gap_quality_rows())
    rows.extend(participant_profile_quality_rows())
    return rows


def _row_counts(outputs: dict[str, pd.DataFrame], data_quality: pd.DataFrame) -> pd.DataFrame:
    rows = [
        {
            "dataset": name,
            "stage": "tableau",
            "row_count": len(frame),
            "column_count": len(frame.columns),
            "notes": "Tableau CSV and Parquet output",
        }
        for name, frame in outputs.items()
    ]
    rows.append(
        {
            "dataset": "tableau_data_quality",
            "stage": "tableau",
            "row_count": len(data_quality),
            "column_count": len(data_quality.columns),
            "notes": "Validation and source-gap audit rows",
        }
    )
    return row_count_frame(rows)


if __name__ == "__main__":
    main()
