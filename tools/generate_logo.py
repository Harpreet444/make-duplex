# SPDX-License-Identifier: GPL-3.0-or-later
"""Generate modern logo and icon files for make-duplex."""

import os
import sys

from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import (
    QColor,
    QGuiApplication,
    QIcon,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)

# Offscreen application
app = QGuiApplication.instance() or QGuiApplication(["make-duplex-icon"])

out_dir = os.path.join(os.path.dirname(__file__), "..", "src", "make_duplex", "resources")
os.makedirs(out_dir, exist_ok=True)


def draw_icon(size: int = 256) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)

    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    s = size / 256.0  # Scale factor

    # Background rounded container
    bg_path = QPainterPath()
    bg_rect = QRectF(12 * s, 12 * s, 232 * s, 232 * s)
    bg_path.addRoundedRect(bg_rect, 48 * s, 48 * s)

    bg_grad = QLinearGradient(0, 0, size, size)
    bg_grad.setColorAt(0.0, QColor("#0f172a"))  # Deep slate/navy
    bg_grad.setColorAt(1.0, QColor("#1e293b"))  # Rich charcoal
    p.fillPath(bg_path, bg_grad)

    # Subtle inner glow / border
    border_pen = QPen(QColor(255, 255, 255, 30), 2 * s)
    p.setPen(border_pen)
    p.drawPath(bg_path)

    # 1. Back Sheet (Offset right/up, purple-themed for Back pass)
    back_sheet = QPainterPath()
    back_rect = QRectF(86 * s, 44 * s, 114 * s, 142 * s)
    back_sheet.addRoundedRect(back_rect, 10 * s, 10 * s)

    back_grad = QLinearGradient(86 * s, 44 * s, 200 * s, 186 * s)
    back_grad.setColorAt(0.0, QColor("#7c3aed"))  # Purple
    back_grad.setColorAt(1.0, QColor("#6366f1"))  # Indigo
    p.fillPath(back_sheet, back_grad)
    p.setPen(QPen(QColor(255, 255, 255, 80), 1.5 * s))
    p.drawPath(back_sheet)

    # Mini slides on back sheet
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(255, 255, 255, 90))
    p.drawRoundedRect(QRectF(98 * s, 60 * s, 90 * s, 48 * s), 4 * s, 4 * s)
    p.drawRoundedRect(QRectF(98 * s, 118 * s, 90 * s, 48 * s), 4 * s, 4 * s)

    # 2. Front Sheet (Offset left/down, blue-themed for Front pass)
    front_sheet = QPainterPath()
    front_rect = QRectF(48 * s, 68 * s, 116 * s, 144 * s)
    front_sheet.addRoundedRect(front_rect, 10 * s, 10 * s)

    front_grad = QLinearGradient(48 * s, 68 * s, 164 * s, 212 * s)
    front_grad.setColorAt(0.0, QColor("#ffffff"))
    front_grad.setColorAt(1.0, QColor("#f1f5f9"))
    p.fillPath(front_sheet, front_grad)
    p.setPen(QPen(QColor("#0284c7"), 2.5 * s))
    p.drawPath(front_sheet)

    # Two 2-up slides on front sheet (Cyan/Blue headers)
    p.setBrush(QColor("#e0f2fe"))
    p.setPen(QPen(QColor("#38bdf8"), 1.2 * s))
    # Slide 1 (top)
    p.drawRoundedRect(QRectF(60 * s, 82 * s, 92 * s, 54 * s), 4 * s, 4 * s)
    # Slide 2 (bottom)
    p.drawRoundedRect(QRectF(60 * s, 144 * s, 92 * s, 54 * s), 4 * s, 4 * s)

    # Slide content lines
    p.setBrush(QColor("#0284c7"))
    p.setPen(Qt.PenStyle.NoPen)
    # Top slide mini header & body
    p.drawRoundedRect(QRectF(66 * s, 90 * s, 36 * s, 6 * s), 2 * s, 2 * s)
    p.setBrush(QColor("#94a3b8"))
    p.drawRoundedRect(QRectF(66 * s, 102 * s, 80 * s, 4 * s), 2 * s, 2 * s)
    p.drawRoundedRect(QRectF(66 * s, 112 * s, 60 * s, 4 * s), 2 * s, 2 * s)

    # Bottom slide mini header & body
    p.setBrush(QColor("#0284c7"))
    p.drawRoundedRect(QRectF(66 * s, 152 * s, 36 * s, 6 * s), 2 * s, 2 * s)
    p.setBrush(QColor("#94a3b8"))
    p.drawRoundedRect(QRectF(66 * s, 164 * s, 80 * s, 4 * s), 2 * s, 2 * s)
    p.drawRoundedRect(QRectF(66 * s, 174 * s, 60 * s, 4 * s), 2 * s, 2 * s)

    # 3. Dynamic Flip / Duplex Badge in bottom right
    badge_center = QPointF(182 * s, 178 * s)
    radius = 36 * s
    badge_grad = QLinearGradient(146 * s, 142 * s, 218 * s, 214 * s)
    badge_grad.setColorAt(0.0, QColor("#0284c7"))  # Sky blue
    badge_grad.setColorAt(1.0, QColor("#8b5cf6"))  # Violet
    p.setBrush(badge_grad)
    p.setPen(QPen(QColor("#ffffff"), 3 * s))
    p.drawEllipse(badge_center, radius, radius)

    # Duplex flip arrow symbol inside badge
    arrow_pen = QPen(QColor("#ffffff"), 3.5 * s)
    arrow_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(arrow_pen)
    p.setBrush(Qt.GlobalColor.transparent)

    # Top arc
    top_arc_rect = QRectF(162 * s, 158 * s, 40 * s, 40 * s)
    p.drawArc(top_arc_rect, 30 * 16, 120 * 16)
    # Bottom arc
    p.drawArc(top_arc_rect, 210 * 16, 120 * 16)

    # Arrowheads
    p.setBrush(QColor("#ffffff"))
    p.setPen(Qt.PenStyle.NoPen)
    # Right arrowhead
    p.drawPolygon([
        QPointF(202 * s, 172 * s),
        QPointF(207 * s, 182 * s),
        QPointF(197 * s, 180 * s),
    ])
    # Left arrowhead
    p.drawPolygon([
        QPointF(162 * s, 184 * s),
        QPointF(157 * s, 174 * s),
        QPointF(167 * s, 176 * s),
    ])

    p.end()
    return image


# Generate and save
img_256 = draw_icon(256)
png_path = os.path.join(out_dir, "icon.png")
ico_path = os.path.join(out_dir, "icon.ico")

img_256.save(png_path, "PNG")

# Generate multi-resolution ICO containing 16, 20, 24, 32, 48, 64, 128, 256
import io
import struct
from PyQt6.QtCore import QBuffer, QIODevice

sizes = [16, 20, 24, 32, 48, 64, 128, 256]
png_data = {}

for s in sizes:
    scaled = img_256.scaled(
        s, s, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
    )
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    scaled.save(buf, "PNG")
    png_data[s] = bytes(buf.data())
    buf.close()

# Assemble standard ICO structure
header = struct.pack("<HHH", 0, 1, len(png_data))
offset = 6 + 16 * len(png_data)
entries = []
image_payload = b""

for s, b in png_data.items():
    w = 0 if s == 256 else s
    h = 0 if s == 256 else s
    entry = struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, len(b), offset + len(image_payload))
    entries.append(entry)
    image_payload += b

with open(ico_path, "wb") as f:
    f.write(header + b"".join(entries) + image_payload)

print(f"Generated icon: {png_path} and {ico_path} with sizes {sizes}")
