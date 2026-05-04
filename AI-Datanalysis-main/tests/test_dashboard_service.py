import pandas as pd

from ai_datanalysis.services.dashboard_service import build_auto_dashboard, build_dashboard_report


def test_build_auto_dashboard_sales_dataset():
    df = pd.DataFrame(
        {
            "order_date": pd.date_range("2025-01-01", periods=8, freq="D"),
            "region": ["North", "South", "North", "East", "East", "South", "West", "North"],
            "product": ["A", "A", "B", "B", "C", "A", "C", "B"],
            "revenue": [100, 120, 90, 150, 170, 180, 160, 210],
            "profit": [20, 25, 18, 30, 31, 36, 28, 40],
            "order_id": [f"O{i}" for i in range(8)],
        }
    )

    dashboard = build_auto_dashboard(df, dataset_name="sales.csv", role="ceo", goal="Tao dashboard tong quan")

    assert dashboard["__type__"] == "dashboard"
    assert dashboard["context"]["primary_metric"] == "revenue"
    assert dashboard["context"]["time_col"] == "order_date"
    assert dashboard["context"]["dashboard_family"] == "finance"
    assert {section["id"] for section in dashboard["sections"]} >= {"kpi_overview", "trend", "breakdown", "comparison", "insight_box", "filter_panel"}
    assert len(dashboard["kpis"]) >= 4
    assert len(dashboard["charts"]) >= 2


def test_build_auto_dashboard_without_time_column():
    df = pd.DataFrame(
        {
            "province": ["A", "B", "C", "A", "B", "C"],
            "gender": ["F", "F", "M", "M", "F", "M"],
            "score": [6.1, 7.2, 5.8, 8.0, 6.9, 7.5],
            "passed_flag": [1, 1, 1, 1, 1, 1],
        }
    )

    dashboard = build_auto_dashboard(df, dataset_name="exam.csv", role="analyst")

    assert dashboard["__type__"] == "dashboard"
    assert dashboard["context"]["primary_metric"] == "score"
    assert dashboard["context"]["time_col"] is None
    assert dashboard["context"]["dashboard_family"] == "quantitative_multivariate"
    assert {section["id"] for section in dashboard["sections"]} >= {"kpi_overview", "distribution", "breakdown", "relationship", "insight_box", "filter_panel"}
    assert len(dashboard["charts"]) >= 1


def test_build_dashboard_report_uses_master_for_related_datasets():
    orders = pd.DataFrame(
        {
            "order_id": ["O1", "O2", "O3"],
            "customer_id": [1, 2, 1],
            "order_date": pd.date_range("2025-01-01", periods=3, freq="D"),
            "revenue": [100, 150, 130],
        }
    )
    customers = pd.DataFrame(
        {
            "customer_id": [1, 2],
            "segment": ["A", "B"],
            "city": ["HN", "HCM"],
        }
    )

    report = build_dashboard_report({"orders": orders, "customers": customers}, role="ceo", goal="Bao cao tong hop")

    assert report["__type__"] == "dashboard_report"
    assert report["overview"]["recommended_join_count"] >= 1
    assert len(report["sections"]) == 1
    assert report["sections"][0]["mode"] == "master"


def test_build_dashboard_report_keeps_unrelated_datasets_separate():
    sales = pd.DataFrame({"region": ["North", "South"], "revenue": [100, 120]})
    hr = pd.DataFrame({"employee": ["A", "B"], "age": [30, 31]})

    report = build_dashboard_report({"sales": sales, "hr": hr}, role="analyst", goal="Bao cao tong quan")

    assert report["__type__"] == "dashboard_report"
    assert report["overview"]["recommended_join_count"] == 0
    assert len(report["sections"]) == 2
    assert all(section["mode"] == "dataset" for section in report["sections"])
