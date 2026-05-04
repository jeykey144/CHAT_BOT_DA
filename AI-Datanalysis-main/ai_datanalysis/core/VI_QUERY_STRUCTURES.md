# Vietnamese Query Structures

Tài liệu này mô tả các mẫu câu truy vấn tiếng Việt mà hệ thống chatbot phân tích dữ liệu có thể hiểu ổn định ngay ở bước `normalize -> route -> select -> prompt`.

Mục tiêu của file:

- Chuẩn hóa cách đặt câu hỏi để hệ thống nhận đúng intent ngay từ đầu.
- Giảm mơ hồ giữa truy vấn tính toán, vẽ biểu đồ, xếp hạng và truy vấn kết hợp.
- Tạo bộ mẫu câu để demo, kiểm thử và viết tài liệu cho người dùng.

File liên quan trong hệ thống:

- `vi_vocab.py`: từ vựng tiếng Việt, viết tắt, keyword intent, keyword chart.
- `normalization.py`: bỏ dấu, mở rộng viết tắt, rút gọn khoảng trắng.
- `router.py`: xác định `intent`, `graph_type`, `follow_up`, `requires_multi_dataset`.
- `semantic_columns.py`: đối chiếu token truy vấn với tên cột dữ liệu.

## 1. Nguyên tắc đặt truy vấn

Hệ thống hiểu tốt nhất khi câu hỏi có cấu trúc rõ ràng:

```text
[hành động] + [chỉ số] + [nhóm / đối tượng] + [thời gian] + [điều kiện] + [kiểu đầu ra]
```

Thành phần khuyến nghị:

- `hành động`: tính, đếm, so sánh, vẽ, hiển thị, xếp hạng, tìm top.
- `chỉ số`: doanh thu, lợi nhuận, chi phí, số lượng, giá trị trung bình, tỷ lệ.
- `nhóm / đối tượng`: theo tháng, theo năm, theo sản phẩm, theo chi nhánh, theo khách hàng.
- `thời gian`: năm 2024, quý 1, tháng 3, từ 2023 đến 2025.
- `điều kiện`: chỉ lấy miền Bắc, bỏ qua đơn hủy, lọc sản phẩm A.
- `kiểu đầu ra`: biểu đồ cột, biểu đồ đường, bảng, dashboard.

Nên ưu tiên câu ngắn gọn, dùng từ khóa rõ ràng, tránh viết câu quá dài nhiều mệnh đề.

## 2. Thành phần placeholder

Trong các mẫu dưới đây:

- `<chỉ_số>`: doanh thu, lợi nhuận, chi phí, số lượng, tỷ lệ, giá trị trung bình.
- `<nhóm>`: tháng, quý, năm, sản phẩm, chi nhánh, nhân viên, khách hàng, khu vực.
- `<điều_kiện>`: chi nhánh Hà Nội, khu vực miền Bắc, năm 2024, sản phẩm A.
- `<top_n>`: top 5, top 10, 3 mục cao nhất.
- `<bảng>`: tên bảng hoặc ngữ cảnh bộ dữ liệu cần phân tích.

## 3. Mẫu truy vấn theo từng loại

### 3.1 Calculation Query

Dùng khi người dùng muốn tính tổng, trung bình, đếm, min, max, tỷ lệ.

Công thức tổng quát:

```text
Tính <chỉ_số> theo <nhóm>
Tính tổng <chỉ_số> theo <nhóm>
Tính trung bình <chỉ_số> theo <nhóm>
Đếm số lượng <đối_tượng> theo <nhóm>
Cho biết <chỉ_số> lớn nhất / nhỏ nhất theo <nhóm>
```

Mẫu câu nên dùng:

```text
Tính tổng doanh thu theo tháng.
Tính trung bình lợi nhuận theo chi nhánh trong năm 2024.
Đếm số lượng hóa đơn theo khu vực.
Cho biết chi phí lớn nhất theo phòng ban.
Tính tỷ lệ doanh thu theo từng sản phẩm.
```

Mẫu câu rút gọn vẫn hệ thống hiểu:

```text
Tổng doanh thu theo tháng
TB lợi nhuận theo chi nhánh
Đếm hóa đơn theo năm
Max doanh thu theo sản phẩm
```

Mục tiêu router:

- `intent`: `calculation`
- `graph_type`: thường là `table` nếu không yêu cầu vẽ biểu đồ.

### 3.2 Chart Query

Dùng khi người dùng muốn vẽ trực quan hóa dữ liệu.

Công thức tổng quát:

```text
Vẽ <loại_biểu_đồ> <chỉ_số> theo <nhóm>
Hiển thị <loại_biểu_đồ> cho <chỉ_số> theo <nhóm>
Tạo biểu đồ <loại_biểu_đồ> thể hiện <chỉ_số> theo <nhóm>
```

Mẫu câu nên dùng:

```text
Vẽ biểu đồ cột doanh thu theo tháng.
Vẽ biểu đồ đường lợi nhuận theo quý.
Hiển thị biểu đồ tròn tỷ lệ doanh thu theo sản phẩm.
Tạo heatmap tương quan giữa doanh thu, chi phí và lợi nhuận.
Vẽ scatter plot giữa doanh thu và chi phí.
```

Mẫu câu rút gọn:

```text
Vẽ cột doanh thu theo tháng
Vẽ đường lợi nhuận theo năm
Vẽ tròn cơ cấu doanh thu theo chi nhánh
Vẽ heatmap tương quan
```

Mục tiêu router:

- `intent`: thường là `trend`, `comparison`, `composition`, `relationship`...
- `graph_type`: `bar_plot`, `line_plot`, `pie_plot`, `heatmap`, `scatter_2d_plot`...

### 3.3 Max / Min / Ranking Query

Loại này trong hệ thống gắn với `ranking`.

Công thức tổng quát:

```text
Tìm <top_n> <đối_tượng> có <chỉ_số> cao nhất
Cho biết <đối_tượng> có <chỉ_số> lớn nhất / nhỏ nhất
Xếp hạng <đối_tượng> theo <chỉ_số>
Liệt kê top <top_n> <đối_tượng> theo <chỉ_số>
```

Mẫu câu nên dùng:

```text
Tìm top 5 sản phẩm có doanh thu cao nhất.
Cho biết chi nhánh có lợi nhuận thấp nhất trong năm 2024.
Xếp hạng nhân viên theo doanh thu giảm dần.
Liệt kê 10 khách hàng có tổng giá trị mua lớn nhất.
```

Mẫu câu rút gọn:

```text
Top 5 sản phẩm doanh thu cao nhất
Chi nhánh lợi nhuận thấp nhất
Xếp hạng nhân viên theo doanh thu
Top 10 khách hàng giá trị mua lớn nhất
```

Mục tiêu router:

- `intent`: `ranking`
- Có thể đi kèm `comparison` nếu có nhiều nhóm đối chiếu.

### 3.4 Comparison Query

Dùng khi muốn so sánh hai nhóm, hai giai đoạn, hai đối tượng.

Công thức tổng quát:

```text
So sánh <chỉ_số> giữa <nhóm_1> và <nhóm_2>
So sánh <chỉ_số> theo <nhóm>
Cho biết chênh lệch <chỉ_số> giữa <đối_tượng_1> và <đối_tượng_2>
```

Mẫu câu nên dùng:

```text
So sánh doanh thu giữa miền Bắc và miền Nam.
So sánh lợi nhuận năm 2024 và 2025 theo quý.
Cho biết chênh lệch chi phí giữa hai chi nhánh Hà Nội và Đà Nẵng.
So sánh doanh thu theo từng phòng ban.
```

Mục tiêu router:

- `intent`: `comparison`
- Nếu có thời gian kèm theo, có thể đồng thời là `trend`.

### 3.5 Top Trend Query

Loại này kết hợp `ranking + trend`, rất hay gặp trong phân tích thực tế.

Công thức tổng quát:

```text
Vẽ xu hướng <chỉ_số> của top <top_n> <đối_tượng>
Cho biết top <top_n> <đối_tượng> có xu hướng <chỉ_số> theo <thời_gian>
Vẽ biểu đồ đường <chỉ_số> theo <thời_gian> cho top <top_n> <đối_tượng>
```

Mẫu câu nên dùng:

```text
Vẽ xu hướng doanh thu theo tháng của top 5 sản phẩm bán chạy nhất.
Cho biết top 3 chi nhánh có doanh thu cao nhất và xu hướng lợi nhuận theo quý.
Vẽ biểu đồ đường doanh thu theo năm cho top 10 khách hàng.
```

Mục tiêu router:

- `intent`: thường cùng lúc là `ranking` và `trend`
- `graph_type`: thường là `line_plot` hoặc `bar_plot`

### 3.6 Mix Query

Loại truy vấn kết hợp nhiều tác vụ trong một câu: lọc + tính toán + xếp hạng + vẽ biểu đồ.

Công thức tổng quát:

```text
<hành_động_1> <chỉ_số> theo <nhóm>, sau đó <hành_động_2>
Lọc <điều_kiện>, tính <chỉ_số>, rồi vẽ <loại_biểu_đồ>
Tìm top <top_n> <đối_tượng>, sau đó vẽ xu hướng theo <thời_gian>
```

Mẫu câu nên dùng:

```text
Lọc dữ liệu năm 2024, tính tổng doanh thu theo tháng và vẽ biểu đồ cột.
Tìm top 5 sản phẩm có doanh thu cao nhất, sau đó vẽ xu hướng lợi nhuận theo quý.
Chỉ lấy khu vực miền Bắc, đếm số lượng đơn hàng theo chi nhánh và hiển thị bảng.
So sánh doanh thu giữa hai miền, sau đó vẽ biểu đồ cột giảm dần.
```

Khuyến nghị:

- Truy vấn mix nên viết theo thứ tự thao tác.
- Nên tách rõ “lọc”, “tính”, “vẽ”, “xếp hạng”.
- Nếu quá dài, có thể chia thành 2 query liên tiếp.

## 4. Mẫu follow-up query bằng tiếng Việt

Hệ thống có hỗ trợ follow-up. Đây là nhóm câu chỉnh sửa kết quả vừa tạo, không phải truy vấn mới.

Mẫu câu:

```text
Đổi màu biểu đồ thành đỏ.
Sắp xếp lại giảm dần.
Thêm nhãn giá trị trên mỗi cột.
Vẽ lại theo tháng thay vì theo quý.
Chuyển biểu đồ này thành biểu đồ đường.
Bỏ chi nhánh Đà Nẵng ra khỏi kết quả.
```

Router kỳ vọng:

- `is_follow_up = True`
- Sử dụng lịch sử hội thoại gần nhất để sửa kết quả trước.

## 5. Từ khóa tiếng Việt hệ thống hiểu tốt

### 5.1 Từ khóa hành động

- `tính`, `đếm`, `tổng`, `trung bình`, `so sánh`, `xếp hạng`, `tìm top`, `vẽ`, `hiển thị`, `tạo`

### 5.2 Từ khóa xếp hạng

- `top`, `cao nhất`, `thấp nhất`, `lớn nhất`, `nhỏ nhất`, `xếp hạng`, `hạng đầu`, `cuối bảng`

### 5.3 Từ khóa xu hướng

- `xu hướng`, `biến động`, `tăng trưởng`, `theo tháng`, `theo quý`, `theo năm`, `qua thời gian`

### 5.4 Từ khóa biểu đồ

- `biểu đồ cột`, `biểu đồ đường`, `biểu đồ tròn`, `heatmap`, `scatter`, `histogram`, `biểu đồ miền`, `radar`

### 5.5 Viết tắt thông dụng mà hệ thống mở rộng

- `dt -> doanh thu`
- `ln -> lợi nhuận`
- `cp -> chi phí`
- `sl -> số lượng`
- `bd -> biểu đồ`
- `kh -> khách hàng`
- `sp -> sản phẩm`
- `nv -> nhân viên`
- `cn -> chi nhánh`

## 6. Mẫu truy vấn ưu tiên cho demo

Những câu sau nên dùng để hệ thống chạy ổn định và dễ giải thích:

```text
Tính tổng doanh thu theo tháng.
Vẽ biểu đồ cột doanh thu theo chi nhánh.
Tìm top 5 sản phẩm có doanh thu cao nhất.
So sánh lợi nhuận giữa năm 2024 và 2025.
Vẽ xu hướng doanh thu theo quý.
Lọc năm 2024 và vẽ biểu đồ đường lợi nhuận theo tháng.
```

## 7. Những cách đặt câu nên tránh

Những mẫu sau dễ gây mơ hồ:

```text
Xem cái này đi
Làm cho tôi một biểu đồ đẹp
Tính giúp tôi toàn bộ
Phân tích hết dữ liệu này
Vẽ cái giống hôm qua nhưng khác tí
```

Lý do:

- Thiếu `chỉ_số`
- Thiếu `nhóm`
- Không có `thời gian` hoặc `điều kiện`
- Không rõ là muốn bảng, biểu đồ hay ranking

Nên đổi thành:

```text
Vẽ biểu đồ cột doanh thu theo tháng.
Phân tích tổng quan dữ liệu và hiển thị bảng thống kê.
Vẽ lại biểu đồ trước đó nhưng đổi màu thành xanh lá.
```

## 8. Mẫu template tổng hợp cho UI hoặc hướng dẫn người dùng

Có thể hiển thị cho người dùng mẫu sau:

```text
1. Tính toán:
   Tính <chỉ_số> theo <nhóm>

2. Vẽ biểu đồ:
   Vẽ <loại_biểu_đồ> <chỉ_số> theo <nhóm>

3. Xếp hạng:
   Tìm top <top_n> <đối_tượng> theo <chỉ_số>

4. So sánh:
   So sánh <chỉ_số> giữa <đối_tượng_1> và <đối_tượng_2>

5. Xu hướng:
   Vẽ xu hướng <chỉ_số> theo <thời_gian>

6. Kết hợp:
   Lọc <điều_kiện>, tính <chỉ_số>, sau đó vẽ <loại_biểu_đồ>
```

## 9. Kết luận

Hệ thống không cần câu hỏi quá dài; điều quan trọng là dùng từ khóa đúng và đặt câu theo một cấu trúc ổn định. Trong thực tế, truy vấn tiếng Việt hiệu quả nhất thường có 3-5 thành phần:

```text
hành động + chỉ số + nhóm + thời gian + kiểu đầu ra
```

Ví dụ:

```text
Vẽ biểu đồ cột doanh thu theo tháng năm 2024.
Top 5 sản phẩm có lợi nhuận cao nhất theo quý.
Tính trung bình chi phí theo chi nhánh.
```
