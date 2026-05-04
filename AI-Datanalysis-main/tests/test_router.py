from ai_datanalysis.core.normalization import normalize_query
from ai_datanalysis.core.router import infer_graph_type, route_query


def test_intent_routing():
    res = route_query("tính tổng doanh thu của sản phẩm")
    assert "calculation" in res.intents

    res2 = route_query("so sánh doanh thu năm nay và năm ngoái")
    assert "comparison" in res2.intents

    res3 = route_query("những nhân viên nào có lương lớn hơn 10tr")
    assert "filter" in res3.intents


def test_graph_inference():
    assert infer_graph_type(normalize_query("vẽ biểu đồ phân tán")) == "scatter_2d_plot"
    assert infer_graph_type(normalize_query("vẽ biểu đồ tỷ lệ doanh thu theo vùng")) == "pie_plot"
    assert infer_graph_type(normalize_query("hãy tổng hợp báo cáo và khám phá dữ liệu")) == "auto_profile"


def test_follow_up():
    res = route_query("vẽ lại biểu đồ trên nhưng đổi thành màu đỏ")
    assert res.is_follow_up is True
