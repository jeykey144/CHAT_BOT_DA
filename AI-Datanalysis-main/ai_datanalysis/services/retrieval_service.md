# retrieval_service.py — Retrieval Service

Tầng dịch vụ cho toàn bộ pipeline hiểu và truy vấn dữ liệu: chuẩn hóa, phân loại intent, chọn dataset, khớp cột ngữ nghĩa.

---

## Mục đích

| Vấn đề trước đây | Giải pháp |
|------------------|-----------|
| `app.py` import trực tiếp từ `core/normalization`, `core/router`, `core/selector` | Gom về `retrieval_service.py` |
| Không có module "retrieval" theo đúng kiến trúc | Module rõ ràng, đúng tên |
| Phải gọi 3-4 hàm riêng để xử lý một query | Hàm `retrieve_context()` tổng hợp |

---

## Phụ thuộc nội bộ

```
retrieval_service.py
  ├── ai_datanalysis.core.normalization    → normalize_query()
  ├── ai_datanalysis.core.router          → route_query(), RouterOutcome
  ├── ai_datanalysis.core.selector        → select_datasets()
  └── ai_datanalysis.core.semantic_columns → score_query_to_column(), get_semantic_type()
```

---

## API

### `normalize_query(text) → str`

Chuẩn hóa query tiếng Việt: bỏ dấu, lowercase, collapse whitespace.

```python
from ai_datanalysis.services.retrieval_service import normalize_query

normalize_query("Phân Tích Doanh Thu Theo Tháng")
# → "phan tich doanh thu theo thang"
```

**Quy trình:**
1. `unicodedata.normalize('NFD')` — tách dấu thành combining chars
2. Lọc category `Mn` (combining marks)
3. `encode('ascii', 'ignore')` — bỏ ký tự non-ASCII
4. `lower()` + collapse whitespace

---

### `route_query(query, data) → RouterOutcome`

Phân loại intent và loại biểu đồ phù hợp.

```python
from ai_datanalysis.services.retrieval_service import route_query

route = route_query("ve bieu do doanh thu theo thang", data)

route.normalized_query        # str: query đã normalize
route.intents                 # list[str]: ["trend", "comparison"]
route.graph_type              # str: "line_plot"
route.is_follow_up            # bool: False
route.requires_multi_dataset  # bool: False
```

**graph_type có thể nhận:**

| Giá trị | Kích hoạt khi query chứa |
|---------|--------------------------|
| `line_plot` | biểu đồ đường, xu hướng, trend |
| `bar_plot` | biểu đồ cột, bar chart |
| `histogram_plot` | phân phối, histogram, tần suất |
| `scatter_2d_plot` | phân tán, scatter |
| `pie_plot` | biểu đồ tròn, tỷ lệ |
| `heatmap` | heatmap, ma trận tương quan |
| `box_plot` | box plot, boxplot |
| `auto_profile` | phân tích, khám phá, tổng quan |
| `table` | mặc định |

---

### `select_datasets(query, data, max_datasets=2) → Dict[str, pd.DataFrame]`

Chọn tập con dataset liên quan nhất đến query.

```python
from ai_datanalysis.services.retrieval_service import select_datasets

selected = select_datasets(
    "doanh thu san pham",
    data={"sales": df_s, "products": df_p, "employees": df_e},
    max_datasets=2,
)
# {"sales": df_s, "products": df_p}  — bỏ employees không liên quan
```

**Scoring:**
```
score(dataset) =
    tên_dataset_khớp_query × 2
  + số_cột_khớp_query × 1
  + số_cột_ID_chung_với_dataset_khác × 0.5
```

---

### `score_query_to_column(query, column_name) → float`

Đánh giá mức độ liên quan giữa query và tên cột.

```python
from ai_datanalysis.services.retrieval_service import score_query_to_column

score_query_to_column("doanh thu", "revenue")      # → float > 0
score_query_to_column("doanh thu", "employee_id")  # → 0.0
```

---

### `column_semantic_hint(column_name) → str`

Sinh gợi ý ngữ nghĩa cho tên cột (dùng trong prompt building).

```python
from ai_datanalysis.services.retrieval_service import column_semantic_hint

column_semantic_hint("revenue")   # → "revenue -> revenue / doanh thu, tong, ..."
column_semantic_hint("created_at") # → "created_at -> created at"
```

---

### `retrieve_context(query, data, max_datasets=2) → dict`

**Hàm tổng hợp** — chạy toàn bộ pipeline truy vấn trong một lần gọi.

```python
from ai_datanalysis.services.retrieval_service import retrieve_context

ctx = retrieve_context(
    query="Vẽ biểu đồ doanh thu theo tháng",
    data={"sales": df_s, "products": df_p},
)

ctx["normalized_query"]   # "ve bieu do doanh thu theo thang"
ctx["route"].graph_type   # "line_plot"
ctx["selected_data"]      # {"sales": df_s}
```

**Tự động mở rộng max_datasets lên 3** khi query chứa từ join/merge/kết hợp.

---

## Luồng trong pipeline

```
User query
    │
    ▼
normalize_query()          → chuẩn hóa text
    │
    ▼
route_query()              → intent + graph_type
    │
    ▼
select_datasets()          → chọn bảng liên quan
    │
    ▼
[core/agent.py tiếp tục]   → build prompt → LLM → execute
```
