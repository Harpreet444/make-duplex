# SPDX-License-Identifier: GPL-3.0-or-later
# make-duplex — Harpreet444/make-duplex
#
# This file is part of make-duplex.
#
# make-duplex is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# make-duplex is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with make-duplex.  If not, see <https://www.gnu.org/licenses/>.

"""
tests/test_engine.py
====================
Pytest test-suite for make_duplex.engine.

Requirements
------------
* Python 3.11+
* pytest
* PyMuPDF (import fitz)
No PyQt6 dependency.
"""

from __future__ import annotations

import pathlib
from typing import Any

import fitz
import pytest

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
    insert_blank_pages,
    is_landscape,
    parse_page_range,
    render_sheet_preview,
)

# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------

PAGE_COUNT = 10


def make_opts(**kwargs: Any) -> DuplexOptions:
    """Return a DuplexOptions with sensible defaults, overridable via kwargs.

    Keyword arguments that are accepted by DuplexOptions may be passed as
    their raw Python values (e.g. ``nup=NUp.TWO``) or, for convenience,
    as the integer/string shorthand that the helper converts:

    * ``nup``   — ``NUp`` member or plain int ``1``/``2``/``4``
    * ``paper`` — ``PaperSize`` member (default ``PaperSize.A4``)
    """
    # Map plain ints to NUp enum members so callers can write nup=2.
    if "nup" in kwargs and isinstance(kwargs["nup"], int):
        kwargs["nup"] = NUp(kwargs["nup"])

    defaults: dict[str, Any] = {
        "nup": NUp.TWO,
        "paper": PaperSize.A4,
        "reverse_back": False,
        "flip_short_edge": False,
        "draw_border": False,  # keep tests fast / output clean
        "margin_pt": 10.0,
        "gap_pt": 4.0,
    }
    defaults.update(kwargs)
    return DuplexOptions(**defaults)


@pytest.fixture()
def sample_pdf(tmp_path: pathlib.Path) -> pathlib.Path:
    """Generate a 10-page PDF where each page shows its 1-based page number.

    Returns the Path to the written PDF file.
    """
    pdf_path = tmp_path / "sample.pdf"
    doc = fitz.open()
    for i in range(PAGE_COUNT):
        page: fitz.Page = doc.new_page(width=595, height=842)  # A4 portrait
        page.insert_text(
            fitz.Point(100, 400),
            f"Page {i + 1}",
            fontsize=48,
        )
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


# ---------------------------------------------------------------------------
# parse_page_range
# ---------------------------------------------------------------------------


def test_parse_page_range_all(sample_pdf: pathlib.Path) -> None:
    """Blank spec returns every page index (0 … N-1)."""
    result = parse_page_range("", PAGE_COUNT)
    assert result == list(range(PAGE_COUNT))


def test_parse_page_range_explicit(sample_pdf: pathlib.Path) -> None:
    """'1-3, 5' returns 0-based indices [0, 1, 2, 4]."""
    result = parse_page_range("1-3, 5", PAGE_COUNT)
    assert result == [0, 1, 2, 4]


def test_parse_page_range_invalid_token() -> None:
    """Non-numeric token raises ValueError."""
    with pytest.raises(ValueError):
        parse_page_range("abc", PAGE_COUNT)


def test_parse_page_range_out_of_range() -> None:
    """'1-999' on a 10-page doc raises ValueError."""
    with pytest.raises(ValueError):
        parse_page_range("1-999", PAGE_COUNT)


def test_parse_page_range_dedup_sort() -> None:
    """'3,1,2,1' returns sorted, deduplicated [0, 1, 2]."""
    result = parse_page_range("3,1,2,1", PAGE_COUNT)
    assert result == [0, 1, 2]


# ---------------------------------------------------------------------------
# filter_pages (Skip Pages)
# ---------------------------------------------------------------------------


def test_filter_pages_no_skip() -> None:
    """Blank skip spec keeps all included pages."""
    result = filter_pages("1-5", "", PAGE_COUNT)
    assert result == [0, 1, 2, 3, 4]


def test_filter_pages_comma_separated() -> None:
    """Exclude specific comma-separated pages."""
    # Exclude page 2 and page 4 (0-based 1 and 3)
    result = filter_pages("1-5", "2, 4", PAGE_COUNT)
    assert result == [0, 2, 4]


def test_filter_pages_range_skip() -> None:
    """Exclude a sub-range from all pages."""
    # From 10 pages, skip 3-8
    result = filter_pages("", "3-8", PAGE_COUNT)
    assert result == [0, 1, 8, 9]


def test_filter_pages_invalid_token() -> None:
    """Invalid token in skip spec raises ValueError."""
    with pytest.raises(ValueError):
        filter_pages("", "xyz", PAGE_COUNT)


def test_insert_blank_pages_after() -> None:
    """Blank page inserted after specified 1-based page numbers."""
    pages = [0, 1, 2, 3]  # pages 1, 2, 3, 4
    # Insert blank after page 2
    res = insert_blank_pages(pages, "2", PAGE_COUNT, position="after")
    assert res == [0, 1, -1, 2, 3]


def test_insert_blank_pages_before() -> None:
    """Blank page inserted before specified 1-based page numbers."""
    pages = [0, 1, 2, 3]
    # Insert blank before page 2
    res = insert_blank_pages(pages, "2", PAGE_COUNT, position="before")
    assert res == [0, -1, 1, 2, 3]


def test_insert_blank_pages_range_and_multiple() -> None:
    """Blank pages inserted for comma-separated list and ranges."""
    pages = [0, 1, 2, 3, 4]
    # Blank after pages 2 and 4
    res = insert_blank_pages(pages, "2, 4", PAGE_COUNT, position="after")
    assert res == [0, 1, -1, 2, 3, -1, 4]

    # Multiple blanks at same page
    res_multi = insert_blank_pages(pages, "2, 2", PAGE_COUNT, position="after")
    assert res_multi == [0, 1, -1, -1, 2, 3, 4]


def test_insert_blank_pages_skipped_page() -> None:
    """Blank page inserted at the position of a skipped page."""
    pages = [0, 1, 3, 4]  # page 3 (index 2) was skipped
    res_after = insert_blank_pages(pages, "3", PAGE_COUNT, position="after")
    assert res_after == [0, 1, -1, 3, 4]

    res_before = insert_blank_pages(pages, "3", PAGE_COUNT, position="before")
    assert res_before == [0, 1, -1, 3, 4]


def test_insert_blank_pages_validation() -> None:
    """Invalid token or out-of-range page raises ValueError."""
    pages = [0, 1, 2]
    with pytest.raises(ValueError, match="Unrecognised"):
        insert_blank_pages(pages, "bad", PAGE_COUNT)

    with pytest.raises(ValueError, match="out of range"):
        insert_blank_pages(pages, "99", PAGE_COUNT)


def test_filter_pages_with_blanks() -> None:
    """filter_pages correctly integrates include, skip, and blanks."""
    # From 5 pages, skip 3, blank after 2
    res = filter_pages("1-5", "3", 5, blank_spec="2", blank_pos="after")
    assert res == [0, 1, -1, 3, 4]


# ---------------------------------------------------------------------------
# compute_sheet_pairs
# ---------------------------------------------------------------------------


def test_compute_sheet_pairs_even_2up() -> None:
    """8 pages at 2-up → 2 sheets with correct front/back indices."""
    pages = list(range(8))
    opts = make_opts(nup=NUp.TWO)
    sheets = compute_sheet_pairs(pages, opts)

    # Expect exactly 2 sheets
    assert len(sheets) == 2

    s0: SheetPair = sheets[0]
    s1: SheetPair = sheets[1]

    # Sheet 0: front pages 0,1 — back pages 2,3
    assert s0.front_page_indices == [0, 1]
    assert s0.back_page_indices == [2, 3]

    # Sheet 1: front pages 4,5 — back pages 6,7
    assert s1.front_page_indices == [4, 5]
    assert s1.back_page_indices == [6, 7]


def test_compute_sheet_pairs_odd_incomplete() -> None:
    """5 pages at 2-up → last sheet has fewer back pages."""
    pages = list(range(5))
    opts = make_opts(nup=NUp.TWO)
    sheets = compute_sheet_pairs(pages, opts)

    # 5 pages / 4 (pages_per_sheet for 2-up) → 2 sheets
    assert len(sheets) == 2

    s0: SheetPair = sheets[0]
    s1: SheetPair = sheets[1]

    assert s0.front_page_indices == [0, 1]
    assert s0.back_page_indices == [2, 3]

    # Last sheet: only page 4 on front, nothing on back
    assert s1.front_page_indices == [4]
    assert s1.back_page_indices == []


def test_compute_sheet_pairs_4up() -> None:
    """8 pages at 4-up → 1 sheet with all 8 pages split correctly."""
    pages = list(range(8))
    opts = make_opts(nup=NUp.FOUR)
    sheets = compute_sheet_pairs(pages, opts)

    assert len(sheets) == 1

    s: SheetPair = sheets[0]
    # First 4 → front, last 4 → back
    assert s.front_page_indices == [0, 1, 2, 3]
    assert s.back_page_indices == [4, 5, 6, 7]


def test_compute_sheet_pairs_reverse_back() -> None:
    """reverse_back=True reverses the back-side ordering across sheets."""
    pages = list(range(8))
    opts_normal   = make_opts(nup=NUp.TWO, reverse_back=False)
    opts_reversed = make_opts(nup=NUp.TWO, reverse_back=True)

    normal   = compute_sheet_pairs(pages, opts_normal)
    reversed_ = compute_sheet_pairs(pages, opts_reversed)

    # Front sides must stay the same
    normal_fronts   = [s.front_page_indices for s in normal]
    reversed_fronts = [s.front_page_indices for s in reversed_]
    assert normal_fronts == reversed_fronts

    # Back sides must be reversed in sheet order
    normal_backs   = [s.back_page_indices for s in normal]
    reversed_backs = [s.back_page_indices for s in reversed_]
    assert reversed_backs == list(reversed(normal_backs))


# ---------------------------------------------------------------------------
# build_nup_page
# ---------------------------------------------------------------------------


def test_build_nup_page_1up(sample_pdf: pathlib.Path) -> None:
    """1-up output has exactly 1 page and matches source page dimensions."""
    src = fitz.open(str(sample_pdf))
    opts = make_opts(nup=NUp.ONE)
    out = build_nup_page(src, [0], opts)

    try:
        assert out.page_count == 1

        out_page = out[0]
        # 1-up is portrait; A4 portrait is ~595 × 842 pt
        assert out_page.rect.width < out_page.rect.height, (
            f"1-up should be portrait, got {out_page.rect.width}×{out_page.rect.height}"
        )
        # Width should be close to A4 width (595 pt)
        assert 580 <= out_page.rect.width <= 610
    finally:
        src.close()
        out.close()


def test_build_nup_page_2up_landscape(sample_pdf: pathlib.Path) -> None:
    """2-up page is landscape by default: width > height for A4."""
    src = fitz.open(str(sample_pdf))
    opts = make_opts(nup=NUp.TWO)
    out = build_nup_page(src, [0, 1], opts)

    try:
        assert out.page_count == 1
        page = out[0]
        assert page.rect.width > page.rect.height, (
            f"Expected landscape (width > height), got "
            f"{page.rect.width}×{page.rect.height}"
        )
    finally:
        src.close()
        out.close()


def test_build_nup_page_2up_portrait(sample_pdf: pathlib.Path) -> None:
    """2-up page with SheetOrientation.PORTRAIT is portrait: height > width for A4."""
    src = fitz.open(str(sample_pdf))
    opts = make_opts(nup=NUp.TWO, orientation=SheetOrientation.PORTRAIT)
    out = build_nup_page(src, [0, 1], opts)

    try:
        assert out.page_count == 1
        page = out[0]
        assert page.rect.height > page.rect.width, (
            f"Expected portrait (height > width), got "
            f"{page.rect.width}×{page.rect.height}"
        )
    finally:
        src.close()
        out.close()


def test_build_nup_page_4up_portrait(sample_pdf: pathlib.Path) -> None:
    """4-up page is portrait: height > width for A4."""
    src = fitz.open(str(sample_pdf))
    opts = make_opts(nup=NUp.FOUR)
    out = build_nup_page(src, [0, 1, 2, 3], opts)

    try:
        assert out.page_count == 1
        page = out[0]
        assert page.rect.height > page.rect.width, (
            f"Expected portrait (height > width), got "
            f"{page.rect.width}×{page.rect.height}"
        )
    finally:
        src.close()
        out.close()


def test_build_nup_page_rotate_180(sample_pdf: pathlib.Path) -> None:
    """rotate_180=True sets the output page rotation to 180."""
    src = fitz.open(str(sample_pdf))
    opts = make_opts(nup=NUp.TWO)
    out = build_nup_page(src, [0, 1], opts, rotate_180=True)

    try:
        assert out.page_count == 1
        page = out[0]
        assert page.rotation == 180
    finally:
        src.close()
        out.close()


# ---------------------------------------------------------------------------
# build_document
# ---------------------------------------------------------------------------


def test_build_document_front_page_count(sample_pdf: pathlib.Path) -> None:
    """Front document has the correct number of pages (one per sheet)."""
    src = fitz.open(str(sample_pdf))
    pages = list(range(8))
    opts = make_opts(nup=NUp.TWO)
    sheets = compute_sheet_pairs(pages, opts)

    front_doc = build_document(src, sheets, "front", opts)

    try:
        # 2 sheets → 2 front pages
        assert front_doc.page_count == 2
    finally:
        src.close()
        front_doc.close()


def test_build_document_back_page_count(sample_pdf: pathlib.Path) -> None:
    """Back document has the correct number of pages (one per sheet)."""
    src = fitz.open(str(sample_pdf))
    pages = list(range(8))
    opts = make_opts(nup=NUp.TWO)
    sheets = compute_sheet_pairs(pages, opts)

    back_doc = build_document(src, sheets, "back", opts)

    try:
        # 2 sheets, each with a back side → 2 back composite pages
        assert back_doc.page_count == 2
    finally:
        src.close()
        back_doc.close()


# ---------------------------------------------------------------------------
# render_sheet_preview
# ---------------------------------------------------------------------------


def test_render_sheet_preview_returns_png(sample_pdf: pathlib.Path) -> None:
    """render_sheet_preview returns bytes whose first 4 bytes are PNG magic."""
    src = fitz.open(str(sample_pdf))
    opts = make_opts(nup=NUp.TWO)
    pair = SheetPair(sheet_index=0, front_page_indices=[0, 1], back_page_indices=[2, 3])

    png_bytes = render_sheet_preview(src, pair, "front", opts, dpi=72)

    try:
        assert isinstance(png_bytes, bytes)
        assert png_bytes[:4] == b"\x89PNG", (
            f"Expected PNG magic bytes, got {png_bytes[:8]!r}"
        )
    finally:
        src.close()


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------


def test_full_pipeline_12_pages_2up(tmp_path: pathlib.Path) -> None:
    """12 pages at 2-up → 3 sheets, correct page counts in front and back docs."""
    # Build a 12-page source
    pdf_path = tmp_path / "twelve.pdf"
    doc = fitz.open()
    for i in range(12):
        p = doc.new_page(width=595, height=842)
        p.insert_text(fitz.Point(100, 400), f"Page {i + 1}", fontsize=36)
    doc.save(str(pdf_path))
    doc.close()

    src = fitz.open(str(pdf_path))
    opts = make_opts(nup=NUp.TWO)
    all_pages = parse_page_range("", 12)
    sheets = compute_sheet_pairs(all_pages, opts)

    # 12 pages / 4 pages_per_sheet = 3 sheets
    assert len(sheets) == 3, f"Expected 3 sheets, got {len(sheets)}"

    front_doc = build_document(src, sheets, "front", opts)
    back_doc  = build_document(src, sheets, "back",  opts)

    try:
        # Every sheet has 2 front and 2 back pages (12 divides evenly)
        assert front_doc.page_count == 3, (
            f"Expected 3 front pages, got {front_doc.page_count}"
        )
        assert back_doc.page_count == 3, (
            f"Expected 3 back pages, got {back_doc.page_count}"
        )
    finally:
        src.close()
        front_doc.close()
        back_doc.close()
