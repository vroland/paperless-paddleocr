"""Paperless parser protocol implementation."""

from __future__ import annotations

import logging
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import Self

from django.conf import settings
from documents.parsers import ParseError
from paperless.parsers import ParserContext
from paperless.parsers.utils import (
    PDF_TEXT_MIN_LENGTH,
    extract_pdf_text,
    get_page_count_for_pdf,
    is_tagged_pdf,
)

from . import __version__
from .client import PaddleOCRClient
from .config import PluginSettings
from .metadata import parser_metadata
from .text import extract_plain_text

logger = logging.getLogger("paperless.parsing.paddleocr")


# TODO: Use a public Paperless born-digital helper when available after v3.0.4.
def _has_native_pdf_text(document_path: Path) -> bool:
    text = extract_pdf_text(document_path)
    return bool(text) and (
        is_tagged_pdf(document_path) or len(text) > PDF_TEXT_MIN_LENGTH
    )


class PaddleOCRVLParser:
    name = "PaddleOCR-VL Parser"
    version = __version__
    author = "paperless-paddleocr"
    url = "https://github.com/"

    @classmethod
    def supported_mime_types(cls) -> dict[str, str]:
        return {
            "application/pdf": ".pdf",
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/tiff": ".tiff",
        }

    @classmethod
    def score(
        cls, mime_type: str, filename: str, path: Path | None = None
    ) -> int | None:
        config = PluginSettings.from_environment()
        if (
            not config.enabled
            or not config.base_url
            or mime_type not in cls.supported_mime_types()
        ):
            return None
        if mime_type == "application/pdf" and path and _has_native_pdf_text(path):
            logger.info("PaddleOCR-VL Parser declined native-text PDF: %s", filename)
            return None
        return config.score

    @property
    def can_produce_archive(self) -> bool:
        return False

    @property
    def requires_pdf_rendition(self) -> bool:
        return False

    def __init__(self, logging_group: object = None) -> None:
        self._tempdir = Path(
            tempfile.mkdtemp(prefix="paperless-paddleocr-", dir=settings.SCRATCH_DIR)
        )
        self._logging_group = logging_group
        self._context: ParserContext | None = None
        self._text = ""

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        shutil.rmtree(self._tempdir, ignore_errors=True)

    def configure(self, context: ParserContext) -> None:
        self._context = context

    def parse(
        self, document_path: Path, mime_type: str, *, produce_archive: bool = True
    ) -> None:
        if mime_type not in self.supported_mime_types() or not document_path.is_file():
            raise ParseError(
                "PaddleOCR-VL received an unsupported or missing source file"
            )
        try:
            with PaddleOCRClient(PluginSettings.from_environment()) as client:
                self._text = extract_plain_text(
                    client.extract(document_path, mime_type)
                )
            if not self._text:
                raise ValueError("PaddleOCR returned no usable text")
        except ParseError:
            raise
        except Exception as exc:
            raise ParseError(
                f"PaddleOCR-VL extraction failed: {type(exc).__name__}: {exc}"
            ) from exc

    def get_text(self) -> str:
        return self._text

    def get_date(self) -> datetime | None:
        return None

    def get_archive_path(self) -> Path | None:
        return None

    def get_page_count(self, document_path: Path, mime_type: str) -> int | None:
        if mime_type == "application/pdf":
            return get_page_count_for_pdf(document_path)
        return 1 if mime_type.startswith("image/") else None

    def get_thumbnail(self, document_path: Path, mime_type: str) -> Path:
        if mime_type == "application/pdf":
            from documents.parsers import make_thumbnail_from_pdf

            return make_thumbnail_from_pdf(
                document_path, self._tempdir, self._logging_group
            )
        from PIL import Image, ImageOps

        output = self._tempdir / "thumbnail.webp"
        with Image.open(document_path) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.thumbnail((500, 700))
            image.save(output, format="WEBP", quality=85, method=6)
        return output

    def extract_metadata(self, document_path: Path, mime_type: str) -> list[object]:
        return parser_metadata()
