import pytest

from paperless_paddleocr.config import PluginSettings


def test_settings_use_safe_defaults(monkeypatch) -> None:
    monkeypatch.delenv("PAPERLESS_PADDLEOCR_URL", raising=False)

    settings = PluginSettings.from_environment()

    assert settings.enabled is True
    assert settings.base_url is None
    assert settings.score == 21
    assert settings.max_attempts == 3
    assert settings.backoff_initial_seconds == 1.0
    assert settings.backoff_max_seconds == 30.0


def test_settings_read_environment(monkeypatch) -> None:
    monkeypatch.setenv("PAPERLESS_PADDLEOCR_URL", "http://ocr.example:8088/")
    monkeypatch.setenv("PAPERLESS_PADDLEOCR_ENABLED", "false")
    monkeypatch.setenv("PAPERLESS_PADDLEOCR_SCORE", "31")
    monkeypatch.setenv("PAPERLESS_PADDLEOCR_BACKOFF_INITIAL_SECONDS", "2.5")
    monkeypatch.setenv("PAPERLESS_PADDLEOCR_BACKOFF_MAX_SECONDS", "12")

    settings = PluginSettings.from_environment()

    assert settings.enabled is False
    assert settings.base_url == "http://ocr.example:8088/"
    assert settings.score == 31
    assert settings.backoff_initial_seconds == 2.5
    assert settings.backoff_max_seconds == 12.0


def test_settings_reject_invalid_backoff_range(monkeypatch) -> None:
    monkeypatch.setenv("PAPERLESS_PADDLEOCR_BACKOFF_INITIAL_SECONDS", "5")
    monkeypatch.setenv("PAPERLESS_PADDLEOCR_BACKOFF_MAX_SECONDS", "4")

    with pytest.raises(ValueError, match="backoff settings"):
        PluginSettings.from_environment()
