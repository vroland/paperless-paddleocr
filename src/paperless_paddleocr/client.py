"""HTTP client for PaddleOCR's layout-parsing endpoint."""

from __future__ import annotations

import base64
import json
import random
import time
from pathlib import Path
from typing import Any

import httpx

from .config import PluginSettings

RETRYABLE_STATUS_CODES = {408, 429, 502, 503, 504}


class PaddleOCRError(RuntimeError):
    """Base class for PaddleOCR integration failures."""


class PaddleOCRUnavailable(PaddleOCRError):
    """The service could not be reached or remained unavailable."""


class PaddleOCRProtocolError(PaddleOCRError):
    """The service returned an invalid or incompatible response."""


class PaddleOCRClient:
    def __init__(self, settings: PluginSettings) -> None:
        if not settings.base_url:
            raise PaddleOCRProtocolError("PAPERLESS_PADDLEOCR_URL is not configured")

        headers = {"Accept": "application/json"}
        if settings.api_key:
            headers["Authorization"] = f"Bearer {settings.api_key}"

        self.settings = settings
        self._client = httpx.Client(
            base_url=settings.base_url.rstrip("/"),
            headers=headers,
            timeout=httpx.Timeout(
                connect=settings.connect_timeout,
                read=settings.read_timeout,
                write=settings.write_timeout,
                pool=settings.connect_timeout,
            ),
            follow_redirects=False,
        )

    def __enter__(self) -> PaddleOCRClient:
        return self

    def __exit__(self, *args: object) -> None:
        self._client.close()

    def extract(self, document_path: Path, mime_type: str) -> dict[str, Any]:
        size = document_path.stat().st_size
        if size > self.settings.max_source_bytes:
            raise PaddleOCRProtocolError(f"source exceeds size limit: {size} bytes")

        payload = {
            "file": base64.b64encode(document_path.read_bytes()).decode("ascii"),
            "fileType": 0 if mime_type == "application/pdf" else 1,
            "useDocOrientationClassify": self.settings.use_orientation,
            "useDocUnwarping": self.settings.use_unwarping,
            "useLayoutDetection": True,
            "useChartRecognition": self.settings.use_charts,
            "useSealRecognition": self.settings.use_seals,
            "formatBlockContent": False,
            "prettifyMarkdown": False,
            "returnMarkdownImages": False,
            "visualize": False,
        }

        last_error: Exception | None = None
        for attempt in range(1, self.settings.max_attempts + 1):
            try:
                response = self._client.post("/layout-parsing", json=payload)
                self._validate_response_size(response)
                if response.status_code in RETRYABLE_STATUS_CODES:
                    raise PaddleOCRUnavailable(f"temporary HTTP status {response.status_code}")
                response.raise_for_status()
                try:
                    data = response.json()
                except json.JSONDecodeError as exc:
                    raise PaddleOCRProtocolError("PaddleOCR returned non-JSON content") from exc
                self.validate_response(data)
                return data
            except PaddleOCRProtocolError:
                raise
            except (
                httpx.ConnectError,
                httpx.ConnectTimeout,
                httpx.ReadTimeout,
                httpx.WriteTimeout,
                httpx.PoolTimeout,
                PaddleOCRUnavailable,
            ) as exc:
                last_error = exc
                if attempt < self.settings.max_attempts:
                    time.sleep(random.uniform(0.75, 1.25) * 2 ** (attempt - 1))
            except httpx.HTTPStatusError as exc:
                raise PaddleOCRProtocolError(f"PaddleOCR HTTP {exc.response.status_code}") from exc

        raise PaddleOCRUnavailable(
            f"PaddleOCR unavailable after {self.settings.max_attempts} attempts"
        ) from last_error

    def _validate_response_size(self, response: httpx.Response) -> None:
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > self.settings.max_response_bytes:
            raise PaddleOCRProtocolError("response exceeds configured size limit")
        if len(response.content) > self.settings.max_response_bytes:
            raise PaddleOCRProtocolError("response exceeds configured size limit")

    @staticmethod
    def validate_response(data: Any) -> None:
        if not isinstance(data, dict):
            raise PaddleOCRProtocolError("top-level response is not an object")
        if data.get("errorCode", 0) not in (0, None):
            raise PaddleOCRProtocolError(
                f"PaddleOCR error {data.get('errorCode')}: {data.get('errorMsg', 'unknown')}"
            )
        result = data.get("result")
        if not isinstance(result, dict) or not isinstance(result.get("layoutParsingResults"), list):
            raise PaddleOCRProtocolError("response has no layoutParsingResults array")
