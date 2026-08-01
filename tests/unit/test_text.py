from paperless_paddleocr.schemas import LayoutParsingResult
from paperless_paddleocr.text import compose_document_text, normalize_layout_page


def _page(blocks: list[dict[str, object]]) -> LayoutParsingResult:
    return LayoutParsingResult.model_validate(
        {"prunedResult": {"parsing_res_list": blocks}, "markdown": {"text": ""}}
    )


def test_normalized_text_preserves_page_and_block_order() -> None:
    first_page = _page(
        [
            {"block_label": "doc_title", "block_content": "Invoice"},
            {"block_label": "footer", "block_content": "Page 1"},
            {"block_label": "text", "block_content": "Supplier: Example GmbH"},
        ]
    )
    second_page = _page([{"block_label": "text", "block_content": "Total: EUR 120.00"}])

    assert compose_document_text(
        [
            normalize_layout_page(first_page, 0, 1, 1, 1.0).text,
            normalize_layout_page(second_page, 1, 1, 1, 1.0).text,
        ]
    ) == ("Invoice\n\nPage 1\n\nSupplier: Example GmbH\n\n\f\n\nTotal: EUR 120.00")


def test_normalized_text_can_exclude_headers_and_footers() -> None:
    page = _page(
        [
            {"block_label": "header", "block_content": "ACME Corp"},
            {"block_label": "text", "block_content": "Invoice total"},
            {"block_label": "footer", "block_content": "Terms apply"},
            {"block_label": "number", "block_content": "Page 1"},
        ]
    )

    assert (
        normalize_layout_page(page, 0, 1, 1, 1.0, include_headers_footers=False).text
        == "Invoice total"
    )


def test_normalized_text_flattens_html_tables() -> None:
    page = _page(
        [
            {
                "block_label": "table",
                "block_content": "<table><tr><td>Item</td><td>Total</td></tr></table>",
            }
        ]
    )

    assert normalize_layout_page(page, 0, 1, 1, 1.0).text == "Item\tTotal"
