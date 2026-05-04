# ai_datanalysis — Package chính

Package Python chứa toàn bộ logic của ứng dụng AI-Datanalysis: từ khởi tạo UI, xác thực người dùng, kết nối LLM, đến thực thi code phân tích và ghi log vận hành.

---

## Cấu trúc module

```
ai_datanalysis/
├── app.py                   # Điểm vào Streamlit — orchestrator trung tâm
├── auth.py                  # Xác thực người dùng (đăng ký, đăng nhập, session)
├── llm_factory.py           # Khởi tạo LLM theo provider từ biến môi trường
├── paths.py                 # Định nghĩa tập trung tất cả đường dẫn file/thư mục
├── secure_cookie_manager.py # Quản lý cookie session mã hóa AES
├── styles.py                # Inject CSS tùy chỉnh vào Streamlit
│
├── core/                    # 5-step AI pipeline (xem core/README.md)
├── services/                # Business logic và persistence (xem services/README.md)
└── ui/                      # Streamlit components (xem ui/README.md)
```

---

## app.py — Orchestrator trung tâm

**Vai trò:** Điểm vào duy nhất của ứng dụng Streamlit. Điều phối toàn bộ luồng từ khi trang load đến khi trả kết quả cho người dùng.

**Các nhiệm vụ chính:**

| Nhiệm vụ | Chi tiết |
|----------|----------|
| Khởi tạo session state | Đặt giá trị mặc định cho tất cả biến Streamlit một lần duy nhất |
| Đồng bộ session cookie | Khôi phục phiên đăng nhập từ cookie hoặc query param khi trang reload |
| Khởi động database | `init_auth_db` + `init_ops_db` — chạy DDL đúng một lần qua `@st.cache_resource` |
| Load dữ liệu đã upload | Tự động nạp lại manifest files của user khi app restart |
| Xây catalog | Phân tích quan hệ giữa các bảng dữ liệu đã nạp |
| Routing query | Phân biệt: query thường → `agent.run_pipeline()` / dashboard → `build_dashboard_report()` |
| Error handling | Hiển thị lỗi + ghi audit log kể cả khi pipeline thất bại |
| Chat persistence | Lưu mọi tin nhắn vào JSON file ngay sau khi xử lý |

**Các hàm cache được đặt ở module level (chạy đúng một lần/app):**
```python
@st.cache_resource
def get_auth_engine()    # SQLAlchemy Engine — pool kết nối MySQL
def _get_llm()           # ChatGroq
def _get_executor()      # LocalRestrictedExecutor hoặc E2BExecutor
def _init_databases()    # init_auth_db + init_ops_db + run_maintenance
```

**Luồng render chính (hàm `main()`):**
```
set_page_config → process_styles → configure_logging
→ session state defaults → sync cookie session
→ _init_databases() [cached]
→ nếu chưa đăng nhập: auth_sidebar + auth_main → return
→ đã đăng nhập:
    → load data từ manifest
    → build_data_catalog
    → render sidebar (auth, dataset, settings, chat history)
    → render action bar + chat history
    → nhận chat_input
    → if trigger_auto_profile/dashboard: override user_text
    → rate_limit check
    → if "dashboard" in query: build_dashboard_report
      else: agent.run_pipeline
    → render_result
    → save_chat_history
    → audit_query + record_metric
```

---

## auth.py — Xác thực người dùng

**Vai trò:** Quản lý toàn bộ vòng đời xác thực: đăng ký, đăng nhập, session token, rate limiting đăng nhập.

**Công nghệ bảo mật:**
- Mã hóa mật khẩu: PBKDF2-HMAC-SHA256 với 200.000 iterations và salt ngẫu nhiên 16 bytes
- So sánh hash: `hmac.compare_digest()` — timing-safe, chống timing attack
- Session token: `secrets.token_urlsafe(32)` — 256-bit entropy
- TTL session: 7 ngày (xoay token mỗi lần đăng nhập)

**Schema database:**

```sql
-- Bảng người dùng
users (id, username UNIQUE, email UNIQUE, password_hash VARBINARY,
       salt VARBINARY, created_at, last_login, is_active)

-- Audit đăng nhập
login_audit (id, username, success TINYINT, created_at)

-- Session tokens
user_sessions (id, username, session_token UNIQUE, expires_at, created_at)
```

**API chính:**

```python
register_user(engine, username, password, email) -> (bool, str)
# Trả về (True, "Đăng ký thành công") hoặc (False, "lý do lỗi")
# Phát hiện duplicate bằng sqlalchemy.exc.IntegrityError (không dùng string matching)

verify_user(engine, username, password) -> (bool, str)
# Kiểm tra rate limit đăng nhập trước
# Dùng hmac.compare_digest cho password comparison

create_session(engine, username) -> str  # token
get_session_username(engine, token) -> str | None
delete_session(engine, token) -> None
```

---

## llm_factory.py — LLM Factory

**Vai trò:** Tạo instance LLM phù hợp dựa vào biến môi trường và lựa chọn của người dùng trên UI. Không có input API key qua UI.

**Provider được hỗ trợ:**

```python
LLM_PROVIDER=groq      → ChatGroq(model=GROQ_MODEL, ...)
```

**Groq models khả dụng (`GROQ_AVAILABLE_MODELS`):**

| Model | Đặc điểm |
|-------|---------|
| `llama-3.3-70b-versatile` | Chính xác hơn, phù hợp truy vấn phức tạp |
| `qwen/qwen3-32b` | Đa năng, mạnh về tiếng Việt và lập trình phức tạp |

**Cấu hình chung cho Groq:**

```python
temperature = float(LLM_TEMPERATURE)            # mặc định 0.0
```

**Cách sử dụng trong app (qua cache):**
```python
# Cached riêng theo tên model — đổi model trên UI không làm chậm lần thứ hai
llm = _get_llm(model_name="llama-3.3-70b-versatile")

# model_override=None → dùng giá trị từ env (GROQ_MODEL)
llm = build_llm(model_override=None)
```

**Thêm Groq model mới:** Chỉ cần thêm tên vào `GROQ_AVAILABLE_MODELS` trong `llm_factory.py` — model selector trên UI tự động hiển thị.

---

## paths.py — Quản lý đường dẫn

**Vai trò:** Định nghĩa tập trung tất cả đường dẫn thư mục. Mọi module khác import từ đây thay vì hardcode đường dẫn.

```python
# Thư mục tĩnh (source code)
ASSETS_DIR    = project_root / "assets"
PROMPTS_DIR   = project_root / "prompts"
DOCS_DIR      = project_root / "docs"       # deprecated
NOTEBOOKS_DIR = project_root / "notebooks"
SCRIPTS_DIR   = project_root / "scripts"

# Thư mục runtime (sinh ra lúc chạy)
DATA_DIR          = project_root / "data" / "runtime"
UPLOADS_DIR       = DATA_DIR / "uploads"
CHAT_HISTORY_DIR  = DATA_DIR / "chat_history"
LOGS_DIR          = DATA_DIR / "logs"
CACHE_DIR         = DATA_DIR / "cache"
CACHE_CODE_DIR    = CACHE_DIR / "code"
CACHE_RESULTS_DIR = CACHE_DIR / "results"
```

Tất cả thư mục runtime được tạo tự động (`.mkdir(parents=True, exist_ok=True)`) khi module được import.

---

## secure_cookie_manager.py — Cookie Session

**Vai trò:** Lưu trữ session token trong cookie trình duyệt với mã hóa AES. Bọc lại `streamlit-cookies-manager` với interface đơn giản hơn.

**Cấu hình:**
```env
COOKIE_SECRET=<32-byte hex string>   # bắt buộc trong production
APP_ENV=production                   # raise RuntimeError nếu thiếu COOKIE_SECRET
```

**Cách hoạt động:**
1. Khi đăng nhập: `cookie_manager["session_token"] = token; cookie_manager.save()`
2. Khi reload trang: `_sync_user_session()` đọc token từ cookie → gọi `get_session_username()`
3. Khi đăng xuất: `del cookie_manager["session_token"]; cookie_manager.save()`

**Fallback:** Nếu cookie không khả dụng, token được truyền qua query param `?session=<token>`.

---

## styles.py — CSS tùy chỉnh

**Vai trò:** Inject CSS vào Streamlit để tùy chỉnh giao diện (title block, màu sắc, layout).

```python
from ai_datanalysis.styles import process_styles
process_styles()  # Gọi một lần ở đầu main()
```

CSS thực tế nằm trong [assets/styles/style.css](../assets/styles/style.css).

---

## Cấu hình môi trường

Xem đầy đủ trong [../.env.example](../.env.example) và [../README.md](../README.md#biến-môi-trường-đầy-đủ).

**Biến quan trọng nhất:**

```env
AUTH_DB_URL=mysql+pymysql://user:pass@host:3306/dbname
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_...
COOKIE_SECRET=<hex 32 bytes>
APP_ENV=production
```

---

## Mở rộng

**Thêm LLM provider mới:** Chỉnh `llm_factory.py` — thêm một nhánh `if provider == "newprovider":`.

**Thêm cột vào database:** Chỉnh DDL trong `auth.py:init_auth_db()` hoặc `ops_service.py:init_ops_db()`.

**Tắt rate limiting:** Đặt `QUERY_RATE_LIMIT=99999` trong `.env`.
