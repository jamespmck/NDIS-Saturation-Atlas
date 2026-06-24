from __future__ import annotations

import streamlit as st

from gm_config import GM_NAVY, GM_NAVY_2, GM_AMBER, GM_AMBER_SOFT


def apply_theme() -> None:
    st.markdown(
        f"""
        <style>
        .stApp {{
            background: #FFFFFF;
            color: {GM_NAVY};
        }}

        section.main > div {{
            max-width: 1960px;
            padding-top: 1.0rem;
        }}

        div[data-testid="stVerticalBlock"] {{
            gap: 0.75rem;
        }}

        h1, h2, h3, h4, h5, h6 {{
            color: {GM_NAVY} !important;
        }}

        [data-testid="stSidebar"] {{
            background: linear-gradient(180deg, {GM_NAVY} 0%, {GM_NAVY_2} 100%);
            min-width: 250px;
        }}

        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] div[data-testid="stMarkdownContainer"],
        [data-testid="stSidebar"] [role="radiogroup"] label p {{
            color: #FFFFFF !important;
        }}

        [data-testid="stSidebar"] div[data-baseweb="select"] *,
        [data-testid="stSidebar"] div[data-baseweb="input"] *,
        div[data-baseweb="popover"] *,
        ul[role="listbox"] *,
        li[role="option"] * {{
            color: {GM_NAVY} !important;
        }}

        [data-testid="stMetric"] {{
            background: {GM_AMBER_SOFT};
            border-left: 5px solid {GM_AMBER};
            border-radius: 10px;
            padding: 0.8rem 0.95rem;
            min-height: 82px;
            box-shadow: 0 1px 6px rgba(6,26,46,0.06);
        }}

        div[data-testid="stMetric"] label {{
            color: {GM_NAVY} !important;
            font-weight: 800 !important;
        }}

        div[data-testid="stMetricValue"] {{
            color: {GM_NAVY} !important;
            font-size: 1.9rem !important;
        }}

        .gm-hero {{
            border: 1px solid rgba(6,26,46,0.15);
            border-radius: 20px;
            padding: 1.2rem 1.45rem;
            margin-bottom: 0.85rem;
            background: linear-gradient(135deg, rgba(248,246,239,0.96), rgba(255,255,255,0.98));
            box-shadow: 0 1px 10px rgba(6,26,46,0.06);
        }}

        .gm-kicker {{
            font-size: 0.78rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: #6B5A45;
            font-weight: 800;
            margin-bottom: 0.25rem;
        }}

        .gm-title {{
            font-size: 2.25rem;
            line-height: 1.1;
            font-weight: 850;
            color: {GM_NAVY};
            margin-bottom: 0.35rem;
        }}

        .gm-subtitle {{
            font-size: 1rem;
            line-height: 1.4;
            color: #26384A;
            max-width: 1280px;
        }}

        .gm-note {{
            border-left: 4px solid {GM_AMBER};
            padding: 0.65rem 0.85rem;
            background: rgba(242,183,5,0.10);
            margin: 0.7rem 0 1rem 0;
        }}

        .stTabs [data-baseweb="tab-list"] {{
            gap: 0.32rem !important;
            border-bottom: 2px solid {GM_NAVY} !important;
            padding-top: 0.25rem;
        }}

        .stTabs [data-baseweb="tab"] {{
            background: #FFFFFF;
            color: {GM_NAVY};
            border: 1px solid {GM_NAVY};
            border-bottom: none;
            border-radius: 8px 8px 0 0;
            font-weight: 700;
            min-height: 2.35rem !important;
            padding: 0.45rem 0.72rem !important;
            font-size: 0.88rem !important;
        }}

        .stTabs [aria-selected="true"] {{
            background: {GM_NAVY} !important;
            color: #FFFFFF !important;
        }}

        div[data-testid="stDataFrame"] {{
            border: 1px solid rgba(6,26,46,0.12);
            border-radius: 8px;
        }}

        [data-testid="stHorizontalBlock"] {{
            gap: 0.85rem;
        }}

        /* GOOD MEASURE SAFE COMPACT LAYOUT PATCH */
        .block-container {
            max-width: 1720px !important;
            padding-top: 0.9rem !important;
            padding-left: 1.6rem !important;
            padding-right: 1.6rem !important;
        }

        div[data-testid="stMetric"] {
            min-height: 76px !important;
        }

        div[data-testid="stMetricValue"] {
            font-size: 1.45rem !important;
            line-height: 1.1 !important;
        }

        div[data-testid="stMetric"] label {
            font-size: 0.78rem !important;
            line-height: 1.15 !important;
        }

        .gm-hero {
            margin-bottom: 0.65rem !important;
        }

        .gm-title {
            font-size: 1.85rem !important;
        }
        
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_case_study_header() -> None:
    st.markdown(
        """
        <div class="gm-hero">
            <div class="gm-kicker">Good Measure technical case study</div>
            <div class="gm-title">NDIS Market Saturation Atlas</div>
            <div class="gm-subtitle">
                Applied public-data, geospatial and benchmark analysis prototype.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
