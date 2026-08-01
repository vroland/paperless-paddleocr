from paperless_paddleocr.text import extract_plain_text


def test_extract_plain_text_preserves_page_and_block_order() -> None:
    response = {
        "result": {
            "layoutParsingResults": [
                {
                    "prunedResult": {
                        "parsing_res_list": [
                            {"block_label": "doc_title", "block_content": "Invoice"},
                            {"block_label": "footer", "block_content": "Page 1"},
                            {"block_label": "text", "block_content": "Supplier: Example GmbH"},
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
        }
    }

    assert extract_plain_text(response) == (
        "Invoice\n\nSupplier: Example GmbH\n\n\f\n\nTotal: EUR 120.00"
    )


def test_extract_plain_text_flattens_html_tables() -> None:
    response = {
        "result": {
            "layoutParsingResults": [
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
        }
    }

    assert extract_plain_text(response) == "Item\tTotal"
