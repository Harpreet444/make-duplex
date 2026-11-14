# main_window.py — make-duplex
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
main_window.py
~~~~~~~~~~~~~~

Modern PyQt6 main window with side-by-side live preview of physical Front and
Back sheets, full duplex configuration, and guided printing/exporting.
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

import fitz  # PyMuPDF
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStatusBar,
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
    compute_sheet_pairs,
    filter_pages,
    is_landscape,
    parse_page_range,
    render_sheet_preview,
)
from make_duplex.printer import GuidedDuplexPrinter, print_single_side


def get_resource_path(filename: str) -> str:
    """Return the absolute path to an application resource, supporting PyInstaller bundles."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
        candidates = [
            os.path.join(base_path, "make_duplex", "resources", filename),
            os.path.join(base_path, "src", "make_duplex", "resources", filename),
            os.path.join(base_path, "resources", filename),
            os.path.join(base_path, filename),
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        return candidates[0]
    return os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "resources", filename
    )


def get_app_icon() -> QIcon:
    """Return a QIcon initialized with icon.ico (preferred on Windows) and icon.png."""
    ico_path = get_resource_path("icon.ico")
    png_path = get_resource_path("icon.png")
    if os.path.exists(ico_path):
        icon = QIcon(ico_path)
        if os.path.exists(png_path):
            icon.addFile(png_path)
        return icon
    if os.path.exists(png_path):
        return QIcon(png_path)
    return QIcon()


class MainWindow(QMainWindow):
    """
    Main application window for make-duplex.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("make-duplex — N-up Duplex Print Helper")
        self.setMinimumSize(1150, 750)
        self.setAcceptDrops(True)

        # Set window icon (both .ico and .png for high-DPI Windows taskbar & titlebar)
        app_icon = get_app_icon()
        if not app_icon.isNull():
            self.setWindowIcon(app_icon)

        self._src_pdf: fitz.Document | None = None
        self._current_pdf_path: str = ""
        self._total_src_pages: int = 0
        self._selected_page_indices: list[int] = []
        self._sheet_pairs: list[SheetPair] = []
        self._current_sheet_idx: int = 0

        self._cached_front_png: bytes | None = None
        self._cached_back_png: bytes | None = None

        self._setup_ui()
        self._update_ui_state()

    # -----------------------------------------------------------------------
    # UI Setup
    # -----------------------------------------------------------------------

    def _setup_ui(self) -> None:
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        main_layout.addWidget(splitter)

        # Left control panel
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFixedWidth(390)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        control_panel = QWidget()
        left_scroll.setWidget(control_panel)
        panel_layout = QVBoxLayout(control_panel)
        panel_layout.setContentsMargins(0, 0, 8, 0)
        panel_layout.setSpacing(12)

        # Brand Header with Logo
        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(4, 2, 4, 4)
        brand_row.setSpacing(10)

        logo_icon_label = QLabel()
        icon_path = get_resource_path("icon.png")
        if os.path.exists(icon_path):
            logo_pix = QPixmap(icon_path)
            if not logo_pix.isNull():
                logo_icon_label.setPixmap(
                    logo_pix.scaled(
                        38,
                        38,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
        brand_row.addWidget(logo_icon_label)

        brand_text_col = QVBoxLayout()
        brand_text_col.setSpacing(0)
        brand_name = QLabel("make-duplex")
        brand_name.setStyleSheet("font-size: 16px; font-weight: bold; color: #0284c7;")
        brand_tag = QLabel("N-up Manual Duplex Print Helper")
        brand_tag.setStyleSheet("font-size: 11px; color: #64748b;")
        brand_text_col.addWidget(brand_name)
        brand_text_col.addWidget(brand_tag)
        brand_row.addLayout(brand_text_col)
        brand_row.addStretch()

        panel_layout.addLayout(brand_row)

        # 1. PDF File Input Group
        file_group = QGroupBox("1. Source Document")
        file_layout = QVBoxLayout(file_group)
        file_layout.setSpacing(8)

        file_row = QHBoxLayout()
        self._path_edit = QLineEdit()
        self._path_edit.setReadOnly(True)
        self._path_edit.setPlaceholderText("Select or drop a PDF file here...")
        file_row.addWidget(self._path_edit)

        self._browse_btn = QPushButton("Browse...")
        self._browse_btn.clicked.connect(self._on_browse_file)
        file_row.addWidget(self._browse_btn)
        file_layout.addLayout(file_row)

        self._doc_info_label = QLabel("No document loaded.")
        self._doc_info_label.setStyleSheet("color: #64748b; font-size: 11px;")
        file_layout.addWidget(self._doc_info_label)

        panel_layout.addWidget(file_group)

        # 2. Page Range Selection Group
        range_group = QGroupBox("2. Page Selection (Include)")
        range_layout = QVBoxLayout(range_group)
        range_layout.setSpacing(6)

        self._range_edit = QLineEdit()
        self._range_edit.setPlaceholderText("e.g. 1-20, 25, 30-42 (blank = all)")
        self._range_edit.returnPressed.connect(self._on_apply_range)
        range_layout.addWidget(self._range_edit)
        panel_layout.addWidget(range_group)

        # 3. Skip Pages Group
        skip_group = QGroupBox("3. Skip Pages (Exclude)")
        skip_layout = QVBoxLayout(skip_group)
        skip_layout.setSpacing(6)

        skip_input_row = QHBoxLayout()
        self._skip_edit = QLineEdit()
        self._skip_edit.setPlaceholderText("e.g. 3, 7, 12-14 (comma-separated)")
        self._skip_edit.returnPressed.connect(self._on_apply_range)
        skip_input_row.addWidget(self._skip_edit)

        self._apply_range_btn = QPushButton("Apply")
        self._apply_range_btn.clicked.connect(self._on_apply_range)
        skip_input_row.addWidget(self._apply_range_btn)
        skip_layout.addLayout(skip_input_row)

        self._range_status_label = QLabel("Sheets: — | Selected pages: —")
        self._range_status_label.setStyleSheet("font-weight: 500; color: #1e293b; font-size: 11px;")
        skip_layout.addWidget(self._range_status_label)
        panel_layout.addWidget(skip_group)

        # 4. Layout & Duplex Options Group
        opts_group = QGroupBox("4. Layout & Duplex Options")
        opts_layout = QVBoxLayout(opts_group)
        opts_layout.setSpacing(10)

        # N-up combo
        nup_row = QHBoxLayout()
        nup_label = QLabel("Slides per side:")
        nup_label.setFixedWidth(110)
        self._nup_combo = QComboBox()
        self._nup_combo.addItem("1-up (1 slide / page)", (NUp.ONE, SheetOrientation.PORTRAIT))
        self._nup_combo.addItem("2-up (2 slides / landscape page)", (NUp.TWO, SheetOrientation.LANDSCAPE))
        self._nup_combo.addItem("2-up (2 slides / portrait page)", (NUp.TWO, SheetOrientation.PORTRAIT))
        self._nup_combo.addItem("4-up (4 slides / 2x2 grid)", (NUp.FOUR, SheetOrientation.PORTRAIT))
        self._nup_combo.addItem("4-up (4 slides / landscape grid)", (NUp.FOUR, SheetOrientation.LANDSCAPE))
        self._nup_combo.setCurrentIndex(1)  # Default 2-up landscape
        self._nup_combo.currentIndexChanged.connect(self._on_options_changed)
        nup_row.addWidget(nup_label)
        nup_row.addWidget(self._nup_combo)
        opts_layout.addLayout(nup_row)

        # Paper size combo
        paper_row = QHBoxLayout()
        paper_label = QLabel("Paper size:")
        paper_label.setFixedWidth(110)
        self._paper_combo = QComboBox()
        self._paper_combo.addItem("A4 (210 x 297 mm)", PaperSize.A4)
        self._paper_combo.addItem("US Letter (8.5 x 11 in)", PaperSize.LETTER)
        self._paper_combo.currentIndexChanged.connect(self._on_options_changed)
        paper_row.addWidget(paper_label)
        paper_row.addWidget(self._paper_combo)
        opts_layout.addLayout(paper_row)

        # Margin & Gap spacing
        spacing_row = QHBoxLayout()
        m_label = QLabel("Margin (pt):")
        self._margin_spin = QDoubleSpinBox()
        self._margin_spin.setRange(0.0, 72.0)
        self._margin_spin.setValue(18.0)
        self._margin_spin.setSingleStep(2.0)
        self._margin_spin.valueChanged.connect(self._on_options_changed)

        g_label = QLabel("Gap (pt):")
        self._gap_spin = QDoubleSpinBox()
        self._gap_spin.setRange(0.0, 36.0)
        self._gap_spin.setValue(6.0)
        self._gap_spin.setSingleStep(1.0)
        self._gap_spin.valueChanged.connect(self._on_options_changed)

        spacing_row.addWidget(m_label)
        spacing_row.addWidget(self._margin_spin)
        spacing_row.addWidget(g_label)
        spacing_row.addWidget(self._gap_spin)
        opts_layout.addLayout(spacing_row)

        # Tray handling checkboxes
        self._border_check = QCheckBox("Draw thin border around each slide")
        self._border_check.setChecked(True)
        self._border_check.stateChanged.connect(self._on_options_changed)
        opts_layout.addWidget(self._border_check)

        self._reverse_back_check = QCheckBox("Reverse back-side order")
        self._reverse_back_check.setToolTip(
            "For printers with face-up output trays where the printed stack\n"
            "is reversed. Automatically inverts the back-side page order\n"
            "so sheet numbers align after flipping."
        )
        self._reverse_back_check.stateChanged.connect(self._on_options_changed)
        opts_layout.addWidget(self._reverse_back_check)

        self._flip_short_check = QCheckBox("Flip on short edge (top-flip)")
        self._flip_short_check.setToolTip(
            "Rotates all back-side pages 180°. Useful for calendars, legal pads,\n"
            "or short-edge duplex re-insertion."
        )
        self._flip_short_check.stateChanged.connect(self._on_options_changed)
        opts_layout.addWidget(self._flip_short_check)

        panel_layout.addWidget(opts_group)

        # 5. Sheet Navigator Group
        nav_group = QGroupBox("5. Sheet Preview Navigator")
        nav_layout = QVBoxLayout(nav_group)
        nav_layout.setSpacing(8)

        nav_row = QHBoxLayout()
        self._prev_btn = QPushButton("◀ Previous")
        self._prev_btn.clicked.connect(self._on_prev_sheet)
        nav_row.addWidget(self._prev_btn)

        self._sheet_indicator = QLabel("Sheet 0 of 0")
        self._sheet_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sheet_indicator.setStyleSheet("font-weight: bold; font-size: 12px;")
        nav_row.addWidget(self._sheet_indicator)

        self._next_btn = QPushButton("Next ▶")
        self._next_btn.clicked.connect(self._on_next_sheet)
        nav_row.addWidget(self._next_btn)

        nav_layout.addLayout(nav_row)
        panel_layout.addWidget(nav_group)

        # 6. Output Actions Group (2x2 Grid)
        action_group = QGroupBox("6. Output Actions")
        action_grid = QGridLayout(action_group)
        action_grid.setContentsMargins(8, 10, 8, 8)
        action_grid.setSpacing(8)

        # Row 0: Separate Front and Back passes
        self._print_front_btn = QPushButton("🖨  Print Front (Pass 1)")
        self._print_front_btn.setStyleSheet(
            "background-color: #0284c7; color: white; font-weight: bold; "
            "font-size: 11px; padding: 10px 4px; border-radius: 6px;"
        )
        self._print_front_btn.setToolTip("Print all Front-side sheets (Pass 1)")
        self._print_front_btn.clicked.connect(self._on_print_front)
        action_grid.addWidget(self._print_front_btn, 0, 0)

        self._print_back_btn = QPushButton("🖨  Print Back (Pass 2)")
        self._print_back_btn.setStyleSheet(
            "background-color: #7c3aed; color: white; font-weight: bold; "
            "font-size: 11px; padding: 10px 4px; border-radius: 6px;"
        )
        self._print_back_btn.setToolTip("Print all Back-side sheets (Pass 2, after flip)")
        self._print_back_btn.clicked.connect(self._on_print_back)
        action_grid.addWidget(self._print_back_btn, 0, 1)

        # Row 1: Guided Duplex and Export
        self._print_guided_btn = QPushButton("🔄  Guided Print")
        self._print_guided_btn.setStyleSheet(
            "background-color: #334155; color: white; font-weight: 500; "
            "font-size: 11px; padding: 10px 4px; border-radius: 6px;"
        )
        self._print_guided_btn.setToolTip("Guided all-in-one duplex flow (Fronts ➔ Flip Dialog ➔ Backs)")
        self._print_guided_btn.clicked.connect(self._on_print_guided)
        action_grid.addWidget(self._print_guided_btn, 1, 0)

        self._export_btn = QPushButton("💾  Export PDFs")
        self._export_btn.setStyleSheet(
            "background-color: #0f766e; color: white; font-weight: bold; "
            "font-size: 11px; padding: 10px 4px; border-radius: 6px;"
        )
        self._export_btn.setToolTip("Export 1_PRINT_FRONT.pdf and 2_PRINT_BACK.pdf to a folder")
        self._export_btn.clicked.connect(self._on_export_pdfs)
        action_grid.addWidget(self._export_btn, 1, 1)

        panel_layout.addWidget(action_group)
        panel_layout.addStretch()

        splitter.addWidget(left_scroll)

        # Right preview panel
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(8, 0, 0, 0)
        right_layout.setSpacing(8)

        # Top summary title of sheet
        self._sheet_detail_label = QLabel("Physical Sheet Preview")
        self._sheet_detail_label.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #1e293b; padding: 4px;"
        )
        right_layout.addWidget(self._sheet_detail_label)

        # Side by side previews
        previews_row = QHBoxLayout()
        previews_row.setSpacing(16)

        # Front preview box
        front_box = QFrame()
        front_box.setFrameShape(QFrame.Shape.StyledPanel)
        front_box.setStyleSheet("background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px;")
        front_box_layout = QVBoxLayout(front_box)
        front_box_layout.setContentsMargins(10, 10, 10, 10)

        front_header = QLabel("FRONT SIDE (Pass 1)")
        front_header.setStyleSheet("font-weight: bold; color: #0284c7; font-size: 12px;")
        front_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        front_box_layout.addWidget(front_header)

        self._front_label = QLabel("Drop or select a PDF to preview")
        self._front_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._front_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
        self._front_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        front_box_layout.addWidget(self._front_label)

        self._front_pages_info = QLabel("Slides: —")
        self._front_pages_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._front_pages_info.setStyleSheet("font-size: 11px; color: #475569;")
        front_box_layout.addWidget(self._front_pages_info)

        previews_row.addWidget(front_box, stretch=1)

        # Back preview box
        back_box = QFrame()
        back_box.setFrameShape(QFrame.Shape.StyledPanel)
        back_box.setStyleSheet("background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px;")
        back_box_layout = QVBoxLayout(back_box)
        back_box_layout.setContentsMargins(10, 10, 10, 10)

        back_header = QLabel("BACK SIDE (Pass 2, after flip)")
        back_header.setStyleSheet("font-weight: bold; color: #7c3aed; font-size: 12px;")
        back_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        back_box_layout.addWidget(back_header)

        self._back_label = QLabel("Drop or select a PDF to preview")
        self._back_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._back_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
        self._back_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        back_box_layout.addWidget(self._back_label)

        self._back_pages_info = QLabel("Slides: —")
        self._back_pages_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._back_pages_info.setStyleSheet("font-size: 11px; color: #475569;")
        back_box_layout.addWidget(self._back_pages_info)

        previews_row.addWidget(back_box, stretch=1)

        right_layout.addLayout(previews_row, stretch=1)

        splitter.addWidget(right_container)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        # Status Bar
        self.statusBar().showMessage("Ready")

    # -----------------------------------------------------------------------
    # Drag and Drop
    # -----------------------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith(".pdf"):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if path.lower().endswith(".pdf"):
                    self.load_pdf(path)
                    event.acceptProposedAction()
                    return
        event.ignore()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._render_current_preview_pixmaps()

    # -----------------------------------------------------------------------
    # Document Loading & Setup
    # -----------------------------------------------------------------------

    def _on_browse_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select PDF File",
            "",
            "PDF Files (*.pdf)",
        )
        if path:
            self.load_pdf(path)

    @staticmethod
    def _truncate_filename(name: str, max_chars: int = 28) -> str:
        """Truncate a long filename with ellipsis (...) so it doesn't overflow UI."""
        if len(name) <= max_chars:
            return name
        stem, ext = os.path.splitext(name)
        avail = max_chars - len(ext) - 3
        if avail > 4:
            return f"{stem[:avail]}...{ext}"
        return f"{name[: max_chars - 3]}..."

    def load_pdf(self, path: str) -> None:
        """Open a PDF document, validate it, and initialize state."""
        try:
            doc = fitz.open(path)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Error Opening PDF",
                f"Could not open '{os.path.basename(path)}':\n{exc}",
            )
            return

        if len(doc) == 0:
            doc.close()
            QMessageBox.warning(
                self,
                "Empty PDF",
                "The selected PDF contains no pages.",
            )
            return

        if self._src_pdf is not None:
            self._src_pdf.close()

        self._src_pdf = doc
        self._current_pdf_path = path
        self._total_src_pages = len(doc)

        base_name = os.path.basename(path)
        truncated_name = self._truncate_filename(base_name, max_chars=28)

        self._path_edit.setText(path)
        self._path_edit.setToolTip(path)
        self._path_edit.setCursorPosition(0)

        self._doc_info_label.setText(
            f"{truncated_name} ({self._total_src_pages} pages)"
        )
        self._doc_info_label.setToolTip(
            f"{base_name} ({self._total_src_pages} pages)\n{path}"
        )
        self._range_edit.clear()
        self._skip_edit.clear()

        # Default: select all pages
        self._selected_page_indices = list(range(self._total_src_pages))
        self._current_sheet_idx = 0
        self._recompute_sheets()
        self.statusBar().showMessage(f"Loaded: {base_name}", 4000)

    # -----------------------------------------------------------------------
    # Options & Range Logic
    # -----------------------------------------------------------------------

    def _get_current_options(self) -> DuplexOptions:
        combo_val = self._nup_combo.currentData()
        if isinstance(combo_val, tuple):
            nup, orientation = combo_val
        elif isinstance(combo_val, NUp):
            nup, orientation = combo_val, SheetOrientation.AUTO
        else:
            nup, orientation = NUp.TWO, SheetOrientation.LANDSCAPE

        paper = self._paper_combo.currentData() or PaperSize.A4
        return DuplexOptions(
            nup=nup,
            paper=paper,
            orientation=orientation,
            reverse_back=self._reverse_back_check.isChecked(),
            flip_short_edge=self._flip_short_check.isChecked(),
            draw_border=self._border_check.isChecked(),
            margin_pt=self._margin_spin.value(),
            gap_pt=self._gap_spin.value(),
        )

    def _on_apply_range(self) -> None:
        if self._src_pdf is None:
            return

        range_spec = self._range_edit.text()
        skip_spec = self._skip_edit.text()
        try:
            indices = filter_pages(range_spec, skip_spec, self._total_src_pages)
        except ValueError as err:
            QMessageBox.warning(self, "Invalid Page Specification", str(err))
            return

        if not indices:
            QMessageBox.warning(
                self, "No Pages Selected", "All pages have been excluded or range is empty."
            )
            return

        self._selected_page_indices = indices
        self._current_sheet_idx = 0
        self._recompute_sheets()

    def _on_options_changed(self) -> None:
        if self._src_pdf is None:
            return
        self._recompute_sheets()

    def _recompute_sheets(self) -> None:
        if self._src_pdf is None or not self._selected_page_indices:
            self._sheet_pairs = []
            self._current_sheet_idx = 0
            self._update_ui_state()
            return

        opts = self._get_current_options()
        self._sheet_pairs = compute_sheet_pairs(self._selected_page_indices, opts)

        if self._current_sheet_idx >= len(self._sheet_pairs):
            self._current_sheet_idx = max(0, len(self._sheet_pairs) - 1)

        self._update_ui_state()
        self._refresh_preview()

    def _update_ui_state(self) -> None:
        has_pdf = self._src_pdf is not None
        has_sheets = len(self._sheet_pairs) > 0

        self._apply_range_btn.setEnabled(has_pdf)
        self._range_edit.setEnabled(has_pdf)
        self._skip_edit.setEnabled(has_pdf)
        self._nup_combo.setEnabled(has_pdf)
        self._paper_combo.setEnabled(has_pdf)
        self._margin_spin.setEnabled(has_pdf)
        self._gap_spin.setEnabled(has_pdf)
        self._border_check.setEnabled(has_pdf)
        self._reverse_back_check.setEnabled(has_pdf)
        self._flip_short_check.setEnabled(has_pdf)

        self._prev_btn.setEnabled(has_sheets and self._current_sheet_idx > 0)
        self._next_btn.setEnabled(
            has_sheets and self._current_sheet_idx < len(self._sheet_pairs) - 1
        )
        self._print_front_btn.setEnabled(has_sheets)
        self._print_back_btn.setEnabled(has_sheets)
        self._print_guided_btn.setEnabled(has_sheets)
        self._export_btn.setEnabled(has_sheets)

        if has_sheets:
            total_sheets = len(self._sheet_pairs)
            sel_count = len(self._selected_page_indices)
            skipped_count = self._total_src_pages - sel_count
            self._sheet_indicator.setText(
                f"Sheet {self._current_sheet_idx + 1} of {total_sheets}"
            )
            if skipped_count > 0:
                self._range_status_label.setText(
                    f"Sheets: {total_sheets} | Slides: {sel_count} (Skipped: {skipped_count})"
                )
            else:
                self._range_status_label.setText(
                    f"Physical Sheets: {total_sheets} | Selected Slides: {sel_count}"
                )
        else:
            self._sheet_indicator.setText("Sheet 0 of 0")
            self._range_status_label.setText("Sheets: — | Selected pages: —")
            self._sheet_detail_label.setText("Physical Sheet Preview")

    # -----------------------------------------------------------------------
    # Preview Rendering
    # -----------------------------------------------------------------------

    def _on_prev_sheet(self) -> None:
        if self._current_sheet_idx > 0:
            self._current_sheet_idx -= 1
            self._update_ui_state()
            self._refresh_preview()

    def _on_next_sheet(self) -> None:
        if self._current_sheet_idx < len(self._sheet_pairs) - 1:
            self._current_sheet_idx += 1
            self._update_ui_state()
            self._refresh_preview()

    def _refresh_preview(self) -> None:
        if (
            self._src_pdf is None
            or not self._sheet_pairs
            or self._current_sheet_idx >= len(self._sheet_pairs)
        ):
            self._cached_front_png = None
            self._cached_back_png = None
            self._front_label.setText("No sheet to preview")
            self._back_label.setText("No sheet to preview")
            self._front_pages_info.setText("Slides: —")
            self._back_pages_info.setText("Slides: —")
            return

        pair = self._sheet_pairs[self._current_sheet_idx]
        opts = self._get_current_options()

        # Render preview PNGs
        try:
            self._cached_front_png = render_sheet_preview(
                self._src_pdf, pair, side="front", opts=opts, dpi=120
            )
            self._cached_back_png = render_sheet_preview(
                self._src_pdf, pair, side="back", opts=opts, dpi=120
            )
        except Exception as exc:
            self.statusBar().showMessage(f"Preview render error: {exc}", 5000)
            return

        # Update slide labels (convert 0-based to human 1-based)
        front_human = [str(p + 1) for p in pair.front_page_indices]
        back_human = [str(p + 1) for p in pair.back_page_indices]

        front_desc = ", ".join(front_human) if front_human else "Blank"
        back_desc = ", ".join(back_human) if back_human else "Blank"

        self._front_pages_info.setText(f"Front Slides: [{front_desc}]")
        self._back_pages_info.setText(f"Back Slides: [{back_desc}]")
        self._sheet_detail_label.setText(
            f"Physical Sheet {self._current_sheet_idx + 1} of {len(self._sheet_pairs)}  —  "
            f"Front: [{front_desc}] | Back: [{back_desc}]"
        )

        self._render_current_preview_pixmaps()

    def _render_current_preview_pixmaps(self) -> None:
        if self._cached_front_png:
            pix_front = QPixmap()
            pix_front.loadFromData(self._cached_front_png)
            scaled_front = pix_front.scaled(
                self._front_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._front_label.setPixmap(scaled_front)

        if self._cached_back_png:
            pix_back = QPixmap()
            pix_back.loadFromData(self._cached_back_png)
            scaled_back = pix_back.scaled(
                self._back_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._back_label.setPixmap(scaled_back)

    # -----------------------------------------------------------------------
    # Output Actions: Print & Export
    # -----------------------------------------------------------------------

    def _on_print_front(self) -> None:
        """Print front sides only (Pass 1)."""
        if self._src_pdf is None or not self._sheet_pairs:
            return
        opts = self._get_current_options()
        print_single_side(
            self._src_pdf, self._sheet_pairs, side="front", opts=opts, parent=self
        )

    def _on_print_back(self) -> None:
        """Print back sides only (Pass 2)."""
        if self._src_pdf is None or not self._sheet_pairs:
            return
        opts = self._get_current_options()
        print_single_side(
            self._src_pdf, self._sheet_pairs, side="back", opts=opts, parent=self
        )

    def _on_print_guided(self) -> None:
        if self._src_pdf is None or not self._sheet_pairs:
            return

        opts = self._get_current_options()
        printer_driver = GuidedDuplexPrinter(
            self._src_pdf, self._sheet_pairs, opts, parent=self
        )
        printer_driver.run()

    def _on_export_pdfs(self) -> None:
        if self._src_pdf is None or not self._sheet_pairs:
            return

        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Output Folder to Save Duplex PDFs",
            "",
        )
        if not folder:
            return

        opts = self._get_current_options()

        front_filename = "1_PRINT_FRONT.pdf"
        back_filename = "2_PRINT_BACK.pdf"

        front_path = os.path.join(folder, front_filename)
        back_path = os.path.join(folder, back_filename)

        try:
            front_doc = build_document(
                self._src_pdf, self._sheet_pairs, side="front", opts=opts
            )
            front_doc.save(front_path)
            front_doc.close()

            back_doc = build_document(
                self._src_pdf, self._sheet_pairs, side="back", opts=opts
            )
            back_doc.save(back_path)
            back_doc.close()

            QMessageBox.information(
                self,
                "PDF Export Complete",
                f"Successfully exported {len(self._sheet_pairs)} sheets to:\n\n"
                f"• {front_path}\n"
                f"• {back_path}\n\n"
                "Print '1_PRINT_FRONT.pdf', flip the paper stack, then print '2_PRINT_BACK.pdf'!",
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Export Error",
                f"Failed to export PDFs:\n{exc}",
            )

    def closeEvent(self, event) -> None:
        if self._src_pdf is not None:
            self._src_pdf.close()
            self._src_pdf = None
        super().closeEvent(event)
