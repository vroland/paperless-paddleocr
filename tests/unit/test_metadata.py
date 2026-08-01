from paperless_paddleocr.metadata import parser_metadata


def test_parser_metadata_identifies_the_parser_without_service_details() -> None:
    assert parser_metadata() == [
        {
            "namespace": "urn:paperless-paddleocr:metadata",
            "prefix": "paddleocr",
            "key": "Parser",
            "value": "PaddleOCR-VL Parser v0.1.0",
        }
    ]
