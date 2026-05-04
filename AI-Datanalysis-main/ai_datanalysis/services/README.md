# ai_datanalysis/services — Tầng dịch vụ

Chứa toàn bộ business logic phía sau pipeline. Mỗi service có trách nhiệm rõ ràng, không overlap.

---

## Danh sách services

| File | Vai trò | Phụ thuộc Streamlit? |
|------|---------|----------------------|
| `llm_service.py` | Khởi tạo LLM, chạy pipeline phân tích, tạo dashboard | Không |
| `data_service.py` | Upload, lưu, nạp dataset; phân tích quan hệ bảng | `@st.cache_data` (OK) |
| `chart_service.py` | Xây dựng biểu đồ Plotly và KPI thuần túy | **Không** |
| `retrieval_service.py` | Chuẩn hóa query, phân loại intent, chọn dataset | Không |
| `chat_service.py` | Lưu/nạp lịch sử chat theo user | Không |
| `dashboard_service.py` | Tự động sinh dashboard từ dữ liệu (không LLM) | Không |
| `ops_service.py` | Logging, rate limiting, audit trail, bảo trì DB | Không |
| `render_service.py` | **Deprecated** — re-export từ `ui/render.py` | — |

---

## Kiến trúc tầng

```
app.py  (UI orchestration)
    │
    ├── llm_service.py      → build_llm, build_agent, run_analysis, run_dashboard
    ├── data_service.py     → load_files, save_user_files, load_user_data, build_catalog
    ├── chart_service.py    → build_bar_chart, build_kpi_summary, prepare_result_for_render
    ├── retrieval_service.py → normalize_query, route_query, select_datasets
    ├── chat_service.py     → lịch sử hội thoại
    └── ops_service.py      → rate limit, audit, logging

ui/render.py  (Streamlit rendering)
    │
    └── render_result()     ← nhận output từ llm_service / chart_service
```

---

## Quy tắc

1. **Services không import nhau** (ngoại trừ `llm_service` import `dashboard_service`).
2. **Services không gọi `st.*`** — ngoại trừ `@st.cache_data` trong `data_service` (decorator hiệu năng, chấp nhận được).
3. **Mọi `st.plotly_chart`, `st.metric`, `st.write`** đều nằm trong `ui/render.py` hoặc `ui/components.py`.
4. **`app.py` là điểm duy nhất** kết nối UI với services.

---

## llm_service.py

**Khởi tạo và chạy LLM pipeline.**

```python
from ai_datanalysis.services.llm_service import build_llm, build_executor, build_agent, run_analysis, run_dashboard
```

Chi tiết: [llm_service.md](llm_service.md)

---

## data_service.py

**Quản lý vòng đời dữ liệu.**

```python
from ai_datanalysis.services.data_service import load_files, save_user_files, load_user_data, clear_user_data, build_catalog
```

Chi tiết: [data_service.md](data_service.md)

---

## chart_service.py

**Xây dựng biểu đồ và KPI (không Streamlit).**

```python
from ai_datanalysis.services.chart_service import build_bar_chart, build_kpi_summary, prepare_result_for_render
```

Chi tiết: [chart_service.md](chart_service.md)

---

## retrieval_service.py

**Pipeline hiểu query và chọn dữ liệu.**

```python
from ai_datanalysis.services.retrieval_service import normalize_query, route_query, select_datasets, retrieve_context
```

Chi tiết: [retrieval_service.md](retrieval_service.md)

---

## chat_service.py

**Lưu trữ lịch sử chat nhiều conversation per user.**

```python
from ai_datanalysis.services.chat_service import (
    create_chat_history, save_chat_history, load_chat_history,
    list_chat_histories, set_active_chat_history, clear_chat_history,
)
```

Lưu trữ: `data/runtime/chat_history/{username}.json`

---

## dashboard_service.py

**Sinh dashboard tự động không cần LLM.**

```python
from ai_datanalysis.services.dashboard_service import build_dashboard_report
# Thường gọi qua llm_service.run_dashboard() thay vì trực tiếp
```

Kích hoạt khi query chứa: `"dashboard"`, `"bao cao"`, `"report"`.

---

## ops_service.py

**Hạ tầng vận hành.**

```python
from ai_datanalysis.services.ops_service import (
    configure_logging, consume_rate_limit, audit_query, record_metric,
    init_ops_db, run_maintenance,
)
```

Lưu trữ: MySQL (`rate_limit_events`, `query_audit`, `app_metrics`).

---

## render_service.py (Deprecated)

File này chỉ còn là wrapper backward-compatible:

```python
# Cũ (vẫn hoạt động)
from ai_datanalysis.services.render_service import render_result

# Mới (ưu tiên dùng)
from ai_datanalysis.ui.render import render_result
```

Logic render đã chuyển về `ui/render.py`.

---

## Dependency map

```
llm_service.py
  ├── llm_factory.py
  ├── core/agent.py
  ├── core/executors.py
  └── services/dashboard_service.py

data_service.py
  ├── services/dataset_service.py
  └── core/data_catalog.py

chart_service.py
  └── (chỉ pandas + plotly)

retrieval_service.py
  ├── core/normalization.py
  ├── core/router.py
  ├── core/selector.py
  └── core/semantic_columns.py

chat_service.py
  └── paths.py

ops_service.py
  └── (sqlalchemy + logging)

dashboard_service.py
  └── core/data_catalog.py
```
