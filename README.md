# make-duplex

[![License: GPL-3.0](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![PyQt6](https://img.shields.io/badge/UI-PyQt6-green.svg)](https://pypi.org/project/PyQt6/)
[![PyMuPDF](https://img.shields.io/badge/PDF-PyMuPDF%20%28fitz%29-orange.svg)](https://pymupdf.readthedocs.io/)
[![Tests](https://img.shields.io/badge/tests-pytest%2042%20passed-brightgreen.svg)]()

> **make-duplex** is a cross-platform desktop application designed to solve the classic broken page-ordering problem when printing **N-up slides (2-up or 4-up)** on single-sided (non-duplex) printers with a single paper-stack flip.

---

## 📌 The Problem

When using standard printer drivers to manually print double-sided N-up slides:
1. You select *"Print Odd Pages"*, then flip the paper stack and select *"Print Even Pages"*.
2. **This destroys the logical reading order!**

For example, consider an 8-slide PDF printed **2-up**:

### ❌ What Standard "Odd / Even" Manual Duplex Does (BROKEN):
```
Pass 1 (Odd Pages):
  Physical Sheet 1 Front: [Slide 1, Slide 2]
  Physical Sheet 2 Front: [Slide 5, Slide 6]

Pass 2 (Even Pages, after flipping the stack):
  Physical Sheet 1 Back:  [Slide 3, Slide 4]   <-- printed on Sheet 2!
  Physical Sheet 2 Back:  [Slide 7, Slide 8]   <-- printed on Sheet 1!

Result: Sheet 1 has Slides [1, 2] on the front and [7, 8] on the back!
```

---

## 💡 How `make-duplex` Solves It

`make-duplex` groups slides into physical sheet chunks:

$$\text{chunk\_size} = \text{slides\_per\_side} \times 2$$

Each chunk corresponds to exactly **one physical sheet of paper**. The document is decomposed into two passes:
- **Pass 1 (`FRONT`):** Front side of Sheet 1, then Sheet 2, Sheet 3, ...
- **Pass 2 (`BACK`):** Back side of Sheet 1, then Sheet 2, Sheet 3, ... (or reversed for face-up output trays)

### ✅ With `make-duplex` (CORRECT):

```
For 2-up (chunk_size = 2 × 2 = 4 slides per sheet):

Physical Sheet 1:
   Front Side: [Slide 1] [Slide 2]
   Back Side:  [Slide 3] [Slide 4]

Physical Sheet 2:
   Front Side: [Slide 5] [Slide 6]
   Back Side:  [Slide 7] [Slide 8]

Pass 1 prints Fronts:  [Sheet 1 Front, Sheet 2 Front]
User flips the stack ONCE and reloads.
Pass 2 prints Backs:   [Sheet 1 Back,  Sheet 2 Back]

Result: Every back side directly and correctly follows its front side!
```

### 4-Up Imposition Diagram (2×2 Grid)
$$\text{chunk\_size} = 4 \times 2 = 8 \text{ slides per sheet}$$

```
Sheet 1 FRONT                   Sheet 1 BACK (after flip)
┌──────────────┬──────────────┐ ┌──────────────┬──────────────┐
│   Slide 1    │   Slide 2    │ │   Slide 5    │   Slide 6    │
├──────────────┼──────────────┤ ├──────────────┼──────────────┤
│   Slide 3    │   Slide 4    │ │   Slide 7    │   Slide 8    │
└──────────────┴──────────────┘ └──────────────┴──────────────┘
```

---

## ✨ Features

- **Decoupled Architecture:** Core imposition engine is 100% pure Python with PyMuPDF (`fitz`), completely free of PyQt6 dependencies for headless scripting and CLI use.
- **Multiple N-up Formats & Orientations:**
  - `1-up`: Single slide per page.
  - `2-up (Landscape)`: Two slides per page side-by-side (default).
  - `2-up (Portrait)`: Two slides per page stacked vertically (ideal for presentation slide handouts).
  - `4-up (Portrait)`: Four slides per page in a 2×2 grid.
  - `4-up (Landscape)`: Four slides per page in a 2×2 landscape grid.
- **Flexible Paper Sizes:** Supports `A4` (default) and `US Letter`.
- **Drag-and-Drop & File Picker:** Drop any PDF directly onto the application window or use the file dialog.
- **Custom Page Selection, Exclusion & Blank Page Insertion:**
  - Include specific page ranges: e.g. `1-20, 25, 30-42` (blank selects all pages).
  - **Skip / Exclude Pages:** Comma-separated list of pages to omit: e.g. `3, 7, 12-14`.
  - **Blank Pages (Insert):** Insert blank slots at comma-separated slide numbers (e.g. `2, 5, 8`) with configurable positioning (*After page* or *Before page*), ideal for note-taking space or aligning section starts on new physical sheets.
  - Live indicator displaying total physical sheets, active slides, and blank/skipped counts.
- **Live Side-by-Side Preview:** Interactive `Sheet X of Y` navigator showing exact Front and Back previews at high resolution.
- **Tray & Orientation Customizations:**
  - **Reverse back-side order:** Essential for printers with face-up output trays where the output stack reverses order.
  - **Flip on short edge:** Rotates back-side pages 180° for top-flip binding or specific printer tray feeds.
  - **Slide Borders & Margins:** Optional thin borders around each slide with customizable margins and slot gaps.
- **Flexible Output Modes:**
  1. **🖨 Separate Print Buttons:** Dedicated **"Print Front Sides (Pass 1)"** and **"Print Back Sides (Pass 2)"** buttons with native print dialog support (color mode, quality, tray selection).
  2. **🔄 Guided Duplex Printing:** Automated flow that prints fronts, pauses with an interactive flip guide, and prints backs.
  3. **💾 Export PDFs:** Exports `1_PRINT_FRONT.pdf` and `2_PRINT_BACK.pdf` to any selected directory.

---

## 🚀 Installation

### Requirements
- Python 3.11 or newer
- Windows, macOS, or Linux

### Quick Start

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Harpreet444/make-duplex.git
   cd make-duplex
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Launch the application:**
   ```bash
   python run.py
   ```

### Editable Package Install (Optional)
```bash
pip install -e .
make-duplex
```

### Standalone Single-File Executable (PyInstaller)
To build a self-contained `.exe` that runs without installing Python or dependencies:
```bash
pip install pyinstaller
pyinstaller make-duplex.spec
```
The resulting standalone executable is generated in:
```
dist/make-duplex.exe
```

---

## 🖥️ Usage Guide

### 1. Load your PDF
- Click **"Browse..."** or drag-and-drop any PDF file directly into the application window.
- The total page count and file name will be displayed.

### 2. Specify Page Range (Optional)
- Enter ranges like `1-16, 20-32` into the page selection field and click **"Apply"** (or hit Enter).
- Leaving the field blank includes the entire document.

### 3. Choose Layout & Options
- **Slides per side:** Select `1-up`, `2-up`, or `4-up`.
- **Paper size:** Select `A4` or `US Letter`.
- **Tray Options:**
  - Check **"Reverse back-side order"** if your printer discharges paper face-up (meaning the first printed page ends up at the bottom of the stack).
  - Check **"Flip on short edge"** if you want top-bound flip or your printer flips on the short edge.
  - Toggle slide borders and adjust margin / gap spacing in points.

### 4. Verify in Live Preview
- Use **"◀ Previous"** and **"Next ▶"** to inspect each physical sheet.
- Check the side-by-side **Front Side** and **Back Side** views to verify slide numbers before printing.

### 5. Print or Export (2×2 Output Actions)

The output action buttons are organized in a 2×2 grid:

| | Col 1 | Col 2 |
|---|---|---|
| **Row 1** | **🖨 Print Front (Pass 1)** | **🖨 Print Back (Pass 2)** |
| **Row 2** | **🔄 Guided Print** | **💾 Export PDFs** |

#### Option A: Independent Two-Pass Printing
1. Click **"🖨 Print Front (Pass 1)"** to open the system print dialog and print all front-side sheets.
2. Flip and re-insert the printed paper stack into your printer tray.
3. Click **"🖨 Print Back (Pass 2)"** to print all corresponding back-side sheets.

#### Option B: Guided Duplex Print
1. Click **"🔄 Guided Print"**.
2. Select your printer in the system print dialog.
3. Front sheets print automatically, then an interactive **"Flip Paper Stack"** dialog appears:
   ```
   ┌──────────────┐         Flip Stack          ┌──────────────┐
   │ [1] [2]      │    ═════════════════>       │ [3] [4]      │
   │ Front Side   │   (Keep stack order)        │ Back Side    │
   │ Physical #1  │                             │ Physical #1  │
   └──────────────┘                             └──────────────┘
   ```
4. Follow the instructions to flip the stack, then click **"Continue (Print Back Side)"**.

#### Option C: Export PDFs
1. Click **"💾 Export PDFs"**.
2. Select a destination directory.
3. `make-duplex` exports:
   - `1_PRINT_FRONT.pdf`
   - `2_PRINT_BACK.pdf`
4. Use your preferred PDF reader to print each pass.

---

## 📁 Project Structure

```
make-duplex/
├── LICENSE                 # GNU General Public License v3.0
├── README.md               # Documentation and diagrams
├── pyproject.toml          # Build configuration & package metadata
├── requirements.txt        # PyQt6, pymupdf, pytest
├── run.py                  # Direct convenience launcher
├── src/
│   └── make_duplex/
│       ├── __init__.py     # Package metadata
│       ├── engine.py       # Pure-Python PDF parsing, N-up imposition & chunking
│       ├── printer.py      # QPrinter/QPainter driver & Guided Flip dialog
│       ├── main.py         # Application entry point
│       └── ui/
│           ├── __init__.py
│           └── main_window.py # PyQt6 UI with live Front/Back previews
└── tests/
    ├── __init__.py
    ├── test_engine.py      # Core engine unit tests (ordering, chunking, N-up)
    └── test_ui.py          # UI & printer integration tests (headless offscreen)
```

---

## 🧪 Running Tests

Run the comprehensive test suite with `pytest`:

```bash
pytest
```

Or via python module:
```bash
python -m pytest tests/ -v
```

All 42 test cases cover:
- Page range parsing, edge cases, and deduplication
- Skip / exclude pages filtering (comma-separated and ranges)
- Blank page insertion (*after* or *before* specified pages, with duplicates and skipped-page alignment)
- Even, odd, and incomplete sheet chunking for 1-up, 2-up, and 4-up
- 2-up portrait orientation (stacked vertically) vs. landscape (side-by-side)
- Face-up reverse tray ordering
- 180° short-edge rotation
- Grayscale and color raster printing via `QPrintDialog`
- Independent Front and Back side printing
- PDF document composition and PNG raster preview rendering
- PyQt6 window lifecycle, file loading, layout switches, blank page UI interactions, and printer dialogs

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Ensure all tests pass (`pytest`)
5. Push to the branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

---

## 📄 License

Distributed under the **GNU General Public License v3.0 (GPL-3.0-or-later)**. See [`LICENSE`](LICENSE) for details.
