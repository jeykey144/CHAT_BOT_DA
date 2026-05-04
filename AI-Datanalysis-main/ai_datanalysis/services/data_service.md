# data_service.py — Data Service

Tầng dịch vụ quản lý toàn bộ vòng đời dữ liệu: upload, lưu trữ, nạp lại và phân tích quan hệ.

---

## Mục đích

| Vấn đề trước đây | Giải pháp |
|------------------|-----------|
| `app.py` import trực tiếp từ `dataset_service` và `data_catalog` | Gom về `data_service.py` |
| Logic nạp dữ liệu user lặp lại ở nhiều nơi | Một hàm `load_user_data(user)` |
| Thiếu error handling khi build catalog | `build_catalog()` bắt exception, trả `{}` |

---

## Phụ thuộc nội bộ

```
data_service.py
  ├── ai_datanalysis.services.dataset_service  → upload, lưu, nạp file
  └── ai_datanalysis.core.data_catalog         → phân tích quan hệ bảng
```

`dataset_service.py` giữ nguyên — `data_service.py` là **facade** bên trên.

---

## Giới hạn upload (kế thừa từ dataset_service)

| Giới hạn | Giá trị |
|----------|---------|
| Số file / lần upload | 5 |
| Kích thước file | 10 MB |
| Số rows / DataFrame | 250.000 |
| Số columns / DataFrame | 200 |
| Số sheets Excel | 10 |

---

## API

### `load_files(uploaded_files) → Dict[str, pd.DataFrame]`

Nạp file upload (từ Streamlit) thành dict DataFrame. Không lưu vào disk.

```python
from ai_datanalysis.services.data_service import load_files

data = load_files(st.session_state["uploaded_files"])
# {"DF_1___sales.csv": df1, "DF_2___products.xlsx::sheet_0::Sheet1": df2}
```

---

### `save_user_files(user, uploaded_files, append=True) → list[str]`

Lưu file vào thư mục của user và cập nhật manifest.

```python
from ai_datanalysis.services.data_service import save_user_files

paths = save_user_files("alice", uploaded_files, append=True)
# ["data/runtime/uploads/alice/20250101_120000_sales.csv", ...]
```

**Cấu trúc thư mục:**
```
data/runtime/uploads/
└── {username}/
    ├── manifest.json
    ├── 20250101_120000_sales.csv
    └── 20250101_120005_products.xlsx
```

---

### `load_user_manifest(user) → list[str]`

Đọc danh sách đường dẫn file đã lưu.

```python
from ai_datanalysis.services.data_service import load_user_manifest

paths = load_user_manifest("alice")
# ["data/runtime/uploads/alice/20250101_120000_sales.csv"]
```

---

### `load_user_data(user) → Dict[str, pd.DataFrame]`

Kết hợp manifest + load file trong một bước. Dùng cho app startup.

```python
from ai_datanalysis.services.data_service import load_user_data

data = load_user_data("alice")
# Trả {} nếu user chưa có dữ liệu
```

**Pattern trong app.py:**
```python
if st.session_state.get("user") and not st.session_state.get("data"):
    data_loaded = load_user_data(st.session_state["user"])
    if data_loaded:
        st.session_state["data"] = data_loaded
```

---

### `clear_user_data(user) → None`

Xóa manifest của user (không xóa file vật lý).

```python
from ai_datanalysis.services.data_service import clear_user_data

clear_user_data("alice")
```

---

### `build_catalog(data) → dict`

Phân tích quan hệ giữa các bảng. Trả `{}` nếu lỗi hoặc data rỗng.

```python
from ai_datanalysis.services.data_service import build_catalog

catalog = build_catalog({"sales": df_sales, "products": df_products})
# {
#   "overview": {"dataset_count": 2, "recommended_join_count": 1},
#   "relationships": [{"left_dataset": "sales", "left_key": "product_id", ...}],
#   "master_tables": [...],
#   "table_roles": {"sales": "fact", "products": "dimension"},
# }
```

---

## Bảo mật path traversal

Khi nạp từ manifest, mọi path đều được kiểm tra:
```python
allowed_root = UPLOADS_DIR / normalize_user(user)
if allowed_root not in resolved_path.parents:
    continue  # bỏ qua file ngoài thư mục của user
```

---

## CSV Encoding Detection

Thử tuần tự: `utf-8` → `utf-8-sig` → `cp1258` (tiếng Việt) → `latin1`.
Fallback về pandas default nếu tất cả thất bại.
