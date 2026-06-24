from __future__ import annotations

from pathlib import Path
import html
import re

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from gm_app_utils import (
    GM_AMBER,
    GM_GREEN,
    GM_NAVY,
    GM_RED,
    benchmark_context_label,
    category_context_label,
    fmt,
    fmt_pct,
    gm_chart,
    metric_axis_title as app_metric_axis_title,
    remoteness_context_label,
    safe_float,
    selected_metric_interpretation as app_selected_metric_interpretation,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PUBLISHED_DIR = PROJECT_ROOT / "data" / "published"

MASTER_PATH = PUBLISHED_DIR / "master_ndis_service_area_quarter_all_available_scoped.csv"
SERVICE_TYPE_PATH = PUBLISHED_DIR / "master_ndis_service_area_quarter_service_type_custom.csv"

MIN_QUARTER = "2024Q2"
DEFAULT_BENCHMARK_QUARTER = "2024Q2"

PLAN_COL = "service_area_funded_plans_per_1000_population_2025_erp"
UTIL_COL = "service_area_mean_plan_utilisation"
PLAN_COUNT_COL = "funded_plans_count"
POP_COL = "population_2025_erp"

PLAN_GAP_COL = "funded_plans_per_1000_gap_from_national"
UTIL_GAP_COL = "mean_plan_utilisation_gap_from_national"

PLAN_BENCHMARK_COL = "plans_per_1000_benchmark_value"
UTIL_BENCHMARK_COL = "mean_utilisation_benchmark_value"

SDAC_PER_1000 = 214.0

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

METRICS = {
    PLAN_GAP_COL: {
        "label": "Plan coverage gap",
        "short": "Plan coverage gap",
        "definition": "Observed funded plans per 1,000 population minus benchmark funded plans per 1,000 population.",
    },
    UTIL_GAP_COL: {
        "label": "Utilisation gap",
        "short": "Utilisation gap",
        "definition": "Benchmark mean plan utilisation minus observed mean plan utilisation.",
    },
    "plans_per_1000_change_from_baseline": {
        "label": "Plan coverage change",
        "short": "Plan coverage change",
        "definition": "Selected quarter funded plans per 1,000 population minus reference quarter funded plans per 1,000 population.",
    },
    "mean_plan_utilisation_change_from_baseline": {
        "label": "Utilisation change",
        "short": "Utilisation change",
        "definition": "Selected quarter mean plan utilisation minus reference quarter mean plan utilisation.",
    },
}


st.set_page_config(
    page_title="Good Measure | NDIS Market Saturation Atlas",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def quarter_key(value: object) -> tuple[int, int]:
    text = str(value)
    match = re.match(r"^(\d{4})Q([1-4])$", text)
    if not match:
        return (9999, 9)
    return (int(match.group(1)), int(match.group(2)))


def in_scope(value: object) -> bool:
    return quarter_key(value) >= quarter_key(MIN_QUARTER)


def num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)


def weighted_mean(values: pd.Series, weights: pd.Series | None = None) -> float:
    values = num(values)

    if weights is None:
        return float(values.mean()) if values.notna().any() else np.nan

    weights = num(weights)
    mask = values.notna() & weights.notna() & (weights > 0)

    if not mask.any():
        return float(values.mean()) if values.notna().any() else np.nan

    return float(np.average(values[mask], weights=weights[mask]))


def metric_axis_title(metric: str) -> str:
    return app_metric_axis_title(metric, METRICS, PLAN_GAP_COL, UTIL_GAP_COL)


def selected_metric_interpretation(metric: str, value: object) -> str:
    return app_selected_metric_interpretation(metric, value, PLAN_GAP_COL, UTIL_GAP_COL)


def get_query_param(name: str) -> str | None:
    try:
        value = st.query_params.get(name)
    except Exception:
        value = None

    if isinstance(value, list):
        value = value[0] if value else None

    if value is None or str(value).strip() == "":
        return None

    return str(value)


def service_type_group(value: object) -> str:
    if pd.isna(value):
        return "Other Core"

    text = str(value).strip()

    if text in SERVICE_TYPE_ORDER:
        return text

    low = text.lower()

    rules = [
        ("Support Coordination", ["support coordination", "coordination of supports", "recovery coach"]),
        ("Plan Management", ["plan management", "financial intermediary"]),
        ("Therapy", ["therapy", "therapeutic", "psychologist", "physiotherapist", "occupational therapist", "speech", "dietitian"]),
        ("Early Childhood Supports", ["early childhood", "early intervention"]),
        ("Shared Accommodation Supports", ["shared accommodation", "supported independent living", "sil", "sda", "specialist disability accommodation"]),
        ("High Needs Personal Care", ["high needs", "high intensity", "complex care", "overnight", "sleepover"]),
        ("Personal Care", ["personal care", "self-care", "self care", "daily activities", "assistance with daily life", "household tasks"]),
        ("Group Centre Care", ["group centre", "centre based", "centre-based", "group activities", "group activity"]),
        ("Community Participation Care", ["community participation", "social and community", "participate community", "civic participation"]),
        ("Capital", ["capital", "assistive technology", "home modification", "vehicle modification", "equipment"]),
        ("Other Capacity Building", ["capacity building", "improved", "behaviour support", "employment", "relationships", "lifelong learning", "choice and control", "training"]),
        ("Other Core", ["core", "transport", "consumables", "daily living"]),
    ]

    for category, terms in rules:
        if any(term in low for term in terms):
            return category

    return "Other Core"


@st.cache_data(show_spinner=False)
def load_master() -> pd.DataFrame:
    if not MASTER_PATH.exists():
        raise FileNotFoundError(f"Main published data not found: {MASTER_PATH}")

    data = pd.read_csv(MASTER_PATH, low_memory=False)

    if "quarter" not in data.columns and "reporting_quarter" in data.columns:
        data["quarter"] = data["reporting_quarter"]

    if "ndis_service_area" not in data.columns and "map_key" in data.columns:
        data["ndis_service_area"] = data["map_key"]

    if "map_key" not in data.columns:
        data["map_key"] = data["ndis_service_area"]

    aliases = {
        "funded_plans_per_1000_population_2025_erp": PLAN_COL,
        "funded_plans_per_1000": PLAN_COL,
        "mean_plan_utilisation": UTIL_COL,
    }

    for source, target in aliases.items():
        if target not in data.columns and source in data.columns:
            data[target] = data[source]

    required = [
        "quarter",
        "map_key",
        "ndis_service_area",
        "remoteness_category",
        POP_COL,
        PLAN_COUNT_COL,
        PLAN_COL,
        UTIL_COL,
    ]

    missing = [col for col in required if col not in data.columns]
    if missing:
        raise ValueError("Main published data missing required columns: " + ", ".join(missing))

    data["quarter"] = data["quarter"].astype(str)
    data = data.loc[data["quarter"].map(in_scope)].copy()

    for col in [POP_COL, PLAN_COUNT_COL, PLAN_COL, UTIL_COL]:
        data[col] = num(data[col])

    data["ndis_service_area"] = data["ndis_service_area"].astype(str)
    data["map_key"] = data["map_key"].astype(str)
    data["remoteness_category"] = data["remoteness_category"].fillna("Unknown").astype(str)

    if "service_area_state_label" not in data.columns:
        data["service_area_state_label"] = data["ndis_service_area"]

    data = data.loc[~data["ndis_service_area"].isin(["ALL", "Other", "Missing", "nan", "None"])].copy()
    data = data.drop_duplicates(["quarter", "map_key"]).copy()

    return data


@st.cache_data(show_spinner=False)
def load_service_type() -> pd.DataFrame:
    if not SERVICE_TYPE_PATH.exists():
        return pd.DataFrame()

    data = pd.read_csv(SERVICE_TYPE_PATH, low_memory=False)

    if "quarter" not in data.columns and "reporting_quarter" in data.columns:
        data["quarter"] = data["reporting_quarter"]

    if "map_key" not in data.columns and "ndis_service_area" in data.columns:
        data["map_key"] = data["ndis_service_area"]

    if "service_type_payment_share_of_area_total" not in data.columns:
        return pd.DataFrame()

    if "service_type" not in data.columns:
        data["service_type"] = "Other Core"

    data["quarter"] = data["quarter"].astype(str)
    data = data.loc[data["quarter"].map(in_scope)].copy()

    data["ndis_service_area"] = data["ndis_service_area"].astype(str)
    data["map_key"] = data["map_key"].astype(str)
    data["service_type"] = data["service_type"].astype(str)

    if "service_type_group" not in data.columns:
        data["service_type_group"] = data["service_type"].map(service_type_group)
    else:
        data["service_type_group"] = data["service_type_group"].fillna(data["service_type"]).map(service_type_group)

    for col in [
        "service_type_payment_share_of_area_total",
        "service_type_payment_amount",
        "service_type_payment_per_1000_population",
        "population_2025_erp",
    ]:
        if col in data.columns:
            data[col] = num(data[col])

    data = data.loc[~data["ndis_service_area"].isin(["ALL", "Other", "Missing", "nan", "None"])].copy()

    if "service_area_state_label" not in data.columns:
        data["service_area_state_label"] = data["ndis_service_area"]

    return data


def apply_service_category_proxy(
    data: pd.DataFrame,
    service_type_data: pd.DataFrame,
    selected_categories: list[str],
    exclude_selected: bool,
) -> pd.DataFrame:
    out = data.copy()

    out["funded_plans_count_raw"] = out[PLAN_COUNT_COL]
    out["plans_per_1000_raw"] = out[PLAN_COL]
    out["mean_plan_utilisation_raw"] = out[UTIL_COL]

    if service_type_data.empty or not selected_categories:
        out["included_service_type_share"] = 1.0
        out["service_type_filter_label"] = "All service categories"
        return out

    selected = set(selected_categories)

    if exclude_selected:
        included = [x for x in SERVICE_TYPE_ORDER if x not in selected]
        label = "All except: " + ", ".join(selected_categories)
    else:
        included = [x for x in SERVICE_TYPE_ORDER if x in selected]
        label = ", ".join(included) if included else "No selected service categories"

    subset = service_type_data.loc[service_type_data["service_type_group"].isin(included)].copy()

    shares = (
        subset.groupby(["quarter", "ndis_service_area"], dropna=False)
        .agg(included_service_type_share=("service_type_payment_share_of_area_total", "sum"))
        .reset_index()
    )

    out = out.merge(shares, on=["quarter", "ndis_service_area"], how="left")
    out["included_service_type_share"] = num(out["included_service_type_share"]).fillna(0).clip(0, 1)

    out["service_type_filter_label"] = label
    out[PLAN_COUNT_COL] = out["funded_plans_count_raw"] * out["included_service_type_share"]
    out[PLAN_COL] = out["plans_per_1000_raw"] * out["included_service_type_share"]
    out[UTIL_COL] = out["mean_plan_utilisation_raw"]

    return out


def apply_benchmark(data: pd.DataFrame, basis: str, historical_quarter: str) -> pd.DataFrame:
    out = data.copy()

    for col in [PLAN_BENCHMARK_COL, UTIL_BENCHMARK_COL, PLAN_GAP_COL, UTIL_GAP_COL]:
        out = out.drop(columns=[col], errors="ignore")

    if basis == "National mean":
        rows = []

        for quarter, group in out.groupby("quarter", dropna=False):
            pop_sum = num(group[POP_COL]).sum()
            plan_sum = num(group[PLAN_COUNT_COL]).sum()

            rows.append({
                "quarter": quarter,
                PLAN_BENCHMARK_COL: plan_sum / pop_sum * 1000 if pop_sum > 0 else np.nan,
                UTIL_BENCHMARK_COL: weighted_mean(group[UTIL_COL], group[PLAN_COUNT_COL]),
            })

        out = out.merge(pd.DataFrame(rows), on="quarter", how="left")
        out["benchmark_basis_label"] = "national mean"
        out["benchmark_reference_quarter"] = out["quarter"]

    elif basis == "Remoteness category mean":
        rows = []

        for key, group in out.groupby(["quarter", "remoteness_category"], dropna=False):
            quarter, remoteness = key
            pop_sum = num(group[POP_COL]).sum()
            plan_sum = num(group[PLAN_COUNT_COL]).sum()

            rows.append({
                "quarter": quarter,
                "remoteness_category": remoteness,
                PLAN_BENCHMARK_COL: plan_sum / pop_sum * 1000 if pop_sum > 0 else np.nan,
                UTIL_BENCHMARK_COL: weighted_mean(group[UTIL_COL], group[PLAN_COUNT_COL]),
            })

        out = out.merge(pd.DataFrame(rows), on=["quarter", "remoteness_category"], how="left")
        out["benchmark_basis_label"] = "remoteness-category mean"
        out["benchmark_reference_quarter"] = out["quarter"]

    elif basis == "Selected historical quarter":
        ref = (
            out.loc[out["quarter"].astype(str) == str(historical_quarter), ["map_key", PLAN_COL, UTIL_COL]]
            .drop_duplicates("map_key")
            .rename(columns={PLAN_COL: PLAN_BENCHMARK_COL, UTIL_COL: UTIL_BENCHMARK_COL})
        )

        out = out.merge(ref, on="map_key", how="left")
        out["benchmark_basis_label"] = f"historical quarter {historical_quarter}"
        out["benchmark_reference_quarter"] = historical_quarter

    else:
        rows = []
        for quarter, group in out.groupby("quarter", dropna=False):
            rows.append({
                "quarter": quarter,
                UTIL_BENCHMARK_COL: weighted_mean(group[UTIL_COL], group[PLAN_COUNT_COL]),
            })

        out = out.merge(pd.DataFrame(rows), on="quarter", how="left")
        out[PLAN_BENCHMARK_COL] = SDAC_PER_1000
        out["benchmark_basis_label"] = "service-area disability estimate 0.214"
        out["benchmark_reference_quarter"] = out["quarter"]

    out[PLAN_GAP_COL] = num(out[PLAN_COL]) - num(out[PLAN_BENCHMARK_COL])
    out[UTIL_GAP_COL] = num(out[UTIL_BENCHMARK_COL]) - num(out[UTIL_COL])

    plan_lower = out[PLAN_GAP_COL] < 0
    util_lower = out[UTIL_GAP_COL] > 0

    out["market_position_typology"] = np.select(
        [
            plan_lower & util_lower,
            plan_lower & ~util_lower,
            ~plan_lower & util_lower,
            ~plan_lower & ~util_lower,
        ],
        [
            "Lower coverage / lower utilisation",
            "Lower coverage / higher utilisation",
            "Higher coverage / lower utilisation",
            "Higher coverage / higher utilisation",
        ],
        default="Insufficient benchmark data",
    )

    out["benchmark_position"] = np.select(
        [out[PLAN_GAP_COL] < 0, out[PLAN_GAP_COL] > 0],
        ["Below benchmark", "Above benchmark"],
        default="At benchmark",
    )

    out.loc[out[PLAN_GAP_COL].isna(), "benchmark_position"] = "Insufficient benchmark data"

    return out


def add_reference_change_measures(data: pd.DataFrame, reference_quarter: str) -> pd.DataFrame:
    out = data.copy()

    reference = (
        out.loc[out["quarter"].astype(str) == str(reference_quarter), ["map_key", PLAN_COL, UTIL_COL]]
        .drop_duplicates("map_key")
        .rename(columns={PLAN_COL: "baseline_plans_per_1000", UTIL_COL: "baseline_mean_plan_utilisation"})
    )

    out = out.drop(
        columns=[c for c in out.columns if c.startswith("baseline_") or c.endswith("_change_from_baseline")],
        errors="ignore",
    )

    out = out.merge(reference, on="map_key", how="left")
    out["plans_per_1000_change_from_baseline"] = num(out[PLAN_COL]) - num(out["baseline_plans_per_1000"])
    out["mean_plan_utilisation_change_from_baseline"] = num(out[UTIL_COL]) - num(out["baseline_mean_plan_utilisation"])
    out["baseline_quarter"] = reference_quarter

    return out


def filtered_current(data: pd.DataFrame, quarter: str, remoteness: list[str], metric: str) -> pd.DataFrame:
    out = data.loc[data["quarter"].astype(str) == str(quarter)].copy()

    if remoteness:
        out = out.loc[out["remoteness_category"].isin(remoteness)].copy()

    out[metric] = num(out[metric])
    return out


def render_css() -> None:
    st.markdown(
        """
        <style>
        [data-testid="stAppViewContainer"] {
            background:
                linear-gradient(90deg,
                #061A2E 0,
                #061A2E 2.3rem,
                #F8FAFC 2.3rem,
                #F8FAFC calc(100% - 2.3rem),
                #061A2E calc(100% - 2.3rem),
                #061A2E 100%);
        }

        .block-container {
            max-width: 1840px;
            padding-top: 0.55rem;
            padding-left: 2.7rem;
            padding-right: 2.7rem;
            padding-bottom: 1.2rem;
        }

        .gm-hero {
            border: 1px solid rgba(6,26,46,0.12);
            border-radius: 8px;
            padding: 0.82rem 1rem;
            margin-bottom: 0.55rem;
            background: #FFFFFF;
            box-shadow: 0 2px 8px rgba(6,26,46,0.045);
        }

        .gm-kicker {
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-size: 0.64rem;
            font-weight: 800;
            color: #6B5A45;
            margin-bottom: 0.12rem;
        }

        .gm-title {
            font-size: 1.48rem;
            font-weight: 850;
            color: #061A2E;
            margin-bottom: 0.12rem;
        }

        .gm-subtitle {
            color: #26384A;
            line-height: 1.24;
            font-size: 0.86rem;
        }

        .gm-nav-tabs {
            background: #061A2E;
            border-radius: 8px;
            padding: 0.38rem;
            margin: 0.45rem 0 0.55rem 0;
            box-shadow: 0 3px 12px rgba(6,26,46,0.14);
        }

        div[data-testid="stSegmentedControl"] {
            width: 100%;
        }

        div[data-testid="stSegmentedControl"] div[role="radiogroup"] {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.35rem;
            width: 100%;
        }

        div[data-testid="stSegmentedControl"] label {
            justify-content: center;
            min-height: 2.25rem;
            border-radius: 10px !important;
            font-weight: 800;
            white-space: nowrap;
            padding-left: 0.2rem !important;
            padding-right: 0.2rem !important;
        }

        div[data-testid="stMetric"] {
            background: #FFF7E6;
            border-left: 4px solid #F2B705;
            border-radius: 8px;
            padding: 0.46rem 0.62rem;
            min-height: 64px;
        }

        div[data-testid="stMetricValue"] {
            font-size: 1.04rem !important;
            line-height: 1.02 !important;
        }

        div[data-testid="stMetricLabel"] {
            font-size: 0.68rem !important;
            line-height: 1.02 !important;
        }

        div[data-testid="stExpander"] details summary {
            min-height: 1.6rem !important;
            padding-top: 0.12rem !important;
            padding-bottom: 0.12rem !important;
            font-size: 0.84rem !important;
        }

        label {
            font-size: 0.72rem !important;
        }

        div[data-baseweb="select"] > div,
        div[data-baseweb="input"] > div {
            min-height: 2.1rem !important;
            font-size: 0.82rem !important;
        }

        .stAlert {
            padding-top: 0.38rem !important;
            padding-bottom: 0.38rem !important;
        }

        .gm-compact-note {
            border-left: 4px solid #F2B705;
            background: rgba(242,183,5,0.10);
            padding: 0.48rem 0.68rem;
            border-radius: 0 8px 8px 0;
            margin: 0.5rem 0 0.6rem 0;
            font-size: 0.86rem;
        }

        .gm-finding {
            border: 1px solid rgba(6,26,46,0.12);
            border-left: 5px solid #F2B705;
            background: #FFFFFF;
            border-radius: 8px;
            padding: 0.72rem 0.85rem;
            margin: 0.55rem 0 0.7rem 0;
        }

        .gm-finding-title {
            color: #061A2E;
            font-size: 0.95rem;
            font-weight: 850;
            margin-bottom: 0.25rem;
        }

        .gm-finding-body {
            color: #26384A;
            font-size: 0.88rem;
            line-height: 1.38;
        }

        .gm-pill-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.35rem;
            margin-top: 0.45rem;
        }

        .gm-pill {
            border: 1px solid rgba(6,26,46,0.16);
            border-radius: 999px;
            padding: 0.18rem 0.52rem;
            font-size: 0.72rem;
            font-weight: 720;
            color: #061A2E;
            background: #F8FAFC;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

def render_header() -> None:
    st.markdown(
        """
        <div class="gm-hero">
            <div class="gm-kicker">Good Measure technical case study</div>
            <div class="gm-title">NDIS Market Saturation Atlas</div>
            <div class="gm-subtitle">Applied public-data, geospatial and benchmark analysis prototype.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_navigation(active: str) -> str:
    nav_options = ["Atlas", "Funded Plans", "Service area", "Data"]

    if "gm_active_view" not in st.session_state or st.session_state.get("gm_active_view") not in nav_options:
        st.session_state["gm_active_view"] = active if active in nav_options else "Atlas"

    if active in nav_options and active != st.session_state.get("gm_active_view"):
        st.session_state["gm_active_view"] = active

    st.markdown('<div class="gm-nav-tabs">', unsafe_allow_html=True)
    selected = st.segmented_control(
        "Navigation",
        nav_options,
        default=st.session_state["gm_active_view"],
        selection_mode="single",
        label_visibility="collapsed",
        width="stretch",
    )
    st.markdown("</div>", unsafe_allow_html=True)

    if selected in nav_options:
        st.session_state["gm_active_view"] = selected

    return st.session_state["gm_active_view"]

def metric_cards(filtered: pd.DataFrame, metric: str, quarter: str) -> None:
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Quarter", quarter)
    c2.metric("Areas", f"{len(filtered):,}")
    c3.metric("Plans benchmark", fmt(num(filtered[PLAN_BENCHMARK_COL]).median()))
    c4.metric("Utilisation benchmark", fmt_pct(num(filtered[UTIL_BENCHMARK_COL]).median()))
    c5.metric("Median plan value", f"{fmt(num(filtered[PLAN_COL]).median())} per 1,000")
    c6.metric("Mean plan utilisation", fmt_pct(num(filtered[UTIL_COL]).mean()))


def key_finding(filtered: pd.DataFrame, metric: str, quarter: str, selected_categories: list[str], exclude_selected: bool, remoteness: list[str], service_area_label: str | None = None) -> None:
    if filtered.empty:
        st.info("No key finding available for the current filter set.")
        return

    service_label = "All service categories"
    if selected_categories:
        service_label = ("All except: " if exclude_selected else "") + ", ".join(selected_categories)

    benchmark_label = filtered["benchmark_basis_label"].dropna().astype(str).iloc[0] if "benchmark_basis_label" in filtered.columns and filtered["benchmark_basis_label"].notna().any() else "selected benchmark"
    scope_label = service_area_label or "the current filter set"
    if service_area_label == "Australia":
        scope_label = "Australian service areas in the current filter set"

    metric_value = num(filtered[metric]).median()

    values = num(filtered[metric])
    below = int((values > 0).sum())
    above = int((values < 0).sum())
    valid = int(values.notna().sum())

    strongest = filtered.copy()
    strongest[metric] = num(strongest[metric])
    strongest = strongest.dropna(subset=[metric])
    lead = None
    if not strongest.empty and "service_area_state_label" in strongest.columns:
        lead_row = strongest.reindex(strongest[metric].abs().sort_values(ascending=False).index).iloc[0]
        lead = f"{lead_row['service_area_state_label']} is the largest absolute signal ({fmt(lead_row[metric])}; {selected_metric_interpretation(metric, lead_row[metric]).lower()})."

    title = f"Key finding: {html.escape(str(scope_label))}"
    body = (
        f"In {quarter}, {html.escape(str(scope_label))} has a median {html.escape(METRICS[metric]['label'].lower())} "
        f"of {fmt(metric_value)} against the {html.escape(str(benchmark_label))}. "
    )

    if metric == PLAN_GAP_COL:
        below = int((values < 0).sum())
        above = int((values > 0).sum())
        body += f"{below:,} of {valid:,} service areas are below benchmark and {above:,} are above benchmark. "
    elif metric == UTIL_GAP_COL:
        below = int((values > 0).sum())
        above = int((values < 0).sum())
        body += f"{below:,} of {valid:,} service areas are below benchmark and {above:,} are above benchmark. "
    else:
        body += f"{above:,} of {valid:,} service areas increased since the reference quarter and {below:,} decreased. "

    if lead:
        body += html.escape(lead)

    st.markdown(
        f"""
        <div class="gm-finding">
            <div class="gm-finding-title">{title}</div>
            <div class="gm-finding-body">{body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def chart_ranked(filtered: pd.DataFrame, metric: str, limit: int = 25, title: str | None = None) -> alt.Chart:
    data = filtered.copy()
    data[metric] = num(data[metric])
    data["selected_metric_interpretation"] = data[metric].map(lambda value: selected_metric_interpretation(metric, value))
    data = data.sort_values(metric, ascending=False).head(limit)

    if data.empty:
        data = pd.DataFrame({
            "service_area_state_label": ["No data"],
            metric: [0],
            "remoteness_category": ["No data"],
            "selected_metric_interpretation": ["Insufficient data"],
        })

    y_order = data["service_area_state_label"].tolist()

    chart = (
        alt.Chart(data)
        .mark_bar(stroke=GM_NAVY, strokeWidth=0.4)
        .encode(
            y=alt.Y(
                "service_area_state_label:N",
                sort=y_order,
                title="Service area",
                axis=alt.Axis(labelLimit=440, labelOverlap=False),
            ),
            x=alt.X(f"{metric}:Q", title=metric_axis_title(metric)),
            color=alt.Color(
                "selected_metric_interpretation:N",
                title="Interpretation",
                scale=alt.Scale(
                    domain=[
                        "Below selected benchmark",
                        "Above selected benchmark",
                        "Increase since reference",
                        "Decrease since reference",
                        "Near benchmark",
                        "No material change",
                        "Insufficient data",
                    ],
                    range=[GM_RED, GM_GREEN, GM_GREEN, GM_RED, GM_AMBER, GM_AMBER, "#B8C2CC"],
                ),
            ),
            tooltip=[
                alt.Tooltip("service_area_state_label:N", title="Service area"),
                alt.Tooltip("remoteness_category:N", title="Remoteness"),
                alt.Tooltip("benchmark_basis_label:N", title="Benchmark basis"),
                alt.Tooltip(f"{PLAN_COL}:Q", title="Observed plans per 1,000", format=".2f"),
                alt.Tooltip(f"{PLAN_BENCHMARK_COL}:Q", title="Plans benchmark", format=".2f"),
                alt.Tooltip(f"{UTIL_COL}:Q", title="Observed utilisation (%)", format=".2f"),
                alt.Tooltip(f"{UTIL_BENCHMARK_COL}:Q", title="Utilisation benchmark (%)", format=".2f"),
                alt.Tooltip(f"{metric}:Q", title=METRICS[metric]["label"], format=".2f"),
                alt.Tooltip("selected_metric_interpretation:N", title="Interpretation"),
            ],
        )
        .properties(
            title=title or f"Service areas ranked by {METRICS[metric]['label']}",
            height=max(420, min(len(data), 90) * 22),
        )
    )

    rule = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(strokeDash=[4, 3]).encode(x="x:Q")
    return gm_chart(chart + rule)

def chart_scatter(filtered: pd.DataFrame, title: str | None = None) -> alt.Chart:
    data = filtered.copy()
    data[PLAN_COL] = num(data[PLAN_COL])
    data[UTIL_COL] = num(data[UTIL_COL])
    data[PLAN_BENCHMARK_COL] = num(data[PLAN_BENCHMARK_COL])
    data[UTIL_BENCHMARK_COL] = num(data[UTIL_BENCHMARK_COL])
    data["plan_gap_label"] = data[PLAN_GAP_COL].map(lambda value: selected_metric_interpretation(PLAN_GAP_COL, value))
    data["util_gap_label"] = data[UTIL_GAP_COL].map(lambda value: selected_metric_interpretation(UTIL_GAP_COL, value))

    plan_ref = data[PLAN_BENCHMARK_COL].median() if data[PLAN_BENCHMARK_COL].notna().any() else data[PLAN_COL].median()
    util_ref = data[UTIL_BENCHMARK_COL].median() if data[UTIL_BENCHMARK_COL].notna().any() else data[UTIL_COL].median()
    ref_label = data["benchmark_basis_label"].dropna().astype(str).iloc[0] if "benchmark_basis_label" in data.columns and data["benchmark_basis_label"].notna().any() else "selected benchmark"
    if data[PLAN_BENCHMARK_COL].nunique(dropna=True) > 1 or data[UTIL_BENCHMARK_COL].nunique(dropna=True) > 1:
        ref_label = f"Median {ref_label.lower()} reference"

    points = (
        alt.Chart(data)
        .mark_circle(size=95, opacity=0.75, stroke="#061A2E", strokeWidth=0.4)
        .encode(
            x=alt.X(f"{PLAN_COL}:Q", title="Funded plans per 1,000 population", scale=alt.Scale(zero=False)),
            y=alt.Y(f"{UTIL_COL}:Q", title="Mean plan utilisation", scale=alt.Scale(zero=False)),
            color=alt.Color("market_position_typology:N", title="Position"),
            tooltip=[
                alt.Tooltip("service_area_state_label:N", title="Service area"),
                alt.Tooltip("remoteness_category:N", title="Remoteness"),
                alt.Tooltip(f"{PLAN_COL}:Q", title="Plans per 1,000", format=".2f"),
                alt.Tooltip(f"{PLAN_BENCHMARK_COL}:Q", title="Plans benchmark", format=".2f"),
                alt.Tooltip(f"{PLAN_GAP_COL}:Q", title="Plan gap", format=".2f"),
                alt.Tooltip("plan_gap_label:N", title="Plan interpretation"),
                alt.Tooltip(f"{UTIL_COL}:Q", title="Utilisation", format=".2f"),
                alt.Tooltip(f"{UTIL_BENCHMARK_COL}:Q", title="Utilisation benchmark", format=".2f"),
                alt.Tooltip(f"{UTIL_GAP_COL}:Q", title="Utilisation gap", format=".2f"),
                alt.Tooltip("util_gap_label:N", title="Utilisation interpretation"),
                alt.Tooltip("benchmark_basis_label:N", title="Benchmark basis"),
            ],
        )
        .properties(title=title or "Market position by service area", height=410)
    )

    x_rule = (
        alt.Chart(pd.DataFrame({"x": [plan_ref], "label": [ref_label]}))
        .mark_rule(strokeDash=[6, 4], strokeWidth=1.4, color=GM_NAVY)
        .encode(x="x:Q", tooltip=[alt.Tooltip("label:N", title="Benchmark"), alt.Tooltip("x:Q", title="Plans benchmark", format=".2f")])
    )
    y_rule = (
        alt.Chart(pd.DataFrame({"y": [util_ref], "label": [ref_label]}))
        .mark_rule(strokeDash=[6, 4], strokeWidth=1.4, color=GM_NAVY)
        .encode(y="y:Q", tooltip=[alt.Tooltip("label:N", title="Benchmark"), alt.Tooltip("y:Q", title="Utilisation benchmark", format=".2f")])
    )

    return gm_chart(points + x_rule + y_rule)


def trend_line(data: pd.DataFrame, y_col: str, title: str, y_title: str) -> alt.Chart:
    trend = (
        data.groupby("quarter", as_index=False)[y_col]
        .mean()
        .sort_values("quarter", key=lambda s: s.map(quarter_key))
    )

    order = sorted(trend["quarter"].dropna().astype(str).unique().tolist(), key=quarter_key)

    chart = (
        alt.Chart(trend)
        .mark_line(point=True, strokeWidth=2.5)
        .encode(
            x=alt.X("quarter:N", sort=order, title="Quarter"),
            y=alt.Y(f"{y_col}:Q", title=y_title, scale=alt.Scale(zero=False)),
            tooltip=[
                alt.Tooltip("quarter:N", title="Quarter"),
                alt.Tooltip(f"{y_col}:Q", title=y_title, format=".2f"),
            ],
        )
        .properties(title=title, height=230)
    )
    return gm_chart(chart)

def trend_chart(area_all: pd.DataFrame, observed_col: str, benchmark_col: str, title: str, y_title: str) -> alt.Chart:
    trend = area_all[["quarter", observed_col, benchmark_col]].copy()
    trend = trend.rename(columns={observed_col: "Observed", benchmark_col: "Benchmark"})
    trend = trend.melt("quarter", var_name="series", value_name="value")
    trend["value"] = num(trend["value"])
    order = sorted(trend["quarter"].dropna().astype(str).unique().tolist(), key=quarter_key)

    chart = (
        alt.Chart(trend)
        .mark_line(point=True, strokeWidth=2.5)
        .encode(
            x=alt.X("quarter:N", sort=order, title="Quarter"),
            y=alt.Y("value:Q", title=y_title, scale=alt.Scale(zero=False)),
            color=alt.Color("series:N", title=None),
            tooltip=[
                alt.Tooltip("quarter:N", title="Quarter"),
                alt.Tooltip("series:N", title="Series"),
                alt.Tooltip("value:Q", title=y_title, format=".2f"),
            ],
        )
        .properties(title=title, height=310)
    )
    return gm_chart(chart)


def payment_share_benchmark_frame(frame: pd.DataFrame, group_cols: list[str], value_name: str = "benchmark_share_percent") -> pd.DataFrame:
    columns = group_cols + ["service_type_group", value_name]

    if frame.empty:
        return pd.DataFrame(columns=columns)

    working = frame.copy()
    working["service_type_group"] = working["service_type_group"].map(service_type_group)
    working["service_type_payment_amount"] = num(working.get("service_type_payment_amount", pd.Series(dtype=float))).fillna(0)
    working["service_type_payment_share_of_area_total"] = num(working.get("service_type_payment_share_of_area_total", pd.Series(dtype=float))).fillna(0)

    if working["service_type_payment_amount"].sum() > 0:
        grouped = (
            working.groupby(group_cols + ["service_type_group"], dropna=False, as_index=False)
            .agg(payment_amount=("service_type_payment_amount", "sum"))
        )

        if group_cols:
            totals = grouped.groupby(group_cols, dropna=False, as_index=False).agg(total_payment_amount=("payment_amount", "sum"))
            grouped = grouped.merge(totals, on=group_cols, how="left")
        else:
            grouped["total_payment_amount"] = grouped["payment_amount"].sum()

        grouped[value_name] = np.where(
            grouped["total_payment_amount"] > 0,
            grouped["payment_amount"] / grouped["total_payment_amount"] * 100,
            0,
        )
        return grouped[columns]

    grouped = (
        working.groupby(group_cols + ["service_type_group"], dropna=False, as_index=False)
        .agg(**{value_name: ("service_type_payment_share_of_area_total", "mean")})
    )
    grouped[value_name] = num(grouped[value_name]).fillna(0) * 100
    return grouped[columns]


def build_service_mix_frame(
    service_type_data: pd.DataFrame,
    current: pd.DataFrame,
    quarter: str,
    selected_area: str | None = None,
    benchmark_basis: str = "National mean",
    benchmark_quarter: str | None = None,
) -> tuple[pd.DataFrame, str]:
    benchmark_quarter = benchmark_quarter or quarter
    categories = pd.DataFrame({"service_type_group": SERVICE_TYPE_ORDER})
    output_columns = [
        "ndis_service_area",
        "service_area_state_label",
        "remoteness_category",
        "service_type_group",
        "payment_share_percent",
        "benchmark_share_percent",
        "payment_share_gap_pp",
        "payment_amount",
    ]

    if service_type_data.empty or current.empty:
        return pd.DataFrame(columns=output_columns), "selected benchmark payment mix"

    areas = current[["ndis_service_area", "service_area_state_label", "remoteness_category"]].drop_duplicates().copy()

    if selected_area and selected_area != "Australia":
        areas = areas.loc[areas["ndis_service_area"].eq(selected_area)].copy()

    if areas.empty:
        return pd.DataFrame(columns=output_columns), "selected benchmark payment mix"

    mix = service_type_data.loc[service_type_data["quarter"].astype(str).eq(str(quarter))].copy()
    mix = mix.loc[mix["ndis_service_area"].isin(areas["ndis_service_area"])].copy()

    if selected_area == "Australia":
        grouped = categories.merge(
            payment_share_benchmark_frame(mix, [], value_name="payment_share_percent"),
            on="service_type_group",
            how="left",
        )
        amounts = (
            mix.groupby("service_type_group", as_index=False)
            .agg(payment_amount=("service_type_payment_amount", "sum"))
        )
        grouped = grouped.merge(amounts, on="service_type_group", how="left")
        grouped["ndis_service_area"] = "Australia"
        grouped["service_area_state_label"] = "Australia"
        grouped["remoteness_category"] = "Selected scope"
    else:
        skeleton = areas.merge(categories, how="cross")
        grouped = (
            mix.groupby(["ndis_service_area", "service_type_group"], dropna=False)
            .agg(
                payment_share=("service_type_payment_share_of_area_total", "sum"),
                payment_amount=("service_type_payment_amount", "sum"),
            )
            .reset_index()
        ) if not mix.empty else pd.DataFrame(columns=["ndis_service_area", "service_type_group", "payment_share", "payment_amount"])

        grouped = skeleton.merge(grouped, on=["ndis_service_area", "service_type_group"], how="left")
        grouped["payment_share"] = num(grouped["payment_share"]).fillna(0)
        grouped["payment_share_percent"] = grouped["payment_share"] * 100
        grouped["payment_amount"] = num(grouped["payment_amount"]).fillna(0)

    if benchmark_basis == "Selected historical quarter":
        hist = service_type_data.loc[service_type_data["quarter"].astype(str).eq(str(benchmark_quarter))].copy()
        hist = hist.loc[hist["ndis_service_area"].isin(areas["ndis_service_area"])].copy()

        if selected_area == "Australia":
            bench = payment_share_benchmark_frame(hist, [])
            grouped = grouped.merge(bench, on="service_type_group", how="left")
        else:
            bench = payment_share_benchmark_frame(hist, ["ndis_service_area"])
            grouped = grouped.merge(bench, on=["ndis_service_area", "service_type_group"], how="left")

        benchmark_label = f"historical quarter {benchmark_quarter}"

    elif benchmark_basis == "Remoteness category mean":
        benchmark_source = service_type_data.loc[service_type_data["quarter"].astype(str).eq(str(quarter))].copy()

        if selected_area == "Australia":
            benchmark_source = benchmark_source.loc[
                benchmark_source["remoteness_category"].isin(areas["remoteness_category"].dropna().unique())
            ].copy()
            bench = payment_share_benchmark_frame(benchmark_source, [])
            grouped = grouped.merge(bench, on="service_type_group", how="left")
            benchmark_label = "selected remoteness-category payment mix"
        else:
            bench = payment_share_benchmark_frame(benchmark_source, ["remoteness_category"])
            grouped = grouped.merge(bench, on=["remoteness_category", "service_type_group"], how="left")
            benchmark_label = "remoteness-category payment mix"

    else:
        benchmark_source = service_type_data.loc[service_type_data["quarter"].astype(str).eq(str(quarter))].copy()
        bench = payment_share_benchmark_frame(benchmark_source, [])
        grouped = grouped.merge(bench, on="service_type_group", how="left")
        benchmark_label = "national payment mix"

    grouped["payment_share_percent"] = num(grouped["payment_share_percent"]).fillna(0)
    grouped["benchmark_share_percent"] = num(grouped["benchmark_share_percent"]).fillna(0)
    grouped["payment_amount"] = num(grouped["payment_amount"]).fillna(0)
    grouped["payment_share_gap_pp"] = grouped["payment_share_percent"] - grouped["benchmark_share_percent"]

    return grouped[output_columns], benchmark_label


def service_mix_chart(
    service_type_data: pd.DataFrame,
    current: pd.DataFrame,
    quarter: str,
    selected_area: str | None = None,
    benchmark_basis: str = "National mean",
    benchmark_quarter: str | None = None,
) -> None:
    grouped, benchmark_label = build_service_mix_frame(
        service_type_data=service_type_data,
        current=current,
        quarter=quarter,
        selected_area=selected_area,
        benchmark_basis=benchmark_basis,
        benchmark_quarter=benchmark_quarter,
    )

    if grouped.empty:
        st.info("No service-category data available for the current scope.")
        return

    strongest_mix = grouped.copy()
    strongest_mix["payment_share_gap_pp"] = num(strongest_mix["payment_share_gap_pp"])
    strongest_mix = strongest_mix.dropna(subset=["payment_share_gap_pp"])
    if not strongest_mix.empty:
        lead_row = strongest_mix.reindex(strongest_mix["payment_share_gap_pp"].abs().sort_values(ascending=False).index).iloc[0]
        lead_area = lead_row.get("service_area_state_label", selected_area or "Selected scope")
        lead_category = lead_row.get("service_type_group", "service category")
        lead_gap = lead_row.get("payment_share_gap_pp")
        lead_gap_value = safe_float(lead_gap)
        if lead_gap_value is None or abs(lead_gap_value) < 0.05:
            finding_body = (
                f"The observed service-category payment mix matches the "
                f"{html.escape(str(benchmark_label))} for this scope. "
                "Payment mix is a composition proxy, not a participant count."
            )
        else:
            direction = "higher" if lead_gap_value > 0 else "lower"
            finding_body = (
                "The largest absolute payment-mix difference is "
                f"<strong>{html.escape(str(lead_category))}</strong> in "
                f"<strong>{html.escape(str(lead_area))}</strong>: "
                f"{fmt(lead_gap, 1)} percentage points {direction} than the "
                f"{html.escape(str(benchmark_label))}. "
                "Payment mix is a composition proxy, not a participant count."
            )
        st.markdown(
            f"""
            <div class="gm-finding">
                <div class="gm-finding-title">Service-category mix signal</div>
                <div class="gm-finding-body">{finding_body}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if selected_area:
        title_area = "Australia" if selected_area == "Australia" else selected_area
        chart_height = max(390, len(SERVICE_TYPE_ORDER) * 32)
        chart = (
            alt.Chart(grouped)
            .mark_bar(stroke="#061A2E", strokeWidth=0.3, cornerRadiusEnd=3)
            .encode(
                y=alt.Y("service_type_group:N", sort=SERVICE_TYPE_ORDER, title="Service category", axis=alt.Axis(labelLimit=380)),
                x=alt.X(
                    "payment_share_gap_pp:Q",
                    title=f"Observed share minus {benchmark_label} (percentage points)",
                ),
                color=alt.Color(
                    "payment_share_gap_pp:Q",
                    title="+/- from benchmark (pp)",
                    scale=alt.Scale(scheme="redblue", reverse=True, domainMid=0),
                ),
                tooltip=[
                    alt.Tooltip("service_type_group:N", title="Service category"),
                    alt.Tooltip("payment_share_percent:Q", title="Observed payment share (%)", format=".1f"),
                    alt.Tooltip("benchmark_share_percent:Q", title="Benchmark payment share (%)", format=".1f"),
                    alt.Tooltip("payment_share_gap_pp:Q", title="+/- from benchmark (pp)", format="+.1f"),
                    alt.Tooltip("payment_amount:Q", title="Payment amount", format="$,.0f"),
                ],
            )
            .properties(
                title=f"{title_area}: service-category payment-share +/- from {benchmark_label} | {quarter}",
                height=chart_height,
            )
        )

        rule = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(strokeDash=[4, 3], color="#061A2E").encode(x="x:Q")
        st.altair_chart(gm_chart(chart + rule), width="stretch")
        return

    ranked = grouped.copy()
    ranked["absolute_gap_pp"] = num(ranked["payment_share_gap_pp"]).abs()
    ranked["service_area_category"] = (
        ranked["service_area_state_label"].astype(str) + " | " + ranked["service_type_group"].astype(str)
    )
    ranked = ranked.sort_values("absolute_gap_pp", ascending=False).head(35)
    y_order = ranked["service_area_category"].tolist()

    chart = (
        alt.Chart(ranked)
        .mark_bar(stroke="#061A2E", strokeWidth=0.25, cornerRadiusEnd=3)
        .encode(
            y=alt.Y(
                "service_area_category:N",
                sort=y_order,
                title="Service area and service category",
                axis=alt.Axis(labelLimit=520, labelOverlap=False),
            ),
            x=alt.X("payment_share_gap_pp:Q", title=f"Observed share minus {benchmark_label} (percentage points)"),
            color=alt.Color(
                "payment_share_gap_pp:Q",
                title="+/- from benchmark (pp)",
                scale=alt.Scale(scheme="redblue", reverse=True, domainMid=0),
            ),
            tooltip=[
                alt.Tooltip("service_area_state_label:N", title="Service area"),
                alt.Tooltip("remoteness_category:N", title="Remoteness"),
                alt.Tooltip("service_type_group:N", title="Service category"),
                alt.Tooltip("payment_share_percent:Q", title="Observed payment share (%)", format=".1f"),
                alt.Tooltip("benchmark_share_percent:Q", title="Benchmark payment share (%)", format=".1f"),
                alt.Tooltip("payment_share_gap_pp:Q", title="+/- from benchmark (pp)", format="+.1f"),
                alt.Tooltip("payment_amount:Q", title="Payment amount", format="$,.0f"),
            ],
        )
        .properties(
            title=f"Largest service-category payment-share gaps | {quarter} | {benchmark_label}",
            height=max(420, len(ranked) * 24),
        )
    )

    rule = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(strokeDash=[4, 3], color="#061A2E").encode(x="x:Q")
    st.altair_chart(gm_chart(chart + rule), width="stretch")

def build_controls(master: pd.DataFrame, service_type_data: pd.DataFrame, requested_area: str | None = None) -> dict:
    quarters = sorted(master["quarter"].dropna().astype(str).unique().tolist(), key=quarter_key)
    remoteness_values = [r for r in REMOTENESS_ORDER if r in set(master["remoteness_category"].dropna())]
    remoteness_values += sorted(set(master["remoteness_category"].dropna()) - set(remoteness_values))

    with st.expander("Evidence controls", expanded=True):
        row1 = st.columns([0.72, 1.05, 0.9, 1.22, 1.55])

        quarter = row1[0].selectbox("Quarter", quarters, index=len(quarters) - 1)

        benchmark_basis = row1[1].selectbox(
            "Benchmark basis",
            ["National mean", "Remoteness category mean", "Selected historical quarter", "Service-area disability estimate (0.214)"],
            index=0,
            help="Select the comparator used to calculate benchmark gaps. Positive gap values mean observed values are below the selected benchmark.",
        )

        if benchmark_basis == "Selected historical quarter":
            historical_index = quarters.index(DEFAULT_BENCHMARK_QUARTER) if DEFAULT_BENCHMARK_QUARTER in quarters else 0
            benchmark_quarter = row1[2].selectbox(
                "Benchmark quarter",
                quarters,
                index=historical_index,
                help="Reference quarter used for historical benchmark and change calculations.",
            )
        else:
            benchmark_quarter = quarter
            row1[2].text_input("Reference", value=quarter, disabled=True)

        area_options = ["Australia"] + sorted(
            master.loc[master["quarter"].astype(str).eq(str(quarter)), "ndis_service_area"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )

        if requested_area and requested_area in area_options:
            area_index = area_options.index(requested_area)
        else:
            area_index = 0

        selected_area = row1[3].selectbox(
            "Service area",
            area_options,
            index=area_index,
            help="Australia shows the selected national/filter scope. Other options show a single service-area profile.",
        ) if area_options else "Australia"

        metric = row1[4].selectbox(
            "Primary metric",
            list(METRICS.keys()),
            format_func=lambda key: f"{METRICS[key]['label']} - {METRICS[key]['definition']}",
            help="Controls the atlas colour, ranking chart and headline interpretation.",
        )

        row2 = st.columns([0.62, 1.7, 0.95, 1.85, 0.78])

        remoteness_mode = row2[0].radio("Remoteness", ["All", "Select"], horizontal=True)

        if remoteness_mode == "Select":
            selected_remoteness = row2[1].multiselect(
                "Remoteness categories",
                remoteness_values,
                default=remoteness_values,
                help="Filter service areas before calculating visible charts and interpretations.",
            )
        else:
            selected_remoteness = remoteness_values
            row2[1].caption("All remoteness categories included.")

        category_mode = row2[2].radio("Service categories", ["All", "Choose"], horizontal=True)

        if category_mode == "Choose":
            selected_categories = row2[3].multiselect(
                "Service categories",
                SERVICE_TYPE_ORDER,
                default=SERVICE_TYPE_ORDER,
                help="Payment-share proxy categories used to scale plan-count and plans-per-1,000 measures.",
            )
            exclude_selected = row2[4].checkbox("Exclude", help="Invert the selected service-category list.")
        else:
            selected_categories = []
            exclude_selected = False
            row2[3].caption("All service categories included.")

    return {
        "quarter": quarter,
        "benchmark_basis": benchmark_basis,
        "benchmark_quarter": benchmark_quarter,
        "selected_area": selected_area,
        "metric": metric,
        "selected_remoteness": selected_remoteness,
        "selected_categories": selected_categories,
        "exclude_selected": exclude_selected,
    }

@st.cache_data(show_spinner=False)
def locate_geo_file() -> Path | None:
    search_roots = [
        PROJECT_ROOT / "outputs" / "powerbi_map",
        PROJECT_ROOT / "data" / "geo",
        PROJECT_ROOT / "data" / "processed",
        PROJECT_ROOT / "data" / "published",
        PROJECT_ROOT / "data" / "raw",
        PROJECT_ROOT,
    ]

    suffixes = {".geojson", ".json", ".gpkg", ".shp"}
    likely_names = (
        "ndis_service_area_boundaries_simplified.geojson",
        "ndis_service_area_boundaries.geojson",
        "ndis_service_areas_simplified.geojson",
        "ndis_service_areas.geojson",
        "service_areas.geojson",
        "service_area.geojson",
    )

    for root in search_roots:
        if not root.exists():
            continue

        for name in likely_names:
            candidate = root / name
            if candidate.is_file():
                return candidate

    candidates: list[Path] = []

    for root in search_roots:
        if not root.exists():
            continue

        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in suffixes:
                continue

            name = path.name.lower()

            if "service" in name and ("area" in name or "district" in name or "ndis" in name):
                candidates.append(path)

    if not candidates:
        return None

    return sorted(
        candidates,
        key=lambda p: (
            0 if "powerbi_map" in str(p).lower() else 1,
            0 if p.suffix.lower() == ".geojson" else 1,
            len(str(p)),
            str(p),
        ),
    )[0]


def render_atlas(current: pd.DataFrame, metric: str) -> None:
    st.markdown("### Atlas")

    geo_path = locate_geo_file()

    if geo_path is None:
        st.warning("No NDIS service-area boundary file was found. Showing analytical atlas fallback.")
        st.altair_chart(chart_scatter(current), width="stretch")
        return

    try:
        from gm_map import render_australia_svg_map

        render_australia_svg_map(
            filtered=current,
            geo_path=geo_path,
            metric=metric,
            metric_label=METRICS[metric]["short"],
            metric_info=METRICS[metric],
            height=1160,
        )

        st.caption(f"Boundary file: {geo_path}")

    except Exception as exc:
        st.warning(f"Polygon atlas could not render. Showing analytical atlas fallback. Error: {exc}")
        st.altair_chart(chart_scatter(current), width="stretch")

def main() -> None:
    render_css()
    render_header()

    try:
        master = load_master()
        service_type_data = load_service_type()
    except Exception as exc:
        st.error("The app could not load the published data.")
        st.exception(exc)
        return

    nav_options = ["Atlas", "Funded Plans", "Service area", "Data"]
    requested_view = get_query_param("view")
    requested_area = get_query_param("service_area")

    if requested_area:
        active_view = "Service area"
    elif requested_view in nav_options:
        active_view = requested_view
    else:
        active_view = st.session_state.get("gm_active_view", "Atlas")
        if active_view not in nav_options:
            active_view = "Atlas"

    active_view = render_navigation(active_view)
    controls = build_controls(master, service_type_data, requested_area=requested_area)

    data = apply_service_category_proxy(master, service_type_data, controls["selected_categories"], controls["exclude_selected"])
    data = apply_benchmark(data, controls["benchmark_basis"], controls["benchmark_quarter"])
    data = add_reference_change_measures(data, controls["benchmark_quarter"])

    current = filtered_current(data, controls["quarter"], controls["selected_remoteness"], controls["metric"])
    trend_scope = data.loc[data["remoteness_category"].isin(controls["selected_remoteness"])].copy()

    benchmark_context = benchmark_context_label(controls["benchmark_basis"], controls["benchmark_quarter"])
    category_context = category_context_label(controls["selected_categories"], controls["exclude_selected"])
    remoteness_context = remoteness_context_label(controls["selected_remoteness"], REMOTENESS_ORDER)

    if active_view == "Overview":
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Rows", f"{len(data):,}")
        c2.metric("Service areas", f"{data['ndis_service_area'].nunique():,}")
        c3.metric("Quarters", f"{data['quarter'].nunique():,}")
        c4.metric("Service-category rows", f"{len(service_type_data):,}")
        st.markdown(
            f"""
            <div class="gm-finding">
                <div class="gm-finding-title">Current analytical scope</div>
                <div class="gm-finding-body">
                    The dashboard is showing <strong>{html.escape(controls['quarter'])}</strong> using the
                    <strong>{html.escape(benchmark_context)}</strong>, with
                    <strong>{html.escape(category_context)}</strong> and
                    <strong>{html.escape(remoteness_context)}</strong>. Positive benchmark gaps mean the observed
                    value is below the selected benchmark.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        key_finding(
            current,
            controls["metric"],
            controls["quarter"],
            controls["selected_categories"],
            controls["exclude_selected"],
            controls["selected_remoteness"],
        )
        st.altair_chart(
            chart_scatter(
                current,
                title=f"Overview market position | {controls['quarter']} | {benchmark_context}",
            ),
            width="stretch",
        )

    elif active_view == "Atlas":
        metric_cards(current, controls["metric"], controls["quarter"])
        render_atlas(current, controls["metric"])

    elif active_view == "Funded Plans":
        metric_cards(current, controls["metric"], controls["quarter"])
        key_finding(
            current,
            controls["metric"],
            controls["quarter"],
            controls["selected_categories"],
            controls["exclude_selected"],
            controls["selected_remoteness"],
        )

        left, right = st.columns([1.05, 0.95], gap="large")

        with left:
            st.markdown("#### Ranked service areas")
            st.altair_chart(
                chart_ranked(
                    current,
                    controls["metric"],
                    limit=len(current),
                    title=f"Service areas ranked by {METRICS[controls['metric']]['label']} | {controls['quarter']} | {benchmark_context} | {remoteness_context}",
                ),
                width="stretch",
            )

        with right:
            st.markdown("#### Funded plan saturation trend")
            st.altair_chart(
                trend_line(
                    trend_scope,
                    PLAN_COL,
                    f"Mean funded plan saturation by quarter | {benchmark_context} | {category_context} | {remoteness_context}",
                    "Funded plans per 1,000 population",
                ),
                width="stretch",
            )

            st.markdown("#### Mean plan utilisation trend")
            st.altair_chart(
                trend_line(
                    trend_scope,
                    UTIL_COL,
                    f"Mean plan utilisation by quarter | {benchmark_context} | {category_context} | {remoteness_context}",
                    "Mean plan utilisation (%)",
                ),
                width="stretch",
            )

            st.markdown("#### Market position")
            st.altair_chart(
                chart_scatter(
                    current,
                    title=f"Market position by service area | {controls['quarter']} | {benchmark_context} | {category_context} | {remoteness_context}",
                ),
                width="stretch",
            )

    elif active_view == "Service area":
        selected_area = controls["selected_area"]

        if selected_area == "Australia":
            metric_cards(current, controls["metric"], controls["quarter"])
            key_finding(
                current,
                controls["metric"],
                controls["quarter"],
                controls["selected_categories"],
                controls["exclude_selected"],
                controls["selected_remoteness"],
                service_area_label="Australia",
            )

            st.markdown("#### Australia trend")
            left, right = st.columns(2, gap="large")

            with left:
                st.altair_chart(
                    trend_line(
                        trend_scope,
                        PLAN_COL,
                        f"Australia funded plan saturation trend | {benchmark_context} | {category_context}",
                        "Funded plans per 1,000 population",
                    ),
                    width="stretch",
                )

            with right:
                st.altair_chart(
                    trend_line(
                        trend_scope,
                        UTIL_COL,
                        f"Australia mean plan utilisation trend | {benchmark_context} | {category_context}",
                        "Mean plan utilisation (%)",
                    ),
                    width="stretch",
                )

            st.markdown("#### Australia service-category payment benchmark")
            service_mix_chart(
                service_type_data,
                current,
                controls["quarter"],
                selected_area="Australia",
                benchmark_basis=controls["benchmark_basis"],
                benchmark_quarter=controls["benchmark_quarter"],
            )

        elif not selected_area:
            st.info("No service area is available for the current quarter.")

        else:
            area_current = current.loc[current["ndis_service_area"].eq(selected_area)].copy()
            area_all = data.loc[data["ndis_service_area"].eq(selected_area)].copy()

            if area_current.empty:
                st.warning("The selected service area is outside the current filter set.")
            else:
                label = area_current["service_area_state_label"].iloc[0] if "service_area_state_label" in area_current.columns else selected_area

                metric_cards(area_current, controls["metric"], controls["quarter"])
                key_finding(
                    area_current,
                    controls["metric"],
                    controls["quarter"],
                    controls["selected_categories"],
                    controls["exclude_selected"],
                    controls["selected_remoteness"],
                    service_area_label=label,
                )

                st.markdown("#### Service-area trend")
                left, right = st.columns(2, gap="large")

                with left:
                    st.altair_chart(
                        trend_chart(
                            area_all,
                            PLAN_COL,
                            PLAN_BENCHMARK_COL,
                            f"{label}: funded plans per 1,000 population",
                            "Plans per 1,000",
                        ),
                        width="stretch",
                    )

                with right:
                    st.altair_chart(
                        trend_chart(
                            area_all,
                            UTIL_COL,
                            UTIL_BENCHMARK_COL,
                            f"{label}: mean plan utilisation",
                            "Mean utilisation (%)",
                        ),
                        width="stretch",
                    )

                st.markdown("#### Service-category payment benchmark")
                service_mix_chart(
                    service_type_data,
                    current,
                    controls["quarter"],
                    selected_area=selected_area,
                    benchmark_basis=controls["benchmark_basis"],
                    benchmark_quarter=controls["benchmark_quarter"],
                )

    elif active_view == "Data quality":
        st.markdown("### Data quality")
        q1, q2, q3, q4 = st.columns(4)
        q1.metric("Master rows", f"{len(master):,}")
        q2.metric("Service-category rows", f"{len(service_type_data):,}")
        q3.metric("Quarters", f"{master['quarter'].nunique():,}")
        q4.metric("Service areas", f"{master['ndis_service_area'].nunique():,}")

        required_cols = ["quarter", "ndis_service_area", "remoteness_category", POP_COL, PLAN_COUNT_COL, PLAN_COL, UTIL_COL]
        completeness = (
            master[required_cols]
            .isna()
            .mean()
            .mul(100)
            .reset_index()
            .rename(columns={"index": "Column", 0: "Missing percent"})
        )
        st.markdown("#### Required-field missingness")
        st.altair_chart(
            gm_chart(
                alt.Chart(completeness)
                .mark_bar(color=GM_AMBER, stroke=GM_NAVY, strokeWidth=0.3)
                .encode(
                    y=alt.Y("Column:N", sort=required_cols, title="Field"),
                    x=alt.X("Missing percent:Q", title="Missing values (%)"),
                    tooltip=[
                        alt.Tooltip("Column:N", title="Field"),
                        alt.Tooltip("Missing percent:Q", title="Missing values (%)", format=".2f"),
                    ],
                )
                .properties(title="Completeness of required app fields", height=260)
            ),
            width="stretch",
        )

        st.markdown("#### Service categories present")
        st.write(sorted(service_type_data["service_type_group"].dropna().unique().tolist()) if not service_type_data.empty else [])
        st.dataframe(master.head(100), width="stretch", hide_index=True)

    elif active_view == "Method":
        st.markdown("### Method")
        st.markdown(
            """
            **Plan coverage** is funded plans divided by 2025 estimated resident population, multiplied by 1,000.

            **Mean plan utilisation** is the published NDIS service-area utilisation percentage, treated as a whole-area context measure.

            **Benchmark gaps** are calculated as benchmark value minus observed value. Positive values mean the area is below benchmark. Negative values mean the area is above benchmark.

            **Service-category payment benchmark** is shown as a percentage-point gap between a service area's payment share for each service category and the selected benchmark's service-category payment share.

            **Service-category selections** use payment share as a proxy. They are not unique participant counts or percentages of plans with the selected support category.

            **Ranking** places the largest positive selected metric values at the top. For benchmark gaps, positive values mean below benchmark. For change metrics, positive values mean increase since the reference quarter.

            **Australia** in the service-area selector means the current national/filter scope, not a literal service-area row.
            """
        )

    elif active_view == "Data":
        st.markdown("### Filtered data")
        st.dataframe(current, width="stretch", hide_index=True, height=620)

    st.markdown("---")
    st.caption("Good Measure | For Community")


if __name__ == "__main__":
    main()

