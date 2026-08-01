"""Typed transient representation of normalized Paddle layout output."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class NormalizedBlock:
    text: str
    bbox: tuple[float, float, float, float] | None
    polygon: tuple[Point, Point, Point, Point] | None


@dataclass(frozen=True, slots=True)
class NormalizedPage:
    page_number: int
    width: int
    height: int
    dpi: float
    blocks: tuple[NormalizedBlock, ...]
    text: str
    geometry_safe: bool
