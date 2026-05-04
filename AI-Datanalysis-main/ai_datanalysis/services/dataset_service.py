"""
Dataset service for upload persistence and safe loading.
"""
from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List

import pandas as pd
import streamlit as st

from ai_datanalysis.paths import UPLOADS_DIR


UPLOAD_DIR = UPLOADS_DIR
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_UPLOAD_FILES = 5
MAX_EXCEL_SHEETS = 10
MAX_ROWS = 250_000
MAX_COLS = 200


def _normalize_user(user: str) -> str:
    return (user or "anonymous").strip().lower()


def _normalize_chat(chat_id: str | None) -> str:
    return (chat_id or "").strip().lower().replace("/", "_").replace("\\", "_")


def _user_dir(user: str) -> Path:
    user_dir = UPLOAD_DIR / _normalize_user(user)
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def _manifest_dir(user: str) -> Path:
    path = _user_dir(user) / "manifests"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _manifest_path(user: str, chat_id: str | None = None) -> Path:
    if chat_id:
        return _manifest_dir(user) / f"{_normalize_chat(chat_id)}.json"
    return _user_dir(user) / "manifest.json"


def _validate_frame_shape(df: pd.DataFrame, source_name: str) -> None:
    if df.shape[0] > MAX_ROWS:
        raise ValueError(f"{source_name} has too many rows ({df.shape[0]} > {MAX_ROWS}).")
    if df.shape[1] > MAX_COLS:
        raise ValueError(f"{source_name} has too many columns ({df.shape[1]} > {MAX_COLS}).")


def _validate_uploads(files: Iterable) -> None:
    files = list(files)
    if len(files) > MAX_UPLOAD_FILES:
        raise ValueError(f"Too many files. Maximum is {MAX_UPLOAD_FILES}.")
    for f in files:
        size = len(f.getvalue())
        if size > MAX_UPLOAD_BYTES:
            raise ValueError(f"{f.name} exceeds the size limit of {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")


def _dedupe_preserve_order(paths: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for path in paths:
        path_str = str(path)
        if path_str in seen:
            continue
        seen.add(path_str)
        ordered.append(path_str)
    return ordered


def save_uploaded_files(user: str, uploaded_files, append: bool = True, chat_id: str | None = None) -> list[str]:
    files = list(uploaded_files or [])
    _validate_uploads(files)

    user = _normalize_user(user)
    user_dir = _user_dir(user)
    user_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    paths: list[str] = []
    for f in files:
        safe_name = f.name.replace("/", "_").replace("\\", "_")
        path = user_dir / f"{ts}_{safe_name}"
        path.write_bytes(f.getvalue())
        paths.append(str(path))

    manifest_path = _manifest_path(user, chat_id=chat_id)
    existing_paths: list[str] = []
    if append and manifest_path.exists():
        try:
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                existing_paths = [str(item) for item in raw]
        except Exception:
            existing_paths = []

    manifest_paths = _dedupe_preserve_order(existing_paths + paths)
    manifest_path.write_text(json.dumps(manifest_paths, ensure_ascii=False), encoding="utf-8")
    return manifest_paths


def load_saved_manifest(user: str, chat_id: str | None = None) -> list[str]:
    manifest_path = _manifest_path(user, chat_id=chat_id)
    if not manifest_path.exists():
        return []
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return data if isinstance(data, list) else []


def clear_saved_manifest(user: str, chat_id: str | None = None) -> None:
    if chat_id:
        manifest_path = _manifest_path(user, chat_id=chat_id)
        if manifest_path.exists():
            manifest_path.unlink()
        return

    manifest_path = _manifest_path(user)
    if manifest_path.exists():
        manifest_path.unlink()

    manifest_dir = _manifest_dir(user)
    for path in manifest_dir.glob("*.json"):
        try:
            path.unlink()
        except OSError:
            pass


@st.cache_data(show_spinner=False)
def _read_csv(file_bytes: bytes, source_name: str) -> pd.DataFrame:
    for enc in ("utf-8", "utf-8-sig", "cp1258", "latin1"):
        try:
            df = pd.read_csv(io.BytesIO(file_bytes), encoding=enc, low_memory=False)
            _validate_frame_shape(df, source_name)
            return df
        except ValueError:
            raise
        except Exception:
            continue

    df = pd.read_csv(io.BytesIO(file_bytes), low_memory=False)
    _validate_frame_shape(df, source_name)
    return df


@st.cache_data(show_spinner=False)
def _read_excel(file_bytes: bytes, filename: str) -> Dict[str, pd.DataFrame]:
    xls = pd.ExcelFile(io.BytesIO(file_bytes))
    if len(xls.sheet_names) > MAX_EXCEL_SHEETS:
        raise ValueError(f"{filename} has too many sheets ({len(xls.sheet_names)} > {MAX_EXCEL_SHEETS}).")

    dfs: Dict[str, pd.DataFrame] = {}
    for i, sheet in enumerate(xls.sheet_names):
        key = f"{filename}::sheet_{i}::{sheet}"
        df = pd.read_excel(xls, sheet_name=sheet)
        _validate_frame_shape(df, key)
        dfs[key] = df
    return dfs


def load_datasets(files: List) -> Dict[str, pd.DataFrame]:
    data: Dict[str, pd.DataFrame] = {}
    counter = 1
    files = list(files or [])
    _validate_uploads(files)

    for f in files:
        name = f.name
        b = f.getvalue()

        if name.lower().endswith(".csv"):
            key = f"DF_{counter}___{name}"
            data[key] = _read_csv(b, name)
            counter += 1

        elif name.lower().endswith((".xlsx", ".xls")):
            dfs = _read_excel(b, name)
            for k, df in dfs.items():
                key = f"DF_{counter}___{k}"
                data[key] = df
                counter += 1

    return data


def load_saved_paths(paths: list[str], user: str | None = None) -> Dict[str, pd.DataFrame]:
    data: Dict[str, pd.DataFrame] = {}
    counter = 1
    allowed_root = (UPLOAD_DIR / _normalize_user(user or "anonymous")).resolve() if user else None

    for p in paths:
        pth = Path(p)
        if not pth.exists():
            continue
        resolved = pth.resolve()
        if allowed_root and allowed_root not in resolved.parents:
            continue

        b = resolved.read_bytes()
        name = resolved.name

        if name.lower().endswith(".csv"):
            key = f"DF_{counter}___{name}"
            data[key] = _read_csv(b, name)
            counter += 1

        elif name.lower().endswith((".xlsx", ".xls")):
            dfs = _read_excel(b, name)
            for k, df in dfs.items():
                key = f"DF_{counter}___{k}"
                data[key] = df
                counter += 1

    return data
