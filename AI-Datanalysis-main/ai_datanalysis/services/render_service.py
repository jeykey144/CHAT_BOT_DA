"""
Backward-compatible wrapper — render_service.py

Logic render đã được chuyển về đúng tầng UI tại:
    ai_datanalysis.ui.render

Module này chỉ re-export để không làm vỡ code cũ đang import từ đây.
Ưu tiên import trực tiếp từ ai_datanalysis.ui.render trong code mới.
"""
from ai_datanalysis.ui.render import render_result  # noqa: F401

__all__ = ["render_result"]
