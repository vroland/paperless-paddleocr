"""Display-only metadata for Paperless document file details."""

from __future__ import annotations

from . import __version__


def parser_metadata() -> list[dict[str, str]]:
    """Return static parser provenance without exposing service configuration."""
    return [
        {
            "namespace": "urn:paperless-paddleocr:metadata",
            "prefix": "paddleocr",
            "key": "Parser",
            "value": f"PaddleOCR-VL Parser v{__version__}",
        }
    ]
