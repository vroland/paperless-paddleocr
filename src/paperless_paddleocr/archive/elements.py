"""Project coarse Paddle block geometry into OCRmyPDF elements."""

from __future__ import annotations

import math

from ocrmypdf.models.ocr_element import BoundingBox, OcrClass, OcrElement

from .models import NormalizedBlock, NormalizedPage, Point


def build_page_element(page: NormalizedPage) -> OcrElement:
    """Project coarse block geometry into an OCRmyPDF element tree.

    Unsafe pages intentionally produce an empty page tree. On safe pages each
    block is divided into line slots and each complete line becomes one word,
    reflecting Paddle's lack of documented line and word geometry.
    """
    root = OcrElement(
        ocr_class=OcrClass.PAGE,
        bbox=BoundingBox(0, 0, page.width, page.height),
        dpi=page.dpi,
        page_number=page.page_number,
    )
    if not page.geometry_safe:
        return root
    for block in page.blocks:
        assert block.bbox is not None
        paragraph = OcrElement(
            ocr_class=OcrClass.PARAGRAPH, bbox=_bounding_box(block.bbox)
        )
        lines = block.text.split("\n")
        for slot_index, line in enumerate(lines):
            if not line:
                continue
            bbox = _line_bbox(block, slot_index, len(lines))
            angle = _line_angle(block.polygon)
            line_element = OcrElement(
                ocr_class=OcrClass.LINE,
                bbox=_bounding_box(bbox),
                textangle=angle,
            )
            line_element.children.append(
                OcrElement(
                    ocr_class=OcrClass.WORD,
                    bbox=_bounding_box(bbox),
                    text=line,
                )
            )
            paragraph.children.append(line_element)
        root.children.append(paragraph)
    return root


def _bounding_box(bbox: tuple[float, float, float, float]) -> BoundingBox:
    return BoundingBox(*bbox)


def _line_bbox(
    block: NormalizedBlock, slot_index: int, slot_count: int
) -> tuple[float, float, float, float]:
    """Approximate a line slot by splitting or interpolating block geometry."""
    assert block.bbox is not None
    left, top, right, bottom = block.bbox
    if block.polygon is None:
        height = (bottom - top) / slot_count
        return left, top + height * slot_index, right, top + height * (slot_index + 1)
    points = block.polygon
    top_left, top_right, bottom_right, bottom_left = points
    start = slot_index / slot_count
    end = (slot_index + 1) / slot_count
    edges = (
        _interpolate(top_left, bottom_left, start),
        _interpolate(top_right, bottom_right, start),
        _interpolate(top_right, bottom_right, end),
        _interpolate(top_left, bottom_left, end),
    )
    return (
        min(point.x for point in edges),
        min(point.y for point in edges),
        max(point.x for point in edges),
        max(point.y for point in edges),
    )


def _interpolate(start: Point, end: Point, fraction: float) -> Point:
    return Point(
        start.x + (end.x - start.x) * fraction,
        start.y + (end.y - start.y) * fraction,
    )


def _line_angle(polygon: tuple[Point, Point, Point, Point] | None) -> float:
    """Convert the polygon top edge from image space to OCRmyPDF page angle."""
    if polygon is None:
        return 0.0
    start, end = polygon[0], polygon[1]
    # Image y grows down; OcrElement angles are counter-clockwise in page space.
    angle = -math.degrees(math.atan2(end.y - start.y, end.x - start.x))
    return angle if math.isfinite(angle) else 0.0
