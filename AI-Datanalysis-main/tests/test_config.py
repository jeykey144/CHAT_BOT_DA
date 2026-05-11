import pytest

from ai_datanalysis.config import inspect_auth_db_url, validate_auth_db_url


def test_inspect_auth_db_url_redacts_password():
    info = inspect_auth_db_url(
        "mysql+pymysql://chatbot_app:secret@mysql-chatbot.example.com:3306/chatbot?charset=utf8mb4"
    )

    assert info.username == "chatbot_app"
    assert info.host == "mysql-chatbot.example.com"
    assert info.port == 3306
    assert info.database == "chatbot"
    assert "secret" not in info.redacted_url
    assert "***" in info.redacted_url


def test_validate_auth_db_url_rejects_localhost_in_production():
    with pytest.raises(RuntimeError, match="local MySQL host in production"):
        validate_auth_db_url(
            "mysql+pymysql://chatbot_app:secret@localhost:3306/chatbot?charset=utf8mb4",
            "production",
        )


def test_validate_auth_db_url_allows_localhost_in_development():
    info = validate_auth_db_url(
        "mysql+pymysql://root:secret@127.0.0.1:3306/chatbot?charset=utf8mb4",
        "development",
    )

    assert info.host == "127.0.0.1"


def test_validate_auth_db_url_rejects_old_database_name_in_production():
    with pytest.raises(RuntimeError, match="chatbot_auth"):
        validate_auth_db_url(
            "mysql+pymysql://root:secret@mysql-chatbot.example.com:3306/chatbot_auth?charset=utf8mb4",
            "production",
        )
