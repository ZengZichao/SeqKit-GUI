# SPDX-License-Identifier: MIT
"""Draw the SeqKit GUI logo and emit the shipped icon set -- no external artwork.

The mark is drawn with QPainter from parametric geometry, so the whole identity
is code: regenerating is

    python tools/make_logo.py [--preview out/logo-preview.png]

and rewrites ``seqkit_gui/assets/{app-1024.png, app.png, app-32.png, app.ico}``.
The design is a black-and-white minimal tile: a near-black rounded square
carrying an abstract DNA ladder in white -- two rails whose separation breathes
along the axis (the 2D projection of a twist) crossed by base-pair rungs. Every
size is rendered from the geometry rather than downscaled from one bitmap; the
smallest ICO frames drop alternate rungs, which would smear together. The .ico
packs PNG-compressed frames (Vista+), the same layout the previous icon used.
"""

from __future__ import annotations

import argparse
import math
import struct
from pathlib import Path

from PySide6.QtCore import Qt, QBuffer, QIODevice, QPointF, QRectF
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPainterPath, QPen, QPixmap

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "seqkit_gui" / "assets"

#: Monochrome pair: the tile is near-black (a hair off pure black reads softer
#: against pure-white UI surfaces), the glyph pure white.
INK = "#14161a"
PAPER = "#ffffff"

#: Rounded-tile corner radius as a fraction of the tile edge.
CORNER = 0.22

#: Ladder geometry in master (1024) coordinates: the axis runs bottom-left to
#: top-right, and each rail sits ``offset(t)`` from it on either side.
AXIS = (288.0, 768.0, 736.0, 256.0)      # ax, ay, bx, by
RAIL_OFFSET = 118.0                       # separation half-width at its widest
RAIL_UNDULATION = (0.35, 0.65, -0.18)     # a, b, phase: a + b*(0.5+0.5*cos(2pi(t-phase)))
RUNGS_AT = (0.06, 0.22, 0.38, 0.54, 0.70, 0.86)
RUNGS_AT_SMALL = (0.10, 0.37, 0.63, 0.90)  # <=32px frames keep every other rung
RAIL_WIDTH = 58.0
RUNG_WIDTH = 46.0

ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)
PNG_SIZES = {1024: "app-1024.png", 256: "app.png", 32: "app-32.png"}


def _offset(t: float) -> float:
    a, b, phase = RAIL_UNDULATION
    return RAIL_OFFSET * (a + b * (0.5 + 0.5 * math.cos(2.0 * math.pi * (t - phase))))


def _point(t: float, side: float) -> tuple[float, float]:
    ax, ay, bx, by = AXIS
    nx, ny = -(by - ay), bx - ax
    norm = math.hypot(nx, ny)
    o = _offset(t) * side / norm
    return ax + (bx - ax) * t + nx * o, ay + (by - ay) * t + ny * o


def _stroke_pen(colour: QColor, base: float, floor_fraction: float,
                scale: float, size: int) -> QPen:
    # Pen widths are logical units under the painter's scale transform, so a
    # width meant as physical pixels has to be divided back out by ``scale``.
    # The floors are fractions of the tile and bind below 1024px, keeping the
    # 16-64px ICO entries as crisp as the master render.
    physical = max(base * scale, size * floor_fraction)
    return QPen(colour, physical / scale, Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)


def draw_logo(size: int) -> QPixmap:
    """One render of the mark at ``size`` pixels; geometry, not a downscale."""
    scale = size / 1024.0
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    # -- tile ---------------------------------------------------------------
    tile_path = QPainterPath()
    tile_path.addRoundedRect(QRectF(0, 0, size, size), size * CORNER, size * CORNER)
    painter.fillPath(tile_path, QColor(INK))

    # -- ladder -------------------------------------------------------------
    # All ladder geometry is in master (1024) coordinates; the painter maps it
    # onto the actual tile. Pens are computed above in the same master units.
    painter.scale(scale, scale)
    ink = QColor(PAPER)
    rail_pen = _stroke_pen(ink, RAIL_WIDTH, 0.055, scale, size)
    rung_pen = _stroke_pen(ink, RUNG_WIDTH, 0.044, scale, size)
    painter.setPen(rail_pen)
    for side in (1.0, -1.0):
        path = QPainterPath()
        for i in range(61):
            x, y = _point(i / 60.0, side)
            (path.moveTo if i == 0 else path.lineTo)(x, y)
        painter.drawPath(path)

    painter.setPen(rung_pen)
    rungs = RUNGS_AT_SMALL if size <= 32 else RUNGS_AT
    for t in rungs:
        painter.drawLine(QPointF(*_point(t, 1.0)), QPointF(*_point(t, -1.0)))
    painter.end()
    return pixmap


def _png_bytes(pixmap: QPixmap) -> bytes:
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.ReadWrite)
    pixmap.save(buffer, "PNG")
    return bytes(buffer.data())


def build_ico(frames: list[tuple[int, bytes]]) -> bytes:
    header = struct.pack("<HHH", 0, 1, len(frames))
    entries = b""
    body = b""
    for size, data in frames:
        edge = 0 if size == 256 else size
        offset = 6 + 16 * len(frames) + len(body)
        entries += struct.pack("<BBBBHHII", edge, edge, 0, 0, 1, 32, len(data), offset)
        body += data
    return header + entries + body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", type=Path, default=None,
                        help="also write a contact sheet of the sizes here")
    args = parser.parse_args()

    app = QGuiApplication(["make_logo"])  # QPainter needs a QGuiApplication

    ASSETS.mkdir(parents=True, exist_ok=True)
    renders = {size: draw_logo(size) for size in sorted(set(ICO_SIZES) | {1024})}

    for size, name in PNG_SIZES.items():
        renders[size].save(str(ASSETS / name), "PNG")
    frames = [(size, _png_bytes(renders[size])) for size in ICO_SIZES]
    (ASSETS / "app.ico").write_bytes(build_ico(frames))
    for name in ("app.png", "app.ico", "app-32.png", "app-1024.png"):
        path = ASSETS / name
        print(name, path.stat().st_size, "bytes")

    if args.preview:
        columns = ((1024, 300), (256, 256), (64, 128), (32, 64), (16, 32))
        width = sum(shown for _size, shown in columns) + 14 * (len(columns) + 1)
        sheet = QPixmap(width, 330)
        sheet.fill(QColor("#eef1f5"))
        painter = QPainter(sheet)
        x = 14.0
        for size, shown in columns:
            scaled = renders[size].scaled(shown, shown,
                                          Qt.AspectRatioMode.KeepAspectRatio,
                                          Qt.TransformationMode.SmoothTransformation)
            painter.drawPixmap(QPointF(x, (330 - shown) / 2.0), scaled)
            x += shown + 14.0
        painter.end()
        args.preview.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(str(args.preview), "PNG")
        print("preview:", args.preview)

    del app
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
