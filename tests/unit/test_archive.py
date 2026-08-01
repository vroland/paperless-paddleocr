from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from paperless_paddleocr.archive.engine import PaddleOcrVLEngine
from paperless_paddleocr.archive.source import image_page_count, stage_image_pdf
from paperless_paddleocr.archive.validate import (
    ArchiveValidationError,
    pages_have_safe_geometry,
    validate_and_read_sidecar,
    write_page_status,
)
from paperless_paddleocr.config import PluginSettings
from paperless_paddleocr.schemas import InferResult, LayoutParsingResult
from paperless_paddleocr.text import normalize_layout_page


def _page(blocks: list[dict[str, object]]) -> LayoutParsingResult:
    return LayoutParsingResult.model_validate(
        {"prunedResult": {"parsing_res_list": blocks}, "markdown": {"text": ""}}
    )


def _settings() -> PluginSettings:
    return PluginSettings(
        enabled=True,
        base_url="http://ocr.example",
        api_key=None,
        score=21,
        connect_timeout=1,
        read_timeout=1,
        write_timeout=1,
        max_attempts=1,
        backoff_initial_seconds=0,
        backoff_max_seconds=0,
        max_source_bytes=1024,
        max_response_bytes=1024,
        use_charts=False,
        use_seals=False,
    )


def test_normalized_page_keeps_text_when_block_geometry_is_invalid() -> None:
    page = normalize_layout_page(
        _page([{"block_label": "text", "block_content": "Invoice", "block_bbox": []}]),
        0,
        100,
        100,
        72,
    )

    assert page.text == "Invoice"
    assert page.geometry_safe is False


def test_status_and_sidecar_require_all_pages(tmp_path: Path) -> None:
    status_dir = tmp_path / "status"
    write_page_status(status_dir, 0, True)
    write_page_status(status_dir, 1, False)
    sidecar = tmp_path / "sidecar.txt"
    sidecar.write_text("First\fSecond", encoding="utf-8")

    assert pages_have_safe_geometry(status_dir, 2) is False
    assert validate_and_read_sidecar(sidecar, 2) == "First\n\n\f\n\nSecond"

    with pytest.raises(ArchiveValidationError, match="every page"):
        pages_have_safe_geometry(status_dir, 3)


def test_multipage_tiff_is_staged_as_matching_pdf_pages(tmp_path: Path) -> None:
    source = tmp_path / "source.tiff"
    first = Image.new("RGB", (20, 10), "white")
    second = Image.new("RGB", (10, 20), "black")
    first.save(source, save_all=True, append_images=[second], dpi=(100, 100))
    staged = tmp_path / "source.pdf"

    assert image_page_count(source, "image/tiff") == 2
    assert stage_image_pdf(source, "image/tiff", staged, None) == 2
    assert staged.is_file()


def test_jpeg_is_staged_as_single_pdf_page(tmp_path: Path) -> None:
    source = tmp_path / "source.jpg"
    Image.new("RGB", (20, 10), "white").save(source, dpi=(100, 100))
    staged = tmp_path / "source.pdf"

    assert image_page_count(source, "image/jpeg") == 1
    assert stage_image_pdf(source, "image/jpeg", staged, None) == 1
    assert staged.is_file()


def test_engine_returns_normalized_text_and_records_status(
    tmp_path: Path, monkeypatch
) -> None:
    input_file = tmp_path / "ocr.png"
    Image.new("RGB", (100, 50), "white").save(input_file, dpi=(72, 72))
    response = InferResult.model_validate(
        {
            "layoutParsingResults": [
                {
                    "prunedResult": {
                        "parsing_res_list": [
                            {
                                "block_label": "text",
                                "block_content": "Paddle text",
                                "block_bbox": [10, 10, 90, 30],
                            }
                        ]
                    },
                    "markdown": {"text": ""},
                }
            ],
            "dataInfo": {"width": 100, "height": 50, "type": "image"},
        }
    )

    class FakeClient:
        def __init__(self, settings: PluginSettings) -> None:
            assert settings == _settings()

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def extract_page(self, path: Path) -> InferResult:
            assert path == input_file
            return response

    monkeypatch.setattr(
        "paperless_paddleocr.archive.engine.PaddleOCRClient", FakeClient
    )
    status_dir = tmp_path / "status"
    options = SimpleNamespace(
        paddle_settings=_settings(), paddle_status_dir=str(status_dir)
    )

    root, text = PaddleOcrVLEngine.generate_ocr(input_file, options)

    assert text == "Paddle text"
    assert [word.text for word in root.words] == ["Paddle text"]
    assert pages_have_safe_geometry(status_dir, 1) is True
