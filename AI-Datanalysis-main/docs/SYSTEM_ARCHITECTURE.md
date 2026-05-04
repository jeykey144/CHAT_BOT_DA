# Kiến trúc & Vận hành Hệ thống — AI-Datanalysis

> Tài liệu này mô tả tác dụng của **từng folder và từng file** đối với cách hệ thống vận hành.
> Đọc từ trên xuống để nắm flow tổng thể, hoặc tra cứu từng mục theo tên.

---

## Mục lục

1. [Sơ đồ tổng thể](#1-sơ-đồ-tổng-thể)
2. [Root — file gốc dự án](#2-root--file-gốc-dự-án)
3. [ai_datanalysis/ — package chính](#3-ai_datanalysis--package-chính)
4. [ai_datanalysis/core/ — tầng logic nghiệp vụ](#4-ai_datanalysiscore--tầng-logic-nghiệp-vụ)
5. [ai_datanalysis/services/ — tầng dịch vụ](#5-ai_datanalysisservices--tầng-dịch-vụ)
6. [ai_datanalysis/ui/ — tầng giao diện](#6-ai_datanalysisui--tầng-giao-diện)
7. [prompts/ — template prompt LLM](#7-prompts--template-prompt-llm)
8. [data/ — dữ liệu runtime](#8-data--dữ-liệu-runtime)
9. [assets/ — tài nguyên tĩnh](#9-assets--tài-nguyên-tĩnh)
10. [tests/ — bộ kiểm thử](#10-tests--bộ-kiểm-thử)
11. [scripts/ — tiện ích](#11-scripts--tiện-ích)
12. [notebooks/ — phân tích thử nghiệm](#12-notebooks--phân-tích-thử-nghiệm)
13. [.devcontainer/ — môi trường phát triển](#13-devcontainer--môi-trường-phát-triển)
14. [.streamlit/ — cấu hình Streamlit](#14-streamlit--cấu-hình-streamlit)
15. [.streamlit_cookies_component/ — component cookie](#15-streamlit_cookies_component--component-cookie)
16. [File cấu hình gốc](#16-file-cấu-hình-gốc)

---

## 1. Sơ đồ tổng thể

```
Người dùng (trình duyệt)
        │
        ▼
  Streamlit Server (app.py)
        │
        ├─► ui/components.py     — render form, upload, sidebar, action bar
        │
        ├─► services/            — public API duy nhất mà app.py gọi
        │      llm_service       — xây dựng LLM + chạy pipeline phân tích
        │      data_service      — load / lưu dataset người dùng
        │      retrieval_service — chuẩn hóa, phân loại intent, chọn dataset
        │      chat_service      — lưu / đọc lịch sử hội thoại
        │      ops_service       — logging, rate-limit, audit, metrics
        │
        └─► core/                — logic nghiệp vụ thuần (không import streamlit)
               normalization     → chuẩn hóa text
               router            → phân loại intent + loại biểu đồ
               selector          → chọn dataset liên quan
               prompt_builder    → ghép prompt cho LLM
               agent             → điều phối pipeline (fast-path → LLM → exec)
               executors         → sandbox thực thi code Python
               cache             → lưu kết quả tránh gọi LLM lặp lại
               fast_path         → sinh code không cần LLM cho query đơn giản
               semantic_columns  → khớp cột dữ liệu với ngữ nghĩa câu hỏi
               join_planner      → phát hiện nhu cầu join nhiều bảng
               data_catalog      → phân tích quan hệ giữa các bảng
```

**Nguyên tắc tầng:** `ui/` → `services/` → `core/`
- `ui/` là tầng **duy nhất** được phép gọi `st.*`
- `services/` là tầng **duy nhất** mà `app.py` được phép import
- `core/` không phụ thuộc vào Streamlit hay bất kỳ tầng nào phía trên

---

## 2. Root — file gốc dự án

Thư mục gốc dự án chứa các file cấu hình và một số file Python **legacy** (phiên bản cũ trước khi refactor thành package).

| File | Tác dụng vận hành |
|------|-------------------|
| `app.py` | **Legacy entry point** — bản gốc trước khi code chuyển vào `ai_datanalysis/`. Không còn được dùng để chạy. |
| `agent.py` | **Legacy** — bản gốc của `ai_datanalysis/core/agent.py`. |
| `auth.py` | **Legacy** — bản gốc của `ai_datanalysis/auth.py`. |
| `executors.py` | **Legacy** — bản gốc của `ai_datanalysis/core/executors.py`. |
| `llm_factory.py` | **Legacy** — bản gốc của `ai_datanalysis/llm_factory.py`. |
| `paths.py` | **Legacy** — bản gốc của `ai_datanalysis/paths.py`. |
| `secure_cookie_manager.py` | **Legacy** — bản gốc của `ai_datanalysis/secure_cookie_manager.py`. |
| `styles.py` | **Legacy** — bản gốc của `ai_datanalysis/styles.py`. |
| `pyproject.toml` | Khai báo dependencies (Poetry). Xác định thư viện được cài: `streamlit`, `langchain`, `plotly`, `pandas`, `sqlalchemy`, `cryptography`, v.v. |
| `poetry.lock` | Khóa phiên bản chính xác của toàn bộ dependency tree. Đảm bảo môi trường production giống development. |
| `.env` | Biến môi trường thực tế (API keys, DB URL). **Không commit lên git.** |
| `.env.example` | Mẫu `.env` cho người mới setup. Chứa tên biến nhưng không chứa giá trị thật. |
| `.gitignore` | Loại trừ `.env`, `.venv/`, `data/runtime/`, `__pycache__/` khỏi version control. |
| `README.md` | Tài liệu giới thiệu dự án, hướng dẫn cài đặt và chạy. |

---

## 3. ai_datanalysis/ — package chính

Đây là **package Python duy nhất** được deploy. Toàn bộ logic hệ thống nằm trong folder này.

### `ai_datanalysis/__init__.py`
Đánh dấu folder là Python package. Cho phép import theo dạng `from ai_datanalysis.xxx import yyy`.

### `ai_datanalysis/app.py` — Entry point thực sự
**Vai trò:** Khởi động toàn bộ ứng dụng Streamlit.

**Vận hành:**
1. Đọc `.env`, khởi tạo kết nối MySQL (`get_auth_engine()` — cached bằng `st.cache_resource`).
2. Khởi tạo database bảng auth + ops (`init_auth_db`, `init_ops_db`).
3. Kiểm tra session cookie → xác định user đang đăng nhập.
4. Nếu chưa login → render màn hình đăng nhập/đăng ký (`auth_main`).
5. Nếu đã login:
   - Render sidebar (thống kê data, cài đặt model, action buttons).
   - Load dataset người dùng đã upload trước đó (`load_user_data`).
   - Nhận câu hỏi qua chat input.
   - Kiểm tra rate limit (`consume_rate_limit`) → chặn nếu vượt quota.
   - Gọi `run_analysis(agent, query, data, history)` → nhận kết quả.
   - Render kết quả ra màn hình (`render_result`).
   - Lưu lịch sử chat (`save_chat_history`).
   - Ghi audit log (`audit_query`).

**Caching quan trọng:**
- `get_auth_engine()` — `@st.cache_resource`: tạo một lần, chia sẻ cho mọi user/session.
- `_get_llm(model_name)` — `@st.cache_resource`: mỗi model name tạo một LLM instance duy nhất.
- `_get_executor()` — `@st.cache_resource`: sandbox executor dùng chung.

### `ai_datanalysis/auth.py` — Xác thực người dùng
**Vai trò:** Quản lý đăng ký, đăng nhập, phiên làm việc qua MySQL.

**Vận hành:**
- **Mã hóa mật khẩu:** PBKDF2-HMAC-SHA256, 200.000 iterations, salt ngẫu nhiên 16 bytes.
- **Session token:** chuỗi ngẫu nhiên 32 bytes, lưu vào bảng `sessions` trong MySQL kèm `expires_at`.
- **Rate limiting đăng nhập:** gọi `consume_rate_limit` từ `ops_service` — chặn sau N lần thất bại trong cửa sổ thời gian.
- `init_auth_db(engine)` — tạo bảng `users` và `sessions` nếu chưa tồn tại.
- `get_session_username(engine, token)` — tra cứu token trong DB, trả về username nếu còn hạn.

### `ai_datanalysis/llm_factory.py` — Khởi tạo LLM
**Vai trò:** Xây dựng đối tượng LLM từ biến môi trường.

**Vận hành:**
- Đọc `LLM_PROVIDER` (openai / anthropic / groq / google) từ `.env`.
- Dựa theo provider, khởi tạo đúng LangChain client: `ChatOpenAI`, `ChatAnthropic`, `ChatGroq`, `ChatGoogleGenerativeAI`.
- Áp dụng cấu hình riêng cho từng Groq model (max_tokens, timeout).
- Không nhận API key từ UI — chỉ đọc từ env vars để đảm bảo bảo mật.

**Models được cấu hình sẵn (Groq):**
| Model | Max tokens | Timeout |
|-------|-----------|---------|
| llama-3.1-8b-instant | 2048 | 30s |
| llama-3.3-70b-versatile | 2048 | 60s |
| deepseek-r1-distill-llama-70b | 4096 | 90s |

### `ai_datanalysis/paths.py` — Quản lý đường dẫn
**Vai trò:** Nguồn sự thật duy nhất cho mọi đường dẫn file/folder trong hệ thống.

**Vận hành:**
- Định nghĩa toàn bộ path constants: `UPLOADS_DIR`, `CACHE_CODE_DIR`, `CHART_TEMPLATES_DIR`, v.v.
- Gọi `ensure_runtime_dirs()` ngay khi import → tự động tạo thư mục nếu chưa tồn tại.
- Các module khác import path từ đây thay vì hardcode string → tránh lỗi đường dẫn khi deploy.

### `ai_datanalysis/secure_cookie_manager.py` — Cookie phiên làm việc
**Vai trò:** Lưu session token vào cookie trình duyệt dưới dạng mã hóa Fernet.

**Vận hành:**
- Dùng custom Streamlit component (JavaScript) trong `.streamlit_cookies_component/` để đọc/ghi cookie.
- Mã hóa giá trị cookie bằng `Fernet` (AES-128-CBC + HMAC-SHA256) trước khi lưu.
- Khi app reload, đọc cookie → giải mã → lấy session token → xác thực với MySQL.
- Không lưu username hay thông tin nhạy cảm trực tiếp trong cookie — chỉ lưu token ngẫu nhiên.

### `ai_datanalysis/styles.py` — CSS tùy chỉnh
**Vai trò:** Inject CSS vào giao diện Streamlit để tùy chỉnh giao diện.

**Vận hành:**
- `process_styles()` — đọc `assets/styles/style.css`, inject vào trang qua `st.markdown`.
- Được gọi một lần ở đầu `app.py` để style toàn bộ ứng dụng.

---

## 4. ai_datanalysis/core/ — Tầng logic nghiệp vụ

Tầng **không được phép import `streamlit`**. Thuần logic xử lý dữ liệu và AI.

### `core/normalization.py` — Chuẩn hóa truy vấn
**Vai trò:** Biến câu hỏi tiếng Việt thành chuỗi ASCII thuần để router và selector xử lý nhất quán.

**Pipeline:**
```
Input: "Vẽ biểu đồ DT theo Tháng"
  → lower()                → "vẽ biểu đồ dt theo tháng"
  → remove_accents()       → "ve bieu do dt theo thang"
  → expand_abbreviations() → "ve bieu do doanh thu theo thang"
  → collapse whitespace    → "ve bieu do doanh thu theo thang"
```

**Quan trọng:** `min`/`max` **không** được expand ở đây vì `router.py` cần detect các từ này nguyên gốc để phân loại ranking intent.

### `core/router.py` — Phân loại intent và loại biểu đồ
**Vai trò:** Nhận query đã normalize → quyết định loại biểu đồ cần tạo và intent của người dùng.

**Vận hành:**
- `infer_graph_type(query)` — khớp keyword theo thứ tự ưu tiên để chọn template:
  `line_plot` / `bar_plot` / `heatmap` / `pie_plot` / ... / `auto_profile` / `table`
- `analyze_intent(query)` — phát hiện các intent song song:
  `calculation`, `filter`, `comparison`, `ranking`, `trend`, `distribution`, `relationship`, `composition`, `join`
- `_detect_follow_up()` — nhận diện câu chỉnh sửa biểu đồ cũ (chỉ khớp cụm từ 2 từ để tránh false positive).
- `_detect_multi_dataset_need()` — phát hiện cần join nhiều bảng.
- Kết quả trả về `RouterOutcome` object chứa toàn bộ thông tin routing.

### `core/selector.py` — Chọn dataset liên quan
**Vai trò:** Trong nhiều bảng dữ liệu đã upload, chọn ra tối đa N bảng phù hợp nhất với câu hỏi.

**Scoring formula:**
```
score(dataset) =
    tên_bảng_khớp_query × 2.0
  + số_cột_khớp_keyword × 1.0
  + số_cột_ID_chung_với_bảng_khác × 0.5
```

Trả về dict `{tên_bảng: DataFrame}` đã được lọc, giúp prompt builder chỉ gửi dữ liệu liên quan cho LLM.

### `core/semantic_columns.py` — Ngữ nghĩa cột dữ liệu
**Vai trò:** Khớp tên cột kỹ thuật với từ khóa tiếng Việt/Anh trong câu hỏi.

**Vận hành:**
- `TOKEN_SYNONYMS` — từ điển đồng nghĩa: `"revenue"` ↔ `"doanh thu"`, `"max"` ↔ `"cao nhat"`, v.v.
- `score_query_to_column(query, col_name)` — tính độ khớp ngữ nghĩa giữa query và tên cột.
- `column_semantic_hint(col_name)` — sinh gợi ý ngữ nghĩa dạng `"revenue -> doanh thu, tong, ..."` để đưa vào prompt.
- Được dùng bởi `fast_path.py` (chọn cột tính toán) và `prompt_builder.py` (thêm hint vào prompt).

### `core/prompt_builder.py` — Xây dựng prompt cho LLM
**Vai trò:** Ghép nối tất cả thông tin thành prompt hoàn chỉnh gửi cho LLM.

**Cấu trúc prompt được tạo:**
```
[Instruction] — luật sinh code Python
[History]     — 3 turn gần nhất (chỉ khi is_follow_up=True)
[Question]    — câu hỏi gốc
[Dataset metadata] — per dataset:
    - shape, missing values
    - numeric_cols, categorical_cols, datetime_cols, id_cols
    - semantic_column_hints
    - sample_head (CSV fallback nếu tabulate chưa cài)
    - table_layout_hint (gợi ý wide vs long format)
[Join guidance] — kết quả từ join_planner
[Chart template] — nội dung từ prompts/chart_templates/*.txt
```

Prompt ngắn gọn về schema thay vì đổ toàn bộ dữ liệu → tiết kiệm tokens.

### `core/agent.py` — Điều phối pipeline
**Vai trò:** Orchestrator chính — điều phối toàn bộ luồng từ câu hỏi đến kết quả.

**Pipeline trong `run_pipeline()`:**
```
1. Kiểm tra cache → nếu hit, trả ngay kết quả (bỏ qua tất cả bước dưới)
2. Thử fast_path → nếu match, sinh code không cần LLM
3. Build prompt (prompt_builder)
4. Gọi LLM → nhận code Python
5. Strip DeepSeek <think>...</think> blocks
6. Validate Python syntax (ast.parse)
7. Thực thi trong sandbox (executor)
8. Nếu lỗi → retry tối đa max_attempts lần với error message
9. Lưu vào cache
10. Trả về ExecOutcome
```

### `core/executors.py` — Sandbox thực thi code
**Vai trò:** Thực thi code Python do LLM sinh ra trong môi trường an toàn.

**Cơ chế bảo mật (AST-based validation):**
- Danh sách đen hàm nguy hiểm: `eval`, `exec`, `open`, `__import__`, `subprocess`, v.v.
- Danh sách đen module: `os`, `sys`, `subprocess`, `socket`, `shutil`, v.v.
- Phân tích AST trước khi chạy → từ chối code có lời gọi nguy hiểm.
- Inject các biến `DF_1`, `DF_2`, ... vào namespace thực thi.
- Capture `result` variable sau khi chạy.
- Trả về `ExecOutcome(ok, result, error, executed_code)`.

### `core/cache.py` — Cache hai tầng
**Vai trò:** Tránh gọi LLM và thực thi code lại cho các query giống nhau trên cùng dữ liệu.

**Cơ chế:**
- **Cache key:** SHA256( normalize(query) + SHA256(schema + data content) ) → duy nhất theo câu hỏi VÀ nội dung dữ liệu.
- **Code cache** (`data/runtime/cache/code/`): lưu code Python đã sinh.
- **Result cache** (`data/runtime/cache/results/`): lưu kết quả đã thực thi (JSON — hỗ trợ DataFrame và Plotly Figure).
- Code chứa lời gọi đọc file (như `pd.read_csv`) không được cache để tránh stale data.

### `core/fast_path.py` — Sinh code không cần LLM
**Vai trò:** Xử lý các query đơn giản (sum, mean, count) bằng rule-based code generation — không tốn API call.

**Các pattern được nhận diện:**
- "tổng / sum [metric]" → `df[col].sum()`
- "trung bình / mean / average [metric]" → `df[col].mean()`
- "đếm / count" → `df.shape[0]`
- "max / cao nhất [metric]" → `df[col].max()`
- "min / thấp nhất [metric]" → `df[col].min()`

Dùng `score_query_to_column` để chọn đúng cột metric từ câu hỏi.

### `core/join_planner.py` — Lập kế hoạch join
**Vai trò:** Phát hiện cột ID chung giữa các bảng và gợi ý câu lệnh join cho LLM.

**Vận hành:**
- Phát hiện keyword join trong query (join, merge, kết hợp...).
- Tìm cột có suffix `_id`, `_code`, `_key` giống nhau giữa các bảng.
- Tính confidence score cho từng cặp join.
- Sinh `JoinHint` object → `build_join_context()` chuyển thành text đưa vào prompt.

### `core/data_catalog.py` — Phân tích quan hệ bảng
**Vai trò:** Phân tích metadata của tập dữ liệu upload — phát hiện quan hệ, tạo master dataset.

**Vận hành:**
- `build_data_catalog(data)` — phát hiện cột ID chung, loại dữ liệu, quan hệ giữa các bảng.
- `build_master_datasets(data, catalog)` — tạo bảng tổng hợp bằng cách join tự động.
- `prepare_analysis_bundle(data, catalog)` — chuẩn bị bundle gồm data gốc + master tables để agent sử dụng.
- Kết quả catalog được hiển thị trong sidebar (quan hệ bảng, thống kê).

---

## 5. ai_datanalysis/services/ — Tầng dịch vụ

**Vai trò:** Lớp facade giữa `app.py` và `core/`. Mỗi service đóng gói một nhóm chức năng liên quan. `app.py` chỉ import từ đây, không import trực tiếp từ `core/`.

### `services/llm_service.py` — Dịch vụ LLM & pipeline phân tích
**Vai trò:** API duy nhất để khởi tạo AI agent và chạy phân tích.

| Hàm | Tác dụng |
|-----|----------|
| `build_llm(model_override)` | Tạo LLM instance (wrap `llm_factory.build_llm`) |
| `build_executor()` | Tạo sandbox executor (wrap `core/executors`) |
| `build_agent(llm, executor, max_attempts)` | Tạo `DataAnalysisAgent` |
| `run_analysis(agent, query, data, history, ...)` | Chạy toàn bộ pipeline → trả `ExecOutcome` |
| `run_dashboard(data, role, goal)` | Tạo dashboard tự động → trả report object |

### `services/retrieval_service.py` — Dịch vụ truy vấn & phân loại
**Vai trò:** Gom pipeline hiểu query vào một hàm duy nhất.

| Hàm | Tác dụng |
|-----|----------|
| `normalize_query(text)` | Chuẩn hóa text tiếng Việt |
| `route_query(query)` | Phân loại intent + graph type |
| `select_datasets(query, data)` | Chọn bảng liên quan |
| `retrieve_context(query, data)` | Chạy cả 3 bước trên trong 1 lần gọi |
| `score_query_to_column(query, col)` | Tính độ khớp ngữ nghĩa query-cột |
| `column_semantic_hint(col)` | Sinh gợi ý ngữ nghĩa cho cột |

### `services/data_service.py` — Dịch vụ quản lý dữ liệu
**Vai trò:** Load, lưu, xóa dataset người dùng — wrapper an toàn quanh `dataset_service`.

| Hàm | Tác dụng |
|-----|----------|
| `load_files(uploaded_files)` | Đọc file CSV/Excel từ Streamlit uploader |
| `save_user_files(user, files, append)` | Lưu file vào `data/runtime/uploads/{user}/` |
| `load_user_data(user)` | Đọc lại toàn bộ data đã lưu của user |
| `clear_user_data(user)` | Xóa sạch data và manifest của user |
| `build_catalog(data)` | Tạo catalog quan hệ bảng (bắt exception → `{}`) |

### `services/dataset_service.py` — Lưu trữ file dataset
**Vai trò:** Xử lý thực tế việc đọc/ghi file upload.

**Giới hạn an toàn:**
- Tối đa 5 file mỗi lần upload.
- Tối đa 10MB mỗi file.
- Tối đa 250.000 rows và 200 cột mỗi DataFrame.
- Tối đa 10 sheet từ file Excel.
- Tên user được sanitize để tránh path traversal.

### `services/chat_service.py` — Lưu trữ lịch sử hội thoại
**Vai trò:** Persist và load lịch sử chat dưới dạng JSON trên disk.

**Vận hành:**
- Mỗi user có 1 file JSON: `data/runtime/chat_history/{username}.json`.
- Hỗ trợ **nhiều conversation** trên mỗi user (có `chat_id`).
- Thread-safe: dùng per-user lock để tránh race condition khi nhiều tab mở cùng lúc.
- Serialize cả Plotly Figure và DataFrame trong lịch sử (để hiển thị lại khi chuyển tab).

### `services/dashboard_service.py` — Tạo dashboard tự động
**Vai trò:** Phân tích dữ liệu và tự động sinh dashboard với KPI, biểu đồ, insights.

**Vận hành:**
- `build_dashboard_report(data, role, goal)` — sinh report nhiều section dựa theo vai trò (CEO, CFO, Sales...).
- Lấy `ROLE_KPI_HINTS` để ưu tiên metric phù hợp với vai trò.
- Tự động phát hiện cột số, cột phân loại, cột thời gian để chọn loại biểu đồ phù hợp.
- Tạo `master_dataset` từ `data_catalog` để báo cáo tổng hợp.

### `services/ops_service.py` — Vận hành hệ thống
**Vai trò:** Logging, rate limiting, audit trail, metrics, dọn dẹp định kỳ.

| Hàm | Tác dụng |
|-----|----------|
| `configure_logging()` | Thiết lập RotatingFileHandler → `data/runtime/logs/app.log` (2MB × 5 files) |
| `consume_rate_limit(engine, user, limit, window)` | Kiểm tra & trừ quota query/login trong DB |
| `audit_query(engine, user, query, status, ms)` | Ghi log query vào bảng `audit_log` |
| `record_metric(engine, name, value)` | Ghi metric vào bảng `metrics` |
| `init_ops_db(engine)` | Tạo bảng `rate_limits`, `audit_log`, `metrics` |
| `run_maintenance(engine)` | Xóa log/cache cũ hơn N ngày |

**Cấu hình qua env vars:**
- `QUERY_RATE_LIMIT` (default 30) — số query tối đa mỗi `QUERY_RATE_WINDOW_S` giây.
- `LOGIN_RATE_LIMIT` (default 5) — số lần đăng nhập sai tối đa mỗi 5 phút.

### `services/chart_service.py` — Xây dựng biểu đồ programmatic
**Vai trò:** Tạo biểu đồ Plotly không cần LLM — dùng trong dashboard tự động.

Cung cấp các builder thuần Python: `build_bar_chart`, `build_line_chart`, `build_histogram`, `build_scatter`, `build_pie_chart`, `build_box_chart`, `build_heatmap`, `build_kpi_summary`.
Không import `streamlit` — chỉ trả về `go.Figure`.

### `services/render_service.py` — Wrapper tương thích ngược
**Vai trò:** Re-export `render_result` từ `ui/render.py` để code cũ không bị vỡ.

```python
from ai_datanalysis.ui.render import render_result  # noqa: F401
```
Module này sẽ bị xóa trong tương lai khi toàn bộ caller đã cập nhật.

---

## 6. ai_datanalysis/ui/ — Tầng giao diện

**Tầng duy nhất được phép gọi `st.*`**. Không chứa business logic.

### `ui/render.py` — Render kết quả ra màn hình
**Vai trò:** Nhận output từ pipeline và hiển thị với định dạng phù hợp.

**Dispatch theo kiểu dữ liệu:**
| Kiểu `result` | Cách render |
|---------------|-------------|
| `dict` `__type__ == "dashboard_report"` | Full report nhiều section, overview metrics |
| `dict` `__type__ == "dashboard"` | Single dashboard: KPI cards + chart grid + insights |
| `go.Figure` | `st.plotly_chart(result, use_container_width=True)` |
| `pd.DataFrame` | `st.dataframe(result, use_container_width=True)` |
| `list` / `tuple` | Render từng phần tử có đánh số |
| Khác | `st.write(result)` |

### `ui/components.py` — Các component giao diện
**Vai trò:** Toàn bộ widget Streamlit tương tác người dùng.

| Component | Tác dụng |
|-----------|----------|
| `auth_sidebar(engine)` | Sidebar: trạng thái đăng nhập + nút đăng xuất |
| `auth_main(engine)` | Màn hình chính khi chưa login: 2 tab Đăng nhập / Đăng ký |
| `dataset_sidebar()` | Sidebar: upload file, thống kê catalog, preview dữ liệu |
| `dataset_main()` | Màn hình upload khi đã login nhưng chưa có data |
| `settings_sidebar()` | Cài đặt: chế độ riêng tư, vai trò dashboard, chọn model |
| `main_action_bar(engine)` | Thanh 7 nút: Đăng xuất, Tải mới, Xóa data, Khám phá, Xóa chat, Chat mới, Dashboard |

---

## 7. prompts/ — Template prompt LLM

Các file `.txt` được đọc bởi `prompt_builder.py` và gắn vào cuối prompt gửi LLM. Mỗi file là tập luật riêng cho một loại biểu đồ.

### `prompts/chart_templates/`

| File | Loại biểu đồ | Điểm đặc biệt |
|------|-------------|---------------|
| `bar_plot.txt` | Biểu đồ cột | Phân biệt WIDE format vs LONG format; hướng dẫn aggregation |
| `line_plot.txt` | Biểu đồ đường | Dùng `px.line` với `markers=True` |
| `scatter_2d_plot.txt` | Biểu đồ phân tán | `px.scatter` với `color` tùy chọn |
| `histogram_plot.txt` | Histogram | `px.histogram` với `nbins` tùy chỉnh |
| `heatmap.txt` | Heatmap | **TYPE A** (correlation matrix, `go.Heatmap`) vs **TYPE B** (pivot, `go.Heatmap`). Nghiêm cấm dùng `px.density_heatmap` |
| `pie_plot.txt` | Biểu đồ tròn | `hole=0` (pie thuần); chỉ dùng `hole=0.3` khi user yêu cầu donut |
| `box_plot.txt` | Box plot | `px.box` với x=category, y=value |
| `violin_plot.txt` | Violin plot | `px.violin` với `box=True` |
| `area_plot.txt` | Biểu đồ miền | `px.area` |
| `bubble_plot.txt` | Biểu đồ bong bóng | `px.scatter` với tham số `size` và `color` |
| `candle_plot.txt` | Candlestick | `go.Candlestick` với OHLC columns |
| `density_contour_plot.txt` | Density contour | `px.density_contour` (đúng cho density — khác `px.density_heatmap`) |
| `polar_plot.txt` | Radar / Polar | `go.Scatterpolar` |
| `sunburst_plot.txt` | Sunburst | `px.sunburst` với `path=[CAT1, CAT2]` |
| `treemap_plot.txt` | Treemap | `px.treemap` với `path=[CAT1, CAT2]` |
| `table.txt` | Bảng dữ liệu | Trả `pd.DataFrame` thay vì Figure |
| `table_plotly.txt` | Bảng Plotly | `go.Figure(go.Table(...))` với header/cells styling |
| `generic_plot.txt` | Fallback | Dùng khi intent là chart nhưng không xác định được loại cụ thể |
| `auto_profile.txt` | Tự động phân tích | Tạo summary thống kê + nhiều biểu đồ thăm dò |

**Quy tắc chung cho tất cả template:**
- Không dùng markdown fences trong code.
- Không gọi `fig.show()`.
- Gán kết quả cuối vào biến `result`.
- Filter dữ liệu TRƯỚC khi aggregate.

---

## 8. data/ — Dữ liệu runtime

### `data/samples/` — Dataset mẫu
Dữ liệu CSV/JSON được cung cấp sẵn để demo và kiểm thử.

| File | Nội dung |
|------|----------|
| `retail_sales_benchmark.csv` | Dữ liệu bán lẻ — benchmark chính |
| `exam_scores_benchmark.csv` | Điểm thi học sinh — benchmark phân phối |
| `bike_sharing_benchmark.csv` | Thuê xe đạp theo giờ — benchmark time-series |
| `monthly.csv` | Dữ liệu tháng tổng hợp |
| `disoccupazione.csv` | Dữ liệu thất nghiệp |
| `geojson_brasil.json` | GeoJSON map Brazil |
| `reproducibility_prompts.txt` | Tập câu hỏi để kiểm thử reproducibility |

### `data/runtime/` — Dữ liệu sinh ra khi chạy

| Thư mục | Nội dung | Ghi chú |
|---------|----------|---------|
| `uploads/{user}/` | File CSV đã upload của từng user + `manifest.json` | Xóa bằng nút "Xóa data" trên UI |
| `cache/code/` | File `.py` — code Python đã được LLM sinh ra | Cache theo SHA256(query+schema) |
| `cache/results/` | File `.json` — kết quả thực thi đã serialize | DataFrame → JSON split format; Figure → Plotly JSON |
| `chat_history/` | File `{user}.json` — lịch sử hội thoại | Hỗ trợ nhiều conversation |
| `logs/app.log` | Log ứng dụng (rotating, tối đa 2MB × 5 files) | Ghi qua `ops_service.configure_logging()` |

---

## 9. assets/ — Tài nguyên tĩnh

### `assets/styles/style.css`
File CSS tùy chỉnh giao diện Streamlit. Được `styles.py` đọc và inject vào trang qua `st.markdown`. Dùng để override màu sắc, font, layout mặc định của Streamlit.

---

## 10. tests/ — Bộ kiểm thử

Mỗi file test tương ứng với một module trong `core/`. Chạy bằng `pytest`.

| File test | Module được test | Kiểm thử gì |
|-----------|-----------------|-------------|
| `test_normalization.py` | `core/normalization.py` | Bỏ dấu, expand abbreviations, lowercase |
| `test_router.py` | `core/router.py` | Intent detection, graph type inference, follow-up detection |
| `test_selector.py` | `core/selector.py` | Chọn đúng dataset theo query |
| `test_prompt_builder.py` | `core/prompt_builder.py` | Cấu trúc prompt, schema summary |
| `test_fast_path.py` | `core/fast_path.py` | Rule-based code generation (sum, mean, count) |
| `test_join_planner.py` | `core/join_planner.py` | Phát hiện join columns, confidence scoring |
| `test_data_catalog.py` | `core/data_catalog.py` | Phát hiện quan hệ bảng, tạo master dataset |
| `test_dashboard_service.py` | `services/dashboard_service.py` | Tạo dashboard, KPI detection theo role |

---

## 11. scripts/ — Tiện ích

| File | Tác dụng |
|------|----------|
| `extract_pkl.py` | Trích xuất dữ liệu từ file pickle cũ (di cư dữ liệu legacy) |
| `standardize_all_plots.py` | Chuẩn hóa hàng loạt chart template `.txt` — thêm đúng cấu trúc `result = fig` và `update_layout` |

---

## 12. notebooks/ — Phân tích thử nghiệm

| File | Tác dụng |
|------|----------|
| `global-employment-unemployment-analysis.ipynb` | Phân tích dữ liệu việc làm thế giới — demo khả năng của hệ thống |
| `test_data.ipynb` | Notebook thử nghiệm pipeline trên dataset mẫu |

---

## 13. .devcontainer/ — Môi trường phát triển

| File | Tác dụng |
|------|----------|
| `devcontainer.json` | Cấu hình VS Code Dev Container (Docker image, extensions, port forward) |

Cho phép mở dự án trong container có sẵn Python, Poetry, và extensions cần thiết — đảm bảo môi trường đồng nhất giữa mọi developer.

---

## 14. .streamlit/ — Cấu hình Streamlit

| File | Tác dụng |
|------|----------|
| `config.toml` | Cấu hình server: port, theme, max upload size, browser settings. Ghi đè mặc định của Streamlit khi deploy. |

---

## 15. .streamlit_cookies_component/ — Component cookie tùy chỉnh

Đây là **React app đã được build sẵn** (không cần build lại) dùng làm Streamlit custom component.

| File/Folder | Tác dụng |
|-------------|----------|
| `index.html` | Entry HTML của component |
| `asset-manifest.json` | Danh sách JS chunks |
| `static/js/*.chunk.js` | Code JavaScript đã minify |

**Cơ chế hoạt động:** `secure_cookie_manager.py` load component này vào trang → JavaScript chạy trong iframe → đọc/ghi cookie trình duyệt → truyền giá trị qua Streamlit component bidirectional messaging.

---

## 16. File cấu hình gốc

| File | Tác dụng |
|------|----------|
| `pyproject.toml` | Định nghĩa dependencies theo Poetry. Section `[tool.poetry.dependencies]` là nguồn sự thật về phiên bản thư viện. |
| `poetry.lock` | Khóa toàn bộ dependency tree — đảm bảo mọi `poetry install` ra cùng kết quả. Cần commit vào git. |
| `.env` | Chứa secret keys (`OPENAI_API_KEY`, `GROQ_API_KEY`, `AUTH_DB_URL`, `COOKIE_SECRET`). **Không commit.** |
| `.env.example` | Bản mẫu `.env` không có giá trị thật — commit để hướng dẫn setup. |
| `.gitignore` | Loại trừ `.env`, `.venv/`, `__pycache__/`, `data/runtime/`, `*.log` khỏi git. |

---

## Luồng xử lý một câu hỏi (end-to-end)

```
1. User nhập câu hỏi vào chat input
         │
         ▼
2. app.py: consume_rate_limit() → kiểm tra quota
         │
         ▼
3. run_analysis(agent, query, data, history)
    │
    ├─► cache.get() → HIT? Trả kết quả ngay
    │
    ├─► try_fast_path() → Match? Sinh code rule-based, bỏ qua LLM
    │
    ├─► select_datasets() → Chọn tối đa 2 bảng liên quan
    │
    ├─► build_prompt() → Ghép: schema + semantic hints + chart template + history
    │
    ├─► llm.invoke(prompt) → Nhận code Python (xử lý DeepSeek <think> blocks)
    │
    ├─► validate_syntax() → ast.parse() nếu lỗi → retry
    │
    ├─► executor.run(code) → sandbox: validate AST + exec → lấy `result`
    │
    └─► cache.set() → Lưu code + kết quả vào disk
         │
         ▼
4. render_result(outcome.result) → ui/render.py dispatch theo kiểu dữ liệu
         │
         ▼
5. save_chat_history(user, messages) → disk JSON
         │
         ▼
6. audit_query(engine, user, query, status, ms) → MySQL audit_log
```

---

*Tài liệu được tạo: 2026-04-16*
*Phiên bản hệ thống: AI-Datanalysis sau refactor service-layer*
