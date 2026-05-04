# data/ — Thư mục dữ liệu

Chứa tất cả dữ liệu liên quan đến ứng dụng: dataset mẫu để demo/benchmark và dữ liệu runtime được sinh ra trong quá trình vận hành (uploads, cache, chat history, logs).

**Quan trọng:** Thư mục `runtime/` được tạo tự động khi app khởi động và không được commit vào git (đã có trong `.gitignore`). Thư mục `samples/` chứa dữ liệu tĩnh và được commit.

---

## Cấu trúc

```
data/
├── README.md              ← tài liệu này
├── samples/               ← dataset mẫu (tĩnh, commit vào git)
│   ├── README.md
│   ├── bike_sharing_benchmark.csv
│   ├── retail_sales_benchmark.csv
│   ├── exam_scores_benchmark.csv
│   ├── disoccupazione.csv
│   ├── monthly.csv
│   ├── geojson_brasil.json
│   └── reproducibility_prompts.txt
│
└── runtime/               ← dữ liệu runtime (động, KHÔNG commit)
    ├── README.md
    ├── uploads/           ← file người dùng upload
    │   └── {username}/
    │       ├── manifest.json
    │       └── {timestamp}_{filename}
    ├── cache/             ← cache code và kết quả
    │   ├── code/
    │   │   └── {sha256}.py
    │   └── results/
    │       └── {sha256}.json
    ├── chat_history/      ← lịch sử chat JSON
    │   └── {username}.json
    └── logs/              ← log ứng dụng
        └── app.log
```

---

## Phân biệt samples vs runtime

| | `samples/` | `runtime/` |
|-|-----------|-----------|
| Mục đích | Demo, benchmark, test | Dữ liệu sinh ra khi chạy |
| Commit git | Có | Không |
| Tạo bởi | Developer | Ứng dụng tự động |
| Xóa được | Không (tham chiếu) | Có (theo retention policy) |

---

## Retention policy (runtime)

Được quản lý bởi `ops_service.run_maintenance()` — chạy một lần khi app khởi động:

| Loại file | Retention | Biến môi trường |
|-----------|-----------|----------------|
| Audit logs (DB) | 30 ngày | `OPS_DB_RETENTION_DAYS` |
| Cache files | 14 ngày | `OPS_FILE_RETENTION_DAYS` |
| Chat history | **Không bao giờ xóa** | — |
| Upload files | Không bị xóa tự động | — |
