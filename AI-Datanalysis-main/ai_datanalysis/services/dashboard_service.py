"""
Automatic dashboard and report generation services.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from ai_datanalysis.core.data_catalog import (
    build_data_catalog,
    build_master_datasets,
    select_non_overlapping_masters,
)


ROLE_KPI_HINTS = {
    "analyst": ["score", "rate", "distribution", "segment"],
    "business_manager": ["revenue", "sales", "profit", "margin", "orders", "customers", "growth"],
    "ceo": ["revenue", "sales", "profit", "margin", "cost", "orders", "growth"],
    "cfo": ["revenue", "profit", "margin", "cost", "expense", "budget", "variance"],
    "finance_manager": ["revenue", "profit", "margin", "cost", "expense", "target", "budget"],
    "sales": ["sales", "revenue", "orders", "quantity", "units", "customers"],
    "marketing": ["conversion", "cac", "roas", "ctr", "impressions", "clicks", "leads"],
    "operations": ["cost", "time", "delay", "throughput", "volume", "inventory"],
}

ROLE_LABELS = {
    "analyst": "Analyst",
    "business_manager": "Business Manager",
    "ceo": "CEO",
    "cfo": "CFO",
    "finance_manager": "Finance Manager",
    "marketing": "Marketing Manager",
    "operations": "Operations Manager",
    "sales": "Sales Manager",
}

DOMAIN_KEYWORDS = {
    "sales": {"revenue", "sales", "profit", "orders", "quantity", "price", "customer", "channel"},
    "marketing": {"campaign", "conversion", "roas", "cac", "click", "impression", "lead"},
    "education": {"score", "exam", "grade", "student", "subject", "passed"},
    "operations": {"inventory", "delay", "shipment", "throughput", "downtime", "volume"},
    "finance": {"amount", "balance", "income", "expense", "margin", "cost", "budget", "target"},
}

FINANCE_METRIC_ALIASES = {
    "revenue": ["revenue", "sales", "net_sales", "gmv", "income", "amount"],
    "cost": ["cost", "expense", "cogs", "opex"],
    "profit": ["profit", "earnings"],
    "margin": ["margin", "profit_margin", "margin_pct", "margin_rate"],
}

TARGET_TOKENS = ["target", "plan", "budget", "forecast", "benchmark"]

FINANCE_DIMENSION_HINTS = [
    "region",
    "area",
    "province",
    "city",
    "channel",
    "product_category",
    "product_group",
    "product",
    "customer_type",
    "customer_segment",
    "segment",
    "business_unit",
    "unit",
]

QUANT_DIMENSION_HINTS = [
    "province",
    "region",
    "category",
    "segment",
    "group",
    "cohort",
    "gender",
    "class",
    "subject",
    "product_group",
    "product_category",
]

REPORT_TITLE = "Bao cao dashboard tu dong"


@dataclass
class SchemaProfile:
    time_cols: list[str]
    numeric_cols: list[str]
    categorical_cols: list[str]
    id_cols: list[str]


def _normalize_name(name: str) -> str:
    return str(name).strip().lower().replace(" ", "_")


def _safe_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _safe_ratio(numerator: float, denominator: float) -> float:
    if not denominator:
        return 0.0
    return float(numerator) / float(denominator)


def _coerce_datetime(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")


def _contains_any(name: str, tokens: list[str] | set[str] | tuple[str, ...]) -> bool:
    return any(token in name for token in tokens)


def _is_identifier_series(series: pd.Series, col_norm: str) -> bool:
    if any(token in col_norm for token in ("id", "code", "key", "uuid")) or col_norm in {"sbd"}:
        return True
    return False


def _is_binary_series(series: pd.Series) -> bool:
    cleaned = series.dropna()
    if cleaned.empty:
        return False
    if pd.api.types.is_numeric_dtype(cleaned):
        values = set(pd.to_numeric(cleaned, errors="coerce").dropna().astype(float).unique().tolist())
        return bool(values) and values.issubset({0.0, 1.0})
    values = {str(v).strip().lower() for v in cleaned.unique()}
    return values.issubset({"0", "1", "yes", "no", "true", "false", "pass", "fail", "passed", "failed", "y", "n"})


def _detect_schema(df: pd.DataFrame) -> SchemaProfile:
    time_cols: list[str] = []
    numeric_cols: list[str] = []
    categorical_cols: list[str] = []
    id_cols: list[str] = []

    for col in df.columns:
        col_name = str(col)
        col_norm = _normalize_name(col_name)
        series = df[col]

        if pd.api.types.is_datetime64_any_dtype(series):
            time_cols.append(col_name)
            continue

        if any(token in col_norm for token in ("date", "time", "month", "year", "day", "week")):
            parsed = _coerce_datetime(series)
            if parsed.notna().sum() >= max(3, len(df) // 5):
                time_cols.append(col_name)
                continue

        if _is_identifier_series(series, col_norm):
            id_cols.append(col_name)
            continue

        if pd.api.types.is_numeric_dtype(series):
            numeric_cols.append(col_name)
        else:
            categorical_cols.append(col_name)

    return SchemaProfile(
        time_cols=time_cols,
        numeric_cols=numeric_cols,
        categorical_cols=categorical_cols,
        id_cols=id_cols,
    )


def _detect_domain(columns: list[str]) -> str:
    tokens = set()
    for col in columns:
        tokens.update(_normalize_name(col).split("_"))

    best_domain = "general"
    best_score = 0
    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = len(tokens.intersection(keywords))
        if score > best_score:
            best_domain = domain
            best_score = score
    return best_domain


def _score_numeric_column(col: str, role: str, domain: str) -> float:
    name = _normalize_name(col)
    score = 1.0
    for token in ROLE_KPI_HINTS.get(role, []):
        if token in name:
            score += 4.0
    for token in DOMAIN_KEYWORDS.get(domain, set()):
        if token in name:
            score += 2.0
    if any(token in name for token in ("revenue", "sales", "profit", "score", "conversion", "cost", "amount")):
        score += 2.5
    if any(token in name for token in ("rate", "ratio", "pct", "percent", "margin", "growth")):
        score += 1.0
    return score


def _non_binary_numeric_cols(df: pd.DataFrame, profile: SchemaProfile) -> list[str]:
    return [col for col in profile.numeric_cols if not _is_binary_series(df[col])]


def _pick_primary_metric(df: pd.DataFrame, profile: SchemaProfile, role: str, domain: str) -> Optional[str]:
    candidates = _non_binary_numeric_cols(df, profile)
    if not candidates:
        candidates = profile.numeric_cols
    if not candidates:
        return None
    ranked = sorted(
        candidates,
        key=lambda col: (_score_numeric_column(col, role, domain), -len(_normalize_name(col))),
        reverse=True,
    )
    return ranked[0]


def _pick_secondary_metrics(
    df: pd.DataFrame,
    profile: SchemaProfile,
    primary_metric: Optional[str],
    role: str,
    domain: str,
) -> list[str]:
    remaining = [col for col in _non_binary_numeric_cols(df, profile) if col != primary_metric]
    ranked = sorted(remaining, key=lambda col: _score_numeric_column(col, role, domain), reverse=True)
    return ranked[:4]


def _pick_best_time_col(df: pd.DataFrame, profile: SchemaProfile) -> Optional[str]:
    for col in profile.time_cols:
        converted = _coerce_datetime(df[col])
        if converted.notna().sum() >= max(3, len(df) // 10):
            return col
    return None


def _pick_best_category(df: pd.DataFrame, profile: SchemaProfile) -> Optional[str]:
    candidates: list[tuple[int, str]] = []
    for col in profile.categorical_cols:
        nunique = int(df[col].nunique(dropna=True))
        if 2 <= nunique <= 20:
            candidates.append((nunique, str(col)))
    if not candidates:
        return profile.categorical_cols[0] if profile.categorical_cols else None
    candidates.sort()
    return candidates[0][1]


def _pick_scatter_metric(secondary_metrics: list[str]) -> Optional[str]:
    return secondary_metrics[0] if secondary_metrics else None


def _format_value(value: float, *, percent: bool = False, metric_name: str = "") -> str:
    if pd.isna(value):
        return "N/A"
    if percent:
        return f"{float(value):.1%}"
    abs_value = abs(float(value))
    prefix = "$" if any(token in _normalize_name(metric_name) for token in ("usd", "dollar")) else ""
    if abs_value >= 1_000_000_000:
        return f"{prefix}{value / 1_000_000_000:.2f}B"
    if abs_value >= 1_000_000:
        return f"{prefix}{value / 1_000_000:.2f}M"
    if abs_value >= 1_000:
        return f"{prefix}{value / 1_000:.1f}K"
    if abs_value >= 100:
        return f"{prefix}{value:.1f}"
    return f"{prefix}{value:.2f}"


def _apply_figure_style(fig: go.Figure, title: str, height: int = 360) -> go.Figure:
    fig.update_layout(
        title=title,
        height=height,
        margin=dict(l=24, r=24, t=64, b=32),
        template="plotly_white",
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(family="Source Sans Pro, Arial, sans-serif", size=12, color="#0f172a"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#eceff4")
    fig.update_yaxes(showgrid=True, gridcolor="#eceff4")
    return fig


def _make_line_chart(
    df: pd.DataFrame,
    time_col: str,
    metric_col: str,
    *,
    agg: str = "sum",
    title: Optional[str] = None,
) -> go.Figure:
    agg_df, _ = _aggregate_metric_over_time(df, time_col, metric_col, agg)

    fig = go.Figure(
        data=[
            go.Scatter(
                x=agg_df["period"],
                y=agg_df[metric_col],
                mode="lines+markers",
                line=dict(color="#0f766e", width=3),
                marker=dict(size=7, color="#115e59"),
                fill="tozeroy",
                fillcolor="rgba(15, 118, 110, 0.10)",
                hovertemplate="<b>%{x}</b><br>Giá trị: %{y}<extra></extra>",
            )
        ]
    )
    fig.update_xaxes(title="Thời gian")
    fig.update_yaxes(title=metric_col)
    return _apply_figure_style(fig, title or f"Xu hướng {metric_col} theo thời gian")


def _make_bar_chart(
    df: pd.DataFrame,
    category_col: str,
    metric_col: str,
    *,
    agg: str = "sum",
    title: Optional[str] = None,
) -> go.Figure:
    temp = df[[category_col, metric_col]].copy()
    temp[metric_col] = _safe_numeric(temp[metric_col])
    temp = temp.dropna()
    agg_df = temp.groupby(category_col, as_index=False)[metric_col].agg(agg)
    agg_df = agg_df.sort_values(metric_col, ascending=False).head(10)

    fig = go.Figure(
        data=[
            go.Bar(
                x=agg_df[category_col].astype(str),
                y=agg_df[metric_col],
                marker_color="#ea580c",
                text=[_format_value(v, metric_name=metric_col) for v in agg_df[metric_col]],
                textposition="auto",
                hovertemplate="<b>%{x}</b><br>Gia tri: %{y}<extra></extra>",
            )
        ]
    )
    fig.update_xaxes(title=category_col, tickangle=-30)
    fig.update_yaxes(title=metric_col)
    return _apply_figure_style(fig, title or f"Top đóng góp theo {category_col}")


def _make_histogram(df: pd.DataFrame, metric_col: str) -> go.Figure:
    temp = _safe_numeric(df[metric_col]).dropna()
    fig = go.Figure(
        data=[
            go.Histogram(
                x=temp,
                nbinsx=25,
                marker_color="#2563eb",
                hovertemplate="Gia tri: %{x}<br>Tan suat: %{y}<extra></extra>",
            )
        ]
    )
    fig.update_xaxes(title=metric_col)
    fig.update_yaxes(title="Tan suat")
    return _apply_figure_style(fig, f"Phan phoi {metric_col}")


def _make_box_chart(df: pd.DataFrame, metric_col: str, category_col: Optional[str]) -> go.Figure:
    temp = df.copy()
    temp[metric_col] = _safe_numeric(temp[metric_col])
    temp = temp.dropna(subset=[metric_col])
    if category_col and category_col in temp.columns:
        temp[category_col] = temp[category_col].astype(str)
        temp = temp[temp[category_col].notna()]
        sample = temp[[category_col, metric_col]].copy()
        top_categories = sample[category_col].value_counts().head(8).index.tolist()
        sample = sample[sample[category_col].isin(top_categories)]
        fig = px.box(sample, x=category_col, y=metric_col, color=category_col)
        fig.update_layout(showlegend=False)
        fig.update_xaxes(tickangle=-25)
        return _apply_figure_style(fig, f"Do phan tan {metric_col} theo nhom")

    fig = go.Figure(data=[go.Box(y=temp[metric_col], marker_color="#7c3aed", boxmean=True)])
    fig.update_yaxes(title=metric_col)
    return _apply_figure_style(fig, f"Bien dong va outlier cua {metric_col}")


def _make_scatter_chart(df: pd.DataFrame, x_col: str, y_col: str, category_col: Optional[str]) -> go.Figure:
    temp = df.copy()
    temp[x_col] = _safe_numeric(temp[x_col])
    temp[y_col] = _safe_numeric(temp[y_col])
    temp = temp.dropna(subset=[x_col, y_col]).head(2000)
    color = category_col if category_col and category_col in temp.columns else None
    fig = px.scatter(temp, x=x_col, y=y_col, color=color, trendline="ols" if len(temp) >= 20 else None)
    fig.update_layout(showlegend=bool(color))
    return _apply_figure_style(fig, f"Tương quan {x_col} và {y_col}")


def _make_heatmap(df: pd.DataFrame, numeric_cols: list[str]) -> Optional[go.Figure]:
    if len(numeric_cols) < 2:
        return None
    cols = numeric_cols[:6]
    temp = df[cols].apply(pd.to_numeric, errors="coerce")
    corr = temp.corr(numeric_only=True)
    if corr.empty:
        return None
    fig = go.Figure(
        data=[
            go.Heatmap(
                z=corr.values,
                x=corr.columns,
                y=corr.index,
                colorscale="RdBu",
                zmid=0,
                hovertemplate="Cột X: %{x}<br>Cột Y: %{y}<br>Tương quan: %{z:.2f}<extra></extra>",
            )
        ]
    )
    return _apply_figure_style(fig, "Bản đồ tương quan các chỉ số", height=380)


def _find_matching_column(columns: list[str], positive_tokens: list[str]) -> Optional[str]:
    best_col = None
    best_score = 0
    for col in columns:
        name = _normalize_name(col)
        score = 0
        for token in positive_tokens:
            if token == name:
                score += 8
            elif name.startswith(token) or name.endswith(token):
                score += 5
            elif token in name:
                score += 3
        if score > best_score:
            best_col = col
            best_score = score
    return best_col


def _find_target_column(columns: list[str], base_tokens: list[str]) -> Optional[str]:
    best_col = None
    best_score = 0
    for col in columns:
        name = _normalize_name(col)
        if not _contains_any(name, TARGET_TOKENS):
            continue
        score = 0
        for token in TARGET_TOKENS:
            if token in name:
                score += 3
        for token in base_tokens:
            if token in name:
                score += 2
        if score > best_score:
            best_col = col
            best_score = score
    return best_col


def _metric_aggregation(metric_name: str) -> str:
    name = _normalize_name(metric_name)
    if any(token in name for token in ("rate", "ratio", "pct", "percent", "margin", "avg", "mean", "score", "rating", "price")):
        return "mean"
    return "sum"


def _choose_time_grain(series: pd.Series) -> str:
    clean = _coerce_datetime(series).dropna().sort_values()
    if clean.empty:
        return "D"
    span_days = max((clean.max() - clean.min()).days, 0)
    unique_days = clean.dt.normalize().nunique()
    if span_days >= 540 or unique_days > 180:
        return "M"
    if span_days >= 120 or unique_days > 60:
        return "W"
    return "D"


def _bucket_time(series: pd.Series, grain: str) -> pd.Series:
    clean = _coerce_datetime(series)
    if grain == "M":
        return clean.dt.to_period("M").dt.to_timestamp()
    if grain == "W":
        return clean.dt.to_period("W").dt.start_time
    return clean.dt.normalize()


def _format_period_label(value: pd.Timestamp, grain: str) -> str:
    ts = pd.Timestamp(value)
    if grain == "M":
        return ts.strftime("%Y-%m")
    if grain == "W":
        return f"Tuan {ts.strftime('%d/%m/%Y')}"
    return ts.strftime("%d/%m/%Y")


def _aggregate_metric_over_time(df: pd.DataFrame, time_col: str, metric_col: str, agg: str) -> tuple[pd.DataFrame, str]:
    temp = df[[time_col, metric_col]].copy()
    temp[time_col] = _coerce_datetime(temp[time_col])
    temp[metric_col] = _safe_numeric(temp[metric_col])
    temp = temp.dropna()
    if temp.empty:
        return pd.DataFrame(columns=["period", metric_col]), "D"
    grain = _choose_time_grain(temp[time_col])
    temp["period"] = _bucket_time(temp[time_col], grain)
    agg_df = temp.groupby("period", as_index=False)[metric_col].agg(agg).sort_values("period")
    return agg_df, grain


def _current_previous_metric(df: pd.DataFrame, time_col: Optional[str], metric_col: str, agg: str) -> dict[str, Any]:
    if time_col:
        series_df, grain = _aggregate_metric_over_time(df, time_col, metric_col, agg)
        if not series_df.empty:
            current_row = series_df.iloc[-1]
            previous_row = series_df.iloc[-2] if len(series_df) >= 2 else None
            return {
                "current": float(current_row[metric_col]),
                "previous": float(previous_row[metric_col]) if previous_row is not None else None,
                "current_label": _format_period_label(current_row["period"], grain),
                "previous_label": _format_period_label(previous_row["period"], grain) if previous_row is not None else None,
            }
    series = _safe_numeric(df[metric_col]).dropna()
    if series.empty:
        return {"current": None, "previous": None, "current_label": None, "previous_label": None}
    value = float(series.mean()) if agg == "mean" else float(series.sum())
    return {"current": value, "previous": None, "current_label": None, "previous_label": None}


def _current_previous_count(
    df: pd.DataFrame,
    time_col: Optional[str],
    *,
    id_col: Optional[str] = None,
    label: str = "count",
) -> dict[str, Any]:
    if time_col:
        temp = df[[time_col]].copy()
        temp[time_col] = _coerce_datetime(temp[time_col])
        temp[label] = df[id_col].astype(str) if id_col and id_col in df.columns else 1
        temp = temp.dropna(subset=[time_col])
        if not temp.empty:
            grain = _choose_time_grain(temp[time_col])
            temp["period"] = _bucket_time(temp[time_col], grain)
            if id_col and id_col in df.columns:
                agg_df = temp.groupby("period", as_index=False)[label].nunique().sort_values("period")
            else:
                agg_df = temp.groupby("period", as_index=False)[label].sum().sort_values("period")
            current_row = agg_df.iloc[-1]
            previous_row = agg_df.iloc[-2] if len(agg_df) >= 2 else None
            return {
                "current": float(current_row[label]),
                "previous": float(previous_row[label]) if previous_row is not None else None,
                "current_label": _format_period_label(current_row["period"], grain),
                "previous_label": _format_period_label(previous_row["period"], grain) if previous_row is not None else None,
            }
    current = float(df[id_col].nunique()) if id_col and id_col in df.columns else float(len(df))
    return {"current": current, "previous": None, "current_label": None, "previous_label": None}


def _format_pct_delta(current: Optional[float], previous: Optional[float]) -> Optional[str]:
    if current is None or previous is None:
        return None
    change_pct = _safe_ratio(current - previous, abs(previous) or 1.0)
    return f"{change_pct:+.1%}"


def _build_metric_card(
    label: str,
    current: Optional[float],
    *,
    previous: Optional[float] = None,
    target: Optional[float] = None,
    positive_when_higher: bool = True,
    percent: bool = False,
    metric_name: str = "",
    description: str = "",
    previous_label: Optional[str] = None,
) -> dict[str, Any]:
    comparison_parts: list[str] = []
    if previous is not None:
        comparison_parts.append(f"So với {previous_label or 'kỳ trước'}")
    if target not in (None, 0):
        comparison_parts.append(f"Dat {(_safe_ratio(current or 0.0, target)):.1%} target")
    return {
        "label": label,
        "value": _format_value(current, percent=percent, metric_name=metric_name) if current is not None else "N/A",
        "delta": _format_pct_delta(current, previous),
        "delta_color": "normal" if positive_when_higher else "inverse",
        "comparison": " | ".join(comparison_parts),
        "description": description,
        "raw_value": current,
    }


def _pick_dimension_candidates(df: pd.DataFrame, profile: SchemaProfile, hints: list[str], max_count: int = 3) -> list[str]:
    scored: list[tuple[float, str]] = []
    for col in profile.categorical_cols:
        name = _normalize_name(col)
        nunique = int(df[col].nunique(dropna=True))
        if nunique < 2 or nunique > max(25, len(df) // 2):
            continue
        score = 1.0
        if 2 <= nunique <= 12:
            score += 3.0
        elif 13 <= nunique <= 20:
            score += 1.0
        for hint in hints:
            if hint in name:
                score += 4.0
        scored.append((score, col))
    if not scored:
        return profile.categorical_cols[:max_count]
    scored.sort(key=lambda item: (item[0], -len(_normalize_name(item[1]))), reverse=True)
    return [col for _, col in scored[:max_count]]


def _pick_binary_metric(df: pd.DataFrame, profile: SchemaProfile) -> Optional[str]:
    candidates = [col for col in profile.numeric_cols + profile.categorical_cols if _is_binary_series(df[col])]
    preferred = _find_matching_column(candidates, ["pass", "passed", "completion", "complete", "success", "flag", "status"])
    return preferred or (candidates[0] if candidates else None)

def _quality_summary(df: pd.DataFrame, primary_metric: Optional[str]) -> dict[str, Any]:
    missing_cells = int(df.isna().sum().sum())
    total_cells = int(df.shape[0] * max(df.shape[1], 1))
    duplicate_rows = int(df.duplicated().sum())
    quality = {
        "missing_cells": missing_cells,
        "missing_ratio": round(_safe_ratio(missing_cells, total_cells), 4),
        "duplicate_rows": duplicate_rows,
        "duplicate_ratio": round(_safe_ratio(duplicate_rows, len(df) or 1), 4),
        "outlier_share": 0.0,
    }

    if not primary_metric:
        return quality

    series = _safe_numeric(df[primary_metric]).dropna()
    if len(series) < 8:
        return quality

    q1 = float(series.quantile(0.25))
    q3 = float(series.quantile(0.75))
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    outliers = series[(series < lower) | (series > upper)]
    quality["outlier_share"] = round(_safe_ratio(len(outliers), len(series)), 4)
    return quality


def _make_multiline_chart(df: pd.DataFrame, time_col: str, metric_cols: list[str], title: str) -> Optional[go.Figure]:
    usable_metrics = [col for col in metric_cols if col in df.columns]
    if not time_col or not usable_metrics:
        return None
    temp = df[[time_col] + usable_metrics].copy()
    temp[time_col] = _coerce_datetime(temp[time_col])
    temp = temp.dropna(subset=[time_col])
    if temp.empty:
        return None
    grain = _choose_time_grain(temp[time_col])
    temp["period"] = _bucket_time(temp[time_col], grain)
    agg = temp.groupby("period", as_index=False)[usable_metrics].sum().sort_values("period")
    if agg.empty:
        return None
    palette = ["#0f766e", "#ea580c", "#2563eb", "#0f172a"]
    fig = go.Figure()
    for idx, metric in enumerate(usable_metrics):
        fig.add_trace(
            go.Scatter(
                x=agg["period"],
                y=agg[metric],
                mode="lines+markers",
                name=metric,
                line=dict(color=palette[idx % len(palette)], width=3),
                marker=dict(size=7),
                hovertemplate=f"<b>{metric}</b><br>%{{x}}<br>Gia tri: %{{y}}<extra></extra>",
            )
        )
    fig.update_xaxes(title="Thoi gian")
    fig.update_yaxes(title="Gia tri")
    return _apply_figure_style(fig, title, height=380)


def _make_margin_bar_chart(df: pd.DataFrame, category_col: str, revenue_col: str, profit_col: str, title: str) -> Optional[go.Figure]:
    temp = df[[category_col, revenue_col, profit_col]].copy()
    temp[revenue_col] = _safe_numeric(temp[revenue_col])
    temp[profit_col] = _safe_numeric(temp[profit_col])
    temp = temp.dropna()
    if temp.empty:
        return None
    agg = temp.groupby(category_col, as_index=False)[[revenue_col, profit_col]].sum()
    agg["margin_ratio"] = np.where(agg[revenue_col].abs() > 0, agg[profit_col] / agg[revenue_col], np.nan)
    agg = agg.dropna(subset=["margin_ratio"]).sort_values("margin_ratio", ascending=False).head(10)
    if agg.empty:
        return None
    fig = go.Figure(
        data=[
            go.Bar(
                x=agg[category_col].astype(str),
                y=agg["margin_ratio"],
                marker_color="#2563eb",
                text=[_format_value(v, percent=True) for v in agg["margin_ratio"]],
                textposition="auto",
                hovertemplate="<b>%{x}</b><br>Margin: %{y:.1%}<extra></extra>",
            )
        ]
    )
    fig.update_xaxes(title=category_col, tickangle=-25)
    fig.update_yaxes(title="Margin", tickformat=".0%")
    return _apply_figure_style(fig, title, height=340)


def _make_grouped_comparison_chart(rows: list[dict[str, float]], title: str) -> Optional[go.Figure]:
    if not rows:
        return None
    df_rows = pd.DataFrame(rows)
    fig = go.Figure()
    if "Previous" in df_rows.columns:
        fig.add_trace(go.Bar(name="Ky truoc", x=df_rows["Metric"], y=df_rows["Previous"], marker_color="#94a3b8"))
    if "Target" in df_rows.columns:
        fig.add_trace(go.Bar(name="Target", x=df_rows["Metric"], y=df_rows["Target"], marker_color="#cbd5e1"))
    fig.add_trace(go.Bar(name="Actual", x=df_rows["Metric"], y=df_rows["Actual"], marker_color="#0f766e"))
    fig.update_layout(barmode="group")
    fig.update_xaxes(title="Chi so")
    fig.update_yaxes(title="Gia tri")
    return _apply_figure_style(fig, title, height=340)


def _make_variance_chart(df: pd.DataFrame, time_col: str, category_col: str, metric_col: str, title: str) -> Optional[go.Figure]:
    temp = df[[time_col, category_col, metric_col]].copy()
    temp[time_col] = _coerce_datetime(temp[time_col])
    temp[metric_col] = _safe_numeric(temp[metric_col])
    temp = temp.dropna()
    if temp.empty:
        return None
    grain = _choose_time_grain(temp[time_col])
    temp["period"] = _bucket_time(temp[time_col], grain)
    periods = temp["period"].sort_values().unique()
    if len(periods) < 2:
        return None
    current_period = periods[-1]
    previous_period = periods[-2]
    temp = temp[temp["period"].isin([previous_period, current_period])]
    agg = temp.groupby(["period", category_col], as_index=False)[metric_col].sum()
    pivot = agg.pivot(index=category_col, columns="period", values=metric_col).fillna(0)
    pivot["variance"] = pivot[current_period] - pivot[previous_period]
    pivot = pivot.sort_values("variance", key=lambda s: s.abs(), ascending=False).head(8).reset_index()
    if pivot.empty:
        return None
    colors = ["#16a34a" if value >= 0 else "#dc2626" for value in pivot["variance"]]
    fig = go.Figure(
        data=[
            go.Bar(
                x=pivot[category_col].astype(str),
                y=pivot["variance"],
                marker_color=colors,
                text=[_format_value(v, metric_name=metric_col) for v in pivot["variance"]],
                textposition="auto",
                hovertemplate="<b>%{x}</b><br>Chenh lech: %{y}<extra></extra>",
            )
        ]
    )
    fig.update_xaxes(title=category_col, tickangle=-25)
    fig.update_yaxes(title="Variance")
    return _apply_figure_style(fig, title, height=340)


def _build_filter_panel(
    df: pd.DataFrame,
    profile: SchemaProfile,
    time_col: Optional[str],
    dimension_cols: list[str],
) -> list[dict[str, Any]]:
    filters: list[dict[str, Any]] = []
    if time_col and time_col in df.columns:
        time_values = _coerce_datetime(df[time_col]).dropna()
        if not time_values.empty:
            filters.append(
                {
                    "label": "Thoi gian",
                    "column": time_col,
                    "kind": "time",
                    "preview": f"{time_values.min().date()} -> {time_values.max().date()}",
                }
            )
    for col in dimension_cols:
        if col not in df.columns:
            continue
        series = df[col].dropna().astype(str)
        if series.empty:
            continue
        nunique = int(series.nunique())
        top_values = series.value_counts().head(4).index.tolist()
        filters.append(
            {
                "label": col,
                "column": col,
                "kind": "category",
                "preview": ", ".join(top_values) + ("..." if nunique > 4 else ""),
            }
        )
    return filters[:6]


def _flatten_section_charts(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    charts: list[dict[str, Any]] = []
    for section in sections:
        for chart in section.get("charts", []):
            if chart.get("figure") is not None:
                charts.append(chart)
    return charts


def _build_kpis(
    df: pd.DataFrame,
    profile: SchemaProfile,
    primary_metric: Optional[str],
    secondary_metrics: list[str],
    time_col: Optional[str],
) -> list[dict[str, str]]:
    quality = _quality_summary(df, primary_metric)
    kpis: list[dict[str, str]] = [
        {"label": "Số dòng", "value": f"{len(df):,}", "description": "Quy mô dữ liệu được đưa vào báo cáo"},
        {"label": "Số cột", "value": str(df.shape[1]), "description": "Tổng số trường thông tin khả dụng"},
        {
            "label": "Thieu du lieu",
            "value": f"{quality['missing_ratio']:.1%}",
            "description": "Ty le o du lieu bi thieu",
        },
        {
            "label": "Dong trung lap",
            "value": f"{quality['duplicate_ratio']:.1%}",
            "description": "Ty le dong trung lap trong bang hien tai",
        },
    ]

    if primary_metric:
        series = _safe_numeric(df[primary_metric]).dropna()
        if not series.empty:
            kpis.append(
                {
                    "label": f"Tong {primary_metric}",
                    "value": _format_value(float(series.sum())),
                    "description": "KPI chính của dashboard",
                }
            )
            kpis.append(
                {
                    "label": f"TB {primary_metric}",
                    "value": _format_value(float(series.mean())),
                    "description": "Giá trị trung bình của KPI chính",
                }
            )

    if time_col and primary_metric:
        temp = df[[time_col, primary_metric]].copy()
        temp[time_col] = _coerce_datetime(temp[time_col])
        temp[primary_metric] = _safe_numeric(temp[primary_metric])
        temp = temp.dropna().sort_values(time_col)
        if len(temp) >= 2:
            first_val = float(temp.iloc[0][primary_metric])
            last_val = float(temp.iloc[-1][primary_metric])
            delta = last_val - first_val
            kpis.append(
                {
                    "label": "Biến động kỳ cuối",
                    "value": _format_value(delta),
                    "description": "Chênh lệch giữa điểm đầu và cuối chuỗi thời gian",
                }
            )

    for metric in secondary_metrics[:1]:
        series = _safe_numeric(df[metric]).dropna()
        if not series.empty:
            kpis.append(
                {
                    "label": f"TB {metric}",
                    "value": _format_value(float(series.mean())),
                    "description": "Chỉ số bổ sung để đối chiếu",
                }
            )

    return kpis[:8]


def _build_insights(
    df: pd.DataFrame,
    primary_metric: Optional[str],
    time_col: Optional[str],
    category_col: Optional[str],
    quality: dict[str, Any],
) -> dict[str, Any]:
    intro_parts = [f"Báo cáo được tạo từ {len(df):,} dòng và {df.shape[1]} cột."]
    if primary_metric:
        intro_parts.append(f"KPI trung tâm đang được ưu tiên là {primary_metric}.")
    if time_col:
        intro_parts.append(f"Trục thời gian hợp lệ được nhận diện là {time_col}.")

    trend_note = None
    if time_col and primary_metric:
        temp = df[[time_col, primary_metric]].copy()
        temp[time_col] = _coerce_datetime(temp[time_col])
        temp[primary_metric] = _safe_numeric(temp[primary_metric])
        temp = temp.dropna().sort_values(time_col)
        if len(temp) >= 2:
            first_val = float(temp.iloc[0][primary_metric])
            last_val = float(temp.iloc[-1][primary_metric])
            change_pct = _safe_ratio(last_val - first_val, abs(first_val) or 1.0)
            direction = "tăng" if change_pct >= 0 else "giảm"
            trend_note = (
                f"{primary_metric} đang {direction} {abs(change_pct):.1%} giữa đầu kỳ và cuối kỳ trong dữ liệu hiện tại."
            )

    decomposition_note = None
    if category_col and primary_metric:
        temp = df[[category_col, primary_metric]].copy()
        temp[primary_metric] = _safe_numeric(temp[primary_metric])
        temp = temp.dropna()
        if not temp.empty:
            agg = temp.groupby(category_col, as_index=False)[primary_metric].sum().sort_values(primary_metric, ascending=False)
            top_row = agg.iloc[0]
            decomposition_note = (
                f"Nhóm đóng góp lớn nhất theo {category_col} hiện là {top_row[category_col]} "
                f"với {_format_value(float(top_row[primary_metric]))}."
            )

    anomaly_note = None
    if primary_metric and quality.get("outlier_share", 0.0) > 0:
        anomaly_note = (
            f"Khoảng {quality['outlier_share']:.1%} giá trị của {primary_metric} nằm ngoài vùng IQR, "
            "cần kiểm tra trước khi đưa vào báo cáo điều hành."
        )

    quality_note = (
        f"Tỷ lệ thiếu dữ liệu là {quality['missing_ratio']:.1%}, "
        f"dòng trùng lặp {quality['duplicate_ratio']:.1%}."
    )

    actions = []
    if trend_note:
        actions.append("Tập trung drill-down vào giai đoạn có biến động mạnh nhất trên trục thời gian.")
    if decomposition_note:
        actions.append(f"So sánh chi tiết các nhóm theo {category_col} để tìm nguyên nhân chênh lệch.")
    if quality["missing_ratio"] > 0.03:
        actions.append("Làm sạch missing values trước khi chốt báo cáo hoặc đưa vào mô hình.")
    if quality["duplicate_ratio"] > 0.0:
        actions.append("Kiểm tra nguồn dòng trùng lặp để tránh double-count KPI.")
    if not actions:
        actions.append("Bổ sung bộ lọc theo thời gian và nhóm để report linh hoạt hơn.")

    return {
        "intro": " ".join(intro_parts),
        "trend": trend_note,
        "decomposition": decomposition_note,
        "anomaly": anomaly_note,
        "quality": quality_note,
        "actions": actions[:4],
    }


def _build_finance_kpis(
    df: pd.DataFrame,
    time_col: Optional[str],
    revenue_col: Optional[str],
    cost_col: Optional[str],
    profit_col: Optional[str],
    order_col: Optional[str],
    customer_col: Optional[str],
    target_cols: dict[str, Optional[str]],
) -> list[dict[str, Any]]:
    kpis: list[dict[str, Any]] = []

    if revenue_col:
        revenue = _current_previous_metric(df, time_col, revenue_col, "sum")
        target = _current_previous_metric(df, time_col, target_cols["revenue"], "sum")["current"] if target_cols.get("revenue") else None
        kpis.append(
            _build_metric_card(
                "Doanh thu",
                revenue["current"],
                previous=revenue["previous"],
                target=target,
                metric_name=revenue_col,
                description="Gia tri thuc te cua ky gan nhat.",
                previous_label=revenue["previous_label"],
            )
        )

    if cost_col:
        cost = _current_previous_metric(df, time_col, cost_col, "sum")
        target = _current_previous_metric(df, time_col, target_cols["cost"], "sum")["current"] if target_cols.get("cost") else None
        kpis.append(
            _build_metric_card(
                "Chi phi",
                cost["current"],
                previous=cost["previous"],
                target=target,
                positive_when_higher=False,
                metric_name=cost_col,
                description="Tong chi phi tai ky gan nhat.",
                previous_label=cost["previous_label"],
            )
        )

    if profit_col:
        profit = _current_previous_metric(df, time_col, profit_col, "sum")
        target = _current_previous_metric(df, time_col, target_cols["profit"], "sum")["current"] if target_cols.get("profit") else None
        kpis.append(
            _build_metric_card(
                "Loi nhuan",
                profit["current"],
                previous=profit["previous"],
                target=target,
                metric_name=profit_col,
                description="Loi nhuan ky gan nhat.",
                previous_label=profit["previous_label"],
            )
        )

    if revenue_col and profit_col:
        revenue = _current_previous_metric(df, time_col, revenue_col, "sum")
        profit = _current_previous_metric(df, time_col, profit_col, "sum")
        current_margin = _safe_ratio(profit["current"] or 0.0, revenue["current"] or 0.0)
        previous_margin = None
        if revenue["previous"] not in (None, 0) and profit["previous"] is not None:
            previous_margin = _safe_ratio(profit["previous"], revenue["previous"])
        kpis.append(
            _build_metric_card(
                "Bien loi nhuan",
                current_margin,
                previous=previous_margin,
                percent=True,
                description="Loi nhuan / doanh thu.",
                previous_label=revenue["previous_label"],
            )
        )

    if order_col:
        orders = _current_previous_count(df, time_col, id_col=order_col, label="orders")
        kpis.append(
            _build_metric_card(
                "Don hang",
                orders["current"],
                previous=orders["previous"],
                description="So don hang unique theo ky.",
                previous_label=orders["previous_label"],
            )
        )

    if customer_col:
        customers = _current_previous_count(df, time_col, id_col=customer_col, label="customers")
        kpis.append(
            _build_metric_card(
                "Khach hang",
                customers["current"],
                previous=customers["previous"],
                description="So khach hang unique theo ky.",
                previous_label=customers["previous_label"],
            )
        )

    return kpis[:6]


def _build_quant_kpis(
    df: pd.DataFrame,
    primary_metric: Optional[str],
    time_col: Optional[str],
    binary_metric: Optional[str],
) -> list[dict[str, Any]]:
    kpis: list[dict[str, Any]] = [
        {
            "label": "Tong record",
            "value": f"{len(df):,}",
            "delta": None,
            "delta_color": "normal",
            "comparison": "",
            "description": "Tong so dong du lieu dang duoc phan tich.",
        }
    ]

    if primary_metric and primary_metric in df.columns:
        series = _safe_numeric(df[primary_metric]).dropna()
        if not series.empty:
            kpis.extend(
                [
                    {
                        "label": "Gia tri trung tam",
                        "value": _format_value(float(series.mean()), metric_name=primary_metric),
                        "delta": None,
                        "delta_color": "normal",
                        "comparison": primary_metric,
                        "description": "Metric chinh cua dashboard.",
                    },
                    {
                        "label": "Min",
                        "value": _format_value(float(series.min()), metric_name=primary_metric),
                        "delta": None,
                        "delta_color": "normal",
                        "comparison": primary_metric,
                        "description": "Gia tri nho nhat.",
                    },
                    {
                        "label": "Max",
                        "value": _format_value(float(series.max()), metric_name=primary_metric),
                        "delta": None,
                        "delta_color": "normal",
                        "comparison": primary_metric,
                        "description": "Gia tri lon nhat.",
                    },
                ]
            )
            if time_col:
                movement = _current_previous_metric(df, time_col, primary_metric, _metric_aggregation(primary_metric))
                if movement["current"] is not None and movement["previous"] is not None:
                    kpis.append(
                        _build_metric_card(
                            "Biến động gần nhất",
                            movement["current"],
                            previous=movement["previous"],
                            metric_name=primary_metric,
                            description="Giá trị kỳ gần nhất so với kỳ trước.",
                            previous_label=movement["previous_label"],
                        )
                    )

    if binary_metric and binary_metric in df.columns:
        rate = float(_safe_numeric(df[binary_metric]).dropna().mean())
        kpis.append(
            {
                "label": "Tỷ lệ đạt",
                "value": _format_value(rate, percent=True),
                "delta": None,
                "delta_color": "normal",
                "comparison": binary_metric,
                "description": "Tỷ lệ pass/completion.",
            }
        )

    return kpis[:5]


def _build_finance_insight_items(
    df: pd.DataFrame,
    time_col: Optional[str],
    revenue_col: Optional[str],
    cost_col: Optional[str],
    profit_col: Optional[str],
    dimension_cols: list[str],
    quality: dict[str, Any],
) -> list[str]:
    insights: list[str] = []
    if revenue_col and time_col:
        revenue = _current_previous_metric(df, time_col, revenue_col, "sum")
        if revenue["current"] is not None and revenue["previous"] is not None:
            change = _safe_ratio(revenue["current"] - revenue["previous"], abs(revenue["previous"]) or 1.0)
            insights.append(f"Doanh thu kỳ gần nhất biến động {change:+.1%} so với {revenue['previous_label']}.")
    if revenue_col and profit_col:
        revenue = _current_previous_metric(df, time_col, revenue_col, "sum")
        profit = _current_previous_metric(df, time_col, profit_col, "sum")
        if revenue["current"] not in (None, 0) and profit["current"] is not None:
            margin_now = _safe_ratio(profit["current"], revenue["current"])
            margin_prev = None
            if revenue["previous"] not in (None, 0) and profit["previous"] is not None:
                margin_prev = _safe_ratio(profit["previous"], revenue["previous"])
            if margin_prev is not None:
                insights.append(f"Biên lợi nhuận thay đổi {(margin_now - margin_prev):+.1%} điểm so với kỳ trước.")
    if cost_col and revenue_col and time_col:
        revenue = _current_previous_metric(df, time_col, revenue_col, "sum")
        cost = _current_previous_metric(df, time_col, cost_col, "sum")
        if revenue["previous"] is not None and cost["previous"] is not None:
            if _safe_ratio(cost["current"] - cost["previous"], abs(cost["previous"]) or 1.0) > _safe_ratio(
                revenue["current"] - revenue["previous"], abs(revenue["previous"]) or 1.0
            ):
                insights.append("Chi phí đang tăng nhanh hơn doanh thu, cần xem lại cơ cấu vận hành và khuyến mãi.")
    if dimension_cols and revenue_col:
        dim = dimension_cols[0]
        temp = df[[dim, revenue_col]].copy()
        temp[revenue_col] = _safe_numeric(temp[revenue_col])
        temp = temp.dropna()
        if not temp.empty:
            agg = temp.groupby(dim, as_index=False)[revenue_col].sum().sort_values(revenue_col, ascending=False)
            top_row = agg.iloc[0]
            insights.append(
                f"{dim} đóng góp lớn nhất là {top_row[dim]} với {_format_value(float(top_row[revenue_col]), metric_name=revenue_col)}."
            )
    if dimension_cols and revenue_col and profit_col:
        dim = dimension_cols[0]
        temp = df[[dim, revenue_col, profit_col]].copy()
        temp[revenue_col] = _safe_numeric(temp[revenue_col])
        temp[profit_col] = _safe_numeric(temp[profit_col])
        temp = temp.dropna()
        if not temp.empty:
            agg = temp.groupby(dim, as_index=False)[[revenue_col, profit_col]].sum()
            agg["margin_ratio"] = np.where(agg[revenue_col].abs() > 0, agg[profit_col] / agg[revenue_col], np.nan)
            agg = agg.dropna(subset=["margin_ratio"]).sort_values("margin_ratio")
            if not agg.empty:
                row = agg.iloc[0]
                insights.append(f"{row[dim]} có margin thấp nhất ({row['margin_ratio']:.1%}), cần ưu tiên drill-down.")
    if quality["missing_ratio"] > 0.03 or quality["duplicate_ratio"] > 0.0:
        insights.append(f"Chất lượng dữ liệu cần xem lại: thiếu {quality['missing_ratio']:.1%}, trùng lặp {quality['duplicate_ratio']:.1%}.")
    return insights[:5]


def _build_quant_insight_items(
    df: pd.DataFrame,
    primary_metric: Optional[str],
    secondary_metrics: list[str],
    time_col: Optional[str],
    dimension_cols: list[str],
    binary_metric: Optional[str],
    quality: dict[str, Any],
) -> list[str]:
    insights: list[str] = []
    if primary_metric and primary_metric in df.columns:
        series = _safe_numeric(df[primary_metric]).dropna()
        if not series.empty:
            insights.append(
                f"{primary_metric} tập trung quanh {_format_value(float(series.median()), metric_name=primary_metric)}, "
                f"dao động từ {_format_value(float(series.min()), metric_name=primary_metric)} đến {_format_value(float(series.max()), metric_name=primary_metric)}."
            )
    if quality["outlier_share"] > 0:
        insights.append(f"Khoảng {quality['outlier_share']:.1%} giá trị nằm ngoài vùng IQR, cần đọc histogram và boxplot trước.")
    if dimension_cols and primary_metric:
        dim = dimension_cols[0]
        temp = df[[dim, primary_metric]].copy()
        temp[primary_metric] = _safe_numeric(temp[primary_metric])
        temp = temp.dropna()
        if not temp.empty:
            agg = temp.groupby(dim, as_index=False)[primary_metric].mean().sort_values(primary_metric, ascending=False)
            best = agg.iloc[0]
            worst = agg.iloc[-1]
            insights.append(
                f"{dim} tốt nhất là {best[dim]} ({_format_value(float(best[primary_metric]), metric_name=primary_metric)}), "
                f"thấp nhất là {worst[dim]} ({_format_value(float(worst[primary_metric]), metric_name=primary_metric)})."
            )
    if time_col and primary_metric:
        movement = _current_previous_metric(df, time_col, primary_metric, _metric_aggregation(primary_metric))
        if movement["current"] is not None and movement["previous"] is not None:
            insights.append(f"Kỳ gần nhất, {primary_metric} biến động {_format_pct_delta(movement['current'], movement['previous'])} so với {movement['previous_label']}.")
    if primary_metric and secondary_metrics:
        corr = df[[primary_metric] + secondary_metrics[:3]].apply(pd.to_numeric, errors="coerce").corr(numeric_only=True)
        if not corr.empty:
            pairs: list[tuple[float, str, str]] = []
            for left in corr.columns:
                for right in corr.columns:
                    if left >= right:
                        continue
                    pairs.append((abs(float(corr.loc[left, right])), left, right))
            pairs.sort(reverse=True)
            if pairs and pairs[0][0] >= 0.3:
                value, left, right = pairs[0]
                insights.append(f"Cặp biến {left} và {right} có tương quan đáng chú ý (|r|={value:.2f}).")
    if binary_metric and binary_metric in df.columns:
        insights.append(f"Tỷ lệ đạt của {binary_metric} hiện tại là {_format_value(float(_safe_numeric(df[binary_metric]).dropna().mean()), percent=True)}.")
    return insights[:5]


def _build_finance_dashboard_result(
    df: pd.DataFrame,
    dataset_name: str,
    role: str,
    goal: str,
    profile: SchemaProfile,
) -> dict[str, Any]:
    working_df = df.copy()
    time_col = _pick_best_time_col(working_df, profile)
    revenue_col = _find_matching_column(profile.numeric_cols, FINANCE_METRIC_ALIASES["revenue"])
    cost_col = _find_matching_column(profile.numeric_cols, FINANCE_METRIC_ALIASES["cost"])
    profit_col = _find_matching_column(profile.numeric_cols, FINANCE_METRIC_ALIASES["profit"])
    margin_col = _find_matching_column(profile.numeric_cols, FINANCE_METRIC_ALIASES["margin"])

    if not profit_col and revenue_col and cost_col:
        working_df["__computed_profit__"] = _safe_numeric(working_df[revenue_col]) - _safe_numeric(working_df[cost_col])
        profit_col = "__computed_profit__"
        if profit_col not in profile.numeric_cols:
            profile.numeric_cols.append(profit_col)

    if not margin_col and revenue_col and profit_col:
        revenue_values = _safe_numeric(working_df[revenue_col])
        profit_values = _safe_numeric(working_df[profit_col])
        working_df["__computed_margin_ratio__"] = np.where(revenue_values.abs() > 0, profit_values / revenue_values, np.nan)
        margin_col = "__computed_margin_ratio__"
        if margin_col not in profile.numeric_cols:
            profile.numeric_cols.append(margin_col)

    order_col = _find_matching_column(profile.id_cols + profile.categorical_cols, ["order", "invoice", "transaction"])
    customer_col = _find_matching_column(profile.id_cols + profile.categorical_cols, ["customer", "client"])
    dimension_cols = _pick_dimension_candidates(working_df, profile, FINANCE_DIMENSION_HINTS, max_count=4)
    quality = _quality_summary(working_df, revenue_col or profit_col or margin_col)
    target_cols = {
        "revenue": _find_target_column(profile.numeric_cols, FINANCE_METRIC_ALIASES["revenue"]),
        "cost": _find_target_column(profile.numeric_cols, FINANCE_METRIC_ALIASES["cost"]),
        "profit": _find_target_column(profile.numeric_cols, FINANCE_METRIC_ALIASES["profit"]),
    }
    kpis = _build_finance_kpis(working_df, time_col, revenue_col, cost_col, profit_col, order_col, customer_col, target_cols)

    trend_charts: list[dict[str, Any]] = []
    trend_fig = _make_multiline_chart(
        working_df,
        time_col,
        [metric for metric in [revenue_col, cost_col, profit_col] if metric],
        "Xu hướng doanh thu, chi phí, lợi nhuận",
    ) if time_col else None
    if trend_fig is not None:
        trend_charts.append({"title": "Xu hướng KPI tài chính", "kind": "trend", "figure": trend_fig})

    breakdown_charts: list[dict[str, Any]] = []
    if revenue_col and dimension_cols:
        breakdown_charts.append(
            {
                "title": f"Doanh thu theo {dimension_cols[0]}",
                "kind": "breakdown",
                "figure": _make_bar_chart(working_df, dimension_cols[0], revenue_col, agg="sum", title=f"Doanh thu theo {dimension_cols[0]}"),
            }
        )
    if revenue_col and profit_col and len(dimension_cols) >= 2:
        fig = _make_margin_bar_chart(working_df, dimension_cols[1], revenue_col, profit_col, f"Margin theo {dimension_cols[1]}")
        if fig is not None:
            breakdown_charts.append({"title": f"Margin theo {dimension_cols[1]}", "kind": "breakdown", "figure": fig})

    comparison_rows: list[dict[str, float]] = []
    for label, metric_name, column in [
        ("Doanh thu", "revenue", revenue_col),
        ("Chi phi", "cost", cost_col),
        ("Lợi nhuận", "profit", profit_col),
    ]:
        if not column:
            continue
        values = _current_previous_metric(working_df, time_col, column, "sum")
        row: dict[str, float] = {"Metric": label, "Actual": values["current"] or 0.0}
        if values["previous"] is not None:
            row["Previous"] = values["previous"]
        if target_cols.get(metric_name):
            target_value = _current_previous_metric(working_df, time_col, target_cols[metric_name], "sum")["current"]
            if target_value is not None:
                row["Target"] = target_value
        comparison_rows.append(row)

    comparison_charts: list[dict[str, Any]] = []
    comparison_title = "Actual vs Target" if any("Target" in row for row in comparison_rows) else "Current vs Previous Period"
    comparison_fig = _make_grouped_comparison_chart(comparison_rows, comparison_title)
    if comparison_fig is not None:
        comparison_charts.append({"title": comparison_title, "kind": "comparison", "figure": comparison_fig})
    if time_col and dimension_cols and (revenue_col or profit_col):
        variance_fig = _make_variance_chart(working_df, time_col, dimension_cols[0], revenue_col or profit_col, f"Top tăng giảm theo {dimension_cols[0]}")
        if variance_fig is not None:
            comparison_charts.append({"title": f"Top tăng giảm theo {dimension_cols[0]}", "kind": "variance", "figure": variance_fig})

    insights_list = _build_finance_insight_items(working_df, time_col, revenue_col, cost_col, profit_col, dimension_cols, quality)
    filters = _build_filter_panel(working_df, profile, time_col, dimension_cols)
    sections = [
        {"id": "kpi_overview", "title": "Tổng quan KPI", "placement": "top", "kpis": kpis},
        {"id": "trend", "title": "Xu hướng", "placement": "main", "charts": trend_charts, "note": "Xem xu hướng trước khi drill-down."},
        {"id": "breakdown", "title": "Phân tích chi tiết", "placement": "main", "charts": breakdown_charts, "note": "Chỉ giữ các chiều đóng góp quan trọng nhất."},
        {"id": "comparison", "title": "So sánh / Biến động", "placement": "main", "charts": comparison_charts, "note": "So sánh với kỳ trước và target nếu có."},
        {"id": "insight_box", "title": "Nhận xét", "placement": "side", "items": insights_list},
        {"id": "filter_panel", "title": "Bộ lọc", "placement": "side", "filters": filters},
        {"id": "data_quality", "title": "Chất lượng dữ liệu", "placement": "side", "quality": quality},
    ]
    questions = [
        "Doanh thu kỳ gần nhất tăng hay giảm so với kỳ trước?",
        "Lợi nhuận và biên lợi nhuận có đang tốt lên không?",
        f"Nhóm {dimension_cols[0] if dimension_cols else 'kinh doanh'} nào đóng góp lớn nhất?",
        "Chi phí có tăng bất thường không?",
        "Điểm tăng mạnh nhất và giảm mạnh nhất nằm ở đâu?",
    ]
    return {
        "__type__": "dashboard",
        "title": f"Dashboard: {dataset_name}",
        "subtitle": f"{ROLE_LABELS.get(role, role.title())} | Theo dõi hiệu quả và variance tài chính.",
        "schema": {
            "time_cols": profile.time_cols,
            "numeric_cols": profile.numeric_cols,
            "categorical_cols": profile.categorical_cols,
            "id_cols": profile.id_cols,
        },
        "quality": quality,
        "kpis": kpis,
        "charts": _flatten_section_charts(sections)[:6],
        "insights": {"items": insights_list, "actions": insights_list[:3]},
        "sections": sections,
        "design": {
            "blueprint": "finance",
            "objective": "Dashboard tài chính gọn, rõ, có so sánh kỳ trước/target và tập trung vào quyết định.",
            "primary_user": ROLE_LABELS.get(role, "Finance Manager"),
            "management_questions": questions,
            "layout": {
                "top": "KPI ở trên cùng",
                "middle": "Trend và comparison ở giữa",
                "bottom": "Breakdown ở phía dưới",
                "side": "Insight box và filter panel bên phải",
            },
            "mistakes_to_avoid": [
                "Không nhóm quá nhiều biểu đồ tài chính vào một màn hình.",
                "Không hiển thị KPI mà thiếu kỳ so sánh.",
                "Không dùng màu sắc không nhất quán cho tăng/giảm.",
            ],
        },
        "context": {
            "dataset_name": dataset_name,
            "domain": "finance",
            "role": role,
            "goal": goal or "dashboard tài chính tự động",
            "primary_metric": revenue_col or profit_col or margin_col,
            "time_col": time_col,
            "category_col": dimension_cols[0] if dimension_cols else None,
            "secondary_metrics": [metric for metric in [cost_col, profit_col, margin_col] if metric and metric != revenue_col],
            "dashboard_family": "finance",
            "filter_columns": [item["column"] for item in filters],
        },
    }


def _build_quant_dashboard_result(
    df: pd.DataFrame,
    dataset_name: str,
    role: str,
    goal: str,
    profile: SchemaProfile,
    domain: str,
) -> dict[str, Any]:
    primary_metric = _pick_primary_metric(df, profile, role, domain)
    secondary_metrics = _pick_secondary_metrics(df, profile, primary_metric, role, domain)
    time_col = _pick_best_time_col(df, profile)
    dimension_cols = _pick_dimension_candidates(df, profile, QUANT_DIMENSION_HINTS, max_count=3)
    if not dimension_cols:
        best_category = _pick_best_category(df, profile)
        dimension_cols = [best_category] if best_category else []
    binary_metric = _pick_binary_metric(df, profile)
    quality = _quality_summary(df, primary_metric)
    kpis = _build_quant_kpis(df, primary_metric, time_col, binary_metric)

    distribution_charts: list[dict[str, Any]] = []
    if primary_metric:
        distribution_charts.append({"title": f"Phân phối {primary_metric}", "kind": "distribution", "figure": _make_histogram(df, primary_metric)})
        distribution_charts.append({"title": f"Boxplot {primary_metric}", "kind": "distribution", "figure": _make_box_chart(df, primary_metric, dimension_cols[0] if dimension_cols else None)})

    trend_charts: list[dict[str, Any]] = []
    if time_col and primary_metric:
        trend_charts.append(
            {
                "title": f"Xu hướng {primary_metric}",
                "kind": "trend",
                "figure": _make_line_chart(
                    df,
                    time_col,
                    primary_metric,
                    agg=_metric_aggregation(primary_metric),
                    title=f"Xu hướng {primary_metric} theo thời gian",
                ),
            }
        )

    breakdown_charts: list[dict[str, Any]] = []
    if dimension_cols and primary_metric:
        breakdown_charts.append(
            {
                "title": f"Hiệu quả theo {dimension_cols[0]}",
                "kind": "breakdown",
                "figure": _make_bar_chart(
                    df,
                    dimension_cols[0],
                    primary_metric,
                    agg="mean" if _metric_aggregation(primary_metric) == "mean" else "sum",
                    title=f"Hiệu quả theo {dimension_cols[0]}",
                ),
            }
        )

    relationship_charts: list[dict[str, Any]] = []
    if primary_metric and secondary_metrics:
        relationship_charts.append(
            {
                "title": f"Tương quan {primary_metric} và {secondary_metrics[0]}",
                "kind": "relationship",
                "figure": _make_scatter_chart(df, primary_metric, secondary_metrics[0], dimension_cols[0] if dimension_cols else None),
            }
        )
    heatmap = _make_heatmap(df, [primary_metric] + secondary_metrics if primary_metric else secondary_metrics)
    if heatmap is not None:
        relationship_charts.append({"title": "Bản đồ tương quan", "kind": "relationship", "figure": heatmap})

    insights_list = _build_quant_insight_items(df, primary_metric, secondary_metrics, time_col, dimension_cols, binary_metric, quality)
    filters = _build_filter_panel(df, profile, time_col, dimension_cols)
    sections = [
        {"id": "kpi_overview", "title": "Tổng quan KPI", "placement": "top", "kpis": kpis},
        {
            "id": "distribution",
            "title": "Phân phối",
            "placement": "main",
            "charts": [chart for chart in distribution_charts if chart.get("figure") is not None],
            "note": "Histogram và boxplot là trọng tâm để đọc phân phối.",
        },
        {
            "id": "trend",
            "title": "Xu hướng",
            "placement": "main",
            "charts": [chart for chart in trend_charts if chart.get("figure") is not None],
            "note": "Chỉ hiển thị khi có cột thời gian hợp lệ.",
        },
        {
            "id": "breakdown",
            "title": "Phân tích / Phân khúc",
            "placement": "main",
            "charts": [chart for chart in breakdown_charts if chart.get("figure") is not None],
            "note": "Ưu tiên 1-2 dimension quan trọng nhất.",
        },
        {
            "id": "relationship",
            "title": "Tương quan",
            "placement": "main",
            "charts": [chart for chart in relationship_charts if chart.get("figure") is not None],
            "note": "Chỉ giữ scatter/heatmap cần thiết.",
        },
        {"id": "insight_box", "title": "Nhận xét", "placement": "side", "items": insights_list},
        {"id": "filter_panel", "title": "Bộ lọc", "placement": "side", "filters": filters},
        {"id": "data_quality", "title": "Chất lượng dữ liệu", "placement": "side", "quality": quality},
    ]
    questions = [
        "Metric chính hiện đang nằm trong vùng giá trị nào?",
        "Dữ liệu có lệch phân phối hoặc có outlier cần chú ý không?",
        f"Nhóm {dimension_cols[0] if dimension_cols else 'segment'} nào tốt nhất và kém nhất?",
        "Xu hướng theo thời gian có bất thường không?" if time_col else "Có mối tương quan nào đáng chú ý giữa các biến?",
        "Có mối tương quan nào đáng chú ý giữa các biến?",
    ]
    return {
        "__type__": "dashboard",
        "title": f"Dashboard: {dataset_name}",
        "subtitle": f"{ROLE_LABELS.get(role, role.title())} | Dashboard định lượng đa biến, gọn và tập trung insight.",
        "schema": {
            "time_cols": profile.time_cols,
            "numeric_cols": profile.numeric_cols,
            "categorical_cols": profile.categorical_cols,
            "id_cols": profile.id_cols,
        },
        "quality": quality,
        "kpis": kpis,
        "charts": _flatten_section_charts(sections)[:6],
        "insights": {"items": insights_list, "actions": insights_list[:3]},
        "sections": sections,
        "design": {
            "blueprint": "quantitative_multivariate",
            "objective": "Dashboard định lượng đa biến, dễ đọc trong 5 giây và ưu tiên distribution, breakdown, relationship.",
            "primary_user": ROLE_LABELS.get(role, "Analyst"),
            "management_questions": questions,
            "layout": {
                "top": "KPI ở trên cùng",
                "middle": "Phân phối và xu hướng ở giữa",
                "bottom": "Phân tích và tương quan ở phía dưới",
                "side": "Nhận xét, chất lượng dữ liệu và bộ lọc bên phải",
            },
            "mistakes_to_avoid": [
                "Không bỏ qua histogram/boxplot khi dữ liệu lệch.",
                "Không nhồi quá nhiều dimension vào một dashboard.",
                "Không vẽ trend chart khi không có cột thời gian hợp lệ.",
            ],
        },
        "context": {
            "dataset_name": dataset_name,
            "domain": domain,
            "role": role,
            "goal": goal or "dashboard định lượng tự động",
            "primary_metric": primary_metric,
            "time_col": time_col,
            "category_col": dimension_cols[0] if dimension_cols else None,
            "secondary_metrics": secondary_metrics,
            "dashboard_family": "quantitative_multivariate",
            "filter_columns": [item["column"] for item in filters],
        },
    }

def build_auto_dashboard(
    df: pd.DataFrame,
    dataset_name: str = "Dataset",
    role: str = "analyst",
    goal: str = "",
) -> dict[str, Any]:
    profile = _detect_schema(df)
    domain = _detect_domain([str(col) for col in df.columns])
    goal_norm = _normalize_name(goal or "")
    finance_signals = [
        col
        for col in profile.numeric_cols + profile.categorical_cols + profile.id_cols
        if _contains_any(_normalize_name(col), ["revenue", "sales", "profit", "margin", "cost", "expense", "target", "budget", "order"])
    ]
    use_finance = domain in {"finance", "sales"} or len(finance_signals) >= 3 or _contains_any(
        goal_norm,
        ["tai_chinh", "doanh_thu", "loi_nhuan", "chi_phi", "margin", "financial", "finance"],
    )
    if use_finance:
        return _build_finance_dashboard_result(df, dataset_name, role, goal, profile)
    return _build_quant_dashboard_result(df, dataset_name, role, goal, profile, domain)


def build_dashboard_report(
    data: Dict[str, pd.DataFrame],
    role: str = "analyst",
    goal: str = "",
) -> dict[str, Any]:
    if not data:
        return {
            "__type__": "dashboard_report",
            "title": REPORT_TITLE,
            "subtitle": "Không có dữ liệu để tạo báo cáo.",
            "overview": {"dataset_count": 0, "section_count": 0, "recommended_join_count": 0},
            "catalog": {},
            "sections": [],
        }

    catalog = build_data_catalog(data)
    master_data = build_master_datasets(data, catalog=catalog)
    selected_masters = select_non_overlapping_masters(catalog)

    sections: list[dict[str, Any]] = []
    covered_datasets: set[str] = set()

    for master_meta in selected_masters:
        master_name = master_meta["name"]
        if master_name not in master_data:
            continue
        dashboard = build_auto_dashboard(master_data[master_name], dataset_name=master_name, role=role, goal=goal)
        sections.append(
            {
                "title": f"Master report: {master_name}",
                "mode": "master",
                "sources": master_meta["sources"],
                "note": (
                    f"Bảng master được tạo từ {master_meta['sources'][0]} + {master_meta['sources'][1]} "
                    f"trên khóa {master_meta['left_key']} = {master_meta['right_key']} "
                    f"(confidence={master_meta['confidence']:.2f})."
                ),
                "dashboard": dashboard,
            }
        )
        covered_datasets.update(master_meta["sources"])

    for name, df in data.items():
        if name in covered_datasets:
            continue
        sections.append(
            {
                "title": f"Dataset report: {name}",
                "mode": "dataset",
                "sources": [name],
                "note": "Không có quan hệ đủ tin cậy với bảng khác. Hệ thống báo cáo độc lập cho bảng này.",
                "dashboard": build_auto_dashboard(df, dataset_name=name, role=role, goal=goal),
            }
        )

    if not sections and len(data) == 1:
        only_name, only_df = next(iter(data.items()))
        sections.append(
            {
                "title": f"Dataset report: {only_name}",
                "mode": "dataset",
                "sources": [only_name],
                "note": "Báo cáo được tạo từ một bảng dữ liệu duy nhất.",
                "dashboard": build_auto_dashboard(only_df, dataset_name=only_name, role=role, goal=goal),
            }
        )

    recommended_relationships = [rel for rel in catalog.get("relationships", []) if rel.get("recommended")]
    subtitle_parts = [
        f"Số bảng gốc: {len(data)}",
        f"Số section báo cáo: {len(sections)}",
        f"Join đề xuất: {len(recommended_relationships)}",
    ]
    if goal:
        subtitle_parts.append(f"Mục tiêu: {goal}")

    return {
        "__type__": "dashboard_report",
        "title": REPORT_TITLE,
        "subtitle": " | ".join(subtitle_parts),
        "overview": {
            "dataset_count": len(data),
            "section_count": len(sections),
            "recommended_join_count": len(recommended_relationships),
            "independent_group_count": catalog.get("overview", {}).get("independent_group_count", len(data)),
        },
        "catalog": catalog,
        "sections": sections,
    }
