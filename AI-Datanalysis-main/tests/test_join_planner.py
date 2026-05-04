import pandas as pd

from ai_datanalysis.core.join_planner import build_join_context, infer_join_hints, query_suggests_join


def test_query_suggests_join():
    assert query_suggests_join("ket hop bang don hang va khach hang") is True
    assert query_suggests_join("tinh tong doanh thu") is False


def test_infer_join_hints_detects_shared_id():
    orders = pd.DataFrame({"customer_id": [1, 2], "revenue": [10, 20]})
    customers = pd.DataFrame({"customer_id": [1, 2], "segment": ["A", "B"]})
    hints = infer_join_hints({"orders": orders, "customers": customers})
    assert hints
    assert hints[0].left_column == "customer_id"
    assert hints[0].right_column == "customer_id"


def test_build_join_context_contains_hint():
    orders = pd.DataFrame({"customer_id": [1, 2], "revenue": [10, 20]})
    customers = pd.DataFrame({"customer_id": [1, 2], "segment": ["A", "B"]})
    context = build_join_context({"orders": orders, "customers": customers})
    assert "customer_id" in context
