"""Convert ordered PaddleOCR layout blocks to searchable plain text."""

from __future__ import annotations

import math
import re
import unicodedata
from typing import Any, cast

from lxml import html

from .archive.models import NormalizedBlock, NormalizedPage, Point

IGNORED_LABELS = frozenset(
    {"header", "header_image", "footer", "footer_image", "number"}
)


def _normalize(value: str) -> str:
    """Normalize OCR text to NFC and canonical spaces and newlines."""
    value = (
        unicodedata.normalize("NFC", value).replace("\r\n", "\n").replace("\r", "\n")
    )
    value = re.sub(r"[ \t]+\n", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    value = re.sub(r"[ \t]{2,}", " ", value)
    return value.strip()


def _table_to_text(value: str) -> str:
    """Flatten HTML table cells into tab-separated rows when parseable."""
    if "<" not in value or ">" not in value:
        return value
    try:
        root = html.fromstring(value)
    except (ValueError, html.ParserError):
        return value
    # lxml-stubs cannot infer element-only results for these XPath expressions.
    for cell in cast(list[Any], root.xpath(".//th | .//td")):
        cell.tail = "\t" + (cell.tail or "")
    for row in cast(list[Any], root.xpath(".//tr")):
        row.tail = "\n" + (row.tail or "")
    return cast(Any, root).text_content()


def compose_document_text(page_texts: list[str]) -> str:
    """Use one canonical separator convention for index and sidecar text."""
    return "\n\n\f\n\n".join(page_texts).strip()


def normalize_layout_page(
    page: Any,
    page_number: int,
    width: int,
    height: int,
    dpi: float,
    dimensions_match: bool = True,
) -> NormalizedPage:
    """Normalize ordered Paddle blocks while retaining text with unsafe geometry.

    Headers, footers, and page numbers are omitted; tables are flattened and
    malformed blocks skipped. Geometry is safe only when dimensions match and
    every retained block has a valid bounding box.
    """
    raw_blocks = page.pruned_result.get("parsing_res_list", [])
    normalized_blocks: list[NormalizedBlock] = []
    if isinstance(raw_blocks, list):
        for raw_block in raw_blocks:
            if not isinstance(raw_block, dict):
                continue
            label = str(raw_block.get("block_label") or "")
            if label in IGNORED_LABELS:
                continue
            content = raw_block.get("block_content")
            if not isinstance(content, str):
                continue
            if label == "table":
                content = _table_to_text(content)
            text = _normalize(content)
            if not text:
                continue
            bbox = _valid_bbox(raw_block.get("block_bbox"), width, height)
            polygon = _valid_polygon(
                raw_block.get("block_polygon_points"), width, height
            )
            normalized_blocks.append(
                NormalizedBlock(
                    text=text,
                    bbox=bbox,
                    polygon=polygon if bbox is not None else None,
                )
            )
    page_text = "\n\n".join(block.text for block in normalized_blocks)
    return NormalizedPage(
        page_number=page_number,
        width=width,
        height=height,
        dpi=dpi,
        blocks=tuple(normalized_blocks),
        text=page_text,
        geometry_safe=dimensions_match
        and all(block.bbox is not None for block in normalized_blocks),
    )


def _valid_bbox(
    raw_bbox: object, width: int, height: int, tolerance: float = 2.0
) -> tuple[float, float, float, float] | None:
    """Validate a bounding box and clip coordinates within the tolerance."""
    if not isinstance(raw_bbox, list) or len(raw_bbox) != 4:
        return None
    try:
        left, top, right, bottom = (float(value) for value in raw_bbox)
    except (TypeError, ValueError):
        return None
    values = (left, top, right, bottom)
    if (
        not all(math.isfinite(value) for value in values)
        or left >= right
        or top >= bottom
    ):
        return None
    if (
        left < -tolerance
        or top < -tolerance
        or right > width + tolerance
        or bottom > height + tolerance
    ):
        return None
    return max(left, 0), max(top, 0), min(right, width), min(bottom, height)


def _valid_polygon(
    raw_polygon: object, width: int, height: int, tolerance: float = 2.0
) -> tuple[Point, Point, Point, Point] | None:
    """Validate and canonically order a nondegenerate four-point polygon."""
    if not isinstance(raw_polygon, list) or len(raw_polygon) != 4:
        return None
    points: list[Point] = []
    try:
        for raw_point in raw_polygon:
            if not isinstance(raw_point, list) or len(raw_point) != 2:
                return None
            point = Point(float(raw_point[0]), float(raw_point[1]))
            if not (
                math.isfinite(point.x)
                and math.isfinite(point.y)
                and -tolerance <= point.x <= width + tolerance
                and -tolerance <= point.y <= height + tolerance
            ):
                return None
            points.append(point)
    except (TypeError, ValueError):
        return None
    center_x = sum(point.x for point in points) / 4
    center_y = sum(point.y for point in points) / 4
    if len({(point.x, point.y) for point in points}) != 4:
        return None
    ordered = sorted(
        points, key=lambda point: math.atan2(point.y - center_y, point.x - center_x)
    )
    start = min(range(4), key=lambda index: (ordered[index].y, ordered[index].x))
    ordered = ordered[start:] + ordered[:start]
    area = sum(
        ordered[index].x * ordered[(index + 1) % 4].y
        - ordered[(index + 1) % 4].x * ordered[index].y
        for index in range(4)
    )
    if abs(area) < 0.01:
        return None
    return cast(tuple[Point, Point, Point, Point], tuple(ordered))
