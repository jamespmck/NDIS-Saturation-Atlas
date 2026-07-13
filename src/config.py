from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
TABLEAU_DIR = DATA_DIR / "tableau"
AUDIT_DIR = DATA_DIR / "audits"
ANALYSIS_DIR = DATA_DIR / "analysis"
METADATA_DIR = PROJECT_ROOT / "metadata"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

RAW_SUBDIRS = ("ndia", "abs", "dss", "phidu", "workforce", "housing", "geography")

MAIN_NDIA_SOURCE = DATA_DIR / "published" / "master_ndis_service_area_quarter_all_available_scoped.csv"
SERVICE_TYPE_SOURCE = DATA_DIR / "published" / "master_ndis_service_area_quarter_service_type_custom.csv"
HISTORICAL_NDIA_SOURCE = PROCESSED_DIR / "historical_ndis_service_area_quarter_2022q4_2025q2_extracted.csv"
SERVICE_AREA_POPULATION_SOURCE = PROCESSED_DIR / "service_area_population_2025_erp.csv"
SERVICE_AREA_CONTEXT_SOURCE = PROCESSED_DIR / "service_area_geography_context_2021_2025.csv"
SERVICE_AREA_REMOTENESS_SOURCE = PROCESSED_DIR / "service_area_remoteness_2021.csv"
SERVICE_AREA_REMOTENESS_DETAIL_SOURCE = PROCESSED_DIR / "service_area_remoteness_detail_2021.csv"
LGA_POPULATION_SOURCE = PROCESSED_DIR / "lga_population_2025_erp.csv"
LGA_REMOTENESS_SOURCE = PROCESSED_DIR / "lga_remoteness_2021.csv"
LGA_REMOTENESS_DETAIL_SOURCE = PROCESSED_DIR / "lga_remoteness_detail_2021.csv"
SERVICE_AREA_GEOJSON_SOURCE = OUTPUTS_DIR / "powerbi_map" / "ndis_service_area_boundaries_simplified.geojson"

TABLEAU_OUTPUTS = {
    "tableau_market_quarter": TABLEAU_DIR / "tableau_market_quarter.csv",
    "tableau_support_type_quarter": TABLEAU_DIR / "tableau_support_type_quarter.csv",
    "tableau_participant_profile": TABLEAU_DIR / "tableau_participant_profile.csv",
    "tableau_community_context": TABLEAU_DIR / "tableau_community_context.csv",
    "tableau_market_classification": TABLEAU_DIR / "tableau_market_classification.csv",
    "tableau_geography_lookup": TABLEAU_DIR / "tableau_geography_lookup.csv",
    "tableau_data_quality": TABLEAU_DIR / "tableau_data_quality.csv",
}

PARQUET_OUTPUTS = {
    name: path.with_suffix(".parquet") for name, path in TABLEAU_OUTPUTS.items()
}

GEOMETRY_OUTPUTS = {
    "ndia_service_area_geojson": TABLEAU_DIR / "geometry_ndia_service_area.geojson",
}

BENCHMARK_LABEL_NATIONAL = "national"
BENCHMARK_LABEL_REMOTENESS = "remoteness"

PERSISTENT_UTILISATION_THRESHOLDS = {
    "low_gap_min": 0.02,
    "high_gap_max": -0.02,
    "deteriorating_slope_max": -0.005,
    "recovering_slope_min": 0.005,
    "volatile_std_min": 0.08,
    "minimum_quarters": 4,
}

RELIABILITY_FLAGS = {
    "observed": "observed",
    "derived": "derived_from_local_curated_source",
    "unavailable": "source_unavailable",
    "insufficient_history": "insufficient_history",
}

REQUIRED_DIRS = [
    RAW_DIR / subdir for subdir in RAW_SUBDIRS
] + [INTERIM_DIR, PROCESSED_DIR, TABLEAU_DIR, AUDIT_DIR, ANALYSIS_DIR, METADATA_DIR]


@dataclass(frozen=True)
class SourceSpec:
    """Metadata for a local or missing source used by the pipeline."""

    source_name: str
    publisher: str
    dataset_name: str
    local_file: Path | None
    geography: str
    geography_vintage: str
    reference_period: str
    notes: str
    source_url: str = ""
    date_downloaded: str = ""
    release_date: str = ""
    update_frequency: str = ""
    licence: str = ""


SOURCE_SPECS = [
    SourceSpec(
        source_name="ndia_service_area_quarter_curated",
        publisher="NDIA, curated in existing repository",
        dataset_name="Master NDIS service-area-quarter table",
        local_file=MAIN_NDIA_SOURCE,
        geography="NDIA Service Area",
        geography_vintage="LGA 2021 assembled service areas; source release geography",
        reference_period="2024Q2-2026Q1",
        notes="Existing curated publication asset reused as local source pending replacement with raw NDIA extracts.",
    ),
    SourceSpec(
        source_name="ndia_service_type_quarter_curated",
        publisher="NDIA, curated in existing repository",
        dataset_name="Service-type payment table",
        local_file=SERVICE_TYPE_SOURCE,
        geography="NDIA Service Area",
        geography_vintage="LGA 2021 assembled service areas; source release geography",
        reference_period="2024Q2-2026Q1",
        notes="Existing curated publication asset reused for support-type Tableau output.",
    ),
    SourceSpec(
        source_name="ndia_historical_quarter_extract",
        publisher="NDIA, curated in existing repository",
        dataset_name="Historical NDIS service-area-quarter extract",
        local_file=HISTORICAL_NDIA_SOURCE,
        geography="NDIA Service Area",
        geography_vintage="source release geography",
        reference_period="2022Q4-2025Q2",
        notes="Contains active participants and plan-value measures for earlier quarters.",
    ),
    SourceSpec(
        source_name="service_area_population_2025_erp",
        publisher="ABS, curated in existing repository",
        dataset_name="Service area population denominators",
        local_file=SERVICE_AREA_POPULATION_SOURCE,
        geography="NDIA Service Area",
        geography_vintage="LGA 2021 assembled to service area",
        reference_period="2025",
        notes="Static ERP denominator currently available locally; annual interpolation awaits source annual series.",
    ),
    SourceSpec(
        source_name="service_area_remoteness_2021",
        publisher="ABS, curated in existing repository",
        dataset_name="Service area remoteness context",
        local_file=SERVICE_AREA_CONTEXT_SOURCE,
        geography="NDIA Service Area",
        geography_vintage="2021",
        reference_period="2021-2025",
        notes="Area-weighted dominant remoteness and population context.",
    ),
    SourceSpec(
        source_name="census_2021_community_indicators",
        publisher="ABS",
        dataset_name="2021 Census disability and community indicators",
        local_file=None,
        geography="SA2/LGA/SA3/SA4 where available",
        geography_vintage="2021",
        reference_period="2021",
        notes="Not available locally. Add official Census DataPacks or TableBuilder extracts before populating Census indicators.",
    ),
    SourceSpec(
        source_name="seifa_2021",
        publisher="ABS",
        dataset_name="SEIFA 2021",
        local_file=None,
        geography="SA1/SA2/LGA/SA3/SA4 where available",
        geography_vintage="2021",
        reference_period="2021",
        notes="Not available locally. Add official ABS SEIFA 2021 indexes before populating socioeconomic gradients.",
    ),
    SourceSpec(
        source_name="dss_payment_data",
        publisher="DSS",
        dataset_name="DSS income support recipient data",
        local_file=None,
        geography="source geography",
        geography_vintage="source release vintage",
        reference_period="latest available",
        notes="Not available locally. Add official DSS payment datasets with stable download provenance.",
    ),
    SourceSpec(
        source_name="phidu_social_health_atlas",
        publisher="PHIDU",
        dataset_name="Social Health Atlas indicators",
        local_file=None,
        geography="PHA or source geography",
        geography_vintage="source release vintage",
        reference_period="latest available",
        notes="Not available locally. PHIDU geographies must be preserved unless a defensible concordance is supplied.",
    ),
    SourceSpec(
        source_name="workforce_public_sources",
        publisher="ABS/Jobs and Skills Australia/AHPRA or other official sources",
        dataset_name="Relevant disability and allied-health workforce measures",
        local_file=None,
        geography="source geography",
        geography_vintage="source release vintage",
        reference_period="latest available",
        notes="Not available locally. Do not label broad occupation counts as NDIS-only workforce.",
    ),
    SourceSpec(
        source_name="housing_and_sda_context",
        publisher="NDIA/ABS/AIHW or other official sources",
        dataset_name="Housing, SDA and rental-stress context",
        local_file=None,
        geography="source geography",
        geography_vintage="source release vintage",
        reference_period="latest available",
        notes="Only SDA-related payment context is present indirectly in local NDIA tables. Broader housing sources are unavailable locally.",
    ),
]
