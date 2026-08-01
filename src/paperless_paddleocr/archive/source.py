"""Prepare image sources as predictable PDF input for OCRmyPDF."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image


class SourcePreparationError(ValueError):
    """The source cannot be preserved safely for archive generation."""


_MIRRORED_ORIENTATIONS = {2, 4, 5, 7}


def image_page_count(document_path: Path, mime_type: str) -> int:
    """Return the TIFF frame count or one for another supported image."""
    if mime_type != "image/tiff":
        return 1
    with Image.open(document_path) as image:
        return image.n_frames


def stage_image_pdf(
    document_path: Path,
    mime_type: str,
    output_path: Path,
    image_dpi: int | None,
) -> int:
    """Wrap validated image frames in an OCRmyPDF-ready PDF.

    The conversion preserves valid EXIF rotation, optionally applies a fixed
    DPI, and verifies the generated page count and page geometry.
    """
    if mime_type not in {"image/jpeg", "image/png", "image/tiff"}:
        raise SourcePreparationError(f"unsupported image MIME type: {mime_type}")

    expected_pages = _inspect_image(document_path)
    try:
        import img2pdf  # type: ignore[import-untyped]
    except ImportError as exc:  # pragma: no cover - deployment dependency
        raise SourcePreparationError(
            "img2pdf is required for archive generation"
        ) from exc

    kwargs: dict[str, object] = {
        "engine": img2pdf.Engine.pikepdf,
        "rotation": img2pdf.Rotation.ifvalid,
    }
    if image_dpi:
        kwargs["layout_fun"] = img2pdf.get_fixed_dpi_layout_fun((image_dpi, image_dpi))
    try:
        output_path.write_bytes(img2pdf.convert(str(document_path), **kwargs))
    except Exception as exc:
        raise SourcePreparationError("could not wrap image source as PDF") from exc

    validate_staged_pdf(output_path, expected_pages)
    return expected_pages


def _inspect_image(document_path: Path) -> int:
    """Validate every frame and return the source image frame count.

    Mirrored EXIF transforms and image modes that cannot be safely preserved
    are rejected before PDF staging.
    """
    try:
        with Image.open(document_path) as image:
            frames = getattr(image, "n_frames", 1)
            for frame_number in range(frames):
                image.seek(frame_number)
                orientation = image.getexif().get(274, 1)
                if orientation in _MIRRORED_ORIENTATIONS:
                    raise SourcePreparationError(
                        f"mirrored EXIF orientation on image frame {frame_number}"
                    )
                if image.width <= 0 or image.height <= 0:
                    raise SourcePreparationError(
                        f"invalid dimensions on image frame {frame_number}"
                    )
                if image.mode in {"I;16", "I;16B", "I;16L", "F"}:
                    raise SourcePreparationError(
                        f"unsupported bit depth on image frame {frame_number}"
                    )
            return frames
    except SourcePreparationError:
        raise
    except Exception as exc:
        raise SourcePreparationError("could not inspect image source") from exc


def validate_staged_pdf(document_path: Path, expected_pages: int) -> None:
    """Require the expected page count and valid MediaBoxes in a readable PDF."""
    try:
        import pikepdf

        with pikepdf.Pdf.open(document_path) as pdf:
            if len(pdf.pages) != expected_pages:
                raise SourcePreparationError("staged PDF page count changed")
            for page in pdf.pages:
                media_box = page.mediabox
                width = float(media_box[2]) - float(media_box[0])
                height = float(media_box[3]) - float(media_box[1])
                if (
                    not (math.isfinite(width) and math.isfinite(height))
                    or min(width, height) <= 0
                ):
                    raise SourcePreparationError("staged PDF has an invalid MediaBox")
    except SourcePreparationError:
        raise
    except Exception as exc:
        raise SourcePreparationError("staged PDF is unreadable") from exc
