# scripts/ — Utility Scripts

Chứa các script bảo trì và phát triển — không thuộc luồng runtime của app. Chỉ chạy thủ công khi cần.

---

## Danh sách script

| File | Mục đích |
|------|---------|
| `extract_pkl.py` | Debug và migration từ chat history định dạng pickle cũ |
| `standardize_all_plots.py` | Tái sinh đồng loạt chart prompt templates |

---

## `extract_pkl.py` — Inspect Legacy Pickle

### Mục đích

Đọc và hiển thị nội dung file chat history cũ ở định dạng pickle (`.pkl`) — định dạng lưu trữ trước khi hệ thống chuyển sang JSON.

Dùng để:
- Debug khi cần xem code Python từ một lượt chat cũ
- Migration dữ liệu từ định dạng pickle sang JSON mới

### Cách chạy

```bash
poetry run python scripts/extract_pkl.py
```

### Input

Mặc định đọc từ:
```
data/runtime/chat_history/kiet.pkl
```

### Output

In ra stdout tất cả Python code từ các lượt chat có role `assistant`:

```
--- Code from turn 3 ---
df = DF_1.copy()
fig = px.bar(df, x="product", y="revenue")
result = fig
---------------------------
```

### Khi nào cần chỉnh sửa

Thay đổi `LEGACY_PICKLE` trong file nếu cần đọc file pickle của user khác:

```python
LEGACY_PICKLE = ROOT_DIR / "data" / "runtime" / "chat_history" / "other_user.pkl"
```

---

## `standardize_all_plots.py` — Chuẩn hóa Chart Templates

### Mục đích

Tái sinh đồng loạt 14 chart prompt templates theo một cấu trúc chuẩn thống nhất. Đảm bảo tất cả templates có cùng:
- Quy tắc reasoning (aggregate trước khi plot, filter trước aggregate)
- Quy tắc làm sạch dữ liệu
- Cấu trúc output (title, width, height, margin)
- Hướng dẫn special cases (wide/long format, top-N)

### Cách chạy

```bash
poetry run python scripts/standardize_all_plots.py
# Output: Done!
```

### File được tái sinh

Script dựa trên `CONFIG` dict — mỗi entry là `filename: (CHART_UPPER, chart_default, plotly_example)`:

```python
CONFIG = {
    "line_plot.txt":            ("LINE CHART", "line chart", "px.line(...)"),
    "scatter_2d_plot.txt":      ("SCATTER PLOT", "scatter plot", "px.scatter(...)"),
    "histogram_plot.txt":       ("HISTOGRAM", "histogram", "px.histogram(...)"),
    # ... 11 loại biểu đồ khác
}
```

### File được bảo vệ (KHÔNG bị ghi đè)

```python
if name in ["table.txt", "table_plotly.txt", "bar_plot.txt"]:
    continue  # skip
```

- `bar_plot.txt` — tùy chỉnh thủ công (wide/long format detection)
- `table.txt` — không dùng Plotly figure
- `table_plotly.txt` — dùng `go.Table`

### Khi nào cần chạy

- Sau khi chỉnh sửa `TEMPLATE` chung trong script (áp dụng cho tất cả templates)
- Sau khi thêm entry mới vào `CONFIG`
- Khi cần reset một template về cấu trúc chuẩn sau khi chỉnh sửa tay

### Lưu ý

Script ghi thẳng vào `prompts/chart_templates/*.txt`. **Backup trước khi chạy** nếu có chỉnh sửa tay chưa được lưu:

```bash
cp -r prompts/chart_templates prompts/chart_templates_backup
poetry run python scripts/standardize_all_plots.py
```
