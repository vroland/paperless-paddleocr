"""Convert ordered PaddleOCR layout blocks to searchable plain text."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from lxml import html

IGNORED_LABELS = frozenset({"header", "header_image", "footer", "footer_image", "number"})


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFC", value).replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"[ \t]+\n", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    value = re.sub(r"[ \t]{2,}", " ", value)
    return value.strip()


def _table_to_text(value: str) -> str:
    if "<" not in value or ">" not in value:
        return value
    try:
        root = html.fromstring(value)
    except (ValueError, html.ParserError):
        return value
    for cell in root.xpath(".//th | .//td"):
        cell.tail = "\t" + (cell.tail or "")
    for row in root.xpath(".//tr"):
        row.tail = "\n" + (row.tail or "")
    return root.text_content()


def extract_plain_text(response: dict[str, Any]) -> str:
    """Preserve the page and block order supplied by PaddleOCR."""
    pages = response.get("result", {}).get("layoutParsingResults", [])
    page_texts: list[str] = []
    for page in pages:
        if not isinstance(page, dict):
            continue
        blocks = page.get("prunedResult", {}).get("parsing_res_list", [])
        if not isinstance(blocks, list):
            continue
        rendered: list[str] = []
        for block in blocks:
            if not isinstance(block, dict):
                continue
            label = str(block.get("block_label") or "")
            if label in IGNORED_LABELS:
                continue
            content = block.get("block_content")
            if not isinstance(content, str):
                continue
            if label == "table":
                content = _table_to_text(content)
            content = _normalize(content)
            if content:
                rendered.append(content)
        if rendered:
            page_texts.append("\n\n".join(rendered))
    return "\n\n\f\n\n".join(page_texts).strip()
