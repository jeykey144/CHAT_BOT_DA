"""
Local encrypted cookie manager without deprecated Streamlit cache APIs.
"""
from __future__ import annotations

import base64
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Mapping, MutableMapping, Optional, Tuple
from urllib.parse import unquote

from cryptography import fernet
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import streamlit as st
from streamlit.components.v1 import components
from ai_datanalysis.paths import PROJECT_ROOT

_build_path = PROJECT_ROOT / ".streamlit_cookies_component"
_component_func = components.declare_component(
    "CookieManager.sync_cookies",
    path=str(_build_path),
)


@lru_cache(maxsize=32)
def key_from_parameters(salt: bytes, iterations: int, password: str) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))


class CookiesNotReady(Exception):
    pass


def parse_cookies(raw_cookie: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for part in raw_cookie.split(";"):
        part = part.strip()
        if not part:
            continue
        name, value = part.split("=", 1)
        cookies[unquote(name)] = unquote(value)
    return cookies


class CookieManager(MutableMapping[str, str]):
    def __init__(self, *, path: str = None, prefix: str = ""):
        self._queue = st.session_state.setdefault("CookieManager.queue", {})
        self._prefix = prefix
        raw_cookie = self._run_component(save_only=False, key="CookieManager.sync_cookies")
        if raw_cookie is None:
            self._cookies = None
        else:
            self._cookies = parse_cookies(raw_cookie)
            self._clean_queue()
        self._default_expiry = datetime.now() + timedelta(days=365)
        self._path = path if path is not None else "/"

    def ready(self) -> bool:
        return self._cookies is not None

    def save(self):
        if self._queue:
            self._run_component(save_only=True, key="CookieManager.sync_cookies.save")

    def _run_component(self, save_only: bool, key: str):
        queue = {self._prefix + k: v for k, v in self._queue.items()}
        return _component_func(queue=queue, saveOnly=save_only, key=key)

    def _clean_queue(self):
        for name, spec in list(self._queue.items()):
            value = self._cookies.get(self._prefix + name)
            if value == spec["value"]:
                del self._queue[name]

    def __repr__(self):
        if self.ready():
            return f"<CookieManager: {dict(self)!r}>"
        return "<CookieManager: not ready>"

    def __getitem__(self, key: str) -> str:
        return self._get_cookies()[key]

    def __iter__(self):
        return iter(self._get_cookies())

    def __len__(self):
        return len(self._get_cookies())

    def __setitem__(self, key: str, value: str) -> None:
        stored_key = self._prefix + key
        if self._cookies.get(stored_key) != value:
            self._queue[key] = {
                "value": value,
                "expires_at": self._default_expiry.isoformat(),
                "path": self._path,
            }

    def __delitem__(self, key: str) -> None:
        stored_key = self._prefix + key
        if stored_key in self._cookies or key in self._queue:
            self._queue[key] = {"value": None, "path": self._path}

    def _get_cookies(self) -> Mapping[str, str]:
        if self._cookies is None:
            raise CookiesNotReady()
        cookies = {
            key[len(self._prefix) :]: value
            for key, value in self._cookies.items()
            if key.startswith(self._prefix)
        }
        for name, spec in self._queue.items():
            if spec["value"] is not None:
                cookies[name] = spec["value"]
            else:
                cookies.pop(name, None)
        return cookies


class EncryptedCookieManager(MutableMapping[str, str]):
    def __init__(
        self,
        *,
        password: str,
        path: str = None,
        prefix: str = "",
        key_params_cookie: str = "EncryptedCookieManager.key_params",
        ignore_broken: bool = True,
    ):
        self._cookie_manager = CookieManager(path=path, prefix=prefix)
        self._fernet: Optional[Fernet] = None
        self._key_params_cookie = key_params_cookie
        self._password = password
        self._ignore_broken = ignore_broken

    def ready(self):
        return self._cookie_manager.ready()

    def save(self):
        return self._cookie_manager.save()

    def _encrypt(self, value: bytes) -> bytes:
        self._setup_fernet()
        return self._fernet.encrypt(value)

    def _decrypt(self, value: bytes) -> bytes:
        self._setup_fernet()
        return self._fernet.decrypt(value)

    def _setup_fernet(self):
        if self._fernet is not None:
            return
        key_params = self._get_key_params()
        if not key_params:
            key_params = self._initialize_new_key_params()
        salt, iterations, _magic = key_params
        key = key_from_parameters(salt=salt, iterations=iterations, password=self._password)
        self._fernet = Fernet(key)

    def _get_key_params(self) -> Optional[Tuple[bytes, int, bytes]]:
        raw_key_params = self._cookie_manager.get(self._key_params_cookie)
        if not raw_key_params:
            return None
        try:
            raw_salt, raw_iterations, raw_magic = raw_key_params.split(":")
            return (
                base64.b64decode(raw_salt),
                int(raw_iterations),
                base64.b64decode(raw_magic),
            )
        except (ValueError, TypeError):
            return None

    def _initialize_new_key_params(self) -> Tuple[bytes, int, bytes]:
        import os

        salt = os.urandom(16)
        iterations = 390000
        magic = os.urandom(16)
        self._cookie_manager[self._key_params_cookie] = b":".join(
            [
                base64.b64encode(salt),
                str(iterations).encode("ascii"),
                base64.b64encode(magic),
            ]
        ).decode("ascii")
        return salt, iterations, magic

    def __repr__(self):
        if self.ready():
            return f"<EncryptedCookieManager: {dict(self)!r}>"
        return "<EncryptedCookieManager: not ready>"

    def __getitem__(self, k: str) -> str:
        try:
            return self._decrypt(self._cookie_manager[k].encode("utf-8")).decode("utf-8")
        except fernet.InvalidToken:
            if self._ignore_broken:
                return None
            raise

    def __iter__(self):
        return iter(self._cookie_manager)

    def __len__(self):
        return len(self._cookie_manager)

    def __setitem__(self, key: str, value: str) -> None:
        self._cookie_manager[key] = self._encrypt(value.encode("utf-8")).decode("utf-8")

    def __delitem__(self, key: str) -> None:
        del self._cookie_manager[key]
