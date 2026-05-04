"""
Retrieval service — public API for query understanding and dataset retrieval.

Cung cấp một interface thống nhất cho toàn bộ pipeline truy vấn:
    normalize_query      → chuẩn hóa text đầu vào
    route_query          → phân loại intent và loại biểu đồ
    select_datasets      → chọn bảng dữ liệu liên quan nhất
    score_query_to_column → đánh giá độ liên quan query-cột
    get_semantic_type     → phân loại ngữ nghĩa cột

Các module core bên dưới KHÔNG được gọi trực tiếp từ app.py — mọi truy cập
đi qua service này để đảm bảo API ổn định khi nội bộ core thay đổi.
"""
from __future__ import annotations

from typing import Dict

import pandas as pd

from ai_datanalysis.core.normalization import normalize_query
from ai_datanalysis.core.router import RouterOutcome, route_query
from ai_datanalysis.core.selector import select_datasets
from ai_datanalysis.core.semantic_columns import column_semantic_hint, score_query_to_column

__all__ = [
    "normalize_query",
    "route_query",
    "RouterOutcome",
    "select_datasets",
    "score_query_to_column",
    "column_semantic_hint",
    "retrieve_context",
]


def retrieve_context(
    query: str,
    data: Dict[str, pd.DataFrame],
    max_datasets: int = 2,
) -> dict:
    """
    Pipeline truy vấn đầy đủ trong một lần gọi.

    Thực hiện tuần tự:
      1. Chuẩn hóa query (bỏ dấu, lowercase)
      2. Phân loại intent + loại biểu đồ
      3. Chọn datasets liên quan nhất

    Parameters
    ----------
    query : str
        Câu hỏi gốc từ người dùng.
    data : Dict[str, pd.DataFrame]
        Toàn bộ dữ liệu đang có.
    max_datasets : int
        Số lượng dataset tối đa được chọn (mặc định 2).

    Returns
    -------
    dict
        {
            "normalized_query": str,
            "route": RouterOutcome,
            "selected_data": Dict[str, pd.DataFrame],
        }
    """
    normalized = normalize_query(query)
    route = route_query(normalized)

    effective_max = max_datasets
    if getattr(route, "requires_multi_dataset", False):
        effective_max = max(max_datasets, 3)

    selected = select_datasets(normalized, data, max_datasets=effective_max)

    return {
        "normalized_query": normalized,
        "route": route,
        "selected_data": selected,
    }
