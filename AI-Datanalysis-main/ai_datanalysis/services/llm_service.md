# llm_service.py — LLM Service

Tầng dịch vụ duy nhất quản lý toàn bộ pipeline phân tích dựa trên LLM.
Mọi logic liên quan đến khởi tạo model và chạy phân tích đều đi qua đây.

---

## Mục đích

| Vấn đề trước đây | Giải pháp |
|------------------|-----------|
| `app.py` import trực tiếp `DataAnalysisAgent`, `AgentConfig`, `build_llm`, `build_executor` | Tất cả gom về `llm_service.py` |
| Thay provider LLM cần sửa `app.py` | Chỉ cần sửa `llm_service.py` |
| Khó test vì agent tạo trực tiếp trong app | Inject qua `build_agent()` dễ mock |

---

## Phụ thuộc nội bộ

```
llm_service.py
  ├── ai_datanalysis.llm_factory          → build_llm() (Groq factory)
  ├── ai_datanalysis.core.agent           → DataAnalysisAgent, AgentConfig
  ├── ai_datanalysis.core.executors       → build_executor()
  └── ai_datanalysis.services.dashboard_service → build_dashboard_report()
```

---

## API

### `build_llm(model_override=None) → LangChain ChatModel`

Khởi tạo LLM theo provider trong env var `LLM_PROVIDER`.

```python
from ai_datanalysis.services.llm_service import build_llm

llm = build_llm()                          # dùng GROQ_MODEL mặc định
llm = build_llm("llama-3.3-70b-versatile") # override model Groq
```

**Env vars liên quan:**

| Var | Mô tả |
|-----|-------|
| `LLM_PROVIDER` | `groq` |
| `GROQ_API_KEY` | API key nếu dùng Groq |
| `LLM_TEMPERATURE` | Float, mặc định `0.0` |

---

### `build_executor() → Executor`

Khởi tạo sandbox thực thi code.

```python
from ai_datanalysis.services.llm_service import build_executor

executor = build_executor()  # local (mặc định) hoặc e2b
```

**Env vars:**

| Var | Mô tả |
|-----|-------|
| `EXECUTOR_BACKEND` | `local` (mặc định) hoặc `e2b` |
| `E2B_API_KEY` | Bắt buộc nếu dùng `e2b` |

---

### `build_agent(llm, executor, max_attempts=3) → DataAnalysisAgent`

Tạo agent từ LLM và executor đã build sẵn.

```python
from ai_datanalysis.services.llm_service import build_agent

agent = build_agent(llm=llm, executor=executor, max_attempts=3)
```

**Pattern dùng với `st.cache_resource`:**

```python
@st.cache_resource
def _get_llm(model_name: str = ""):
    return build_llm(model_override=model_name or None)

@st.cache_resource
def _get_executor():
    return build_executor()

# Per-rerun (nhẹ, an toàn)
agent = build_agent(llm=_get_llm(model), executor=_get_executor())
```

---

### `run_analysis(agent, query, data, ...) → ExecOutcome`

Chạy toàn bộ pipeline phân tích 5 bước.

```python
from ai_datanalysis.services.llm_service import run_analysis

outcome = run_analysis(
    agent=agent,
    query="Vẽ biểu đồ doanh thu theo tháng",
    data={"sales": df_sales},
    history=[{"role": "user", "content": "..."}],
    language="vi",
    privacy=True,
    sample=0,
    scope="alice",
)

if outcome.ok:
    result = outcome.result   # go.Figure | pd.DataFrame | str
else:
    error = outcome.error     # str mô tả lỗi
```

**Pipeline 5 bước:**
1. Normalize + Route query
2. Select datasets liên quan
3. Build prompt ngữ nghĩa
4. LLM sinh code Python
5. Thực thi an toàn trong sandbox

---

### `run_dashboard(data, role="analyst", goal="") → dict`

Sinh dashboard tự động không dùng LLM.

```python
from ai_datanalysis.services.llm_service import run_dashboard

report = run_dashboard(
    data={"sales": df_sales, "products": df_products},
    role="ceo",
    goal="Xem tổng quan doanh thu Q1",
)
# report["__type__"] == "dashboard_report"
```

**Roles:** `analyst`, `ceo`, `cfo`, `finance_manager`, `sales`, `marketing`, `operations`

---

## Luồng trong app.py

```
app.py
  ├── _get_llm()      → build_llm()       [st.cache_resource]
  ├── _get_executor() → build_executor()  [st.cache_resource]
  ├── build_agent()                       [per-rerun]
  ├── run_analysis()  → agent.run_pipeline()
  └── run_dashboard() → build_dashboard_report()
```
