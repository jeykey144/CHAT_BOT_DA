# tests/ — Hướng dẫn Kiểm thử

Chứa unit tests cho các khối logic quan trọng của pipeline AI. Tests không phụ thuộc vào database, LLM hay network — tất cả chạy offline với dữ liệu giả lập.

---

## Chạy tests

```bash
# Chạy toàn bộ test suite
poetry run pytest tests/ -v

# Chạy một file test cụ thể
poetry run pytest tests/test_router.py -v

# Chạy một test cụ thể
poetry run pytest tests/test_fast_path.py::test_fast_path_top_n -v

# Chạy với coverage
poetry run pytest tests/ --cov=ai_datanalysis --cov-report=term-missing
```

---

## Danh sách file test

| File | Module được test | Nội dung |
|------|-----------------|---------|
| `test_normalization.py` | `core/normalization.py` | Chuẩn hóa query: lowercase, bỏ dấu, mở rộng viết tắt |
| `test_router.py` | `core/router.py` | Phân loại intent, nhận diện graph type, follow-up |
| `test_selector.py` | `core/selector.py` | Chọn dataset phù hợp theo query |
| `test_data_catalog.py` | `core/data_catalog.py` | Phát hiện quan hệ bảng, nhóm độc lập |
| `test_join_planner.py` | `core/join_planner.py` | Kế hoạch join bảng, tìm khóa chung |
| `test_prompt_builder.py` | `core/prompt_builder.py` | Sinh prompt đầy đủ, load template đúng |
| `test_fast_path.py` | `core/fast_path.py` | Fast path: top-N, count, min/max, mean, skip chart queries |
| `test_dashboard_service.py` | `services/dashboard_service.py` | Sinh dashboard KPI, chart, insight |

---

## Chi tiết từng nhóm test

### `test_normalization.py`

Kiểm tra hàm `normalize_query()`:

```python
test_normalization_lowercases()           # "TeSt" → "test"
test_normalization_removes_accents()       # "Đếm KẾT QUẢ" → "dem ket qua"
test_normalization_expands_abbreviations() # "sp" → "san pham", "sl" → "so luong"
test_normalization_removes_extra_spaces()  # "  tinh    tong " → "tinh tong"
```

---

### `test_router.py`

Kiểm tra `route_query()` và `infer_graph_type()`:

```python
test_intent_routing()   # "tính tổng" → intent "calculation"
                        # "so sánh" → intent "comparison"
                        # "nhân viên nào có lương > 10tr" → intent "filter"

test_graph_inference()  # "vẽ biểu đồ phân tán" → "scatter_2d_plot"
                        # "tỷ lệ doanh thu theo vùng" → "pie_plot"
                        # "khám phá dữ liệu" → "auto_profile"

test_follow_up()        # "vẽ lại biểu đồ trên nhưng đổi màu" → is_follow_up=True
```

---

### `test_selector.py`

Kiểm tra `select_datasets()` — scoring theo tên cột so với từ khóa query:

```python
test_selector()  # query "doanh thu và chi phí" → chọn "sales.csv" (có cột doanh_thu, chi_phi)
                 # query "tuổi nhân viên" → chọn "hr.csv" (có cột nhan_vien, tuoi)
```

---

### `test_fast_path.py`

Kiểm tra toàn bộ fast path — các trường hợp xử lý không cần LLM:

```python
test_fast_path_top_n()                      # "top 5" → code có "head(5)"
test_fast_path_count()                      # "tổng số dòng" → code có "len"
test_fast_path_min_max_temperature_bike_sharing()  # nhận diện cột "temperature_c"
test_fast_path_average_total_rides()               # nhận diện cột "total_rides", sinh ".mean()"
test_fast_path_generic_salary_min_max()            # nhận diện cột "salary_usd"
test_fast_path_generic_revenue_average()           # nhận diện cột "monthly_revenue"
test_fast_path_skips_chart_queries()               # "vẽ biểu đồ" → fast_path trả về None
test_auto_profile_treats_student_id_like_column_as_id()  # "sbd" → nhóm "id"
test_auto_profile_treats_year_month_as_datetime_not_numeric()  # "year", "month" → "datetime"
```

---

### `test_data_catalog.py`, `test_join_planner.py`

Kiểm tra phát hiện quan hệ giữa các bảng dữ liệu:
- Tìm cột khóa chung giữa 2 DataFrame (overlap ratio, confidence)
- Nhóm bảng độc lập khi không có khóa chung
- Kế hoạch join (INNER, LEFT) với bảng master đề xuất

---

### `test_prompt_builder.py`

Kiểm tra `build_prompt()`:
- Load đúng template theo `graph_type`
- Schema DataFrame xuất hiện trong prompt
- Sample head xuất hiện khi `sample_n > 0`
- Join plan được nhúng khi có đề xuất

---

### `test_dashboard_service.py`

Kiểm tra `build_dashboard_report()`:
- Sinh đúng KPI theo role (analyst, ceo, ...)
- Phát hiện domain từ tên cột (sales, finance, education, ...)
- Cấu trúc output: `__type__`, `sections`, `kpis`, `charts`

---

## Nguyên tắc viết test mới

1. **Không mock database hay LLM** — tests phải chạy offline hoàn toàn
2. **Tạo DataFrame nhỏ trực tiếp trong test** — không đọc file CSV
3. **Kiểm tra output cụ thể** — không chỉ kiểm tra `!= None`
4. **Mỗi test function kiểm tra một behavior** — không gộp nhiều assertion không liên quan
5. **Đặt tên rõ ràng** — `test_{module}_{behavior}_{condition}` hoặc `test_{module}_{what_it_does}`

```python
# Ví dụ test mới cho normalization
def test_normalization_handles_empty_string():
    assert normalize_query("") == ""

def test_normalization_handles_numbers():
    assert normalize_query("top 10 san pham") == "top 10 san pham"
```

---

## Chạy trước khi merge

Tối thiểu phải chạy và pass:

```bash
poetry run pytest tests/test_normalization.py tests/test_router.py tests/test_fast_path.py -v
```
