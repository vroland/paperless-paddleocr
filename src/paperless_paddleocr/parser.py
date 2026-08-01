"""Paperless parser protocol implementation."""

from __future__ import annotations

import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import Any, Self

import ocrmypdf
from django.conf import settings
from documents.parsers import ParseError, make_thumbnail_from_pdf
from paperless.parsers import MetadataEntry, ParserContext
from paperless.parsers.utils import extract_pdf_text, get_page_count_for_pdf
from PIL import Image, ImageOps

from . import __version__
from .archive.source import (
    SourcePreparationError,
    image_page_count,
    stage_image_pdf,
    validate_staged_pdf,
)
from .archive.validate import (
    ArchiveValidationError,
    pages_have_safe_geometry,
    validate_and_read_sidecar,
    validate_archive,
)
from .config import PluginSettings

logger = logging.getLogger("paperless.parsing.paddleocr")


def _has_native_pdf_text(document_path: Path) -> bool:
    return bool(extract_pdf_text(document_path).strip())


class PaddleOCRVLParser:
    name = "PaddleOCR-VL Parser"
    version = __version__
    author = "paperless-paddleocr"
    url = "https://github.com/vroland/paperless_paddleocr"

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
        """Decline unavailable inputs and PDFs that Paperless can parse natively."""
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
        return True

    @property
    def requires_pdf_rendition(self) -> bool:
        return False

    def __init__(self, logging_group: object = None) -> None:
        settings.SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
        self._temporary_directory = tempfile.TemporaryDirectory(
            prefix="paperless-paddleocr-", dir=settings.SCRATCH_DIR
        )
        self._tempdir = Path(self._temporary_directory.name)
        self._logging_group = logging_group
        self._text = ""
        self._archive_path: Path | None = None

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self._temporary_directory.cleanup()

    def configure(self, context: ParserContext) -> None:
        pass

    def parse(
        self, document_path: Path, mime_type: str, *, produce_archive: bool = True
    ) -> None:
        """Extract text and optionally publish a validated searchable archive.

        Images are staged as PDFs so both modes use the same OCRmyPDF-rendered
        pages. Unexpected failures are exposed to Paperless as ``ParseError``.
        """
        if mime_type not in self.supported_mime_types() or not document_path.is_file():
            raise ParseError(
                "PaddleOCR-VL received an unsupported or missing source file"
            )
        try:
            self._text = ""
            self._archive_path = None
            if mime_type == "application/pdf" and _has_native_pdf_text(document_path):
                raise ParseError(
                    "PaddleOCR-VL does not process PDFs with existing text"
                )
            # OcrConfig imports Django models and requires the initialized app registry.
            from paperless.config import OcrConfig

            ocr_config = OcrConfig()
            staged_pdf, page_count = self._stage_source(
                document_path, mime_type, ocr_config.image_dpi
            )
            output_type = str(ocr_config.output_type)
            self._run_ocrmypdf(
                staged_pdf,
                page_count,
                produce_archive,
                output_type,
                str(ocr_config.color_conversion_strategy)
                if "pdfa" in output_type
                else None,
            )
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
        return self._archive_path

    def get_page_count(self, document_path: Path, mime_type: str) -> int | None:
        """Return PDF pages, TIFF frames, or one for other supported images."""
        if mime_type == "application/pdf":
            return get_page_count_for_pdf(document_path)
        if mime_type not in self.supported_mime_types():
            return None
        try:
            return image_page_count(document_path, mime_type)
        except (OSError, SourcePreparationError):
            return None

    def get_thumbnail(self, document_path: Path, mime_type: str) -> Path:
        """Create a WebP thumbnail, applying EXIF orientation to image inputs."""
        if mime_type == "application/pdf":
            return make_thumbnail_from_pdf(
                document_path, self._tempdir, self._logging_group
            )
        output = self._tempdir / "thumbnail.webp"
        with Image.open(document_path) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.thumbnail((500, 700))
            image.save(output, format="WEBP", quality=85, method=6)
        return output

    def extract_metadata(
        self, document_path: Path, mime_type: str
    ) -> list[MetadataEntry]:
        """Return static parser provenance without service configuration."""
        return [
            {
                "namespace": "urn:paperless-paddleocr:metadata",
                "prefix": "paddleocr",
                "key": "Parser",
                "value": f"PaddleOCR-VL Parser v{__version__}",
            }
        ]

    def _stage_source(
        self, document_path: Path, mime_type: str, image_dpi: int | None
    ) -> tuple[Path, int]:
        """Return a validated OCRmyPDF input PDF and its page count."""
        if mime_type == "application/pdf":
            page_count = get_page_count_for_pdf(document_path)
            if page_count is None or page_count <= 0:
                raise ValueError("source PDF has no readable pages")
            validate_staged_pdf(document_path, page_count)
            return document_path, page_count
        staged_pdf = self._tempdir / "source.pdf"
        page_count = stage_image_pdf(document_path, mime_type, staged_pdf, image_dpi)
        return staged_pdf, page_count

    def _run_ocrmypdf(
        self,
        staged_pdf: Path,
        page_count: int,
        produce_archive: bool,
        output_type: str,
        color_conversion_strategy: str | None,
    ) -> None:
        """Run Paddle recognition and apply the archive publication policy.

        Complete sidecar text survives rendering or geometry failures. An
        archive is published atomically only after every page reports safe
        geometry and the resulting PDF passes validation.
        """
        settings = PluginSettings.from_environment()
        status_dir = self._tempdir / "status"
        sidecar = self._tempdir / "archive.txt"
        partial_archive = self._tempdir / "archive.partial.pdf"
        output = partial_archive if produce_archive else Path(os.devnull)
        arguments: dict[str, Any] = {
            "plugins": ["paperless_paddleocr.archive.engine"],
            "ocr_engine": "paddleocr-vl",
            "pdf_renderer": "fpdf2",
            "output_type": output_type if produce_archive else "none",
            "sidecar": sidecar,
            "jobs": 1,
            "use_threads": True,
            "optimize": 0,
            "rotate_pages": False,
            "deskew": False,
            "clean": False,
            "clean_final": False,
            "remove_background": False,
            "remove_vectors": False,
            "tagged_pdf_mode": "ignore",
            "progress_bar": False,
            "paddle_settings": settings,
            "paddle_status_dir": str(status_dir),
        }
        if color_conversion_strategy is not None and produce_archive:
            arguments["color_conversion_strategy"] = color_conversion_strategy

        processing_error: Exception | None = None
        try:
            exit_code = ocrmypdf.ocr(staged_pdf, output, **arguments)
            if int(exit_code) != 0:
                raise RuntimeError(f"OCRmyPDF exited with status {int(exit_code)}")
        except Exception as exc:
            processing_error = exc

        try:
            geometry_safe = pages_have_safe_geometry(status_dir, page_count)
            self._text = validate_and_read_sidecar(sidecar, page_count)
        except ArchiveValidationError as exc:
            if processing_error is not None:
                raise processing_error from exc
            raise
        if not self._text:
            raise ValueError("PaddleOCR returned no usable text")
        if processing_error is not None:
            logger.warning(
                "PaddleOCR-VL archive generation failed after OCR completion"
            )
            partial_archive.unlink(missing_ok=True)
            return
        if not produce_archive:
            return
        if not geometry_safe:
            logger.warning("PaddleOCR-VL archive omitted because geometry was unsafe")
            partial_archive.unlink(missing_ok=True)
            return
        try:
            validate_archive(partial_archive, page_count)
            final_archive = self._tempdir / "archive.pdf"
            os.replace(partial_archive, final_archive)
            self._archive_path = final_archive
        except Exception:
            partial_archive.unlink(missing_ok=True)
            logger.warning(
                "PaddleOCR-VL archive validation failed after OCR completion"
            )
