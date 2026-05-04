"""
Dataset selector with lightweight relevance and join-awareness scoring.
"""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

import pandas as pd

from ai_datanalysis.core.join_planner import query_suggests_join
from ai_datanalysis.core.normalization import normalize_query


def _tokenize(text: str) -> List[str]:
    if not isinstance(text, str):
        return []
    tokens = re.split(r"[\s_\-]+", text.lower())
    return [t for t in tokens if t]


def _normalized_columns(df: pd.DataFrame) -> set[str]:
    return {normalize_query(str(col)).replace(" ", "_") for col in df.columns}


def score_dataset(query: str, df_name: str, df: pd.DataFrame) -> float:
    query_tokens = set(_tokenize(query))
    if not query_tokens:
        return 0.0

    scores: list[float] = [0.0]

    name_tokens = _tokenize(df_name)
    name_overlap = query_tokens.intersection(name_tokens)
    scores.append(float(len(name_overlap) * 2.0))

    column_hits = 0
    id_hits = 0
    for col in df.columns:
        col_text = normalize_query(str(col))
        col_tokens = _tokenize(col_text)
        col_overlap = query_tokens.intersection(col_tokens)
        if col_overlap:
            column_hits += len(col_overlap)
            if any(tok in col_text for tok in ("id", "code", "key", "customer", "user")):
                id_hits += len(col_overlap)

    scores.append(float(column_hits))
    scores.append(float(id_hits * 0.5))
    return sum(scores)


def _relationship_bonus(df_a: pd.DataFrame, df_b: pd.DataFrame) -> float:
    common = _normalized_columns(df_a).intersection(_normalized_columns(df_b))
    if not common:
        return 0.0
    bonus = float(len(common))
    if any(token.endswith("id") or token.startswith("id") or "code" in token for token in common):
        bonus += 1.5
    return bonus


def select_datasets(
    query: str,
    data: Dict[str, pd.DataFrame],
    max_datasets: int = 2,
) -> Dict[str, pd.DataFrame]:
    if len(data) <= max_datasets:
        return data

    query_normalized = normalize_query(query)
    join_mode = query_suggests_join(query_normalized)

    scored: List[Tuple[float, str, pd.DataFrame]] = []
    for name, df in data.items():
        scored.append((score_dataset(query_normalized, name, df), name, df))

    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored:
        return {}

    primary_name, primary_df = scored[0][1], scored[0][2]
    selected: Dict[str, pd.DataFrame] = {primary_name: primary_df}

    if max_datasets <= 1:
        return selected

    secondary_candidates: list[Tuple[float, str, pd.DataFrame]] = []
    for base_score, name, df in scored[1:]:
        adjusted = base_score
        if join_mode:
            adjusted += _relationship_bonus(primary_df, df)
        secondary_candidates.append((adjusted, name, df))

    secondary_candidates.sort(key=lambda x: x[0], reverse=True)
    for adjusted, name, df in secondary_candidates[: max_datasets - 1]:
        if adjusted <= 0 and not join_mode:
            continue
        selected[name] = df

    return selected
