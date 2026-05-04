"""
Chart service — pure chart-building functions (không phụ thuộc Streamlit).

Nhận DataFrame, trả về Plotly Figure hoặc structured dict.
Tầng UI (ui/render.py) chịu trách nhiệm gọi st.plotly_chart() từ kết quả này.

Mục đích tách biệt:
  - Service layer chỉ BUILD dữ liệu biểu đồ
  - UI layer mới RENDER ra màn hình
  → Dễ test, dễ tái sử dụng ngoài Streamlit (FastAPI, Jupyter, v.v.)
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

__all__ = [
    "build_bar_chart",
    "build_line_chart",
    "build_histogram",
    "build_scatter",
    "build_pie_chart",
    "build_box_chart",
    "build_heatmap",
    "build_kpi_summary",
    "prepare_result_for_render",
]


# ---------------------------------------------------------------------------
# Chart builders — nhận DataFrame, trả về go.Figure
# ---------------------------------------------------------------------------


def build_bar_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    title: str = "",
    color: Optional[str] = None,
    barmode: str = "group",
    orientation: str = "v",
) -> go.Figure:
    """
    Tạo biểu đồ cột (bar chart).

    Parameters
    ----------
    df : pd.DataFrame
    x, y : str
        Tên cột trục ngang / dọc.
    title : str
        Tiêu đề biểu đồ.
    color : str | None
        Cột dùng để phân nhóm màu.
    barmode : str
        ``"group"`` (nhóm) hoặc ``"stack"`` (chồng).
    orientation : str
        ``"v"`` (dọc, mặc định) hoặc ``"h"`` (ngang).

    Returns
    -------
    go.Figure
    """
    fig = px.bar(
        df,
        x=x,
        y=y,
        title=title,
        color=color,
        barmode=barmode,
        orientation=orientation,
    )
    fig.update_layout(margin=dict(t=40, b=20, l=10, r=10))
    return fig


def build_line_chart(
    df: pd.DataFrame,
    x: str,
    y: str | List[str],
    title: str = "",
    color: Optional[str] = None,
    markers: bool = False,
) -> go.Figure:
    """
    Tạo biểu đồ đường (line chart).

    Parameters
    ----------
    df : pd.DataFrame
    x : str
        Cột trục ngang (thường là thời gian).
    y : str | list[str]
        Một hoặc nhiều cột trục dọc.
    markers : bool
        Hiển thị điểm dữ liệu trên đường nếu True.

    Returns
    -------
    go.Figure
    """
    fig = px.line(df, x=x, y=y, title=title, color=color, markers=markers)
    fig.update_layout(margin=dict(t=40, b=20, l=10, r=10))
    return fig


def build_histogram(
    df: pd.DataFrame,
    column: str,
    title: str = "",
    nbins: int = 30,
    color: Optional[str] = None,
) -> go.Figure:
    """
    Tạo histogram phân phối cho một cột số.

    Parameters
    ----------
    df : pd.DataFrame
    column : str
        Tên cột cần vẽ phân phối.
    nbins : int
        Số bins (mặc định 30).

    Returns
    -------
    go.Figure
    """
    fig = px.histogram(df, x=column, title=title, nbins=nbins, color=color)
    fig.update_layout(margin=dict(t=40, b=20, l=10, r=10))
    return fig


def build_scatter(
    df: pd.DataFrame,
    x: str,
    y: str,
    title: str = "",
    color: Optional[str] = None,
    size: Optional[str] = None,
    hover_data: Optional[List[str]] = None,
) -> go.Figure:
    """
    Tạo biểu đồ phân tán (scatter plot).

    Parameters
    ----------
    size : str | None
        Cột dùng để điều chỉnh kích thước điểm (bubble chart).

    Returns
    -------
    go.Figure
    """
    fig = px.scatter(
        df,
        x=x,
        y=y,
        title=title,
        color=color,
        size=size,
        hover_data=hover_data,
    )
    fig.update_layout(margin=dict(t=40, b=20, l=10, r=10))
    return fig


def build_pie_chart(
    df: pd.DataFrame,
    names: str,
    values: str,
    title: str = "",
    hole: float = 0.0,
) -> go.Figure:
    """
    Tạo biểu đồ tròn (pie / donut chart).

    Parameters
    ----------
    hole : float
        0.0 = pie đầy đủ. 0.3–0.5 = donut chart.

    Returns
    -------
    go.Figure
    """
    fig = px.pie(df, names=names, values=values, title=title, hole=hole)
    fig.update_layout(margin=dict(t=40, b=20, l=10, r=10))
    return fig


def build_box_chart(
    df: pd.DataFrame,
    x: Optional[str] = None,
    y: str = "",
    title: str = "",
    color: Optional[str] = None,
) -> go.Figure:
    """
    Tạo box plot hiển thị phân phối và ngoại lệ.

    Returns
    -------
    go.Figure
    """
    fig = px.box(df, x=x, y=y, title=title, color=color)
    fig.update_layout(margin=dict(t=40, b=20, l=10, r=10))
    return fig


def build_heatmap(
    df: pd.DataFrame,
    title: str = "",
    color_scale: str = "RdBu_r",
) -> go.Figure:
    """
    Tạo heatmap từ DataFrame dạng ma trận (thường là correlation matrix).

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame vuông (rows = columns = biến số). Ví dụ: ``df.corr()``.
    color_scale : str
        Bảng màu Plotly (mặc định ``"RdBu_r"`` — đỏ/xanh cho tương quan).

    Returns
    -------
    go.Figure
    """
    fig = go.Figure(
        data=go.Heatmap(
            z=df.values,
            x=df.columns.tolist(),
            y=df.index.tolist(),
            colorscale=color_scale,
            zmid=0,
        )
    )
    if title:
        fig.update_layout(title=title)
    fig.update_layout(margin=dict(t=40, b=20, l=10, r=10))
    return fig


# ---------------------------------------------------------------------------
# KPI helpers — trả về list[dict] không phụ thuộc Streamlit
# ---------------------------------------------------------------------------


def build_kpi_summary(
    df: pd.DataFrame,
    numeric_columns: Optional[List[str]] = None,
    max_kpis: int = 8,
) -> List[Dict[str, Any]]:
    """
    Trích xuất KPI summary từ DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
    numeric_columns : list[str] | None
        Danh sách cột số để tính KPI. None = tự động phát hiện.
    max_kpis : int
        Số KPI tối đa (mặc định 8).

    Returns
    -------
    list[dict]
        Mỗi phần tử:
        ``{"label": str, "value": str, "delta": str | None, "mean": str}``
    """
    if numeric_columns is None:
        numeric_columns = df.select_dtypes(include="number").columns.tolist()

    kpis: List[Dict[str, Any]] = []
    for col in numeric_columns[:max_kpis]:
        series = df[col].dropna()
        if series.empty:
            continue
        total = series.sum()
        mean = series.mean()
        kpis.append(
            {
                "label": col.replace("_", " ").title(),
                "value": f"{total:,.0f}" if abs(total) >= 1000 else f"{total:,.2f}",
                "mean": f"{mean:,.2f}",
                "delta": None,
            }
        )
    return kpis


# ---------------------------------------------------------------------------
# Result normalizer — chuẩn hóa output cho UI layer
# ---------------------------------------------------------------------------


def prepare_result_for_render(result: Any) -> Dict[str, Any]:
    """
    Chuẩn hóa kết quả pipeline thành typed render descriptor.

    UI layer dùng dict này để quyết định cách render mà không cần
    kiểm tra type trực tiếp.

    Parameters
    ----------
    result : Any
        Output từ ExecOutcome.result hoặc build_dashboard_report.

    Returns
    -------
    dict
        ``{"type": str, "data": Any}``

        Các giá trị ``type``:

        ============== =====================================
        ``"figure"``   go.Figure — biểu đồ Plotly
        ``"dataframe"``pd.DataFrame — bảng dữ liệu
        ``"dashboard"``dict với ``__type__ == "dashboard"``
        ``"dashboard_report"`` dict với ``__type__ == "dashboard_report"``
        ``"list"``     list — nhiều kết quả
        ``"text"``     str hoặc giá trị khác
        ============== =====================================
    """
    if isinstance(result, go.Figure):
        return {"type": "figure", "data": result}

    if isinstance(result, pd.DataFrame):
        return {"type": "dataframe", "data": result}

    if isinstance(result, dict):
        result_type = result.get("__type__", "")
        if result_type == "dashboard_report":
            return {"type": "dashboard_report", "data": result}
        if result_type == "dashboard":
            return {"type": "dashboard", "data": result}

    if isinstance(result, (list, tuple)):
        return {"type": "list", "data": list(result)}

    return {"type": "text", "data": result}
