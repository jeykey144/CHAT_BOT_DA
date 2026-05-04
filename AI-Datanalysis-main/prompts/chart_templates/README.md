# prompts/chart_templates/ — Đặc tả Chart Templates

Mỗi file `.txt` là một prompt template hướng dẫn LLM sinh Python code cho một loại biểu đồ hoặc loại phân tích cụ thể. Được nạp bởi `core/prompt_builder.py` và ghép với context dữ liệu thực tế trước khi gửi đến LLM.

---

## Danh sách 19 templates

| File | Loại | Thư viện Plotly | Khi nào dùng |
|------|------|-----------------|--------------|
| `bar_plot.txt` | Bar chart | `go.Bar` | So sánh giá trị theo danh mục; count/mean/sum theo nhóm |
| `line_plot.txt` | Line chart | `px.line` | Xu hướng theo thời gian; chuỗi liên tục |
| `scatter_2d_plot.txt` | Scatter plot | `px.scatter` | Tương quan 2 biến số |
| `histogram_plot.txt` | Histogram | `px.histogram` | Phân phối của một biến số |
| `box_plot.txt` | Box plot | `px.box` | Phân phối + outlier theo nhóm |
| `violin_plot.txt` | Violin plot | `px.violin` | Phân phối mật độ theo nhóm (chi tiết hơn box plot) |
| `pie_plot.txt` | Pie / Donut chart | `px.pie` | Tỷ lệ phần trăm; cơ cấu thành phần |
| `area_plot.txt` | Area chart | `px.area` | Xu hướng + diện tích (stacked area) |
| `bubble_plot.txt` | Bubble chart | `px.scatter` + `size=` | Tương quan 3 chiều (x, y, kích thước) |
| `heatmap.txt` | Heatmap | `px.density_heatmap` | Ma trận tương quan; mật độ 2D |
| `candle_plot.txt` | Candlestick | `go.Candlestick` | Dữ liệu tài chính OHLCV |
| `density_contour_plot.txt` | Density contour | `px.density_contour` | Phân phối 2D dạng đường đồng mức |
| `polar_plot.txt` | Polar / Radar | `px.line_polar` | So sánh đa chiều trên trục cực |
| `sunburst_plot.txt` | Sunburst | `px.sunburst` | Phân cấp cây dạng vòng tròn |
| `treemap_plot.txt` | Treemap | `px.treemap` | Phân cấp cây dạng hình chữ nhật |
| `table.txt` | DataFrame table | `pd.DataFrame` | Hiển thị bảng dữ liệu thuần túy |
| `table_plotly.txt` | Plotly table | `go.Table` | Hiển thị bảng với định dạng Plotly (header màu sắc) |
| `auto_profile.txt` | Auto profile | custom code | Phân tích tổng quan toàn bộ dataset |
| `generic_plot.txt` | Generic fallback | bất kỳ | Khi router không xác định được loại biểu đồ |

---

## Cấu trúc chung của mỗi template

```
# {CHART_TYPE} GENERATION RULES

Create exactly ONE valid Plotly {chart_name} and assign it to variable: result.

## Libraries
Use: pandas as pd, numpy as np, plotly.graph_objects as go, plotly.express as px

## Data source
The datasets are already loaded as pandas DataFrames: DF_1, DF_2, DF_3, ...
Choose the most relevant DataFrame for the user request.

## Critical reasoning rules
1) Aggregate before plotting when user asks for averages/sums/counts
2) Filter before aggregating (boolean indexing)
3) ...

## Data cleaning & Filtering rules
- df = DF_n.copy()
- pd.to_numeric(..., errors="coerce")
- dropna(subset=[...])

## Output structure
[Code skeleton với placeholder]

result = fig
```

---

## Chi tiết template quan trọng

### `bar_plot.txt` — Phức tạp nhất

Template bar chart xử lý 2 định dạng dữ liệu khác nhau:

**WIDE FORMAT** — mỗi cột là một danh mục so sánh:
```python
# Ví dụ cột: ['StudentID', 'Toan', 'Van', 'Anh', 'Li']
numeric_cols = ['Toan', 'Van', 'Anh', 'Li']
agg = df[numeric_cols].mean()
# x = agg.index (tên môn), y = agg.values (điểm trung bình)
```

**LONG FORMAT** — một cột label, một cột value:
```python
# Ví dụ cột: ['MonHoc', 'Diem', 'StudentID']
agg = df.groupby('MonHoc')['Diem'].mean()
# x = agg.index, y = agg.values
```

Template cảnh báo rõ ràng:
- `NEVER plot raw rows as bars` khi user yêu cầu tổng hợp
- Mỗi danh mục chỉ được tạo một bar (trừ grouped/stacked được yêu cầu rõ)

---

### `auto_profile.txt` — Phân tích tổng quan

Sinh code phân tích tự động toàn bộ dataset:

**Phân loại cột:**
- `numeric` — giá trị liên tục (mean, std, min, max, outlier)
- `categorical` — chuỗi văn bản (top values, cardinality)
- `datetime` — cột năm/tháng (không tính mean)
- `id` — mã định danh (StudentID, SBD, ...) — không tính thống kê
- `boolean` — True/False

**Output:** tuple `(summary_df, insight_text)`

```python
result = (summary_df, insight_text)
```

Được render bởi `render_service.py`:
- `summary_df` → `st.dataframe()`
- `insight_text` → `st.markdown()`

---

### `generic_plot.txt` — Fallback

Dùng khi Router trả `graph_type=None`. Template cho phép LLM tự chọn loại biểu đồ phù hợp nhất dựa vào câu hỏi và schema dữ liệu. Vẫn phải gán `result = fig`.

---

## Layout chuẩn cho figure

| Thuộc tính | Giá trị |
|-----------|---------|
| `width` | 900–950 |
| `height` | 500–600 |
| `margin.l / .r` | 40 |
| `margin.t` | 65 |
| `margin.b` | 65 (hoặc 120 nếu label xoay dài) |
| `title_font_size` | 20 |

```python
fig.update_layout(
    title="<TITLE>",
    width=900,
    height=600,
    margin=dict(l=40, r=40, t=65, b=65),
    title_font_size=20,
)
result = fig  # KHÔNG gọi fig.show()
```

---

## Quy tắc bắt buộc (mọi template)

```python
# 1. Copy trước khi xử lý
df = DF_n.copy()

# 2. Filter TRƯỚC aggregate (nếu user yêu cầu subset)
df = df[df['col'].str.contains('value', case=False, na=False)]

# 3. Làm sạch numeric
df["col"] = pd.to_numeric(df["col"], errors="coerce")
df = df.dropna(subset=["col"])

# 4. Aggregate nếu user hỏi trung bình/tổng/đếm theo nhóm
agg = df.groupby("category", as_index=False)["metric"].mean()

# 5. Tạo figure
fig = px.bar(agg, x="category", y="metric")  # hoặc go.*

# 6. Update layout
fig.update_layout(title="...", width=900, height=600, ...)

# 7. Gán kết quả
result = fig
```

---

## Cập nhật hàng loạt

```bash
# Tái sinh 14 templates theo cấu trúc chuẩn (trừ bar, table, table_plotly)
python scripts/standardize_all_plots.py
```

File được bảo vệ khỏi ghi đè tự động (cần chỉnh sửa thủ công):
- `bar_plot.txt` — wide/long format detection logic
- `table.txt` — không dùng Plotly figure
- `table_plotly.txt` — dùng `go.Table` thay vì `px.*`
