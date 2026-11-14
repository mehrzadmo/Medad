"""
Medad - draw and write on top of your screen (Windows / Linux)

Install:  pip install PySide6 pynput qtawesome
          (qtawesome = Font Awesome icons; optional, built-in icons are used without it)
Run:      python medad.py

Tools:    Select | Pen | Highlighter | Eraser | Line / Arrow / Rectangle / Ellipse | Text | Font
Select tool:
  Click = select | Shift+click = add/remove | drag on empty space = marquee selection
  Drag = move | corner handles = resize | circle above the frame = rotate (Shift = 15 deg steps)
  Double-click a text = edit it.  Color / thickness / font apply to the selection.
Text:     click with the Text tool and type.  Ctrl+Enter or click outside = confirm, Esc = cancel
Keys:     Delete = remove | Ctrl+D = duplicate | Ctrl+A = select all | Ctrl+Z / Ctrl+Y = undo / redo | Esc = quit
Hotkey:   Ctrl+Alt+D toggles Interact mode (click through to the apps underneath)
Menu (...): Settings (theme, toolbar and icon size), save / load drawings as JSON.

Icons: Phosphor Icons (MIT) via qtawesome; Font Awesome Free (CC BY 4.0) as fallback.
"""
import sys
import os
import math
import json
import random
import signal
from datetime import datetime

os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.fonts=false")   # DirectWrite warnings for legacy Windows fonts
os.environ.setdefault("QT_API", "pyside6")                         # for qtawesome

# On Linux/Wayland run through XWayland (xcb): transparent always-on-top windows work much better there
if (sys.platform.startswith("linux") and os.environ.get("XDG_SESSION_TYPE") == "wayland"
        and "QT_QPA_PLATFORM" not in os.environ):
    os.environ["QT_QPA_PLATFORM"] = "xcb"

try:
    import qtawesome as qta          # Font Awesome 6 icons
except Exception:
    qta = None

from PySide6.QtCore import (Qt, QPointF, QPoint, QRectF, QRect, QLineF, QSize, QTimer, Signal, QObject,
                            QEvent, QSettings)
from PySide6.QtGui import (QPainter, QPen, QColor, QPolygonF, QPainterPath, QFont, QFontMetricsF,
                           QGuiApplication, QShortcut, QKeySequence, QPixmap, QIcon, QFontDatabase,
                           QImage, QScreen, QBrush, QIntValidator)
from PySide6.QtWidgets import (QApplication, QWidget, QHBoxLayout, QVBoxLayout, QBoxLayout, QGridLayout,
                               QPushButton, QSlider, QColorDialog, QFileDialog, QLabel, QPlainTextEdit,
                               QMessageBox, QFrame, QMenu, QGraphicsDropShadowEffect, QLineEdit,
                               QListWidget, QListWidgetItem, QToolTip, QDialog, QButtonGroup)

APP_NAME = "Medad"
ROT = ("rect", "ellipse", "text")      # shapes stored with a rotation angle
VALID_TOOLS = {"pen", "highlighter", "line", "arrow", "rect", "ellipse", "text"}
SHAPES = ("line", "arrow", "rect", "ellipse")
SHAPE_TIPS = {"line": "Line", "arrow": "Arrow", "rect": "Rectangle", "ellipse": "Ellipse"}
COLORS = ["#27AE60", "#1FD430", "#00FF18",
          "#1C6A9D", "#00ADEF", "#00F0FF",
          "#BF2110", "#E74C3C", "#FF0000",
          "#911253", "#DC0B76", "#F55096",
          "#F1C40F", "#FEF200", "#FFF36A",
          "#D35400", "#E67E22", "#FF7800",
          "#FFFFFF", "#595B5C", "#402B56",
          "#BDC3C7", "#000000", "#502D1D"]
DEFAULT_COLOR = "#FF0B88"
HANDLE = 10
ROT_OFFSET = 28

# pen styles for lines, shapes and text: (key, label)
STYLES = [("solid", "Standard"), ("pencil", "Pencil"), ("ballpoint", "Ballpoint pen"),
          ("fountain", "Fountain pen"), ("marker", "Marker"), ("brush", "Brush"),
          ("chalk", "Chalk"), ("dashed", "Dashed")]
STYLE_WIDTH = {"solid": 1.0, "pencil": 0.9, "ballpoint": 0.55, "fountain": 1.0,
               "marker": 1.7, "brush": 1.3, "chalk": 1.3, "dashed": 1.0}

# ---------------------------------------------------------------- themes (Windows 11 / Fluent look)
THEMES = {
    "dark": dict(bg="#2c2c2c", border="#3f3f3f", sep="#404040", hover="#383838", pressed="#323232", sel="#3b3b3b",
                 accent="#60cdff", accent_hover="#7fd6ff", on_accent="#000000", badge="#0078d4",
                 icon="#ffffff", text="#ffffff", field="#313131", field_border="#454545", field_hover="#383838",
                 list_bg="#272727", list_border="#3f3f3f", handle="#5a5a5a", groove="#8a8a8a",
                 ring_handle="#d0d0d0", tip_bg="#2c2c2c", tip_text="#ffffff", tip_border="#454545",
                 ring="#555555", ring_sel="#ffffff", dot_ring="#777777", close_hover="#c42b1c", shadow=140),
    "light": dict(bg="#f9f9f9", border="#e0e0e0", sep="#e3e3e3", hover="#eeeeee", pressed="#e6e6e6", sel="#e9e9e9",
                  accent="#0067c0", accent_hover="#0f78d4", on_accent="#ffffff", badge="#0078d4",
                  icon="#1a1a1a", text="#1a1a1a", field="#fdfdfd", field_border="#d6d6d6", field_hover="#f3f3f3",
                  list_bg="#ffffff", list_border="#e0e0e0", handle="#b4b4b4", groove="#8c8c8c",
                  ring_handle="#ffffff", tip_bg="#f9f9f9", tip_text="#1a1a1a", tip_border="#d6d6d6",
                  ring="#c4c4c4", ring_sel="#1a1a1a", dot_ring="#9a9a9a", close_hover="#e5484d", shadow=60),
}
THEME = dict(THEMES["dark"])             # current theme tokens (updated in place)
UI = {"btn": 40, "icon": 22, "badge": 60, "vertical": True, "weight": "light"}   # sizes (px), badge opacity (%), orientation, icon weight
DEFAULTS = {"theme": "dark", "btn": 40, "icon": 22, "badge": 60, "weight": "light"}
WEIGHTS = ("thin", "light", "regular", "bold")
WEIGHT_SUFFIX = {"thin": "-thin", "light": "-light", "regular": "", "bold": "-bold"}      # Phosphor icon variants
WEIGHT_STROKE = {"thin": 0.8, "light": 1.2, "regular": 1.6, "bold": 2.3}                 # stroke of the drawn icons


def refresh_metrics():
    """Corner radii follow the button size: rounder toolbar, Fluent-style controls."""
    THEME["bar_r"] = max(14, int(UI["btn"] * 0.55))
    THEME["btn_r"] = max(8, int(UI["btn"] * 0.28))
    THEME["fly_r"] = 12


refresh_metrics()

BAR_QSS = """
QFrame#bar { background:@bg@; border:1px solid @border@; border-radius:@bar_r@px; }
QFrame#sep { background:@sep@; border:none; }
QLabel { background:transparent; border:none; }
QPushButton { background:transparent; border:none; border-radius:@btn_r@px; }
QPushButton:hover { background:@hover@; }
QPushButton:pressed { background:@pressed@; }
QPushButton:checked { background:@sel@; }
QPushButton:checked:hover { background:@hover@; }
QPushButton#close:hover { background:@close_hover@; }
QToolTip { background:@tip_bg@; color:@tip_text@; border:1px solid @tip_border@; padding:5px 8px; }
"""

FLY_QSS = """
QFrame#fly { background:@bg@; border:1px solid @border@; border-radius:@fly_r@px; }
QLabel { color:@text@; background:transparent; font-size:12px; }
QPushButton { color:@text@; background:transparent; border:none; border-radius:@btn_r@px; }
QPushButton:hover { background:@hover@; }
QPushButton:pressed { background:@pressed@; }
QPushButton:checked { background:@sel@; }
QPushButton#more { color:@text@; background:@field@; border:1px solid @field_border@; border-radius:6px; padding:7px 12px; font-size:12px; }
QPushButton#more:hover { background:@field_hover@; }
QLineEdit { background:@field@; color:@text@; border:1px solid @field_border@; border-radius:6px; padding:5px 8px; selection-background-color:@accent@; selection-color:@on_accent@; }
QLineEdit:focus { border-bottom:2px solid @accent@; }
QListWidget { background:@list_bg@; color:@text@; border:1px solid @list_border@; border-radius:8px; outline:0; padding:2px; }
QListWidget::item { padding:4px 8px; border-radius:5px; margin:1px 0; }
QListWidget::item:hover { background:@hover@; }
QListWidget::item:selected { background:@sel@; color:@text@; border-left:3px solid @accent@; }
QScrollBar:vertical { background:transparent; width:10px; margin:2px; }
QScrollBar::handle:vertical { background:@handle@; border-radius:3px; min-height:24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
QSlider::groove:horizontal { height:4px; background:@groove@; border-radius:2px; }
QSlider::sub-page:horizontal { background:@accent@; border-radius:2px; }
QSlider::handle:horizontal { background:@accent@; border:4px solid @ring_handle@; width:12px; height:12px; margin:-8px 0; border-radius:10px; }
QToolTip { background:@tip_bg@; color:@tip_text@; border:1px solid @tip_border@; padding:5px 8px; }
"""

MENU_QSS = """
QMenu { background:@bg@; color:@text@; border:1px solid @border@; border-radius:8px; padding:5px; }
QMenu::item { padding:7px 26px 7px 14px; border-radius:4px; margin:1px 2px; }
QMenu::item:selected { background:@hover@; color:@text@; }
QMenu::separator { height:1px; background:@sep@; margin:5px 8px; }
"""

DLG_QSS = """
QDialog, QMessageBox { background:@bg@; }
QLabel { color:@text@; font-size:13px; background:transparent; }
QPushButton { color:@text@; background:@field@; border:1px solid @field_border@; border-radius:6px; padding:6px 16px; font-size:13px; }
QPushButton:hover { background:@field_hover@; }
QPushButton:checked { background:@accent@; border-color:@accent@; color:@on_accent@; }
QSlider::groove:horizontal { height:4px; background:@groove@; border-radius:2px; }
QSlider::sub-page:horizontal { background:@accent@; border-radius:2px; }
QSlider::handle:horizontal { background:@accent@; border:4px solid @ring_handle@; width:12px; height:12px; margin:-8px 0; border-radius:10px; }
"""


def qss(template):
    for k, v in THEME.items():
        template = template.replace(f"@{k}@", str(v))
    return template


def show_message(title, text, icon=QMessageBox.Warning, pixmap=None):
    m = QMessageBox(icon, title, text)
    if pixmap is not None:
        m.setIconPixmap(pixmap)
    m.setWindowFlag(Qt.WindowStaysOnTopHint, True)
    m.setAttribute(Qt.WA_QuitOnClose, False)
    m.setStyleSheet(qss(DLG_QSS))
    m.exec()


# ---------------------------------------------------------------- geometry / font helpers
def seg_dist(p, a, b):
    abx, aby = b.x() - a.x(), b.y() - a.y()
    l2 = abx * abx + aby * aby
    if l2 == 0:
        return QLineF(p, a).length()
    t = max(0.0, min(1.0, ((p.x() - a.x()) * abx + (p.y() - a.y()) * aby) / l2))
    return QLineF(p, QPointF(a.x() + t * abx, a.y() + t * aby)).length()


def rot_pt(p, c, a):
    cs, sn = math.cos(a), math.sin(a)
    dx, dy = p.x() - c.x(), p.y() - c.y()
    return QPointF(c.x() + dx * cs - dy * sn, c.y() + dx * sn + dy * cs)


def make_font(size, family="", bold=False, italic=False):
    f = QFont()
    if family:
        f.setFamily(family)
    f.setBold(bold)
    f.setItalic(italic)
    f.setPixelSize(max(6, int(size)))
    return f


def text_size(text, size, family="", bold=False, italic=False):
    r = QFontMetricsF(make_font(size, family, bold, italic)).boundingRect(
        QRectF(0, 0, 100000, 100000), Qt.AlignLeft | Qt.AlignTop, text or " ")
    return r.width() + 4, r.height() + 2


class Stroke:
    def __init__(self, tool, color, width, pts, rot=0.0, text="", size=0.0,
                 family="", bold=False, italic=False, style="solid", seed=None):
        self.tool, self.color, self.width, self.pts = tool, QColor(color), width, pts
        self.rot, self.text, self.size = rot, text, size
        self.family, self.bold, self.italic = family, bold, italic
        self.style = style if style in STYLE_WIDTH else "solid"
        self.seed = random.getrandbits(30) if seed is None else int(seed)     # fixed noise for textured styles

    def copy(self):
        return Stroke(self.tool, QColor(self.color), self.width, [QPointF(p) for p in self.pts],
                      self.rot, self.text, self.size, self.family, self.bold, self.italic,
                      self.style, self.seed)

    def font(self):
        return make_font(self.size, self.family, self.bold, self.italic)

    def tsize(self):
        return text_size(self.text, self.size, self.family, self.bold, self.italic)

    def eff_width(self):
        if self.tool == "text":
            return 0
        if self.tool == "highlighter":
            return self.width * 4
        return self.width * STYLE_WIDTH.get(self.style, 1.0)

    def local_rect(self):
        if self.tool == "text":
            w, h = self.tsize()
            return QRectF(self.pts[0].x(), self.pts[0].y(), w, h)
        return QRectF(self.pts[0], self.pts[-1]).normalized()

    def center(self):
        return self.local_rect().center()

    def segments(self):
        pts = self.pts
        if self.tool in ("pen", "highlighter"):
            return [(pts[0], pts[0])] if len(pts) == 1 else list(zip(pts, pts[1:]))
        if len(pts) < 2:
            return []
        if self.tool in ("line", "arrow"):
            return [(pts[0], pts[-1])]
        r = self.local_rect()
        if self.tool == "rect":
            c = [r.topLeft(), r.topRight(), r.bottomRight(), r.bottomLeft()]
            return [(c[i], c[(i + 1) % 4]) for i in range(4)]
        n = 64
        e = [QPointF(r.center().x() + r.width() / 2 * math.cos(2 * math.pi * i / n),
                     r.center().y() + r.height() / 2 * math.sin(2 * math.pi * i / n)) for i in range(n)]
        return [(e[i], e[(i + 1) % n]) for i in range(n)]

    def bbox(self):
        if self.tool in ROT:
            r = self.local_rect()
            c = r.center()
            cs = [r.topLeft(), r.topRight(), r.bottomRight(), r.bottomLeft()]
            if self.rot:
                cs = [rot_pt(q, c, self.rot) for q in cs]
            xs, ys = [q.x() for q in cs], [q.y() for q in cs]
            pad = 3 if self.tool == "text" else self.eff_width() / 2 + 2
        else:
            xs, ys = [p.x() for p in self.pts], [p.y() for p in self.pts]
            pad = self.eff_width() / 2 + 2
        return QRectF(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)).adjusted(-pad, -pad, pad, pad)

    def frame_points(self):
        """Points that define the extent of the shape (rotation included) for the oriented selection frame."""
        if self.tool in ROT:
            r = self.local_rect()
            c = r.center()
            cs = [r.topLeft(), r.topRight(), r.bottomRight(), r.bottomLeft()]
            return [rot_pt(q, c, self.rot) for q in cs] if self.rot else cs
        return list(self.pts)

    def pad(self):
        return 3.0 if self.tool == "text" else self.eff_width() / 2 + 2

    def near(self, pos, tol):
        if self.tool in ROT and self.rot:
            pos = rot_pt(pos, self.center(), -self.rot)
        if self.tool == "text":
            return self.local_rect().adjusted(-tol, -tol, tol, tol).contains(pos)
        return any(seg_dist(pos, a, b) < tol for a, b in self.segments())

    def hit(self, pos):
        return self.near(pos, max(self.eff_width() / 2, 3) + 6)

    def to_dict(self):
        return {"tool": self.tool, "color": self.color.name(QColor.HexArgb), "width": self.width,
                "pts": [[p.x(), p.y()] for p in self.pts], "rot": self.rot,
                "text": self.text, "size": self.size,
                "family": self.family, "bold": self.bold, "italic": self.italic,
                "style": self.style, "seed": self.seed}

    @staticmethod
    def from_dict(o):
        if o["tool"] not in VALID_TOOLS or not o["pts"]:
            raise ValueError("bad stroke")
        return Stroke(o["tool"], QColor(o["color"]), float(o["width"]),
                      [QPointF(float(x), float(y)) for x, y in o["pts"]],
                      float(o.get("rot", 0.0)), str(o.get("text", "")), float(o.get("size", 0.0)),
                      str(o.get("family", "")), bool(o.get("bold", False)), bool(o.get("italic", False)),
                      str(o.get("style", "solid")), o.get("seed"))


# ---------------------------------------------------------------- pen styles (lines, shapes and text)
_TEX = {}


def grain_brush(kind, color):
    """Tiled grain texture (pencil / chalk / bristle streaks) in the given color; cached."""
    col = QColor(color)
    key = (kind, col.rgb())
    if key in _TEX:
        return _TEX[key]
    rng = random.Random({"pencil": 7, "chalk": 11, "streak": 5}[kind])
    size = 64 if kind == "streak" else 96
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    r, g, b = col.red(), col.green(), col.blue()
    for y in range(size):
        row_a = int(150 + 105 * rng.random())                 # streak: one opacity per row = bristle lines
        for x in range(size):
            if kind == "streak":
                a = row_a if rng.random() > 0.12 else int(row_a * 0.4)
            elif kind == "pencil":
                a = int(255 * (0.5 + 0.5 * rng.random())) if rng.random() > 0.26 else int(80 * rng.random())
            else:
                a = int(255 * (0.55 + 0.45 * rng.random())) if rng.random() > 0.48 else int(40 * rng.random())
            img.setPixelColor(x, y, QColor(r, g, b, a))
    br = QBrush(QPixmap.fromImage(img))
    _TEX[key] = br
    return br


def _path(pts):
    path = QPainterPath(pts[0])
    for q in pts[1:]:
        path.lineTo(q)
    return path


def _resample(pts, step):
    if len(pts) < 2:
        return list(pts)
    out = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        d = QLineF(a, b).length()
        if d == 0:
            continue
        n = max(1, int(d / step))
        for i in range(1, n + 1):
            out.append(QPointF(a.x() + (b.x() - a.x()) * i / n, a.y() + (b.y() - a.y()) * i / n))
    return out


def _decimate(pts, min_dist):
    """Drop points closer than min_dist to the previous kept point (keeps the last one)."""
    if len(pts) < 3:
        return list(pts)
    out = [pts[0]]
    for q in pts[1:-1]:
        if QLineF(out[-1], q).length() >= min_dist:
            out.append(q)
    out.append(pts[-1])
    return out


def _jitter(pts, amp, rng):
    return [QPointF(q.x() + rng.uniform(-amp, amp), q.y() + rng.uniform(-amp, amp)) for q in pts]


NIB_ANGLE = -math.pi / 4            # fountain pen: flat nib at 45 degrees


def stroke_polyline(p, pts, c, w, style, seed, closed=False):
    """Draw one polyline with a pen style. w = nominal line width (already scaled for the style)."""
    if closed:
        pts = list(pts) + [pts[0]]
    if len(pts) < 2:
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        p.drawEllipse(pts[0], w / 2, w / 2)
        return
    rng = random.Random(seed)
    p.setBrush(Qt.NoBrush)
    if style in ("pencil", "chalk", "fountain", "brush"):
        pts = _decimate(pts, 1.6)                       # dense mouse samples add cost, not quality
    if style == "pencil":
        rp = _resample(pts, 3)
        g = grain_brush("pencil", c)
        for amp, ww, op in ((w * 0.10, w, 0.95), (w * 0.18, w * 0.6, 0.65)):   # two slightly offset graphite passes
            p.save()
            p.setOpacity(op)
            p.setPen(QPen(g, ww, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPath(_path(_jitter(rp, amp, rng)))
            p.restore()
    elif style == "ballpoint":
        col = QColor(c)
        col.setAlpha(238)
        p.setPen(QPen(col, w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(_path(pts))
        p.setPen(Qt.NoPen)                              # ink blobs where the pen touches / leaves the paper
        p.setBrush(c)
        for q in (pts[0], pts[-1]):
            p.drawEllipse(q, w * 0.78, w * 0.78)
    elif style == "fountain":
        rp = _resample(pts, 4)
        L = w * 2.0
        nx, ny = math.cos(NIB_ANGLE) * L / 2, math.sin(NIB_ANGLE) * L / 2
        path = QPainterPath()
        path.setFillRule(Qt.WindingFill)
        for a, b in zip(rp, rp[1:]):                    # sweep the flat nib along the path
            cross = (b.x() - a.x()) * ny - (b.y() - a.y()) * nx
            if abs(cross) < 1e-6:
                continue
            quad = [QPointF(a.x() - nx, a.y() - ny), QPointF(b.x() - nx, b.y() - ny),
                    QPointF(b.x() + nx, b.y() + ny), QPointF(a.x() + nx, a.y() + ny)]
            if cross < 0:
                quad.reverse()                          # same orientation everywhere -> one seamless fill
            path.addPolygon(QPolygonF(quad))
            path.closeSubpath()
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        p.drawPath(path)
        p.setBrush(Qt.NoBrush)                          # hairline: strokes along the nib stay visible
        p.setPen(QPen(c, max(1.0, w * 0.16), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(_path(rp))
    elif style == "marker":
        col = QColor(c)
        col.setAlpha(205)
        p.setPen(QPen(col, w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(_path(pts))
    elif style == "brush":
        rp = _resample(pts, 3)
        n = len(rp)
        cum = [0.0]
        for a, b in zip(rp, rp[1:]):
            cum.append(cum[-1] + QLineF(a, b).length())
        total = cum[-1] or 1.0
        left, right = [], []
        for i, q in enumerate(rp):                      # thin at both ends, full width in the middle
            t = cum[i] / total
            hw = w * 0.5 * (0.14 + 0.86 * math.sin(math.pi * t) ** 0.6)
            a, b = rp[max(0, i - 2)], rp[min(n - 1, i + 2)]
            dx, dy = b.x() - a.x(), b.y() - a.y()
            ln = math.hypot(dx, dy) or 1.0
            nx, ny = -dy / ln, dx / ln
            left.append(QPointF(q.x() + nx * hw, q.y() + ny * hw))
            right.append(QPointF(q.x() - nx * hw, q.y() - ny * hw))
        path = QPainterPath()
        path.addPolygon(QPolygonF(left + right[::-1]))
        path.closeSubpath()
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        p.drawPath(path)
    elif style == "chalk":
        rp = _resample(pts, 3)
        g = grain_brush("chalk", c)
        for amp, ww, op in ((w * 0.10, w, 1.0), (w * 0.22, w * 0.65, 0.75)):
            p.save()
            p.setOpacity(op)
            p.setPen(QPen(g, ww, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPath(_path(_jitter(rp, amp, rng)))
            p.restore()
        dust = QColor(c)                                # chalk dust around the line
        dust.setAlpha(120)
        p.setPen(Qt.NoPen)
        p.setBrush(dust)
        for q in rp[::3]:
            for _ in range(2):
                rr = rng.uniform(0.3, 1.0) * max(0.5, w * 0.09)
                p.drawEllipse(QPointF(q.x() + rng.uniform(-1, 1) * w * 0.75,
                                      q.y() + rng.uniform(-1, 1) * w * 0.75), rr, rr)
    elif style == "dashed":
        pen = QPen(c, w, Qt.CustomDashLine, Qt.FlatCap, Qt.RoundJoin)
        pen.setDashPattern([3.0, 2.0])
        p.setPen(pen)
        p.drawPath(_path(pts))
    else:                                               # standard
        p.setPen(QPen(c, w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(_path(pts))


def tool_polylines(s):
    """Outline of a stroke as polylines [(points, closed)] in its own (unrotated) coordinates."""
    pts = s.pts
    if s.tool in ("pen", "highlighter"):
        return [(list(pts), False)]
    if len(pts) < 2:
        return []
    a, b = pts[0], pts[-1]
    if s.tool == "line":
        return [([a, b], False)]
    if s.tool == "arrow":
        ang = math.atan2(b.y() - a.y(), b.x() - a.x())
        size = max(14, s.width * 4)
        h1 = QPointF(b.x() - size * math.cos(ang - 0.45), b.y() - size * math.sin(ang - 0.45))
        h2 = QPointF(b.x() - size * math.cos(ang + 0.45), b.y() - size * math.sin(ang + 0.45))
        return [([a, b], False), ([h1, b], False), ([h2, b], False)]
    r = s.local_rect()
    if s.tool == "rect":
        return [([r.topLeft(), r.topRight(), r.bottomRight(), r.bottomLeft()], True)]
    n = 96
    return [([QPointF(r.center().x() + r.width() / 2 * math.cos(2 * math.pi * i / n),
                      r.center().y() + r.height() / 2 * math.sin(2 * math.pi * i / n)) for i in range(n)], True)]


def paint_text(p, s, c):
    r = s.local_rect()
    if s.style == "solid":
        p.setPen(c)
        p.setFont(s.font())
        p.drawText(r, Qt.AlignLeft | Qt.AlignAbsolute | Qt.AlignTop | Qt.TextDontClip, s.text)
        return
    font = s.font()
    fm = QFontMetricsF(font)
    path = QPainterPath()
    for i, line in enumerate(s.text.split("\n")):
        path.addText(QPointF(r.left(), r.top() + fm.ascent() + i * fm.lineSpacing()), font, line)
    size, style = s.size, s.style
    if style == "pencil":
        g = grain_brush("pencil", c)
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawPath(path)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(g, max(0.7, size * 0.02)))
        p.drawPath(path)
    elif style == "ballpoint":
        fill = QColor(c)
        fill.setAlpha(238)
        p.setPen(QPen(QColor(c).darker(125), max(0.6, size * 0.016)))
        p.setBrush(fill)
        p.drawPath(path)
    elif style == "fountain":
        shadow = QColor(c)                              # soft ink bleed
        shadow.setAlpha(70)
        p.save()
        p.translate(size * 0.04, size * 0.04)
        p.setPen(Qt.NoPen)
        p.setBrush(shadow)
        p.drawPath(path)
        p.restore()
        p.setPen(QPen(c, max(0.6, size * 0.012)))
        p.setBrush(c)
        p.drawPath(path)
    elif style == "marker":
        col = QColor(c)
        col.setAlpha(205)
        p.setPen(QPen(col, max(1.0, size * 0.07), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(col)
        p.drawPath(path)
    elif style == "brush":
        edge = QColor(c)
        edge.setAlpha(170)
        p.setPen(QPen(edge, max(1.0, size * 0.035), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(grain_brush("streak", c))
        p.drawPath(path)
    elif style == "chalk":
        dust = QColor(c)
        dust.setAlpha(90)
        p.save()
        p.translate(size * 0.025, size * 0.02)
        p.setPen(Qt.NoPen)
        p.setBrush(dust)
        p.drawPath(path)
        p.restore()
        g = grain_brush("chalk", c)
        p.setPen(QPen(g, max(0.8, size * 0.03)))
        p.setBrush(g)
        p.drawPath(path)
    elif style == "dashed":
        pen = QPen(c, max(1.0, size * 0.04), Qt.CustomDashLine, Qt.FlatCap, Qt.RoundJoin)
        pen.setDashPattern([3.0, 2.0])
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)


def paint_stroke(p, s):
    c = QColor(s.color)
    if s.tool == "highlighter":
        c.setAlpha(110)
    p.save()
    if s.tool in ROT and s.rot:
        ctr = s.center()
        p.translate(ctr)
        p.rotate(math.degrees(s.rot))
        p.translate(-ctr.x(), -ctr.y())
    if s.tool == "text":
        paint_text(p, s, c)
        p.restore()
        return
    style = "solid" if s.tool == "highlighter" else s.style
    w = s.eff_width()
    pts = s.pts
    if style == "solid":
        p.setPen(QPen(c, w, Qt.SolidLine, Qt.FlatCap if s.tool == "highlighter" else Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        if s.tool in ("pen", "highlighter"):
            if len(pts) == 1:
                p.drawPoint(pts[0])
            else:
                p.drawPath(_path(pts))
        elif len(pts) >= 2:
            a, b = pts[0], pts[-1]
            if s.tool == "line":
                p.drawLine(a, b)
            elif s.tool == "rect":
                p.drawRect(s.local_rect())
            elif s.tool == "ellipse":
                p.drawEllipse(s.local_rect())
            elif s.tool == "arrow":
                p.drawLine(a, b)
                ang = math.atan2(b.y() - a.y(), b.x() - a.x())
                size = max(14, s.width * 4)
                h = QPolygonF([b,
                               QPointF(b.x() - size * math.cos(ang - 0.45), b.y() - size * math.sin(ang - 0.45)),
                               QPointF(b.x() - size * math.cos(ang + 0.45), b.y() - size * math.sin(ang + 0.45))])
                p.setBrush(c)
                p.drawPolygon(h)
    else:
        for i, (pl, closed) in enumerate(tool_polylines(s)):
            stroke_polyline(p, pl, c, w, style, (s.seed or 0) + i * 7919, closed)
    p.restore()


def style_preview(key, color, w=150, h=34):
    """Small preview image of a style: a wavy line plus a styled 'Abc'."""
    pm = QPixmap(w * 2, h * 2)
    pm.setDevicePixelRatio(2)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    wave = [QPointF(8 + i * 3.0, 17 + 7 * math.sin(i / 24 * 2 * math.pi * 1.2)) for i in range(25)]
    paint_stroke(p, Stroke("pen", color, 4, wave, style=key, seed=5))
    paint_stroke(p, Stroke("text", color, 4, [QPointF(96, 3)], 0.0, "Abc", 26, style=key, seed=5))
    p.end()
    return pm


# ---------------------------------------------------------------- icons
def _pts(*a):
    return QPolygonF([QPointF(a[i], a[i + 1]) for i in range(0, len(a), 2)])


def draw_icon(name, color="#eeeeee"):
    """Built-in vector icons (fallback when qtawesome is not installed)"""
    pm = QPixmap(48, 48)
    pm.setDevicePixelRatio(2)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    c = QColor(color)
    sw = WEIGHT_STROKE.get(UI["weight"], 1.2)
    p.setPen(QPen(c, sw, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    if name == "cursor":
        p.setBrush(c)
        p.drawPolygon(_pts(6, 3, 6, 19, 10.5, 14.8, 13.6, 21, 16.2, 19.8, 13.2, 13.8, 19, 13.8))
    elif name == "select":
        p.setPen(QPen(c, 1.5, Qt.DashLine))
        p.drawRect(QRectF(3.5, 3.5, 13, 13))
        p.setPen(QPen(c, 1.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(c)
        p.drawPolygon(_pts(12, 12, 12, 21, 14.5, 18.6, 16.2, 22, 17.8, 21.2, 16.2, 17.8, 19.6, 17.8))
    elif name == "pen":
        p.translate(12, 12)
        p.rotate(45)
        p.drawRect(QRectF(-2.6, -10, 5.2, 12.5))
        p.setBrush(c)
        p.drawPolygon(_pts(-2.6, 2.5, 2.6, 2.5, 0, 8.5))
    elif name == "highlighter":
        p.fillRect(QRectF(3, 19.5, 18, 2.6), QColor(255, 214, 10, 230))
        p.translate(12, 10)
        p.rotate(45)
        p.drawRect(QRectF(-3.2, -8, 6.4, 8.5))
        p.setBrush(c)
        p.drawPolygon(_pts(-3.2, 0.5, 3.2, 0.5, 2.2, 4.5, -2.2, 4.5))
    elif name == "eraser":
        p.translate(12, 12)
        p.rotate(-45)
        p.drawRoundedRect(QRectF(-9, -4.5, 18, 9), 2, 2)
        p.setBrush(c)
        p.drawRoundedRect(QRectF(-9, -4.5, 7.5, 9), 2, 2)
    elif name == "line":
        p.drawLine(QPointF(5, 19), QPointF(19, 5))
    elif name == "arrow":
        p.drawLine(QPointF(5, 19), QPointF(19, 5))
        p.drawPolyline(_pts(11.5, 6, 19, 5, 18, 12.5))
    elif name == "rect":
        p.drawRoundedRect(QRectF(4.5, 6.5, 15, 11), 1.5, 1.5)
    elif name == "ellipse":
        p.drawEllipse(QRectF(4, 6, 16, 12))
    elif name == "text":
        p.drawLine(QPointF(6, 6.5), QPointF(18, 6.5))
        p.drawLine(QPointF(12, 6.5), QPointF(12, 19))
        p.drawLine(QPointF(9.5, 19), QPointF(14.5, 19))
    elif name == "font":
        p.drawPolyline(_pts(3.5, 19, 8.5, 6, 13.5, 19))
        p.drawLine(QPointF(5.5, 14.5), QPointF(11.5, 14.5))
        p.drawEllipse(QRectF(14.2, 12.6, 5, 6.4))
        p.drawLine(QPointF(19.2, 12.6), QPointF(19.2, 19))
    elif name == "size":
        for y, w in ((7, sw * 0.7), (12, sw * 1.2), (18, sw * 2.0)):
            p.setPen(QPen(c, w, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(5, y), QPointF(19, y))
    elif name in ("undo", "redo"):
        if name == "redo":
            p.translate(24, 0)
            p.scale(-1, 1)
        p.drawArc(QRectF(6, 7, 13, 12), 30 * 16, 150 * 16)
        p.drawPolyline(_pts(3.3, 10.6, 6, 13.6, 9, 10.8))
    elif name == "trash":
        p.drawLine(QPointF(5, 7), QPointF(19, 7))
        p.drawPolyline(_pts(10, 7, 10, 4.5, 14, 4.5, 14, 7))
        p.drawPolyline(_pts(7, 7, 8, 20, 16, 20, 17, 7))
        p.drawLine(QPointF(10.5, 10.5), QPointF(10.5, 17))
        p.drawLine(QPointF(13.5, 10.5), QPointF(13.5, 17))
    elif name == "camera":
        p.drawRoundedRect(QRectF(3.5, 8, 17, 12), 2, 2)
        p.drawPolyline(_pts(8, 8, 9.5, 5, 14.5, 5, 16, 8))
        p.drawEllipse(QPointF(12, 14), 3.6, 3.6)
    elif name.startswith("board"):
        st = name[-1]
        p.setBrush(c if st == "2" else Qt.NoBrush)
        p.drawRoundedRect(QRectF(3.5, 4.5, 17, 12), 1.5, 1.5)
        p.drawLine(QPointF(8, 20.5), QPointF(12, 16.5))
        p.drawLine(QPointF(16, 20.5), QPointF(12, 16.5))
        if st == "1":
            p.drawLine(QPointF(7, 9), QPointF(13, 9))
    elif name == "menu":
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        for x in (5.5, 12, 18.5):
            p.drawEllipse(QPointF(x, 12), 1.9, 1.9)
    elif name == "close":
        p.drawLine(QPointF(7, 7), QPointF(17, 17))
        p.drawLine(QPointF(17, 7), QPointF(7, 17))
    elif name == "chev_up":
        p.drawPolyline(_pts(7, 15, 12, 9.5, 17, 15))
    elif name == "chev_down":
        p.drawPolyline(_pts(7, 9, 12, 14.5, 17, 9))
    elif name == "chev_left":
        p.drawPolyline(_pts(15, 7, 9.5, 12, 15, 17))
    elif name == "chev_right":
        p.drawPolyline(_pts(9, 7, 14.5, 12, 9, 17))
    p.end()
    return QIcon(pm)


FA_ICONS = {
    "logo": ("fa6s.pencil", {}), "style": ("fa6s.pen-fancy", {}),
    "cursor": ("fa6s.arrow-pointer", {}), "select": ("fa6s.vector-square", {}),
    "pen": ("fa6s.pen", {}), "highlighter": ("fa6s.highlighter", {}), "eraser": ("fa6s.eraser", {}),
    "line": ("fa6s.minus", {"rotated": -45}), "arrow": ("fa6s.arrow-right-long", {"rotated": -45}),
    "rect": ("fa6.square", {"scale_factor": 0.85}), "ellipse": ("fa6.circle", {"scale_factor": 0.85}),
    "text": ("fa6s.t", {}), "font": ("fa6s.font", {}), "size": ("fa6s.grip-lines", {}),
    "undo": ("fa6s.rotate-left", {}), "redo": ("fa6s.rotate-right", {}), "trash": ("fa6s.trash-can", {}),
    "board0": ("fa6s.desktop", {}), "board1": ("fa6.file", {}), "board2": ("fa6s.chalkboard", {}),
    "camera": ("fa6s.camera", {}), "menu": ("fa6s.ellipsis", {}), "close": ("fa6s.xmark", {}),
    "chev_up": ("fa6s.chevron-up", {}), "chev_down": ("fa6s.chevron-down", {}),
    "chev_left": ("fa6s.chevron-left", {}), "chev_right": ("fa6s.chevron-right", {}),
}


# Phosphor Icons (regular = thin outline strokes), much lighter than Font Awesome "solid"
PH_ICONS = {
    "logo": "pencil-simple", "cursor": "cursor", "select": "selection", "pen": "pen",
    "highlighter": "highlighter-circle", "eraser": "eraser", "line": "line-segment", "arrow": "arrow-up-right",
    "rect": "square", "ellipse": "circle", "text": "text-t", "font": "text-aa", "style": "pen-nib",
    "undo": "arrow-counter-clockwise", "redo": "arrow-clockwise", "trash": "trash", "board0": "monitor",
    "board1": "file", "board2": "chalkboard", "camera": "camera", "menu": "dots-three", "close": "x",
}
CUSTOM_ICONS = ("size", "highlighter")   # drawn by draw_icon (no clear Phosphor equivalent)


def make_icon(name, color="#eeeeee"):
    if qta is not None and name not in CUSTOM_ICONS:
        for spec in ((f"ph.{PH_ICONS[name]}", {}) if name in PH_ICONS else None, FA_ICONS.get(name)):
            if not spec:
                continue
            try:
                name_ = spec[0]
                if name_.startswith("ph."):
                    # the badge pencil stays at least "regular" so it is readable on the translucent circle
                    w = UI["weight"] if name != "logo" else ("bold" if UI["weight"] == "bold" else "regular")
                    name_ += WEIGHT_SUFFIX[w]
                return qta.icon(name_, color=color, **spec[1])
            except Exception:
                continue                  # older qtawesome without Phosphor -> Font Awesome -> drawn icon
    return draw_icon({"logo": "pen", "style": "pen"}.get(name, name), color)


def color_icon(col, ring=None):
    pm = QPixmap(48, 48)
    pm.setDevicePixelRatio(2)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor(ring or THEME["icon"]), 1.8))
    p.setBrush(QColor(col))
    p.drawEllipse(QPointF(12, 12), 8.5, 8.5)
    p.end()
    return QIcon(pm)


# ---------------------------------------------------------------- Medad's own icon (the colored pencil)
PENCIL_ANGLE = 45.0                  # the logo pencil is tilted 45 degrees clockwise (eraser top-right, tip bottom-left)


def pencil_scale(side, angle=PENCIL_ANGLE):
    """Scale that makes the (tilted) 148 x 512 pencil just fit a square of the given side."""
    a = math.radians(angle)
    ext = max(abs(148 * math.cos(a) + 512 * math.sin(a)), abs(148 * math.sin(a) + 512 * math.cos(a)), 148)
    return side * 0.985 / ext


def draw_app_pencil(p, rect, angle=PENCIL_ANGLE):
    """Medad's pencil icon, ported from the supplied SVG (512 x 512 viewBox), painted into rect (aspect kept)."""
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    sc = pencil_scale(min(rect.width(), rect.height()), angle)
    p.translate(rect.center())
    p.scale(sc, sc)
    p.rotate(angle)                                       # positive = clockwise on screen
    p.translate(-256, -256)
    p.setPen(Qt.NoPen)

    def poly(color, *pts):
        p.setBrush(QColor(color))
        p.drawPolygon(_pts(*pts))

    poly("#E9F4FC", 182.179, 96.538, 182.179, 408.648, 256.002, 425.903, 329.825, 408.648, 329.825, 96.538)
    poly("#C9E3F7", 182.179, 96.538, 182.179, 408.648, 204.893, 425.903, 227.608, 408.648, 227.608, 96.538)
    poly("#78B9EB", 284.395, 96.538, 284.395, 408.648, 307.11, 425.903, 329.825, 408.648, 329.825, 96.538)
    poly("#FFEFD9", 182.179, 408.648, 256.002, 512, 329.825, 408.648)                      # wood
    poly("#FFD6A0", 256.002, 512, 329.825, 408.648, 256.002, 408.648)                      # wood shade
    p.setBrush(QColor("#FFC170"))
    p.drawRect(QRectF(182.175, 79.502, 147.646, 34.072))                                    # band
    p.setBrush(QColor("#FF9811"))
    p.drawRect(QRectF(255.998, 79.502, 73.823, 34.072))
    dome = QPainterPath()                                                                   # eraser dome
    dome.moveTo(329.825, 79.502)
    dome.lineTo(329.825, 73.823)
    dome.cubicTo(329.825, 33.117, 296.708, 0, 256.002, 0)
    dome.cubicTo(215.296, 0, 182.179, 33.117, 182.179, 73.823)
    dome.lineTo(182.179, 79.502)
    dome.closeSubpath()
    p.setBrush(QColor("#FFD6A0"))
    p.drawPath(dome)
    poly("#3C5D76", 218.841, 459.975, 256.002, 512, 293.163, 459.975)                      # lead
    p.restore()


def app_pixmap(size):
    pm = QPixmap(size * 2, size * 2)
    pm.setDevicePixelRatio(2)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    draw_app_pencil(p, QRectF(0, 0, size, size))
    p.end()
    return pm


def app_icon():
    """Window / taskbar icon: exact pixel sizes (crisp at 100 % scaling) plus the HiDPI renderings."""
    ic = QIcon()
    for n in (16, 24, 32, 48, 64, 128, 256):
        pm = QPixmap(n, n)                                # exactly n x n device pixels
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        draw_app_pencil(p, QRectF(0, 0, n, n))
        p.end()
        ic.addPixmap(pm)
        ic.addPixmap(app_pixmap(n))                      # n logical px at 2x
    return ic


# ---------------------------------------------------------------- inline text editor
class TextEditor(QPlainTextEdit):
    """In-place editor; its font and size are exactly what the text is drawn with afterwards."""
    done = Signal(bool, str)

    def __init__(self, parent, color, size, text="", family="", bold=False, italic=False):
        super().__init__(parent)
        self.setFrameShape(QPlainTextEdit.NoFrame)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.document().setDocumentMargin(2)
        opt = self.document().defaultTextOption()
        opt.setAlignment(Qt.AlignLeft | Qt.AlignAbsolute)      # same as the drawn text
        self.document().setDefaultTextOption(opt)
        self._done = False
        self.restyle(color, size, family, bold, italic)
        self.setPlainText(text)
        self.moveCursor(self.textCursor().MoveOperation.End)
        self.textChanged.connect(self._fit)
        self._fit()

    def restyle(self, color, size, family, bold, italic):
        c = QColor(color)
        # fully transparent: you see exactly what is behind the text while typing (only a thin dashed outline)
        self.setStyleSheet(f"QPlainTextEdit {{ background:transparent; color:{c.name()};"
                           " border:1px dashed rgba(10,132,255,170); padding:0px; }")
        self.setAutoFillBackground(False)
        self.viewport().setAutoFillBackground(False)
        f = make_font(size, family, bold, italic)
        self.setFont(f)
        self.document().setDefaultFont(f)
        self._fit()

    def _fit(self):
        fm = QFontMetricsF(self.font())
        lines = self.toPlainText().split("\n")
        w = max(fm.horizontalAdvance(ln) for ln in lines)
        h = fm.lineSpacing() * len(lines)
        m = self.document().documentMargin()
        self.resize(int(max(120, w + 2 * m + 30)), int(h + 2 * m + 6))
        self.horizontalScrollBar().setValue(0)
        self.verticalScrollBar().setValue(0)

    def event(self, e):
        if e.type() == QEvent.ShortcutOverride:   # keep Delete / Esc / Ctrl+Z ... for the editor itself
            e.accept()
            return True
        return super().event(e)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.finish(False)
        elif e.key() in (Qt.Key_Return, Qt.Key_Enter) and e.modifiers() & Qt.ControlModifier:
            self.finish(True)
        else:
            super().keyPressEvent(e)

    def focusOutEvent(self, e):
        super().focusOutEvent(e)
        # Clicking the toolbar / a popup must not confirm the text: font and color apply live instead
        if e.reason() in (Qt.ActiveWindowFocusReason, Qt.PopupFocusReason):
            return
        self.finish(True)

    def finish(self, ok):
        if self._done:
            return
        self._done = True
        text = self.toPlainText()
        self.hide()
        self.done.emit(ok, text)
        self.deleteLater()


# ---------------------------------------------------------------- one overlay window per screen
class ScreenWindow(QWidget):
    """
    A transparent always-on-top window that covers exactly ONE screen.
    A single window spanning screens with different resolution / scaling covers only part of the sharper
    screen on Windows, so every screen gets its own window. All drawing happens in global (virtual
    desktop) coordinates; each window just paints its own part of it.
    """

    def __init__(self, ov, screen):
        flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        if ov.interact:
            flags |= Qt.WindowTransparentForInput
        super().__init__(None, flags)
        self.ov, self.scr = ov, screen
        self._tries = 0
        self._layer, self._layer_key = None, None
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.ClickFocus)
        self.setMouseTracking(True)
        self.setCursor(ov.cursor_shape())
        for seq, fn in [("Ctrl+Z", ov.undo), ("Ctrl+Y", ov.redo), ("Delete", ov.delete_selected),
                        ("Ctrl+D", ov.duplicate_selected), ("Ctrl+A", ov.select_all),
                        ("Esc", QApplication.quit)]:
            QShortcut(QKeySequence(seq), self, fn)

    def origin(self):
        return self.geometry().topLeft()

    def place_and_show(self):
        self.create()
        wh = self.windowHandle()
        if wh is not None and isinstance(self.scr, QScreen):
            wh.setScreen(self.scr)          # create it on the right screen -> right DPI from the start
        self.setGeometry(self.scr.geometry())
        self.show()
        self.reset_geometry()

    def reset_geometry(self):
        self._tries = 0
        for ms in (0, 120, 500):            # Windows may rescale the window right after it is shown
            QTimer.singleShot(ms, self.fix_geometry)

    def fix_geometry(self):
        try:
            g = self.scr.geometry()
            if self.geometry() != g and self._tries < 8:
                self._tries += 1
                self.setGeometry(g)
        except RuntimeError:                # window already deleted
            pass

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.geometry() != self.scr.geometry():
            QTimer.singleShot(0, self.fix_geometry)

    def paintEvent(self, _):
        ov = self.ov
        p = QPainter(self)
        o = self.origin()
        if ov.needs_cache():
            dpr = self.devicePixelRatioF()
            key = (ov.version, self.width(), self.height(), dpr)
            if self._layer is None or self._layer_key != key:
                pm = QPixmap(max(1, int(self.width() * dpr)), max(1, int(self.height() * dpr)))
                pm.setDevicePixelRatio(dpr)
                pm.fill(Qt.transparent)
                lp = QPainter(pm)
                lp.translate(-o.x(), -o.y())
                ov.paint_layer(lp, QRectF(self.geometry()))
                lp.end()
                self._layer, self._layer_key = pm, key
            p.drawPixmap(0, 0, self._layer)
            p.translate(-o.x(), -o.y())
            ov.paint_overlay(p)
        else:
            self._layer = None                  # free the memory when nothing needs caching
            p.translate(-o.x(), -o.y())
            ov.paint(p, QRectF(self.geometry()))

    def changeEvent(self, e):
        if e.type() == QEvent.ActivationChange and self.isActiveWindow():
            self.ov.raise_toolbar()
        super().changeEvent(e)

    def mousePressEvent(self, e):
        self.ov.on_press(e.globalPosition(), e.button(), e.modifiers())

    def mouseMoveEvent(self, e):
        self.ov.on_move(e.globalPosition(), e.buttons(), e.modifiers())

    def mouseReleaseEvent(self, e):
        self.ov.on_release(e.globalPosition(), e.button())

    def mouseDoubleClickEvent(self, e):
        self.ov.on_double(e.globalPosition(), e.button())


# ---------------------------------------------------------------- drawing controller
class Overlay(QObject):
    """Holds the drawing state and logic; one ScreenWindow per screen displays and feeds it."""

    def __init__(self):
        super().__init__()
        self.tool = "pen"
        self.color = QColor(DEFAULT_COLOR)
        self.width = 4
        self.font_size = 26.0           # text size in px (independent of line thickness)
        self.style = "solid"
        self.font_family, self.bold, self.italic = "", False, False
        self.strokes, self.history, self.future = [], [], []
        self.selected = []
        self.current = None
        self.board = 0              # 0 transparent | 1 whiteboard | 2 blackboard
        self.suspend_raise = False
        self.interact = False
        self.mode = None            # move | resize | rotate | marquee | erase
        self._press = QPointF()
        self._orig = {}
        self._marquee = None
        self._moved = False
        self._corner = self._anchor = self._rot_center = QPointF()
        self._rot_start = 0.0
        self.sel_angle = 0.0            # orientation of the selection frame (it turns together with the objects)
        self._sel_key = ()
        self._rot_angle0 = 0.0
        self._rs_theta = 0.0
        self._rs_pad, self._rs_sign, self._rs_g = 0.0, (1, 1), (1.0, 1.0)
        self._rs_origin = QPointF()
        self.toolbar = None         # set by Toolbar
        self.editor = None
        self._edit_win = None
        self._hidden = None
        self._edit_target = None
        self._edit_pos = QPointF()
        self._edit_size = 20.0
        self._edit_color = QColor(self.color)
        self._edit_family, self._edit_bold, self._edit_italic = "", False, False
        self._edit_style = "solid"

        self.version = 0
        self.windows = []
        self._rebuild_timer = QTimer(self)
        self._rebuild_timer.setSingleShot(True)
        self._rebuild_timer.setInterval(300)
        self._rebuild_timer.timeout.connect(self.rebuild_windows)
        app = QGuiApplication.instance()
        for scr in self.screens():
            if isinstance(scr, QScreen):
                scr.geometryChanged.connect(self.schedule_rebuild)
        app.screenAdded.connect(self._screen_added)
        app.screenRemoved.connect(self.schedule_rebuild)
        self.build_windows()

        # keep the toolbar above the drawing windows (activating a window pushes the toolbar behind it)
        self._raise_timer = QTimer(self)
        self._raise_timer.timeout.connect(self.raise_toolbar)
        self._raise_timer.start(700)

    # ----- screens / windows
    def screens(self):
        return QGuiApplication.screens()

    def _screen_added(self, scr):
        scr.geometryChanged.connect(self.schedule_rebuild)
        self.schedule_rebuild()

    def schedule_rebuild(self, *_):
        self._rebuild_timer.start()

    def build_windows(self):
        old, self.windows = self.windows, []
        for w in old:
            w.hide()
            w.deleteLater()
        for scr in self.screens():
            w = ScreenWindow(self, scr)
            self.windows.append(w)
            w.place_and_show()
        self.raise_toolbar()

    def rebuild_windows(self):
        self.close_editor(True)
        self.build_windows()

    def window_at(self, pos):
        for w in self.windows:
            if w.geometry().contains(pos.toPoint()):
                return w
        return self.windows[0]

    def update(self):
        """Strokes changed: the cached layers must be rebuilt."""
        self.version += 1
        self.update_light()

    def update_light(self):
        """Only the stroke being drawn / the marquee changed: cached layers stay valid."""
        for w in self.windows:
            w.update()

    def needs_cache(self):
        """Textured styles are expensive to paint; keep finished strokes in a cached layer."""
        return any(st.style in ("pencil", "chalk", "fountain", "brush")
                   or (st.tool == "text" and st.style != "solid") for st in self.strokes)

    def cursor_shape(self):
        return {"select": Qt.ArrowCursor, "text": Qt.IBeamCursor}.get(self.tool, Qt.CrossCursor)

    def apply_cursor(self):
        for w in self.windows:
            w.setCursor(self.cursor_shape())

    def render_image(self):
        r = QRectF()
        for w in self.windows:
            r = r.united(QRectF(w.geometry()))
        img = QImage(max(1, int(r.width())), max(1, int(r.height())), QImage.Format_ARGB32)
        img.fill(Qt.transparent)
        p = QPainter(img)
        p.translate(-r.topLeft())
        self.paint(p, r)
        p.end()
        return img

    # ----- toolbar helpers
    def raise_toolbar(self):
        tb = self.toolbar
        if tb is None or not tb.isVisible() or self.suspend_raise:
            return
        # while a tooltip is open or the mouse is over the toolbar it is already on top;
        # raising it again would cover the tooltip
        if QToolTip.isVisible() or tb.underMouse():
            return
        tb.raise_()

    def over_toolbar(self, gpos):
        """True if the pointer is over the toolbar: nothing may be drawn there."""
        return (self.toolbar is not None and self.toolbar.isVisible()
                and self.toolbar.frameGeometry().contains(gpos.toPoint()))

    # ----- history
    def snapshot(self):
        return [s.copy() for s in self.strokes]

    def push_history(self):
        self.history.append(self.snapshot())
        self.future.clear()

    def undo(self):
        if self.history:
            self.future.append(self.snapshot())
            self.strokes = self.history.pop()
            self.selected = []
            self.update()

    def redo(self):
        if self.future:
            self.history.append(self.snapshot())
            self.strokes = self.future.pop()
            self.selected = []
            self.update()

    # ----- modes and tools
    def set_interact(self, on):
        self.interact = on
        for w in self.windows:
            w.setWindowFlag(Qt.WindowTransparentForInput, on)
            w.show()
            w.reset_geometry()

    def set_tool(self, tool):
        self.close_editor(True)
        self.tool = tool
        if tool != "select":
            self.selected = []
        self.apply_cursor()
        self.update()

    def set_font(self, family=None, bold=None, italic=None):
        if family is not None:
            self.font_family = family
        if bold is not None:
            self.bold = bold
        if italic is not None:
            self.italic = italic
        if self.editor is not None:                      # while typing: apply instantly (changed parts only)
            if family is not None:
                self._edit_family = family
            if bold is not None:
                self._edit_bold = bold
            if italic is not None:
                self._edit_italic = italic
            self._restyle_editor()
            return
        texts = [s for s in self.selected if s.tool == "text"]
        if texts:
            self.push_history()
            for s in texts:
                s.family, s.bold, s.italic = self.font_family, self.bold, self.italic
            self.update()

    def set_style(self, key):
        if key not in STYLE_WIDTH:
            return
        self.style = key
        if self.editor is not None:                      # while typing: applied when the text is confirmed
            self._edit_style = key
            return
        targets = [s for s in self.selected if s.tool != "highlighter"]
        if targets:
            self.push_history()
            for s in targets:
                s.style = key
            self.update()

    def current_style(self):
        if self.editor is not None:
            return self._edit_style
        targets = [s for s in self.selected if s.tool != "highlighter"]
        return targets[0].style if targets else self.style

    def current_font_state(self):
        """Font shown in the font popup: open editor > selected text > defaults."""
        if self.editor is not None:
            return self._edit_family, self._edit_bold, self._edit_italic
        texts = [s for s in self.selected if s.tool == "text"]
        if texts:
            return texts[0].family, texts[0].bold, texts[0].italic
        return self.font_family, self.bold, self.italic

    def _restyle_editor(self):
        if self.editor is not None:
            self.editor.restyle(self._edit_color, self._edit_size, self._edit_family,
                                self._edit_bold, self._edit_italic)

    def refocus_editor(self):
        if self.editor is not None and self.editor.isVisible() and self._edit_win is not None:
            self._edit_win.activateWindow()
            self.editor.setFocus()
            self.raise_toolbar()

    def set_width(self, w, pushed=False):
        """Line thickness (text size has its own control in the font popup)."""
        self.width = w
        if self.editor is not None:
            return
        targets = [s for s in self.selected if s.tool != "text"]
        if targets:
            if not pushed:
                self.push_history()
            for s in targets:
                s.width = w
            self.update()

    def set_font_size(self, size, pushed=False):
        size = max(6.0, min(400.0, float(size)))
        self.font_size = size
        if self.editor is not None:                      # while typing: instantly
            self._edit_size = size
            self._restyle_editor()
            return
        texts = [s for s in self.selected if s.tool == "text"]
        if texts:
            if not pushed:
                self.push_history()
            for s in texts:
                s.size = size
            self.update()

    def begin_font_size_change(self):
        if self.editor is None and any(s.tool == "text" for s in self.selected):
            self.push_history()

    def current_font_size(self):
        """Size shown in the font popup: open editor > selected text > default."""
        if self.editor is not None:
            return self._edit_size
        texts = [s for s in self.selected if s.tool == "text"]
        return texts[0].size if texts else self.font_size

    def set_color(self, c):
        self.color = QColor(c)
        if self.editor is not None:
            self._edit_color = QColor(c)
            self._restyle_editor()
            return
        if self.selected:
            self.push_history()
            for s in self.selected:
                s.color = QColor(c)
            self.update()

    def clear(self):
        if self.strokes:
            self.push_history()
        self.strokes, self.selected = [], []
        self.update()

    def cycle_board(self):
        self.board = (self.board + 1) % 3
        self.update()
        return self.board

    def select_all(self):
        if self.tool == "select":
            self.selected = list(self.strokes)
            self.update()

    def delete_selected(self):
        if self.selected:
            self.push_history()
            self.strokes = [s for s in self.strokes if s not in self.selected]
            self.selected = []
            self.update()

    def duplicate_selected(self):
        if self.selected:
            self.push_history()
            new = []
            for s in self.selected:
                c = s.copy()
                c.pts = [p + QPointF(20, 20) for p in c.pts]
                new.append(c)
            self.strokes += new
            self.selected = new
            self.update()

    # ----- save / load
    def save_file(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"app": APP_NAME, "version": 2,
                       "strokes": [s.to_dict() for s in self.strokes]}, f, ensure_ascii=False, indent=1)

    def load_file(self, path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        new = [Stroke.from_dict(o) for o in data["strokes"]]
        self.push_history()
        self.strokes, self.selected = new, []
        self.update()

    # ----- selection frame
    def sel_rect(self):
        if not self.selected:
            return None
        r = self.selected[0].bbox()
        for s in self.selected[1:]:
            r = r.united(s.bbox())
        return r

    @staticmethod
    def corners(r):
        return [r.topLeft(), r.topRight(), r.bottomRight(), r.bottomLeft()]

    @staticmethod
    def rot_handle(r):
        return QPointF(r.center().x(), r.top() - ROT_OFFSET)

    def sel_frame(self):
        """Oriented frame of the selection: (center, width, height, angle). It rotates with the objects."""
        if not self.selected:
            self._sel_key = ()
            return None
        sig = tuple(id(s) for s in self.selected)
        if sig != self._sel_key:                         # new selection: a single rotated shape defines the angle
            self._sel_key = sig
            only = self.selected[0] if len(self.selected) == 1 else None
            self.sel_angle = only.rot if (only is not None and only.tool in ROT) else 0.0
        th = self.sel_angle
        o = QPointF(0, 0)
        pts, pad = [], 0.0
        for s in self.selected:
            pts += s.frame_points()
            pad = max(pad, s.pad())
        rp = [rot_pt(q, o, -th) for q in pts]
        x0, x1 = min(q.x() for q in rp), max(q.x() for q in rp)
        y0, y1 = min(q.y() for q in rp), max(q.y() for q in rp)
        center = rot_pt(QPointF((x0 + x1) / 2, (y0 + y1) / 2), o, th)
        return center, x1 - x0 + 2 * pad, y1 - y0 + 2 * pad, th

    @staticmethod
    def frame_corners(fr):
        c, w, h, th = fr
        return [rot_pt(QPointF(c.x() + dx, c.y() + dy), c, th)
                for dx, dy in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2))]

    @staticmethod
    def frame_rot_handle(fr):
        c, w, h, th = fr
        return rot_pt(QPointF(c.x(), c.y() - h / 2 - ROT_OFFSET), c, th)

    def handle_at(self, pos):
        fr = self.sel_frame()
        if fr is None:
            return None
        if QLineF(pos, self.frame_rot_handle(fr)).length() <= HANDLE + 3:
            return "rot"
        for i, h in enumerate(self.frame_corners(fr)):
            if QLineF(pos, h).length() <= HANDLE + 2:
                return i
        return None

    # ----- painting (global coordinates; the painter is already translated by the window)
    def paint(self, p, rect):
        self.paint_layer(p, rect)
        self.paint_overlay(p)

    def paint_layer(self, p, rect):
        """Background + finished strokes (cacheable)."""
        p.setRenderHint(QPainter.Antialiasing)
        # alpha 1: Windows lets clicks fall through fully transparent pixels
        bg = {0: QColor(0, 0, 0, 1), 1: QColor(255, 255, 255), 2: QColor(24, 24, 26)}[self.board]
        p.fillRect(rect, bg)
        for s in self.strokes:
            if s is not self._hidden:
                self.draw_stroke(p, s)

    def paint_overlay(self, p):
        """The stroke being drawn, selection frame and marquee (always drawn live)."""
        p.setRenderHint(QPainter.Antialiasing)
        if self.current is not None:
            self.draw_stroke(p, self.current)
        fr = self.sel_frame()
        if fr is not None and self.tool == "select":
            c, w, h, th = fr
            blue = QColor("#0a84ff")
            p.save()
            p.translate(c)
            p.rotate(math.degrees(th))                       # the frame turns together with the objects
            p.setPen(QPen(blue, 1.5, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            p.drawRect(QRectF(-w / 2, -h / 2, w, h))
            p.drawLine(QPointF(0, -h / 2), QPointF(0, -h / 2 - ROT_OFFSET))
            p.setPen(QPen(blue, 1.5))
            p.setBrush(QColor("white"))
            p.drawEllipse(QPointF(0, -h / 2 - ROT_OFFSET), 6, 6)
            for dx, dy in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)):
                p.drawRect(QRectF(dx - 5, dy - 5, 10, 10))
            p.restore()
        if self._marquee:
            p.setPen(QPen(QColor("#0a84ff"), 1, Qt.DashLine))
            p.setBrush(QColor(10, 132, 255, 40))
            p.drawRect(self._marquee.normalized())

    def draw_stroke(self, p, s):
        paint_stroke(p, s)

    # ----- text
    def start_text(self, pos, target=None):
        self.close_editor(True)
        self._edit_target = target
        if target:
            self._edit_pos, self._edit_size = QPointF(target.pts[0]), target.size
            self._edit_color, text = QColor(target.color), target.text
            self._edit_family, self._edit_bold, self._edit_italic = target.family, target.bold, target.italic
            self._edit_style = target.style
            self._hidden = target
        else:
            self._edit_pos, self._edit_size, text = QPointF(pos), self.font_size, ""
            self._edit_color = QColor(self.color)
            self._edit_family, self._edit_bold, self._edit_italic = self.font_family, self.bold, self.italic
            self._edit_style = self.style
        win = self.window_at(self._edit_pos)
        self._edit_win = win
        ed = TextEditor(win, self._edit_color, self._edit_size, text,
                        self._edit_family, self._edit_bold, self._edit_italic)
        ed.done.connect(self._text_done)
        local = self._edit_pos - QPointF(win.geometry().topLeft())
        ed.move((local - QPointF(3, 3)).toPoint())          # border + margin: text sits exactly on pos
        ed.show()
        win.activateWindow()
        ed.setFocus()
        self.raise_toolbar()
        self.editor = ed
        self.update()

    def close_editor(self, commit):
        if self.editor is not None:
            self.editor.finish(commit)

    def _text_done(self, ok, text):
        self.editor = None
        t, self._edit_target, self._hidden = self._edit_target, None, None
        if ok:
            if t is not None:
                self.push_history()
                if text.strip():
                    t.text, t.size, t.color = text, self._edit_size, QColor(self._edit_color)
                    t.family, t.bold, t.italic = self._edit_family, self._edit_bold, self._edit_italic
                    t.style = self._edit_style
                elif t in self.strokes:
                    self.strokes.remove(t)
            elif text.strip():
                self.push_history()
                self.strokes.append(Stroke("text", self._edit_color, self.width, [self._edit_pos], 0.0,
                                           text, self._edit_size, self._edit_family,
                                           self._edit_bold, self._edit_italic, style=self._edit_style))
        self.update()

    # ----- mouse (global positions)
    def on_press(self, pos, button, mods):
        if button != Qt.LeftButton:
            return
        if self.over_toolbar(pos):          # a click on the toolbar must never draw
            self.raise_toolbar()
            return
        self.close_editor(True)
        self._press, self._moved = pos, False
        if self.tool == "select":
            self.press_select(pos, bool(mods & Qt.ShiftModifier))
        elif self.tool == "eraser":
            self.mode = "erase"
            self.erase_at(pos)
        elif self.tool == "text":
            hit = next((s for s in reversed(self.strokes) if s.tool == "text" and s.hit(pos)), None)
            self.start_text(pos, hit)
        else:
            self.current = Stroke(self.tool, self.color, self.width, [QPointF(pos)], style=self.style)
            self.update()

    def on_double(self, pos, button):
        if self.over_toolbar(pos):
            return
        if self.tool == "select" and button == Qt.LeftButton:
            hit = next((s for s in reversed(self.strokes) if s.tool == "text" and s.hit(pos)), None)
            if hit is not None:
                self.mode, self.selected = None, []
                self.start_text(pos, hit)

    def press_select(self, pos, shift):
        h = self.handle_at(pos)
        if h is not None:
            fr = self.sel_frame()
            self._orig = {s: s.copy() for s in self.selected}
            if h == "rot":
                c = fr[0]
                self._rot_center = c
                self._rot_angle0 = fr[3]
                self._rot_start = math.atan2(pos.y() - c.y(), pos.x() - c.x())
                self.mode = "rotate"
            else:
                pts = self.frame_corners(fr)
                self._corner, self._anchor = pts[h], pts[(h + 2) % 4]
                self._rs_theta = fr[3]                       # resize along the frame's own (rotated) axes
                # the frame is the shape plus padding: scale only the shape, so the corner follows the pointer exactly
                pad = max(st.pad() for st in self.selected)
                v0 = rot_pt(self._corner, self._anchor, -fr[3]) - self._anchor
                sgx, sgy = (1 if v0.x() >= 0 else -1), (1 if v0.y() >= 0 else -1)
                self._rs_pad, self._rs_sign = pad, (sgx, sgy)
                self._rs_g = (abs(v0.x()) - 2 * pad, abs(v0.y()) - 2 * pad)
                self._rs_origin = rot_pt(self._anchor + QPointF(pad * sgx, pad * sgy), self._anchor, fr[3])
                self.mode = "resize"
            return
        hit = next((s for s in reversed(self.strokes) if s.hit(pos)), None)
        if hit is not None:
            if shift:
                if hit in self.selected:
                    self.selected.remove(hit)
                else:
                    self.selected.append(hit)
            elif hit not in self.selected:
                self.selected = [hit]
            self._orig = {s: s.copy() for s in self.selected}
            self.mode = "move"
        else:
            if not shift:
                self.selected = []
            self.mode = "marquee"
            self._marquee = QRectF(pos, pos)
        self.update()

    def _begin_modify(self):
        self.push_history()
        self._moved = True

    def apply_move(self, d):
        for s, o in self._orig.items():
            s.pts = [q + d for q in o.pts]

    def _scale_pt(self, q, sx, sy):
        a, th = self._rs_origin, self._rs_theta
        v = rot_pt(q, a, -th) - a                           # vector from the fixed point in the frame's own axes
        return rot_pt(a + QPointF(v.x() * sx, v.y() * sy), a, th)

    def apply_resize(self, sx, sy):
        th = self._rs_theta
        for s, o in self._orig.items():
            if o.tool in ROT:
                nc = self._scale_pt(o.center(), sx, sy)
                if o.tool == "text":
                    s.size = max(6.0, o.size * (abs(sx) + abs(sy)) / 2)
                    w, h = s.tsize()
                    s.pts = [QPointF(nc.x() - w / 2, nc.y() - h / 2)]
                else:
                    r = o.local_rect()
                    d = o.rot - th
                    if abs(math.sin(d)) < 1e-3:              # shape axes == frame axes: stretch each axis on its own
                        fx, fy = abs(sx), abs(sy)
                    elif abs(math.cos(d)) < 1e-3:
                        fx, fy = abs(sy), abs(sx)
                    else:
                        fx = fy = (abs(sx) + abs(sy)) / 2
                    hw, hh = r.width() / 2 * fx, r.height() / 2 * fy
                    s.pts = [QPointF(nc.x() - hw, nc.y() - hh), QPointF(nc.x() + hw, nc.y() + hh)]
            else:
                s.pts = [self._scale_pt(q, sx, sy) for q in o.pts]

    def apply_rotate(self, d):
        c0 = self._rot_center
        for s, o in self._orig.items():
            if o.tool in ROT:
                c = o.center()
                delta = rot_pt(c, c0, d) - c
                s.pts = [q + delta for q in o.pts]
                s.rot = o.rot + d
            else:
                s.pts = [rot_pt(q, c0, d) for q in o.pts]

    def on_move(self, pos, buttons, mods):
        if self.over_toolbar(pos):
            self.raise_toolbar()
        if not (buttons & Qt.LeftButton):
            return
        if self.mode == "erase":
            self.erase_at(pos)
        elif self.mode == "move" and self.selected:
            if not self._moved:
                if QLineF(pos, self._press).length() < 3:
                    return
                self._begin_modify()
            self.apply_move(pos - self._press)
            self.update()
        elif self.mode == "resize" and self.selected:
            if not self._moved:
                self._begin_modify()
            a, th = self._anchor, self._rs_theta
            v1 = rot_pt(pos, a, -th) - a
            gx, gy = self._rs_g
            sgx, sgy = self._rs_sign
            sx = (sgx * v1.x() - 2 * self._rs_pad) / gx if gx > 1 else 1.0
            sy = (sgy * v1.y() - 2 * self._rs_pad) / gy if gy > 1 else 1.0
            self.apply_resize(sx, sy)
            self.update()
        elif self.mode == "rotate" and self.selected:
            if not self._moved:
                self._begin_modify()
            c = self._rot_center
            d = math.atan2(pos.y() - c.y(), pos.x() - c.x()) - self._rot_start
            if mods & Qt.ShiftModifier:
                step = math.radians(15)
                d = round(d / step) * step
            self.sel_angle = self._rot_angle0 + d            # the selection frame rotates live with the objects
            self.apply_rotate(d)
            self.update()
        elif self.mode == "marquee":
            self._marquee = QRectF(self._press, pos)
            self.update_light()
        elif self.current:
            if self.current.tool in ("pen", "highlighter"):
                self.current.pts.append(QPointF(pos))
            else:
                self.current.pts = [self.current.pts[0], QPointF(pos)]
            self.update_light()

    def on_release(self, pos, button):
        if self.mode == "marquee" and self._marquee:
            r = self._marquee.normalized()
            for s in self.strokes:
                if r.intersects(s.bbox()) and s not in self.selected:
                    self.selected.append(s)
            self._marquee = None
        if self.current:
            c, self.current = self.current, None
            tiny = (c.tool not in ("pen", "highlighter")
                    and QLineF(c.pts[0], c.pts[-1]).length() < 3)
            if not tiny:
                self.push_history()
                self.strokes.append(c)
        self.mode = None
        self.update()

    def erase_at(self, pos):
        r = max(10, self.width * 3)
        keep = [s for s in self.strokes if not s.near(pos, r + s.eff_width() / 2)]
        if len(keep) != len(self.strokes):
            if not self._moved:
                self.push_history()
                self._moved = True
            self.strokes = keep
            self.update()


# ---------------------------------------------------------------- toolbar widgets
class IconButton(QPushButton):
    def __init__(self, icon_name, tip, checkable=False, pill="auto"):
        super().__init__()
        self.icon_name = icon_name
        self.icon_fn = None               # optional callable returning a custom QIcon (e.g. the color dot)
        self.pill = pill                  # accent indicator of a checked button: auto | bottom | None
        self.setToolTip(tip)
        self.setCheckable(checkable)
        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.toggled.connect(lambda _=False: self.refresh_icon())
        self.apply_size()
        self.refresh_icon()

    def apply_size(self):
        self.setFixedSize(UI["btn"], UI["btn"])
        self.setIconSize(QSize(UI["icon"], UI["icon"]))

    def refresh_icon(self):
        if self.icon_fn is not None:
            self.setIcon(self.icon_fn())
            return
        col = THEME["accent"] if self.isChecked() else THEME["icon"]
        self.setIcon(make_icon(self.icon_name, col))

    def set_icon_name(self, name):
        self.icon_name = name
        self.refresh_icon()

    def paintEvent(self, e):
        super().paintEvent(e)
        if self.isChecked() and self.pill:           # Windows 11 style selection pill
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(THEME["accent"]))
            w, h = self.width(), self.height()
            if self.pill == "bottom" or (self.pill == "auto" and not UI["vertical"]):
                p.drawRoundedRect(QRectF(w / 2 - 8, h - 4.5, 16, 3), 1.5, 1.5)
            else:
                p.drawRoundedRect(QRectF(1.5, h / 2 - 8, 3, 16), 1.5, 1.5)


class DragHandle(QWidget):
    """
    Floating pencil badge above (or left of) the toolbar - it is not part of the toolbar bar itself.
    Drag it to move the toolbar, click it to collapse / expand the toolbar.
    """

    def __init__(self, tb):
        super().__init__()
        self.tb = tb
        self._moved = False
        self._press = QPoint()
        self.setCursor(Qt.OpenHandCursor)
        self.setToolTip("Medad - drag to move, click to collapse / expand the toolbar")
        self.apply_size()

    def apply_size(self):
        d = UI["btn"] + 10
        self.setFixedSize(d, d)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)
        a = UI["badge"] / 100.0
        fill = QColor(THEME["badge"])
        fill.setAlphaF(a)                                   # translucent blue circle
        ring = QColor(THEME["badge"])
        ring.setAlphaF(min(1.0, a + 0.25))
        p.setPen(QPen(ring, 1.5))
        p.setBrush(fill)
        p.drawEllipse(r)
        s = r.width() * 0.84                                # Medad's colored pencil, as large as the circle allows
        draw_app_pencil(p, QRectF(r.center().x() - s / 2, r.center().y() - s / 2, s, s))

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            gp = e.globalPosition().toPoint()
            self._press, self._moved = gp, False
            self.tb._drag = gp - self.tb.frameGeometry().topLeft()
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, e):
        if self.tb._drag is None:
            return
        gp = e.globalPosition().toPoint()
        if not self._moved and (gp - self._press).manhattanLength() > 4:
            self._moved = True                              # real drag, not a click
        if self._moved:
            self.tb.move(gp - self.tb._drag)

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        self.tb._drag = None
        self.setCursor(Qt.OpenHandCursor)
        if self._moved:
            self.tb.ensure_on_screen()
        else:
            self.tb.toggle_collapse()                       # plain click


# ---------------------------------------------------------------- flyouts (popups next to the toolbar)
class Flyout(QWidget):
    def __init__(self, tb):
        super().__init__(None, Qt.Popup | Qt.FramelessWindowHint)
        self.tb = tb
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_AlwaysShowToolTips)
        o = QVBoxLayout(self)
        o.setContentsMargins(8, 8, 8, 10)               # room for the soft shadow
        self.frame = QFrame()
        self.frame.setObjectName("fly")
        o.addWidget(self.frame)
        self.shadow = QGraphicsDropShadowEffect(self.frame)
        self.shadow.setBlurRadius(18)
        self.shadow.setOffset(0, 3)
        self.frame.setGraphicsEffect(self.shadow)
        self.setStyleSheet(qss(FLY_QSS))
        self.shadow.setColor(QColor(0, 0, 0, THEME["shadow"]))

    def hideEvent(self, e):
        super().hideEvent(e)
        QTimer.singleShot(0, self.tb.ov.refocus_editor)

    def apply_theme(self):
        self.setStyleSheet(qss(FLY_QSS))
        self.shadow.setColor(QColor(0, 0, 0, THEME["shadow"]))
        for b in self.findChildren(IconButton):
            b.refresh_icon()

    def apply_sizes(self):
        for b in self.findChildren(IconButton):
            b.apply_size()


class ColorFlyout(Flyout):
    COLS = 3

    def __init__(self, tb):
        super().__init__(tb)
        g = QGridLayout(self.frame)
        g.setContentsMargins(12, 12, 12, 12)
        g.setSpacing(6)
        self.sw = []
        for i, col in enumerate(COLORS):
            b = QPushButton()
            b.setFocusPolicy(Qt.NoFocus)
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip(col)
            b.clicked.connect(lambda _=False, c=col: self._pick(c))
            g.addWidget(b, i // self.COLS, i % self.COLS)
            self.sw.append((b, col))
        self.more = QPushButton("+ Custom color...")
        self.more.setObjectName("more")
        self.more.setFocusPolicy(Qt.NoFocus)
        self.more.setIconSize(QSize(14, 14))
        self.more.clicked.connect(self._custom)
        g.addWidget(self.more, (len(COLORS) + self.COLS - 1) // self.COLS, 0, 1, self.COLS)
        self.apply_sizes()
        self.refresh(tb.ov.color)

    def apply_sizes(self):
        super().apply_sizes()
        d = max(26, int(UI["btn"] * 0.8))
        for b, _ in self.sw:
            b.setFixedSize(d, d)

    def apply_theme(self):
        super().apply_theme()
        self.refresh(self.tb.ov.color)

    def refresh(self, cur):
        cur = QColor(cur)
        in_palette = False
        for b, col in self.sw:
            same = QColor(col).rgb() == cur.rgb()
            in_palette = in_palette or same
            ring = THEME["ring_sel"] if same else THEME["ring"]
            r = max(6, b.width() // 4)
            b.setStyleSheet(f"QPushButton {{ background:{col}; border:{2 if same else 1}px solid {ring};"
                            f" border-radius:{r}px; }}")
        # a color that is not in the palette (e.g. the default) is shown next to the custom-color button
        self.more.setIcon(QIcon() if in_palette else color_icon(cur))

    def _pick(self, c):
        self.close()
        self.tb.set_color(QColor(c))

    def _custom(self):
        self.close()
        QTimer.singleShot(0, self.tb.pick_color)


class Dot(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(44, 44)
        self.col, self.n = QColor("#ffffff"), 4

    def set(self, col, n):
        self.col, self.n = QColor(col), n
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(THEME["dot_ring"]), 1))
        p.setBrush(self.col)
        d = min(38, max(3, self.n * 1.2))
        p.drawEllipse(QPointF(22, 22), d / 2, d / 2)


class SizeFlyout(Flyout):
    def __init__(self, tb):
        super().__init__(tb)
        v = QVBoxLayout(self.frame)
        v.setContentsMargins(14, 10, 14, 12)
        v.setSpacing(6)
        self.dot = Dot()
        v.addWidget(self.dot, 0, Qt.AlignHCenter)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(1, 30)
        self.slider.setFixedWidth(160)
        self.slider.setFocusPolicy(Qt.NoFocus)
        self.slider.sliderPressed.connect(tb._size_pressed)
        self.slider.valueChanged.connect(self._changed)
        v.addWidget(self.slider)
        self.label = QLabel("4 px")
        self.label.setAlignment(Qt.AlignCenter)
        v.addWidget(self.label)

    def sync(self):
        self.slider.blockSignals(True)
        self.slider.setValue(self.tb.ov.width)
        self.slider.blockSignals(False)
        self.label.setText(f"{self.tb.ov.width} px")
        self.dot.set(self.tb.ov.color, self.tb.ov.width)

    def _changed(self, v):
        self.label.setText(f"{v} px")
        self.dot.set(self.tb.ov.color, v)
        self.tb.ov.set_width(v, pushed=self.slider.isSliderDown())


class ShapesFlyout(Flyout):
    def __init__(self, tb):
        super().__init__(tb)
        h = QHBoxLayout(self.frame)
        h.setContentsMargins(8, 8, 8, 8)
        h.setSpacing(4)
        self.btns = {}
        for key in SHAPES:
            b = IconButton(key, SHAPE_TIPS[key], True, pill="bottom")
            b.clicked.connect(lambda _=False, k=key: self._pick(k))
            h.addWidget(b)
            self.btns[key] = b

    def refresh(self, cur):
        for k, b in self.btns.items():
            b.setChecked(k == cur)

    def _pick(self, k):
        self.close()
        self.tb.select_tool(k)


class FontFlyout(Flyout):
    def __init__(self, tb):
        super().__init__(tb)
        v = QVBoxLayout(self.frame)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search fonts...")
        self.search.textChanged.connect(self._filter)
        v.addWidget(self.search)
        self.list = QListWidget()
        self.list.setFixedSize(260, 230)
        self.list.setUniformItemSizes(True)
        self.list.itemClicked.connect(self._picked)
        v.addWidget(self.list)
        srow = QHBoxLayout()
        srow.setSpacing(8)
        srow.addWidget(QLabel("Size"))
        self.size_slider = QSlider(Qt.Horizontal)
        self.size_slider.setRange(8, 200)
        self.size_slider.setFocusPolicy(Qt.NoFocus)
        self.size_slider.sliderPressed.connect(lambda: self.tb.ov.begin_font_size_change())
        self.size_slider.valueChanged.connect(self._size_from_slider)
        srow.addWidget(self.size_slider, 1)
        self.size_edit = QLineEdit()                        # exact size: type a number, press Enter
        self.size_edit.setValidator(QIntValidator(6, 400, self))
        self.size_edit.setAlignment(Qt.AlignCenter)
        self.size_edit.setFixedWidth(56)
        self.size_edit.editingFinished.connect(self._size_from_edit)
        srow.addWidget(self.size_edit)
        srow.addWidget(QLabel("px"))
        v.addLayout(srow)
        row = QHBoxLayout()
        row.setSpacing(6)
        self.b_bold, self.b_italic = QPushButton("B"), QPushButton("I")
        for b, bold, italic in ((self.b_bold, True, False), (self.b_italic, False, True)):
            b.setCheckable(True)
            b.setFixedSize(38, 32)
            b.setFocusPolicy(Qt.NoFocus)
            f = b.font()
            f.setBold(bold)
            f.setItalic(italic)
            f.setPixelSize(15)
            b.setFont(f)
            b.clicked.connect(self._style)
            row.addWidget(b)
        self.preview = QLabel("Aa  Sample text")
        self.preview.setMinimumHeight(34)
        row.addWidget(self.preview, 1)
        v.addLayout(row)
        self._filled = False

    @staticmethod
    def usable_families():
        """Legacy bitmap fonts (Fixedsys, Terminal, MS Sans Serif ...), symbol fonts and vertical (@) fonts are skipped."""
        out = []
        for fam in QFontDatabase.families():
            try:
                if fam.startswith("@") or not QFontDatabase.isSmoothlyScalable(fam):
                    continue
                ws = QFontDatabase.writingSystems(fam)
                if ws and all(w == QFontDatabase.WritingSystem.Symbol for w in ws):
                    continue
            except Exception:
                pass
            out.append(fam)
        return out

    def _fill(self):
        if self._filled:
            return
        self._filled = True
        it = QListWidgetItem("System default")
        it.setData(Qt.UserRole, "")
        self.list.addItem(it)
        for fam in self.usable_families():
            it = QListWidgetItem(fam)
            it.setData(Qt.UserRole, fam)
            it.setSizeHint(QSize(220, 28))     # fixed size: Qt does not have to load every font to measure it
            f = QFont(fam)
            f.setPixelSize(16)
            it.setFont(f)
            self.list.addItem(it)

    def _set_size_widgets(self, v):
        for w in (self.size_slider, self.size_edit):
            w.blockSignals(True)
        self.size_slider.setValue(int(max(8, min(200, v))))
        self.size_edit.setText(str(int(round(v))))
        for w in (self.size_slider, self.size_edit):
            w.blockSignals(False)

    def _size_from_slider(self, v):
        self._set_size_widgets(v)
        self.tb.ov.set_font_size(v, pushed=self.size_slider.isSliderDown())

    def _size_from_edit(self):
        try:
            v = max(6, min(400, int(self.size_edit.text())))
        except ValueError:
            v = self.tb.ov.current_font_size()
        if abs(v - self.tb.ov.current_font_size()) >= 0.5:      # focus-out with no change must not add history
            self.tb.ov.set_font_size(v)
        self._set_size_widgets(self.tb.ov.current_font_size())

    def sync(self):
        self._fill()
        fam, bold, italic = self.tb.ov.current_font_state()
        self._set_size_widgets(self.tb.ov.current_font_size())
        self.search.clear()
        self.b_bold.setChecked(bold)
        self.b_italic.setChecked(italic)
        for i in range(self.list.count()):
            it = self.list.item(i)
            if it.data(Qt.UserRole) == fam:
                self.list.setCurrentItem(it)
                self.list.scrollToItem(it, QListWidget.PositionAtCenter)
                break
        self._preview()

    def apply_theme(self):
        super().apply_theme()
        self._preview()

    def showEvent(self, e):
        super().showEvent(e)
        self.search.setFocus()

    def _filter(self, t):
        t = t.strip().lower()
        for i in range(self.list.count()):
            it = self.list.item(i)
            it.setHidden(bool(t) and t not in it.text().lower())

    def _picked(self, it):
        self.tb.set_font(family=it.data(Qt.UserRole))
        self._preview()

    def _style(self):
        self.tb.set_font(bold=self.b_bold.isChecked(), italic=self.b_italic.isChecked())
        self._preview()

    def _preview(self):
        fam, bold, italic = self.tb.ov.current_font_state()
        fam = fam.replace("'", "") or "sans-serif"
        self.preview.setStyleSheet(
            f"font-family:'{fam}'; font-size:20px; color:{THEME['text']};"
            f"font-weight:{'bold' if bold else 'normal'}; font-style:{'italic' if italic else 'normal'};")


class StyleFlyout(Flyout):
    def __init__(self, tb):
        super().__init__(tb)
        v = QVBoxLayout(self.frame)
        v.setContentsMargins(10, 10, 10, 10)
        self.list = QListWidget()
        self.list.setIconSize(QSize(150, 34))
        self.list.setFixedSize(300, 8 * 44 + 8)
        self.list.setUniformItemSizes(True)
        self.list.itemClicked.connect(self._picked)
        for key, label in STYLES:
            it = QListWidgetItem(label)
            it.setData(Qt.UserRole, key)
            it.setSizeHint(QSize(280, 44))
            self.list.addItem(it)
        v.addWidget(self.list)

    def sync(self):
        cur = self.tb.ov.current_style()
        for i in range(self.list.count()):
            it = self.list.item(i)
            key = it.data(Qt.UserRole)
            it.setIcon(QIcon(style_preview(key, THEME["text"])))
            if key == cur:
                self.list.setCurrentItem(it)

    def apply_theme(self):
        super().apply_theme()
        self.sync()

    def _picked(self, it):
        self.close()
        self.tb.set_style(it.data(Qt.UserRole))


# ---------------------------------------------------------------- settings dialog
class SettingsDialog(QDialog):
    def __init__(self, tb):
        super().__init__(None, Qt.Dialog | Qt.WindowStaysOnTopHint | Qt.WindowCloseButtonHint)
        self.tb = tb
        self.setAttribute(Qt.WA_QuitOnClose, False)
        self.setWindowTitle(f"{APP_NAME} - Settings")
        g = QGridLayout(self)
        g.setContentsMargins(20, 18, 20, 18)
        g.setHorizontalSpacing(14)
        g.setVerticalSpacing(14)

        g.addWidget(QLabel("Theme"), 0, 0)
        row = QHBoxLayout()
        row.setSpacing(6)
        self.b_dark, self.b_light = QPushButton("Dark"), QPushButton("Light")
        self.g_theme = QButtonGroup(self)       # each pair is its own exclusive group
        for b, name in ((self.b_dark, "dark"), (self.b_light, "light")):
            b.setCheckable(True)
            self.g_theme.addButton(b)
            b.setFocusPolicy(Qt.NoFocus)
            b.clicked.connect(lambda _=False, n=name: self.tb.set_ui(theme=n))
            row.addWidget(b)
        g.addLayout(row, 0, 1, 1, 2)

        g.addWidget(QLabel("Layout"), 1, 0)
        row = QHBoxLayout()
        row.setSpacing(6)
        self.b_vert, self.b_horiz = QPushButton("Vertical"), QPushButton("Horizontal")
        self.g_layout = QButtonGroup(self)
        for b, vertical in ((self.b_vert, True), (self.b_horiz, False)):
            b.setCheckable(True)
            self.g_layout.addButton(b)
            b.setFocusPolicy(Qt.NoFocus)
            b.clicked.connect(lambda _=False, v=vertical: self.tb.set_vertical(v))
            row.addWidget(b)
        g.addLayout(row, 1, 1, 1, 2)

        g.addWidget(QLabel("Toolbar button size"), 2, 0)
        self.s_btn = QSlider(Qt.Horizontal)
        self.s_btn.setRange(28, 72)
        self.s_btn.setMinimumWidth(200)
        self.l_btn = QLabel()
        self.l_btn.setMinimumWidth(44)
        g.addWidget(self.s_btn, 2, 1)
        g.addWidget(self.l_btn, 2, 2)

        g.addWidget(QLabel("Icon size"), 3, 0)
        self.s_icon = QSlider(Qt.Horizontal)
        self.s_icon.setRange(12, 40)
        self.l_icon = QLabel()
        self.l_icon.setMinimumWidth(44)
        g.addWidget(self.s_icon, 3, 1)
        g.addWidget(self.l_icon, 3, 2)

        g.addWidget(QLabel("Icon weight"), 4, 0)
        wrow = QHBoxLayout()
        wrow.setSpacing(4)
        self.g_weight = QButtonGroup(self)
        self.b_weight = {}
        for wname in WEIGHTS:
            b = QPushButton(wname.capitalize())
            b.setCheckable(True)
            b.setFocusPolicy(Qt.NoFocus)
            b.setStyleSheet("padding:6px 8px;")
            b.clicked.connect(lambda _=False, n=wname: self.tb.set_ui(weight=n))
            self.g_weight.addButton(b)
            self.b_weight[wname] = b
            wrow.addWidget(b)
        g.addLayout(wrow, 4, 1, 1, 2)

        g.addWidget(QLabel("Pencil badge opacity"), 5, 0)
        self.s_badge = QSlider(Qt.Horizontal)
        self.s_badge.setRange(15, 100)
        self.l_badge = QLabel()
        self.l_badge.setMinimumWidth(44)
        g.addWidget(self.s_badge, 5, 1)
        g.addWidget(self.l_badge, 5, 2)

        btns = QHBoxLayout()
        reset, close = QPushButton("Reset to defaults"), QPushButton("Close")
        reset.setFocusPolicy(Qt.NoFocus)
        reset.clicked.connect(self._reset)
        close.clicked.connect(self.close)
        btns.addWidget(reset)
        btns.addStretch(1)
        btns.addWidget(close)
        g.addLayout(btns, 6, 0, 1, 3)

        self.s_btn.valueChanged.connect(lambda v: self.tb.set_ui(btn=v))
        self.s_icon.valueChanged.connect(lambda v: self.tb.set_ui(icon=v))
        self.s_badge.valueChanged.connect(lambda v: self.tb.set_ui(badge=v))
        self.apply_theme()
        self.sync()

    def apply_theme(self):
        self.setStyleSheet(qss(DLG_QSS))

    def sync(self):
        for w in (self.s_btn, self.s_icon, self.s_badge):
            w.blockSignals(True)
        self.s_btn.setValue(UI["btn"])
        self.s_icon.setValue(UI["icon"])
        self.s_badge.setValue(UI["badge"])
        for w in (self.s_btn, self.s_icon, self.s_badge):
            w.blockSignals(False)
        self.l_btn.setText(f"{UI['btn']} px")
        self.l_icon.setText(f"{UI['icon']} px")
        self.l_badge.setText(f"{UI['badge']} %")
        self.b_dark.setChecked(self.tb.theme_name == "dark")
        self.b_light.setChecked(self.tb.theme_name == "light")
        for wname, b in self.b_weight.items():
            b.setChecked(wname == UI["weight"])
        self.b_vert.setChecked(self.tb.vertical)
        self.b_horiz.setChecked(not self.tb.vertical)

    def _reset(self):
        self.tb.set_ui(theme=DEFAULTS["theme"], btn=DEFAULTS["btn"], icon=DEFAULTS["icon"],
                       badge=DEFAULTS["badge"], weight=DEFAULTS["weight"])


# ---------------------------------------------------------------- toolbar
class Toolbar(QWidget):
    def __init__(self, ov):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.ov = ov
        ov.toolbar = self
        self.setWindowTitle(APP_NAME)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_AlwaysShowToolTips)   # Qt hides tooltips of inactive windows by default

        # saved settings
        self.settings = QSettings(APP_NAME, APP_NAME)
        theme = str(self.settings.value("theme", DEFAULTS["theme"]))
        self.theme_name = theme if theme in THEMES else DEFAULTS["theme"]
        try:
            UI["btn"] = max(28, min(72, int(self.settings.value("btn_size", DEFAULTS["btn"]))))
            UI["icon"] = max(12, min(40, int(self.settings.value("icon_size", DEFAULTS["icon"]))))
            UI["badge"] = max(15, min(100, int(self.settings.value("badge_opacity", DEFAULTS["badge"]))))
            w = str(self.settings.value("icon_weight", DEFAULTS["weight"]))
            UI["weight"] = w if w in WEIGHTS else DEFAULTS["weight"]
        except (TypeError, ValueError):
            UI.update(btn=DEFAULTS["btn"], icon=DEFAULTS["icon"], badge=DEFAULTS["badge"])
        UI["icon"] = min(UI["icon"], UI["btn"] - 6)
        THEME.clear()
        THEME.update(THEMES[self.theme_name])

        self.vertical = self.settings.value("vertical", True, type=bool)
        UI["vertical"] = self.vertical
        refresh_metrics()
        self.collapsed, self.shape = False, "rect"
        self._drag = None
        self._dlg = None
        self.settings_dlg = None

        # the pencil badge floats outside (above / left of) the dark bar
        self.outer = QBoxLayout(QBoxLayout.TopToBottom, self)
        self.outer.setContentsMargins(10, 10, 10, 10)
        self.outer.setSpacing(2)
        self.handle = DragHandle(self)
        self.outer.addWidget(self.handle, 0, Qt.AlignHCenter)
        self.frame = QFrame()
        self.frame.setObjectName("bar")
        self.outer.addWidget(self.frame)
        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(18)
        self.shadow.setOffset(0, 3)
        self.frame.setGraphicsEffect(self.shadow)

        self.box = QBoxLayout(QBoxLayout.TopToBottom, self.frame)
        self.box.setContentsMargins(3, 3, 3, 3)           # only ~3 px between the icons and the bar edge
        self.box.setSpacing(4)
        self.body, self.seps = [], []

        self.mouse_btn = IconButton("cursor", "Interact mode: use the apps underneath (Ctrl+Alt+D)", True)
        self.mouse_btn.clicked.connect(lambda: self.set_mouse_mode(self.mouse_btn.isChecked()))
        self._add(self.mouse_btn)

        self.tool_btns = {}
        self._tool("select", "select", "Select, move, rotate and edit")
        self._sep()
        self._tool("pen", "pen", "Pen")
        self._tool("highlighter", "highlighter", "Highlighter")
        self._tool("eraser", "eraser", "Eraser")
        b = IconButton("rect", "Shapes: line, arrow, rectangle, ellipse", True)
        b.clicked.connect(self.open_shapes)
        self.tool_btns["shape"] = b
        self._add(b)
        self._tool("text", "text", "Text")
        self.font_btn = IconButton("font", "Text font (family, size, bold, italic)")
        self.font_btn.clicked.connect(self.open_font)
        self._add(self.font_btn)
        self._sep()

        self.color_btn = IconButton("cursor", "Color")
        self.color_btn.icon_fn = lambda: color_icon(self.ov.color)
        self.color_btn.refresh_icon()
        self.color_btn.clicked.connect(self.open_colors)
        self._add(self.color_btn)
        self.size_btn = IconButton("size", "Thickness")
        self.size_btn.clicked.connect(self.open_size)
        self._add(self.size_btn)
        self.style_btn = IconButton("style", "Line and text style (pencil, ballpoint, fountain pen, ...)")
        self.style_btn.clicked.connect(self.open_style)
        self._add(self.style_btn)
        self._sep()

        for icon, tip, fn in [("undo", "Undo (Ctrl+Z)", ov.undo), ("redo", "Redo (Ctrl+Y)", ov.redo),
                              ("trash", "Clear everything", ov.clear)]:
            b = IconButton(icon, tip)
            b.clicked.connect(fn)
            self._add(b)
        self._sep()

        self.board_btn = IconButton("board0", "Whiteboard / blackboard", True)
        self.board_btn.clicked.connect(self.cycle_board)
        self._add(self.board_btn)
        b = IconButton("camera", "Save screenshot")
        b.clicked.connect(self.screenshot)
        self._add(b)
        self.menu_btn = IconButton("menu", "More")
        self.menu_btn.clicked.connect(self.open_menu)
        self._add(self.menu_btn)
        self._sep()
        close = IconButton("close", f"Quit {APP_NAME}")
        close.setObjectName("close")
        close.clicked.connect(QApplication.quit)
        self._add(close)

        self.fly_colors, self.fly_size, self.fly_shapes = ColorFlyout(self), SizeFlyout(self), ShapesFlyout(self)
        self.fly_font = FontFlyout(self)
        self.fly_style = StyleFlyout(self)
        self.menu = QMenu(self)
        self.menu.setWindowFlags(self.menu.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.menu.setAttribute(Qt.WA_TranslucentBackground)       # lets the rounded corners show
        a = self.menu.addAction("Settings...")
        a.triggered.connect(self.open_settings)
        self.menu.addSeparator()
        a = self.menu.addAction("Save drawing to file...")
        a.triggered.connect(self.save_strokes)
        a = self.menu.addAction("Load drawing from file...")
        a.triggered.connect(self.load_strokes)
        self.menu.addSeparator()
        self.orient_act = self.menu.addAction("")
        self.orient_act.triggered.connect(self.toggle_orientation)
        self.menu.addSeparator()
        a = self.menu.addAction(f"About {APP_NAME}")
        a.triggered.connect(self.show_about)
        a = self.menu.addAction(f"Quit {APP_NAME}")
        a.triggered.connect(QApplication.quit)

        self.refresh_checks()
        self.apply_look()
        scr = QGuiApplication.primaryScreen().availableGeometry()
        saved = self.settings.value("pos")
        if isinstance(saved, QPoint):
            self.move(saved)
        else:
            self.move(scr.left() + 12, scr.center().y() - self.height() // 2)
        self.ensure_on_screen()

    # ----- build helpers
    def _add(self, w):
        self.box.addWidget(w, 0, Qt.AlignCenter)
        self.body.append(w)

    def _sep(self):
        s = QFrame()
        s.setObjectName("sep")
        self.box.addWidget(s, 0, Qt.AlignCenter)
        self.body.append(s)
        self.seps.append(s)

    def _tool(self, key, icon, tip):
        b = IconButton(icon, tip, True)
        b.clicked.connect(lambda _=False, k=key: self.select_tool(k))
        self.tool_btns[key] = b
        self._add(b)

    # ----- look: theme + sizes + orientation
    def apply_look(self):
        THEME.clear()
        THEME.update(THEMES[self.theme_name])
        UI["icon"] = min(UI["icon"], UI["btn"] - 6)
        refresh_metrics()
        self.setStyleSheet(qss(BAR_QSS))
        self.shadow.setColor(QColor(0, 0, 0, THEME["shadow"]))
        self.menu.setStyleSheet(qss(MENU_QSS))
        for f in (self.fly_colors, self.fly_size, self.fly_shapes, self.fly_font, self.fly_style):
            f.apply_theme()
            f.apply_sizes()
        for b in self.findChildren(IconButton):
            b.apply_size()
            b.refresh_icon()
        self.handle.apply_size()
        self.handle.update()
        if self.settings_dlg is not None:
            self.settings_dlg.apply_theme()
        self._apply_orientation()
        self._relayout()
        QTimer.singleShot(40, self._ensure_fits)

    def set_ui(self, theme=None, btn=None, icon=None, badge=None, weight=None):
        if theme in THEMES:
            self.theme_name = theme
        if btn is not None:
            UI["btn"] = max(28, min(72, int(btn)))
        if icon is not None:
            UI["icon"] = max(12, min(40, int(icon)))
        if badge is not None:
            UI["badge"] = max(15, min(100, int(badge)))
        if weight in WEIGHTS:
            UI["weight"] = weight
        UI["icon"] = min(UI["icon"], UI["btn"] - 6)
        self.settings.setValue("theme", self.theme_name)
        self.settings.setValue("btn_size", UI["btn"])
        self.settings.setValue("icon_size", UI["icon"])
        self.settings.setValue("badge_opacity", UI["badge"])
        self.settings.setValue("icon_weight", UI["weight"])
        self.apply_look()
        if self.settings_dlg is not None:
            self.settings_dlg.sync()

    def _apply_orientation(self):
        v, b = self.vertical, UI["btn"]
        UI["vertical"] = v
        self.box.setDirection(QBoxLayout.TopToBottom if v else QBoxLayout.LeftToRight)
        self.outer.setDirection(QBoxLayout.TopToBottom if v else QBoxLayout.LeftToRight)
        al = Qt.AlignHCenter if v else Qt.AlignVCenter
        self.outer.setAlignment(self.handle, al)
        self.outer.setAlignment(self.frame, al)            # the bar keeps its own tight width (badge may be wider)
        sep = int(b * 0.65)
        for s in self.seps:
            s.setFixedSize(*((sep, 1) if v else (1, sep)))
        self.orient_act.setText("Horizontal layout" if v else "Vertical layout")

    def _relayout(self):
        self.setMinimumSize(0, 0)         # old minimum size (from the previous layout) must not block resizing
        self.box.invalidate()
        self.layout().invalidate()
        self.layout().activate()
        self._fit()
        QTimer.singleShot(0, self._fit)   # once more after the layout is fully updated

    def _fit(self):
        self.resize(self.sizeHint())      # adjustSize() would cap the size at 2/3 of the screen
        self.ensure_on_screen()

    def toggle_orientation(self):
        self.vertical = not self.vertical
        self.settings.setValue("vertical", self.vertical)
        self._apply_orientation()
        self._relayout()
        if self.settings_dlg is not None:
            self.settings_dlg.sync()

    def set_vertical(self, v):
        if bool(v) != self.vertical:
            self.toggle_orientation()

    def _ensure_fits(self):
        """A tall vertical toolbar (large buttons, small screen) would be cut off: switch to horizontal."""
        scr = (QGuiApplication.screenAt(self.frameGeometry().center())
               or QGuiApplication.primaryScreen()).availableGeometry()
        if self.vertical and not self.collapsed and self.height() > scr.height():
            self.toggle_orientation()

    def toggle_collapse(self):
        self.collapsed = not self.collapsed
        self.frame.setVisible(not self.collapsed)          # only the pencil badge stays when collapsed
        self._apply_orientation()
        self._relayout()

    def ensure_on_screen(self):
        scr = (QGuiApplication.screenAt(self.frameGeometry().center())
               or QGuiApplication.primaryScreen()).availableGeometry()
        g = self.frameGeometry()
        x = max(scr.left(), min(g.left(), scr.right() - g.width()))
        y = max(scr.top(), min(g.top(), scr.bottom() - g.height()))
        self.move(x, y)

    def save_state(self):
        self.settings.setValue("pos", self.pos())
        self.settings.setValue("vertical", self.vertical)
        self.settings.sync()

    # ----- tools
    def refresh_checks(self):
        tool = self.ov.tool
        active = None if self.ov.interact else ("shape" if tool in SHAPES else tool)
        for k, b in self.tool_btns.items():
            b.setChecked(k == active)
        self.mouse_btn.setChecked(self.ov.interact)

    def select_tool(self, key):
        self.ov.set_tool(key)
        if key in SHAPES:
            self.shape = key
            self.tool_btns["shape"].set_icon_name(key)
        self.set_mouse_mode(False)

    def set_mouse_mode(self, on):
        self.ov.set_interact(on)
        self.refresh_checks()
        self.raise_()

    def set_color(self, c):
        if self.ov.tool == "eraser":
            self.select_tool("pen")
        self.ov.set_color(c)
        self.color_btn.refresh_icon()

    def cycle_board(self):
        n = self.ov.cycle_board()
        self.board_btn.set_icon_name(f"board{n}")
        self.board_btn.setChecked(n != 0)

    def _size_pressed(self):
        if self.ov.selected:
            self.ov.push_history()

    # ----- flyouts
    def pos_for(self, btn, size):
        g = btn.mapToGlobal(QPoint(0, 0))
        sg = (QGuiApplication.screenAt(g) or QGuiApplication.primaryScreen()).availableGeometry()
        w, h = size.width(), size.height()
        if self.vertical:
            x, y = g.x() + btn.width() + 4, g.y() + (btn.height() - h) // 2
            if x + w > sg.right():
                x = g.x() - w - 4
        else:
            x, y = g.x() + (btn.width() - w) // 2, g.y() + btn.height() + 4
            if y + h > sg.bottom():
                y = g.y() - h - 4
        return QPoint(max(sg.left(), min(x, sg.right() - w)), max(sg.top(), min(y, sg.bottom() - h)))

    def open_flyout(self, fly, btn):
        fly.adjustSize()
        fly.move(self.pos_for(btn, fly.size()))
        fly.show()

    def open_shapes(self):
        self.select_tool(self.shape)
        self.fly_shapes.refresh(self.shape)
        self.open_flyout(self.fly_shapes, self.tool_btns["shape"])

    def open_colors(self):
        self.fly_colors.refresh(self.ov.color)
        self.open_flyout(self.fly_colors, self.color_btn)

    def open_size(self):
        self.fly_size.sync()
        self.open_flyout(self.fly_size, self.size_btn)

    def open_style(self):
        self.fly_style.sync()
        self.open_flyout(self.fly_style, self.style_btn)

    def set_style(self, key):
        self.ov.set_style(key)

    def open_font(self):
        self.fly_font.sync()
        self.open_flyout(self.fly_font, self.font_btn)

    def set_font(self, family=None, bold=None, italic=None):
        self.ov.set_font(family, bold, italic)

    def open_menu(self):
        self.menu.exec(self.pos_for(self.menu_btn, self.menu.sizeHint()))

    def open_settings(self):
        if self.settings_dlg is None:
            self.settings_dlg = SettingsDialog(self)
        self.settings_dlg.sync()
        self.settings_dlg.show()
        self.settings_dlg.raise_()
        self.settings_dlg.activateWindow()

    def show_about(self):
        show_message(f"About {APP_NAME}",
                     f"{APP_NAME} - draw and write on top of your screen.\n\n"
                     "Icons: Phosphor Icons (MIT) and Font Awesome Free (CC BY 4.0), via qtawesome.",
                     QMessageBox.Information, app_pixmap(64))

    # ----- dialogs (always on top of the drawing windows)
    def pick_color(self):
        dlg = QColorDialog(QColor(self.ov.color))
        dlg.setOption(QColorDialog.DontUseNativeDialog, True)
        dlg.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        dlg.setAttribute(Qt.WA_QuitOnClose, False)
        dlg.setWindowTitle("Custom color")
        dlg.colorSelected.connect(self.set_color)
        dlg.finished.connect(lambda _=0: setattr(self.ov, "suspend_raise", False))
        self.ov.suspend_raise = True
        self._dlg = dlg
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _file_dialog(self, save, title, name="", filt="", suffix=""):
        dlg = QFileDialog(None, title, os.path.expanduser("~"), filt)
        dlg.setOption(QFileDialog.DontUseNativeDialog, True)
        dlg.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        dlg.setAttribute(Qt.WA_QuitOnClose, False)      # closing a dialog must never quit the app
        if suffix:
            dlg.setDefaultSuffix(suffix)
        dlg.setAcceptMode(QFileDialog.AcceptSave if save else QFileDialog.AcceptOpen)
        if save:
            dlg.selectFile(name)
        self.ov.suspend_raise = True
        try:
            ok = dlg.exec()
        finally:
            self.ov.suspend_raise = False
        return dlg.selectedFiles()[0] if ok and dlg.selectedFiles() else ""

    def save_strokes(self):
        path = self._file_dialog(True, "Save drawing", f"medad_{datetime.now():%Y%m%d_%H%M%S}.json",
                                 "Medad drawing (*.json)", "json")
        if path:
            try:
                self.ov.save_file(path)
            except Exception as ex:
                show_message("Error", f"Could not save the drawing:\n{ex}")

    def load_strokes(self):
        path = self._file_dialog(False, "Load drawing", filt="Medad drawing (*.json)")
        if path:
            try:
                self.ov.load_file(path)
            except Exception as ex:
                show_message("Error", f"This is not a valid drawing file:\n{ex}")

    def screenshot(self):
        path = self._file_dialog(True, "Save screenshot", f"medad_{datetime.now():%Y%m%d_%H%M%S}.png",
                                 "PNG image (*.png)", "png")
        if path:
            self.hide()
            QTimer.singleShot(300, lambda: self._grab(path))

    def _grab(self, path):
        try:
            scr = QGuiApplication.screenAt(self.frameGeometry().center()) or QGuiApplication.primaryScreen()
            pm = scr.grabWindow(0)
            if pm.isNull() or not pm.save(path):
                # e.g. Wayland: grabbing the whole screen is not allowed; save only the drawing layer
                if not self.ov.render_image().save(path):
                    raise OSError(f"could not write {path}")
        except Exception as ex:
            show_message("Error", f"Could not save the screenshot:\n{ex}")
        finally:
            self.show()
            self.raise_()

    # ----- dragging by the empty parts of the toolbar
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, _):
        self._drag = None
        self.ensure_on_screen()


class HotkeyBridge(QObject):
    toggled = Signal()


def _selftest(app, ov, bar):
    """Quick health check of a (packaged) build: icon fonts, windows, hotkey library. Exit code 0 = OK."""
    report = {}
    try:
        import qtawesome
        report["qtawesome"] = not qtawesome.icon("ph.pen-light", color="#fff").pixmap(24, 24).isNull()
    except Exception as ex:
        report["qtawesome"] = f"missing ({type(ex).__name__})"
    try:
        import pynput.keyboard  # noqa: F401
        report["pynput"] = True
    except Exception as ex:
        report["pynput"] = f"missing ({type(ex).__name__})"
    report["screen windows"] = len(ov.windows)
    report["toolbar visible"] = bar.isVisible()
    report["app icon"] = not app_icon().isNull()
    ok = report["qtawesome"] is True and report["screen windows"] >= 1 and report["toolbar visible"]
    lines = [f"  {k}: {v}" for k, v in report.items()] + ["SELFTEST OK" if ok else "SELFTEST FAILED"]
    text = "\n".join(lines)
    print(text)
    try:                                   # a windowed .exe has no console: also leave the report in a file
        import tempfile
        path = os.path.join(tempfile.gettempdir(), "medad_selftest.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    except Exception:
        pass
    app.exit(0 if ok else 1)


def main():
    try:
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)    # exact scaling on 125% / 175% screens
    except Exception:
        pass
    if sys.platform == "win32":                       # own taskbar identity instead of "python.exe"
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Medad.Medad.1")
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setWindowIcon(app_icon())
    # Medad only quits through its own Quit / Ctrl+C / Esc. Without this Qt quits the moment a dialog
    # (screenshot, color, settings ...) is closed, because our overlay windows are Tool windows and do not count.
    app.setQuitOnLastWindowClosed(False)
    if sys.platform == "win32":                       # Windows 11 system font
        fams = set(QFontDatabase.families())
        for name in ("Segoe UI Variable Text", "Segoe UI Variable", "Segoe UI"):
            if name in fams:
                app.setFont(QFont(name, 9))
                break
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    # Ctrl+C in the terminal: Python only handles signals while Python code runs; a light timer guarantees that
    signal.signal(signal.SIGINT, lambda *_: QApplication.quit())
    signal.signal(signal.SIGTERM, lambda *_: QApplication.quit())
    tick = QTimer()
    tick.timeout.connect(lambda: None)
    tick.start(200)

    ov = Overlay()
    bar = Toolbar(ov)
    bar.show()
    bar.raise_()
    app.aboutToQuit.connect(bar.save_state)
    if "--selftest" in sys.argv:          # used to verify a packaged build: prints a report and exits
        QTimer.singleShot(300, lambda: _selftest(app, ov, bar))
    try:  # global hotkey (Windows and X11); does not work on pure Wayland
        from pynput import keyboard
        bridge = HotkeyBridge()
        bridge.toggled.connect(lambda: bar.set_mouse_mode(not ov.interact))
        hk = keyboard.GlobalHotKeys({"<ctrl>+<alt>+d": bridge.toggled.emit})
        hk.daemon = True
        hk.start()
    except Exception:
        print("pynput is not installed (pip install pynput): the global hotkey Ctrl+Alt+D is disabled. "
              "Use the Interact-mode button on the toolbar instead.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
