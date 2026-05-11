"""Main entry point for AI-Datanalysis."""
from __future__ import annotations

import os
import time
from typing import Dict

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine

try:
    from dotenv import load_dotenv

    # Load local .env defaults without overriding environment variables injected
    # by the deployment platform.
    load_dotenv(override=False)
except Exception:
    pass

from ai_datanalysis.auth import get_session_username, init_auth_db
from ai_datanalysis.config import inspect_auth_db_url, validate_auth_db_url
from ai_datanalysis.secure_cookie_manager import EncryptedCookieManager
from ai_datanalysis.services.chat_service import (
    create_chat_history,
    list_chat_histories,
    load_chat_history,
    save_chat_history,
    set_active_chat_history,
)
from ai_datanalysis.services.data_service import build_catalog, load_user_data
from ai_datanalysis.services.llm_service import (
    build_agent,
    build_executor,
    build_llm,
    run_analysis,
    run_dashboard,
)
from ai_datanalysis.services.ops_service import (
    DEFAULT_QUERY_LIMIT,
    DEFAULT_QUERY_WINDOW_S,
    audit_query,
    configure_logging,
    consume_rate_limit,
    init_ops_db,
    record_metric,
    run_maintenance,
)
from ai_datanalysis.services.retrieval_service import normalize_query
from ai_datanalysis.styles import process_styles
from ai_datanalysis.ui.components import (
    auth_main,
    auth_sidebar,
    data_system_preview_main,
    dataset_main,
    dataset_sidebar,
    main_action_bar,
)
from ai_datanalysis.ui.render import render_result

_MODEL_AGENT_ATTEMPTS = {
    "llama-3.3-70b-versatile": 2,
    "qwen/qwen3-32b": 1,
}


@st.cache_resource
def get_auth_engine():
    """Cached once per app instance — connection pool is shared across all users/reruns."""
    auth_db_url = os.getenv("AUTH_DB_URL", "").strip()
    app_env = os.getenv("APP_ENV", "development").strip().lower()
    validate_auth_db_url(auth_db_url, app_env)
    connect_timeout_s = int(os.getenv("DB_CONNECT_TIMEOUT_S", "10"))
    pool_timeout_s = int(os.getenv("DB_POOL_TIMEOUT_S", "10"))
    return create_engine(
        auth_db_url,
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_timeout=pool_timeout_s,
        connect_args={"connect_timeout": connect_timeout_s},
        future=True,
    )


@st.cache_resource
def _get_llm(model_name: str = ""):
    """Build LLM once per unique model name — cached per model, safe to share across users."""
    return build_llm(model_override=model_name or None)


@st.cache_resource
def _get_executor():
    """Build executor once per app instance."""
    return build_executor()


@st.cache_resource
def _init_databases():
    """Run DDL exactly once per app instance, not on every rerun."""
    engine = get_auth_engine()
    init_auth_db(engine)
    init_ops_db(engine)
    run_maintenance(engine)
    return True


def _get_cookie_manager() -> EncryptedCookieManager | None:
    secret = (os.getenv("COOKIE_SECRET", "") or "").strip()
    app_env = (os.getenv("APP_ENV", "development") or "development").strip().lower()
    if not secret:
        if app_env == "production":
            raise RuntimeError(
                "COOKIE_SECRET must be set as an environment variable in production. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        secret = "local-dev-cookie-secret"
    try:
        manager = EncryptedCookieManager(password=secret, prefix="ai_datanalysis_")
    except Exception:
        return None
    return manager


def _sync_user_session(auth_engine, cookie_manager: EncryptedCookieManager | None) -> None:
    if st.session_state.get("user"):
        return

    token = None
    if cookie_manager is not None and cookie_manager.ready():
        try:
            token = cookie_manager.get("session_token")
        except Exception:
            token = None

    if not token:
        token = st.query_params.get("session")
    if not token:
        return

    username = get_session_username(auth_engine, token)
    if username:
        st.session_state["session_token"] = token
        st.session_state["user"] = username
        if cookie_manager is not None and cookie_manager.ready():
            try:
                if cookie_manager.get("session_token") != token:
                    cookie_manager["session_token"] = token
                    cookie_manager.save()
            except Exception:
                pass
        st.query_params["session"] = token
        return

    if cookie_manager is not None and cookie_manager.ready():
        try:
            del cookie_manager["session_token"]
            cookie_manager.save()
        except Exception:
            pass
    st.query_params.pop("session", None)
    st.session_state["session_token"] = None


def _initialize_chat_state(user: str) -> None:
    st.session_state.setdefault("active_chat_id", None)
    histories = list_chat_histories(user)
    active_chat_id = st.session_state.get("active_chat_id")

    if active_chat_id and any(item["id"] == active_chat_id for item in histories):
        st.session_state["messages"] = load_chat_history(user, active_chat_id)
        return

    if histories:
        active_chat_id = histories[0]["id"]
        st.session_state["active_chat_id"] = active_chat_id
        set_active_chat_history(user, active_chat_id)
        st.session_state["messages"] = load_chat_history(user, active_chat_id)
        return

    st.session_state["active_chat_id"] = None
    st.session_state["messages"] = []


def _load_chat_dataset_state(user: str, chat_id: str | None) -> None:
    if not user or not chat_id:
        st.session_state["data"] = {}
        st.session_state["dfs_var"] = []
        st.session_state["data_catalog"] = {}
        st.session_state["loaded_chat_id"] = chat_id
        return

    try:
        data_loaded = load_user_data(user, chat_id=chat_id)
    except Exception:
        data_loaded = {}

    st.session_state["data"] = data_loaded
    st.session_state["dfs_var"] = list(data_loaded.values())
    st.session_state["data_catalog"] = build_catalog(data_loaded) if data_loaded else {}
    st.session_state["loaded_chat_id"] = chat_id


def _ensure_active_chat_dataset_loaded(user: str) -> None:
    active_chat_id = st.session_state.get("active_chat_id")
    if st.session_state.get("loaded_chat_id") != active_chat_id:
        _load_chat_dataset_state(user, active_chat_id)


def _render_chat_history_sidebar(user: str) -> None:
    st.sidebar.markdown("## Lịch sử chat")
    histories = list_chat_histories(user)
    if not histories:
        st.sidebar.caption("Chưa có đoạn chat nào.")
        return

    labels = {item["id"]: f"{item['title']} ({item['message_count']} tin)" for item in histories}
    active_chat_id = st.session_state.get("active_chat_id")
    if active_chat_id not in labels:
        active_chat_id = histories[0]["id"]

    selected_chat_id = st.sidebar.radio(
        "Chọn đoạn chat",
        options=[item["id"] for item in histories],
        index=[item["id"] for item in histories].index(active_chat_id),
        format_func=lambda item_id: labels[item_id],
        key="chat_history_selector",
        label_visibility="collapsed",
    )
    if selected_chat_id != st.session_state.get("active_chat_id"):
        st.session_state["active_chat_id"] = selected_chat_id
        st.session_state["messages"] = load_chat_history(user, selected_chat_id)
        st.session_state["last_code"] = ""
        st.session_state["last_error"] = ""
        st.session_state["last_selected_datasets"] = []
        set_active_chat_history(user, selected_chat_id)
        _load_chat_dataset_state(user, selected_chat_id)
        st.rerun()


def _render_sidebar_monitor() -> None:
    messages = st.session_state.get("messages", []) or []
    last_code = st.session_state.get("last_code", "") or ""
    last_error = st.session_state.get("last_error", "") or ""
    active_chat_id = st.session_state.get("active_chat_id") or ""
    data = st.session_state.get("data", {}) or {}
    provider = os.getenv("LLM_PROVIDER", "groq").strip().lower()
    selected_model = st.session_state.get("selected_model", "") or "(chưa chọn)"
    last_selected = st.session_state.get("last_selected_datasets", []) or []

    st.sidebar.markdown("## Monitor")
    info_col, status_col, data_col = st.sidebar.columns(3)
    with info_col:
        st.metric("Tin nhắn", len(messages))
    with status_col:
        st.metric("Trạng thái", "Error" if last_error else "OK")
    with data_col:
        st.metric("Bảng", len(data))

    if active_chat_id:
        st.sidebar.caption(f"Active chat: {active_chat_id[:8]}")
    else:
        st.sidebar.caption("Chưa có đoạn chat đang chọn.")
    st.sidebar.caption(f"Model: {provider.upper()} | {selected_model}")
    if last_selected:
        st.sidebar.caption("Dùng gần nhất: " + ", ".join(last_selected))

    with st.sidebar.expander("Lỗi gần nhất", expanded=bool(last_error)):
        if last_error:
            st.code(last_error, language="text")
        else:
            st.caption("Không có lỗi nào được ghi nhận.")

    with st.sidebar.expander("Code gần nhất", expanded=False):
        if last_code:
            st.code(last_code, language="python")
        else:
            st.caption("Chưa có code được sinh.")


def _render_sidebar_toggle_bridge() -> None:
    # Rely on Streamlit's native sidebar controls. The previous DOM observer
    # implementation could trigger runaway browser work on reruns and freeze
    # the page before forms or chat interactions became usable.
    return


def _render_startup_error(title: str, detail: str, ex: Exception, hints: list[str]) -> None:
    st.error(title)
    st.caption(detail)
    for hint in hints:
        st.markdown(f"- {hint}")
    with st.expander("Deployment error detail", expanded=True):
        st.code(str(ex), language="text")


def _render_database_startup_error(ex: Exception) -> None:
    raw = str(ex).lower()
    auth_db_url = os.getenv("AUTH_DB_URL", "").strip()
    hints = [
        "Verify AUTH_DB_URL is set on the deployment platform and points to the existing database name.",
        "For this RDS instance, local checks found the existing database name is `chatbot`, not `chatbot_auth`.",
        "Allow outbound traffic from the deployment platform to the RDS security group on TCP port 3306.",
        "If RDS is outside the deployment network, it must be publicly reachable or connected through a private network/VPC tunnel.",
    ]
    if auth_db_url:
        try:
            info = inspect_auth_db_url(auth_db_url)
            hints.insert(0, f"Current AUTH_DB_URL target: `{info.summary}`.")
            if info.is_local_host:
                hints.insert(1, "The deployment is still using a local MySQL target. Set AUTH_DB_URL to the RDS endpoint, not localhost or 127.0.0.1.")
        except Exception:
            pass
    if "timed out" in raw or "(2003" in raw:
        hints.insert(0, "The app can resolve the RDS host, but the network path to MySQL port 3306 is timing out.")
    elif "local mysql host in production" in raw:
        hints.insert(0, "Production is configured with a local MySQL host. Re-push or replace AUTH_DB_URL on the deployment platform.")
    elif "access denied" in raw or "(1045" in raw:
        hints.insert(0, "The MySQL host is reachable, but the database rejected the username/password or user host permission.")
        hints.insert(1, "Update AUTH_DB_URL on the deployment platform with the correct MySQL username and URL-encoded password.")
        if "@'localhost'" in raw:
            hints.insert(2, "MySQL reports the client as localhost, which usually means the deployed AUTH_DB_URL is still targeting local MySQL instead of RDS.")
    elif "could not parse sqlalchemy url" in raw:
        hints.insert(0, "AUTH_DB_URL is not a valid SQLAlchemy URL. On the deployment platform, set the key to AUTH_DB_URL and the value to only the mysql+pymysql://... URL.")
        hints.insert(1, "Do not include quotes, backticks, spaces, angle brackets, or the literal `AUTH_DB_URL=` prefix inside the value field.")
    elif "unknown database" in raw:
        hints.insert(0, "The MySQL host is reachable, but AUTH_DB_URL uses a database name that does not exist.")

    _render_startup_error(
        "Database is not reachable",
        "The Streamlit service started, but authentication and app storage cannot initialize until MySQL is reachable.",
        ex,
        hints,
    )


def main():
    st.set_page_config(page_title="AI-Datanalysis", layout="wide", initial_sidebar_state="expanded")
    process_styles()
    _render_sidebar_toggle_bridge()
    logger = configure_logging()

    st.session_state.setdefault("user", None)
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("data", {})
    st.session_state.setdefault("dfs_var", [])
    st.session_state.setdefault("last_code", "")
    st.session_state.setdefault("last_error", "")
    st.session_state.setdefault("uploader_nonce", 0)
    st.session_state.setdefault("active_chat_id", None)
    st.session_state.setdefault("session_token", None)
    st.session_state.setdefault("trigger_auto_profile", False)
    st.session_state.setdefault("trigger_auto_dashboard", False)
    st.session_state.setdefault("data_catalog", {})
    st.session_state.setdefault("warmed_models", set())
    st.session_state.setdefault("selected_model", os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip())
    st.session_state.setdefault("last_selected_datasets", [])
    st.session_state.setdefault("loaded_chat_id", None)
    st.session_state.setdefault("lang_var", "vi")
    st.session_state.setdefault("sample_var", 0)
    st.session_state.setdefault("dashboard_role", "analyst")

    try:
        cookie_manager = st.session_state.get("_cookie_manager")
        if cookie_manager is None:
            cookie_manager = _get_cookie_manager()
            st.session_state["_cookie_manager"] = cookie_manager
    except Exception as ex:
        logger.exception("cookie_manager_init_failed")
        _render_startup_error(
            "Session configuration error",
            "The app cannot initialize browser sessions with the current environment variables.",
            ex,
            [
                "Set COOKIE_SECRET on the deployment platform.",
                "Use a long random value, for example 32 random bytes encoded as hex.",
            ],
        )
        return

    # Engine and DB init are cached — run at most once per app instance
    try:
        auth_engine = get_auth_engine()
        _init_databases()
    except Exception as ex:
        logger.exception("database_init_failed")
        _render_database_startup_error(ex)
        return

    _sync_user_session(auth_engine, cookie_manager)

    if st.session_state.get("user"):
        _initialize_chat_state(st.session_state["user"])
        _ensure_active_chat_dataset_loaded(st.session_state["user"])

    st.session_state["data_catalog"] = build_catalog(st.session_state.get("data") or {})

    if not st.session_state.get("user"):
        auth_sidebar(auth_engine)
        auth_main(auth_engine)
        return

    auth_sidebar(auth_engine)
    _render_chat_history_sidebar(st.session_state["user"])
    dataset_sidebar()

    if st.session_state.get("auth_notice"):
        st.success(st.session_state.pop("auth_notice"))

    data: Dict[str, pd.DataFrame] = st.session_state.get("data", {}) or {}
    if not data:
        dataset_main()
        return

    st.markdown(
        """
        <div class="app-title">
          <div class="app-title__name">AI-Datanalysis</div>
          <div class="app-title__desc">Chatbot xử lý dữ liệu | Phân tích thông minh | Nhanh chóng.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    main_action_bar(auth_engine)
    data_system_preview_main()

    # Model selector — hiển thị ngay dưới action bar, luôn nhìn thấy
    provider = os.getenv("LLM_PROVIDER", "groq").strip().lower()
    if provider == "groq":
        from ai_datanalysis.llm_factory import GROQ_AVAILABLE_MODELS
        _MODEL_LABELS = {
            "llama-3.3-70b-versatile": "🎯 Llama 3.3 70B — Chính xác",
            "qwen/qwen3-32b":          "🌐 Qwen3 32B — Đa năng",
        }
        default_model = os.getenv("GROQ_MODEL", GROQ_AVAILABLE_MODELS[0]).strip()
        current_model = st.session_state.get("selected_model", default_model)
        if current_model not in GROQ_AVAILABLE_MODELS:
            current_model = GROQ_AVAILABLE_MODELS[0]
        col_model, col_info = st.columns([2, 3])
        with col_model:
            chosen = st.selectbox(
                "Model đang dùng",
                options=GROQ_AVAILABLE_MODELS,
                index=GROQ_AVAILABLE_MODELS.index(current_model),
                format_func=lambda m: _MODEL_LABELS.get(m, m),
                key="main_model_selector",
                label_visibility="visible",
            )
        with col_info:
            _hints = {
                "llama-3.3-70b-versatile": "Cân bằng tốt giữa tốc độ và độ chính xác, phù hợp hầu hết truy vấn.",
                "qwen/qwen3-32b":          "Đa năng, mạnh về ngôn ngữ và lập trình phức tạp.",
            }
            st.caption("")
            st.caption(_hints.get(chosen, ""))
        if chosen != st.session_state.get("selected_model"):
            st.session_state["selected_model"] = chosen
            st.session_state.pop("model_selector", None)
            st.rerun()

    try:
        selected_model = st.session_state.get("selected_model", "")
        llm = _get_llm(selected_model)
    except Exception as ex:
        st.error("Không thể khởi tạo LLM. Hãy kiểm tra API key và biến môi trường.")
        st.caption(str(ex))
        return

    # Model warmup — gửi request nhỏ lần đầu dùng model để tránh cold start khi query thật.
    # Groq cần load model lớn vào GPU; nếu không warmup, request đầu tiên của user sẽ bị treo.
    _warmed = st.session_state.get("warmed_models", set())
    if selected_model and selected_model not in _warmed:
        _WARMUP_LABELS = {
            "llama-3.3-70b-versatile": "Llama 3.3 70B",
            "qwen/qwen3-32b":          "Qwen3 32B",
        }
        _display = _WARMUP_LABELS.get(selected_model, selected_model)
        with st.spinner(f"Đang khởi động {_display}… lần đầu có thể mất 15–30 giây"):
            try:
                warmup_msg = "/no_think hi" if "qwen" in selected_model.lower() else "hi"
                llm.invoke(warmup_msg)
            except Exception:
                pass
            finally:
                _warmed.add(selected_model)
                st.session_state["warmed_models"] = _warmed
        st.rerun()

    try:
        executor = _get_executor()
    except Exception as ex:
        st.error("Không thể khởi tạo môi trường thực thi an toàn.")
        st.caption(str(ex))
        return

    # Agent is lightweight — wraps the shared LLM/executor, safe to create per-rerun
    agent_max_attempts = 3
    if provider == "groq":
        agent_max_attempts = _MODEL_AGENT_ATTEMPTS.get(selected_model, 2)
    agent = build_agent(llm=llm, executor=executor, max_attempts=agent_max_attempts)

    code_col, error_col = st.columns(2)
    with code_col:
        with st.expander("Code gần nhất"):
            st.code(st.session_state.get("last_code") or "(chưa có)", language="python")
    with error_col:
        with st.expander("Lỗi gần nhất"):
            st.code(st.session_state.get("last_error") or "(không có)", language="text")

    for item in st.session_state.get("messages", []):
        role = item.get("role", "assistant")
        with st.chat_message(role):
            if role == "user":
                st.markdown(item.get("question", ""))
            else:
                if "response" in item:
                    render_result(item["response"])
                elif "error" in item:
                    st.error(item["error"])
                else:
                    st.write(item)

    user_text = st.chat_input("Nhập yêu cầu... Ví dụ: 'Vẽ biểu đồ cột đếm theo variety'.")
    if st.session_state.get("trigger_auto_profile", False):
        user_text = (
            "Thực hiện Auto-Profiling: phân tích tổng quan, thông tin cơ bản, "
            "ngoại lệ, missing, và gợi ý hướng phân tích tiếp theo."
        )
        st.session_state["trigger_auto_profile"] = False
    elif st.session_state.get("trigger_auto_dashboard", False):
        user_text = "Tạo dashboard tự động từ dữ liệu hiện tại."
        st.session_state["trigger_auto_dashboard"] = False

    if not user_text:
        return

    st.session_state["messages"].append({"role": "user", "question": str(user_text)})
    active_chat_id = st.session_state.get("active_chat_id") or create_chat_history(st.session_state["user"])
    st.session_state["active_chat_id"] = save_chat_history(
        st.session_state["user"],
        st.session_state["messages"],
        chat_id=active_chat_id,
    )

    with st.chat_message("user"):
        st.markdown(user_text)

    with st.chat_message("assistant"):
        with st.spinner("Đang phân tích..."):
            started_at = time.perf_counter()
            provider = os.getenv("LLM_PROVIDER", "groq").strip().lower()
            model_name = (
                st.session_state.get("selected_model")
                or os.getenv("GROQ_MODEL")
                or "unknown"
            )
            try:
                if not consume_rate_limit(
                    auth_engine,
                    action_key="chat_query",
                    scope_key=st.session_state.get("user", "anonymous"),
                    limit=DEFAULT_QUERY_LIMIT,
                    window_seconds=DEFAULT_QUERY_WINDOW_S,
                ):
                    raise RuntimeError("Bạn đã gửi quá nhiều truy vấn trong thời gian ngắn. Hãy thử lại sau.")

                history = []
                for msg in st.session_state["messages"][:-1][-6:]:
                    if msg.get("role") == "user":
                        history.append({"role": "user", "content": msg.get("question", "")})
                    elif msg.get("role") == "assistant" and "response" in msg:
                        resp = msg.get("response")
                        if hasattr(resp, "to_json"):
                            desc = f"[Generated {type(resp).__name__}]"
                        else:
                            raw = str(resp)
                            desc = raw[:500] + "..." if len(raw) > 500 else raw
                        history.append({"role": "assistant", "content": desc})

                normalized_user_text = normalize_query(str(user_text))
                if any(token in normalized_user_text for token in ("dashboard", "bao cao", "report")):
                    from ai_datanalysis.services.retrieval_service import select_datasets
                    if len(data) <= 3 or any(
                        token in normalized_user_text for token in ("hien tai", "tat ca", "toan bo", "tu dong", "auto")
                    ):
                        dashboard_data = data
                    else:
                        dashboard_data = select_datasets(normalized_user_text, data, max_datasets=min(3, len(data)))

                    result = run_dashboard(
                        dashboard_data,
                        role=st.session_state.get("dashboard_role", "analyst"),
                        goal=str(user_text),
                    )
                    agent.selected_dataset_names = list(dashboard_data.keys())
                    st.session_state["last_selected_datasets"] = list(dashboard_data.keys())
                    agent.last_code = "# Auto dashboard report generated via llm_service.run_dashboard"
                    agent.last_error = ""
                    st.session_state["last_code"] = agent.last_code
                    st.session_state["last_error"] = ""
                else:
                    outcome = run_analysis(
                        agent=agent,
                        query=str(user_text),
                        data=data,
                        history=history,
                        language=st.session_state.get("lang_var", "vi"),
                        privacy=(st.session_state.get("sample_var", 0) == 0),
                        sample=st.session_state.get("sample_var", 0),
                        scope=st.session_state.get("user", "anonymous"),
                    )

                    st.session_state["last_code"] = agent.last_code
                    st.session_state["last_error"] = agent.last_error
                    st.session_state["last_selected_datasets"] = list(agent.selected_dataset_names)

                    if getattr(outcome, "ok", False) is False:
                        err = getattr(outcome, "error", "") or agent.last_error or "Execution failed"
                        raise RuntimeError(err)

                    result = getattr(outcome, "result", None)

                latency_ms = int((time.perf_counter() - started_at) * 1000)
                audit_query(
                    auth_engine,
                    username=st.session_state.get("user", "anonymous"),
                    raw_query=str(user_text),
                    normalized_query=normalize_query(str(user_text)),
                    success=True,
                    latency_ms=latency_ms,
                    dataset_count=len(agent.selected_dataset_names),
                    selected_datasets=agent.selected_dataset_names,
                    llm_provider=provider,
                    llm_model=model_name,
                )
                record_metric(
                    auth_engine,
                    "query_latency_ms",
                    latency_ms,
                    {"provider": provider, "user": st.session_state.get("user", "anonymous")},
                )
                record_metric(
                    auth_engine,
                    "query_success",
                    1,
                    {"provider": provider, "user": st.session_state.get("user", "anonymous")},
                )
                logger.info(
                    "query_success user=%s provider=%s model=%s latency_ms=%s datasets=%s",
                    st.session_state.get("user", "anonymous"),
                    provider,
                    model_name,
                    latency_ms,
                    ",".join(agent.selected_dataset_names),
                )

            except Exception as ex:
                latency_ms = int((time.perf_counter() - started_at) * 1000)
                # Persist last code/error so the top expanders update on next rerun
                st.session_state["last_code"] = getattr(agent, "last_code", "") or st.session_state.get("last_code", "")
                st.session_state["last_error"] = getattr(agent, "last_error", "") or str(ex)
                st.session_state["last_selected_datasets"] = list(getattr(agent, "selected_dataset_names", []) or [])
                audit_query(
                    auth_engine,
                    username=st.session_state.get("user", "anonymous"),
                    raw_query=str(user_text),
                    normalized_query=normalize_query(str(user_text)),
                    success=False,
                    latency_ms=latency_ms,
                    dataset_count=len(agent.selected_dataset_names),
                    selected_datasets=agent.selected_dataset_names,
                    llm_provider=provider,
                    llm_model=model_name,
                    error_text=str(ex),
                )
                record_metric(
                    auth_engine,
                    "query_failure",
                    1,
                    {"provider": provider, "user": st.session_state.get("user", "anonymous")},
                )
                logger.exception(
                    "query_failure user=%s provider=%s model=%s latency_ms=%s",
                    st.session_state.get("user", "anonymous"),
                    provider,
                    model_name,
                    latency_ms,
                )
                st.error("Gặp lỗi khi xử lý yêu cầu.")
                st.caption(str(ex))
                if getattr(agent, "last_error", "") or getattr(agent, "last_code", ""):
                    with st.expander("Debug gần nhất"):
                        st.markdown("**Lỗi cuối**")
                        st.code(agent.last_error, language="text")
                        st.markdown("**Code cuối**")
                        st.code(agent.last_code, language="python")

                st.session_state["messages"].append({"role": "assistant", "error": f"Loi: {ex}"})
                st.session_state["active_chat_id"] = save_chat_history(
                    st.session_state["user"],
                    st.session_state["messages"],
                    chat_id=st.session_state.get("active_chat_id"),
                )
                st.stop()

            render_result(result)
            st.session_state["messages"].append({"role": "assistant", "response": result})
            st.session_state["active_chat_id"] = save_chat_history(
                st.session_state["user"],
                st.session_state["messages"],
                chat_id=st.session_state.get("active_chat_id"),
            )


if __name__ == "__main__":
    main()
