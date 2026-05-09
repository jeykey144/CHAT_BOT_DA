import pandas as pd

from ai_datanalysis.core.agent import AgentConfig, DataAnalysisAgent
from ai_datanalysis.core.executors import LocalRestrictedExecutor
from ai_datanalysis.core.fast_path import try_fast_path


def test_fast_path_top_n():
    df = pd.DataFrame({"A": [1, 2, 3]})
    data = {"test": df}

    code = try_fast_path("top 5", data)
    assert "head(5)" in code

    code = try_fast_path("top 10", data)
    assert "head(10)" in code


def test_fast_path_count():
    df = pd.DataFrame({"A": [1, 2, 3]})
    data = {"test": df}

    code = try_fast_path("tong so dong", data)
    assert "len" in code


def test_fast_path_min_max_temperature_bike_sharing():
    df = pd.DataFrame(
        {
            "temperature_c": [5.2, 5.7, -5.5, 40.4],
            "total_rides": [73, 117, 44, 134],
        }
    )
    data = {"bike_sharing": df}

    code = try_fast_path("hay hien thi nhiet do thap nhat va nhiet do cao nhat trong bo du lieu", data)
    assert "temperature_c" in code
    assert "Nhiệt độ thấp nhất" in code
    assert "Nhiệt độ cao nhất" in code


def test_fast_path_average_total_rides():
    df = pd.DataFrame(
        {
            "temperature_c": [5.2, 5.7, -5.5, 40.4],
            "total_rides": [73, 117, 44, 134],
        }
    )
    data = {"bike_sharing": df}

    code = try_fast_path("gia tri trung binh tong luot di", data)
    assert "total_rides" in code
    assert ".mean()" in code


def test_fast_path_generic_salary_min_max():
    df = pd.DataFrame(
        {
            "employee_name": ["A", "B", "C"],
            "salary_usd": [1000, 2500, 1800],
        }
    )
    data = {"hr": df}

    code = try_fast_path("hien thi luong thap nhat va luong cao nhat", data)
    assert "salary_usd" in code


def test_fast_path_generic_revenue_average():
    df = pd.DataFrame(
        {
            "product": ["A", "B", "C"],
            "monthly_revenue": [100.0, 150.0, 200.0],
        }
    )
    data = {"sales": df}

    code = try_fast_path("doanh thu trung binh la bao nhieu", data)
    assert "monthly_revenue" in code
    assert ".mean()" in code


def test_fast_path_skips_chart_queries():
    df = pd.DataFrame(
        {
            "season": ["Winter", "Spring", "Summer", "Autumn"],
            "temperature_c": [5.0, 15.0, 28.0, 18.0],
        }
    )
    data = {"weather": df}

    code = try_fast_path("ve bieu do line chart the hien nhiet do trung binh theo tung mua", data)
    assert code is None


def test_fast_path_pie_chart_counts_orders_by_group():
    df = pd.DataFrame(
        {
            "order_id": ["O1", "O1", "O2", "O3", "O4"],
            "sales_channel": ["Store", "Store", "Online", "Store", "Marketplace"],
            "quantity": [2, 1, 3, 1, 4],
        }
    )
    data = {"retail_sales": df}

    code = try_fast_path(
        "ve bieu do pie chart the hien ty trong don hang theo kenh ban hang",
        data,
        graph_type="pie_plot",
    )

    assert code is not None
    assert "sales_channel" in code
    assert "order_id" in code
    assert ".nunique()" in code

    executor = LocalRestrictedExecutor()
    outcome = executor.run(code, [df])

    assert outcome.ok is True
    fig = outcome.result
    mapping = dict(zip(fig.data[0].labels, fig.data[0].values))
    assert mapping == {"Marketplace": 1, "Online": 1, "Store": 2}


def test_fast_path_histogram_uses_stable_30_bins_for_numeric_distribution():
    df = pd.DataFrame(
        {
            "profit_usd": [10, 12, 15, 18, 21, 35, 42, 48, 60, 75, 90, 120],
            "sales_channel": ["Store"] * 12,
        }
    )
    data = {"retail_sales": df}

    code = try_fast_path(
        "ve bieu do histogram phan phoi loi nhuan",
        data,
        graph_type="histogram_plot",
    )

    assert code is not None
    assert "profit_usd" in code
    assert "nbins=30" in code
    assert "pd.to_numeric" in code

    executor = LocalRestrictedExecutor()
    outcome = executor.run(code, [df])

    assert outcome.ok is True
    fig = outcome.result
    assert fig.data[0].type == "histogram"
    assert fig.data[0].nbinsx == 30


def test_auto_profile_treats_student_id_like_column_as_id():
    df = pd.DataFrame(
        {
            "sbd": [2000001, 2000002, 2000003, 2000004],
            "province": ["A", "B", "C", "D"],
            "toan": [6.5, 7.0, 5.5, 8.0],
        }
    )
    data = {"exam": df}

    code = try_fast_path("phan tich tong quan du lieu", data)
    executor = LocalRestrictedExecutor()
    outcome = executor.run(code, [df])

    assert outcome.ok is True
    summary_df, insights_text = outcome.result
    assert list(summary_df.columns) == [
        "Cột",
        "Kiểu dữ liệu",
        "Trung bình",
        "Max",
        "Min",
        "Số giá trị thiếu",
        "Tỷ lệ thiếu (%)",
    ]
    assert summary_df["Cột"].tolist() == ["sbd", "province", "toan"]
    sbd_row = summary_df[summary_df["Cột"] == "sbd"].iloc[0]
    province_row = summary_df[summary_df["Cột"] == "province"].iloc[0]
    toan_row = summary_df[summary_df["Cột"] == "toan"].iloc[0]
    assert sbd_row["Kiểu dữ liệu"] == "int64"
    assert province_row["Kiểu dữ liệu"] == "object"
    assert toan_row["Kiểu dữ liệu"] == "float64"
    assert pd.isna(sbd_row["Trung bình"])
    assert pd.isna(sbd_row["Min"])
    assert pd.isna(sbd_row["Max"])
    assert pd.isna(province_row["Trung bình"])
    assert pd.isna(province_row["Min"])
    assert pd.isna(province_row["Max"])
    assert toan_row["Trung bình"] == 6.75
    assert toan_row["Min"] == 5.5
    assert toan_row["Max"] == 8.0
    assert "mã định danh" in insights_text.lower()
    assert "cấu trúc tập dữ liệu" in insights_text.lower()


def test_auto_profile_treats_year_month_as_datetime_not_numeric():
    df = pd.DataFrame(
        {
            "year": [2019, 2020, 2021, 2022],
            "month": [1, 2, 3, 4],
            "value": [10.5, 12.0, 11.2, 13.4],
        }
    )
    data = {"time_series": df}

    code = try_fast_path("phan tich tong quan du lieu", data)
    executor = LocalRestrictedExecutor()
    outcome = executor.run(code, [df])

    assert outcome.ok is True
    summary_df, _ = outcome.result

    assert summary_df["Cột"].tolist() == ["year", "month", "value"]
    year_row = summary_df[summary_df["Cột"] == "year"].iloc[0]
    month_row = summary_df[summary_df["Cột"] == "month"].iloc[0]
    value_row = summary_df[summary_df["Cột"] == "value"].iloc[0]
    assert year_row["Kiểu dữ liệu"] == "int64"
    assert month_row["Kiểu dữ liệu"] == "int64"
    assert value_row["Kiểu dữ liệu"] == "float64"
    assert pd.isna(year_row["Trung bình"])
    assert pd.isna(year_row["Min"])
    assert pd.isna(year_row["Max"])
    assert pd.isna(month_row["Trung bình"])
    assert pd.isna(month_row["Min"])
    assert pd.isna(month_row["Max"])
    assert value_row["Trung bình"] == 11.775
    assert value_row["Min"] == 10.5
    assert value_row["Max"] == 13.4


def test_agent_auto_profile_uses_fast_path_without_llm():
    class ExplodingLLM:
        def invoke(self, messages):
            raise AssertionError("LLM should not be called for auto_profile fast-path")

    df = pd.DataFrame(
        {
            "sbd": [2000001, 2000002, 2000003],
            "province": ["A", "B", "A"],
            "toan": [6.5, 7.0, 5.5],
        }
    )

    agent = DataAnalysisAgent(
        llm=ExplodingLLM(),
        executor=LocalRestrictedExecutor(),
        config=AgentConfig(max_attempts=1),
    )
    outcome = agent.run_pipeline(
        query="kham pha du lieu",
        data={"exam": df},
        history=[],
        language="vi",
        privacy=True,
        sample=0,
        scope="test-auto-profile-fast-path",
    )

    assert outcome.ok is True
    assert isinstance(outcome.result, tuple)
    summary_df, insights_text = outcome.result
    assert not summary_df.empty
    assert "Tổng quan dữ liệu" in insights_text
    assert agent.last_error == ""


def test_agent_pie_order_share_uses_fast_path_without_llm():
    class ExplodingLLM:
        def invoke(self, messages):
            raise AssertionError("LLM should not be called for pie count fast-path")

    df = pd.DataFrame(
        {
            "order_id": ["O1", "O1", "O2", "O3", "O4"],
            "sales_channel": ["Store", "Store", "Online", "Store", "Marketplace"],
            "quantity": [2, 1, 3, 1, 4],
        }
    )

    agent = DataAnalysisAgent(
        llm=ExplodingLLM(),
        executor=LocalRestrictedExecutor(),
        config=AgentConfig(max_attempts=1),
    )
    outcome = agent.run_pipeline(
        query="ve bieu do pie chart the hien ty trong don hang theo kenh ban hang",
        data={"retail_sales": df},
        history=[],
        language="vi",
        privacy=True,
        sample=0,
        scope="test-pie-count-fast-path",
    )

    assert outcome.ok is True
    fig = outcome.result
    mapping = dict(zip(fig.data[0].labels, fig.data[0].values))
    assert mapping == {"Marketplace": 1, "Online": 1, "Store": 2}
    assert agent.last_error == ""


def test_agent_histogram_distribution_uses_fast_path_without_llm():
    class ExplodingLLM:
        def invoke(self, messages):
            raise AssertionError("LLM should not be called for histogram fast-path")

    df = pd.DataFrame(
        {
            "profit_usd": [10, 12, 15, 18, 21, 35, 42, 48, 60, 75, 90, 120],
            "sales_channel": ["Store"] * 12,
        }
    )

    agent = DataAnalysisAgent(
        llm=ExplodingLLM(),
        executor=LocalRestrictedExecutor(),
        config=AgentConfig(max_attempts=1),
    )
    outcome = agent.run_pipeline(
        query="ve bieu do histogram phan phoi loi nhuan",
        data={"retail_sales": df},
        history=[],
        language="vi",
        privacy=True,
        sample=0,
        scope="test-histogram-fast-path",
    )

    assert outcome.ok is True
    fig = outcome.result
    assert fig.data[0].type == "histogram"
    assert fig.data[0].nbinsx == 30
    assert agent.last_error == ""
