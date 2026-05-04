"""
UI render layer — toàn bộ lệnh Streamlit để hiển thị kết quả pipeline.

Module này là điểm duy nhất trong tầng UI chịu trách nhiệm render:
  - go.Figure       → st.plotly_chart
  - pd.DataFrame    → st.dataframe
  - dashboard dict  → layout KPI / chart / insight
  - dashboard_report → layout report nhiều section

Quy tắc:
  - KHÔNG chứa business logic (tính toán, gọi LLM, query DB).
  - KHÔNG import từ services/ (chỉ import kiểu dữ liệu).
  - Nhận kết quả đã build sẵn, render ra màn hình.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objs as go
import streamlit as st


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _next_plotly_key(prefix: str = "plotly_chart") -> str:
    counter = int(st.session_state.get("_plotly_render_counter", 0)) + 1
    st.session_state["_plotly_render_counter"] = counter
    return f"{prefix}_{counter}"


def _render_kpis(kpis: list[dict]) -> None:
    if not kpis:
        return
    for start in range(0, len(kpis), 4):
        row = kpis[start : start + 4]
        cols = st.columns(len(row))
        for col, item in zip(cols, row):
            with col:
                st.metric(
                    item.get("label", "KPI"),
                    item.get("value", "N/A"),
                    delta=item.get("delta"),
                    delta_color=item.get("delta_color", "normal"),
                )
                if item.get("comparison"):
                    st.caption(item["comparison"])
                if item.get("description"):
                    st.caption(item["description"])


def _render_quality(quality: dict, title: str = "Chất lượng dữ liệu") -> None:
    if not quality:
        return
    st.markdown(f"#### {title}")
    cols = st.columns(3)
    cols[0].metric("Thiếu", f"{quality.get('missing_ratio', 0.0):.1%}")
    cols[1].metric("Trùng lặp", f"{quality.get('duplicate_ratio', 0.0):.1%}")
    cols[2].metric("Ngoại lệ", f"{quality.get('outlier_share', 0.0):.1%}")


def _render_chart_grid(charts: list[dict]) -> None:
    charts = [c for c in charts if c.get("figure") is not None]
    if not charts:
        return
    for idx in range(0, len(charts), 2):
        row = charts[idx : idx + 2]
        cols = st.columns(len(row))
        for col, chart in zip(cols, row):
            with col:
                st.markdown(f"**{chart.get('title', 'Biểu đồ')}**")
                if isinstance(chart.get("figure"), go.Figure):
                    st.plotly_chart(
                        chart["figure"],
                        use_container_width=True,
                        key=_next_plotly_key("dashboard_chart"),
                    )


def _render_filter_panel(filters: list[dict]) -> None:
    if not filters:
        return
    st.markdown("#### Bộ lọc")
    for item in filters:
        st.write(f"- {item.get('label', 'Bộ lọc')}: {item.get('preview', '')}")


def _render_insight_box(items) -> None:
    if not items:
        return
    st.markdown("#### Nhận xét")
    if isinstance(items, dict):
        for key in ("intro", "trend", "decomposition", "anomaly", "quality"):
            value = items.get(key)
            if value:
                st.write(f"- {value}")
        for action in items.get("actions", []):
            st.write(f"- {action}")
        return
    for item in items:
        st.write(f"- {item}")


def _render_dashboard_meta(result: dict) -> None:
    design = result.get("design", {})
    if not design:
        return
    with st.expander("Mục tiêu và câu hỏi quản trị"):
        st.write(f"**Người dùng chính:** {design.get('primary_user', 'N/A')}")
        st.write(f"**Mục tiêu:** {design.get('objective', 'N/A')}")
        for question in design.get("management_questions", []):
            st.write(f"- {question}")


def _render_section(section: dict) -> None:
    if not section:
        return
    if title := section.get("title"):
        st.markdown(f"### {title}")
    if note := section.get("note"):
        st.caption(note)
    if section.get("kpis"):
        _render_kpis(section["kpis"])
    if section.get("charts"):
        _render_chart_grid(section["charts"])
    if section.get("items"):
        _render_insight_box(section["items"])
    if section.get("filters"):
        _render_filter_panel(section["filters"])
    if section.get("quality"):
        _render_quality(section["quality"])


def _render_dashboard(result: dict, show_header: bool = True) -> None:
    if show_header:
        st.markdown(f"## {result.get('title', 'Dashboard tự động')}")
        if subtitle := result.get("subtitle"):
            st.caption(subtitle)

    sections = result.get("sections", [])
    if not sections:
        _render_kpis(result.get("kpis", []))
        _render_chart_grid(result.get("charts", []))
        _render_insight_box(result.get("insights", {}))
        _render_quality(result.get("quality", {}))
        return

    _render_dashboard_meta(result)
    top_sections = [s for s in sections if s.get("placement") == "top"]
    main_sections = [s for s in sections if s.get("placement") == "main"]
    side_sections = [s for s in sections if s.get("placement") == "side"]

    for section in top_sections:
        _render_section(section)

    if main_sections or side_sections:
        main_col, side_col = st.columns([3, 1.2])
        with main_col:
            for section in main_sections:
                _render_section(section)
        with side_col:
            for section in side_sections:
                _render_section(section)


def _render_dashboard_report(result: dict) -> None:
    st.markdown(f"## {result.get('title', 'Báo cáo dashboard')}")
    if subtitle := result.get("subtitle"):
        st.caption(subtitle)

    overview = result.get("overview", {})
    cols = st.columns(4)
    cols[0].metric("Bảng gốc", overview.get("dataset_count", 0))
    cols[1].metric("Section", overview.get("section_count", 0))
    cols[2].metric("Join đề xuất", overview.get("recommended_join_count", 0))
    cols[3].metric("Nhóm độc lập", overview.get("independent_group_count", 0))

    catalog = result.get("catalog", {})
    if catalog:
        with st.expander("Toàn cảnh dữ liệu"):
            dataset_groups = catalog.get("dataset_groups", [])
            if dataset_groups:
                st.write("Nhóm bảng:", " | ".join(", ".join(g) for g in dataset_groups))
            for rel in catalog.get("relationships", [])[:5]:
                st.write(
                    f"- {rel['left_dataset']}.{rel['left_key']} "
                    f"<-> {rel['right_dataset']}.{rel['right_key']} "
                    f"(conf={rel['confidence']:.2f}, overlap={rel['overlap_ratio']:.0%})"
                )

    sections = result.get("sections", [])
    if not sections:
        st.info("Không có section nào để hiển thị.")
        return

    for section in sections:
        st.markdown(f"### {section.get('title', 'Section')}")
        if note := section.get("note"):
            st.caption(note)
        _render_dashboard(section.get("dashboard", {}), show_header=False)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render_result(result) -> None:
    """
    Điểm vào chính để render kết quả pipeline ra Streamlit UI.

    Dispatch tự động theo kiểu dữ liệu:

    ====================== ================================================
    Kiểu ``result``        Cách render
    ====================== ================================================
    ``dict`` dashboard_report  Full report nhiều section
    ``dict`` dashboard         Single dashboard với KPI/chart/insight
    ``go.Figure``          ``st.plotly_chart``
    ``pd.DataFrame``       ``st.dataframe``
    ``list`` / ``tuple``   Render từng phần tử theo thứ tự
    Khác                   ``st.write``
    ====================== ================================================

    Parameters
    ----------
    result :
        Giá trị từ ``ExecOutcome.result`` hoặc ``build_dashboard_report()``.
    """
    if isinstance(result, dict) and result.get("__type__") == "dashboard_report":
        _render_dashboard_report(result)
        return

    if isinstance(result, dict) and result.get("__type__") == "dashboard":
        _render_dashboard(result)
        return

    if isinstance(result, go.Figure):
        # Apply dark-mode compatible styling when no explicit background is set.
        # Charts from dashboard_service explicitly set paper_bgcolor="white" so
        # they are skipped; LLM-generated charts don't → they need this fix.
        if not result.layout.paper_bgcolor:
            result.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e2e8f0"),
                legend=dict(font=dict(color="#e2e8f0")),
            )
        st.plotly_chart(
            result,
            use_container_width=True,
            key=_next_plotly_key("result_chart"),
        )
        return

    if isinstance(result, pd.DataFrame):
        if result.empty:
            st.info("(Không có dữ liệu)")
        else:
            st.dataframe(result, use_container_width=True)
        return

    if isinstance(result, (list, tuple)):
        if not result:
            st.info("(Kết quả rỗng)")
            return
        for item in result:
            render_result(item)
        return

    if isinstance(result, str):
        st.markdown(result)
        return

    st.write(result)
