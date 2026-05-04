# data/samples/ — Dataset Mẫu

Chứa các dataset tĩnh dùng cho benchmark, demo và kiểm tra hệ thống. Đây là dữ liệu tham chiếu — không phải output runtime.

---

## Danh sách file

### Dataset CSV (tabular)

| File | Mô tả | Cột chính |
|------|-------|-----------|
| `bike_sharing_benchmark.csv` | Dữ liệu thuê xe đạp theo ngày/giờ | `date`, `season`, `temperature_c`, `humidity`, `total_rides` |
| `retail_sales_benchmark.csv` | Doanh thu bán lẻ theo sản phẩm và khu vực | `date`, `product`, `region`, `quantity`, `revenue` |
| `exam_scores_benchmark.csv` | Điểm thi học sinh nhiều môn | `student_id`, `province`, `toan`, `van`, `anh`, `li`, `hoa`, `sinh` |
| `disoccupazione.csv` | Tỷ lệ thất nghiệp theo quý và vùng (Italy) | `year`, `quarter`, `region`, `unemployment_rate` |
| `monthly.csv` | Chuỗi thời gian theo tháng | `month`, `year`, `value` |

### File hỗ trợ

| File | Mô tả | Dùng để |
|------|-------|---------|
| `geojson_brasil.json` | GeoJSON bản đồ các bang Brazil | Biểu đồ choropleth / map |
| `reproducibility_prompts.txt` | Danh sách câu hỏi mẫu theo từng dataset | Tái hiện truy vấn, benchmark |

---

## Mục đích sử dụng

### 1. Benchmark pipeline

Dùng các file CSV để kiểm tra luồng xử lý từ đầu đến cuối:

```bash
# Upload bike_sharing_benchmark.csv lên app, sau đó hỏi:
"Vẽ biểu đồ đường thể hiện tổng số lượt đi theo tháng"
"Nhiệt độ trung bình theo mùa là bao nhiêu?"
"Hãy phân tích tổng quan dữ liệu"
```

### 2. Test nhận diện cột đặc biệt

- `exam_scores_benchmark.csv` — test WIDE FORMAT (nhiều cột môn học) trong bar chart
- `bike_sharing_benchmark.csv` — test nhận diện cột `temperature_c` (numeric), `season` (categorical), `date` (datetime)
- `disoccupazione.csv` — test multi-language data, chuỗi thời gian

### 3. Tái hiện kịch bản

`reproducibility_prompts.txt` chứa danh sách câu hỏi mẫu kèm dataset tương ứng để kiểm tra tính ổn định của pipeline qua nhiều lần chạy.

---

## Thêm dataset mẫu mới

1. Đặt file CSV/XLSX vào thư mục này
2. Cập nhật bảng danh sách trong file này
3. Thêm câu hỏi mẫu vào `reproducibility_prompts.txt` nếu cần
4. Commit vào git (samples được version control)
