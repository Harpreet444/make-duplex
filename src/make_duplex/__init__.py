# SPDX-License-Identifier: GPL-3.0-or-later
# make-duplex — Harpreet444/make-duplex
"""make-duplex: correct N-up manual duplex printing for single-sided printers."""

from make_duplex.engine import (
    DuplexOptions,
    NUp,
    PaperSize,
    SheetOrientation,
    SheetPair,
    build_document,
    build_nup_page,
    compute_sheet_pairs,
    filter_pages,
    is_landscape,
    parse_page_range,
    render_sheet_preview,
)

__version__ = "0.1.0"
__author__ = "Harpreet444"
__license__ = "GPL-3.0-or-later"

__all__ = [
    "DuplexOptions",
    "NUp",
    "PaperSize",
    "SheetOrientation",
    "SheetPair",
    "build_document",
    "build_nup_page",
    "compute_sheet_pairs",
    "filter_pages",
    "is_landscape",
    "parse_page_range",
    "render_sheet_preview",
]
