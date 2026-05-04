"""
Intent and Graph Type Router.
Classifies query intent and selects the appropriate chart template.

Vietnamese vocabulary is centralized in vi_vocab.py.
"""
from __future__ import annotations

import re
from typing import List

from ai_datanalysis.core.normalization import normalize_query
from ai_datanalysis.core.vi_vocab import (
    VI_CHART_KEYWORDS,
    VI_FOLLOW_UP_KEYWORDS,
    VI_INTENT_KEYWORDS,
)

# ── Intent keywords ───────────────────────────────────────────────────
# VI_INTENT_KEYWORDS is the authoritative source; loaded directly.
INTENT_KEYWORDS: dict[str, list[str]] = VI_INTENT_KEYWORDS

# ── Explicit chart trigger words ──────────────────────────────────────
_CHART_TRIGGERS = (
    "bieu do", "do thi", "chart", "plot", "graph", "hinh",
    "ve ", "tao bieu do", "hien thi bieu do",
)

# ── Fallback keywords when chart trigger present but type unspecified ─
_CHART_FALLBACKS: list[tuple[str, list[str]]] = [
    ("line_plot",       ["duong", "trend", "bien thien", "xu huong", "thoi gian"]),
    ("bar_plot",        ["cot", "thanh", "so sanh", "nhom"]),
    ("scatter_2d_plot", ["phan tan", "diem", "point"]),
    ("area_plot",       ["mien", "vung", "area"]),
    ("pie_plot",        ["ty le", "ti le", "phan tram", "tron"]),
    ("histogram_plot",  ["tan suat", "phan phoi", "histogram"]),
]


def has_any(query: str, *keywords: str) -> bool:
    query_padded = f" {query} "
    return any(
        re.search(r"\b" + re.escape(k) + r"\b", query_padded)
        for k in keywords
    )


def analyze_intent(query: str) -> List[str]:
    """Return list of matched intents. Falls back to ['general']."""
    intents = {
        intent
        for intent, keywords in INTENT_KEYWORDS.items()
        if has_any(query, *keywords)
    }
    return list(intents) if intents else ["general"]


def infer_graph_type(normalized_query: str) -> str:
    """
    Return the template key based on the normalized query.
    Priority: specific chart keywords → fallback with chart trigger → auto_profile → table.
    """
    q = normalized_query

    is_explicit_chart = (
        any(trigger in q for trigger in _CHART_TRIGGERS)
        or has_any(q, "ve")
    )

    # 1. Specific chart type — iterate VI_CHART_KEYWORDS in priority order.
    #    "auto_profile" is skipped here and handled below.
    for chart_type, keywords in VI_CHART_KEYWORDS.items():
        if chart_type == "auto_profile":
            continue
        if has_any(q, *keywords):
            return chart_type

    # 2. Chart trigger present but type unclear → fallback heuristics.
    if is_explicit_chart:
        for chart_type, fallback_kws in _CHART_FALLBACKS:
            if has_any(q, *fallback_kws):
                return chart_type
        return "generic_plot"

    # 3. Profiling / exploration queries.
    if has_any(q, *VI_CHART_KEYWORDS["auto_profile"]):
        return "auto_profile"

    # 4. Default: return as table.
    return "table"


class RouterOutcome:
    def __init__(self, query: str):
        self.raw_query = query
        self.normalized_query = normalize_query(query)
        self.intents = analyze_intent(self.normalized_query)
        self.graph_type = infer_graph_type(self.normalized_query)
        self.is_follow_up = self._detect_follow_up()
        self.requires_multi_dataset = self._detect_multi_dataset_need()

    def _detect_follow_up(self) -> bool:
        return has_any(self.normalized_query, *VI_FOLLOW_UP_KEYWORDS)

    def _detect_multi_dataset_need(self) -> bool:
        return has_any(
            self.normalized_query,
            *INTENT_KEYWORDS.get("join", []),
        )

    def to_dict(self) -> dict:
        return {
            "normalized_query": self.normalized_query,
            "intents": self.intents,
            "graph_type": self.graph_type,
            "is_follow_up": self.is_follow_up,
            "requires_multi_dataset": self.requires_multi_dataset,
        }


def route_query(query: str) -> RouterOutcome:
    """Main entry point for routing a query."""
    return RouterOutcome(query)
