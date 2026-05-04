"""
Data service — public API cho quản lý và nạp dữ liệu.

Cung cấp interface sạch bao bọc:
    services/dataset_service.py  → upload, lưu, nạp file CSV/XLSX
    core/data_catalog.py         → phân tích quan hệ giữa các bảng

Quy tắc:
  - Tất cả thao tác với dữ liệu file đi qua module này.
  - dataset_service.py vẫn được giữ nguyên cho backward compatibility.
  - Module này không phụ thuộc Streamlit ngoài @st.cache_data từ dataset_service.
"""
from __future__ import annotations

from typing import Dict, List

import pandas as pd

from ai_datanalysis.core.data_catalog import build_data_catalog
from ai_datanalysis.services.dataset_service import (
    clear_saved_manifest,
    load_datasets,
    load_saved_manifest,
    load_saved_paths,
    save_uploaded_files,
)

__all__ = [
    "load_files",
    "save_user_files",
    "load_user_manifest",
    "load_user_data",
    "clear_user_data",
    "build_catalog",
    "load_datasets",
]


def load_files(uploaded_files) -> Dict[str, pd.DataFrame]:
    """
    Nạp danh sách file upload (từ Streamlit file_uploader) thành dict DataFrame.

    Parameters
    ----------
    uploaded_files :
        Danh sách UploadedFile từ ``st.file_uploader``.

    Returns
    -------
    Dict[str, pd.DataFrame]
        Key: ``"DF_N___filename.csv"`` hoặc ``"DF_N___file.xlsx::sheet_0::Sheet1"``
        Value: DataFrame đã parse.

    Raises
    ------
    ValueError
        Nếu vượt quá giới hạn số file, kích thước, số rows/columns.
    """
    return load_datasets(uploaded_files)


def save_user_files(
    user: str,
    uploaded_files,
    append: bool = True,
    chat_id: str | None = None,
) -> List[str]:
    """
    Lưu file upload vào thư mục của user và cập nhật manifest.

    Parameters
    ----------
    user : str
        Tên người dùng (dùng để tạo thư mục con).
    uploaded_files :
        Danh sách UploadedFile từ ``st.file_uploader``.
    append : bool
        True (mặc định): cộng thêm vào manifest hiện có.
        False: ghi đè manifest.

    Returns
    -------
    List[str]
        Danh sách đường dẫn tuyệt đối của tất cả file trong manifest sau khi lưu.
    """
    return save_uploaded_files(user, uploaded_files, append=append, chat_id=chat_id)


def load_user_manifest(user: str, chat_id: str | None = None) -> List[str]:
    """
    Đọc danh sách đường dẫn file đã lưu của một user.

    Parameters
    ----------
    user : str
        Tên người dùng.

    Returns
    -------
    List[str]
        Danh sách đường dẫn tuyệt đối. Rỗng nếu chưa có manifest.
    """
    return load_saved_manifest(user, chat_id=chat_id)


def load_user_data(user: str, chat_id: str | None = None) -> Dict[str, pd.DataFrame]:
    """
    Nạp toàn bộ dữ liệu đã lưu của một user từ manifest.

    Kết hợp load_user_manifest + load_saved_paths trong một bước.

    Parameters
    ----------
    user : str
        Tên người dùng.

    Returns
    -------
    Dict[str, pd.DataFrame]
        Các DataFrame đã nạp. Rỗng nếu user chưa có dữ liệu.
    """
    paths = load_saved_manifest(user, chat_id=chat_id)
    if not paths:
        return {}
    return load_saved_paths(paths, user=user)


def clear_user_data(user: str, chat_id: str | None = None) -> None:
    """
    Xóa manifest upload của user (không xóa file vật lý).

    Parameters
    ----------
    user : str
        Tên người dùng.
    """
    clear_saved_manifest(user, chat_id=chat_id)


def build_catalog(data: Dict[str, pd.DataFrame]) -> dict:
    """
    Phân tích quan hệ giữa các bảng và xây dựng data catalog.

    Phát hiện:
      - Cột khóa chính / khóa ngoại
      - Quan hệ join với confidence score
      - Master tables (bảng đã được join sẵn)
      - Vai trò bảng: fact / dimension

    Parameters
    ----------
    data : Dict[str, pd.DataFrame]
        Tập dữ liệu cần phân tích.

    Returns
    -------
    dict
        ::

            {
                "overview": {"dataset_count": 2, "recommended_join_count": 1},
                "relationships": [{"left_dataset": ..., "confidence": 0.9, ...}],
                "master_tables": [...],
                "table_roles": {"sales": "fact", "product": "dimension"},
            }

        Trả về dict rỗng nếu ``data`` rỗng hoặc xảy ra lỗi.
    """
    if not data:
        return {}
    try:
        return build_data_catalog(data)
    except Exception:
        return {}
