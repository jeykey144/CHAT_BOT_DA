import pandas as pd

from ai_datanalysis.core.executors import LocalRestrictedExecutor


def test_executor_comprehension_can_access_exec_assigned_variables():
    df = pd.DataFrame({"revenue": [100, 120, 90], "cost": [60, 70, 50]})
    code = """
_num_cols = ["revenue", "cost"]
result = pd.DataFrame({
    "column": [col for col in _num_cols],
    "mean": [DF_1[col].mean() for col in _num_cols],
})
"""

    outcome = LocalRestrictedExecutor().run(code, [df])

    assert outcome.ok, outcome.error
    assert outcome.result["column"].tolist() == ["revenue", "cost"]
    assert outcome.result["mean"].tolist() == [df["revenue"].mean(), df["cost"].mean()]
