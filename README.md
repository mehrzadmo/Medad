# Medad
Screen Annotation &amp; Presentation Overlay
<img width="1200" height="896" alt="medad" src="https://github.com/user-attachments/assets/87192e0e-0626-4abe-a574-f9cd8682d4bf" />


# Medad — Screen Annotation & Presentation Overlay

**Medad** (Persian for *Pencil*) is a lightweight, cross-platform desktop screen annotation tool for **Windows** and **Linux**, built with **Python** and **PySide6**.

Designed with AI-assisted engineering as a UX-focused alternative to traditional screen-drawing tools (such as Epic Pen), Medad solves two common pain points: **reliable multi-monitor mixed-DPI support** and **full post-draw editing** of every shape, stroke, and text element.

---

## Why Medad?

Most screen annotation utilities treat drawings as static pixels on a single giant overlay window—which breaks on multi-monitor setups with different resolutions/scaling factors and makes it impossible to adjust an arrow or typo after drawing it.

Medad takes a different approach:

1. **Per-Screen DPI-Aware Windows:** Instead of stretching one transparent window across the entire virtual desktop, Medad creates a dedicated overlay window for each monitor (`QScreen`) with `PassThrough` high-DPI scaling, while storing all annotations in unified global coordinates.
2. **Non-Destructive Vector Editing:** Every freehand stroke, shape, and text block remains an editable object. You can select, move, resize, rotate, recolor, restyle, or rewrite elements at any time.

---

## Key Features

### Drawing & Annotation Tools
- **Pen & Highlighter:** Smooth freehand drawing and semi-transparent highlighting.
- **Shapes:** Line, Arrow, Rectangle, and Ellipse.
- **Eraser:** Precision stroke removal with undo support.
- **8 Expressive Pen & Text Styles:** Standard, Pencil, Ballpoint Pen, Fountain Pen, Marker, Brush, Chalk, and Dashed—with automatic per-screen `QPixmap` layer caching for smooth performance.
- **24 Preset Colors + Custom Picker:** Quick color flyout plus full system color dialog.

### Post-Draw Selection & Editing
- **Select & Marquee:** Click to select, `Shift + Click` to add/remove items, or drag across empty space for marquee selection.
- **Transform Handles:** Drag to move, drag corner handles to resize along the object's oriented axes, or drag the top handle to rotate (`Shift` snaps to 15° increments).
- **Live Property Updates:** Change color, line thickness, pen style, or font properties on already-drawn objects.
- **History:** Full **Undo / Redo** (`Ctrl+Z` / `Ctrl+Y`), **Duplicate** (`Ctrl+D`), **Select All** (`Ctrl+A`), and **Delete** (`Delete`).

### In-Place Text & Typography
- **Transparent Inline Editor:** Click anywhere with the Text tool and type directly over your screen.
- **Live Styling:** Adjust font family, pixel size (`6–400 px`), Bold, Italic, color, and pen style while typing without closing the editor.
- **Double-Click to Re-Edit:** Double-click any existing text block using the Select tool to edit its content or styling.

### Presentation & Workflow Utilities
- **Interact Mode (`Ctrl+Alt+D`):** Global hotkey toggles click-through mode so you can interact with underlying apps while keeping your annotations visible on screen.
- **Board Modes:** Cycle between Transparent Overlay, Whiteboard, and Blackboard.
- **Save, Load & Capture:** Export drawings as `.json` project files to resume later, or save screenshots as `.png`.
- **Fluent-Inspired Floating Toolbar:** Collapsible vertical or horizontal toolbar with Dark & Light themes, customizable button/icon sizes, icon weights (`thin`, `light`, `regular`, `bold`), and persistent settings via `QSettings`.

---

## Installation

### Requirements
- Python 3.9+
- `PySide6`
- `pynput` *(optional — enables the global `Ctrl+Alt+D` Interact hotkey)*
- `qtawesome` *(optional — provides Phosphor / Font Awesome icons; built-in vector icons are used automatically if omitted)*

```bash
pip install PySide6 pynput qtawesome
