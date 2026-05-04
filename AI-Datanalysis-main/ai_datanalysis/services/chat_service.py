"""
Chat history persistence with support for multiple conversations per user.
"""
from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go

from ai_datanalysis.paths import CHAT_HISTORY_DIR

# Per-user in-process locks prevent race conditions when multiple Streamlit
# tabs for the same user read-modify-write the chat history file simultaneously.
_user_file_locks: dict[str, threading.Lock] = {}
_user_file_locks_meta = threading.Lock()


def _get_user_lock(user: str) -> threading.Lock:
    with _user_file_locks_meta:
        if user not in _user_file_locks:
            _user_file_locks[user] = threading.Lock()
        return _user_file_locks[user]


CHAT_DIR = CHAT_HISTORY_DIR


def _chat_history_path(user: str) -> Path:
    user = (user or "anonymous").strip().lower()
    CHAT_DIR.mkdir(parents=True, exist_ok=True)
    return CHAT_DIR / f"{user}.json"


def _serialize_dataframe(df: pd.DataFrame) -> dict:
    """Serialize DataFrame tránh ujson overflow bằng cách dùng json chuẩn."""
    try:
        return {
            "__type__": "dataframe",
            "value": df.to_json(orient="split", date_format="iso"),
        }
    except (OverflowError, RecursionError, Exception):
        # Fallback: dùng json chuẩn với default=str để tránh ujson recursion
        safe = df.where(pd.notnull(df), None)
        payload = json.dumps(
            {
                "columns": [str(c) for c in safe.columns],
                "index": list(range(len(safe))),
                "data": [
                    [None if v is None else (float(v) if isinstance(v, float) else str(v)) for v in row]
                    for row in safe.itertuples(index=False, name=None)
                ],
            }
        )
        return {"__type__": "dataframe", "value": payload}


def _serialize_value(value: Any, _depth: int = 0) -> Any:
    # Depth guard — tránh stackoverflow khi object lồng nhau quá sâu
    if _depth > 12:
        return None

    if isinstance(value, pd.DataFrame):
        return _serialize_dataframe(value)

    if isinstance(value, go.Figure):
        try:
            return {"__type__": "plotly_figure", "value": value.to_json()}
        except Exception:
            return None

    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [_serialize_value(item, _depth + 1) for item in value]
    if isinstance(value, tuple):
        return {"__type__": "tuple", "value": [_serialize_value(item, _depth + 1) for item in value]}
    if isinstance(value, dict):
        return {str(k): _serialize_value(v, _depth + 1) for k, v in value.items()}
    return str(value)


def _deserialize_value(value: Any) -> Any:
    if isinstance(value, list):
        return [_deserialize_value(item) for item in value]
    if not isinstance(value, dict):
        return value

    value_type = value.get("__type__")
    if value_type == "dataframe":
        try:
            return pd.read_json(value["value"], orient="split")
        except Exception:
            return pd.DataFrame()
    if value_type == "plotly_figure":
        try:
            return go.Figure(json.loads(value["value"]))
        except Exception:
            return None
    if value_type == "tuple":
        return tuple(_deserialize_value(item) for item in value.get("value", []))
    return {k: _deserialize_value(v) for k, v in value.items()}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None).isoformat() + "Z"


def _conversation_title(messages: list[dict], fallback: str = "Đoạn chat mới") -> str:
    for item in messages:
        if item.get("role") == "user":
            question = str(item.get("question", "")).strip()
            if question:
                return question[:60]
    return fallback


def _new_conversation(messages: list[dict] | None = None, title: str | None = None) -> dict:
    safe_messages = [m for m in (messages or []) if isinstance(m, dict)]
    now = _utc_now()
    return {
        "id": uuid.uuid4().hex,
        "title": (title or _conversation_title(safe_messages)).strip() or "Đoạn chat mới",
        "created_at": now,
        "updated_at": now,
        "messages": [_serialize_value(m) for m in safe_messages],
    }


def _empty_store() -> dict:
    return {"active_chat_id": None, "conversations": []}


def _normalize_store(raw: Any) -> dict:
    if isinstance(raw, list):
        conv = _new_conversation(raw, title=_conversation_title(raw, "Đoạn chat cũ"))
        return {"active_chat_id": conv["id"], "conversations": [conv]}

    if not isinstance(raw, dict):
        return _empty_store()

    conversations = []
    for item in raw.get("conversations", []):
        if not isinstance(item, dict):
            continue
        conv_id = str(item.get("id") or uuid.uuid4().hex)
        messages = [m for m in item.get("messages", []) if isinstance(m, dict)]
        title = str(item.get("title") or _conversation_title(messages)).strip() or "Đoạn chat mới"
        created_at = str(item.get("created_at") or _utc_now())
        updated_at = str(item.get("updated_at") or created_at)
        conversations.append(
            {
                "id": conv_id,
                "title": title,
                "created_at": created_at,
                "updated_at": updated_at,
                "messages": [_serialize_value(m) for m in messages],
            }
        )

    active_chat_id = raw.get("active_chat_id")
    if active_chat_id and not any(c["id"] == active_chat_id for c in conversations):
        active_chat_id = None
    if not active_chat_id and conversations:
        conversations.sort(key=lambda c: c.get("updated_at", ""), reverse=True)
        active_chat_id = conversations[0]["id"]
    return {"active_chat_id": active_chat_id, "conversations": conversations}


def _read_store(user: str) -> dict:
    path = _chat_history_path(user)
    if not path.exists():
        return _empty_store()
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return _normalize_store(raw)
    except Exception:
        return _empty_store()


def _write_store(user: str, store: dict) -> None:
    path = _chat_history_path(user)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False)


def list_chat_histories(user: str) -> list[dict]:
    store = _read_store(user)
    conversations = store.get("conversations", [])
    conversations.sort(key=lambda c: c.get("updated_at", ""), reverse=True)
    return [
        {
            "id": item["id"],
            "title": item.get("title", "Đoạn chat mới"),
            "created_at": item.get("created_at", ""),
            "updated_at": item.get("updated_at", ""),
            "message_count": len(item.get("messages", [])),
        }
        for item in conversations
    ]


def create_chat_history(user: str, title: str = "Đoạn chat mới") -> str:
    lock = _get_user_lock(user)
    with lock:
        store = _read_store(user)
        conv = _new_conversation([], title=title)
        store.setdefault("conversations", []).append(conv)
        store["active_chat_id"] = conv["id"]
        _write_store(user, store)
    return conv["id"]


def load_chat_history(user: str, chat_id: str | None = None) -> list[dict]:
    # Read-only — no write, no lock needed
    store = _read_store(user)
    target_id = chat_id or store.get("active_chat_id")
    for item in store.get("conversations", []):
        if item.get("id") == target_id:
            return [_deserialize_value(msg) for msg in item.get("messages", []) if isinstance(msg, dict)]
    return []


def save_chat_history(user: str, messages: list[dict], chat_id: str | None = None, title: str | None = None) -> str:
    lock = _get_user_lock(user)
    with lock:
        store = _read_store(user)
        conversations = store.setdefault("conversations", [])
        target_id = chat_id or store.get("active_chat_id")
        safe_messages = [m for m in messages if isinstance(m, dict)]
        now = _utc_now()

        for item in conversations:
            if item.get("id") == target_id:
                item["messages"] = [_serialize_value(m) for m in safe_messages]
                item["updated_at"] = now
                item["title"] = (title or _conversation_title(safe_messages, item.get("title", "Đoạn chat mới"))).strip()
                store["active_chat_id"] = item["id"]
                _write_store(user, store)
                return item["id"]

        conv = _new_conversation(safe_messages, title=title)
        conversations.append(conv)
        store["active_chat_id"] = conv["id"]
        _write_store(user, store)
    return conv["id"]


def set_active_chat_history(user: str, chat_id: str) -> None:
    lock = _get_user_lock(user)
    with lock:
        store = _read_store(user)
        if any(item.get("id") == chat_id for item in store.get("conversations", [])):
            store["active_chat_id"] = chat_id
            _write_store(user, store)


def clear_chat_history(user: str, chat_id: str | None = None) -> None:
    lock = _get_user_lock(user)
    try:
        with lock:
            path = _chat_history_path(user)
            if chat_id is None:
                if path.exists():
                    path.unlink()
                legacy_path = path.with_suffix(".pkl")
                if legacy_path.exists():
                    legacy_path.unlink()
                return

            store = _read_store(user)
            conversations = [c for c in store.get("conversations", []) if c.get("id") != chat_id]
            store["conversations"] = conversations
            if store.get("active_chat_id") == chat_id:
                store["active_chat_id"] = conversations[0]["id"] if conversations else None
            _write_store(user, store)
    except Exception:
        pass
