from ai_datanalysis.core.normalization import normalize_query


def test_normalization_lowercases():
    assert normalize_query("TeSt") == "test"


def test_normalization_removes_accents():
    assert normalize_query("Tinh tong doanh thu") == "tinh tong doanh thu"
    assert normalize_query("Đếm KẾT QUẢ") == "dem ket qua"


def test_normalization_expands_abbreviations():
    assert "san pham" in normalize_query("co sp nao")
    assert "so luong" in normalize_query("tinh sl")
    assert "quy 1" in normalize_query("q1")
    assert "khong" in normalize_query("ko co")
    assert "khach hang" in normalize_query("khach mua gi")


def test_normalization_removes_extra_spaces():
    assert normalize_query("   tinh    tong ") == "tinh tong"
