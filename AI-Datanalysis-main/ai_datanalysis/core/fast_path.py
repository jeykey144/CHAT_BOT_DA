"""
Fast-path handlers for predictable single-dataset queries.
"""
from __future__ import annotations

import re
from typing import Dict, Optional

import pandas as pd

from ai_datanalysis.core.normalization import normalize_query
from ai_datanalysis.core.semantic_columns import score_query_to_column


_ID_COL_PATTERN = re.compile(r"(^|_)(id|code|key|ma|sbd)(_|$)")
_GROUP_AGGREGATION_CUES = (
    "theo",
    "theo tung",
    "tung",
    "moi",
    "group by",
    "by",
    "giua",
    "so sanh",
    "cao hon",
    "thap hon",
    "lon hon",
    "nho hon",
    "nao",
)


def _normalize_text(text: str) -> str:
    return str(text).strip().lower()


def _column_phrase(column_name: str) -> str:
    normalized = normalize_query(str(column_name)).replace("/", " ")
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _query_mentions_column(query: str, column_name: str) -> bool:
    phrase = _column_phrase(column_name)
    if not phrase:
        return False
    return bool(re.search(r"\b" + re.escape(phrase) + r"\b", query))


def _query_references_column(query: str, column_name: str) -> bool:
    return _query_mentions_column(query, column_name) or score_query_to_column(query, column_name) > 0


def _resolve_metric_column(query: str, df: pd.DataFrame) -> Optional[str]:
    q = _normalize_text(query)
    best_col = None
    best_score = 0.0

    for col in df.columns:
        if not pd.api.types.is_numeric_dtype(df[col]):
            continue
        score = score_query_to_column(q, str(col))
        if _query_mentions_column(q, str(col)):
            score += 5.0
        if score > best_score:
            best_score = score
            best_col = str(col)

    if best_col and best_score > 0:
        return best_col

    numeric_cols = [str(col) for col in df.columns if pd.api.types.is_numeric_dtype(df[col])]
    if len(numeric_cols) == 1:
        return numeric_cols[0]
    return None


def _resolve_group_column(query: str, df: pd.DataFrame) -> Optional[str]:
    q = _normalize_text(query)
    best_col = None
    best_score = 0.0

    for col in df.columns:
        series = df[col]
        if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
            continue
        score = score_query_to_column(q, str(col))
        unique_count = int(series.nunique(dropna=True))
        if 2 <= unique_count <= 20:
            score += 0.5
        elif unique_count == 1:
            score -= 1.0
        if score > best_score:
            best_score = score
            best_col = str(col)

    if best_col and best_score > 0:
        return best_col
    return None


def _explicit_group_values(query: str, df: pd.DataFrame, group_col: str) -> list[str]:
    matched_values: list[str] = []
    series = df[group_col].dropna()
    for value in series.unique():
        value_text = str(value).strip()
        if not value_text:
            continue
        value_norm = normalize_query(value_text)
        if value_norm and re.search(r"\b" + re.escape(value_norm) + r"\b", query):
            matched_values.append(value_text)
    return matched_values


def _grouped_aggregate_code(query: str, df: pd.DataFrame, metric_col: str) -> Optional[str]:
    q = _normalize_text(query)
    group_col = _resolve_group_column(q, df)
    if not group_col:
        return None

    if not _query_references_column(q, group_col):
        return None

    if not _contains_any(q, *_GROUP_AGGREGATION_CUES):
        return None

    if _contains_any(q, "trung binh", "average", "mean"):
        agg_method = "mean"
        value_col = f"{metric_col}_mean"
    elif _contains_any(q, "tong", "sum", "total"):
        agg_method = "sum"
        value_col = f"{metric_col}_sum"
    else:
        return None

    values = _explicit_group_values(q, df, group_col)
    filter_code = ""
    if values:
        filter_code = (
            f"allowed = {[str(value) for value in values]!r}\n"
            f"df = df[df[{group_col!r}].astype(str).isin(allowed)]\n"
        )

    ascending = "True" if _contains_any(q, "thap hon", "thap nhat", "nho hon", "nho nhat", "min", "lowest") else "False"
    sort_code = ""
    if _contains_any(
        q,
        "cao hon",
        "cao nhat",
        "lon hon",
        "lon nhat",
        "thap hon",
        "thap nhat",
        "nho hon",
        "nho nhat",
        "max",
        "min",
        "highest",
        "lowest",
        "so sanh",
        "giua",
    ):
        sort_code = f"result = result.sort_values({value_col!r}, ascending={ascending}).reset_index(drop=True)\n"

    return (
        "df = DF_1.copy()\n"
        f"df[{metric_col!r}] = pd.to_numeric(df[{metric_col!r}], errors='coerce')\n"
        f"df = df.dropna(subset=[{group_col!r}, {metric_col!r}])\n"
        f"{filter_code}"
        f"result = df.groupby({group_col!r}, as_index=False)[{metric_col!r}].{agg_method}()"
        f".rename(columns={{{metric_col!r}: {value_col!r}}})\n"
        f"{sort_code}"
    ).rstrip()


def _resolve_id_like_column(query: str, df: pd.DataFrame) -> Optional[str]:
    q = _normalize_text(query)
    best_col = None
    best_score = 0.0

    for col in df.columns:
        col_name = str(col)
        col_lower = col_name.lower()
        if not _ID_COL_PATTERN.search(col_lower):
            continue
        score = score_query_to_column(q, col_name)
        if "order" in q and "order" in col_lower:
            score += 2.0
        if score > best_score:
            best_score = score
            best_col = col_name

    if best_col and best_score > 0:
        return best_col
    return None


def _histogram_code(query: str, df: pd.DataFrame) -> Optional[str]:
    q = _normalize_text(query)
    if not _contains_any(
        q,
        "histogram",
        "phan phoi",
        "tan suat",
        "distribution",
    ):
        return None

    if _contains_any(
        q,
        "theo tung",
        "theo nhom",
        "cho tung",
        "group by",
        "moi nhom",
        "moi kenh",
        "stack",
        "overlay",
        "phan loai theo",
    ):
        return None

    metric_col = _resolve_metric_column(q, df)
    if not metric_col:
        return None

    title = f"Phan phoi cua bien {metric_col}"
    x_title = f"Gia tri {metric_col}"
    return (
        "df = DF_1.copy()\n"
        f"df[{metric_col!r}] = pd.to_numeric(df[{metric_col!r}], errors='coerce')\n"
        f"df = df.dropna(subset=[{metric_col!r}])\n"
        f"fig = px.histogram(df, x={metric_col!r}, nbins=30)\n"
        "fig.update_traces(marker=dict(line=dict(width=1, color='rgba(255,255,255,0.35)')))\n"
        "fig.update_layout(\n"
        f"    title={title!r},\n"
        f"    xaxis_title={x_title!r},\n"
        "    yaxis_title='So luong quan sat',\n"
        "    width=900,\n"
        "    height=600,\n"
        "    margin=dict(l=40, r=40, t=65, b=65),\n"
        "    title_font_size=20,\n"
        ")\n"
        "result = fig"
    )


def _pie_count_code(query: str, df: pd.DataFrame) -> Optional[str]:
    q = _normalize_text(query)
    if not _contains_any(
        q,
        "pie chart",
        "pie plot",
        "bieu do tron",
        "do thi tron",
        "bieu do ty le",
        "ty le",
        "ti le",
        "ty trong",
        "phan tram",
        "co cau",
        "dong gop",
    ):
        return None

    if not _contains_any(
        q,
        "don hang",
        "order",
        "order_id",
        "count",
        "dem",
        "so luong",
        "so don",
        "record",
        "ban ghi",
    ):
        return None

    group_col = _resolve_group_column(q, df)
    if not group_col:
        return None

    count_col = _resolve_id_like_column(q, df)
    value_col = "group_count"
    agg_code = (
        f"agg = df.groupby({group_col!r}, dropna=False).size().reset_index(name={value_col!r})"
    )
    if count_col:
        value_col = f"{count_col}_count"
        agg_code = (
            f"agg = df.dropna(subset=[{group_col!r}]).groupby({group_col!r}, as_index=False)[{count_col!r}]"
            f".nunique().rename(columns={{{count_col!r}: {value_col!r}}})"
        )

    title = f"Ty trong theo {group_col.replace('_', ' ')}"
    return (
        "df = DF_1.copy()\n"
        f"{agg_code}\n"
        f"agg = agg[agg[{value_col!r}] > 0]\n"
        f"fig = px.pie(agg, names={group_col!r}, values={value_col!r}, hole=0)\n"
        "fig.update_traces(textposition='inside', textinfo='percent+label')\n"
        "fig.update_layout(\n"
        f"    title={title!r},\n"
        "    width=900,\n"
        "    height=600,\n"
        "    margin=dict(l=40, r=40, t=65, b=65),\n"
        "    title_font_size=20,\n"
        ")\n"
        "result = fig"
    )


def _contains_any(text: str, *phrases: str) -> bool:
    text_padded = f" {text} "
    return any(re.search(r"\b" + re.escape(phrase) + r"\b", text_padded) for phrase in phrases)


def _extreme_labels(query: str, column: str) -> tuple[str, str]:
    q = _normalize_text(query)
    if _contains_any(q, "nhiet do", "temperature", "temp"):
        return ("Nhiệt độ thấp nhất", "Nhiệt độ cao nhất")
    nice = column.replace("_", " ").title()
    return (f"{nice} thấp nhất", f"{nice} cao nhất")


def _auto_profile_code() -> str:
    return """
import re as _re

df = DF_1.copy()
_row_count, _col_count = df.shape
_total_cells = max(_row_count * _col_count, 1)
_missing_total = int(df.isna().sum().sum())
_duplicate_count = int(df.duplicated().sum())
_ID_PAT = _re.compile(r'(^|_)(id|code|key|ma|sbd)(_|$)')
_DT_PAT = _re.compile(r'(^|_)(date|time|year|month|quarter|week|day|ngay|thang|nam|quy)(_|$)')


def _safe_ratio(_numerator, _denominator):
    return float(_numerator) / float(_denominator) if _denominator else 0.0


def _format_value(_value):
    if pd.isna(_value):
        return "NA"
    try:
        _text = str(_value.isoformat())
        return _text.replace("T", " ")
    except Exception:
        pass
    try:
        _value = _value.item()
    except Exception:
        pass
    if isinstance(_value, bool):
        return str(_value)
    if isinstance(_value, int):
        return f"{_value:,}"
    if isinstance(_value, float):
        if _value.is_integer():
            return f"{int(_value):,}"
        return f"{_value:,.3f}".rstrip("0").rstrip(".")
    _text = str(_value).replace("\\n", " ").strip()
    if len(_text) > 36:
        return _text[:33] + "..."
    return _text


def _format_column_list(_cols, _limit=8):
    _names = [str(_col) for _col in _cols]
    if not _names:
        return "Không có"
    if len(_names) <= _limit:
        return ", ".join(_names)
    return ", ".join(_names[:_limit]) + f", ... (+{len(_names) - _limit})"

_summary_rows = []
_id_cols, _dt_cols, _num_cols, _cat_cols = [], [], [], []
_missing_cols = []
_missing_stats = []
_time_ranges = []
_numeric_ranges = []
_categorical_levels = []

for _col in df.columns:
    _series = df[_col]
    _col_name = str(_col)
    _name = _col_name.strip().lower()
    _non_null = _series.dropna()
    _missing_count = int(_series.isna().sum())
    _missing_ratio = _safe_ratio(_missing_count, _row_count or 1)
    _unique_count = int(_series.nunique(dropna=True))
    _unique_ratio = _safe_ratio(_unique_count, len(_non_null))
    _group = "categorical"

    if pd.api.types.is_datetime64_any_dtype(_series) or _DT_PAT.search(_name):
        _group = "datetime"
    elif _ID_PAT.search(_name):
        _group = "id"
    elif pd.api.types.is_integer_dtype(_series) and len(_non_null) > 0:
        _avg_len = float(_non_null.astype(str).str.len().mean())
        if _unique_count == len(_non_null) and _avg_len >= 6:
            _group = "id"
        else:
            _group = "numeric"
    elif pd.api.types.is_numeric_dtype(_series):
        _group = "numeric"
    elif len(_non_null) > 0:
        _avg_len = float(_non_null.astype(str).str.len().mean())
        if _unique_ratio >= 0.98 and _avg_len >= 6:
            _group = "id"

    if _group == "id":
        _id_cols.append(_col)
    elif _group == "datetime":
        _dt_cols.append(_col)
    elif _group == "numeric":
        _num_cols.append(_col)
    else:
        _cat_cols.append(_col)

    if _missing_count > 0:
        _missing_cols.append(_col_name)
        _missing_stats.append((_col_name, _missing_count, _missing_ratio))

    _mean_value = float("nan")
    _min_value = float("nan")
    _max_value = float("nan")

    if _group == "numeric":
        _numeric = pd.to_numeric(_series, errors="coerce").dropna()
        if not _numeric.empty:
            _mean_value = float(_numeric.mean())
            _min_value = float(_numeric.min())
            _max_value = float(_numeric.max())
            _numeric_ranges.append(f"{_col_name}: {_format_value(_min_value)} -> {_format_value(_max_value)}")
    elif _group == "datetime":
        if pd.api.types.is_numeric_dtype(_series):
            _time_numeric = pd.to_numeric(_series, errors="coerce").dropna()
            if not _time_numeric.empty:
                _time_ranges.append(
                    f"{_col_name}: {_format_value(float(_time_numeric.min()))} -> {_format_value(float(_time_numeric.max()))}"
                )
        else:
            _parsed = pd.to_datetime(_series, errors="coerce").dropna()
            if not _parsed.empty:
                _min_text = _format_value(_parsed.min())
                _max_text = _format_value(_parsed.max())
                _time_ranges.append(f"{_col_name}: {_min_text} -> {_max_text}")
    elif _group == "categorical":
        _categorical_levels.append((_col_name, _unique_count))

    _summary_rows.append({
        "Cột": _col_name,
        "Kiểu dữ liệu": str(_series.dtype),
        "Trung bình": round(_mean_value, 4) if not pd.isna(_mean_value) else _mean_value,
        "Max": round(_max_value, 4) if not pd.isna(_max_value) else _max_value,
        "Min": round(_min_value, 4) if not pd.isna(_min_value) else _min_value,
        "Số giá trị thiếu": _missing_count,
        "Tỷ lệ thiếu (%)": round(_missing_ratio * 100, 2),
    })

summary_df = pd.DataFrame(
    _summary_rows,
    columns=["Cột", "Kiểu dữ liệu", "Trung bình", "Max", "Min", "Số giá trị thiếu", "Tỷ lệ thiếu (%)"],
)

_missing_stats = sorted(_missing_stats, key=lambda _item: (_item[1], _item[2]), reverse=True)
_categorical_levels = sorted(_categorical_levels, key=lambda _item: (_item[1], _item[0]), reverse=True)

_insights = [
    "## Tổng quan dữ liệu",
    f"- Số dòng: {_row_count:,}",
    f"- Số cột: {_col_count}",
    f"- Tổng số ô dữ liệu: {_row_count * _col_count:,}",
    f"- Ô thiếu dữ liệu: {_missing_total:,} ({_safe_ratio(_missing_total, _total_cells):.1%})",
    f"- Dòng trùng lặp hoàn toàn: {_duplicate_count:,} ({_safe_ratio(_duplicate_count, _row_count or 1):.1%})",
    "",
    "## Cấu trúc tập dữ liệu",
    f"- Cột số ({len(_num_cols)}): {_format_column_list(_num_cols)}",
    f"- Cột phân loại ({len(_cat_cols)}): {_format_column_list(_cat_cols)}",
    f"- Cột thời gian ({len(_dt_cols)}): {_format_column_list(_dt_cols)}",
    f"- Cột mã định danh ({len(_id_cols)}): {_format_column_list(_id_cols)}",
]
if _time_ranges:
    _insights.append("- Khoảng thời gian nhận diện: " + " | ".join(_time_ranges[:3]) + ".")
if _numeric_ranges:
    _insights.append("- Biên độ các cột số chính: " + " | ".join(_numeric_ranges[:3]) + ".")
if _categorical_levels:
    _top_category_parts = []
    for _name, _levels in _categorical_levels[:3]:
        _top_category_parts.append(f"{_name} ({_levels} nhóm)")
    _insights.append(
        "- Cột phân loại có nhiều nhóm nhất: "
        + " | ".join(_top_category_parts)
        + "."
    )

_insights.extend([
    "",
    "## Chất lượng dữ liệu",
    f"- Tỷ lệ thiếu toàn bảng: {_safe_ratio(_missing_total, _total_cells):.1%}",
    f"- Cột có thiếu dữ liệu: {len(_missing_cols)} / {_col_count}",
])
if _missing_cols:
    _insights.append("- Cột có giá trị thiếu: " + ", ".join(_missing_cols) + ".")
    _top_missing_parts = []
    for _name, _count, _ratio in _missing_stats[:5]:
        _top_missing_parts.append(f"{_name} ({_count:,} giá trị, {_ratio:.1%})")
    _insights.append(
        "- Thiếu nhiều nhất: "
        + " | ".join(_top_missing_parts)
        + "."
    )
else:
    _insights.append("- Không phát hiện giá trị thiếu.")

_insights.extend([
    "",
    "## Cách đọc nhanh bộ dữ liệu",
    "- Xem bảng chi tiết bên trên để biết từng cột thuộc nhóm nào, ví dụ giá trị ra sao, và nên dùng cho loại phân tích nào.",
])
if _id_cols:
    _insights.append("- Cột mã định danh phù hợp để join hoặc tra cứu hồ sơ, không dùng làm thước đo trung tâm.")
if _dt_cols and _num_cols:
    _insights.append("- Bộ dữ liệu đã có cột thời gian và cột số: phù hợp cho phân tích xu hướng, tăng giảm theo kỳ.")
if _cat_cols and _num_cols:
    _insights.append("- Có thể so sánh các cột số theo từng nhóm phân loại để tìm khác biệt giữa các phân khúc.")
if _cat_cols and not _num_cols:
    _insights.append("- Bộ dữ liệu thiên về phân loại: nên ưu tiên đếm tần suất, tỷ trọng và tìm nhóm nổi bật.")

insights_text = "\\n".join(_insights)
result = (summary_df, insights_text)
""".strip()


def try_fast_path(normalized_query: str, data: Dict[str, pd.DataFrame], graph_type: str = "") -> Optional[str]:
    """
    Return static Python code for highly predictable requests.
    """
    q = _normalize_text(normalized_query)

    if len(data) != 1:
        return None

    df = list(data.values())[0]

    if graph_type == "auto_profile" or _contains_any(
        q,
        "phan tich", "kham pha", "tong quan", "explore", "profile", "insight",
        "mo ta du lieu", "thong ke tong quat", "bao cao tong hop",
        "kiem tra du lieu", "bao cao tu dong", "nhin tong quan",
    ):
        return _auto_profile_code()

    if graph_type == "pie_plot":
        pie_code = _pie_count_code(q, df)
        if pie_code:
            return pie_code

    if graph_type == "histogram_plot":
        histogram_code = _histogram_code(q, df)
        if histogram_code:
            return histogram_code

    if _contains_any(q, "bieu do", "chart", "plot", "do thi"):
        return None

    metric_col = _resolve_metric_column(q, df)
    if metric_col:
        grouped_code = _grouped_aggregate_code(q, df, metric_col)
        if grouped_code:
            return grouped_code

    if _contains_any(q, "theo", "by", "tung", "moi", "group by"):
        return None

    which_category = (
        "mon nao",
        "mon thi nao",
        "mon hoc nao",
        "nhom nao",
        "cot nao",
        "loai nao",
        "danh muc nao",
        "san pham nao",
        "khu vuc nao",
        "nhan vien nao",
        "khach hang nao",
    )
    if _contains_any(q, *which_category):
        return None

    if _contains_any(q, "mon thi", "mon hoc") and _contains_any(
        q, "cao nhat", "thap nhat", "lon nhat", "nho nhat", "max", "min"
    ):
        return None

    if q in ("dem", "so dong", "tong so dong", "count rows", "count"):
        return "result = f'Tổng số dòng trong dữ liệu là: {len(DF_1)}'"

    top_match = re.search(r"^top (\d+)$", q)
    if top_match:
        n = int(top_match.group(1))
        return f"result = DF_1.head({n})"

    if q in ("shape", "kich thuoc", "info", "thong tin"):
        return "result = f'Dataset có {DF_1.shape[0]} dòng và {DF_1.shape[1]} cột.'"

    if metric_col:
        if _contains_any(q, "thap nhat va", "cao nhat va", "minimum and maximum", "min and max"):
            low_label, high_label = _extreme_labels(q, metric_col)
            return (
                f"series = pd.to_numeric(DF_1[{metric_col!r}], errors='coerce').dropna()\n"
                "result = pd.DataFrame([\n"
                "    {\n"
                f"        {low_label!r}: float(series.min()),\n"
                f"        {high_label!r}: float(series.max()),\n"
                "    }\n"
                "])"
            )

        if _contains_any(q, "thap nhat", "nho nhat", "minimum", "min"):
            return (
                f"series = pd.to_numeric(DF_1[{metric_col!r}], errors='coerce').dropna()\n"
                f"result = pd.DataFrame([{{{metric_col!r}: float(series.min())}}])"
            )

        if _contains_any(q, "cao nhat", "lon nhat", "maximum", "max"):
            return (
                f"series = pd.to_numeric(DF_1[{metric_col!r}], errors='coerce').dropna()\n"
                f"result = pd.DataFrame([{{{metric_col!r}: float(series.max())}}])"
            )

        if _contains_any(q, "trung binh", "average", "mean"):
            return (
                f"series = pd.to_numeric(DF_1[{metric_col!r}], errors='coerce').dropna()\n"
                f"result = pd.DataFrame([{{{metric_col!r}: float(series.mean())}}])"
            )

        if _contains_any(q, "tong", "sum", "total"):
            return (
                f"series = pd.to_numeric(DF_1[{metric_col!r}], errors='coerce').dropna()\n"
                f"result = pd.DataFrame([{{{metric_col!r}: float(series.sum())}}])"
            )

    return None
