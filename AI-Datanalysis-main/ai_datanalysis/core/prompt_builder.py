"""
Semantic Prompt Builder
Replaces the old verbose prompt building logic.
Uses semantic column categorization to save tokens and improve LLM understanding.
"""
import re as _re
from typing import Dict

import pandas as pd

from ai_datanalysis.core.join_planner import build_join_context
from ai_datanalysis.core.router import route_query
from ai_datanalysis.core.semantic_columns import column_semantic_hint
from ai_datanalysis.core.selector import select_datasets
from ai_datanalysis.paths import CHART_TEMPLATES_DIR

_ID_COL_PATTERN = _re.compile(r'(^|_)id$|^id(_|$)|(^|_)code$|^code(_|$)|(^|_)key$|^key(_|$)')


def _templates_base() -> Dict[str, str]:
    return {
        "line_plot": str(CHART_TEMPLATES_DIR / "line_plot.txt"),
        "bar_plot": str(CHART_TEMPLATES_DIR / "bar_plot.txt"),
        "scatter_2d_plot": str(CHART_TEMPLATES_DIR / "scatter_2d_plot.txt"),
        "histogram_plot": str(CHART_TEMPLATES_DIR / "histogram_plot.txt"),
        "box_plot": str(CHART_TEMPLATES_DIR / "box_plot.txt"),
        "violin_plot": str(CHART_TEMPLATES_DIR / "violin_plot.txt"),
        "heatmap": str(CHART_TEMPLATES_DIR / "heatmap.txt"),
        "pie_plot": str(CHART_TEMPLATES_DIR / "pie_plot.txt"),
        "area_plot": str(CHART_TEMPLATES_DIR / "area_plot.txt"),
        "table": str(CHART_TEMPLATES_DIR / "table.txt"),
        "table_plotly": str(CHART_TEMPLATES_DIR / "table_plotly.txt"),
        "bubble_plot": str(CHART_TEMPLATES_DIR / "bubble_plot.txt"),
        "candle_plot": str(CHART_TEMPLATES_DIR / "candle_plot.txt"),
        "density_contour_plot": str(CHART_TEMPLATES_DIR / "density_contour_plot.txt"),
        "polar_plot": str(CHART_TEMPLATES_DIR / "polar_plot.txt"),
        "sunburst_plot": str(CHART_TEMPLATES_DIR / "sunburst_plot.txt"),
        "treemap_plot": str(CHART_TEMPLATES_DIR / "treemap_plot.txt"),
        "generic_plot": str(CHART_TEMPLATES_DIR / "generic_plot.txt"),
        "auto_profile": str(CHART_TEMPLATES_DIR / "auto_profile.txt"),
    }


def _read_template(template_path: str) -> str:
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def _is_id_col_name(c_str: str) -> bool:
    """True only when the column name IS an ID/code/key, not merely contains those letters."""
    return bool(_ID_COL_PATTERN.search(c_str))


def _semantic_schema_summary(df: pd.DataFrame) -> str:
    """
    Group columns into semantic categories for the LLM prompt:
    numeric, categorical, datetime, id-like.
    Uses word-boundary ID detection to avoid false positives on names like
    'unit_price_usd', 'discount_rate', etc.
    """
    numeric_cols = []
    categorical_cols = []
    datetime_cols = []
    id_cols = []

    for c in df.columns:
        dt = df[c].dtype
        c_str = str(c).lower()
        unique_ratio = (df[c].nunique(dropna=True) / len(df)) if len(df) else 0.0

        if pd.api.types.is_datetime64_any_dtype(dt) or 'date' in c_str or 'time' in c_str:
            datetime_cols.append(c)
        elif pd.api.types.is_numeric_dtype(dt):
            # ID: name matches pattern, OR integer col with very long string representation
            if _is_id_col_name(c_str) \
               or (not pd.api.types.is_float_dtype(dt)
                   and df[c].dropna().astype(str).str.len().mean() > 10):
                id_cols.append(c)
            else:
                numeric_cols.append(c)
        else:
            avg_len = df[c].dropna().astype(str).str.len().mean() if df[c].notna().any() else 0
            if _is_id_col_name(c_str) or (unique_ratio >= 0.98 and avg_len >= 6):
                id_cols.append(c)
            else:
                categorical_cols.append(c)

    summary = f"shape={df.shape}\n"
    summary += f"missing_values_total={int(df.isna().sum().sum())}\n"
    if numeric_cols:
        summary += f"numeric_cols={numeric_cols}\n"
    if categorical_cols:
        summary += f"categorical_cols={categorical_cols}\n"
    if datetime_cols:
        summary += f"datetime_like_cols={datetime_cols}\n"
    if id_cols:
        summary += f"id_cols={id_cols}\n"

    return summary


def _column_semantic_hints(df: pd.DataFrame) -> str:
    hints: list[str] = []
    for col in list(df.columns)[:20]:
        hint = column_semantic_hint(str(col))
        if hint:
            hints.append(hint)
    if not hints:
        return ""
    return "semantic_column_hints=\n- " + "\n- ".join(hints) + "\n"


def build_prompt(
    question: str,
    data: Dict[str, pd.DataFrame],
    selected_data: Dict[str, pd.DataFrame] | None = None,
    history: list = None,
    language: str = "vi",
    privacy: bool = True,
    sample_rows: int = 5,
    analysis_context: str = "",
) -> str:
    """
    Main prompt entrypoint.
    1. Route intent and graph type.
    2. Select dataset.
    3. Generate semantic summary and limited samples.
    4. Compile prompt.
    """
    router_out = route_query(question)
    graph_type = router_out.graph_type
    selected_data = selected_data or select_datasets(question, data, max_datasets=2)
    template = _read_template(_templates_base().get(graph_type, ""))

    blocks = []
    for i, (name, df) in enumerate(selected_data.items(), start=1):
        blocks.append(f"### Dataset: {name}")
        blocks.append(f"Alias in code: DF_{i}")
        blocks.append(_semantic_schema_summary(df))
        hint_text = _column_semantic_hints(df)
        if hint_text:
            blocks.append(hint_text)

        n = max(0, min(sample_rows, 10))
        if privacy:
            n = 0

        if n > 0:
            blocks.append("sample_head:")
            blocks.append("(first rows for structure inference only)")
            try:
                blocks.append(df.head(n).to_markdown(index=False))
            except Exception:
                blocks.append(df.head(n).to_csv(index=False))

        numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        # Skip this hint for histogram/distribution plots — it causes the LLM to
        # compute means across columns and histogram those aggregates instead of
        # plotting the raw row-level distribution of a single column.
        _distribution_types = {"histogram_plot", "box_plot", "violin_plot", "density_contour_plot"}
        if len(numeric_cols) > 1 and graph_type not in _distribution_types:
            blocks.append(f"table_layout_hint: This table has {len(numeric_cols)} numeric columns ({', '.join(str(c) for c in numeric_cols[:10])}{'...' if len(numeric_cols) > 10 else ''}). If these columns represent different categories/subjects/months, compute metric ACROSS columns (e.g. df[cols].mean()), NOT groupby on a string column.")

        blocks.append("")

    data_prompt = "\n".join(blocks)
    join_context = build_join_context(selected_data)

    history_text = ""
    # ONLY INCLUDE HISTORY IF IT'S A FOLLOW UP
    if history and router_out.is_follow_up:
        history_text = "Chat History (recent context):\n"
        for msg in history[-3:]:
            role = "USER" if msg["role"] == "user" else "ASSISTANT"
            history_text += f"[{role}]: {msg['content']}\n"
        history_text += "\n"

    instruction = f"""
You are an expert data analyst and Python engineer.

You must write VALID python code (no markdown fences) that uses: pandas, numpy, plotly.graph_objects.

Datasets are pre-loaded. Use the aliases assigned (e.g., DF_1).

Rules:
1) NEVER call fig.show().
2) Assign final output to `result`. Chart -> Plotly Figure, Table -> pandas DataFrame, Text -> string.
3) Use the exact column names specified in the metadata.
4) Do NOT output markdown fences like ```python. ONLY raw code.
5) IF THERE IS CHAT HISTORY: Use it to understand context (e.g. "change color to red" applies to the previous chart).
6) Only join datasets when the metadata explicitly shows a reliable relationship, or when a system-prepared master table is available.
7) NEVER call pd.read_csv, pd.read_excel, open(), or load any local/remote file. You must use only DF_1, DF_2, DF_3... already provided.
8) Your code MUST be syntactically valid Python.
9) Never leave string literals unterminated.
10) Do not place raw line breaks inside single-quoted or double-quoted strings. Use triple quotes or \\n when needed.
11) If datasets are unrelated, analyze them separately and never mix metrics across tables.
12) If a master table is provided by the system, prefer it for combined reporting instead of rebuilding a merge.
13) Return the SHORTEST complete Python solution that satisfies the request.
14) Do NOT include explanations, prose, comments, or reasoning blocks such as <think>...</think>.
15) Avoid unnecessary intermediate variables, repeated conversions, or extra formatting work.

Answer language for text explanation: {language}

{history_text}User question (CURRENT TASK):
{question}

Dataset metadata:
{data_prompt}

Join guidance:
{join_context}

Analysis constraints:
{analysis_context or "No extra analysis constraints."}

Extra rules for requested type:
{template}
""".strip()

    return instruction
