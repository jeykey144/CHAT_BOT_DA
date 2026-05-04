# chart_service.py — Chart Service

Module xây dựng biểu đồ thuần túy (pure functions) — không phụ thuộc Streamlit.

---

## Mục đích

| Vấn đề trước đây | Giải pháp |
|------------------|-----------|
| `render_service.py` trộn lẫn build chart + `st.*` calls | Tách thành `chart_service.py` (build) + `ui/render.py` (display) |
| Không thể test chart logic mà không có Streamlit | Pure functions, test bình thường với pytest |
| Không thể dùng ngoài Streamlit (API, Jupyter) | Import và gọi trực tiếp |

---

## Nguyên tắc

```
chart_service.py       → BUILD  (trả go.Figure, list[dict])
ui/render.py           → RENDER (gọi st.plotly_chart, st.metric, ...)
```

**Không có `import streamlit` trong file này.**

---

## API

### Chart builders

Tất cả hàm nhận `pd.DataFrame`, trả `go.Figure`.

#### `build_bar_chart(df, x, y, title, color, barmode, orientation)`

```python
from ai_datanalysis.services.chart_service import build_bar_chart

fig = build_bar_chart(df, x="month", y="revenue", title="Doanh thu theo tháng")
fig = build_bar_chart(df, x="category", y="count", barmode="stack", orientation="h")
```

#### `build_line_chart(df, x, y, title, color, markers)`

```python
fig = build_line_chart(df, x="date", y=["revenue", "cost"], title="Xu hướng")
fig = build_line_chart(df, x="month", y="sales", markers=True)
```

#### `build_histogram(df, column, title, nbins, color)`

```python
fig = build_histogram(df, column="age", title="Phân phối tuổi", nbins=20)
```

#### `build_scatter(df, x, y, title, color, size, hover_data)`

```python
fig = build_scatter(df, x="price", y="quantity", color="category", size="profit")
```

#### `build_pie_chart(df, names, values, title, hole)`

```python
fig = build_pie_chart(df, names="region", values="revenue", hole=0.3)  # donut
```

#### `build_box_chart(df, x, y, title, color)`

```python
fig = build_box_chart(df, x="category", y="score", title="Phân phối điểm")
```

#### `build_heatmap(df, title, color_scale)`

```python
corr = df.select_dtypes("number").corr()
fig = build_heatmap(corr, title="Ma trận tương quan")
```

---

### KPI helpers

#### `build_kpi_summary(df, numeric_columns, max_kpis) → list[dict]`

Trích xuất KPI từ DataFrame, tối đa `max_kpis` (mặc định 8).

```python
from ai_datanalysis.services.chart_service import build_kpi_summary

kpis = build_kpi_summary(df_sales)
# [
#   {"label": "Revenue", "value": "1,234,567", "mean": "102,880.58", "delta": None},
#   {"label": "Profit", "value": "456,789", "mean": "38,065.75", "delta": None},
# ]
```

Kết quả có thể truyền vào `_render_kpis()` trong `ui/render.py`.

---

### Result normalizer

#### `prepare_result_for_render(result) → dict`

Chuẩn hóa output pipeline thành typed descriptor cho UI layer.

```python
from ai_datanalysis.services.chart_service import prepare_result_for_render

descriptor = prepare_result_for_render(outcome.result)
# {"type": "figure", "data": go.Figure(...)}
# {"type": "dataframe", "data": pd.DataFrame(...)}
# {"type": "dashboard_report", "data": {...}}
# {"type": "list", "data": [...]}
# {"type": "text", "data": "..."}
```

UI layer dùng `descriptor["type"]` để chọn cách render, thay vì kiểm tra type trực tiếp.

---

## Dùng kết hợp với ui/render.py

```python
# Service layer — build
from ai_datanalysis.services.chart_service import build_bar_chart, build_kpi_summary

fig = build_bar_chart(df, x="month", y="revenue", title="Doanh thu")
kpis = build_kpi_summary(df)

# UI layer — render (trong Streamlit)
from ai_datanalysis.ui.render import render_result
import streamlit as st

st.plotly_chart(fig, use_container_width=True)
for kpi in kpis:
    st.metric(kpi["label"], kpi["value"])
```

---

## Dùng trong Jupyter / FastAPI

```python
# Không cần Streamlit, dùng bình thường
fig = build_bar_chart(df, x="month", y="revenue")
fig.show()   # Jupyter
fig.write_html("chart.html")   # Export
```
