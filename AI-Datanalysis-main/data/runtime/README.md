# data/runtime/ — Dữ liệu Runtime

Chứa tất cả dữ liệu được sinh ra trong quá trình ứng dụng vận hành. **Không commit thư mục này vào git.** Toàn bộ cấu trúc được tạo tự động bởi `paths.py` khi app khởi động lần đầu.

---

## Cấu trúc chi tiết

```
data/runtime/
├── uploads/                  ← file người dùng upload
│   └── {username}/
│       ├── manifest.json
│       ├── 20250101_120000_sales.csv
│       └── 20250101_120005_data.xlsx
│
├── cache/                    ← cache code và kết quả pipeline
│   ├── code/
│   │   └── {sha256_64hex}.py       ← code đã sinh và validated
│   └── results/
│       └── {sha256_64hex}.json     ← kết quả serialized
│
├── chat_history/             ← lịch sử hội thoại JSON
│   └── {username}.json
│
└── logs/                     ← log ứng dụng
    └── app.log
```

---

## uploads/ — File người dùng

**Quản lý bởi:** `services/dataset_service.py`

**Cách hoạt động:**
- Mỗi user có thư mục riêng: `uploads/{username}/`
- Tên file theo pattern: `{YYYYMMDD_HHMMSS}_{original_filename}` — tránh conflict
- `manifest.json` lưu danh sách đường dẫn tuyệt đối của các file đã upload

**manifest.json format:**
```json
[
  "/absolute/path/to/data/runtime/uploads/alice/20250101_120000_sales.csv",
  "/absolute/path/to/data/runtime/uploads/alice/20250101_120005_products.xlsx"
]
```

**Path traversal protection:** Mọi path trong manifest phải nằm trong `uploads/{username}/`. Path ngoài vùng này sẽ bị bỏ qua khi nạp lại.

**Isolation:** User A không thể truy cập file của user B. `normalize_user()` sanitize tên user trước khi dùng làm tên thư mục.

---

## cache/ — Cache Code và Kết quả

**Quản lý bởi:** `core/cache.py`

**Cache key:** SHA-256 của `(normalized_query + schema_fingerprint)`, 64 ký tự hex.

**Hai lớp cache:**

| Lớp | Thư mục | Nội dung |
|-----|---------|---------|
| Code cache | `cache/code/{key}.py` | Python code đã validate, sẵn sàng execute |
| Result cache | `cache/results/{key}.json` | Kết quả đã serialize (DataFrame/Figure/text) |

**Luồng cache:**
```
Query → normalize → hash
  → hit code cache? → execute lại (bỏ qua LLM call)
  → hit result cache? → deserialize + return (bỏ qua cả execute)
  → miss → LLM → validate → execute → save both caches
```

**Serialization trong result cache:**
```json
{
  "__type__": "dataframe",
  "value": "{ ... pandas json split ... }"
}
```

**Security check:** Trước khi serve từ cache, `_contains_prohibited_code()` dùng AST parsing để kiểm tra code cache không chứa lệnh đọc file (`open`, `read_csv`, v.v.).

**Retention:** Xóa tự động sau `OPS_FILE_RETENTION_DAYS` ngày (mặc định 14) bởi `run_maintenance()`.

---

## chat_history/ — Lịch sử Hội thoại

**Quản lý bởi:** `services/chat_service.py`

**Một file JSON mỗi user:** `chat_history/{username}.json`

**Cấu trúc:**
```json
{
  "active_chat_id": "abc123",
  "conversations": [
    {
      "id": "abc123",
      "title": "Phân tích doanh thu tháng 3",
      "created_at": "2025-01-01T00:00:00Z",
      "updated_at": "2025-01-01T12:00:00Z",
      "messages": [
        {"role": "user", "question": "Tổng doanh thu là bao nhiêu?"},
        {
          "role": "assistant",
          "response": {
            "__type__": "dataframe",
            "value": "{ ... pandas json split ... }"
          }
        }
      ]
    }
  ]
}
```

**Thread safety:** Mỗi user có `threading.Lock` riêng — tất cả thao tác ghi đều atomic (read-modify-write có lock).

**Retention:** Chat history **KHÔNG bị xóa** bởi `run_maintenance()`. Chỉ xóa thủ công qua UI hoặc API.

---

## logs/ — Log Ứng dụng

**Quản lý bởi:** `services/ops_service.configure_logging()`

**File:** `logs/app.log` với `RotatingFileHandler`:
- Kích thước tối đa: 2 MB mỗi file
- Số file giữ lại: 5 (tổng tối đa 10 MB)
- Level: `APP_LOG_LEVEL` env var (mặc định `INFO`)

**Format log:**
```
2025-01-01 12:00:00 INFO ai_datanalysis query_success user=alice latency_ms=1250
```

**Log levels:**
| Level | Khi nào |
|-------|---------|
| `DEBUG` | Chi tiết pipeline, prompt, AST validation |
| `INFO` | Query thành công, đăng nhập, startup |
| `WARNING` | Cache miss, retry LLM, encoding fallback |
| `ERROR` | Lỗi thực thi, lỗi DB, lỗi LLM |

---

## Khởi tạo tự động

`paths.py` tạo tất cả thư mục runtime khi được import:

```python
for d in [UPLOADS_DIR, CHAT_HISTORY_DIR, LOGS_DIR, CACHE_CODE_DIR, CACHE_RESULTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)
```

Không cần tạo thư mục thủ công trước khi chạy app.
