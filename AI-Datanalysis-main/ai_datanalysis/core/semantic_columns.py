"""
Generic semantic helpers for matching natural-language queries to dataset columns.
Vietnamese vocabulary is centralized in vi_vocab.py — edit there to add terms.
"""
from __future__ import annotations

import re
from typing import Iterable

from ai_datanalysis.core.normalization import normalize_query
from ai_datanalysis.core.vi_vocab import VI_TOKEN_SYNONYMS

# Domain-specific synonyms kept here (bike-share / weather dataset originals).
_BASE_TOKEN_SYNONYMS: dict[str, set[str]] = {
    "ride":       {"ride", "rides", "luot di", "chuyen di"},
    "registered": {"registered", "dang ky"},
    "casual":     {"casual", "vang lai"},
    "feels":      {"feels", "cam nhan"},
    "like":       {"like", "tuong tu"},
}

# Merge: VI_TOKEN_SYNONYMS is authoritative; _BASE adds domain-specific extras.
# For keys present in both, take the union of synonym sets.
TOKEN_SYNONYMS: dict[str, set[str]] = {**VI_TOKEN_SYNONYMS}
for _k, _v in _BASE_TOKEN_SYNONYMS.items():
    TOKEN_SYNONYMS[_k] = TOKEN_SYNONYMS.get(_k, set()) | _v

UNIT_HINTS = {
    "c": {"c", "do c", "celsius"},
    "pct": {"pct", "percent", "phan tram", "%"},
    "kmh": {"kmh", "km h", "km/h"},
}


def tokenize_identifier(text: str) -> list[str]:
    normalized = normalize_query(str(text)).replace("/", " ").replace("%", " pct ")
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return [token for token in normalized.split() if token]


def expand_tokens(tokens: Iterable[str]) -> set[str]:
    expanded: set[str] = set()
    for token in tokens:
        expanded.add(token)
        expanded.update(TOKEN_SYNONYMS.get(token, set()))
        expanded.update(UNIT_HINTS.get(token, set()))
    return expanded


def column_aliases(column_name: str) -> set[str]:
    tokens = tokenize_identifier(column_name)
    expanded = expand_tokens(tokens)
    aliases = set(expanded)
    if tokens:
        aliases.add(" ".join(tokens))
    if expanded:
        aliases.add(" ".join(sorted(t for t in expanded if " " not in t)))
    return {alias.strip() for alias in aliases if alias and len(alias.strip()) >= 2}


def score_query_to_column(query: str, column_name: str) -> float:
    query_tokens = expand_tokens(tokenize_identifier(query))
    column_tokens = expand_tokens(tokenize_identifier(column_name))
    if not column_tokens:
        return 0.0
    overlap = query_tokens.intersection(column_tokens)
    score = float(len(overlap))

    aliases = column_aliases(column_name)
    q_norm = normalize_query(query)
    for alias in aliases:
        if alias in q_norm:
            score += max(1.0, len(alias.split()) * 1.5)
    return score


def column_semantic_hint(column_name: str) -> str:
    tokens = tokenize_identifier(column_name)
    if not tokens:
        return ""
    human_label = " ".join(tokens)
    expansions = sorted(
        {
            phrase
            for token in tokens
            for phrase in TOKEN_SYNONYMS.get(token, set())
            if phrase != token
        }
    )
    if expansions:
        return f"{column_name} -> {human_label} / {', '.join(expansions[:4])}"
    return f"{column_name} -> {human_label}"
