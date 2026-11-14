# SPDX-License-Identifier: GPL-3.0-or-later
# make-duplex — Harpreet444/make-duplex
"""
tests/test_ui.py
================
Pytest test-suite for make_duplex PyQt6 UI and printer components.
Uses offscreen Qt platform for headless CI / testing.
"""

from __future__ import annotations

import os
import pathlib
import sys

import fitz
import pytest

# Ensure offscreen Qt
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication

from PyQt6.QtPrintSupport import QPrintDialog, QPrinter
from make_duplex.engine import (
    DuplexOptions,
    NUp,
    PaperSize,
    SheetOrientation,
    SheetPair,
    build_document,
)
from make_duplex.printer import (
    FlipStackDialog,
    GuidedDuplexPrinter,
    PrinterSelectDialog,
    print_fitz_document,
    print_single_side,
)
from make_duplex.ui.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture()
def sample_pdf_path(tmp_path: pathlib.Path) -> pathlib.Path:
    pdf_path = tmp_path / "ui_sample.pdf"
    doc = fitz.open()
    for i in range(8):
        page = doc.new_page(width=595, height=842)
        page.insert_text(fitz.Point(100, 300), f"Slide {i + 1}", fontsize=36)
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


def test_main_window_init(qapp: QApplication) -> None:
    """MainWindow initializes cleanly with default state."""
    window = MainWindow()
    assert window.windowTitle() == "make-duplex — N-up Duplex Print Helper"
    assert window._src_pdf is None
    assert window._sheet_pairs == []
    window.close()


def test_main_window_load_pdf(qapp: QApplication, sample_pdf_path: pathlib.Path) -> None:
    """MainWindow loads PDF, computes sheet pairs, and updates preview."""
    window = MainWindow()
    window.load_pdf(str(sample_pdf_path))

    assert window._src_pdf is not None
    assert window._total_src_pages == 8
    # 8 pages at 2-up (4 pages/sheet) -> 2 physical sheets
    assert len(window._sheet_pairs) == 2
    assert "Sheet 1 of 2" in window._sheet_indicator.text()
    assert window._cached_front_png is not None
    assert window._cached_back_png is not None
    window.close()


def test_main_window_long_filename_truncated(
    qapp: QApplication, tmp_path: pathlib.Path
) -> None:
    """Long filename is truncated with '...' so horizontal scrollbar is not needed."""
    long_name = "Introduction_to_Computer_Networks___OSI_Model_1783600720.pdf"
    pdf_path = tmp_path / long_name
    doc = fitz.open()
    doc.new_page()
    doc.save(str(pdf_path))
    doc.close()

    window = MainWindow()
    window.load_pdf(str(pdf_path))

    label_text = window._doc_info_label.text()
    assert "..." in label_text
    assert len(label_text) < len(long_name) + 15
    # Full filename is preserved in the tooltip
    assert long_name in window._doc_info_label.toolTip()
    window.close()


def test_main_window_page_range(qapp: QApplication, sample_pdf_path: pathlib.Path) -> None:
    """Applying custom page range updates sheet count and preview."""
    window = MainWindow()
    window.load_pdf(str(sample_pdf_path))

    # Select pages 1-4 only -> 1 physical sheet for 2-up
    window._range_edit.setText("1-4")
    window._on_apply_range()

    assert len(window._sheet_pairs) == 1
    assert "Sheet 1 of 1" in window._sheet_indicator.text()
    assert window._sheet_pairs[0].front_page_indices == [0, 1]
    assert window._sheet_pairs[0].back_page_indices == [2, 3]
    window.close()


def test_main_window_2up_portrait(qapp: QApplication, sample_pdf_path: pathlib.Path) -> None:
    """Selecting 2-up portrait configures SheetOrientation.PORTRAIT."""
    window = MainWindow()
    window.load_pdf(str(sample_pdf_path))

    # Index 2 is "2-up (2 slides / portrait page)"
    window._nup_combo.setCurrentIndex(2)
    opts = window._get_current_options()
    assert opts.nup == NUp.TWO
    assert opts.orientation == SheetOrientation.PORTRAIT
    assert len(window._sheet_pairs) == 2
    window.close()


def test_main_window_nup_change(qapp: QApplication, sample_pdf_path: pathlib.Path) -> None:
    """Switching to 4-up updates sheet chunks (8 pages -> 1 sheet)."""
    window = MainWindow()
    window.load_pdf(str(sample_pdf_path))

    # Switch to 4-up (index 3)
    window._nup_combo.setCurrentIndex(3)
    assert len(window._sheet_pairs) == 1
    assert window._sheet_pairs[0].front_page_indices == [0, 1, 2, 3]
    assert window._sheet_pairs[0].back_page_indices == [4, 5, 6, 7]
    window.close()


def test_main_window_navigation(qapp: QApplication, sample_pdf_path: pathlib.Path) -> None:
    """Next and Previous buttons navigate between sheets."""
    window = MainWindow()
    window.load_pdf(str(sample_pdf_path))

    assert window._current_sheet_idx == 0
    window._on_next_sheet()
    assert window._current_sheet_idx == 1
    window._on_prev_sheet()
    assert window._current_sheet_idx == 0
    window.close()


def test_flip_stack_dialog(qapp: QApplication) -> None:
    """FlipStackDialog instantiates and shows correct instructions."""
    opts = DuplexOptions(nup=NUp.TWO, flip_short_edge=False, reverse_back=True)
    dlg = FlipStackDialog(total_sheets=5, opts=opts, printer_name="Office Printer")
    assert dlg.windowTitle() == "Step 1 Complete: Flip Paper Stack"
    dlg.close()


def test_printer_select_dialog(qapp: QApplication) -> None:
    """PrinterSelectDialog initializes without error."""
    dlg = PrinterSelectDialog()
    assert dlg.windowTitle() == "Select Printer — make-duplex"
    dlg.close()


def test_qprint_dialog_init(qapp: QApplication) -> None:
    """QPrintDialog initializes and can be pre-configured with options."""
    printer = QPrinter()
    dlg = QPrintDialog(printer)
    dlg.setWindowTitle("Print Setup (Guided Duplex) — make-duplex")
    dlg.setOption(QPrintDialog.PrintDialogOption.PrintPageRange, False)
    assert dlg.windowTitle() == "Print Setup (Guided Duplex) — make-duplex"
    dlg.close()


def test_print_fitz_document_grayscale(
    qapp: QApplication, sample_pdf_path: pathlib.Path
) -> None:
    """print_fitz_document respects Grayscale color mode without errors."""
    doc = fitz.open(str(sample_pdf_path))
    printer = QPrinter()
    printer.setOutputFileName("test_out.pdf")
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setColorMode(QPrinter.ColorMode.GrayScale)

    opts = DuplexOptions(nup=NUp.TWO, orientation=SheetOrientation.LANDSCAPE)
    success = print_fitz_document(doc, printer, opts)
    assert success is True
    doc.close()


def test_main_window_skip_pages(qapp: QApplication, sample_pdf_path: pathlib.Path) -> None:
    """MainWindow correctly excludes skipped pages and updates sheet count."""
    window = MainWindow()
    window.load_pdf(str(sample_pdf_path))

    # Document has 8 pages (1-8).
    # Include: 1-6 (6 pages)
    # Skip: 2, 4 (2 pages skipped)
    # Remaining pages: 1, 3, 5, 6 (4 pages) -> at 2-up that's 1 physical sheet!
    window._range_edit.setText("1-6")
    window._skip_edit.setText("2, 4")
    window._on_apply_range()

    assert len(window._selected_page_indices) == 4
    assert window._selected_page_indices == [0, 2, 4, 5]
    assert len(window._sheet_pairs) == 1
    assert "Sheet 1 of 1" in window._sheet_indicator.text()
    assert "Skipped:" in window._range_status_label.text()
    window.close()


def test_print_single_side_front_and_back(
    qapp: QApplication, sample_pdf_path: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """print_single_side prints front and back passes independently."""
    doc = fitz.open(str(sample_pdf_path))
    opts = DuplexOptions(nup=NUp.TWO, orientation=SheetOrientation.LANDSCAPE)
    sheet_pairs = [
        SheetPair(sheet_index=0, front_page_indices=[0, 1], back_page_indices=[2, 3])
    ]

    # Test Front pass
    front_printer = QPrinter()
    front_pdf = tmp_path / "front_pass.pdf"
    front_printer.setOutputFileName(str(front_pdf))
    front_printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)

    success_front = print_single_side(
        doc, sheet_pairs, side="front", opts=opts, printer=front_printer, show_dialogs=False
    )
    assert success_front is True
    assert front_pdf.exists()

    # Test Back pass
    back_printer = QPrinter()
    back_pdf = tmp_path / "back_pass.pdf"
    back_printer.setOutputFileName(str(back_pdf))
    back_printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)

    success_back = print_single_side(
        doc, sheet_pairs, side="back", opts=opts, printer=back_printer, show_dialogs=False
    )
    assert success_back is True
    assert back_pdf.exists()
    doc.close()
