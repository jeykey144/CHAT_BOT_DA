# ai_datanalysis/core — AI Pipeline

Tầng xử lý trí tuệ của hệ thống. Nhận query ngôn ngữ tự nhiên, chọn dữ liệu phù hợp, sinh code Python qua LLM, thực thi an toàn trong sandbox và trả về kết quả.

---

## Tổng quan — 5-Step Pipeline

```
Query đầu vào
     │
     ▼
[1] NORMALIZE + ROUTE           router.py, normalization.py
     Chuẩn hóa text, phát hiện intent, loại biểu đồ, follow-up
     │
     ▼
[2] DATASET SELECTION           selector.py, data_catalog.py, join_planner.py
     Chọn bảng dữ liệu liên quan nhất; phát hiện quan hệ join
     │
     ├── Fast-path?  ──[Yes]──→ fast_path.py → execute → kết quả
     │   (query đơn giản)
     │
     ▼ [No]
[3] PROMPT BUILDING             prompt_builder.py, semantic_columns.py
     Xây prompt theo template loại biểu đồ + schema ngữ nghĩa
     │
     ▼
[4] LLM CODE GENERATION         agent.py, cache.py
     Gọi LLM → extract code → validate syntax → retry nếu lỗi
     │
     ▼
[5] SAFE EXECUTION              executors.py
     AST check → chạy trong sandbox → trả ExecOutcome
```

---

## Các module

### agent.py — Orchestrator pipeline

**Class:** `DataAnalysisAgent`

**Vai trò:** Điều phối toàn bộ 5 bước, quản lý retry loop và heuristic fixes.

**Config:**
```python
@dataclass
class AgentConfig:
    max_attempts: int = 3   # số lần retry tối đa khi code thất bại
```

**Method chính:**

```python
agent.run_pipeline(
    query: str,
    data: Dict[str, pd.DataFrame],
    history: list = None,       # lịch sử chat (tối đa 6 tin nhắn gần nhất)
    language: str = "vi",       # ngôn ngữ prompt: "vi" hoặc "en"
    privacy: bool = True,       # True = không gửi sample rows lên LLM
    sample: int = 5,            # số dòng mẫu gửi kèm nếu privacy=False
    scope: str = "global",      # user scope cho cache
) -> ExecOutcome
```

**Retry logic trong `_execute_with_retries()`:**
```
Attempt N:
  1. Validate dataset aliases (DF_1..DF_N)?   → LLM fix nếu sai
  2. Validate Python syntax (AST.parse)?       → LLM fix nếu sai
  3. Execute in sandbox
  4. Nếu lỗi runtime:
     a. Thử heuristic fix (_heuristic_fix)
     b. Nếu không fix được → reprompt LLM với error message
  5. Lặp đến max_attempts
```

**Heuristic fixes tự động (không cần LLM):**
- `KeyError`: tìm tên cột đúng (case-insensitive) và thay thế
- `AttributeError: sortvalue` → `.sort_values()`
- `AttributeError: drop_duplicate` → `.drop_duplicates()`
- `NameError: is_numeric_dtype` → `pd.api.types.is_numeric_dtype(`
- `NameError: is_datetime64_any_dtype` → `pd.api.types.is_datetime64_any_dtype(`

**Code extraction:** Hỗ trợ output có/không có markdown fence:
```python
# LLM trả về ```python ... ``` hoặc ``` ... ``` hoặc raw code
code = DataAnalysisAgent._extract_code(llm_response)
```

---

### router.py — Intent Router

**Vai trò:** Phân tích query để xác định: ý định người dùng, loại output phù hợp, có phải follow-up không, có cần join nhiều bảng không.

**Output — `RouterOutcome`:**

```python
router_out.normalized_query     # str: query đã normalize
router_out.intents              # List[str]: ["calculation", "ranking", ...]
router_out.graph_type           # str: "bar_plot" | "line_plot" | "table" | ...
router_out.is_follow_up         # bool: True nếu câu hỏi sửa kết quả trước
router_out.requires_multi_dataset  # bool: True nếu có từ "join/merge/kết hợp"
```

**Tất cả `graph_type` có thể:**

| graph_type | Trigger keywords |
|------------|-----------------|
| `line_plot` | line chart, biểu đồ đường, xu hướng |
| `bar_plot` | bar chart, biểu đồ cột |
| `scatter_2d_plot` | scatter, phân tán |
| `histogram_plot` | histogram, phân phối, tần suất |
| `heatmap` | heatmap, ma trận |
| `box_plot` | box plot, boxplot |
| `violin_plot` | violin |
| `area_plot` | area chart, biểu đồ miền |
| `pie_plot` | pie chart, biểu đồ tròn, bánh |
| `bubble_plot` | bubble chart, bong bóng |
| `candle_plot` | candlestick, biến động giá, nến |
| `density_contour_plot` | density plot, mật độ |
| `polar_plot` | polar chart, radar |
| `sunburst_plot` | sunburst |
| `treemap_plot` | treemap, tree map |
| `auto_profile` | phân tích, khám phá, tổng quan, profile |
| `table` | mặc định nếu không khớp biểu đồ nào |
| `generic_plot` | có yêu cầu vẽ biểu đồ nhưng không rõ loại |

**Intent được phát hiện:**
`calculation`, `filter`, `comparison`, `ranking`, `trend`, `distribution`, `relationship`, `composition`, `join`, `general`

---

### normalization.py — Chuẩn hóa query

**Vai trò:** Chuyển tiếng Việt có dấu thành không dấu, lowercase, normalize whitespace. Giúp keyword matching nhất quán.

```python
from ai_datanalysis.core.normalization import normalize_query

normalize_query("Phân tích Doanh Thu")
# → "phan tich doanh thu"
```

**Quy trình:**
1. `unicodedata.normalize('NFD', text)` — tách dấu thành combining characters
2. Lọc bỏ `Mn` category (combining marks)
3. `encode('ascii', 'ignore').decode('ascii')` — bỏ ký tự non-ASCII
4. `lower()` + collapse whitespace

---

### selector.py — Dataset Selector

**Vai trò:** Khi user upload nhiều bảng, chọn ra tập con liên quan nhất đến query hiện tại (mặc định tối đa 2 bảng).

**Thuật toán scoring:**

```
score(dataset) =
    tên_dataset_khớp_query × 2
  + số_cột_khớp_query × 1
  + số_cột_ID_chung_với_dataset_khác × 0.5
```

- So sánh sau khi normalize (bỏ dấu, lowercase, split theo `_`, số)
- Nếu query có từ join/merge/kết hợp: `max_datasets = 3`
- Nếu chỉ 1 dataset: trả về ngay không tính điểm

---

### data_catalog.py — Data Catalog & Master Tables

**Vai trò:** Phân tích toàn bộ dữ liệu đã upload, phát hiện quan hệ giữa các bảng và tạo master tables (join sẵn).

**Hàm chính:**

```python
catalog = build_data_catalog(data: Dict[str, pd.DataFrame])
# catalog = {
#   "overview": {"dataset_count": 2, "recommended_join_count": 1, ...},
#   "relationships": [{"left_dataset": "...", "left_key": "id",
#                       "right_dataset": "...", "right_key": "id",
#                       "confidence": 0.9, "overlap_ratio": 0.95}],
#   "master_tables": [{"name": "...", "sources": [...], ...}],
#   "table_roles": {"sales": "fact", "product": "dimension"},
# }

analysis_data, catalog, context = prepare_analysis_bundle(query, selected_data)
# analysis_data: dict bao gồm master tables nếu phù hợp
# context: string mô tả quan hệ cho LLM
```

**Phát hiện quan hệ:** So sánh các cột có tên dạng `*_id`, `id_*`, `*_code` giữa các bảng; tính `overlap_ratio` để xác định mức độ tin cậy.

---

### prompt_builder.py — Prompt Builder

**Vai trò:** Xây dựng prompt hoàn chỉnh gửi đến LLM, bao gồm schema dữ liệu, lịch sử chat, template biểu đồ và hướng dẫn sinh code.

```python
prompt = build_prompt(
    question=query,
    data=data,
    selected_data=analysis_data,
    history=history,             # list[{"role": "user"|"assistant", "content": str}]
    language="vi",               # "vi" hoặc "en"
    privacy=True,                # không gửi sample data nếu True
    sample_rows=5,               # số dòng mẫu nếu privacy=False
    analysis_context=context,    # thông tin join từ data_catalog
)
```

**Nội dung prompt được xây:**
1. **System instruction**: Bạn là data analyst, sinh Python code, gán kết quả vào `result`
2. **Dataset schemas**: Mô tả ngữ nghĩa (numeric/categorical/datetime/id) thay vì dtype thô
3. **Sample rows** (nếu privacy=False): Tối đa `sample_rows` dòng đầu của mỗi bảng
4. **Join context**: Quan hệ giữa các bảng (từ data_catalog)
5. **Chart template**: Nội dung từ `prompts/chart_templates/<graph_type>.txt`
6. **Chat history**: Tối đa 6 tin nhắn gần nhất (để xử lý follow-up)
7. **User question**: Câu hỏi gốc

**Biến trong sandbox:**
- `DF_1`, `DF_2`, ..., `DF_N` — tương ứng với `analysis_data.values()`
- `result` — biến bắt buộc phải gán kết quả cuối

---

### semantic_columns.py — Nhãn ngữ nghĩa cột

**Vai trò:** Phân loại cột thành nhóm ngữ nghĩa (`numeric`, `categorical`, `datetime`, `id`) thay vì gửi dtype thô cho LLM. Giảm token và tăng chất lượng code sinh ra.

```python
from ai_datanalysis.core.semantic_columns import score_query_to_column

# Trả về điểm relevance giữa query và tên cột
score = score_query_to_column("doanh thu", "revenue")  # → float
```

**Phân loại cột:**
- `id`: tên chứa `id`/`code`, hoặc uniqueness_ratio ≥ 95%, hoặc toàn số nguyên tăng dần
- `datetime`: tên chứa `date`/`time`/`year`/`month`, hoặc dtype datetime
- `numeric`: `pd.api.types.is_numeric_dtype()` và không phải id/datetime
- `categorical`: còn lại

---

### executors.py — Code Execution Sandbox

**Vai trò:** Thực thi code Python do LLM sinh ra trong môi trường bị giới hạn. Ngăn chặn truy cập file system, subprocess, reflection và các thao tác nguy hiểm khác.

**Class:** `LocalRestrictedExecutor`

```python
executor = LocalRestrictedExecutor()
outcome: ExecOutcome = executor.run(code, [df1, df2])
# outcome.ok      → bool
# outcome.result  → pd.DataFrame | go.Figure | str | None
# outcome.error   → str | None
```

**Lớp bảo vệ 1 — AST validation (trước khi chạy):**

Tất cả `Import`/`ImportFrom` node được cho phép pass (runtime sẽ chặn), nhưng các node sau bị từ chối:

```python
banned_names = {
    "__import__", "eval", "exec", "compile", "globals", "locals",
    "open", "input", "help", "dir", "getattr", "setattr", "delattr",
    "vars", "breakpoint"
}
banned_attrs = {
    "__class__", "__bases__", "__mro__", "__subclasses__",
    "__globals__", "__code__", "__getattribute__"
}
banned_call_attrs = {
    "read_csv", "read_excel", "read_parquet", "read_json", "read_pickle",
    "to_csv", "to_excel", "to_parquet", "to_json", "to_pickle",
    "savefig",   # matplotlib file write
    "save",      # openpyxl/PIL file write
}
```

**Lớp bảo vệ 2 — Restricted builtins (lúc exec):**

Thay `__builtins__` bằng dict chỉ chứa các hàm an toàn:
```python
# Có: abs, all, any, bool, chr, dict, enumerate, float, format, hash,
#     hex, int, len, list, map, max, min, oct, ord, pow, print, range,
#     repr, round, set, slice, sorted, str, sum, tuple, zip
#     isinstance, issubclass, type, callable, filter, next, iter, reversed
#     Exception, ValueError, TypeError, KeyError, IndexError, ...
# Không có: open, eval, exec, compile, breakpoint, ...
```

**Lớp bảo vệ 3 — Restricted imports (runtime):**

```python
allowed_imports = {
    "math", "statistics", "datetime", "json", "re",
    "numpy", "pandas", "plotly", "plotly.express", "plotly.graph_objects",
    "scipy", "statsmodels", "sklearn",
    "openpyxl", "xlsxwriter", "matplotlib", "matplotlib.pyplot", "seaborn"
}
# import subprocess → ImportError
# import os         → ImportError
```

**Environment khi exec:**
```python
env = {
    "__builtins__": safe_builtins,
    "pd": pd, "np": np, "go": go, "px": px,
    "DF_1": df1, "DF_2": df2, ...
}
```

**Lấy kết quả:** Sau exec, tìm biến `result` trong `context` dict.

**E2BExecutor:** Alternative executor chạy code trong sandbox cloud (E2B). Cấu hình qua `EXECUTOR_BACKEND=e2b`.

---

### cache.py — Query Cache

**Vai trò:** Cache 2 tầng: (1) code Python đã sinh, (2) kết quả thực thi. Tránh gọi LLM lặp lại cho cùng query + cùng dữ liệu.

**Cache key:** SHA256 của `f"{normalized_query}###{schema_fingerprint}"`

Trong đó `schema_fingerprint` = SHA256 của hash từng DataFrame (shape + columns + dtypes + row hashes).

**Lưu trữ:**
- Code: `data/runtime/cache/code/<hash>.py`
- Results: `data/runtime/cache/results/<hash>.json`

**Serialization kết quả:**
- `pd.DataFrame` → JSON (orient="split")
- `go.Figure` → JSON (plotly JSON format)
- `str` → JSON string

**Bảo vệ cache:** Trước khi cache code, dùng AST parsing để từ chối code có chứa `read_csv`, `read_excel`, `open` (tránh cache code đọc file hardcode).

---

### fast_path.py — Fast-path Executor

**Vai trò:** Sinh code trực tiếp (không qua LLM) cho các query đơn giản và có thể dự đoán. Giảm latency và chi phí API.

**Điều kiện kích hoạt:** `router_out.graph_type in {"table", "auto_profile"}` và `not is_follow_up` và chỉ có 1 dataset.

**Query được xử lý fast-path:**

| Loại query | Ví dụ | Action |
|-----------|-------|--------|
| Auto-profile | "phân tích", "khám phá", "tổng quan" | Sinh profile report đầy đủ |
| Row count | "đếm", "so dong", "count" | `len(DF_1)` |
| Shape | "shape", "kích thước" | `DF_1.shape` |
| Top N | "top 5" | `DF_1.head(5)` |
| Min/Max | "nhỏ nhất", "lớn nhất" | `series.min()` / `series.max()` |
| Mean | "trung bình", "average" | `series.mean()` |
| Sum | "tổng", "sum", "total" | `series.sum()` |

**Auto-profile report** bao gồm:
- Schema từng cột: dtype, semantic type, missing %, unique count, min/max/mean/std
- Phát hiện cột ID-like (skip numeric stats)
- Phát hiện cột temporal (year, month, day range)
- Insights tự động + gợi ý phân tích tiếp theo

---

### join_planner.py — Join Planner

**Vai trò:** Phân tích xem query có yêu cầu join nhiều bảng không, và gợi ý chiến lược join cho LLM.

```python
from ai_datanalysis.core.join_planner import query_suggests_join

if query_suggests_join(normalized_query):
    max_datasets = 3  # Mở rộng dataset selection
```

Phát hiện các từ: `join`, `merge`, `kết hợp`, `liên kết`, `ghép bảng`, `nối bảng`, `combine`, `match`.

---

## Luồng dữ liệu qua các module

```
app.py
  └─ agent.run_pipeline(query, data)
       ├─ route_query(query)                  → router.py
       ├─ cache.get_result(...)               → cache.py
       ├─ select_datasets(query, data)        → selector.py
       ├─ query_suggests_join(query)          → join_planner.py
       ├─ prepare_analysis_bundle(query, sel) → data_catalog.py
       ├─ try_fast_path(query, sel)           → fast_path.py
       ├─ build_prompt(question, ...)         → prompt_builder.py
       │    └─ semantic hints                 → semantic_columns.py
       │    └─ normalize_query               → normalization.py
       ├─ llm.invoke([HumanMessage])
       ├─ _execute_with_retries(code, data)
       │    └─ executor.run(code, dfs)        → executors.py
       ├─ cache.set_code / cache.set_result   → cache.py
       └─ return ExecOutcome
```

---

## Thêm module mới vào pipeline

1. Tạo file `ai_datanalysis/core/my_module.py`
2. Import và gọi trong `agent.py:run_pipeline()` tại vị trí phù hợp
3. Viết test trong `tests/test_my_module.py`
