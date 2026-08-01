from pathlib import Path

from paperless_paddleocr.parser import PaddleOCRVLParser


def test_parser_metadata_identifies_the_parser_without_service_details() -> None:
    parser = object.__new__(PaddleOCRVLParser)

    assert parser.extract_metadata(Path("document.pdf"), "application/pdf") == [
        {
            "namespace": "urn:paperless-paddleocr:metadata",
            "prefix": "paddleocr",
            "key": "Parser",
            "value": "PaddleOCR-VL Parser v0.1.0",
        }
    ]
