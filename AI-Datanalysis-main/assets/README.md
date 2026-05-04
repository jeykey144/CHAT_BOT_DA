# assets/ — Tài nguyên Giao diện

Chứa tài nguyên tĩnh phục vụ giao diện ứng dụng. Hiện tại gồm CSS tùy chỉnh cho Streamlit.

---

## Cấu trúc

```
assets/
├── README.md
└── styles/
    └── style.css     ← CSS tùy chỉnh toàn bộ giao diện
```

---

## styles/style.css — Dark Theme

### Mục đích

Inject CSS vào Streamlit để tạo giao diện dark theme theo phong cách ChatGPT, thay thế giao diện mặc định của Streamlit.

### Cách inject

```python
# ai_datanalysis/styles.py
from ai_datanalysis.styles import process_styles
process_styles()  # gọi một lần ở đầu main()
```

`process_styles()` đọc `assets/styles/style.css` và inject qua `st.markdown(..., unsafe_allow_html=True)`.

---

### Thiết kế màu sắc

```css
:root {
  --bg0:    #071019;                    /* nền tối nhất */
  --bg1:    #0b1220;                    /* nền chính */
  --panel:  rgba(255,255,255,0.04);    /* panel phụ */
  --panel2: rgba(255,255,255,0.06);    /* panel hover */
  --border: rgba(255,255,255,0.10);    /* đường viền */
  --text:   rgba(255,255,255,0.92);    /* text chính */
  --muted:  rgba(255,255,255,0.66);    /* text phụ */
  --accent: #7c3aed;                   /* violet — màu nhấn */
}
```

---

### Các khu vực được tùy chỉnh

| Selector | Khu vực | Tùy chỉnh |
|----------|---------|-----------|
| `[data-testid="stAppViewContainer"]` | Toàn bộ app | Gradient background (violet + blue) |
| `[data-testid="stSidebar"]` | Sidebar | Dark background, border phải |
| `section.main > div.block-container` | Khu vực chính | `max-width: 980px`, padding |
| `.app-title` | Block tiêu đề | Font size, weight |
| `.stChatMessage` | Bubble chat | Background theo role (user/assistant) |
| `.stChatInputContainer` | Input chat | Fixed bottom, blur backdrop |
| `.stButton > button` | Tất cả nút | Pill shape, violet gradient |
| `.stMetric` | KPI metrics | Card style với border |
| `.stDataFrame` | Bảng dữ liệu | Dark table header |
| `.stExpander` | Expander sections | Border + panel background |

---

### Thay đổi màu accent

Để đổi màu nhấn từ violet sang màu khác, chỉnh `--accent` trong `:root`:

```css
/* Đổi sang xanh lam */
--accent: #2563eb;

/* Đổi sang xanh lá */
--accent: #16a34a;

/* Đổi sang đỏ cam */
--accent: #ea580c;
```

Tất cả nút, border focus, và highlight sẽ tự động cập nhật theo biến CSS này.

---

### Responsive layout

```css
/* Khu vực chat input cố định ở đáy màn hình */
.stChatInputContainer {
  position: fixed;
  bottom: 0;
  /* padding-bottom để tránh bị che bởi taskbar */
}

/* Padding dưới main container để không bị input che */
section.main > div.block-container {
  padding-bottom: 6rem;
}
```

---

### Thêm tùy chỉnh mới

1. Mở `assets/styles/style.css`
2. Thêm selector và rules vào cuối file
3. Dùng DevTools trình duyệt (F12) để tìm selector Streamlit chính xác
4. Test bằng cách restart app (`poetry run streamlit run app.py`)

**Lưu ý:** Streamlit cập nhật data-testid attribute theo version. Nếu CSS ngừng hoạt động sau upgrade Streamlit, kiểm tra lại selector.
