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
    file_type: Literal[1] = Field(
        default=1, description="Image input for one OCRmyPDF-rendered page."
    )
    use_doc_orientation_classify: Literal[False] = Field(
        default=False,
        description=(
            "OCRmyPDF supplies the page orientation, so classification is disabled."
        ),
    )
    use_doc_unwarping: Literal[False] = Field(
        default=False,
        description="OCRmyPDF geometry must be preserved, so unwarping is disabled.",
    )
    use_layout_detection: Literal[True] = Field(
        default=True, description="Layout detection is required."
    )
    use_chart_recognition: bool = Field(
        description="Whether the service should run chart recognition."
    )
    use_seal_recognition: bool = Field(
        description="Whether the service should run seal recognition."
    )
    format_block_content: Literal[False] = Field(
        default=False,
        description="Whether the service should format the content of layout blocks.",
    )
    prettify_markdown: Literal[False] = Field(
        default=False,
        description="Whether the service should prettify markdown output.",
    )
    return_markdown_images: Literal[False] = Field(
        default=False,
        description=(
            "Whether the service should return images referenced by markdown output."
        ),
    )
    visualize: Literal[False] = Field(
        default=False, description="Whether the service should produce visualizations."
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


class InferResult(PaddleOCRModel):
    layout_parsing_results: list[LayoutParsingResult] = Field(
        description="Layout-parsing result for each input page."
    )
    data_info: ImageInfo = Field(
        description="Rendered-page metadata supplied by the service."
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
