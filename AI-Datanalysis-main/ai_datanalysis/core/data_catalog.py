"""
Dataset cataloging and relationship detection for multi-table analysis.
"""
from __future__ import annotations

from collections import OrderedDict
from itertools import combinations
from typing import Dict, Iterable, List, Tuple

import pandas as pd

from ai_datanalysis.core.normalization import normalize_query


GENERIC_KEY_TOKENS = {
    "id",
    "ids",
    "code",
    "key",
    "uuid",
    "pk",
    "fk",
    "ma",
}
ID_LIKE_TOKENS = GENERIC_KEY_TOKENS.union(
    {
        "customer",
        "client",
        "user",
        "account",
        "order",
        "invoice",
        "product",
        "item",
        "employee",
        "student",
        "member",
        "branch",
        "region",
        "store",
        "sku",
    }
)
MASTER_TABLE_CONFIDENCE = 0.78
MIN_RELATIONSHIP_CONFIDENCE = 0.55
COMBINED_VIEW_KEYWORDS = (
    "dashboard",
    "bao cao",
    "report",
    "tong quan",
    "overview",
    "phan tich",
    "insight",
    "join",
    "merge",
    "ket hop",
    "ghep",
    "lien ket",
    "so sanh",
)


def _normalize_name(name: str) -> str:
    return normalize_query(str(name)).replace(" ", "_")


def _tokenize_name(name: str) -> list[str]:
    return [token for token in _normalize_name(name).split("_") if token]


def _meaningful_tokens(name: str) -> set[str]:
    return {token for token in _tokenize_name(name) if token not in GENERIC_KEY_TOKENS}


def _is_id_like_column(name: str) -> bool:
    tokens = set(_tokenize_name(name))
    return bool(tokens.intersection(ID_LIKE_TOKENS))


def _safe_ratio(numerator: float, denominator: float) -> float:
    if not denominator:
        return 0.0
    return float(numerator) / float(denominator)


def _standardize_key_series(series: pd.Series) -> pd.Series:
    values = series.copy()
    if pd.api.types.is_datetime64_any_dtype(values):
        dt = pd.to_datetime(values, errors="coerce")
        return dt.dt.strftime("%Y-%m-%d %H:%M:%S")

    if pd.api.types.is_numeric_dtype(values):
        numeric = pd.to_numeric(values, errors="coerce")
        standardized = numeric.map(lambda v: None if pd.isna(v) else f"{float(v):.12g}")
        return standardized.astype("object")

    cleaned = values.astype("string").str.strip().str.lower()
    cleaned = cleaned.mask(cleaned.isin({"", "nan", "none", "<na>"}))
    return cleaned.astype("object")


def _uniqueness_ratio(series: pd.Series) -> float:
    normalized = _standardize_key_series(series).dropna()
    if normalized.empty:
        return 0.0
    return _safe_ratio(normalized.nunique(dropna=True), len(normalized))


def _candidate_keys(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    primary_keys: list[str] = []
    candidate_keys: list[str] = []

    for col in df.columns:
        col_name = str(col)
        series = df[col]
        non_null = int(series.notna().sum())
        if non_null < max(2, min(len(df), 5)):
            continue

        uniqueness = _uniqueness_ratio(series)
        missing_ratio = 1.0 - _safe_ratio(non_null, len(df) or 1)
        col_norm = _normalize_name(col_name)
        id_like = _is_id_like_column(col_name)
        is_datetime = pd.api.types.is_datetime64_any_dtype(series) or any(
            token in col_norm for token in ("date", "time", "month", "year", "day", "week")
        )
        is_numeric = pd.api.types.is_numeric_dtype(series)
        avg_len = series.dropna().astype(str).str.len().mean() if series.notna().any() else 0.0

        if is_datetime:
            continue

        if id_like and uniqueness >= 0.98 and missing_ratio <= 0.05:
            primary_keys.append(col_name)
            continue

        if not is_numeric and uniqueness >= 0.98 and missing_ratio <= 0.02 and avg_len >= 6:
            primary_keys.append(col_name)
            continue

        if id_like and uniqueness >= 0.45:
            candidate_keys.append(col_name)
            continue

        if not is_numeric and uniqueness >= 0.85 and avg_len >= 6:
            candidate_keys.append(col_name)

    ordered_candidates = [col for col in candidate_keys if col not in primary_keys]
    return primary_keys, primary_keys + ordered_candidates


def _dataset_summary(name: str, df: pd.DataFrame) -> dict:
    primary_keys, candidate_keys = _candidate_keys(df)
    time_cols: list[str] = []
    numeric_cols: list[str] = []
    categorical_cols: list[str] = []

    for col in df.columns:
        col_name = str(col)
        series = df[col]
        col_norm = _normalize_name(col_name)
        if pd.api.types.is_datetime64_any_dtype(series) or any(
            token in col_norm for token in ("date", "time", "month", "year", "day", "week")
        ):
            time_cols.append(col_name)
        elif pd.api.types.is_numeric_dtype(series):
            numeric_cols.append(col_name)
        else:
            categorical_cols.append(col_name)

    duplicate_ratio = _safe_ratio(int(df.duplicated().sum()), len(df) or 1)
    missing_ratio = _safe_ratio(float(df.isna().sum().sum()), max(int(df.shape[0] * max(df.shape[1], 1)), 1))

    return {
        "name": name,
        "rows": int(df.shape[0]),
        "cols": int(df.shape[1]),
        "primary_keys": primary_keys,
        "candidate_keys": candidate_keys,
        "time_cols": time_cols,
        "numeric_cols": numeric_cols,
        "categorical_cols": categorical_cols,
        "duplicate_ratio": round(duplicate_ratio, 4),
        "missing_ratio": round(missing_ratio, 4),
    }


def _column_name_match(left_col: str, right_col: str) -> tuple[bool, bool]:
    left_norm = _normalize_name(left_col)
    right_norm = _normalize_name(right_col)
    if left_norm == right_norm:
        return True, True

    left_tokens = _meaningful_tokens(left_col)
    right_tokens = _meaningful_tokens(right_col)
    if left_tokens and left_tokens == right_tokens:
        return True, False
    return False, False


def _join_type(left_series: pd.Series, right_series: pd.Series) -> str:
    left_unique = _uniqueness_ratio(left_series) >= 0.98
    right_unique = _uniqueness_ratio(right_series) >= 0.98

    if left_unique and right_unique:
        return "one_to_one"
    if left_unique:
        return "one_to_many"
    if right_unique:
        return "many_to_one"
    return "many_to_many"


def _relationship_candidates(
    left_name: str,
    left_df: pd.DataFrame,
    left_summary: dict,
    right_name: str,
    right_df: pd.DataFrame,
    right_summary: dict,
) -> list[dict]:
    candidates: list[dict] = []
    left_keyish = set(left_summary["candidate_keys"]).union(left_summary["primary_keys"])
    right_keyish = set(right_summary["candidate_keys"]).union(right_summary["primary_keys"])

    for left_col in left_df.columns:
        left_col_name = str(left_col)
        left_id_like = _is_id_like_column(left_col_name)
        for right_col in right_df.columns:
            right_col_name = str(right_col)
            right_id_like = _is_id_like_column(right_col_name)

            matched, exact_name = _column_name_match(left_col_name, right_col_name)
            if not matched:
                continue
            if not (left_id_like or right_id_like or left_col_name in left_keyish or right_col_name in right_keyish):
                continue

            left_values = set(_standardize_key_series(left_df[left_col_name]).dropna().unique().tolist())
            right_values = set(_standardize_key_series(right_df[right_col_name]).dropna().unique().tolist())
            if not left_values or not right_values:
                continue

            shared_values = left_values.intersection(right_values)
            if len(shared_values) < 2:
                continue

            overlap_ratio = _safe_ratio(len(shared_values), min(len(left_values), len(right_values)))
            if overlap_ratio < 0.10:
                continue

            relation_type = _join_type(left_df[left_col_name], right_df[right_col_name])
            confidence = 0.0
            reasons: list[str] = []

            if exact_name:
                confidence += 0.28
                reasons.append("same normalized key name")
            else:
                confidence += 0.18
                reasons.append("similar business key name")

            if left_col_name in left_summary["primary_keys"]:
                confidence += 0.16
                reasons.append(f"{left_name}.{left_col_name} looks like primary key")
            elif left_col_name in left_summary["candidate_keys"]:
                confidence += 0.08

            if right_col_name in right_summary["primary_keys"]:
                confidence += 0.16
                reasons.append(f"{right_name}.{right_col_name} looks like primary key")
            elif right_col_name in right_summary["candidate_keys"]:
                confidence += 0.08

            if left_id_like or right_id_like:
                confidence += 0.10
                reasons.append("id-like column naming")

            if overlap_ratio >= 0.90:
                confidence += 0.22
            elif overlap_ratio >= 0.70:
                confidence += 0.18
            elif overlap_ratio >= 0.50:
                confidence += 0.12
            else:
                confidence += 0.06

            if relation_type != "many_to_many":
                confidence += 0.08
            else:
                confidence -= 0.08

            confidence = max(0.0, min(confidence, 0.99))
            if confidence < MIN_RELATIONSHIP_CONFIDENCE:
                continue

            candidates.append(
                {
                    "left_dataset": left_name,
                    "right_dataset": right_name,
                    "left_key": left_col_name,
                    "right_key": right_col_name,
                    "join_type": relation_type,
                    "shared_values": int(len(shared_values)),
                    "overlap_ratio": round(overlap_ratio, 4),
                    "confidence": round(confidence, 4),
                    "recommended": confidence >= MASTER_TABLE_CONFIDENCE and relation_type != "many_to_many",
                    "reason": "; ".join(reasons[:4]),
                }
            )

    candidates.sort(
        key=lambda item: (item["confidence"], item["shared_values"], item["overlap_ratio"]),
        reverse=True,
    )
    return candidates[:3]


def _dataset_groups(dataset_names: Iterable[str], relationships: list[dict]) -> list[list[str]]:
    parent = {name: name for name in dataset_names}

    def find(node: str) -> str:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for rel in relationships:
        if rel["confidence"] >= MIN_RELATIONSHIP_CONFIDENCE:
            union(rel["left_dataset"], rel["right_dataset"])

    groups: dict[str, list[str]] = {}
    for name in dataset_names:
        groups.setdefault(find(name), []).append(name)

    return sorted((sorted(items) for items in groups.values()), key=lambda group: (len(group), group), reverse=True)


def build_data_catalog(data: Dict[str, pd.DataFrame]) -> dict:
    dataset_summaries = {name: _dataset_summary(name, df) for name, df in data.items()}
    relationships: list[dict] = []

    for left_name, right_name in combinations(data.keys(), 2):
        rels = _relationship_candidates(
            left_name,
            data[left_name],
            dataset_summaries[left_name],
            right_name,
            data[right_name],
            dataset_summaries[right_name],
        )
        if rels:
            relationships.extend(rels[:1])

    relationships.sort(
        key=lambda item: (item["confidence"], item["shared_values"], item["overlap_ratio"]),
        reverse=True,
    )

    groups = _dataset_groups(data.keys(), relationships)
    master_tables = [
        {
            "name": master_dataset_name(rel),
            "sources": [rel["left_dataset"], rel["right_dataset"]],
            "left_key": rel["left_key"],
            "right_key": rel["right_key"],
            "join_type": rel["join_type"],
            "confidence": rel["confidence"],
            "recommended": rel["recommended"],
        }
        for rel in relationships
        if rel["recommended"]
    ]

    return {
        "datasets": dataset_summaries,
        "relationships": relationships,
        "dataset_groups": groups,
        "master_tables": master_tables,
        "overview": {
            "dataset_count": len(data),
            "recommended_join_count": len(master_tables),
            "independent_group_count": len(groups),
        },
    }


def _preferred_join_order(relationship: dict, data: Dict[str, pd.DataFrame]) -> tuple[str, str, str, str]:
    left_name = relationship["left_dataset"]
    right_name = relationship["right_dataset"]
    left_key = relationship["left_key"]
    right_key = relationship["right_key"]
    relation_type = relationship["join_type"]

    if relation_type == "one_to_many":
        return right_name, left_name, right_key, left_key
    if relation_type == "many_to_one":
        return left_name, right_name, left_key, right_key

    if len(data[left_name]) >= len(data[right_name]):
        return left_name, right_name, left_key, right_key
    return right_name, left_name, right_key, left_key


def master_dataset_name(relationship: dict) -> str:
    left_name = relationship["left_dataset"].replace(" ", "_")
    right_name = relationship["right_dataset"].replace(" ", "_")
    return f"MASTER__{left_name}__{right_name}"


def build_master_dataset(data: Dict[str, pd.DataFrame], relationship: dict) -> pd.DataFrame:
    base_name, lookup_name, base_key, lookup_key = _preferred_join_order(relationship, data)
    base_df = data[base_name].copy()
    lookup_df = data[lookup_name].copy()

    rename_map: dict[str, str] = {}
    for col in lookup_df.columns:
        col_name = str(col)
        if col_name == lookup_key:
            continue
        if col_name in base_df.columns:
            rename_map[col_name] = f"{lookup_name}__{col_name}"

    if rename_map:
        lookup_df = lookup_df.rename(columns=rename_map)

    merged = base_df.merge(
        lookup_df,
        how="left",
        left_on=base_key,
        right_on=lookup_key,
        suffixes=("", f"__{lookup_name}"),
    )
    if lookup_key != base_key and lookup_key in merged.columns:
        merged = merged.rename(columns={lookup_key: f"{lookup_name}__{lookup_key}"})
    return merged


def build_master_datasets(data: Dict[str, pd.DataFrame], catalog: dict | None = None) -> dict[str, pd.DataFrame]:
    catalog = catalog or build_data_catalog(data)
    masters: dict[str, pd.DataFrame] = {}
    for relationship in catalog.get("relationships", []):
        if not relationship.get("recommended"):
            continue
        masters[master_dataset_name(relationship)] = build_master_dataset(data, relationship)
    return masters


def select_non_overlapping_masters(catalog: dict) -> list[dict]:
    chosen: list[dict] = []
    used_sources: set[str] = set()

    for master in sorted(catalog.get("master_tables", []), key=lambda item: item["confidence"], reverse=True):
        sources = set(master["sources"])
        if sources.intersection(used_sources):
            continue
        chosen.append(master)
        used_sources.update(sources)

    return chosen


def _best_master_for_analysis(catalog: dict, masters: dict[str, pd.DataFrame]) -> dict | None:
    for master in select_non_overlapping_masters(catalog):
        if master["name"] in masters:
            return master
    return None


def build_catalog_context(catalog: dict, dataset_names: list[str] | None = None) -> str:
    dataset_names = dataset_names or list(catalog.get("datasets", {}).keys())
    dataset_set = set(dataset_names)
    datasets = catalog.get("datasets", {})
    relationships = [
        rel
        for rel in catalog.get("relationships", [])
        if rel["left_dataset"] in dataset_set and rel["right_dataset"] in dataset_set
    ]

    lines = ["Dataset catalog summary:"]
    for name in dataset_names:
        summary = datasets.get(name)
        if not summary:
            continue
        primary_keys = ", ".join(summary["primary_keys"]) or "none"
        candidate_keys = ", ".join(summary["candidate_keys"][:3]) or "none"
        lines.append(
            f"- {name}: rows={summary['rows']}, cols={summary['cols']}, "
            f"primary_keys=[{primary_keys}], candidate_keys=[{candidate_keys}], "
            f"missing_ratio={summary['missing_ratio']:.2%}, duplicate_ratio={summary['duplicate_ratio']:.2%}"
        )

    if relationships:
        lines.append("Detected relationships:")
        for rel in relationships[:3]:
            action = "recommended for master table" if rel["recommended"] else "possible only"
            lines.append(
                f"- {rel['left_dataset']}.{rel['left_key']} <-> {rel['right_dataset']}.{rel['right_key']} "
                f"({rel['join_type']}, confidence={rel['confidence']:.2f}, overlap={rel['overlap_ratio']:.0%}, {action})"
            )
    else:
        lines.append("No reliable relationship detected between selected datasets. Analyze them separately and do not merge them.")

    return "\n".join(lines)


def query_prefers_combined_view(query: str) -> bool:
    normalized = normalize_query(query)
    return any(keyword in normalized for keyword in COMBINED_VIEW_KEYWORDS)


def prepare_analysis_bundle(query: str, selected_data: Dict[str, pd.DataFrame]) -> tuple[OrderedDict[str, pd.DataFrame], dict, str]:
    catalog = build_data_catalog(selected_data)
    bundle: OrderedDict[str, pd.DataFrame] = OrderedDict((name, df) for name, df in selected_data.items())
    context = build_catalog_context(catalog, list(selected_data.keys()))

    if len(selected_data) < 2:
        return bundle, catalog, context

    should_prepare_master = len(selected_data) == 2 or query_prefers_combined_view(query)
    if not should_prepare_master:
        return bundle, catalog, context

    masters = build_master_datasets(selected_data, catalog=catalog)
    if not masters:
        return bundle, catalog, context

    best_master = _best_master_for_analysis(catalog, masters)
    if best_master is None:
        return bundle, catalog, context

    ordered = OrderedDict()
    ordered[best_master["name"]] = masters[best_master["name"]]
    for name, df in selected_data.items():
        ordered[name] = df

    context += (
        "\nSystem prepared a master table from related datasets:\n"
        f"- {best_master['name']} built from {best_master['sources'][0]} + {best_master['sources'][1]} "
        f"using {best_master['left_key']} <-> {best_master['right_key']} "
        f"(confidence={best_master['confidence']:.2f}). Use this table for cross-table analysis; "
        "use the original tables when the user asks about only one source table."
    )
    return ordered, catalog, context
