"""
Lightweight join planning for multi-dataset analysis.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import pandas as pd

from ai_datanalysis.core.normalization import normalize_query


JOIN_KEYWORDS = (
    "join",
    "merge",
    "ket hop",
    "lien ket",
    "noi bang",
    "ghep bang",
    "combine",
    "match",
)


@dataclass
class JoinHint:
    left_alias: str
    right_alias: str
    left_column: str
    right_column: str
    reason: str
    confidence: float


def _normalize_token(text: str) -> str:
    return normalize_query(str(text)).replace(" ", "_")


def _looks_like_key(column: str) -> bool:
    col = _normalize_token(column)
    return any(token in col for token in ("id", "code", "key", "uuid", "ma_", "customer", "user"))


def query_suggests_join(query: str) -> bool:
    normalized = normalize_query(query)
    return any(keyword in normalized for keyword in JOIN_KEYWORDS)


def _compatible_dtypes(left: pd.Series, right: pd.Series) -> bool:
    if pd.api.types.is_numeric_dtype(left.dtype) and pd.api.types.is_numeric_dtype(right.dtype):
        return True
    if pd.api.types.is_datetime64_any_dtype(left.dtype) and pd.api.types.is_datetime64_any_dtype(right.dtype):
        return True
    return left.dtype == right.dtype or left.dtype == object or right.dtype == object


def infer_join_hints(selected_data: Dict[str, pd.DataFrame]) -> List[JoinHint]:
    items = list(selected_data.items())
    hints: list[JoinHint] = []
    for left_idx in range(len(items)):
        left_name, left_df = items[left_idx]
        for right_idx in range(left_idx + 1, len(items)):
            right_name, right_df = items[right_idx]
            for left_col in left_df.columns:
                for right_col in right_df.columns:
                    left_token = _normalize_token(left_col)
                    right_token = _normalize_token(right_col)
                    if left_token != right_token:
                        continue
                    if not _compatible_dtypes(left_df[left_col], right_df[right_col]):
                        continue
                    confidence = 0.7
                    reason = "same normalized column name"
                    if _looks_like_key(left_col) or _looks_like_key(right_col):
                        confidence = 0.9
                        reason = "shared business key or id-like column"
                    hints.append(
                        JoinHint(
                            left_alias=left_name,
                            right_alias=right_name,
                            left_column=str(left_col),
                            right_column=str(right_col),
                            reason=reason,
                            confidence=confidence,
                        )
                    )
    hints.sort(key=lambda hint: hint.confidence, reverse=True)
    return hints[:5]


def build_join_context(selected_data: Dict[str, pd.DataFrame]) -> str:
    hints = infer_join_hints(selected_data)
    if not hints:
        return "No obvious join keys detected. Avoid joining unless the user explicitly requires it."

    lines = ["Potential join paths:"]
    for hint in hints:
        lines.append(
            f"- {hint.left_alias}.{hint.left_column} <-> {hint.right_alias}.{hint.right_column} "
            f"(confidence={hint.confidence:.1f}, reason={hint.reason})"
        )
    lines.append("Only join datasets when the analysis requires multiple tables.")
    return "\n".join(lines)
