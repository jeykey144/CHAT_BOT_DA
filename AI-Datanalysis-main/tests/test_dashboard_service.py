import pandas as pd

from ai_datanalysis.core.data_catalog import build_data_catalog
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
    trend_section = next(section for section in dashboard["sections"] if section["id"] == "trend")
    assert trend_section["charts"][0]["figure"] is None
    assert "Khong tim thay cot thoi gian hop le" in trend_section["charts"][0]["message"]


def test_build_auto_dashboard_prefers_timestamp_over_duration():
    df = pd.DataFrame(
        {
            "student_id": ["S1", "S1", "S2", "S2", "S3", "S3"],
            "content_id": ["C1", "C2", "C1", "C2", "C1", "C2"],
            "score": [92, 86, 55, 72, 64, 66],
            "time_spent": [40, 41, 36, 54, 57, 8],
            "timestamp": pd.date_range("2025-09-11", periods=6, freq="D"),
            "subject": ["Math", "Math", "History", "History", "Science", "Science"],
        }
    )

    dashboard = build_auto_dashboard(df, dataset_name="progress.csv", role="analyst", goal="xu huong score")

    assert dashboard["context"]["primary_metric"] == "score"
    assert dashboard["context"]["time_col"] == "timestamp"
    trend = next(chart for chart in dashboard["charts"] if chart["kind"] == "trend")
    x_values = list(trend["figure"].data[0].x)
    assert len(x_values) == 6
    assert all(pd.Timestamp(value).year == 2025 for value in x_values)


def test_build_dashboard_report_master_uses_progress_timestamp():
    progress = pd.DataFrame(
        {
            "student_id": ["S1", "S1", "S2", "S2"],
            "content_id": ["C1", "C2", "C1", "C2"],
            "score": [80, 90, 70, 85],
            "time_spent": [40, 45, 35, 50],
            "timestamp": pd.date_range("2025-09-11", periods=4, freq="D"),
        }
    )
    content = pd.DataFrame(
        {
            "content_id": ["C1", "C2"],
            "title": ["Algebra", "Python"],
            "subject": ["Math", "Computer Science"],
            "duration_minutes": [15, 60],
        }
    )

    report = build_dashboard_report(
        {"progress.csv": progress, "content.csv": content},
        role="analyst",
        goal="xu huong score theo thoi gian",
    )

    assert report["sections"][0]["mode"] == "master"
    dashboard = report["sections"][0]["dashboard"]
    assert dashboard["context"]["primary_metric"] == "score"
    assert dashboard["context"]["time_col"] == "timestamp"
    trend = next(chart for chart in dashboard["charts"] if chart["kind"] == "trend")
    assert all(pd.Timestamp(value).year == 2025 for value in trend["figure"].data[0].x)


def test_dashboard_skips_invalid_timestamps_instead_of_using_1970():
    df = pd.DataFrame(
        {
            "score": [80, 90, 70, 85],
            "time_spent": [40, 45, 35, 50],
            "timestamp": ["2025-09-11", "bad-date", "2025-09-13", "2025-09-14"],
            "subject": ["Math", "Math", "Science", "Science"],
        }
    )

    dashboard = build_auto_dashboard(df, dataset_name="progress.csv", role="analyst", goal="dashboard xu huong score")

    assert dashboard["context"]["time_col"] == "timestamp"
    assert dashboard["quality"]["datetime_invalid_counts"]["timestamp"] == 1
    trend = next(chart for chart in dashboard["charts"] if chart["kind"] == "trend")
    years = [pd.Timestamp(value).year for value in trend["figure"].data[0].x]
    assert years == [2025, 2025, 2025]
    assert 1970 not in years


def test_dashboard_scatter_uses_explanatory_x_and_score_y():
    df = pd.DataFrame(
        {
            "score": [80, 90, 70, 85, 75, 88],
            "time_spent": [40, 45, 35, 50, 38, 44],
            "timestamp": pd.date_range("2025-09-11", periods=6, freq="D"),
            "subject": ["Math", "Math", "Science", "Science", "History", "History"],
        }
    )

    dashboard = build_auto_dashboard(df, dataset_name="progress.csv", role="analyst", goal="scatter score time spent")
    scatter = next(chart for chart in dashboard["charts"] if chart["kind"] == "relationship")

    assert scatter["title"] == "Quan he time_spent -> score"
    fig = scatter["figure"]
    assert fig.layout.xaxis.title.text == "time_spent"
    assert fig.layout.yaxis.title.text == "score"


def test_data_catalog_prefers_content_id_over_descriptive_duplicate_columns():
    progress = pd.DataFrame(
        {
            "content_id": ["C1", "C2", "C1", "C2"],
            "title": ["Same", "Same", "Same", "Same"],
            "subject": ["Math", "Math", "Math", "Math"],
            "difficulty_level": ["Beginner", "Beginner", "Beginner", "Beginner"],
            "score": [80, 90, 70, 85],
        }
    )
    content = pd.DataFrame(
        {
            "content_id": ["C1", "C2"],
            "title": ["Same", "Same"],
            "subject": ["Math", "Math"],
            "difficulty_level": ["Beginner", "Beginner"],
            "duration_minutes": [15, 60],
        }
    )

    catalog = build_data_catalog({"progress": progress, "content": content})
    rel = catalog["relationships"][0]

    assert rel["left_key"] == "content_id"
    assert rel["right_key"] == "content_id"
    assert rel["recommended"] is True


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
