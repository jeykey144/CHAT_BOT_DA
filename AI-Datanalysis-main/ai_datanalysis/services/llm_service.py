"""
LLM service — public API cho toàn bộ pipeline phân tích dựa trên LLM.

Cung cấp interface sạch bao bọc:
    llm_factory.py           → khởi tạo LLM provider
    core/agent.py            → pipeline phân tích 5 bước
    services/dashboard_service.py → dashboard không cần LLM

Quy tắc:
  - app.py chỉ gọi các hàm trong module này, KHÔNG import trực tiếp llm_factory
    hay DataAnalysisAgent.
  - Mọi thay đổi provider/agent đều được cô lập tại đây.
"""
from __future__ import annotations

from typing import Any, Dict

import pandas as pd

from ai_datanalysis.core.agent import AgentConfig, DataAnalysisAgent
from ai_datanalysis.core.executors import build_executor as _build_executor
from ai_datanalysis.llm_factory import build_llm as _build_llm
from ai_datanalysis.services.dashboard_service import build_dashboard_report

__all__ = [
    "build_llm",
    "build_executor",
    "build_agent",
    "run_analysis",
    "run_dashboard",
]


def build_llm(model_override: str | None = None) -> Any:
    """
    Khởi tạo LLM instance theo cấu hình môi trường hiện tại.

    Provider được đọc từ env var ``LLM_PROVIDER`` (groq only).
    API key tương ứng phải có trong môi trường.

    Parameters
    ----------
    model_override : str | None
        Ghi đè tên model (chỉ áp dụng với Groq). None = dùng giá trị env var.

    Returns
    -------
    LangChain chat model instance (ChatGroq).

    Raises
    ------
    RuntimeError
        Nếu thiếu API key hoặc provider không hợp lệ.
    """
    return _build_llm(model_override=model_override)


def build_executor() -> Any:
    """
    Khởi tạo executor thực thi code an toàn.

    Backend được đọc từ env var ``EXECUTOR_BACKEND`` (local / e2b).
    Mặc định: ``local`` (LocalRestrictedExecutor với AST validation).

    Returns
    -------
    LocalRestrictedExecutor hoặc E2BExecutor.
    """
    return _build_executor()


def build_agent(
    llm: Any,
    executor: Any,
    max_attempts: int = 3,
) -> DataAnalysisAgent:
    """
    Tạo DataAnalysisAgent từ LLM và executor đã khởi tạo.

    Parameters
    ----------
    llm :
        LangChain chat model (từ build_llm).
    executor :
        Code executor (từ build_executor).
    max_attempts : int
        Số lần retry tối đa khi code thất bại (mặc định 3).

    Returns
    -------
    DataAnalysisAgent
    """
    return DataAnalysisAgent(
        llm=llm,
        executor=executor,
        config=AgentConfig(max_attempts=max_attempts),
    )


def run_analysis(
    agent: DataAnalysisAgent,
    query: str,
    data: Dict[str, pd.DataFrame],
    history: list | None = None,
    language: str = "vi",
    privacy: bool = True,
    sample: int = 0,
    scope: str = "anonymous",
) -> Any:
    """
    Chạy toàn bộ pipeline phân tích LLM (5 bước).

    Parameters
    ----------
    agent : DataAnalysisAgent
        Agent đã được khởi tạo với LLM và executor.
    query : str
        Câu hỏi của người dùng.
    data : Dict[str, pd.DataFrame]
        Các bảng dữ liệu đang có, key là tên bảng.
    history : list | None
        Lịch sử chat (tối đa 6 tin gần nhất). Mỗi phần tử:
        ``{"role": "user"|"assistant", "content": str}``.
    language : str
        Ngôn ngữ prompt — ``"vi"`` (mặc định) hoặc ``"en"``.
    privacy : bool
        True = không gửi dữ liệu mẫu lên LLM (mặc định an toàn).
    sample : int
        Số hàng mẫu gửi kèm khi privacy=False.
    scope : str
        User scope cho cache key (thường là username).

    Returns
    -------
    ExecOutcome
        ``.ok``     → bool: thành công hay không
        ``.result`` → DataFrame | go.Figure | str | None: kết quả
        ``.error``  → str | None: thông báo lỗi nếu thất bại
    """
    return agent.run_pipeline(
        query=query,
        data=data,
        history=history or [],
        language=language,
        privacy=privacy,
        sample=sample,
        scope=scope,
    )


def run_dashboard(
    data: Dict[str, pd.DataFrame],
    role: str = "analyst",
    goal: str = "",
) -> dict:
    """
    Sinh dashboard phân tích tự động (không dùng LLM).

    Parameters
    ----------
    data : Dict[str, pd.DataFrame]
        Dữ liệu để phân tích dashboard.
    role : str
        Vai trò người dùng ảnh hưởng đến KPI được chọn.
        Hợp lệ: ``analyst``, ``ceo``, ``cfo``, ``finance_manager``,
        ``sales``, ``marketing``, ``operations``.
    goal : str
        Câu hỏi / mục tiêu từ người dùng (dùng để tinh chỉnh output).

    Returns
    -------
    dict
        ``{"__type__": "dashboard_report", "sections": [...], ...}``
    """
    return build_dashboard_report(data=data, role=role, goal=goal)
