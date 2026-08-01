from paperless.parsers import ParserProtocol

from paperless_paddleocr.parser import PaddleOCRVLParser


def test_parser_satisfies_the_real_paperless_protocol() -> None:
    # Avoid __init__: this structural check needs no Django settings or OCR service.
    parser = object.__new__(PaddleOCRVLParser)

    assert isinstance(parser, ParserProtocol)
