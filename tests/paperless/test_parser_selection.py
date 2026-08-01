import logging
from pathlib import Path

import pytest

from paperless_paddleocr.parser import PaddleOCRVLParser


def _write_pdf(path: Path, text: str, *, tagged: bool) -> None:
    escaped_text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    content = f"BT /F1 12 Tf 72 720 Td ({escaped_text}) Tj ET".encode()
    mark_info = b" /MarkInfo << /Marked true >>" if tagged else b""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R" + mark_info + b" >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream",
    ]
    pdf = b"%PDF-1.4\n"
    offsets: list[int] = []
    for object_number, object_data in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += f"{object_number} 0 obj\n".encode() + object_data + b"\nendobj\n"
    xref_offset = len(pdf)
    pdf += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    pdf += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    pdf += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    ).encode()
    path.write_bytes(pdf)


@pytest.mark.parametrize(
    ("text", "tagged", "expected_score"),
    [
        ("", False, 21),
        ("x" * 48, False, 21),
        ("x" * 49, False, None),
        ("short", True, None),
    ],
)
def test_score_delegates_native_pdfs_to_paperless(
    tmp_path, monkeypatch, caplog, text: str, tagged: bool, expected_score: int | None
) -> None:
    document = tmp_path / "invoice.pdf"
    _write_pdf(document, text, tagged=tagged)
    monkeypatch.setenv("PAPERLESS_PADDLEOCR_URL", "http://ocr.example:8088")
    caplog.set_level(logging.INFO, logger="paperless.parsing.paddleocr")

    assert (
        PaddleOCRVLParser.score("application/pdf", document.name, document)
        == expected_score
    )
    messages = [
        record.getMessage()
        for record in caplog.records
        if record.name == "paperless.parsing.paddleocr"
    ]
    expected_message = f"PaddleOCR-VL Parser declined native-text PDF: {document.name}"
    assert messages == ([expected_message] if expected_score is None else [])
