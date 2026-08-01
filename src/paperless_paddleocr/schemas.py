"""Pydantic models for PaddleOCR-VL's layout-parsing API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class PaddleOCRModel(BaseModel):
    """Use the API's camelCase names while accepting future response fields."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        extra="ignore",
        populate_by_name=True,
        strict=True,
    )


class InferRequest(PaddleOCRModel):
    file: str = Field(
        description="Source document supplied to the layout-parsing endpoint."
    )
    file_type: Literal[0, 1] = Field(
        description="File-type selector: 0 for PDF and 1 for image."
    )
    use_doc_orientation_classify: bool = Field(
        description=(
            "Whether the service should run document-orientation classification."
        )
    )
    use_doc_unwarping: bool = Field(
        description="Whether the service should run document unwarping."
    )
    use_layout_detection: bool = Field(
        description="Whether the service should run layout detection."
    )
    use_chart_recognition: bool = Field(
        description="Whether the service should run chart recognition."
    )
    use_seal_recognition: bool = Field(
        description="Whether the service should run seal recognition."
    )
    format_block_content: bool = Field(
        description="Whether the service should format the content of layout blocks."
    )
    prettify_markdown: bool = Field(
        description="Whether the service should prettify markdown output."
    )
    return_markdown_images: bool = Field(
        description=(
            "Whether the service should return images referenced by markdown output."
        )
    )
    visualize: bool = Field(
        description="Whether the service should produce visualizations."
    )


class MarkdownData(PaddleOCRModel):
    text: str = Field(description="Markdown text for one parsed page.")
    images: dict[str, str] | None = Field(
        default=None,
        description="Optional mapping of markdown image identifiers to their content.",
    )


class LayoutParsingResult(PaddleOCRModel):
    # PaddleOCR's OpenAPI schema deliberately leaves this object open-ended.
    pruned_result: dict[str, Any] = Field(
        description=(
            "Unstructured, pruned per-page parsing result returned by the service."
        )
    )
    markdown: MarkdownData = Field(
        description="Markdown representation of the parsed page."
    )


class ImageInfo(PaddleOCRModel):
    width: int = Field(description="Reported image width.")
    height: int = Field(description="Reported image height.")
    type: Literal["image"] = Field(
        default="image", description="Always `image` for image input."
    )


class PDFPageInfo(PaddleOCRModel):
    width: int = Field(description="Reported page width.")
    height: int = Field(description="Reported page height.")


class PDFInfo(PaddleOCRModel):
    num_pages: int = Field(description="Number of pages in the PDF.")
    pages: list[PDFPageInfo] = Field(description="Dimensions of each PDF page.")
    type: Literal["pdf"] = Field(
        default="pdf", description="Always `pdf` for PDF input."
    )


class TIFFInfo(PaddleOCRModel):
    num_pages: int = Field(description="Number of pages in the TIFF.")
    pages: list[PDFPageInfo] = Field(description="Dimensions of each TIFF page.")
    type: Literal["tiff"] = Field(
        default="tiff", description="Always `tiff` for TIFF input."
    )


class InferResult(PaddleOCRModel):
    layout_parsing_results: list[LayoutParsingResult] = Field(
        description="Layout-parsing result for each input page."
    )
    data_info: ImageInfo | PDFInfo | TIFFInfo = Field(
        description="Input-document metadata supplied by the service."
    )


class InferResponse(PaddleOCRModel):
    log_id: str = Field(
        description="Service log identifier for this inference request."
    )
    result: InferResult = Field(description="Successful layout-parsing result.")
    error_code: Literal[0] = Field(
        default=0,
        description="Successful responses have the fixed error code 0.",
    )
    error_msg: Literal["Success"] = Field(
        default="Success",
        description="Successful responses have the fixed message `Success`.",
    )


class ErrorResponse(PaddleOCRModel):
    log_id: str = Field(description="Service log identifier for the failed request.")
    error_code: int = Field(description="Service-defined error code.")
    error_msg: str = Field(description="Service-defined error message.")
