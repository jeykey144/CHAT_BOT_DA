# ai_datanalysis/ui — Tầng giao diện Streamlit

Chứa toàn bộ code Streamlit: components tương tác người dùng và rendering kết quả.
Đây là tầng **duy nhất** được phép gọi `st.*`.

---

## Danh sách file

| File | Vai trò |
|------|---------|
| `components.py` | Auth, dataset upload, settings, action bar |
| `render.py` | Render kết quả pipeline ra màn hình |
| `__init__.py` | Package marker |

---

## Nguyên tắc của tầng UI

1. **Chỉ tầng này gọi `st.*`** — không có `st.plotly_chart` trong services/.
2. **Không chứa business logic** — không tính toán, không gọi LLM, không query DB.
3. **Nhận dữ liệu đã build sẵn** từ services, render ra màn hình.
4. **Tương tác qua `st.session_state`** để truyền trạng thái.

---

## render.py — Render Layer

### Mục đích

Nhận output từ pipeline (`ExecOutcome.result`, `build_dashboard_report()`) và render ra Streamlit với định dạng phù hợp.

### Hàm chính

```python
from ai_datanalysis.ui.render import render_result

render_result(outcome.result)
```

### Dispatch theo kiểu dữ liệu

| Kiểu `result` | Cách render |
|---------------|-------------|
| `dict` `__type__ == "dashboard_report"` | Full report nhiều section với overview metrics |
| `dict` `__type__ == "dashboard"` | Single dashboard: KPI cards + chart grid + insights |
| `go.Figure` | `st.plotly_chart(result, use_container_width=True)` |
| `pd.DataFrame` | `st.dataframe(result, use_container_width=True)` |
| `list` hoặc `tuple` | Render từng phần tử có đánh số |
| Khác | `st.write(result)` |

### Layout dashboard

```
[Header + subtitle]
[Overview metrics — 4 cột]
[Expander: Toàn cảnh dữ liệu]
  Section 1:
    [top sections — full width]
    [main (3) | side (1.2)]
      ├── KPI cards (4 per row)
      ├── Chart grid (2 per row)
      ├── Insight box
      └── Quality metrics
```

### Vì sao render.py nằm trong ui/ không phải services/?

`render_service.py` cũ nằm sai tầng vì nó gọi `st.*` (UI concern) từ services/ (business logic layer).

```
TRƯỚC (sai):              SAU (đúng):
services/
  render_service.py       services/
    import streamlit ←✗     chart_service.py   ← build only
                          ui/
                            render.py          ← st.* calls
```

---

## components.py — UI Components

### auth_sidebar(auth_engine)

Sidebar trạng thái đăng nhập. Hiển thị username + nút "Đăng xuất" khi đã login.

### auth_main(auth_engine)

Màn hình chính khi chưa đăng nhập: 2 tab Đăng nhập / Đăng ký.

### dataset_sidebar()

Sidebar quản lý dữ liệu:
- Chưa có data: file_uploader
- Đã có data: thống kê catalog, preview quan hệ bảng, xem nhanh data

### dataset_main()

Màn hình upload dữ liệu (khi đã login nhưng chưa có data).

### settings_sidebar()

Cài đặt: chế độ riêng tư, vai trò dashboard, chọn model Groq.

### main_action_bar(auth_engine)

Thanh 7 nút: Đăng xuất | Tải mới | Xóa data | Khám phá | Xóa chat | Chat mới | Dashboard.

---

## Session state keys

| Key | Kiểu | Mô tả |
|-----|------|-------|
| `user` | `str \| None` | Username đang đăng nhập |
| `session_token` | `str \| None` | Session token |
| `messages` | `list[dict]` | Lịch sử chat trong session |
| `active_chat_id` | `str \| None` | ID conversation đang mở |
| `data` | `Dict[str, DataFrame]` | Các bảng dữ liệu đã nạp |
| `dfs_var` | `list[DataFrame]` | Danh sách DataFrame |
| `data_catalog` | `dict` | Metadata quan hệ bảng |
| `last_code` | `str` | Code Python sinh ra lần cuối |
| `last_error` | `str` | Lỗi thực thi lần cuối |
| `sample_var` | `int` | Số hàng mẫu gửi LLM (0=tắt, 5=bật) |
| `dashboard_role` | `str` | Vai trò dashboard |
| `selected_model` | `str` | Model Groq đang dùng |
| `uploader_nonce` | `int` | Force reset file_uploader widget |
| `trigger_auto_profile` | `bool` | Signal kích hoạt auto-profile |
| `trigger_auto_dashboard` | `bool` | Signal kích hoạt auto-dashboard |

---

## Dependency

```
ui/render.py
  └── (chỉ streamlit + pandas + plotly — không import services)

ui/components.py
  ├── ai_datanalysis.auth
  ├── ai_datanalysis.core.data_catalog
  ├── ai_datanalysis.llm_factory          (danh sách model Groq)
  ├── ai_datanalysis.services.chat_service
  └── ai_datanalysis.services.data_service  (thay dataset_service)
```
