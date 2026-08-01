import base64
import json
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from paperless_paddleocr.client import (
    PaddleOCRClient,
    PaddleOCRError,
    PaddleOCRProtocolError,
)
from paperless_paddleocr.config import PluginSettings


def _settings() -> PluginSettings:
    return PluginSettings(
        enabled=True,
        base_url="https://paddleocr.example.test",
        api_key="test-key",
        score=21,
        connect_timeout=1,
        read_timeout=1,
        write_timeout=1,
        max_attempts=1,
        backoff_initial_seconds=1,
        backoff_max_seconds=30,
        max_source_bytes=1024,
        max_response_bytes=1024,
        use_charts=True,
        use_seals=False,
        include_headers_footers=True,
    )


def _success_response() -> dict[str, object]:
    return {
        "logId": "request-123",
        "result": {
            "layoutParsingResults": [
                {
                    "prunedResult": {"parsing_res_list": []},
                    "markdown": {"text": ""},
                }
            ],
            "dataInfo": {"width": 1200, "height": 800, "type": "image"},
        },
    }


def _client(
    handler: httpx.MockTransport, settings: PluginSettings | None = None
) -> PaddleOCRClient:
    client = PaddleOCRClient(settings or _settings())
    headers = dict(client._client.headers)
    client._client.close()
    client._client = httpx.Client(
        base_url="https://paddleocr.example.test",
        headers=headers,
        transport=handler,
    )
    return client


def test_extract_page_serializes_image_as_documented_request(
    tmp_path: Path,
) -> None:
    document = tmp_path / "invoice.png"
    document.write_bytes(b"png")
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=_success_response())

    with _client(httpx.MockTransport(handler)) as client:
        result = client.extract_page(document)

    assert result.data_info.width == 1200
    assert len(requests) == 1
    request = requests[0]
    assert request.method == "POST"
    assert request.url == "https://paddleocr.example.test/layout-parsing"
    assert request.headers["Authorization"] == "Bearer test-key"
    assert json.loads(request.content) == {
        "file": base64.b64encode(b"png").decode("ascii"),
        "fileType": 1,
        "useDocOrientationClassify": False,
        "useDocUnwarping": False,
        "useLayoutDetection": True,
        "useChartRecognition": True,
        "useSealRecognition": False,
        "formatBlockContent": False,
        "prettifyMarkdown": False,
        "returnMarkdownImages": False,
        "visualize": False,
    }


def test_extract_reports_documented_error_response(tmp_path: Path) -> None:
    document = tmp_path / "invoice.png"
    document.write_bytes(b"png")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422,
            json={
                "logId": "request-123",
                "errorCode": 1001,
                "errorMsg": "invalid document",
            },
        )

    with (
        _client(httpx.MockTransport(handler)) as client,
        pytest.raises(PaddleOCRError, match="PaddleOCR error 1001: invalid document"),
    ):
        client.extract_page(document)


def test_extract_rejects_malformed_success_response(tmp_path: Path) -> None:
    document = tmp_path / "invoice.png"
    document.write_bytes(b"png")

    def handler(request: httpx.Request) -> httpx.Response:
        response = _success_response()
        result = response["result"]
        assert isinstance(result, dict)
        result.pop("dataInfo")
        return httpx.Response(200, json=response)

    with (
        _client(httpx.MockTransport(handler)) as client,
        pytest.raises(PaddleOCRProtocolError, match="invalid success response"),
    ):
        client.extract_page(document)


def test_extract_uses_configured_capped_backoff(tmp_path: Path, monkeypatch) -> None:
    document = tmp_path / "invoice.png"
    document.write_bytes(b"png")
    attempts = 0
    delays: list[float] = []
    jitter_ranges: list[tuple[float, float]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            return httpx.Response(503)
        return httpx.Response(200, json=_success_response())

    def uniform(lower: float, upper: float) -> float:
        jitter_ranges.append((lower, upper))
        return 1.0

    monkeypatch.setattr("paperless_paddleocr.client.random.uniform", uniform)
    monkeypatch.setattr("paperless_paddleocr.client.time.sleep", delays.append)
    settings = replace(
        _settings(),
        max_attempts=3,
        backoff_initial_seconds=2,
        backoff_max_seconds=3,
    )

    with _client(httpx.MockTransport(handler), settings) as client:
        result = client.extract_page(document)

    assert result.data_info.width == 1200
    assert attempts == 3
    assert jitter_ranges == [(0.75, 1.25), (0.75, 1.25)]
    assert delays == [2, 3]
