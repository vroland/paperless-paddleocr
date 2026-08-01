"""Validate transient OCR status records, sidecars, and archive PDFs."""

from __future__ import annotations

import json
import math
import os
import tempfile
from pathlib import Path

from ..text import compose_document_text


class ArchiveValidationError(ValueError):
    """An archive artifact is incomplete or unsafe to publish."""


def write_page_status(status_dir: Path, page_number: int, geometry_safe: bool) -> None:
    """Atomically record geometry safety for one completed OCR page."""
    status_dir.mkdir(parents=True, exist_ok=True)
    target = status_dir / f"{page_number:06d}.json"
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=status_dir, delete=False
    ) as temporary:
        json.dump(geometry_safe, temporary)
        temporary.write("\n")
        temporary_path = Path(temporary.name)
    os.replace(temporary_path, target)


def pages_have_safe_geometry(status_dir: Path, expected_pages: int) -> bool:
    """Validate exact page completion and report aggregate geometry safety.

    Missing, extra, or malformed records mean OCR did not complete reliably
    and raise ``ArchiveValidationError`` rather than merely returning false.
    """
    geometry_safe = True
    for page_number in range(expected_pages):
        path = status_dir / f"{page_number:06d}.json"
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ArchiveValidationError("OCR did not complete every page") from exc
        if not isinstance(value, bool):
            raise ArchiveValidationError("invalid OCR page completion status")
        geometry_safe = geometry_safe and value
    if len(list(status_dir.glob("*.json"))) != expected_pages:
        raise ArchiveValidationError("unexpected OCR page completion status")
    return geometry_safe


def validate_and_read_sidecar(sidecar_path: Path, expected_pages: int) -> str:
    """Read complete sidecar pages and apply the canonical page separator."""
    try:
        sidecar = sidecar_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ArchiveValidationError("OCR sidecar is unavailable") from exc
    if "[OCR skipped on page" in sidecar:
        raise ArchiveValidationError("OCR sidecar contains skipped pages")
    pages = sidecar.split("\f")
    if len(pages) != expected_pages:
        raise ArchiveValidationError("OCR sidecar page count is incomplete")
    return compose_document_text(pages)


def validate_archive(document_path: Path, expected_pages: int) -> None:
    """Require a nonempty PDF with unchanged page count and valid MediaBoxes."""
    if not document_path.is_file() or document_path.stat().st_size == 0:
        raise ArchiveValidationError("OCRmyPDF did not produce an archive")
    try:
        import pikepdf

        with pikepdf.Pdf.open(document_path) as pdf:
            if len(pdf.pages) != expected_pages:
                raise ArchiveValidationError("archive page count changed")
            for page in pdf.pages:
                media_box = page.mediabox
                width = float(media_box[2]) - float(media_box[0])
                height = float(media_box[3]) - float(media_box[1])
                if (
                    not (math.isfinite(width) and math.isfinite(height))
                    or min(width, height) <= 0
                ):
                    raise ArchiveValidationError("archive has an invalid MediaBox")
    except ArchiveValidationError:
        raise
    except Exception as exc:
        raise ArchiveValidationError("archive PDF is unreadable") from exc
