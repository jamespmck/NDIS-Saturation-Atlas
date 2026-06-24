from __future__ import annotations

import pandas as pd
import altair as alt

from gm_config import GM_NAVY, GM_AMBER, GM_RED, REMOTENESS_ORDER, SERVICE_TYPE_ORDER, METRIC_INFO
from gm_data import quarter_sort_key, weighted_mean


def gm_chart_config(chart: alt.Chart) -> alt.Chart:
    return (
        chart
        .configure(font="Segoe UI")
        .configure_axis(
            labelFont="Segoe UI",
            titleFont="Segoe UI",
            labelColor=GM_NAVY,
            titleColor=GM_NAVY,
            gridColor="#E8E1D2",
            domainColor=GM_NAVY,
            tickColor=GM_NAVY,
        )
        .configure_legend(
            labelFont="Segoe UI",
            titleFont="Segoe UI",
            labelColor=GM_NAVY,
            titleColor=GM_NAVY,
            orient="top-left",
            direction="horizontal",
            symbolSize=140,
            titlePadding=8,
        )
        .configure_title(font="Segoe UI", color=GM_NAVY)
        .configure_view(strokeWidth=0)
    )


def ranked_bar_chart(filtered: pd.DataFrame, metric: str, rank_mode: str, limit: int = 20) -> alt.Chart:
    data = filtered.copy()
    data[metric] = pd.to_numeric(data[metric], errors="coerce")
    data = data.dropna(subset=[metric]).copy()

    if data.empty:
        data = pd.DataFrame({
            "service_area_state_label": ["No data"],
            metric: [0],
            "benchmark_position": ["No data"],
            "remoteness_category": ["No data"],
        })

    if rank_mode == "Largest negative values":
        data = data.sort_values(metric, ascending=True).head(limit)
    elif rank_mode == "Largest absolute values":
        data["_abs_metric"] = data[metric].abs()
        data = data.sort_values("_abs_metric", ascending=False).head(limit)
    else:
        data = data.sort_values(metric, ascending=False).head(limit)

    y_order = data["service_area_state_label"].tolist()
    data["_metric_label"] = data[metric].map(lambda x: "" if pd.isna(x) else f"{x:,.2f}")

    bars = (
        alt.Chart(data)
        .mark_bar(color=GM_AMBER, stroke=GM_NAVY, strokeWidth=0.4)
        .encode(
            y=alt.Y("service_area_state_label:N", sort=y_order, title=None, axis=alt.Axis(labelLimit=360)),
            x=alt.X(f"{metric}:Q", title=METRIC_INFO[metric]["short"]),
            tooltip=[
                alt.Tooltip("service_area_state_label:N", title="Service area"),
                alt.Tooltip("remoteness_category:N", title="Remoteness"),
                alt.Tooltip("benchmark_position:N", title="Position"),
                alt.Tooltip(f"{metric}:Q", title=METRIC_INFO[metric]["short"], format=".2f"),
            ],
        )
        .properties(height=max(360, len(data) * 24))
    )

    labels = (
        alt.Chart(data)
        .mark_text(align="left", baseline="middle", dx=4, fontSize=10, color=GM_NAVY)
        .encode(
            y=alt.Y("service_area_state_label:N", sort=y_order, title=None),
            x=alt.X(f"{metric}:Q"),
            text="_metric_label:N",
        )
    )

    rule = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color=GM_NAVY, strokeDash=[4, 3]).encode(x="x:Q")
    return gm_chart_config(bars + labels + rule)


def remoteness_bar_chart(filtered: pd.DataFrame, metric: str) -> alt.Chart:
    data = filtered.copy()
    data[metric] = pd.to_numeric(data[metric], errors="coerce")
    grouped = data.groupby("remoteness_category", dropna=False)[metric].mean().reset_index()

    present = [item for item in REMOTENESS_ORDER if item in set(grouped["remoteness_category"].dropna())]
    extra = sorted(set(grouped["remoteness_category"].dropna()) - set(present))
    order = present + extra

    chart = (
        alt.Chart(grouped)
        .mark_bar(color=GM_AMBER, stroke=GM_NAVY, strokeWidth=0.4)
        .encode(
            y=alt.Y("remoteness_category:N", sort=order, title=None, axis=alt.Axis(labelLimit=260)),
            x=alt.X(f"{metric}:Q", title=f"Mean {METRIC_INFO[metric]['short']}"),
            tooltip=[
                alt.Tooltip("remoteness_category:N", title="Remoteness"),
                alt.Tooltip(f"{metric}:Q", title=f"Mean {METRIC_INFO[metric]['short']}", format=".2f"),
            ],
        )
        .properties(height=300)
    )

    rule = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color=GM_NAVY, strokeDash=[4, 3]).encode(x="x:Q")
    return gm_chart_config(chart + rule)


def trend_by_remoteness_chart(data: pd.DataFrame, metric: str, selected_remoteness: list[str]) -> alt.Chart:
    out = data.copy()
    if selected_remoteness:
        out = out.loc[out["remoteness_category"].isin(selected_remoteness)].copy()

    out[metric] = pd.to_numeric(out[metric], errors="coerce")
    grouped = out.groupby(["quarter", "remoteness_category"], dropna=False)[metric].mean().reset_index()
    quarter_order = sorted(grouped["quarter"].dropna().astype(str).unique().tolist(), key=quarter_sort_key)

    chart = (
        alt.Chart(grouped)
        .mark_line(point=True, strokeWidth=2.5)
        .encode(
            x=alt.X("quarter:N", sort=quarter_order, title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y(f"{metric}:Q", title=f"Mean {METRIC_INFO[metric]['short']}"),
            color=alt.Color(
                "remoteness_category:N",
                title="Remoteness",
                sort=REMOTENESS_ORDER,
                legend=alt.Legend(orient="top-left", direction="horizontal", symbolSize=130),
            ),
            tooltip=[
                alt.Tooltip("quarter:N", title="Quarter"),
                alt.Tooltip("remoteness_category:N", title="Remoteness"),
                alt.Tooltip(f"{metric}:Q", title=METRIC_INFO[metric]["short"], format=".2f"),
            ],
        )
        .properties(height=420)
    )
    return gm_chart_config(chart)



def scatter_market_position_chart(filtered: pd.DataFrame) -> alt.Chart:
    """Scatter chart using the selected benchmark basis for reference lines."""
    data = filtered.copy()

    plan_col = "service_area_funded_plans_per_1000_population_2025_erp"
    util_col = "service_area_mean_plan_utilisation"
    plan_benchmark_col = "plans_per_1000_benchmark_value"
    util_benchmark_col = "mean_utilisation_benchmark_value"

    data[plan_col] = pd.to_numeric(data[plan_col], errors="coerce")
    data[util_col] = pd.to_numeric(data[util_col], errors="coerce")

    if plan_benchmark_col not in data.columns:
        data[plan_benchmark_col] = data[plan_col].median()

    if util_benchmark_col not in data.columns:
        data[util_benchmark_col] = data[util_col].median()

    data[plan_benchmark_col] = pd.to_numeric(data[plan_benchmark_col], errors="coerce")
    data[util_benchmark_col] = pd.to_numeric(data[util_benchmark_col], errors="coerce")

    benchmark_label = "selected benchmark"
    if "benchmark_basis_label" in data.columns and data["benchmark_basis_label"].notna().any():
        benchmark_label = data["benchmark_basis_label"].dropna().astype(str).iloc[0]

    x_ref = float(data[plan_benchmark_col].median()) if data[plan_benchmark_col].notna().any() else float(data[plan_col].median())
    y_ref = float(data[util_benchmark_col].median()) if data[util_benchmark_col].notna().any() else float(data[util_col].median())

    points = (
        alt.Chart(data)
        .mark_circle(size=95, opacity=0.78, stroke=GM_NAVY, strokeWidth=0.5)
        .encode(
            x=alt.X(
                f"{plan_col}:Q",
                title="Funded plans per 1,000 population",
                scale=alt.Scale(zero=False),
            ),
            y=alt.Y(
                f"{util_col}:Q",
                title="Mean plan utilisation",
                scale=alt.Scale(zero=False),
            ),
            color=alt.Color(
                "market_position_typology:N",
                title="Benchmark position",
                legend=alt.Legend(orient="top-left", direction="vertical", symbolSize=130),
            ),
            tooltip=[
                alt.Tooltip("service_area_state_label:N", title="Service area"),
                alt.Tooltip("remoteness_category:N", title="Remoteness"),
                alt.Tooltip(f"{plan_col}:Q", title="Plans per 1,000", format=".2f"),
                alt.Tooltip(f"{plan_benchmark_col}:Q", title="Plans benchmark", format=".2f"),
                alt.Tooltip("funded_plans_per_1000_gap_from_national:Q", title="Plan benchmark gap", format=".2f"),
                alt.Tooltip(f"{util_col}:Q", title="Mean utilisation", format=".2f"),
                alt.Tooltip(f"{util_benchmark_col}:Q", title="Utilisation benchmark", format=".2f"),
                alt.Tooltip("mean_plan_utilisation_gap_from_national:Q", title="Utilisation benchmark gap", format=".2f"),
                alt.Tooltip("benchmark_basis_label:N", title="Benchmark basis"),
            ],
        )
    )

    x_rule = (
        alt.Chart(pd.DataFrame({"x": [x_ref], "label": [benchmark_label]}))
        .mark_rule(strokeDash=[6, 4], strokeWidth=1.4)
        .encode(
            x=alt.X("x:Q"),
            tooltip=[
                alt.Tooltip("label:N", title="Benchmark basis"),
                alt.Tooltip("x:Q", title="Plans benchmark", format=".2f"),
            ],
        )
    )

    y_rule = (
        alt.Chart(pd.DataFrame({"y": [y_ref], "label": [benchmark_label]}))
        .mark_rule(strokeDash=[6, 4], strokeWidth=1.4)
        .encode(
            y=alt.Y("y:Q"),
            tooltip=[
                alt.Tooltip("label:N", title="Benchmark basis"),
                alt.Tooltip("y:Q", title="Utilisation benchmark", format=".2f"),
            ],
        )
    )

    chart = (points + x_rule + y_rule).properties(height=360)

    return gm_chart_config(chart)


def service_type_heatmap(service_type_data: pd.DataFrame, quarter: str) -> alt.Chart:
    data = service_type_data.loc[service_type_data["quarter"].astype(str) == str(quarter)].copy()

    if data.empty:
        data = pd.DataFrame({
            "service_area_state_label": ["No data"],
            "service_type": ["No data"],
            "service_type_payment_share_of_area_total": [0],
        })

    data["service_type_payment_share_of_area_total"] = pd.to_numeric(data["service_type_payment_share_of_area_total"], errors="coerce").fillna(0)

    chart = (
        alt.Chart(data)
        .mark_rect(stroke="white", strokeWidth=0.4)
        .encode(
            y=alt.Y("service_area_state_label:N", title=None, axis=alt.Axis(labelLimit=280)),
            x=alt.X("service_type:N", title=None, sort=SERVICE_TYPE_ORDER, axis=alt.Axis(labelAngle=-35)),
            color=alt.Color("service_type_payment_share_of_area_total:Q", title="Payment share", scale=alt.Scale(scheme="blues")),
            tooltip=[
                alt.Tooltip("service_area_state_label:N", title="Service area"),
                alt.Tooltip("service_type:N", title="Service type"),
                alt.Tooltip("service_type_payment_share_of_area_total:Q", title="Payment share", format=".1%"),
            ],
        )
        .properties(height=760)
    )
    return gm_chart_config(chart)


def service_type_stacked_bar_chart(
    service_type_data: pd.DataFrame,
    filtered: pd.DataFrame,
    quarter: str,
    selected_service_types: list[str] | None = None,
    exclude_selected: bool = False,
    service_type_label: str = "All service types",
) -> alt.Chart:
    """Stacked service-type payment-share chart for all currently filtered service areas.

    The chart shows all service areas in the selected national view. Values are
    service-type payment share of each service area's total payments, not unique
    participants and not participant outcomes.
    """
    selected_service_types = selected_service_types or []

    if service_type_data.empty or filtered.empty:
        fallback = pd.DataFrame({
            "service_area_state_label": ["No service-type data"],
            "service_type": ["No data"],
            "payment_share_percent": [0],
            "service_type_label": [service_type_label],
        })

        chart = (
            alt.Chart(fallback)
            .mark_bar()
            .encode(
                y=alt.Y("service_area_state_label:N", title=None),
                x=alt.X("payment_share_percent:Q", title="Payment share of service-area total (%)"),
                color=alt.Color("service_type:N", title="Service type"),
                tooltip=[
                    alt.Tooltip("service_area_state_label:N", title="Service area"),
                    alt.Tooltip("service_type:N", title="Service type"),
                    alt.Tooltip("payment_share_percent:Q", title="Payment share (%)", format=".1f"),
                ],
            )
            .properties(height=220)
        )
        return gm_chart_config(chart)

    current_areas = filtered[[
        "ndis_service_area",
        "service_area_state_label",
        "remoteness_category",
        "market_position_typology",
    ]].drop_duplicates("ndis_service_area").copy()

    data = service_type_data.loc[
        service_type_data["quarter"].astype(str) == str(quarter)
    ].copy()

    data = data.merge(
        current_areas,
        on="ndis_service_area",
        how="inner",
        suffixes=("", "_current"),
    )

    if data.empty:
        fallback = pd.DataFrame({
            "service_area_state_label": ["No matching service areas"],
            "service_type": ["No data"],
            "payment_share_percent": [0],
            "service_type_label": [service_type_label],
        })

        chart = (
            alt.Chart(fallback)
            .mark_bar()
            .encode(
                y=alt.Y("service_area_state_label:N", title=None),
                x=alt.X("payment_share_percent:Q", title="Payment share of service-area total (%)"),
                color=alt.Color("service_type:N", title="Service type"),
                tooltip=[
                    alt.Tooltip("service_area_state_label:N", title="Service area"),
                    alt.Tooltip("service_type:N", title="Service type"),
                    alt.Tooltip("payment_share_percent:Q", title="Payment share (%)", format=".1f"),
                ],
            )
            .properties(height=220)
        )
        return gm_chart_config(chart)

    if selected_service_types:
        selected = set(selected_service_types)
        if exclude_selected:
            data = data.loc[~data["service_type"].isin(selected)].copy()
        else:
            data = data.loc[data["service_type"].isin(selected)].copy()

    if data.empty:
        fallback = current_areas.copy()
        fallback["service_type"] = "No selected service types"
        fallback["payment_share_percent"] = 0.0
        fallback["service_type_label"] = service_type_label
        data = fallback
    else:
        data["payment_share_percent"] = (
            pd.to_numeric(data["service_type_payment_share_of_area_total"], errors="coerce")
            .fillna(0)
            .clip(lower=0)
            * 100
        )
        data["service_type_label"] = service_type_label

    totals = (
        data.groupby("service_area_state_label", dropna=False)["payment_share_percent"]
        .sum()
        .sort_values(ascending=False)
    )

    y_order = totals.index.tolist()
    chart_height = max(980, len(y_order) * 22)

    chart = (
        alt.Chart(data)
        .mark_bar(stroke="#061A2E", strokeWidth=0.15)
        .encode(
            y=alt.Y(
                "service_area_state_label:N",
                sort=y_order,
                title=None,
                axis=alt.Axis(labelLimit=330),
            ),
            x=alt.X(
                "payment_share_percent:Q",
                title="Payment share of service-area total (%)",
                scale=alt.Scale(domain=[0, max(100, float(totals.max()) if len(totals) else 100)]),
            ),
            color=alt.Color(
                "service_type:N",
                title="Service type",
                sort=SERVICE_TYPE_ORDER,
                legend=alt.Legend(
                    orient="top-left",
                    direction="vertical",
                    columns=1,
                    symbolSize=120,
                    titleLimit=260,
                    labelLimit=300,
                ),
            ),
            tooltip=[
                alt.Tooltip("service_area_state_label:N", title="Service area"),
                alt.Tooltip("remoteness_category:N", title="Remoteness"),
                alt.Tooltip("service_type:N", title="Service type"),
                alt.Tooltip("payment_share_percent:Q", title="Payment share of area total (%)", format=".1f"),
                alt.Tooltip("service_type_label:N", title="Selected service categories"),
            ],
        )
        .properties(height=chart_height)
    )

    return gm_chart_config(chart)


def _gm_local_quarter_sort_key(value):
    import re

    text = str(value)
    match = re.match(r"^(\d{4})Q([1-4])$", text)

    if not match:
        return (9999, 9)

    return (int(match.group(1)), int(match.group(2)))


def _gm_local_weighted_mean(values, weights):
    values = pd.to_numeric(values, errors="coerce")
    weights = pd.to_numeric(weights, errors="coerce")

    valid = values.notna() & weights.notna() & (weights > 0)

    if valid.any():
        return float((values.loc[valid] * weights.loc[valid]).sum() / weights.loc[valid].sum())

    return float(values.mean()) if values.notna().any() else None


def service_area_benchmark_trend_chart(
    data: pd.DataFrame,
    service_area: str,
    value_col: str,
    y_title: str,
) -> alt.Chart:
    """Trend chart for one service area against the selected benchmark basis.

    This function restores the import expected by ndis_service_area_dashboard.py.
    It uses benchmark columns from the selectable benchmark patch when present.
    If those columns are not available, it falls back to national and remoteness
    benchmark series.
    """
    working = data.copy()

    if working.empty:
        fallback = pd.DataFrame({
            "quarter": ["No data"],
            "value": [0],
            "series": ["No data"],
            "benchmark_basis": ["No data"],
        })

        chart = (
            alt.Chart(fallback)
            .mark_line(point=True)
            .encode(
                x=alt.X("quarter:N", title=None),
                y=alt.Y("value:Q", title=y_title),
                color=alt.Color("series:N", title="Series"),
                tooltip=[
                    alt.Tooltip("quarter:N", title="Quarter"),
                    alt.Tooltip("series:N", title="Series"),
                    alt.Tooltip("value:Q", title=y_title, format=".2f"),
                ],
            )
            .properties(height=420)
        )

        return gm_chart_config(chart)

    working["quarter"] = working["quarter"].astype(str)

    area_rows = working.loc[
        working["ndis_service_area"].astype(str) == str(service_area)
    ].copy()

    if area_rows.empty:
        fallback = pd.DataFrame({
            "quarter": ["No data"],
            "value": [0],
            "series": [f"{service_area} not found"],
            "benchmark_basis": ["No data"],
        })

        chart = (
            alt.Chart(fallback)
            .mark_line(point=True)
            .encode(
                x=alt.X("quarter:N", title=None),
                y=alt.Y("value:Q", title=y_title),
                color=alt.Color("series:N", title="Series"),
                tooltip=[
                    alt.Tooltip("quarter:N", title="Quarter"),
                    alt.Tooltip("series:N", title="Series"),
                    alt.Tooltip("value:Q", title=y_title, format=".2f"),
                ],
            )
            .properties(height=420)
        )

        return gm_chart_config(chart)

    area_label = (
        area_rows["service_area_state_label"].dropna().astype(str).iloc[0]
        if "service_area_state_label" in area_rows.columns and area_rows["service_area_state_label"].notna().any()
        else str(service_area)
    )

    remoteness = (
        area_rows["remoteness_category"].dropna().astype(str).iloc[0]
        if "remoteness_category" in area_rows.columns and area_rows["remoteness_category"].notna().any()
        else None
    )

    area_series = area_rows[["quarter", value_col]].copy()
    area_series = area_series.rename(columns={value_col: "value"})
    area_series["series"] = area_label

    benchmark_basis = "Selected benchmark"

    if "benchmark_basis_label" in area_rows.columns and area_rows["benchmark_basis_label"].notna().any():
        benchmark_basis = area_rows["benchmark_basis_label"].dropna().astype(str).iloc[0]

    benchmark_col = None

    if value_col == "service_area_funded_plans_per_1000_population_2025_erp":
        benchmark_col = "plans_per_1000_benchmark_value"

    elif value_col == "service_area_mean_plan_utilisation":
        benchmark_col = "mean_utilisation_benchmark_value"

    benchmark_series = pd.DataFrame()

    if benchmark_col and benchmark_col in area_rows.columns:
        benchmark_series = area_rows[["quarter", benchmark_col]].copy()
        benchmark_series = benchmark_series.rename(columns={benchmark_col: "value"})
        benchmark_series["series"] = f"Benchmark: {benchmark_basis}"

    else:
        if value_col == "service_area_funded_plans_per_1000_population_2025_erp":
            national = (
                working.groupby("quarter", dropna=False)
                .apply(
                    lambda group: (
                        pd.to_numeric(group["funded_plans_count"], errors="coerce").sum()
                        / pd.to_numeric(group["population_2025_erp"], errors="coerce").sum()
                        * 1000
                    )
                    if pd.to_numeric(group["population_2025_erp"], errors="coerce").sum() > 0
                    else pd.NA
                )
                .rename("value")
                .reset_index()
            )

            if remoteness:
                rem = (
                    working.loc[working["remoteness_category"].astype(str) == remoteness]
                    .groupby("quarter", dropna=False)
                    .apply(
                        lambda group: (
                            pd.to_numeric(group["funded_plans_count"], errors="coerce").sum()
                            / pd.to_numeric(group["population_2025_erp"], errors="coerce").sum()
                            * 1000
                        )
                        if pd.to_numeric(group["population_2025_erp"], errors="coerce").sum() > 0
                        else pd.NA
                    )
                    .rename("value")
                    .reset_index()
                )
            else:
                rem = pd.DataFrame(columns=["quarter", "value"])

        elif value_col == "service_area_mean_plan_utilisation":
            national = (
                working.groupby("quarter", dropna=False)
                .apply(lambda group: _gm_local_weighted_mean(group[value_col], group.get("funded_plans_count", pd.Series(1, index=group.index))))
                .rename("value")
                .reset_index()
            )

            if remoteness:
                rem = (
                    working.loc[working["remoteness_category"].astype(str) == remoteness]
                    .groupby("quarter", dropna=False)
                    .apply(lambda group: _gm_local_weighted_mean(group[value_col], group.get("funded_plans_count", pd.Series(1, index=group.index))))
                    .rename("value")
                    .reset_index()
                )
            else:
                rem = pd.DataFrame(columns=["quarter", "value"])

        else:
            national = working.groupby("quarter", dropna=False)[value_col].mean().rename("value").reset_index()
            rem = pd.DataFrame(columns=["quarter", "value"])

        national["series"] = "National mean"

        if not rem.empty:
            rem["series"] = f"{remoteness} mean"
            benchmark_series = pd.concat([national, rem], ignore_index=True)
        else:
            benchmark_series = national

    plot = pd.concat([area_series, benchmark_series], ignore_index=True)
    plot["value"] = pd.to_numeric(plot["value"], errors="coerce")
    plot = plot.dropna(subset=["quarter", "value"]).copy()

    if plot.empty:
        plot = pd.DataFrame({
            "quarter": ["No data"],
            "value": [0],
            "series": ["No data"],
        })

    quarter_order = sorted(
        plot["quarter"].dropna().astype(str).unique().tolist(),
        key=_gm_local_quarter_sort_key,
    )

    chart = (
        alt.Chart(plot)
        .mark_line(point=True, strokeWidth=2.8)
        .encode(
            x=alt.X(
                "quarter:N",
                sort=quarter_order,
                title=None,
                axis=alt.Axis(labelAngle=0),
            ),
            y=alt.Y("value:Q", title=y_title, scale=alt.Scale(zero=False)),
            color=alt.Color(
                "series:N",
                title="Series",
                legend=alt.Legend(orient="top-left", direction="horizontal", symbolSize=150),
            ),
            strokeDash=alt.StrokeDash("series:N", title=None, legend=None),
            tooltip=[
                alt.Tooltip("quarter:N", title="Quarter"),
                alt.Tooltip("series:N", title="Series"),
                alt.Tooltip("value:Q", title=y_title, format=".2f"),
            ],
        )
        .properties(height=420)
    )

    return gm_chart_config(chart)
