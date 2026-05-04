# prompts/ — Hệ thống Prompt

Chứa toàn bộ prompt templates sử dụng trong AI pipeline. Mỗi template là file `.txt` định nghĩa cách LLM sinh Python code để phân tích dữ liệu hoặc tạo biểu đồ.

---

## Cấu trúc

```
prompts/
├── README.md                  ← tài liệu này
└── chart_templates/
    ├── README.md              ← đặc tả từng chart template
    ├── bar_plot.txt
    ├── line_plot.txt
    ├── scatter_2d_plot.txt
    ├── histogram_plot.txt
    ├── box_plot.txt
    ├── violin_plot.txt
    ├── pie_plot.txt
    ├── area_plot.txt
    ├── bubble_plot.txt
    ├── heatmap.txt
    ├── candle_plot.txt
    ├── density_contour_plot.txt
    ├── polar_plot.txt
    ├── sunburst_plot.txt
    ├── treemap_plot.txt
    ├── table.txt
    ├── table_plotly.txt
    ├── auto_profile.txt
    └── generic_plot.txt
```

---

## Cách hoạt động

### 1. Chọn template

`core/prompt_builder.py` nhận `graph_type` từ Router và ánh xạ sang file template:

```python
graph_type_to_template = {
    "bar_plot":             "bar_plot.txt",
    "line_plot":            "line_plot.txt",
    "scatter_2d_plot":      "scatter_2d_plot.txt",
    "histogram_plot":       "histogram_plot.txt",
    "box_plot":             "box_plot.txt",
    "violin_plot":          "violin_plot.txt",
    "pie_plot":             "pie_plot.txt",
    "area_plot":            "area_plot.txt",
    "bubble_plot":          "bubble_plot.txt",
    "heatmap":              "heatmap.txt",
    "candle_plot":          "candle_plot.txt",
    "density_contour_plot": "density_contour_plot.txt",
    "polar_plot":           "polar_plot.txt",
    "sunburst_plot":        "sunburst_plot.txt",
    "treemap_plot":         "treemap_plot.txt",
    "table":                "table.txt",
    "table_plotly":         "table_plotly.txt",
    "auto_profile":         "auto_profile.txt",
    None:                   "generic_plot.txt",
}
```

### 2. Build prompt đầy đủ

Template được nạp và kết hợp với context thực tế:

```
[SYSTEM INSTRUCTIONS]
[NỘI DUNG TEMPLATE — chart generation rules]

---

User question: {câu hỏi người dùng}

Available DataFrames:
- DF_1: {tên cột + dtype}
- DF_2: {tên cột + dtype}

{sample_head — 5 hàng đầu, chỉ nếu sample_var > 0}
{join_plan — nếu có bảng đề xuất join}
{semantic_columns — nếu phát hiện cột ngày/tiền/tỷ lệ đặc biệt}

Output: raw Python code only. No markdown fences.
```

### 3. LLM sinh code

LLM nhận prompt → trả về Python code dạng plain text.

### 4. Extract code

`core/agent.py` trích xuất code từ response: bóc tách markdown fences (```python ... ```) nếu LLM vô tình thêm.

### 5. Execute trong sandbox

Code chạy qua `LocalRestrictedExecutor` với môi trường:
- `DF_1`, `DF_2`, ... — các DataFrame đã được chọn bởi Dataset Selector
- Biến `result` — biến mà code phải gán kết quả vào

---

## Quy tắc chung của mọi template

Tất cả chart templates đều yêu cầu LLM:

1. **Một biến kết quả duy nhất:** `result = fig` hoặc `result = df`
2. **Không gọi `fig.show()`** — Streamlit tự render qua `render_service.py`
3. **Không dùng markdown fence** — output phải là raw Python, không có ``` ```
4. **Copy trước khi xử lý:** `df = DF_n.copy()`
5. **Làm sạch numeric columns:** `pd.to_numeric(..., errors="coerce")`
6. **Filter TRƯỚC aggregate:** Nếu user yêu cầu subset → boolean indexing trước `groupby`
7. **Aggregate trước plot:** Nếu user hỏi trung bình/tổng/đếm → `groupby().agg()` trước, không plot raw rows

---

## Cập nhật template

Để cập nhật đồng loạt 14 chart templates theo cấu trúc chuẩn:

```bash
python scripts/standardize_all_plots.py
```

File không bị ghi đè tự động (tùy chỉnh thủ công):
- `bar_plot.txt` — logic wide/long format đặc biệt
- `table.txt` — không dùng Plotly
- `table_plotly.txt` — dùng `go.Table`

---

## Thêm template mới

1. Tạo `chart_templates/{chart_type}.txt` theo cấu trúc chuẩn
2. Thêm ánh xạ trong `core/prompt_builder.py`
3. Thêm keyword nhận diện trong `core/router.py`
4. (Tùy chọn) Thêm vào `CONFIG` trong `scripts/standardize_all_plots.py`
