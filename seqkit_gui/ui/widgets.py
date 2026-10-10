"""Form building blocks: file list, per-flag rows, editors."""

from __future__ import annotations

import os
import re
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFrame,
    QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QPlainTextEdit,
    QSpinBox, QToolButton, QVBoxLayout, QWidget,
)

from ..core.spec import Flag
from .theme import MONO_FONT, PALETTES, Palette

#: The text colours the application stylesheet assigns; whichever one a widget
#: resolves to says which palette it is being drawn in.
_TEXT_TOKENS = ("text", "text_secondary", "text_muted")

#: A stored default that names a home directory rather than a fixed path.
_HOME_TOKENS = ("$HOME", "~")


def home_expanded(value: str) -> str:
    """Resolve the neutral home-directory placeholder a generated default holds.

    ``tools/extract_spec.py`` stores ``$HOME/...`` because the upstream value is a
    runtime home-directory expansion. QProcess hands arguments to the child verbatim,
    with no shell to expand it, so the token has to be resolved before pre-filling
    the editor or the child writes into a directory literally named ``$HOME``.
    """
    home = str(Path.home())
    for token in _HOME_TOKENS:
        if value == token:
            return home
        if value.startswith(token + "/"):
            return home + value[len(token):].replace("/", os.sep)
    return value

#: Input files the list will hold. A paste of a few hundred thousand paths would
#: otherwise freeze the widget and hand an unusable argument vector to the child.
MAX_INPUT_FILES = 2000

#: Control characters cannot survive the trip into a child process argument.
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")

#: Above this a Windows path needs long-path support in every program that touches
#: it, so it is worth telling the user rather than letting seqkit fail quietly.
LONG_PATH_WARNING = 259

#: An entry longer than this is not a path anybody typed on purpose.
MAX_PATH_CHARS = 4096


def clean_path(text: str) -> str:
    """One input entry, as it can safely be stored and later passed as argv.

    Control characters go first -- a NUL truncates the argument where it appears.
    Windows Explorer's "Copy as path" hands back the name wrapped in double
    quotes, which are then part of the string rather than shell syntax.
    """
    value = _CONTROL.sub("", str(text)).strip()
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        value = value[1:-1].strip()
    return value


def usable_path(text: str) -> tuple[str, bool]:
    """``(path, was_resolved)``: entries that would be read as an option are made absolute."""
    if text.startswith("-"):
        # seqkit would parse this as a flag rather than a file. Resolving it against
        # the working directory keeps the intent and drops the leading dash.
        return os.path.abspath(text), True
    return text, False


def _palette_of(widget: QWidget) -> Palette:
    """The palette ``widget`` is being drawn in, read back off the widget itself.

    One :class:`~seqkit_gui.ui.theme.Palette` is installed as the application
    stylesheet at a time, and that stylesheet takes every colour in it from the
    palette, so the text colour a widget actually resolves to identifies it. A
    state drawn here then uses the same ``error`` red as the Stop button and the
    error view of that theme, instead of a second red fixed in this file.
    """
    widget.ensurePolished()      # a hidden widget resolves its colours only when polished
    resolved = widget.palette().color(QPalette.ColorRole.WindowText).name().lower()
    for palette in PALETTES.values():
        if any(resolved == getattr(palette, token).lower() for token in _TEXT_TOKENS):
            return palette
    return PALETTES["light"]


class FileListField(QWidget):
    """Positional input files, editable by dialog or drag & drop."""

    changed = Signal()

    def __init__(self, catalog, parent: QWidget | None = None):
        super().__init__(parent)
        self.catalog = catalog
        self.refused: tuple[str, ...] = ()
        self.repaired: tuple[str, ...] = ()
        # What the last add() had to change or leave out, kept so a language switch
        # can render the notice again in the new language.
        self._notice: tuple[list[str], int, int] = ([], 0, 0)
        self.list = QListWidget(self)
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list.setAcceptDrops(True)
        self.list.setAlternatingRowColors(True)
        self.list.itemDoubleClicked.connect(lambda *_: self._edit_selected())
        self.list.viewport().installEventFilter(self)

        self.hint = QLabel("", self)
        self.hint.setObjectName("Hint")
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint.setWordWrap(True)

        # Entries the field had to repair or refuse. Shown apart from `hint`, whose
        # text belongs to the command that is currently selected.
        self.notice = QLabel("", self)
        self.notice.setObjectName("Hint")
        self.notice.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.notice.setWordWrap(True)
        self.notice.setVisible(False)

        self.add_button = QToolButton(self)
        self.remove_button = QToolButton(self)
        self.clear_button = QToolButton(self)
        for button, key in ((self.add_button, "Add files"), (self.remove_button, "Remove"),
                            (self.clear_button, "Clear")):
            button.setText(catalog.tr(key))
            button.clicked.connect(
                {"Add files": self._add, "Remove": self.remove_selected,
                 "Clear": self.clear}[key]
            )
        self.paste_button = QToolButton(self)
        self.paste_button.setText(catalog.tr("Paste paths"))
        self.paste_button.clicked.connect(self._paste)

        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(self.add_button)
        row.addWidget(self.remove_button)
        row.addWidget(self.clear_button)
        row.addWidget(self.paste_button)
        row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addLayout(row)
        layout.addWidget(self.list)
        layout.addWidget(self.hint)
        layout.addWidget(self.notice)
        self.list.model().rowsInserted.connect(lambda *_: self.changed.emit())
        self.list.model().rowsRemoved.connect(lambda *_: self.changed.emit())

    # -- data ---------------------------------------------------------------
    def files(self) -> tuple[str, ...]:
        return tuple(self.list.item(index).text() for index in range(self.list.count()))

    def add(self, paths) -> None:
        existing = set(self.files())
        repaired: list[str] = []
        dropped: list[str] = []
        long_paths = 0
        for path in [paths] if isinstance(paths, (str, Path)) else paths:
            text = clean_path(str(path))
            if not text or len(text) > MAX_PATH_CHARS:
                continue
            text, was_resolved = usable_path(text)
            if was_resolved:
                repaired.append(text)
            if text in existing:
                continue
            if self.list.count() >= MAX_INPUT_FILES:
                dropped.append(text)
                continue
            self.list.addItem(text)
            existing.add(text)
            if len(text) > LONG_PATH_WARNING:
                long_paths += 1
        self.repaired = tuple(repaired)
        self.refused = tuple(dropped)
        self._notice = (repaired[:3], len(dropped), long_paths)
        self._show_notice()
        self.changed.emit()

    def _show_notice(self) -> None:
        """Report what was changed or left out, without touching the command hint."""
        repaired, dropped, long_paths = self._notice
        parts: list[str] = []
        if repaired:
            parts.append(self.catalog.tr(
                "Resolved against the working directory: {paths}",
                paths=", ".join(repaired)))
        if dropped:
            parts.append(self.catalog.tr(
                "Input list capped at {limit}, {count} not added",
                limit=MAX_INPUT_FILES, count=dropped))
        if long_paths:
            parts.append(self.catalog.tr(
                "{count} path(s) exceed {limit} characters and need Windows "
                "long-path support", count=long_paths, limit=LONG_PATH_WARNING))
        self.notice.setText(" · ".join(parts))
        self.notice.setVisible(bool(parts))

    def remove_selected(self) -> None:
        for item in self.list.selectedItems():
            self.list.takeItem(self.list.row(item))
        self.changed.emit()

    def clear(self) -> None:
        self.list.clear()
        self.repaired = ()
        self.refused = ()
        self._notice = ([], 0, 0)
        self.notice.clear()
        self.notice.setVisible(False)
        self.changed.emit()

    def set_hint(self, text: str) -> None:
        self.hint.setText(text)

    def set_single_mode(self, single: bool) -> None:
        self.list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection if single
            else QAbstractItemView.SelectionMode.ExtendedSelection
        )

    def retranslate(self) -> None:
        self.add_button.setText(self.catalog.tr("Add files"))
        self.remove_button.setText(self.catalog.tr("Remove"))
        self.clear_button.setText(self.catalog.tr("Clear"))
        self.paste_button.setText(self.catalog.tr("Paste paths"))
        self._show_notice()

    # -- helpers ------------------------------------------------------------
    def _add(self) -> None:
        start = self._first_dir()
        paths, _ = QFileDialog.getOpenFileNames(
            self, self.catalog.tr("Select input files"), start,
            self.catalog.tr("Sequence files") + " (*.fa *.fasta *.fq *.fastq *.gz *.bgzip "
            "*.bz2 *.xz *.zst *.sam *.bam);;" + self.catalog.tr("All files") + " (*)",
        )
        if paths:
            self.add(paths)

    def _edit_selected(self) -> None:
        """Double-click corrects one entry in place, the way a mistyped path asks for.

        The replacement passes through the same cleaning and de-duplication as
        ``add()``: control characters out, one entry per list row. An edit that
        would land on a name already in the list is refused, keeping the list the
        same set of paths the user added.
        """
        item = self.list.currentItem()
        if item is None:
            return
        item.setSelected(True)
        edited, accepted = QInputDialog.getText(
            self, self.catalog.tr("Edit path"), item.text(), text=item.text())
        if not accepted:
            return
        text = clean_path(edited)
        if not text or text == item.text() or text in set(self.files()):
            return
        item.setText(text)
        self.changed.emit()

    def _paste(self) -> None:
        text = QGuiApplication.clipboard().text() or ""
        self.add(text.splitlines())

    def _first_dir(self) -> str:
        for path in self.files():
            try:
                parent = Path(path).parent
                if parent.is_dir():
                    return str(parent)
            except (OSError, ValueError):
                continue                      # a name Windows cannot inspect
        return str(Path.home())

    def eventFilter(self, watched, event) -> bool:  # noqa: D102 - Qt override
        if event.type() == event.Type.Drop and event.mimeData().hasUrls():
            self.add([url.toLocalFile() for url in event.mimeData().urls()])
            event.acceptProposedAction()
            return True
        return super().eventFilter(watched, event)


class FlagRow(QFrame):
    """One flag: an enable checkbox plus the editor its type calls for."""

    changed = Signal()

    def __init__(self, flag: Flag, catalog, chinese: bool, required: bool = False,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.flag = flag
        self.catalog = catalog
        self.setObjectName("Card")
        self.setStyleSheet("QFrame#Card{background:transparent;border:none;}")

        self.enable = QCheckBox(self)
        self.enable.setText(f"--{flag.name}")
        self.enable.setToolTip(self._tooltip())
        self.enable.toggled.connect(self._sync_enabled)

        self.shorthand = QLabel(f"-{flag.shorthand}" if flag.shorthand else "", self)
        self.shorthand.setObjectName("Shorthand")
        self.shorthand.setStyleSheet(f"font-family: {MONO_FONT};")

        self.badge = QLabel("", self)
        if required:
            self.badge.setObjectName("BadgeWarn")
            self.badge.setText(catalog.tr("required"))

        # A boolean flag carries no value, so its checkbox is the whole row.
        self.editor = None if flag.is_bool else _make_editor(flag, catalog, self)
        if self.editor is not None:
            self.editor.value_changed.connect(self._emit)
            self.editor.setEnabled(False)

        self.description = QLabel(flag.describe(chinese), self)
        self.description.setObjectName("FlagUsage")
        self.description.setWordWrap(True)

        head = QHBoxLayout()
        head.setSpacing(8)
        head.addWidget(self.enable)
        head.addWidget(self.shorthand)
        head.addWidget(self.badge)
        head.addStretch(1)
        if self.editor is not None:
            head.addWidget(self.editor.size_hint_widget())

        body = QHBoxLayout()
        body.setSpacing(8)
        if self.editor is not None:
            body.addWidget(self.editor, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(3)
        layout.addLayout(head)
        layout.addLayout(body)
        layout.addWidget(self.description)

        self._chinese = chinese
        self.enable.toggled.connect(lambda checked: self.changed.emit())

    # -- state --------------------------------------------------------------
    @property
    def enabled(self) -> bool:
        return self.enable.isChecked()

    def set_enabled(self, value: bool) -> None:
        self.enable.setChecked(bool(value))

    def value_text(self) -> str:
        return "true" if self.editor is None else self.editor.text()

    def items(self) -> tuple[str, ...]:
        return () if self.editor is None else self.editor.items()

    def set_from_defaults(self) -> None:
        """Pre-fill the editor with seqkit's own default value, still disabled."""
        if self.editor is not None:
            self.editor.set_text(home_expanded(self.flag.default))

    def retranslate(self, chinese: bool) -> None:
        self._chinese = chinese
        self.description.setText(self.flag.describe(chinese))
        self.enable.setText(f"--{self.flag.name}")
        if self.editor is not None:
            self.editor.retranslate(self.catalog, chinese)
        if self.badge.text():
            self.badge.setText(self.catalog.tr("required"))

    def set_busy(self, busy: bool) -> None:
        self.enable.setEnabled(not busy)
        if self.editor is not None:
            self.editor.setEnabled(self.enabled and not busy)

    def mark_problem(self, problem: bool) -> None:
        self.description.setStyleSheet(
            f"color: {_palette_of(self.description).error};" if problem else "")

    def _sync_enabled(self, checked: bool) -> None:
        if self.editor is not None:
            self.editor.setEnabled(checked)
        self.changed.emit()

    def _tooltip(self) -> str:
        flag = self.flag
        parts = [f"seqkit --{flag.name}"]
        if flag.shorthand:
            parts[0] = f"-{flag.shorthand}, --{flag.name}"
        parts.append(f"type: {flag.type}")
        parts.append(f"default: {flag.default if flag.default != '' else '(empty)'}")
        parts.append(flag.usage)
        return "\n".join(parts)

    def _emit(self) -> None:
        self.changed.emit()


def _make_editor(flag: Flag, catalog, parent) -> "EditorBase":
    if flag.widget == "int":
        return _IntEditor(flag, catalog, parent)
    if flag.widget == "float":
        return _FloatEditor(flag, catalog, parent)
    if flag.widget == "enum":
        return _EnumEditor(flag, catalog, parent)
    if flag.widget == "list":
        return _ListEditor(flag, catalog, parent)
    if flag.widget == "in_file":
        return _FileEditor(flag, catalog, parent, mode="open")
    if flag.widget == "out_file":
        return _FileEditor(flag, catalog, parent, mode="save")
    if flag.widget == "dir":
        return _FileEditor(flag, catalog, parent, mode="dir")
    return _TextEditor(flag, catalog, parent)


class EditorBase(QWidget):
    value_changed = Signal()

    def __init__(self, flag: Flag, catalog, parent: QWidget | None = None):
        super().__init__(parent)
        self.flag = flag
        self.catalog = catalog

    def text(self) -> str:
        return ""

    def items(self) -> tuple[str, ...]:
        return ()

    def set_text(self, value: str) -> None:
        pass

    def retranslate(self, catalog, chinese: bool) -> None:
        pass

    def size_hint_widget(self) -> QWidget:
        return QLabel("", self)


class _TextEditor(EditorBase):
    def __init__(self, flag: Flag, catalog, parent):
        super().__init__(flag, catalog, parent)
        self.box = QLineEdit(home_expanded(flag.default or ""), self)
        self.box.textChanged.connect(lambda *_: self.value_changed.emit())
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.box)

    def text(self) -> str:
        return self.box.text()

    def set_text(self, value: str) -> None:
        self.box.setText(value or "")

    def size_hint_widget(self) -> QWidget:
        if self.flag.default:
            label = QLabel(self.catalog.tr("default") + f": {self.flag.default}", self)
            label.setObjectName("Hint")
            return label
        return QLabel("", self)


class _IntEditor(EditorBase):
    def __init__(self, flag: Flag, catalog, parent):
        super().__init__(flag, catalog, parent)
        self.box = QSpinBox(self)
        self.box.setRange(-2_147_483_648, 2_147_483_647)
        try:
            self.box.setValue(int(str(flag.default).strip()))
        except ValueError:
            self.box.setValue(0)
        self.box.valueChanged.connect(lambda *_: self.value_changed.emit())
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.box)

    def text(self) -> str:
        return str(self.box.value())

    def set_text(self, value: str) -> None:
        try:
            self.box.setValue(int(str(value).strip()))
        except ValueError:
            pass

    def size_hint_widget(self) -> QWidget:
        label = QLabel(self.catalog.tr("default") + f": {self.flag.default}", self)
        label.setObjectName("Hint")
        return label


class _FloatEditor(EditorBase):
    def __init__(self, flag: Flag, catalog, parent):
        super().__init__(flag, catalog, parent)
        self.box = QDoubleSpinBox(self)
        self.box.setDecimals(6)
        self.box.setRange(-1e12, 1e12)
        try:
            self.box.setValue(float(str(flag.default).strip()))
        except ValueError:
            self.box.setValue(0.0)
        self.box.valueChanged.connect(lambda *_: self.value_changed.emit())
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.box)

    def text(self) -> str:
        value = self.box.value()
        return f"{value:g}"

    def set_text(self, value: str) -> None:
        try:
            self.box.setValue(float(str(value).strip()))
        except ValueError:
            pass


class _EnumEditor(EditorBase):
    """Choices seqkit enumerates in its own usage text; still free-typable."""

    def __init__(self, flag: Flag, catalog, parent):
        super().__init__(flag, catalog, parent)
        self.box = QComboBox(self)
        self.box.setEditable(True)
        options = list(flag.options)
        if flag.default and flag.default not in options:
            options.insert(0, flag.default)
        self.box.addItems(options)
        index = self.box.findText(flag.default)
        if index >= 0:
            self.box.setCurrentIndex(index)
        self.box.currentTextChanged.connect(lambda *_: self.value_changed.emit())
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.box)

    def text(self) -> str:
        return self.box.currentText()

    def set_text(self, value: str) -> None:
        if self.box.findText(value) < 0 and value:
            self.box.addItem(value)
        self.box.setCurrentText(value)


class _ListEditor(EditorBase):
    """Repeatable flags: one value per line, emitted as the flag repeated."""

    def __init__(self, flag: Flag, catalog, parent):
        super().__init__(flag, catalog, parent)
        self.box = QPlainTextEdit(self)
        self.box.setPlaceholderText(catalog.tr("one value per line"))
        self.box.setMaximumHeight(96)
        self.box.textChanged.connect(lambda *_: self.value_changed.emit())
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.box)

    def text(self) -> str:
        return "\n".join(self.items())

    def items(self) -> tuple[str, ...]:
        return tuple(line.strip() for line in self.box.toPlainText().splitlines() if line.strip())

    def set_text(self, value: str) -> None:
        self.box.setPlainText(value or "")

    def retranslate(self, catalog, chinese: bool) -> None:
        self.box.setPlaceholderText(catalog.tr("one value per line"))


class _FileEditor(EditorBase):
    def __init__(self, flag: Flag, catalog, parent, mode: str):
        super().__init__(flag, catalog, parent)
        self.mode = mode
        self.box = QLineEdit(self)
        self.box.textChanged.connect(lambda *_: self.value_changed.emit())
        self.button = QToolButton(self)
        self.button.setText(catalog.tr("Browse"))
        self.button.clicked.connect(self._browse)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.box, 1)
        layout.addWidget(self.button)

    def text(self) -> str:
        return self.box.text().strip()

    def set_text(self, value: str) -> None:
        self.box.setText(value or "")

    def retranslate(self, catalog, chinese: bool) -> None:
        self.button.setText(catalog.tr("Browse"))

    def _browse(self) -> None:
        start = self.text() or str(Path.home())
        if self.mode == "dir":
            picked = QFileDialog.getExistingDirectory(self, self.catalog.tr("Choose a folder"), start)
        elif self.mode == "save":
            picked, _ = QFileDialog.getSaveFileName(
                self, self.catalog.tr("Save output file"), start)
        else:
            picked, _ = QFileDialog.getOpenFileName(
                self, self.catalog.tr("Choose a file"), start,
                self.catalog.tr("All files") + " (*)")
        if picked:
            self.box.setText(picked)
