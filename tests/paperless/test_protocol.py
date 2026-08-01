from pathlib import Path
from types import SimpleNamespace

from paperless.parsers import ParserProtocol

from paperless_paddleocr.parser import PaddleOCRVLParser


def test_parser_satisfies_the_real_paperless_protocol() -> None:
    # Avoid __init__: this structural check needs no Django settings or OCR service.
    parser = object.__new__(PaddleOCRVLParser)

    assert isinstance(parser, ParserProtocol)


def test_parser_temporary_directory_follows_context_lifecycle(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        "paperless_paddleocr.parser.settings",
        SimpleNamespace(SCRATCH_DIR=tmp_path),
    )
    parser = PaddleOCRVLParser()
    temporary_directory = parser._tempdir

    assert temporary_directory.is_dir()
    with parser:
        assert temporary_directory.is_dir()
        assert temporary_directory.parent == tmp_path

    assert not temporary_directory.exists()
