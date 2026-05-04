import pandas as pd

from ai_datanalysis.core.prompt_builder import build_prompt


def test_privacy_mode_omits_sample_rows():
    df = pd.DataFrame({"doanh_thu": [1, 2], "vung": ["A", "B"]})
    prompt = build_prompt(
        question="ve bieu do cot doanh thu theo vung",
        data={"sales.csv": df},
        privacy=True,
        sample_rows=5,
    )
    assert "sample_head:" not in prompt


def test_non_private_mode_includes_sample_rows():
    df = pd.DataFrame({"doanh_thu": [1, 2], "vung": ["A", "B"]})
    prompt = build_prompt(
        question="ve bieu do cot doanh thu theo vung",
        data={"sales.csv": df},
        privacy=False,
        sample_rows=2,
    )
    assert "sample_head:" in prompt


def test_auto_profile_prompt_requires_min_max_stats():
    df = pd.DataFrame({"doanh_thu": [1, 2], "chi_phi": [0.5, 1.0]})
    prompt = build_prompt(
        question="kham pha du lieu",
        data={"sales.csv": df},
        privacy=True,
        sample_rows=0,
    )
    assert "includes `min` and `max` values" in prompt
