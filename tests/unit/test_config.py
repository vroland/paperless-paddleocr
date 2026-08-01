from paperless_paddleocr.config import PluginSettings


def test_settings_use_safe_defaults(monkeypatch) -> None:
    monkeypatch.delenv("PAPERLESS_PADDLEOCR_URL", raising=False)

    settings = PluginSettings.from_environment()

    assert settings.enabled is True
    assert settings.base_url is None
    assert settings.score == 21
    assert settings.max_attempts == 3


def test_settings_read_environment(monkeypatch) -> None:
    monkeypatch.setenv("PAPERLESS_PADDLEOCR_URL", "http://ocr.example:8088/")
    monkeypatch.setenv("PAPERLESS_PADDLEOCR_ENABLED", "false")
    monkeypatch.setenv("PAPERLESS_PADDLEOCR_SCORE", "31")

    settings = PluginSettings.from_environment()

    assert settings.enabled is False
    assert settings.base_url == "http://ocr.example:8088/"
    assert settings.score == 31
