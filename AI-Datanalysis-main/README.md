# Chạy hệ thống
cd D:\Kiet\AI-Datanalysis-main\AI-Datanalysis-main
poetry run streamlit run app.py
# AI-Datanalysis

Chatbot phân tích dữ liệu thông minh xây dựng trên **Streamlit**, **LangChain** và các mô hình ngôn ngữ lớn chạy qua Groq. Người dùng tải lên file CSV/XLSX, đặt câu hỏi bằng ngôn ngữ tự nhiên (tiếng Việt hoặc tiếng Anh), và nhận kết quả là bảng dữ liệu, biểu đồ tương tác hoặc dashboard tự động.

---

## Tính năng chính

| Tính năng | Mô tả |
|-----------|-------|
| **Phân tích ngôn ngữ tự nhiên** | Hỗ trợ tiếng Việt và tiếng Anh; tự phát hiện ý định và loại biểu đồ phù hợp |
| **Groq LLM** | Hỗ trợ hai model đang dùng: Llama 3.3 70B Versatile và Qwen3 32B |
| **Sandbox an toàn** | Code do LLM sinh ra chạy trong môi trường bị giới hạn (AST validation + restricted builtins) |
| **Cache thông minh** | Cache cả code sinh ra và kết quả thực thi theo cặp (query, schema dữ liệu) |
| **Multi-tenant** | Dữ liệu, lịch sử chat và upload được cô lập hoàn toàn theo từng người dùng |
| **Auto-dashboard** | Tự động sinh dashboard với KPI, biểu đồ và insight theo vai trò người dùng |
| **Audit trail** | Ghi log đầy đủ: query, latency, lỗi, provider, model vào database |
| **Rate limiting** | Giới hạn tần suất query và đăng nhập; bảo vệ khỏi lạm dụng |

---

## Kiến trúc tổng quan

```
┌─────────────────────────────────────────────────────┐
│                   Streamlit UI                       │
│         (auth / dataset / chat / dashboard)          │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│              ai_datanalysis/app.py                   │
│   Điều phối: session, routing, agent, rendering      │
└──┬─────────────┬──────────────┬─────────────────────┘
   │             │              │
┌──▼──────┐ ┌───▼──────────┐ ┌─▼──────────┐
│ core/   │ │ services/    │ │   ui/      │
│ 5-step  │ │ chat,dataset │ │ components │
│ pipeline│ │ dashboard,   │ │            │
│ LLM+box │ │ ops, render  │ │            │
└─────────┘ └──────────────┘ └────────────┘
```

**Luồng xử lý một query:**
```
Người dùng nhập
  → Normalize (bỏ dấu, lowercase)
  → Router   (intent + graph_type + is_follow_up)
  → Dataset Selector (scoring theo relevance)
  → Data Catalog / Join Planner (phát hiện quan hệ bảng)
  → Fast-path? ──[Yes]──→ Execute trực tiếp
               └─[No]──→ Build Prompt → LLM → Extract Code
                          → Validate (AST) → Execute (sandbox)
                          → Retry tối đa 3 lần nếu lỗi
  → Cache kết quả
  → Render (Table / Chart / Dashboard)
  → Lưu chat history
  → Audit log
```

---

## Cấu trúc thư mục

```
AI-Datanalysis-main/
├── README.md                    ← tài liệu này
├── app.py                       ← entry point (wrapper)
├── pyproject.toml               ← dependencies (Poetry)
├── Dockerfile
├── docker-compose.yml
├── .env.example                 ← mẫu biến môi trường
│
├── ai_datanalysis/              ← package chính
│   ├── README.md                ← mô tả package, entry points, cấu hình
│   ├── core/
│   │   └── README.md            ← đặc tả 5-step AI pipeline
│   ├── services/
│   │   └── README.md            ← đặc tả từng service
│   └── ui/
│       └── README.md            ← đặc tả UI components
│
├── prompts/
│   ├── README.md                ← cách hoạt động của prompt system
│   └── chart_templates/
│       └── README.md            ← đặc tả 18 chart templates
│
├── data/
│   ├── README.md                ← cấu trúc thư mục data
│   ├── samples/
│   │   └── README.md            ← dataset mẫu
│   └── runtime/
│       └── README.md            ← runtime data (cache, upload, logs)
│
├── tests/
│   └── README.md                ← hướng dẫn chạy và viết tests
│
├── scripts/
│   └── README.md                ← hướng dẫn từng utility script
│
├── notebooks/
│   └── README.md                ← danh sách và hướng dẫn notebooks
│
└── assets/
    └── README.md                ← tùy chỉnh giao diện (CSS)
```

---

## Cài đặt nhanh

### Yêu cầu

- Python 3.11+
- [Poetry](https://python-poetry.org/)
- MySQL 8.0+
- API key của ít nhất một LLM provider

### 1 — Cài dependencies

```bash
poetry install
```

### 2 — Cấu hình môi trường

```bash
cp .env.example .env
# Chỉnh sửa .env với thông tin thực tế
```

Các biến **bắt buộc**:

```env
AUTH_DB_URL=mysql+pymysql://root:<password>@mysql-chatbot.c3igik0cizol.ap-southeast-1.rds.amazonaws.com:3306/chatbot_auth?charset=utf8mb4
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_...
```

Biến **bảo mật** (bắt buộc trong production):

```env
COOKIE_SECRET=<chuỗi ngẫu nhiên 32 byte>
APP_ENV=production
```

Tạo `COOKIE_SECRET`:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 3 — Khởi chạy

```bash
poetry run streamlit run app.py
```

Truy cập: `http://localhost:8501`

---

## Cấu hình LLM Provider

| Provider | Biến môi trường | Model mặc định |
|----------|----------------|----------------|
| `groq` *(mặc định)* | `GROQ_API_KEY`, `GROQ_MODEL` | `llama-3.3-70b-versatile` |

### Groq — Chọn model trên giao diện

Khi dùng Groq (`LLM_PROVIDER=groq`), người dùng có thể **đổi model trực tiếp trên UI** mà không cần sửa file `.env`. Có 2 model khả dụng:

| Model | Đặc điểm |
|-------|---------|
| `llama-3.3-70b-versatile` | Cân bằng tốc độ và độ chính xác — khuyến nghị dùng hàng ngày |
| `qwen/qwen3-32b` | Đa năng, mạnh về tiếng Việt và lập trình phức tạp |

Model selector xuất hiện ngay dưới thanh điều khiển sau khi đăng nhập và có dữ liệu. Mỗi model được cache riêng (`@st.cache_resource`) nên đổi qua lại không bị chậm lần thứ hai.

`GROQ_MODEL` trong `.env` chỉ đóng vai trò **giá trị mặc định** khi app khởi động lần đầu.

---

## Chạy tests

```bash
poetry run pytest tests/ -v
```

---

## Biến môi trường đầy đủ

| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `AUTH_DB_URL` | *(bắt buộc)* | SQLAlchemy URL tới MySQL |
| `LLM_PROVIDER` | `groq` | Provider LLM |
| `LLM_TEMPERATURE` | `0.0` | Temperature khi sinh code |
| `COOKIE_SECRET` | *(dev fallback)* | Khóa mã hóa cookie session |
| `APP_ENV` | `development` | `production` bật kiểm tra bảo mật |
| `EXECUTOR_BACKEND` | `local` | `local` hoặc `e2b` |
| `LOGIN_RATE_LIMIT` | `5` | Số lần đăng nhập tối đa / window |
| `LOGIN_RATE_WINDOW_S` | `300` | Window rate limit login (giây) |
| `QUERY_RATE_LIMIT` | `30` | Số query tối đa / window |
| `QUERY_RATE_WINDOW_S` | `60` | Window rate limit query (giây) |
| `OPS_DB_RETENTION_DAYS` | `30` | Giữ audit logs bao nhiêu ngày |
| `OPS_FILE_RETENTION_DAYS` | `14` | Giữ cache files bao nhiêu ngày |
| `APP_LOG_LEVEL` | `INFO` | Log level (`DEBUG`/`INFO`/`WARNING`/`ERROR`) |
