"""Explicit OCRmyPDF engine that delegates recognition to PaddleOCR-VL."""

from __future__ import annotations

import math
from pathlib import Path

from ocrmypdf import hookimpl
from ocrmypdf._options import OcrOptions
from ocrmypdf.models.ocr_element import OcrElement
from ocrmypdf.pluginspec import OcrEngine, OrientationConfidence
from PIL import Image

from .. import __version__
from ..client import PaddleOCRClient, PaddleOCRProtocolError
from ..config import PluginSettings
from ..text import normalize_layout_page
from .elements import build_page_element
from .validate import write_page_status


class PaddleOcrVLEngine(OcrEngine):
    @staticmethod
    def version() -> str:
        return __version__

    @staticmethod
    def creator_tag(options: OcrOptions) -> str:
        return f"PaddleOCR-VL paperless-paddleocr {__version__}"

    def __str__(self) -> str:
        return f"PaddleOCR-VL {__version__}"

    @staticmethod
    def languages(options: OcrOptions) -> set[str]:
        languages = options.languages
        return set(languages or ())

    @staticmethod
    def get_orientation(input_file: Path, options: OcrOptions) -> OrientationConfidence:
        """Disable OCRmyPDF rotation because page geometry must remain unchanged."""
        return OrientationConfidence(0, 0.0)

    @staticmethod
    def generate_hocr(
        input_file: Path, output_hocr: Path, output_text: Path, options: OcrOptions
    ) -> None:
        raise NotImplementedError("PaddleOCR-VL requires OCRmyPDF's fpdf2 renderer")

    @staticmethod
    def generate_pdf(
        input_file: Path, output_pdf: Path, output_text: Path, options: OcrOptions
    ) -> None:
        raise NotImplementedError("PaddleOCR-VL requires OCRmyPDF's fpdf2 renderer")

    @staticmethod
    def supports_generate_ocr() -> bool:
        return True

    @staticmethod
    def generate_ocr(
        input_file: Path, options: OcrOptions, page_number: int = 0
    ) -> tuple[OcrElement, str]:
        """Recognize one OCRmyPDF-rendered page and record geometry safety.

        The service must return exactly one image result whose dimensions match
        the rendered page. Text remains available independently of the element
        tree when the reported geometry is unsafe.
        """
        width, height, dpi = _image_details(input_file)
        settings = getattr(options, "paddle_settings", None)
        status_dir = getattr(options, "paddle_status_dir", None)
        if not isinstance(settings, PluginSettings) or not isinstance(status_dir, str):
            raise PaddleOCRProtocolError("archive OCR engine was not configured")
        with PaddleOCRClient(settings) as client:
            result = client.extract_page(input_file)
        if len(result.layout_parsing_results) != 1:
            raise PaddleOCRProtocolError(
                "PaddleOCR page response must contain one image"
            )
        dimensions_match = (
            result.data_info.width == width and result.data_info.height == height
        )
        raw_page = result.layout_parsing_results[0]
        pruned_width = raw_page.pruned_result.get("width")
        pruned_height = raw_page.pruned_result.get("height")
        if pruned_width is not None or pruned_height is not None:
            dimensions_match = dimensions_match and (
                pruned_width == width and pruned_height == height
            )
        page = normalize_layout_page(
            raw_page,
            page_number,
            width,
            height,
            dpi,
            dimensions_match,
            settings.include_headers_footers,
        )
        write_page_status(Path(status_dir), page_number, page.geometry_safe)
        return build_page_element(page), page.text


def _image_details(input_file: Path) -> tuple[int, int, float]:
    """Read positive image dimensions and finite horizontal DPI."""
    with Image.open(input_file) as image:
        dpi_value = image.info.get("dpi")
        dpi = (
            float(dpi_value[0])
            if isinstance(dpi_value, tuple)
            else float(dpi_value or 0)
        )
        if image.width <= 0 or image.height <= 0 or not math.isfinite(dpi) or dpi <= 0:
            raise PaddleOCRProtocolError(
                "OCRmyPDF supplied an image without usable DPI"
            )
        return image.width, image.height, dpi


@hookimpl
def get_ocr_engine(options: OcrOptions | None) -> PaddleOcrVLEngine | None:
    """Provide this engine only when OCRmyPDF selected ``paddleocr-vl``."""
    if options is None or options.ocr_engine != "paddleocr-vl":
        return None
    return PaddleOcrVLEngine()
