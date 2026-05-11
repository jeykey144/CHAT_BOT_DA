"""
Vietnamese vocabulary hub — single source of truth for all VI query understanding.

Imported by:
  - normalization.py  → VI_ABBREVIATIONS
  - router.py         → VI_INTENT_KEYWORDS, VI_CHART_KEYWORDS, VI_FOLLOW_UP_KEYWORDS
  - semantic_columns.py → VI_TOKEN_SYNONYMS

Để bổ sung từ vựng mới, chỉ cần chỉnh sửa file này.
"""
from __future__ import annotations

# ══════════════════════════════════════════════════════════════════════
# 1. ABBREVIATIONS
#    Quy tắc: regex key → chuỗi mở rộng.
#    Lưu ý: KHÔNG mở rộng "min"/"max" — router.py dùng trực tiếp.
# ══════════════════════════════════════════════════════════════════════
VI_ABBREVIATIONS: dict[str, str] = {

    # ── Chung ─────────────────────────────────────────────────────────
    r"\bko\b":  "khong",
    r"\bk\b":   "khong",
    r"\bdc\b":  "duoc",
    r"\bok\b":  "duoc",
    r"\bvd\b":  "vi du",
    r"\btt\b":  "tong the",

    # ── Thực thể kinh doanh ───────────────────────────────────────────
    r"\bkh\b":  "khach hang",
    r"\bkhach\b": "khach hang",
    r"\bsp\b":  "san pham",
    r"\bcn\b":  "chi nhanh",
    r"\bnv\b":  "nhan vien",
    r"\bdv\b":  "don vi",
    r"\bncc\b": "nha cung cap",
    r"\bhh\b":  "hang hoa",
    r"\bhd\b":  "hoa don",
    r"\bddh\b": "don dat hang",
    r"\bhdh\b": "hop dong",
    r"\bpb\b":  "phong ban",

    # ── Chỉ số tài chính ─────────────────────────────────────────────
    r"\bdt\b":      "doanh thu",
    r"\bthu nhap\b":"doanh thu",
    r"\bln\b":      "loi nhuan",
    r"\bcp\b":      "chi phi",
    r"\btl\b":      "ty le",
    r"\bgt\b":      "gia tri",
    r"\bsl\b":      "so luong",
    r"\bgg\b":      "giam gia",
    r"\bdg\b":      "don gia",
    r"\bck\b":      "chiet khau",
    r"\bnk\b":      "nhap khau",
    r"\bxk\b":      "xuat khau",
    r"\bns\b":      "ngan sach",
    r"\bmt\b":      "muc tieu",

    # ── Kỳ thời gian ─────────────────────────────────────────────────
    r"\bq1\b":      "quy 1",
    r"\bq2\b":      "quy 2",
    r"\bq3\b":      "quy 3",
    r"\bq4\b":      "quy 4",
    r"\bquy i\b":   "quy 1",
    r"\bquy ii\b":  "quy 2",
    r"\bquy iii\b": "quy 3",
    r"\bquy iv\b":  "quy 4",
    r"\bt1\b":      "thang 1",
    r"\bt2\b":      "thang 2",
    r"\bt3\b":      "thang 3",
    r"\bt4\b":      "thang 4",
    r"\bt5\b":      "thang 5",
    r"\bt6\b":      "thang 6",
    r"\bt7\b":      "thang 7",
    r"\bt8\b":      "thang 8",
    r"\bt9\b":      "thang 9",
    r"\bt10\b":     "thang 10",
    r"\bt11\b":     "thang 11",
    r"\bt12\b":     "thang 12",
    r"\bh1\b":      "nua dau nam",
    r"\bh2\b":      "nua cuoi nam",
    r"\bytd\b":     "luy ke nam",
    r"\bmtd\b":     "luy ke thang",
    r"\bqtd\b":     "luy ke quy",
    r"\byoy\b":     "tang truong nam tren nam",
    r"\bmom\b":     "tang truong thang tren thang",
    r"\bqoq\b":     "tang truong quy tren quy",

    # ── Biểu đồ ───────────────────────────────────────────────────────
    r"\bbd\b":   "bieu do",
    r"\bchar\b": "chart",
    r"\bpict\b": "chart",
    r"\bhinh\b": "bieu do",

    # ── Tiếng Anh viết tắt ────────────────────────────────────────────
    r"\bqty\b":  "quantity",
    r"\bamt\b":  "amount",
    r"\brevs\b": "revenue",
    r"\bavg\b":  "average",
    r"\bpct\b":  "percent",
    r"\bvol\b":  "volume",
    r"\bwow\b":  "tang truong tuan tren tuan",
}


# ══════════════════════════════════════════════════════════════════════
# 2. INTENT KEYWORDS
#    Mỗi intent là list từ/cụm từ đã được normalize (không dấu, thường).
# ══════════════════════════════════════════════════════════════════════
VI_INTENT_KEYWORDS: dict[str, list[str]] = {

    "calculation": [
        # Tính toán
        "tinh", "tinh toan", "tinh ra",
        "tong", "tong cong", "tong the", "tong so",
        "trung binh", "gia tri trung binh", "tb", "mean",
        "dem", "so luong", "bao nhieu", "co bao nhieu",
        "lon nhat", "nho nhat",
        "thong ke", "thong ke mo ta", "mo ta",
        "do lech chuan", "phuong sai", "bien dong",
        "tong hop ket qua",
        # English
        "count", "sum", "mean", "average", "calc",
        "total", "aggregate", "calculate", "compute",
        "std", "variance", "median", "quantile",
    ],

    "filter": [
        # Lọc / Tìm kiếm
        "loc", "loc theo", "loc ra", "loc du lieu",
        "lay", "lay ra", "lay du lieu", "lay nhung", "lay cac",
        "tim", "tim kiem", "tim nhung", "tim cac", "tim ra",
        "chon", "chon loc", "chon ra",
        "chi lay", "chi hien thi", "chi tinh", "chi xem", "chi",
        "nhung", "cac", "nhung cai",
        # Điều kiện
        "dieu kien", "theo dieu kien",
        "lon hon", "nho hon", "bang", "khong bang",
        "tu nam", "den nam", "tu thang", "den thang",
        "trong khoang", "khoang", "pham vi",
        # Địa lý
        "khu vuc", "vung", "mien bac", "mien nam", "mien trung",
        "tinh", "thanh pho", "quan", "huyen",
        # Loại trừ
        "loai tru", "loai bo", "bo qua", "ngoai tru", "khong tinh",
        "giu lai", "giu nguyen",
        "truoc", "sau", "gan day", "gan nhat",
        # English
        "filter", "where", "condition", "select",
        "exclude", "include", "between", "greater", "less",
        "only", "just", "restrict", "subset",
    ],

    "comparison": [
        # So sánh
        "so sanh", "so sanh voi", "doi chieu",
        "khac biet", "su khac nhau", "chenh lech", "cach biet",
        "cao hon", "thap hon", "lon hon", "nho hon",
        "kem hon", "vuot hon", "tot hon", "te hon",
        "nam nay va nam ngoai", "thang nay va thang truoc",
        "giua cac", "theo tung", "tung",
        "gap doi", "gap ba",
        # English
        "compare", "comparison", "vs", "versus",
        "difference", "contrast", "relative", "benchmark",
    ],

    "ranking": [
        # Xếp hạng
        "top", "top n",
        "hang dau", "hang nhat", "hang thu",
        "cao nhat", "lon nhat", "nhieu nhat", "nhat",
        "thap nhat", "nho nhat", "it nhat", "cuoi",
        "xep hang", "vi tri", "thu hang",
        "dung dau", "dung cuoi", "cuoi bang", "dau bang",
        "tot nhat", "kem nhat", "ban chay nhat",
        "nhieu nhat", "it nhat",
        # English
        "top", "bottom", "rank", "ranking",
        "max", "min", "highest", "lowest",
        "most", "least", "best", "worst",
    ],

    "trend": [
        # Xu hướng / Thời gian
        "xu huong", "xu the",
        "tang giam", "bien dong", "bien thien",
        "tang truong", "tang len", "giam xuong",
        "di xuong", "di len", "leo thang", "sut giam",
        "qua thoi gian", "theo thoi gian",
        "theo ngay", "theo tuan", "theo thang",
        "theo quy", "theo nam",
        "qua cac nam", "qua cac thang", "qua cac quy",
        "lich su", "lich su du lieu",
        "toc do tang", "toc do tang truong",
        "luy ke", "luy ke nam", "luy ke thang",
        "nam tren nam", "thang tren thang",
        "yoy", "mom", "qoq",
        # English
        "trend", "over time", "time series", "history",
        "growth", "change", "evolution", "progress",
    ],

    "distribution": [
        # Phân phối
        "phan phoi", "phan bo",
        "mat do", "do mat do",
        "tan suat", "tan suat xuat hien",
        "do phan tan", "khoang gia tri",
        "nhu the nao", "pho bien",
        # English
        "distribution", "histogram", "density",
        "spread", "frequency", "how many",
    ],

    "relationship": [
        # Tương quan / Quan hệ
        "tuong quan", "moi tuong quan", "he so tuong quan",
        "anh huong", "anh huong den", "tac dong", "tac dong cua",
        "lien he", "moi lien he", "quan he",
        "phu thuoc", "phu thuoc vao",
        "khi tang thi", "khi giam thi",
        # English
        "correlation", "relationship", "scatter",
        "impact", "influence", "dependency", "association",
    ],

    "composition": [
        # Cơ cấu / Tỉ lệ
        "ty le", "ti le", "ty trong",
        "phan tram", "phan tram dong gop", "phan tram cua",
        "thanh phan", "cac thanh phan",
        "chiem", "chiem bao nhieu", "chiem bao nhieu phan tram",
        "co cau", "co cau doanh thu", "co cau chi phi",
        "chia theo", "theo co cau",
        "dong gop", "dong gop cua",
        # English
        "composition", "proportion", "percentage",
        "share", "breakdown", "pie", "sunburst", "part of",
    ],

    "profiling": [
        # Khám phá / Tổng quan
        "phan tich tong quan", "phan tich co ban",
        "kham pha", "kham pha du lieu",
        "tong quan", "nhin tong quan", "xem tong the",
        "mo ta du lieu", "thong ke tong quat",
        "bao cao nhanh", "bao cao tu dong", "bao cao tong hop",
        "kiem tra du lieu", "kiem tra chat luong",
        "du lieu bi thieu", "gia tri null", "gia tri ngoai le",
        # English
        "profile", "auto profile", "auto-profile",
        "explore", "overview", "summary", "insight", "describe",
    ],

    "join": [
        # Ghép bảng
        "ket hop", "ket hop du lieu", "ket hop 2 bang",
        "lien ket", "lien ket bang",
        "ghep bang", "ghep du lieu",
        "noi bang", "noi du lieu",
        "phan tich tong hop tu nhieu bang",
        # English
        "join", "merge", "combine", "link", "match",
    ],
}


# ══════════════════════════════════════════════════════════════════════
# 3. CHART TYPE KEYWORDS
#    Thứ tự dict = thứ tự ưu tiên nhận diện (specific trước, generic sau).
#    "auto_profile" và "table" được xử lý riêng ở cuối router.
# ══════════════════════════════════════════════════════════════════════
VI_CHART_KEYWORDS: dict[str, list[str]] = {

    "candle_plot": [
        "candle chart", "candlestick", "bieu do nen",
        "bieu do nến", "gia chung khoan", "bien dong gia co phieu",
        "ohlc", "o-h-l-c",
    ],
    "line_plot": [
        "line chart", "line plot",
        "bieu do duong", "bieu do duong thang",
        "do thi duong", "do thi duong thang",
        "duong xu huong", "duong bien dong", "duong bieu dien",
        "bieu do xu huong", "bieu do bien thien",
        "bieu do theo thoi gian",
        "ve duong",
    ],
    "bar_plot": [
        "bar chart", "bar plot",
        "bieu do cot", "do thi cot",
        "bieu do thanh", "bieu do thanh doc", "bieu do thanh ngang",
        "bieu do cot dung", "bieu do cot ngang",
        "cot dung", "thanh ngang",
        "bieu do so sanh cot",
        "ve cot",
    ],
    "scatter_2d_plot": [
        "scatter", "scatter plot", "scatter chart",
        "bieu do phan tan", "do thi phan tan",
        "phan tan", "diem du lieu",
        "bieu do 2 bien", "bieu do tuong quan diem",
    ],
    "histogram_plot": [
        "histogram", "bieu do tan suat",
        "phan phoi tan suat", "do thi phan phoi",
        "bieu do phan phoi", "ve histogram",
    ],
    "heatmap": [
        "heatmap", "heat map",
        "ban do nhiet", "ban do nhiet do",
        "ma tran tuong quan", "ma tran",
        "bieu do nhiet", "bieu do ma tran",
        "bieu do nuoc nong",
    ],
    "box_plot": [
        "box plot", "boxplot", "bieu do hop",
        "bieu do tu phan vi", "box and whisker",
        "bieu do phan phoi so lieu",
    ],
    "violin_plot": [
        "violin", "violin plot", "bieu do violin",
    ],
    "area_plot": [
        "area chart", "area plot",
        "bieu do mien", "bieu do dien tich",
        "bieu do vung", "do thi mien",
        "ve mien",
    ],
    "pie_plot": [
        "pie chart", "pie plot",
        "bieu do tron", "do thi tron",
        "bieu do banh", "bieu do ty le",
        "ve tron", "ty le phan tram",
    ],
    "bubble_plot": [
        "bubble chart", "bubble plot",
        "bieu do bong bong", "bong bong", "bubble",
    ],
    "density_contour_plot": [
        "density plot", "density contour",
        "bieu do mat do", "bieu do duong mat do",
        "mat do",
    ],
    "polar_plot": [
        "polar chart", "polar plot",
        "bieu do radar", "radar chart",
        "radar", "polar", "bieu do nhen",
    ],
    "sunburst_plot": [
        "sunburst", "sunburst chart",
        "bieu do mat troi", "bieu do cap bac",
    ],
    "treemap_plot": [
        "treemap", "tree map",
        "ban do cay", "bieu do cay",
    ],
    "auto_profile": [
        "phan tich tong quan", "phan tich co ban",
        "kham pha du lieu", "kham pha",
        "tong quan du lieu", "nhin tong quan",
        "auto profile", "auto-profile",
        "explore", "profile", "mo ta du lieu",
        "thong ke tong quat", "bao cao tong hop",
        "kiem tra du lieu", "bao cao tu dong",
    ],
}


# ══════════════════════════════════════════════════════════════════════
# 4. FOLLOW-UP KEYWORDS
#    Nhận diện query chỉnh sửa kết quả trước (không tạo mới).
# ══════════════════════════════════════════════════════════════════════
VI_FOLLOW_UP_KEYWORDS: list[str] = [
    # Đổi / Sửa
    "doi thanh", "doi sang", "doi mau", "doi mau thanh",
    "sua thanh", "sua lai", "sua sang",
    "thay doi", "thay bang", "thay the",
    "chinh sua", "chinh lai",
    "doi title", "sua title", "chinh title",
    "doi ten", "sua ten truc",
    "doi truc", "doi truc x", "doi truc y",
    # Thêm
    "them vao", "them nhan", "them label",
    "them chu thich", "them legend",
    "them truong", "them cot", "them dong",
    "them nhan truc", "them gia tri",
    # Xóa
    "xoa di", "xoa bot", "xoa truong",
    "bo di", "bo bot", "bo truong",
    # Hành động trên kết quả trước
    "lam lai", "ve lai", "tao lai", "thu lai",
    "giong tren", "tuong tu vay", "giong vay",
    "tiep tuc", "con lai", "cai vua roi", "bieu do tren",
    "bien thanh", "chuyen thanh", "doi sang dang",
    # Màu
    "mau do", "mau xanh", "mau vang", "mau tim",
    "mau cam", "mau xanh la", "mau xanh duong",
    "mau trang", "mau den", "mau hong",
    "mau sac", "doi mau sac",
    # Sắp xếp
    "sap xep", "sap xep lai", "sap xep theo",
    "tang dan", "giam dan", "theo thu tu",
    "theo abc", "theo gia tri",
    # Layout / Kích thước
    "co chu", "font size", "kich thuoc",
    "ngang", "doc", "chinh ngang", "chinh doc",
    "phong to", "thu nho",
    # Định dạng số
    "them phan tram", "them don vi",
    "2 chu so thap phan", "lam tron",
]


# ══════════════════════════════════════════════════════════════════════
# 5. TOKEN SYNONYMS (cho semantic column matching)
#    Format: "canonical_key": {set of synonyms including key itself}
# ══════════════════════════════════════════════════════════════════════
VI_TOKEN_SYNONYMS: dict[str, set[str]] = {

    # ── Tài chính / Kinh doanh ────────────────────────────────────────
    "revenue":     {"revenue", "doanh thu", "dt", "ban hang", "net sales", "gmv"},
    "profit":      {"profit", "loi nhuan", "ln", "earnings", "thu nhap rong"},
    "cost":        {"cost", "chi phi", "cp", "gia von", "cogs", "opex", "expense"},
    "price":       {"price", "gia", "don gia", "dg", "gia ban", "unit price"},
    "discount":    {"discount", "giam gia", "gg", "chiet khau", "ck"},
    "sales":       {"sales", "doanh thu", "ban hang", "dt"},
    "amount":      {"amount", "gia tri", "gt", "so tien", "tien"},
    "margin":      {"margin", "bien loi nhuan", "ty suat loi nhuan", "bien"},
    "growth":      {"growth", "tang truong", "toc do tang", "rate of growth"},
    "target":      {"target", "muc tieu", "mt", "ke hoach", "chi tieu", "plan"},
    "budget":      {"budget", "ngan sach", "ns", "du toan"},
    "expense":     {"expense", "chi phi", "cp", "chi tieu"},
    "income":      {"income", "thu nhap", "tn", "doanh thu"},
    "tax":         {"tax", "thue", "vat"},
    "invoice":     {"invoice", "hoa don", "hd"},
    "order":       {"order", "don hang", "ddh", "don dat hang"},
    "contract":    {"contract", "hop dong", "hdh"},

    # ── Thống kê / Phân tích ──────────────────────────────────────────
    "count":       {"count", "so luong", "sl", "dem", "bao nhieu", "quantity"},
    "total":       {"total", "tong", "tong cong", "sum"},
    "avg":         {"avg", "average", "mean", "trung binh", "gia tri trung binh"},
    "sum":         {"sum", "tong", "tong cong", "total"},
    "min":         {"min", "minimum", "thap nhat", "nho nhat"},
    "max":         {"max", "maximum", "cao nhat", "lon nhat"},
    "rate":        {"rate", "ty le", "tl", "phan tram", "%", "ratio"},
    "ratio":       {"ratio", "ty le", "tl", "ti le", "ty trong"},
    "score":       {"score", "diem", "diem so", "ket qua"},
    "rank":        {"rank", "hang", "xep hang", "vi tri", "thu hang"},
    "percentage":  {"percentage", "phan tram", "ty le", "%"},
    "quantity":    {"quantity", "so luong", "sl", "qty", "dem"},

    # ── Thời gian ─────────────────────────────────────────────────────
    "date":        {"date", "ngay", "ngay thang", "ngay thang nam"},
    "time":        {"time", "gio", "thoi gian", "thoi diem"},
    "year":        {"year", "nam", "nam hoc", "nam tai chinh"},
    "month":       {"month", "thang"},
    "quarter":     {"quarter", "quy"},
    "week":        {"week", "tuan"},
    "day":         {"day", "ngay"},
    "hour":        {"hour", "gio"},
    "period":      {"period", "ky", "giai doan", "thoi ky"},
    "season":      {"season", "mua"},

    # ── Tổ chức / Nhân sự ─────────────────────────────────────────────
    "customer":    {"customer", "khach hang", "kh", "client", "nguoi mua"},
    "employee":    {"employee", "nhan vien", "nv", "staff", "nhan su"},
    "product":     {"product", "san pham", "sp", "hang hoa", "hh", "item"},
    "category":    {"category", "danh muc", "loai", "nhom", "phan loai", "nhom hang"},
    "branch":      {"branch", "chi nhanh", "cn", "van phong"},
    "region":      {"region", "vung", "khu vuc", "mien", "zone"},
    "department":  {"department", "phong ban", "pb", "bo phan"},
    "store":       {"store", "cua hang", "diem ban", "showroom"},
    "supplier":    {"supplier", "nha cung cap", "ncc", "vendor"},
    "channel":     {"channel", "kenh", "kenh ban", "kenh phan phoi"},
    "segment":     {"segment", "phan khuc", "nhom khach hang", "tier"},

    # ── Logistics / Kho ───────────────────────────────────────────────
    "inventory":   {"inventory", "ton kho", "kho", "luong ton", "stock"},
    "stock":       {"stock", "hang ton", "ton kho", "luong ton"},
    "import":      {"import", "nhap", "nhap khau", "nk"},
    "export":      {"export", "xuat", "xuat khau", "xk"},
    "delivery":    {"delivery", "giao hang", "van chuyen", "ship"},
    "warehouse":   {"warehouse", "kho hang", "kho"},

    # ── Thời tiết (giữ lại từ bản gốc) ───────────────────────────────
    "temp":        {"temp", "temperature", "nhiet", "nhiet do"},
    "temperature": {"temperature", "temp", "nhiet", "nhiet do"},
    "humidity":    {"humidity", "humid", "do am"},
    "wind":        {"wind", "gio"},
    "windspeed":   {"windspeed", "wind speed", "toc do gio", "gio"},
    "speed":       {"speed", "toc do"},
    "weather":     {"weather", "thoi tiet"},

    # ── Kỹ thuật / Dữ liệu ────────────────────────────────────────────
    "id":          {"id", "ma", "ma so", "ma id", "so id"},
    "code":        {"code", "ma", "ma code", "ma so"},
    "status":      {"status", "trang thai", "tinh trang"},
    "type":        {"type", "loai", "kieu", "dang"},
    "value":       {"value", "gia tri", "gt"},
    "name":        {"name", "ten", "ten goi"},
    "description": {"description", "mo ta", "ghi chu"},
    "salary":      {"salary", "luong", "thu nhap", "muc luong"},
    "age":         {"age", "tuoi", "do tuoi"},
    "gender":      {"gender", "gioi tinh", "sex"},

    # ── Đơn vị ────────────────────────────────────────────────────────
    "pct":         {"pct", "percent", "phan tram", "%"},
    "kmh":         {"kmh", "km h", "km/h"},
    "usd":         {"usd", "dollar", "do la"},
    "vnd":         {"vnd", "dong", "viet nam dong"},
}
