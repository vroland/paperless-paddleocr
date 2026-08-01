"""Environment-backed configuration for the Paperless parser."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value else default


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    return float(value) if value else default


@dataclass(frozen=True, slots=True)
class PluginSettings:
    enabled: bool
    base_url: str | None
    api_key: str | None
    score: int
    connect_timeout: float
    read_timeout: float
    write_timeout: float
    max_attempts: int
    backoff_initial_seconds: float
    backoff_max_seconds: float
    max_source_bytes: int
    max_response_bytes: int
    use_orientation: bool
    use_unwarping: bool
    use_charts: bool
    use_seals: bool

    @classmethod
    def from_environment(cls) -> PluginSettings:
        base_url = os.getenv("PAPERLESS_PADDLEOCR_URL", "").strip() or None
        backoff_initial_seconds = _get_float(
            "PAPERLESS_PADDLEOCR_BACKOFF_INITIAL_SECONDS", 1.0
        )
        backoff_max_seconds = _get_float(
            "PAPERLESS_PADDLEOCR_BACKOFF_MAX_SECONDS", 30.0
        )
        if backoff_initial_seconds < 0 or backoff_max_seconds < backoff_initial_seconds:
            raise ValueError(
                "PaddleOCR backoff settings must be non-negative and ordered"
            )
        return cls(
            enabled=_get_bool("PAPERLESS_PADDLEOCR_ENABLED", True),
            base_url=base_url,
            api_key=os.getenv("PAPERLESS_PADDLEOCR_API_KEY") or None,
            score=_get_int("PAPERLESS_PADDLEOCR_SCORE", 21),
            connect_timeout=_get_float("PAPERLESS_PADDLEOCR_TIMEOUT_CONNECT", 10.0),
            read_timeout=_get_float("PAPERLESS_PADDLEOCR_TIMEOUT_READ", 900.0),
            write_timeout=_get_float("PAPERLESS_PADDLEOCR_TIMEOUT_WRITE", 120.0),
            max_attempts=_get_int("PAPERLESS_PADDLEOCR_MAX_ATTEMPTS", 3),
            backoff_initial_seconds=backoff_initial_seconds,
            backoff_max_seconds=backoff_max_seconds,
            max_source_bytes=_get_int(
                "PAPERLESS_PADDLEOCR_MAX_BYTES", 100 * 1024 * 1024
            ),
            max_response_bytes=_get_int(
                "PAPERLESS_PADDLEOCR_MAX_RESPONSE_BYTES", 200 * 1024 * 1024
            ),
            use_orientation=_get_bool("PAPERLESS_PADDLEOCR_USE_ORIENTATION", False),
            use_unwarping=_get_bool("PAPERLESS_PADDLEOCR_USE_UNWARPING", False),
            use_charts=_get_bool("PAPERLESS_PADDLEOCR_USE_CHARTS", False),
            use_seals=_get_bool("PAPERLESS_PADDLEOCR_USE_SEALS", False),
        )
