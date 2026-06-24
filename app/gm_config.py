from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_CANDIDATES = [
    PROJECT_ROOT / "data" / "published" / "master_ndis_service_area_quarter_all_available_scoped.csv",
    PROJECT_ROOT / "data" / "published" / "master_ndis_service_area_quarter_all_available_benchmarked.csv",
    PROJECT_ROOT / "data" / "published" / "master_ndis_service_area_quarter_all_available.csv",
]

SERVICE_TYPE_CANDIDATES = [
    PROJECT_ROOT / "data" / "published" / "master_ndis_service_area_quarter_service_type_custom.csv",
    PROJECT_ROOT / "data" / "published" / "master_ndis_service_area_quarter_service_type_benchmarks.csv",
]

GEO_CANDIDATES = [
    PROJECT_ROOT / "outputs" / "powerbi_map" / "ndis_service_area_boundaries_simplified.geojson",
    PROJECT_ROOT / "data" / "published" / "ndis_service_area_boundaries_simplified.geojson",
    PROJECT_ROOT / "data" / "geo" / "ndis_service_area_boundaries_simplified.geojson",
]

BASELINE_QUARTER_DEFAULT = "2024Q2"
MIN_QUARTER_DEFAULT = "2024Q2"

GM_NAVY = "#061A2E"
GM_NAVY_2 = "#0B2A4A"
GM_AMBER = "#F2B705"
GM_AMBER_SOFT = "#FFF7E6"
GM_RED = "#B3261E"

REMOTENESS_ORDER = [
    "Major Cities of Australia",
    "Inner Regional Australia",
    "Outer Regional Australia",
    "Remote Australia",
    "Very Remote Australia",
    "Unknown",
]

SERVICE_TYPE_ORDER = [
    "Capital",
    "Community Participation Care",
    "Early Childhood Supports",
    "Group Centre Care",
    "High Needs Personal Care",
    "Other Capacity Building",
    "Other Core",
    "Personal Care",
    "Plan Management",
    "Shared Accommodation Supports",
    "Support Coordination",
    "Therapy",
]

METRIC_INFO = {
    "funded_plans_per_1000_gap_from_national": {
        "label": "Is plan coverage above or below the national benchmark?",
        "short": "Plan coverage gap",
        "definition": "National funded plans per 1,000 population minus service-area funded plans per 1,000 population.",
        "positive": "Below national benchmark",
        "negative": "Above national benchmark",
        "map_score": "invert",
    },
    "mean_plan_utilisation_gap_from_national": {
        "label": "Is utilisation above or below the national benchmark?",
        "short": "Utilisation gap",
        "definition": "National weighted mean utilisation minus service-area mean utilisation.",
        "positive": "Below national benchmark",
        "negative": "Above national benchmark",
        "map_score": "invert",
    },
    "plans_per_1000_change_from_baseline": {
        "label": "Has plan coverage increased or decreased since baseline?",
        "short": "Plan coverage change",
        "definition": "Selected quarter funded plans per 1,000 population minus baseline quarter funded plans per 1,000 population.",
        "positive": "Increase since baseline",
        "negative": "Decrease since baseline",
        "map_score": "direct",
    },
    "mean_plan_utilisation_change_from_baseline": {
        "label": "Has utilisation increased or decreased since baseline?",
        "short": "Utilisation change",
        "definition": "Selected quarter mean utilisation minus baseline quarter mean utilisation.",
        "positive": "Increase since baseline",
        "negative": "Decrease since baseline",
        "map_score": "direct",
    },
}

SERVICE_AREA_STATE_FALLBACK = {
    "ACT": "ACT",
    "Adelaide Hills": "SA",
    "Barkly": "NT",
    "Barossa, Light and Lower North": "SA",
    "Barwon": "VIC",
    "Bayside Peninsula": "VIC",
    "Beenleigh": "QLD",
    "Brimbank Melton": "VIC",
    "Brisbane": "QLD",
    "Bundaberg": "QLD",
    "Caboolture/Strathpine": "QLD",
    "Cairns": "QLD",
    "Central Australia": "NT",
    "Central Coast": "NSW",
    "Central Highlands": "VIC",
    "Central North Metro": "WA",
    "Central South Metro": "WA",
    "Darwin Remote": "NT",
    "Darwin Urban": "NT",
    "East Arnhem": "NT",
    "Eastern Adelaide": "SA",
    "Eyre and Western": "SA",
    "Far North (SA)": "SA",
    "Far West": "NSW",
    "Fleurieu and Kangaroo Island": "SA",
    "Goldfields-Esperance": "WA",
    "Goulburn": "VIC",
    "Great Southern": "WA",
    "Hume Moreland": "VIC",
    "Hunter New England": "NSW",
    "Illawarra Shoalhaven": "NSW",
    "Inner East Melbourne": "VIC",
    "Inner Gippsland": "VIC",
    "Ipswich": "QLD",
    "Katherine": "NT",
    "Kimberley-Pilbara": "WA",
    "Limestone Coast": "SA",
    "Loddon": "VIC",
    "Mackay": "QLD",
    "Mallee": "VIC",
    "Maroochydore": "QLD",
    "Maryborough": "QLD",
    "Mid North Coast": "NSW",
    "Midwest-Gascoyne": "WA",
    "Murray and Mallee": "SA",
    "Murrumbidgee": "NSW",
    "Nepean Blue Mountains": "NSW",
    "North East Melbourne": "VIC",
    "North East Metro": "WA",
    "North Metro": "WA",
    "North Sydney": "NSW",
    "Northern Adelaide": "SA",
    "Northern NSW": "NSW",
    "Outer East Melbourne": "VIC",
    "Outer Gippsland": "VIC",
    "Ovens Murray": "VIC",
    "Robina": "QLD",
    "Rockhampton": "QLD",
    "South East Metro": "WA",
    "South Eastern Sydney": "NSW",
    "South Metro": "WA",
    "South West": "WA",
    "South Western Sydney": "NSW",
    "Southern Adelaide": "SA",
    "Southern Melbourne": "VIC",
    "Southern NSW": "NSW",
    "Sydney": "NSW",
    "TAS North": "TAS",
    "TAS North West": "TAS",
    "TAS South East": "TAS",
    "TAS South West": "TAS",
    "Toowoomba": "QLD",
    "Townsville": "QLD",
    "Western Adelaide": "SA",
    "Western District": "VIC",
    "Western Melbourne": "VIC",
    "Western NSW": "NSW",
    "Western Sydney": "NSW",
    "Wheat Belt": "WA",
    "Yorke and Mid North": "SA",
}

BENCHMARK_SERVICE_AREA_CANDIDATES = [
    PROJECT_ROOT / "data" / "published" / "benchmark_service_area_quarter_long.csv",
]

BENCHMARK_SERVICE_TYPE_CANDIDATES = [
    PROJECT_ROOT / "data" / "published" / "benchmark_service_type_area_quarter_long.csv",
]
