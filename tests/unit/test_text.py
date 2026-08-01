from paperless_paddleocr.schemas import InferResult
from paperless_paddleocr.text import extract_plain_text


def _result(pages: list[dict[str, object]]) -> InferResult:
    return InferResult.model_validate(
        {
            "layoutParsingResults": [
                {**page, "markdown": {"text": ""}} for page in pages
            ],
            "dataInfo": {"width": 1, "height": 1},
        }
    )


def test_extract_plain_text_preserves_page_and_block_order() -> None:
    result = _result(
        [
            {
                "prunedResult": {
                    "parsing_res_list": [
                        {"block_label": "doc_title", "block_content": "Invoice"},
                        {"block_label": "footer", "block_content": "Page 1"},
                        {
                            "block_label": "text",
                            "block_content": "Supplier: Example GmbH",
                        },
                    ]
                }
            },
            {
                "prunedResult": {
                    "parsing_res_list": [
                        {"block_label": "text", "block_content": "Total: EUR 120.00"}
                    ]
                }
            },
        ]
    )

    assert extract_plain_text(result) == (
        "Invoice\n\nSupplier: Example GmbH\n\n\f\n\nTotal: EUR 120.00"
    )


def test_extract_plain_text_flattens_html_tables() -> None:
    result = _result(
        [
            {
                "prunedResult": {
                    "parsing_res_list": [
                        {
                            "block_label": "table",
                            "block_content": (
                                "<table><tr><td>Item</td><td>Total</td></tr></table>"
                            ),
                        }
                    ]
                }
            }
        ]
    )

    assert extract_plain_text(result) == "Item\tTotal"
