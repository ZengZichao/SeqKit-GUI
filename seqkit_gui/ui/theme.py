# SPDX-License-Identifier: MIT
"""Light and dark palettes plus the QSS the app is styled with.

Colours are declared once per theme and every widget style is derived from them,
so a palette tweak lands everywhere. Filled accent surfaces always use the deep
accent so that white label text on them keeps its contrast in both themes;
warning fills pair with ``on_warning`` instead, because amber needs ink-dark text
in the dark theme and carries white fine in the light one.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    name: str
    window: str
    surface: str
    surface_alt: str
    sidebar: str
    border: str
    border_strong: str
    text: str
    text_secondary: str
    text_muted: str
    accent: str          # filled surfaces: always paired with on_accent
    accent_hover: str
    on_accent: str
    on_warning: str      # text on warning fills: white on ochre, ink on amber
    accent_soft: str    # tinted backgrounds for selected rows
    accent_text: str    # accent used as text/icon colour on the window background
    warning: str
    error: str
    selection: str
    code_background: str
    code_text: str
    scroll_handle: str
    scroll_handle_hover: str


LIGHT = Palette(
    name="light",
    window="#f5f6f8",
    surface="#ffffff",
    surface_alt="#fafbfc",
    sidebar="#eff1f4",
    border="#dfe2e7",
    border_strong="#c7ccd4",
    text="#1f2328",
    text_secondary="#4a5260",
    text_muted="#737b88",
    accent="#1b6fd0",
    accent_hover="#1560b8",
    on_accent="#ffffff",
    on_warning="#ffffff",
    accent_soft="#e4effb",
    accent_text="#155cb0",
    warning="#9a6700",
    error="#c0392b",
    selection="#cfe3f7",
    code_background="#f8f8fa",
    code_text="#24292f",
    scroll_handle="#c3c9d2",
    scroll_handle_hover="#a7afbb",
)

DARK = Palette(
    name="dark",
    window="#1b1d21",
    surface="#22252a",
    surface_alt="#262a30",
    sidebar="#1f2226",
    border="#34383f",
    border_strong="#454b54",
    text="#e6e8ea",
    text_secondary="#b3bac4",
    text_muted="#8b93a0",
    accent="#2f7fe0",
    accent_hover="#3f8fe9",
    on_accent="#ffffff",
    on_warning="#16181c",
    accent_soft="#26384d",
    accent_text="#7ab4f5",
    warning="#e0b040",
    error="#f07b6c",
    selection="#2f4d70",
    code_background="#1a1c20",
    code_text="#dcdfe4",
    scroll_handle="#3d434b",
    scroll_handle_hover="#4d545e",
)

PALETTES = {palette.name: palette for palette in (LIGHT, DARK)}

# The theme picker in the header bar and in the Settings dialog both read this, so
# adding a palette is the only place a new theme has to be declared.
THEME_CHOICES = [(name, name.capitalize()) for name in PALETTES]

RADIUS = "6px"

# The monospace stack used wherever seqkit output, flags or command lines are shown.
MONO_FONT = '"Cascadia Mono", Consolas, "Courier New", monospace'


def stylesheet(p: Palette, pixel_size: int = 13) -> str:
    return f"""
* {{
    font-family: "Segoe UI", "Microsoft YaHei UI", "PingFang SC", "Noto Sans CJK SC",
                 "Helvetica Neue", Arial, sans-serif;
    font-size: {pixel_size}px;
    color: {p.text};
    outline: none;
}}
QMainWindow, QWidget {{ background: {p.window}; }}
QDialog {{ background: {p.window}; }}
QMenuBar {{ background: {p.surface}; border-bottom: 1px solid {p.border}; }}
QMenuBar::item {{
    background: transparent;
    padding: 5px 10px;
    border-radius: {RADIUS};
    color: {p.text_secondary};
}}
QMenuBar::item:selected, QMenuBar::item:pressed {{
    background: {p.accent_soft};
    color: {p.accent_text};
}}

/* ---- sidebar / command list ---- */
QTreeView, QListView {{
    background: {p.sidebar};
    alternate-background-color: {p.surface_alt};
    border: none;
    padding: 4px;
}}
QTreeView::item, QListView::item {{
    padding: 7px 10px;
    border-radius: {RADIUS};
    margin: 1px 4px 1px 2px;
}}
QTreeView::item:hover, QListView::item:hover {{ background: {p.accent_soft}; }}
QTreeView::item:selected, QListView::item:selected {{
    background: {p.accent};
    color: {p.on_accent};
}}
QTreeView::item:selected:active, QListView::item:selected:active {{
    background: {p.accent};
    color: {p.on_accent};
}}
QTreeView::branch {{ background: transparent; }}
QTreeView QHeaderView::section {{ background: {p.sidebar}; border: none; color: {p.text_muted}; }}

/* ---- panels ---- */
QFrame#Card {{
    background: {p.surface};
    border: 1px solid {p.border};
    border-radius: {RADIUS};
}}
QFrame#HeaderBar {{
    background: {p.surface};
    border-bottom: 1px solid {p.border};
}}
QLabel#CommandTitle {{ font-size: {pixel_size + 4}px; font-weight: 700; }}
QLabel#CommandDesc {{ color: {p.text_secondary}; }}
QLabel#Hint {{
    color: {p.text_muted};
    font-size: {pixel_size - 1}px;
}}
QLabel#Badge {{
    background: {p.accent};
    color: {p.on_accent};
    border-radius: 10px;
    padding: 2px 9px;
    font-size: {pixel_size - 1}px;
    font-weight: 600;
}}
QLabel#BadgeWarn {{
    background: {p.warning};
    color: {p.on_warning};
    border-radius: 10px;
    padding: 2px 9px;
    font-size: {pixel_size - 1}px;
    font-weight: 600;
}}
QLabel#Shorthand {{ color: {p.text_muted}; font-family: {MONO_FONT}; }}
QLabel#FlagUsage {{ color: {p.text_secondary}; font-size: {pixel_size - 1}px; }}

/* ---- inputs ---- */
QLineEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {p.surface_alt};
    border: 1px solid {p.border};
    border-radius: {RADIUS};
    padding: 5px 8px;
    selection-background-color: {p.selection};
}}
QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus,
QDoubleSpinBox:focus, QComboBox:focus {{ border: 1px solid {p.accent}; }}
QLineEdit:disabled, QPlainTextEdit:disabled, QSpinBox:disabled,
QDoubleSpinBox:disabled, QComboBox:disabled {{
    color: {p.text_muted};
    background: {p.window};
}}
QLineEdit#SearchBox {{ padding: 7px 10px; border-radius: 14px; }}
QSpinBox, QDoubleSpinBox {{ padding-right: 2px; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{
    background: {p.surface};
    border: 1px solid {p.border_strong};
    selection-background-color: {p.accent};
    selection-color: {p.on_accent};
}}
QCheckBox {{ spacing: 7px; background: transparent; }}
QCheckBox::indicator {{
    width: 15px; height: 15px;
    border: 1px solid {p.border_strong};
    border-radius: 4px;
    background: {p.surface};
}}
QCheckBox::indicator:checked {{ background: {p.accent}; border-color: {p.accent}; }}
QCheckBox::indicator:hover {{ border-color: {p.accent}; }}

/* ---- buttons ---- */
QPushButton {{
    background: {p.surface_alt};
    border: 1px solid {p.border};
    border-radius: {RADIUS};
    padding: 6px 14px;
}}
QPushButton:hover {{ border-color: {p.accent}; color: {p.accent_text}; }}
QPushButton:pressed {{ background: {p.accent_soft}; }}
QPushButton:disabled {{ color: {p.text_muted}; background: {p.window}; border-color: {p.border}; }}
/* Toggled buttons (the word-wrap switch) need a visible resting state, not just hover. */
QPushButton:checked {{ background: {p.accent_soft}; border-color: {p.accent}; color: {p.accent_text}; }}
QPushButton:checked:hover {{ background: {p.accent_soft}; border-color: {p.accent_hover}; }}
QPushButton#RunButton {{
    background: {p.accent};
    border: 1px solid {p.accent};
    color: {p.on_accent};
    font-weight: 700;
    padding: 8px 22px;
}}
QPushButton#RunButton:hover {{ background: {p.accent_hover}; border-color: {p.accent_hover}; color: {p.on_accent}; }}
QPushButton#RunButton:disabled {{ background: {p.border}; border-color: {p.border}; color: {p.text_muted}; }}
QPushButton#StopButton {{
    background: {p.error};
    border: 1px solid {p.error};
    color: {p.on_accent};
    font-weight: 600;
    padding: 8px 18px;
}}
QPushButton#Ghost {{ background: transparent; border: 1px solid transparent; padding: 5px 9px; }}
QPushButton#Ghost:hover {{ background: {p.accent_soft}; border-color: {p.border}; color: {p.accent_text}; }}
QToolButton {{
    background: {p.surface_alt};
    border: 1px solid {p.border};
    border-radius: {RADIUS};
    padding: 4px 10px;
}}
QToolButton:hover {{ border-color: {p.accent}; color: {p.accent_text}; }}
QToolButton:pressed {{ background: {p.accent_soft}; }}
QToolButton:disabled {{ color: {p.text_muted}; background: {p.window}; border-color: {p.border}; }}
/* Collapsible section headers stay quiet until pointed at; the arrow lives in the text. */
QToolButton#Ghost {{ background: transparent; border: 1px solid transparent; padding: 3px 6px;
                      font-weight: 600; color: {p.text_secondary}; }}
QToolButton#Ghost:hover {{ background: {p.accent_soft}; border-color: {p.border}; color: {p.accent_text}; }}
QPushButton#Chip {{
    background: {p.surface_alt};
    border: 1px solid {p.border};
    border-radius: 13px;
    padding: 4px 12px;
}}
QPushButton#Chip:checked {{ background: {p.accent}; border-color: {p.accent}; color: {p.on_accent}; }}

/* ---- tabs ---- */
QTabBar::tab {{
    background: transparent;
    padding: 7px 16px;
    border-bottom: 2px solid transparent;
    color: {p.text_secondary};
}}
QTabBar::tab:selected {{ color: {p.accent_text}; border-bottom: 2px solid {p.accent}; }}
QTabBar::tab:hover {{ color: {p.text}; }}
QTabWidget::pane {{ border: none; }}

/* ---- output views ---- */
QPlainTextEdit#OutputView {{
    background: {p.code_background};
    color: {p.code_text};
    border: none;
    border-radius: {RADIUS};
    padding: 6px 8px;
    font-family: {MONO_FONT};
    font-size: {pixel_size - 1}px;
}}
QPlainTextEdit#ErrorView {{ color: {p.error}; }}

/* ---- scrolling ---- */
QScrollBar:vertical {{ background: transparent; width: 11px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {p.scroll_handle}; border-radius: 5px; min-height: 26px; }}
QScrollBar::handle:vertical:hover {{ background: {p.scroll_handle_hover}; }}
QScrollBar:horizontal {{ background: transparent; height: 11px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {p.scroll_handle}; border-radius: 5px; min-width: 26px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ---- misc ---- */
QStatusBar {{ background: {p.surface}; border-top: 1px solid {p.border}; color: {p.text_secondary}; }}
QStatusBar::item {{ border: none; }}
QToolTip {{
    background: {p.surface};
    color: {p.text};
    border: 1px solid {p.border_strong};
    border-radius: 4px;
    padding: 6px 8px;
}}
QSplitter::handle {{ background: {p.border}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}
QMenu {{
    background: {p.surface};
    border: 1px solid {p.border_strong};
    padding: 5px;
}}
QMenu::item {{ padding: 6px 22px 6px 14px; border-radius: {RADIUS}; }}
QMenu::item:selected {{ background: {p.accent}; color: {p.on_accent}; }}
QMenu::item:disabled {{ color: {p.text_muted}; }}
QMenu::separator {{ height: 1px; background: {p.border}; margin: 4px 8px; }}
QMessageBox {{ background: {p.window}; }}
QLabel#VersionInfo {{ color: {p.text_muted}; }}
QLabel#HeaderLabel {{ color: {p.text_secondary}; }}
"""
