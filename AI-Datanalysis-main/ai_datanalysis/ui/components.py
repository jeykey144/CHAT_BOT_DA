"""
UI components for authentication, dataset management, and settings.
"""
from __future__ import annotations

import os
from typing import Dict

import pandas as pd
import streamlit as st

from ai_datanalysis.auth import create_session, delete_session, register_user, verify_user
from ai_datanalysis.llm_factory import GROQ_AVAILABLE_MODELS
from ai_datanalysis.core.data_catalog import build_data_catalog, select_non_overlapping_masters
from ai_datanalysis.services.chat_service import clear_chat_history, create_chat_history
from ai_datanalysis.services.dataset_service import (
    clear_saved_manifest,
    load_saved_manifest,
    load_saved_paths,
    save_uploaded_files,
)


def _complete_login(auth_engine, username: str) -> None:
    token = create_session(auth_engine, username)
    cookie_manager = st.session_state.get("_cookie_manager")
    if cookie_manager is not None and getattr(cookie_manager, "ready", lambda: False)():
        try:
            cookie_manager["session_token"] = token
            cookie_manager.save()
        except Exception:
            pass
    st.query_params["session"] = token
    st.session_state["session_token"] = token
    st.session_state["user"] = username
    st.session_state["messages"] = []
    st.session_state["active_chat_id"] = None
    st.session_state["last_code"] = ""
    st.session_state["last_error"] = ""
    st.session_state["data_catalog"] = {}
    st.session_state["last_selected_datasets"] = []
    st.session_state["loaded_chat_id"] = None
    st.session_state["auth_notice"] = "Đăng nhập thành công."
    st.session_state["_just_logged_in"] = True
    st.session_state.pop("chat_history_selector", None)


def reset_data_upload():
    user = st.session_state.get("user")
    active_chat_id = st.session_state.get("active_chat_id")
    st.session_state["data"] = {}
    st.session_state["dfs_var"] = []
    st.session_state["data_catalog"] = {}
    st.session_state["last_selected_datasets"] = []
    st.session_state["loaded_chat_id"] = active_chat_id
    st.session_state["uploader_nonce"] = st.session_state.get("uploader_nonce", 0) + 1
    if user and active_chat_id:
        clear_saved_manifest(user, chat_id=active_chat_id)
    st.rerun()


def _logout(auth_engine):
    token = st.session_state.get("session_token") or st.query_params.get("session")
    if token:
        try:
            delete_session(auth_engine, token)
        except Exception:
            pass
    cookie_manager = st.session_state.get("_cookie_manager")
    if cookie_manager is not None and getattr(cookie_manager, "ready", lambda: False)():
        try:
            del cookie_manager["session_token"]
            cookie_manager.save()
        except Exception:
            pass
    st.query_params.pop("session", None)
    st.session_state["session_token"] = None
    st.session_state["user"] = None
    st.session_state["messages"] = []
    st.session_state["active_chat_id"] = None
    st.session_state["data"] = {}
    st.session_state["dfs_var"] = []
    st.session_state["data_catalog"] = {}
    st.session_state["last_code"] = ""
    st.session_state["last_error"] = ""
    st.session_state["last_selected_datasets"] = []
    st.session_state["loaded_chat_id"] = None
    st.session_state["uploader_nonce"] = st.session_state.get("uploader_nonce", 0) + 1
    st.session_state.pop("chat_history_selector", None)
    st.session_state.pop("model_selector", None)
    st.session_state.pop("main_model_selector", None)
    st.rerun()


def auth_sidebar(auth_engine):
    st.sidebar.markdown("## Tài khoản")
    if st.session_state.get("user"):
        st.sidebar.success(f"Đang đăng nhập: **{st.session_state['user']}**")
        if st.sidebar.button("Đăng xuất", key="btn_logout_sidebar"):
            _logout(auth_engine)
        st.sidebar.markdown("---")
        return

    st.sidebar.info("Đăng nhập ở khu vực chính để bắt đầu sử dụng hệ thống.")
    st.sidebar.markdown("---")


def auth_main(auth_engine):
    st.title("AI-Datanalysis")
    st.info("Vui lòng đăng nhập để sử dụng chatbot.")
    tab1, tab2 = st.tabs(["Đăng nhập", "Đăng ký"])
    with tab1:
        with st.form("login_form_main", clear_on_submit=False):
            u = st.text_input("Tên đăng nhập", key="login_user_main")
            p = st.text_input("Mật khẩu", type="password", key="login_pass_main")
            submitted = st.form_submit_button("Đăng nhập")
        if submitted:
            ok = False
            msg = ""
            with st.spinner("Đang đăng nhập..."):
                try:
                    ok, msg = verify_user(auth_engine, u, p)
                except Exception as ex:
                    st.error("Đăng nhập thất bại do lỗi hệ thống.")
                    st.caption(str(ex))
            if ok:
                username = u.strip().lower()
                try:
                    _complete_login(auth_engine, username)
                except Exception as ex:
                    st.error("Đăng nhập thất bại do lỗi tạo phiên.")
                    st.caption(str(ex))
                else:
                    st.rerun()
            elif msg:
                st.error(msg)
    with tab2:
        with st.form("register_form_main", clear_on_submit=False):
            u = st.text_input("Tên đăng nhập (≥3 ký tự)", key="reg_user_main")
            e = st.text_input("Email (tùy chọn)", key="reg_email_main")
            p1 = st.text_input("Mật khẩu (≥6 ký tự)", type="password", key="reg_pass1_main")
            p2 = st.text_input("Nhập lại mật khẩu", type="password", key="reg_pass2_main")
            submitted = st.form_submit_button("Tạo tài khoản")
        if submitted:
            if p1 != p2:
                st.error("Mật khẩu nhập lại không khớp.")
            else:
                ok, msg = register_user(auth_engine, u, p1, email=e or None)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)


def _handle_upload(uploaded):
    if not uploaded:
        return
    success = False
    try:
        user = st.session_state.get("user") or "anonymous"
        active_chat_id = st.session_state.get("active_chat_id")
        if not active_chat_id:
            active_chat_id = create_chat_history(user)
            st.session_state["active_chat_id"] = active_chat_id
            st.session_state["messages"] = []
            st.session_state.pop("chat_history_selector", None)
        save_uploaded_files(user, uploaded, append=True, chat_id=active_chat_id)
        paths = load_saved_manifest(user, chat_id=active_chat_id)
        data = load_saved_paths(paths, user=user)
        st.session_state["data"] = data
        st.session_state["dfs_var"] = list(data.values())
        st.session_state["data_catalog"] = build_data_catalog(data) if data else {}
        st.session_state["loaded_chat_id"] = active_chat_id
        success = True
    except Exception as ex:
        st.error("Không thể nạp dữ liệu.")
        st.caption(str(ex))

    if success:
        st.success("Đã nạp dữ liệu. Bạn có thể tải bổ sung thêm bảng nếu cần.")
        st.rerun()


def _render_single_dataset_preview(
    data: Dict[str, pd.DataFrame],
    *,
    select_key: str,
    height: int,
) -> None:
    if not data:
        st.info("Chưa có dữ liệu để preview.")
        return

    dataset_names = list(data.keys())
    selected_name = st.selectbox(
        "Chọn bảng",
        options=dataset_names,
        key=select_key,
        label_visibility="collapsed",
    )
    df = data[selected_name]
    st.caption(f"{selected_name} | shape={df.shape}")
    st.dataframe(df, use_container_width=True, height=height)


def dataset_sidebar():
    st.sidebar.markdown("## Dữ liệu")
    if not st.session_state.get("user"):
        st.sidebar.caption("Đăng nhập để tải và quản lý dữ liệu.")
        st.sidebar.markdown("---")
        return
    st.sidebar.caption("Dữ liệu được gắn với đoạn chat hiện tại. Tạo chat mới cần nạp bộ dữ liệu mới.")

    nonce = st.session_state.get("uploader_nonce", 0)
    c1, c2 = st.sidebar.columns(2)
    with c1:
        if st.button("Tải mới", key=f"btn_newdata_sidebar_{nonce}"):
            reset_data_upload()
    with c2:
        if st.button("Xóa", key=f"btn_cleardata_sidebar_{nonce}"):
            reset_data_upload()

    uploaded = st.sidebar.file_uploader(
        "Tải lên CSV/XLSX",
        type=["csv", "xlsx", "xls"],
        accept_multiple_files=True,
        key=f"uploader_sidebar_{nonce}",
    )
    if uploaded:
        _handle_upload(uploaded)

    data: Dict[str, pd.DataFrame] = st.session_state.get("data", {}) or {}
    if not data:
        st.sidebar.info("Chưa có dữ liệu.")
        return

    catalog = st.session_state.get("data_catalog") or build_data_catalog(data)
    st.session_state["data_catalog"] = catalog

    st.sidebar.success(f"Đã nạp: {len(data)} bảng dữ liệu.")
    overview = catalog.get("overview", {})
    if len(data) > 1:
        st.sidebar.caption(
            "Nhóm độc lập: "
            f"{overview.get('independent_group_count', len(data))} | "
            f"Join đề xuất: {overview.get('recommended_join_count', 0)}"
        )

        with st.sidebar.expander("Quan hệ giữa các bảng"):
            recommended = [rel for rel in catalog.get("relationships", []) if rel.get("recommended")]
            if recommended:
                for rel in recommended[:3]:
                    st.write(
                        f"{rel['left_dataset']} <-> {rel['right_dataset']} | "
                        f"{rel['left_key']} = {rel['right_key']} | "
                        f"conf={rel['confidence']:.2f}"
                    )
            else:
                st.caption("Chưa thấy khóa chung đủ tin cậy. Hệ thống sẽ ưu tiên phân tích riêng.")

            masters = select_non_overlapping_masters(catalog)
            if masters:
                st.markdown("**Bảng master đề xuất**")
                for master in masters[:3]:
                    st.write(
                        f"{master['name']} | "
                        f"{master['sources'][0]} + {master['sources'][1]} | "
                        f"conf={master['confidence']:.2f}"
                    )

    with st.sidebar.expander("Xem nhanh dữ liệu"):
        _render_single_dataset_preview(
            data,
            select_key="sidebar_dataset_preview",
            height=220,
        )


def dataset_main():
    if not st.session_state.get("user"):
        st.title("AI-Datanalysis")
        st.info("Vui lòng đăng nhập để tải dữ liệu và bắt đầu chat.")
        return

    st.title("AI-Datanalysis")
    st.info("Hãy tải lên dữ liệu CSV/XLSX cho đoạn chat hiện tại để bắt đầu phân tích.")
    nonce = st.session_state.get("uploader_nonce", 0)
    if st.button("Tải dữ liệu mới", key=f"btn_newdata_main_{nonce}"):
        reset_data_upload()

    uploaded_main = st.file_uploader(
        "Tải lên CSV/XLSX",
        type=["csv", "xlsx", "xls"],
        accept_multiple_files=True,
        key=f"uploader_main_{nonce}",
    )
    if uploaded_main:
        _handle_upload(uploaded_main)
    st.caption("Bạn cũng có thể tải dữ liệu ở thanh bên. Dữ liệu chỉ áp dụng cho đoạn chat đang mở.")


def data_system_preview_main() -> None:
    data: Dict[str, pd.DataFrame] = st.session_state.get("data", {}) or {}
    if not data:
        return

    with st.expander("Xem trước dữ liệu", expanded=False):
        for name, df in data.items():
            with st.expander(name, expanded=False):
                st.dataframe(df, use_container_width=True, height=320)


def settings_sidebar():
    st.sidebar.markdown("## Cài đặt")
    st.session_state["lang_var"] = "vi"
    privacy = st.sidebar.checkbox("Chế độ riêng tư (không gửi sample)", value=True)
    st.session_state["sample_var"] = 0 if privacy else 5
    st.session_state["dashboard_role"] = st.sidebar.selectbox(
        "Vai trò dashboard",
        options=["analyst", "ceo", "cfo", "finance_manager", "business_manager", "sales", "marketing", "operations"],
        index=0,
    )

    provider = os.getenv("LLM_PROVIDER", "groq").strip().lower()
    st.sidebar.markdown(f"### Model ({provider.upper()})")
    if provider != "groq":
        st.sidebar.error("Only LLM_PROVIDER=groq is supported in this build.")
        return
    if provider == "groq":
        _MODEL_LABELS = {
            "llama-3.3-70b-versatile": "Llama 3.3 70B — Chính xác",
            "qwen/qwen3-32b":          "Qwen3 32B — Đa năng",
        }
        default_model = os.getenv("GROQ_MODEL", GROQ_AVAILABLE_MODELS[0]).strip()
        current = st.session_state.get("selected_model", default_model)
        if current not in GROQ_AVAILABLE_MODELS:
            current = GROQ_AVAILABLE_MODELS[0]
        selected = st.sidebar.selectbox(
            "Chọn model",
            options=GROQ_AVAILABLE_MODELS,
            index=GROQ_AVAILABLE_MODELS.index(current),
            format_func=lambda m: _MODEL_LABELS.get(m, m),
            key="model_selector",
        )
        if selected != st.session_state.get("selected_model"):
            st.session_state["selected_model"] = selected
            st.session_state.pop("main_model_selector", None)


def main_action_bar(auth_engine):
    st.markdown("### Điều khiển nhanh")
    c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
    with c1:
        if st.button("Đăng xuất", key="btn_logout_main"):
            _logout(auth_engine)
    with c2:
        if st.button("Tải dữ liệu mới", key="btn_upload_new_main"):
            reset_data_upload()
    with c3:
        if st.button("Xóa dữ liệu", key="btn_clear_data_main"):
            reset_data_upload()
    with c4:
        if st.button("Khám phá dữ liệu", key="btn_auto_profile_main"):
            st.session_state["trigger_auto_profile"] = True
            st.rerun()
    with c5:
        if st.button("Xóa chat", key="btn_clear_chat_main"):
            st.session_state["messages"] = []
            st.session_state["last_code"] = ""
            st.session_state["last_error"] = ""
            active_chat_id = st.session_state.get("active_chat_id")
            if active_chat_id:
                clear_saved_manifest(st.session_state.get("user"), chat_id=active_chat_id)
                clear_chat_history(st.session_state.get("user"), active_chat_id)
                st.session_state["active_chat_id"] = None
            st.session_state["data"] = {}
            st.session_state["dfs_var"] = []
            st.session_state["data_catalog"] = {}
            st.session_state["last_selected_datasets"] = []
            st.session_state["loaded_chat_id"] = None
            st.session_state["uploader_nonce"] = st.session_state.get("uploader_nonce", 0) + 1
            st.session_state.pop("chat_history_selector", None)
            st.rerun()
    with c6:
        if st.button("Đoạn chat mới", key="btn_new_chat_main"):
            st.session_state["messages"] = []
            st.session_state["last_code"] = ""
            st.session_state["last_error"] = ""
            st.session_state["active_chat_id"] = create_chat_history(st.session_state.get("user"))
            st.session_state["data"] = {}
            st.session_state["dfs_var"] = []
            st.session_state["data_catalog"] = {}
            st.session_state["last_selected_datasets"] = []
            st.session_state["loaded_chat_id"] = st.session_state["active_chat_id"]
            st.session_state["uploader_nonce"] = st.session_state.get("uploader_nonce", 0) + 1
            st.session_state.pop("chat_history_selector", None)
            st.rerun()
    with c7:
        if st.button("Tạo dashboard", key="btn_auto_dashboard_main"):
            st.session_state["trigger_auto_dashboard"] = True
            st.rerun()
