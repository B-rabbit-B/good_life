from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.main import create_app

GOOD = {
    "database_url": "postgresql+psycopg://u:p@localhost:5433/db",
    "jwt_secret": "x" * 32,
    "field_encryption_key": "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
}


def _settings(**overrides: str) -> Settings:
    return Settings(_env_file=None, **{**GOOD, **overrides})


def test_valid_settings_are_accepted():
    assert _settings().jwt_secret == "x" * 32


@pytest.mark.parametrize(
    "overrides",
    [
        {"jwt_secret": "replace-with-a-random-string-of-at-least-32-chars"},
        {"field_encryption_key": "replace-with-output-of-the-fernet-generate-command-in-README"},
        {"jwt_secret": "too-short"},
        {"field_encryption_key": "not-a-fernet-key"},
    ],
)
def test_bad_secrets_are_rejected(overrides):
    with pytest.raises(ValidationError):
        _settings(**overrides)


def test_env_file_path_is_absolute_backend_env():
    env_file = Settings.model_config["env_file"]
    assert Path(env_file).is_absolute()
    assert Path(env_file) == Path(__file__).resolve().parents[1] / ".env"


def test_create_app_fails_fast_on_placeholder_secret(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "replace-with-a-random-string-of-at-least-32-chars")
    get_settings.cache_clear()
    try:
        with pytest.raises(ValidationError):
            create_app()
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
