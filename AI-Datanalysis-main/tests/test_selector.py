import pandas as pd

from ai_datanalysis.core.selector import select_datasets


def test_selector():
    df1 = pd.DataFrame({"doanh_thu": [1], "chi_phi": [2]})
    df2 = pd.DataFrame({"nhan_vien": [1], "tuoi": [30]})
    df3 = pd.DataFrame({"san_pham": [1], "gia_ban": [100]})

    data = {
        "sales.csv": df1,
        "hr.csv": df2,
        "products.csv": df3,
    }

    sel = select_datasets("tính tổng doanh thu và chi phí", data, max_datasets=1)
    assert len(sel) == 1
    assert "sales.csv" in sel

    sel2 = select_datasets("tuổi của nhân viên là bao nhiêu", data, max_datasets=1)
    assert "hr.csv" in sel2
