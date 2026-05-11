"""Configuration helpers shared by the Streamlit app and tests."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.engine import make_url


LOCAL_DB_HOSTS = {"", "localhost", "127.0.0.1", "::1", "0.0.0.0"}


@dataclass(frozen=True)
class AuthDbUrlInfo:
    drivername: str
    username: str
    host: str
    port: int | None
    database: str
    redacted_url: str

    @property
    def is_local_host(self) -> bool:
        return self.host.lower() in LOCAL_DB_HOSTS

    @property
    def summary(self) -> str:
        port = self.port if self.port is not None else "(default)"
        username = self.username or "(missing)"
        host = self.host or "(missing)"
        database = self.database or "(missing)"
        return f"user={username}, host={host}, port={port}, database={database}"


def inspect_auth_db_url(raw_url: str) -> AuthDbUrlInfo:
    auth_db_url = (raw_url or "").strip()
    if not auth_db_url:
        raise RuntimeError("Missing AUTH_DB_URL env var.")

    try:
        url = make_url(auth_db_url)
    except Exception as ex:
        raise RuntimeError(
            "AUTH_DB_URL is not a valid SQLAlchemy URL. Set the value to only "
            "mysql+pymysql://user:password@host:3306/database?charset=utf8mb4."
        ) from ex

    return AuthDbUrlInfo(
        drivername=url.drivername or "",
        username=url.username or "",
        host=url.host or "",
        port=url.port,
        database=url.database or "",
        redacted_url=url.render_as_string(hide_password=True),
    )


def validate_auth_db_url(raw_url: str, app_env: str) -> AuthDbUrlInfo:
    info = inspect_auth_db_url(raw_url)
    is_production = (app_env or "").strip().lower() == "production"

    if is_production and info.is_local_host:
        raise RuntimeError(
            "AUTH_DB_URL points to a local MySQL host in production. "
            f"Current target: {info.summary}. "
            "Set AUTH_DB_URL on the deployment platform to the RDS endpoint."
        )

    if is_production and info.database == "chatbot_auth":
        raise RuntimeError(
            "AUTH_DB_URL points to database 'chatbot_auth' in production. "
            "This RDS instance uses database 'chatbot'."
        )

    return info
