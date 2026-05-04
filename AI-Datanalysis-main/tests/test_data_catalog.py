import pandas as pd

from ai_datanalysis.core.agent import DataAnalysisAgent
from ai_datanalysis.core.data_catalog import build_data_catalog, build_master_datasets, prepare_analysis_bundle
from ai_datanalysis.core.executors import LocalRestrictedExecutor


def test_build_data_catalog_detects_recommended_relationship():
    orders = pd.DataFrame(
        {
            "order_id": ["O1", "O2", "O3"],
            "customer_id": [1, 2, 1],
            "revenue": [100, 150, 120],
        }
    )
    customers = pd.DataFrame(
        {
            "customer_id": [1, 2],
            "segment": ["A", "B"],
            "city": ["HN", "HCM"],
        }
    )

    catalog = build_data_catalog({"orders": orders, "customers": customers})

    assert catalog["relationships"]
    assert catalog["relationships"][0]["recommended"] is True
    assert catalog["master_tables"]

    masters = build_master_datasets({"orders": orders, "customers": customers}, catalog=catalog)
    master_name = catalog["master_tables"][0]["name"]
    assert master_name in masters
    assert len(masters[master_name]) == len(orders)
    assert "segment" in masters[master_name].columns


def test_prepare_analysis_bundle_includes_master_for_combined_queries():
    orders = pd.DataFrame({"customer_id": [1, 2, 1], "revenue": [100, 120, 90]})
    customers = pd.DataFrame({"customer_id": [1, 2], "segment": ["A", "B"]})

    bundle, _catalog, context = prepare_analysis_bundle(
        "tao dashboard tong quan cho toan bo du lieu",
        {"orders": orders, "customers": customers},
    )

    first_name = next(iter(bundle.keys()))
    assert first_name.startswith("MASTER__")
    assert "master table" in context.lower()


def test_prepare_analysis_bundle_auto_merges_two_related_tables():
    orders = pd.DataFrame({"customer_id": [1, 2, 1], "revenue": [100, 120, 90]})
    customers = pd.DataFrame({"customer_id": [1, 2], "segment": ["A", "B"]})

    bundle, _catalog, context = prepare_analysis_bundle(
        "ve bieu do doanh thu theo segment",
        {"orders": orders, "customers": customers},
    )

    first_name = next(iter(bundle.keys()))
    assert first_name.startswith("MASTER__")
    assert "segment" in bundle[first_name].columns
    assert "cross-table analysis" in context


def test_prepare_analysis_bundle_keeps_unrelated_datasets_separate():
    sales = pd.DataFrame({"revenue": [100, 120], "region": ["North", "South"]})
    hr = pd.DataFrame({"employee": ["A", "B"], "age": [30, 31]})

    bundle, _catalog, context = prepare_analysis_bundle(
        "tao dashboard tong quan cho toan bo du lieu",
        {"sales": sales, "hr": hr},
    )

    first_name = next(iter(bundle.keys()))
    assert not first_name.startswith("MASTER__")
    assert "Analyze them separately" in context


def test_agent_auto_profile_uses_master_table_fast_path_without_llm():
    class FailingLLM:
        def invoke(self, _messages):
            raise AssertionError("LLM should not be called for related-table auto_profile fast-path")

    orders = pd.DataFrame({"customer_id": [1, 2, 1], "revenue": [100, 120, 90]})
    customers = pd.DataFrame({"customer_id": [1, 2], "segment": ["A", "B"]})
    agent = DataAnalysisAgent(llm=FailingLLM(), executor=LocalRestrictedExecutor())

    outcome = agent.run_pipeline(
        query="kham pha du lieu",
        data={"orders": orders, "customers": customers},
        scope="test-related-table-auto-profile",
    )

    assert outcome.ok, outcome.error
    assert agent.last_code
    assert "DF_1.copy()" in agent.last_code
