# engine.py — make-duplex
#
# Copyright (C) 2024  Harpreet444 <https://github.com/Harpreet444/make-duplex>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
engine.py
~~~~~~~~~

Pure-Python 3.11+ duplex-printing engine for make-duplex.

No Qt imports — only the standard library and PyMuPDF (fitz).

Responsibilities
----------------
* Parse human-readable page-range strings.
* Group selected pages into physical *sheet pairs* (front / back).
* Tile source pages into N-up output pages (1-up, 2-up, 4-up).
* Assemble multi-page front or back documents ready for printing.
* Render per-sheet PNG previews for the UI.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import NamedTuple

import fitz  # PyMuPDF

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

#: Paper dimensions (width × height) in PDF points (1 pt = 1/72 inch).
PAPER_SIZES_PT: dict[str, tuple[float, float]] = {
    "A4": (595.0, 842.0),
    "LETTER": (612.0, 792.0),
}

_BORDER_COLOR: tuple[float, float, float] = (0.5, 0.5, 0.5)  # mid-gray
_BORDER_WIDTH: float = 0.5  # points
_BORDER_INSET: float = 1.0  # points — inset from slot edge before drawing


# ---------------------------------------------------------------------------
# Enumerations & data classes
# ---------------------------------------------------------------------------


class NUp(Enum):
    """Number of source-PDF pages placed on each side of a physical sheet."""

    ONE = 1
    TWO = 2
    FOUR = 4


class PaperSize(Enum):
    """Supported output paper sizes."""

    A4 = auto()
    LETTER = auto()


class SheetOrientation(Enum):
    """Supported sheet orientations (Portrait, Landscape, or Auto based on N-up)."""

    AUTO = auto()
    PORTRAIT = auto()
    LANDSCAPE = auto()


@dataclass
class DuplexOptions:
    """
    Configuration that controls the duplex-printing layout.

    Attributes
    ----------
    nup:
        How many source pages to tile per sheet side (1, 2, or 4).
    paper:
        Output paper size (A4 or US Letter).
    orientation:
        Sheet orientation (Portrait, Landscape, or Auto based on N-up).
    reverse_back:
        When *True*, reverse the ordering of back-side sheet pages across the
        whole document — useful for face-up output trays.
    flip_short_edge:
        When *True*, rotate every back-side output page 180° so that the
        printed sheet can be re-inserted for short-edge (top-flip) duplexing.
    draw_border:
        Draw a thin gray rectangle around each N-up slot.
    margin_pt:
        Outer margin (all four sides) in PDF points.
    gap_pt:
        Gap between adjacent N-up slots in PDF points.
    """

    nup: NUp = NUp.TWO
    paper: PaperSize = PaperSize.A4
    orientation: SheetOrientation = SheetOrientation.AUTO
    reverse_back: bool = False
    flip_short_edge: bool = False
    draw_border: bool = True
    margin_pt: float = 18.0
    gap_pt: float = 6.0


@dataclass
class SheetPair:
    """
    Represents one physical sheet of paper (both sides).

    Attributes
    ----------
    sheet_index:
        0-based index of this physical sheet in the print job.
    front_page_indices:
        0-based source-PDF page indices that appear on the **front** side
        (up to ``nup`` entries; fewer on the last sheet).
    back_page_indices:
        0-based source-PDF page indices that appear on the **back** side
        (may be fewer than ``nup`` if the job doesn't fill the last sheet).
    """

    sheet_index: int
    front_page_indices: list[int] = field(default_factory=list)
    back_page_indices: list[int] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public API — parsing
# ---------------------------------------------------------------------------


def parse_page_range(spec: str, total_pages: int) -> list[int]:
    """
    Convert a human-readable page-range string into 0-based page indices.

    Parameters
    ----------
    spec:
        Page specification using 1-based page numbers, e.g.
        ``"1-3, 5, 8-10"``.  An empty or whitespace-only *spec* selects all
        pages.
    total_pages:
        Total number of pages in the source PDF (used for validation).

    Returns
    -------
    list[int]
        Sorted, deduplicated list of **0-based** page indices.

    Raises
    ------
    ValueError
        If *spec* contains a malformed token or a page number outside the
        valid 1-based range ``[1, total_pages]``.

    Examples
    --------
    >>> parse_page_range("1-3, 5", 10)
    [0, 1, 2, 4]
    >>> parse_page_range("", 5)
    [0, 1, 2, 3, 4]
    """
    if not spec or not spec.strip():
        return list(range(total_pages))

    indices: set[int] = set()

    # Split on commas; each token is either "N" or "N-M".
    for raw_token in spec.split(","):
        token = raw_token.strip()
        if not token:
            continue

        # Range token: "N-M"
        range_match = re.fullmatch(r"(\d+)\s*-\s*(\d+)", token)
        # Single token: "N"
        single_match = re.fullmatch(r"(\d+)", token)

        if range_match:
            start_1 = int(range_match.group(1))
            end_1 = int(range_match.group(2))
            if start_1 < 1 or end_1 < 1:
                raise ValueError(
                    f"Page numbers must be >= 1; got '{token}'."
                )
            if start_1 > end_1:
                raise ValueError(
                    f"Range start must not exceed range end; got '{token}'."
                )
            if end_1 > total_pages:
                raise ValueError(
                    f"Page {end_1} is out of range (document has "
                    f"{total_pages} page(s))."
                )
            for p in range(start_1, end_1 + 1):
                indices.add(p - 1)  # convert to 0-based

        elif single_match:
            page_1 = int(single_match.group(1))
            if page_1 < 1:
                raise ValueError(
                    f"Page numbers must be >= 1; got '{token}'."
                )
            if page_1 > total_pages:
                raise ValueError(
                    f"Page {page_1} is out of range (document has "
                    f"{total_pages} page(s))."
                )
            indices.add(page_1 - 1)

        else:
            raise ValueError(
                f"Unrecognised page-range token: '{token}'. "
                "Expected formats: '5', '1-3'."
            )

    return sorted(indices)


def insert_blank_pages(
    page_indices: list[int],
    blank_spec: str,
    total_pages: int,
    position: str = "after",
) -> list[int]:
    """
    Insert blank-page placeholders (-1) into *page_indices* at positions
    specified by 1-based page numbers.

    Parameters
    ----------
    page_indices:
        Ordered list of 0-based page indices to which blanks are added.
    blank_spec:
        Comma-separated 1-based page numbers or ranges where blank pages
        should be inserted, e.g. ``"2, 5"`` or ``"3-5"``.  An empty or
        whitespace-only *blank_spec* returns a copy of *page_indices*.
    total_pages:
        Total number of pages in the source PDF (used for validation).
    position:
        ``"after"`` (default) to insert after the specified page,
        or ``"before"`` to insert before the specified page.

    Returns
    -------
    list[int]
        New list of page indices where ``-1`` represents an inserted blank page.

    Raises
    ------
    ValueError
        If *blank_spec* contains an invalid token or a page number outside
        the valid range ``[1, total_pages]``.
    """
    if not blank_spec or not blank_spec.strip():
        return list(page_indices)

    targets: list[int] = []
    for raw_token in blank_spec.split(","):
        token = raw_token.strip()
        if not token:
            continue

        range_match = re.fullmatch(r"(\d+)\s*-\s*(\d+)", token)
        single_match = re.fullmatch(r"(\d+)", token)

        if range_match:
            s1 = int(range_match.group(1))
            e1 = int(range_match.group(2))
            if s1 < 1 or e1 < 1:
                raise ValueError(f"Page numbers must be >= 1; got '{token}'.")
            if s1 > e1:
                raise ValueError(f"Range start must not exceed range end; got '{token}'.")
            if e1 > total_pages:
                raise ValueError(
                    f"Page {e1} is out of range (document has {total_pages} page(s))."
                )
            for p in range(s1, e1 + 1):
                targets.append(p - 1)

        elif single_match:
            p1 = int(single_match.group(1))
            if p1 < 1:
                raise ValueError(f"Page numbers must be >= 1; got '{token}'.")
            if p1 > total_pages:
                raise ValueError(
                    f"Page {p1} is out of range (document has {total_pages} page(s))."
                )
            targets.append(p1 - 1)

        else:
            raise ValueError(
                f"Unrecognised blank-page token: '{token}'. "
                "Expected formats: '5', '1-3'."
            )

    if not targets:
        return list(page_indices)

    target_counts = Counter(targets)
    result: list[int] = []
    handled: set[int] = set()

    for p in page_indices:
        if p >= 0 and position == "before":
            for t in sorted(target_counts.keys()):
                if t <= p and t not in handled:
                    result.extend([-1] * target_counts[t])
                    handled.add(t)

        if p >= 0 and position == "after":
            # If target t was skipped/omitted and is < p, insert before subsequent page p
            for t in sorted(target_counts.keys()):
                if t < p and t not in handled:
                    result.extend([-1] * target_counts[t])
                    handled.add(t)

        result.append(p)

        if p >= 0 and position == "after":
            if p in target_counts and p not in handled:
                result.extend([-1] * target_counts[p])
                handled.add(p)

    # Any remaining unhandled targets (e.g. after the last page in page_indices)
    for t in sorted(target_counts.keys()):
        if t not in handled:
            result.extend([-1] * target_counts[t])
            handled.add(t)

    return result


def filter_pages(
    include_spec: str,
    skip_spec: str,
    total_pages: int,
    blank_spec: str = "",
    blank_pos: str = "after",
) -> list[int]:
    """
    Compute 0-based page indices to include, excluding any skipped pages
    and inserting blank pages (-1) at specified page numbers.

    Parameters
    ----------
    include_spec:
        Specification of pages to include (e.g. "1-20, 25"; blank = all pages).
    skip_spec:
        Comma-separated list or ranges of pages to skip (e.g. "3, 7, 10-12";
        blank = skip nothing).
    total_pages:
        Total number of pages in the source PDF.
    blank_spec:
        Comma-separated list or ranges of pages where blank pages should be
        inserted (e.g. "2, 5"; blank = insert no blanks).
    blank_pos:
        "after" (default) or "before".

    Returns
    -------
    list[int]
        Ordered list of 0-based page indices with blanks represented by -1.

    Raises
    ------
    ValueError
        If include_spec, skip_spec, or blank_spec has invalid syntax or out-of-range pages.

    Examples
    --------
    >>> filter_pages("1-5", "2, 4", 5)
    [0, 2, 4]
    >>> filter_pages("1-5", "", 5, blank_spec="2", blank_pos="after")
    [0, 1, -1, 2, 3, 4]
    """
    included = parse_page_range(include_spec, total_pages)
    if skip_spec and skip_spec.strip():
        skipped = set(parse_page_range(skip_spec, total_pages))
        included = [p for p in included if p not in skipped]

    if blank_spec and blank_spec.strip():
        included = insert_blank_pages(
            included, blank_spec, total_pages, position=blank_pos
        )

    return included


# ---------------------------------------------------------------------------
# Public API — sheet-pair computation
# ---------------------------------------------------------------------------


def compute_sheet_pairs(
    page_indices: list[int],
    opts: DuplexOptions,
) -> list[SheetPair]:
    """
    Group selected pages into physical sheet pairs ready for duplex printing.

    Layout rules
    ------------
    * ``chunk_size = opts.nup.value * 2``  — pages per physical sheet.
    * *page_indices* is split into consecutive chunks of *chunk_size*.
    * For each chunk:

      - ``front_page_indices = chunk[:nup]``
      - ``back_page_indices  = chunk[nup:]``  (shorter on the last sheet)

    * If ``opts.reverse_back`` is *True*, the **list of back-side page-index
      lists** (one list per sheet) is reversed so that the physical stack can
      be fed back into a face-up output tray without manual reordering.

    Parameters
    ----------
    page_indices:
        Ordered list of 0-based source-PDF page indices to include.
    opts:
        Layout and printing options.

    Returns
    -------
    list[SheetPair]
        One :class:`SheetPair` per physical sheet, in front-print order.
    """
    nup: int = opts.nup.value
    chunk_size: int = nup * 2

    # Split page_indices into chunks of chunk_size.
    chunks: list[list[int]] = [
        page_indices[i : i + chunk_size]
        for i in range(0, max(len(page_indices), 1), chunk_size)
        if page_indices[i : i + chunk_size]
    ]

    # Build raw (front, back) pairs.
    raw_pairs: list[tuple[list[int], list[int]]] = []
    for chunk in chunks:
        front = chunk[:nup]
        back = chunk[nup:]
        raw_pairs.append((front, back))

    # Optionally reverse the ordering of back-side stacks across sheets.
    back_sides: list[list[int]] = [b for _, b in raw_pairs]
    if opts.reverse_back:
        back_sides = list(reversed(back_sides))

    sheet_pairs: list[SheetPair] = []
    for idx, ((front, _), back) in enumerate(zip(raw_pairs, back_sides)):
        sheet_pairs.append(
            SheetPair(
                sheet_index=idx,
                front_page_indices=front,
                back_page_indices=back,
            )
        )

    return sheet_pairs


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def is_landscape(opts: DuplexOptions) -> bool:
    """
    Determine whether the physical output sheet should be formatted as landscape.

    If ``opts.orientation`` is explicitly PORTRAIT or LANDSCAPE, that takes precedence.
    Under AUTO, 2-up defaults to landscape and 1-up/4-up default to portrait.
    """
    if opts.orientation == SheetOrientation.LANDSCAPE:
        return True
    if opts.orientation == SheetOrientation.PORTRAIT:
        return False
    return opts.nup == NUp.TWO


def _paper_dimensions(opts: DuplexOptions, landscape: bool) -> tuple[float, float]:
    """
    Return ``(width, height)`` in points for the configured paper size.

    Parameters
    ----------
    opts:
        Duplex options containing the target paper size.
    landscape:
        When *True*, swap width and height to produce a landscape orientation.

    Returns
    -------
    tuple[float, float]
        ``(width_pt, height_pt)``
    """
    key = opts.paper.name  # "A4" or "LETTER"
    w, h = PAPER_SIZES_PT[key]
    if landscape:
        return h, w
    return w, h


def _slot_rects(
    page_width: float,
    page_height: float,
    nup: int,
    landscape: bool,
    margin: float,
    gap: float,
) -> list[fitz.Rect]:
    """
    Compute the bounding rectangles for each N-up slot on the output page.

    Grid layout
    -----------
    * 1-up -> 1 column x 1 row
    * 2-up:
      - landscape -> 2 columns x 1 row (side-by-side)
      - portrait  -> 1 column x 2 rows (stacked vertically: top & bottom)
    * 4-up -> 2 columns x 2 rows (2x2 grid)

    Parameters
    ----------
    page_width:
        Output page width in points.
    page_height:
        Output page height in points.
    nup:
        Number of slots (1, 2, or 4).
    landscape:
        Whether the page orientation is landscape.
    margin:
        Outer margin on all four sides in points.
    gap:
        Gap between adjacent slots in points.

    Returns
    -------
    list[fitz.Rect]
        Slot rectangles in left-to-right, top-to-bottom order.
    """
    if nup == 1:
        cols, rows = 1, 1
    elif nup == 2:
        if landscape:
            cols, rows = 2, 1
        else:
            cols, rows = 1, 2
    else:  # 4
        cols, rows = 2, 2

    usable_w = page_width - 2 * margin - (cols - 1) * gap
    usable_h = page_height - 2 * margin - (rows - 1) * gap
    slot_w = usable_w / cols
    slot_h = usable_h / rows

    rects: list[fitz.Rect] = []
    for row in range(rows):
        for col in range(cols):
            x0 = margin + col * (slot_w + gap)
            y0 = margin + row * (slot_h + gap)
            rects.append(fitz.Rect(x0, y0, x0 + slot_w, y0 + slot_h))

    return rects


# ---------------------------------------------------------------------------
# Public API — page building
# ---------------------------------------------------------------------------


def build_nup_page(
    src_pdf: fitz.Document,
    page_indices: list[int],
    opts: DuplexOptions,
    rotate_180: bool = False,
) -> fitz.Document:
    """
    Build a single N-up output page as a new one-page :class:`fitz.Document`.

    Layout rules
    ------------
    * **1-up** — single slot fills the available area.
    * **2-up** — landscape (two side-by-side slots) or portrait (two vertically
      stacked slots: top and bottom).
    * **4-up** — 2 x 2 grid of slots.

    Each source page is placed with ``keep_proportion=True`` so that the
    aspect ratio of the original content is preserved inside its slot.

    If fewer source pages are provided than the number of N-up slots (e.g. the
    last sheet in the job), the remaining slots are left blank — no crash.

    Parameters
    ----------
    src_pdf:
        Open source :class:`fitz.Document` from which pages are read.
    page_indices:
        0-based indices into *src_pdf* to tile, in left-to-right,
        top-to-bottom order.  May be shorter than ``opts.nup.value``.
    opts:
        Layout options (paper size, orientation, margins, gap, border).
    rotate_180:
        When *True*, apply a 180-degree rotation to the finished output page
        (used for short-edge back-side flipping).

    Returns
    -------
    fitz.Document
        A new, single-page :class:`fitz.Document` containing the tiled layout.
        The caller is responsible for closing it when done.
    """
    nup: int = opts.nup.value
    landscape: bool = is_landscape(opts)

    page_w, page_h = _paper_dimensions(opts, landscape=landscape)
    slot_rects: list[fitz.Rect] = _slot_rects(
        page_w, page_h, nup, landscape, opts.margin_pt, opts.gap_pt
    )

    # Create a new single-page document.
    out_doc: fitz.Document = fitz.open()
    out_page: fitz.Page = out_doc.new_page(width=page_w, height=page_h)

    for slot_idx, slot_rect in enumerate(slot_rects):
        if slot_idx >= len(page_indices):
            # No more source pages — leave this slot blank.
            break

        src_page_no = page_indices[slot_idx]
        if 0 <= src_page_no < len(src_pdf):
            out_page.show_pdf_page(
                slot_rect,
                src_pdf,
                src_page_no,
                keep_proportion=True,
            )

        if opts.draw_border:
            # Inset the border rectangle slightly so the line sits inside the slot.
            border_rect = fitz.Rect(
                slot_rect.x0 + _BORDER_INSET,
                slot_rect.y0 + _BORDER_INSET,
                slot_rect.x1 - _BORDER_INSET,
                slot_rect.y1 - _BORDER_INSET,
            )
            out_page.draw_rect(
                border_rect,
                color=_BORDER_COLOR,
                width=_BORDER_WIDTH,
            )

    if rotate_180:
        out_page.set_rotation(180)

    return out_doc


# ---------------------------------------------------------------------------
# Public API — document assembly
# ---------------------------------------------------------------------------


def build_document(
    src_pdf: fitz.Document,
    sheet_pairs: list[SheetPair],
    side: str,
    opts: DuplexOptions,
) -> fitz.Document:
    """
    Assemble a multi-page output :class:`fitz.Document` for one side of the
    duplex job.

    Parameters
    ----------
    src_pdf:
        Open source :class:`fitz.Document` from which pages are read.
    sheet_pairs:
        Ordered list of physical sheet pairs as produced by
        :func:`compute_sheet_pairs`.
    side:
        ``"front"`` or ``"back"``.  Controls which page-index list is tiled
        and whether ``flip_short_edge`` rotation is applied.
    opts:
        Layout and printing options.

    Returns
    -------
    fitz.Document
        A new multi-page :class:`fitz.Document` ready to be saved or printed.
        One output page per physical sheet, in print order.

    Raises
    ------
    ValueError
        If *side* is not ``"front"`` or ``"back"``.
    """
    if side not in {"front", "back"}:
        raise ValueError(
            f"'side' must be 'front' or 'back', got {side!r}."
        )

    is_back: bool = side == "back"
    rotate_180: bool = is_back and opts.flip_short_edge

    out_doc: fitz.Document = fitz.open()

    for pair in sheet_pairs:
        indices: list[int] = (
            pair.back_page_indices if is_back else pair.front_page_indices
        )

        # Build a temporary one-page document for this sheet side.
        nup_doc: fitz.Document = build_nup_page(
            src_pdf, indices, opts, rotate_180=rotate_180
        )
        try:
            # Append the single page into the accumulator document.
            out_doc.insert_pdf(nup_doc)
        finally:
            nup_doc.close()

    return out_doc


# ---------------------------------------------------------------------------
# Public API — preview rendering
# ---------------------------------------------------------------------------


def render_sheet_preview(
    src_pdf: fitz.Document,
    pair: SheetPair,
    side: str,
    opts: DuplexOptions,
    dpi: int = 120,
) -> bytes:
    """
    Render a PNG preview of one side of a physical sheet.

    Parameters
    ----------
    src_pdf:
        Open source :class:`fitz.Document` from which pages are read.
    pair:
        The :class:`SheetPair` whose side is to be previewed.
    side:
        ``"front"`` or ``"back"``.
    opts:
        Layout and printing options.
    dpi:
        Resolution of the preview raster image in dots per inch.

    Returns
    -------
    bytes
        Raw PNG image bytes.

    Raises
    ------
    ValueError
        If *side* is not ``"front"`` or ``"back"``.
    """
    if side not in {"front", "back"}:
        raise ValueError(
            f"'side' must be 'front' or 'back', got {side!r}."
        )

    is_back: bool = side == "back"
    rotate_180: bool = is_back and opts.flip_short_edge
    indices: list[int] = (
        pair.back_page_indices if is_back else pair.front_page_indices
    )

    nup_doc: fitz.Document = build_nup_page(
        src_pdf, indices, opts, rotate_180=rotate_180
    )
    try:
        preview_page: fitz.Page = nup_doc[0]
        pixmap: fitz.Pixmap = preview_page.get_pixmap(dpi=dpi)
        return pixmap.tobytes("png")
    finally:
        nup_doc.close()
