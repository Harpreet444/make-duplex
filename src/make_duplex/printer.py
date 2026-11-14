# printer.py — make-duplex
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
printer.py
~~~~~~~~~~

Direct printing integration for make-duplex using QtPrintSupport.

Handles:
* Printer discovery and selection dialog.
* Multi-page rendering and printing via QPrinter and QPainter.
* Interactive "Flip Paper Stack" dialog guiding single-stack manual duplexing.
* Two-phase guided duplex workflow (Front -> Flip Stack -> Back).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

import fitz  # PyMuPDF
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QFont, QImage, QPainter, QPageLayout, QPageSize
from PyQt6.QtPrintSupport import QPrinter, QPrinterInfo, QPrintDialog
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from make_duplex.engine import (
    DuplexOptions,
    NUp,
    PaperSize,
    SheetOrientation,
    SheetPair,
    build_document,
    is_landscape,
)


class PrinterSelectDialog(QDialog):
    """
    Modal dialog allowing the user to select an available system printer.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Select Printer — make-duplex")
        self.resize(420, 180)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        header = QLabel("Choose the target printer:")
        header.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(header)

        self._combo = QComboBox()
        available = QPrinterInfo.availablePrinterNames()
        default_name = QPrinterInfo.defaultPrinterName()

        if available:
            for name in available:
                label = f"{name} (Default)" if name == default_name else name
                self._combo.addItem(label, userData=name)
            default_idx = self._combo.findData(default_name)
            if default_idx >= 0:
                self._combo.setCurrentIndex(default_idx)
        else:
            self._combo.addItem("No printers found", userData=None)
            self._combo.setEnabled(False)

        layout.addWidget(self._combo)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def selected_printer_name(self) -> str | None:
        """Return the name of the chosen printer, or None if cancelled/none."""
        return self._combo.currentData()


class FlipStackDialog(QDialog):
    """
    Modal dialog displayed after the front side pass finishes,
    instructing the user exactly how to flip and reload the paper stack.
    """

    def __init__(
        self,
        total_sheets: int,
        opts: DuplexOptions,
        parent: QWidget | None = None,
        printer_name: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Step 1 Complete: Flip Paper Stack")
        self.resize(520, 440)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        # Title / Banner
        title_label = QLabel("Front Sides Printed Successfully!")
        title_label.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #166534; padding: 4px 0;"
        )
        layout.addWidget(title_label)

        # Summary badge
        info_label = QLabel(
            f"Printed {total_sheets} physical sheet(s). "
            f"Now prepare the stack for printing the back sides."
        )
        info_label.setStyleSheet("color: #374151; font-size: 13px;")
        layout.addWidget(info_label)

        if printer_name:
            printer_badge = QLabel(f"🖨 Target Printer: <b>{printer_name}</b>")
            printer_badge.setStyleSheet(
                "background-color: #e0f2fe; color: #0369a1; padding: 6px 10px; "
                "border-radius: 4px; font-size: 11px;"
            )
            layout.addWidget(printer_badge)

        # Step card
        card = QFrame()
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setStyleSheet(
            "background-color: #f8fafc; border: 1px solid #cbd5e1; "
            "border-radius: 6px; padding: 12px;"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(10)

        flip_edge = "SHORT edge (top-flip)" if opts.flip_short_edge else "LONG edge (standard book-turn)"
        tray_note = (
            "• Tray setting: 'Reverse back-side' is ACTIVE. Stack order has been adapted."
            if opts.reverse_back
            else "• Tray setting: Standard face-down order."
        )

        steps_text = (
            "<b>Instructions:</b><br>"
            "1. Take the entire printed paper stack from the printer's output tray.<br>"
            "2. <b>Do not change the page order</b> within the stack.<br>"
            f"3. Flip the entire stack along the <b>{flip_edge}</b>.<br>"
            "4. Insert the flipped stack back into your printer's paper feed tray.<br>"
            f"<i>{tray_note}</i><br><br>"
            "5. Click <b>Continue (Print Back Side)</b> when ready."
        )

        steps_label = QLabel(steps_text)
        steps_label.setWordWrap(True)
        steps_label.setStyleSheet("font-size: 12px; line-height: 1.4;")
        card_layout.addWidget(steps_label)

        # Diagram preview
        diagram = QLabel(
            "┌──────────────┐         Flip Stack          ┌──────────────┐\n"
            "│ [1] [2]      │    ═════════════════>       │ [3] [4]      │\n"
            "│ Front Side   │   (Keep stack order)        │ Back Side    │\n"
            "└──────────────┘                             └──────────────┘"
        )
        diagram_font = QFont("Courier New", 9)
        diagram_font.setStyleHint(QFont.StyleHint.Monospace)
        diagram.setFont(diagram_font)
        diagram.setAlignment(Qt.AlignmentFlag.AlignCenter)
        diagram.setStyleSheet(
            "background-color: #f1f5f9; padding: 8px; border: 1px dashed #94a3b8; border-radius: 4px;"
        )
        card_layout.addWidget(diagram)

        layout.addWidget(card)

        # Buttons
        button_row = QHBoxLayout()
        button_row.addStretch()

        self._btn_cancel = QPushButton("Cancel Job")
        self._btn_cancel.clicked.connect(self.reject)
        button_row.addWidget(self._btn_cancel)

        self._btn_continue = QPushButton("Continue (Print Back Side)")
        self._btn_continue.setStyleSheet(
            "background-color: #2563eb; color: white; font-weight: bold; "
            "padding: 8px 16px; border-radius: 4px;"
        )
        self._btn_continue.clicked.connect(self.accept)
        button_row.addWidget(self._btn_continue)

        layout.addLayout(button_row)


def print_fitz_document(
    doc: fitz.Document,
    printer: QPrinter,
    opts: DuplexOptions,
    progress_callback: Callable[[int, int], bool] | None = None,
) -> bool:
    """
    Render each page of a PyMuPDF Document and draw it onto a QPrinter.

    Parameters
    ----------
    doc:
        PyMuPDF document to print.
    printer:
        Configured QPrinter target.
    opts:
        Duplex options (for orientation and paper size setup).
    progress_callback:
        Optional callback (page_index, total_pages) -> bool.
        If it returns False, printing is cancelled.

    Returns
    -------
    bool
        True if all pages printed successfully, False if cancelled.
    """
    total_pages = len(doc)
    if total_pages == 0:
        return True

    # Configure paper size
    q_page_size = (
        QPageSize(QPageSize.PageSizeId.A4)
        if opts.paper == PaperSize.A4
        else QPageSize(QPageSize.PageSizeId.Letter)
    )

    orientation = (
        QPageLayout.Orientation.Landscape
        if is_landscape(opts)
        else QPageLayout.Orientation.Portrait
    )

    printer.setPageSize(q_page_size)
    printer.setPageOrientation(orientation)

    painter = QPainter()
    if not painter.begin(printer):
        raise RuntimeError("Failed to initialize QPainter for printer.")

    try:
        page_layout = printer.pageLayout()
        paint_rect = page_layout.paintRectPixels(printer.resolution())

        for page_idx in range(total_pages):
            if progress_callback is not None:
                continue_printing = progress_callback(page_idx, total_pages)
                if not continue_printing:
                    return False

            if page_idx > 0:
                printer.newPage()

            page = doc[page_idx]
            # Render page at 300 DPI for sharp output
            pix = page.get_pixmap(dpi=300)

            # Check if printer requested grayscale / monochrome
            if printer.colorMode() == QPrinter.ColorMode.GrayScale:
                if pix.alpha:
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                pix = fitz.Pixmap(fitz.csGRAY, pix)
                image = QImage(
                    pix.samples,
                    pix.width,
                    pix.height,
                    pix.stride,
                    QImage.Format.Format_Grayscale8,
                )
            else:
                if pix.alpha:
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                image = QImage(
                    pix.samples,
                    pix.width,
                    pix.height,
                    pix.stride,
                    QImage.Format.Format_RGB888,
                )

            target_rect = QRectF(
                float(paint_rect.x()),
                float(paint_rect.y()),
                float(paint_rect.width()),
                float(paint_rect.height()),
            )
            # Scale proportionally to fit within the paintable rect
            scaled_image = image.scaled(
                paint_rect.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            x_offset = float(paint_rect.x()) + (paint_rect.width() - scaled_image.width()) / 2.0
            y_offset = float(paint_rect.y()) + (paint_rect.height() - scaled_image.height()) / 2.0
            draw_rect = QRectF(x_offset, y_offset, float(scaled_image.width()), float(scaled_image.height()))

            painter.drawImage(draw_rect, scaled_image)
    finally:
        painter.end()

    return True


def print_single_side(
    src_pdf: fitz.Document,
    sheet_pairs: list[SheetPair],
    side: str,  # "front" or "back"
    opts: DuplexOptions,
    parent: QWidget | None = None,
    printer: QPrinter | None = None,
    show_dialogs: bool = True,
) -> bool:
    """
    Print only one side ("front" or "back") of the duplex job.

    Opens QPrintDialog for user printer & preference selection if a configured
    printer is not already supplied.

    Parameters
    ----------
    src_pdf:
        Source PDF document.
    sheet_pairs:
        List of sheet pairs for the job.
    side:
        "front" or "back".
    opts:
        Duplex options (paper size, orientation, flip settings).
    parent:
        Parent widget for modal dialogs.
    printer:
        Optional pre-configured QPrinter instance. If None, QPrintDialog is displayed.
    show_dialogs:
        Whether to show progress and completion dialogs (set False for testing).

    Returns
    -------
    bool
        True if printing succeeded, False if cancelled or aborted.
    """
    if not sheet_pairs:
        if show_dialogs:
            QMessageBox.warning(
                parent,
                "No Sheets",
                "There are no pages selected to print.",
            )
        return False

    if printer is None:
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        q_page_size = (
            QPageSize(QPageSize.PageSizeId.A4)
            if opts.paper == PaperSize.A4
            else QPageSize(QPageSize.PageSizeId.Letter)
        )
        orientation = (
            QPageLayout.Orientation.Landscape
            if is_landscape(opts)
            else QPageLayout.Orientation.Portrait
        )
        printer.setPageSize(q_page_size)
        printer.setPageOrientation(orientation)

        title = "Print Front Sides" if side == "front" else "Print Back Sides"
        pass_num = "1" if side == "front" else "2"
        print_dialog = QPrintDialog(printer, parent)
        print_dialog.setWindowTitle(f"{title} (Pass {pass_num}) — make-duplex")
        print_dialog.setOption(QPrintDialog.PrintDialogOption.PrintPageRange, False)
        print_dialog.setOption(QPrintDialog.PrintDialogOption.PrintSelection, False)
        print_dialog.setOption(QPrintDialog.PrintDialogOption.PrintCurrentPage, False)

        if print_dialog.exec() != QDialog.DialogCode.Accepted:
            return False

    total_sheets = len(sheet_pairs)
    doc = build_document(src_pdf, sheet_pairs, side=side, opts=opts)

    prog = None
    if show_dialogs:
        prog = QProgressDialog(
            f"Printing {side.capitalize()} sides...",
            "Cancel",
            0,
            total_sheets,
            parent,
        )
        prog.setWindowTitle(f"Printing {side.capitalize()} Sides")
        prog.setWindowModality(Qt.WindowModality.ApplicationModal)
        prog.show()

    def cb(idx: int, total: int) -> bool:
        if prog is not None:
            prog.setValue(idx)
            QApplication.processEvents()
            return not prog.wasCanceled()
        return True

    try:
        success = print_fitz_document(doc, printer, opts, progress_callback=cb)
        if prog is not None:
            prog.setValue(total_sheets)
    finally:
        if prog is not None:
            prog.close()
        doc.close()

    if not success:
        if show_dialogs:
            QMessageBox.information(
                parent,
                "Cancelled",
                f"{side.capitalize()}-side printing was cancelled.",
            )
        return False

    if show_dialogs:
        if side == "front":
            QMessageBox.information(
                parent,
                "Front Sides Printed",
                f"Successfully printed all {total_sheets} Front sheet(s)!\n\n"
                "Next steps:\n"
                "1. Take the entire printed stack from the output tray.\n"
                "2. Flip the stack without changing page order.\n"
                "3. Place the flipped stack back into the paper tray.\n"
                "4. Click '🖨 Print Back Sides (Pass 2)' to finish.",
            )
        else:
            QMessageBox.information(
                parent,
                "Back Sides Printed",
                f"Successfully printed all {total_sheets} Back sheet(s)!\n\n"
                "Duplex printing is complete! Your double-sided document is ready.",
            )

    return True


class GuidedDuplexPrinter:
    """
    High-level orchestrator for manual duplex printing.

    Workflow:
    1. Select printer.
    2. Build front document and print all front sides.
    3. Display FlipStackDialog and pause for user action.
    4. Build back document and print all back sides.
    5. Show completion dialog.
    """

    def __init__(
        self,
        src_pdf: fitz.Document,
        sheet_pairs: list[SheetPair],
        opts: DuplexOptions,
        parent: QWidget | None = None,
    ) -> None:
        self._src_pdf = src_pdf
        self._sheet_pairs = sheet_pairs
        self._opts = opts
        self._parent = parent

    def run(self) -> None:
        """Execute the two-pass guided printing workflow."""
        if not self._sheet_pairs:
            QMessageBox.warning(
                self._parent,
                "No Sheets",
                "There are no pages selected to print.",
            )
            return

        # 1. Initialize printer and open system Print Dialog
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)

        # Pre-configure page size and orientation
        q_page_size = (
            QPageSize(QPageSize.PageSizeId.A4)
            if self._opts.paper == PaperSize.A4
            else QPageSize(QPageSize.PageSizeId.Letter)
        )
        orientation = (
            QPageLayout.Orientation.Landscape
            if is_landscape(self._opts)
            else QPageLayout.Orientation.Portrait
        )
        printer.setPageSize(q_page_size)
        printer.setPageOrientation(orientation)

        # Open native system Print Dialog (allows choosing printer, color format/mode, tray, quality, etc.)
        print_dialog = QPrintDialog(printer, self._parent)
        print_dialog.setWindowTitle("Print Setup (Guided Duplex) — make-duplex")
        print_dialog.setOption(QPrintDialog.PrintDialogOption.PrintPageRange, False)
        print_dialog.setOption(QPrintDialog.PrintDialogOption.PrintSelection, False)
        print_dialog.setOption(QPrintDialog.PrintDialogOption.PrintCurrentPage, False)

        if print_dialog.exec() != QDialog.DialogCode.Accepted:
            return  # User cancelled the print menu

        printer_name = printer.printerName()

        # 2. Build Front Document
        front_doc = build_document(
            self._src_pdf, self._sheet_pairs, side="front", opts=self._opts
        )

        total_sheets = len(self._sheet_pairs)

        # Progress dialog for front pass
        prog_front = QProgressDialog(
            "Printing Front sides...",
            "Cancel",
            0,
            total_sheets,
            self._parent,
        )
        prog_front.setWindowTitle("Printing Front Sides")
        prog_front.setWindowModality(Qt.WindowModality.ApplicationModal)
        prog_front.show()

        def front_cb(idx: int, total: int) -> bool:
            prog_front.setValue(idx)
            QApplication.processEvents()
            return not prog_front.wasCanceled()

        try:
            success = print_fitz_document(
                front_doc, printer, self._opts, progress_callback=front_cb
            )
            prog_front.setValue(total_sheets)
        finally:
            prog_front.close()
            front_doc.close()

        if not success:
            QMessageBox.information(
                self._parent,
                "Cancelled",
                "Front-side printing was cancelled.",
            )
            return

        # 3. Guided Flip Dialog
        flip_dialog = FlipStackDialog(
            total_sheets, self._opts, self._parent, printer_name=printer_name
        )
        if flip_dialog.exec() != QDialog.DialogCode.Accepted:
            QMessageBox.information(
                self._parent,
                "Job Stopped",
                "Printing was stopped after front sides. Back sides were not printed.",
            )
            return

        # 4. Build Back Document
        back_doc = build_document(
            self._src_pdf, self._sheet_pairs, side="back", opts=self._opts
        )

        prog_back = QProgressDialog(
            "Printing Back sides...",
            "Cancel",
            0,
            total_sheets,
            self._parent,
        )
        prog_back.setWindowTitle("Printing Back Sides")
        prog_back.setWindowModality(Qt.WindowModality.ApplicationModal)
        prog_back.show()

        def back_cb(idx: int, total: int) -> bool:
            prog_back.setValue(idx)
            QApplication.processEvents()
            return not prog_back.wasCanceled()

        try:
            success_back = print_fitz_document(
                back_doc, printer, self._opts, progress_callback=back_cb
            )
            prog_back.setValue(total_sheets)
        finally:
            prog_back.close()
            back_doc.close()

        if not success_back:
            QMessageBox.warning(
                self._parent,
                "Cancelled",
                "Back-side printing was cancelled midway.",
            )
            return

        # 5. Success Notification
        QMessageBox.information(
            self._parent,
            "Duplex Printing Finished",
            f"Successfully printed all {total_sheets} sheet(s) (Front & Back)!\n\n"
            "Your double-sided document is ready in the output tray with correct page order.",
        )
