# SPDX-License-Identifier: MIT
"""The dynamic parameter form: one section per part of a seqkit invocation."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea,
    QToolButton, QVBoxLayout, QWidget,
)

from ..core.builder import FlagState, RunRequest
from ..core.spec import Command, Flag
from .theme import MONO_FONT
from .widgets import FileListField, FlagRow


class Section(QWidget):
    """Collapsible titled container used for every part of the form."""

    def __init__(self, title: str, expanded: bool = True, parent=None):
        super().__init__(parent)
        self.header = QToolButton(self)
        self.header.setObjectName("Ghost")
        self.header.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.header.setCheckable(True)
        self.header.setChecked(expanded)
        self.header.setCursor(Qt.CursorShape.PointingHandCursor)
        self.header.toggled.connect(self._toggle)

        self.count = QLabel("", self)
        self.count.setObjectName("Hint")

        self.body = QWidget(self)
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(2, 4, 2, 2)
        self.body_layout.setSpacing(6)

        line = QFrame(self)
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: palette(mid);")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        head = QHBoxLayout()
        head.setSpacing(6)
        head.addWidget(self.header)
        head.addWidget(self.count)
        head.addStretch(1)
        layout.addLayout(head)
        layout.addWidget(line)
        layout.addWidget(self.body)
        self.body.setVisible(expanded)
        self.set_title(title)

    def set_title(self, title: str) -> None:
        self._title = title
        arrow = "▾ " if self.body.isVisible() else "▸ "
        self.header.setText(arrow + title)

    def set_count(self, text: str) -> None:
        self.count.setText(text)

    def add(self, widget: QWidget) -> None:
        self.body_layout.addWidget(widget)

    def _toggle(self, expanded: bool) -> None:
        self.body.setVisible(expanded)
        self.set_title(self._title)


class CommandForm(QScrollArea):
    """Renders one command's whole parameter surface and collects a RunRequest."""

    changed = Signal()
    run_requested = Signal()

    def __init__(self, catalog, chinese: bool, parent: QWidget | None = None):
        super().__init__(parent)
        self.catalog = catalog
        self.chinese = chinese
        self.command: Command | None = None
        self.rows: list[FlagRow] = []
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)

        self.content = QWidget(self)
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(16, 14, 16, 14)
        self.content_layout.setSpacing(14)

        self.title = QLabel("", self.content)
        self.title.setObjectName("CommandTitle")
        self.summary = QLabel("", self.content)
        self.summary.setObjectName("CommandDesc")
        self.summary.setWordWrap(True)
        self.summary.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.filter_box = QLineEdit(self.content)
        self.filter_box.setObjectName("SearchBox")
        self.filter_box.setClearButtonEnabled(True)
        self.filter_box.textChanged.connect(self._apply_filter)

        meta = QVBoxLayout()
        meta.setSpacing(4)
        meta.addWidget(self.title)
        meta.addWidget(self.summary)
        meta.addWidget(self.filter_box)
        self.content_layout.addLayout(meta)

        self.input_section = Section(catalog.tr("Input files"))
        self.file_field = FileListField(catalog)
        self.file_field.changed.connect(self._on_change)
        self.input_section.add(self.file_field)

        self.working_label = QLabel(catalog.tr("Working directory"), self.content)
        self.working_box = QLineEdit(self.content)
        self.working_box.textChanged.connect(self._on_change)
        working_row = QHBoxLayout()
        working_row.setSpacing(8)
        working_row.addWidget(self.working_label)
        working_row.addWidget(self.working_box, 1)
        self.working_button = QPushButton(catalog.tr("Browse"))
        self.working_button.clicked.connect(self._pick_working_dir)
        working_row.addWidget(self.working_button)
        working_container = QWidget(self.content)
        working_container.setLayout(working_row)
        self.input_section.add(working_container)

        self.content_layout.addWidget(self.input_section)

        self.param_section = Section(catalog.tr("Command parameters"))
        self.content_layout.addWidget(self.param_section)

        self.global_section = Section(catalog.tr("Global parameters"), expanded=False)
        self.content_layout.addWidget(self.global_section)

        self.extra_box = QLineEdit(self.content)
        self.extra_box.setPlaceholderText(self.catalog.tr("extra arguments, e.g. --by-seq"))
        self.extra_box.textChanged.connect(self._on_change)
        self.extra_section = Section(catalog.tr("Extra arguments"), expanded=False)
        self.extra_section.add(self.extra_box)
        self.content_layout.addWidget(self.extra_section)

        self.notes_section = Section(catalog.tr("Notes"))
        self.content_layout.addWidget(self.notes_section)

        self.docs_section = Section(catalog.tr("Documentation"), expanded=False)
        self.content_layout.addWidget(self.docs_section)

        self.content_layout.addStretch(1)
        self.setWidget(self.content)

        shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        shortcut.activated.connect(self.run_requested.emit)

    # -- building -----------------------------------------------------------
    def set_command(self, command: Command | None, working_dir: str = "") -> None:
        self.clear()
        self.command = command
        if command is None:
            self.title.setText("")
            self.summary.setText(self.catalog.tr("Select a command to start"))
            self.filter_box.setVisible(False)
            for section in (self.input_section, self.param_section, self.global_section,
                            self.extra_section, self.notes_section, self.docs_section):
                section.setVisible(False)
            return

        self.filter_box.setVisible(True)
        self.filter_box.clear()
        self.filter_box.setPlaceholderText(self.catalog.tr("Search parameters"))
        self.title.setText(command.display + ("  " + " ".join(
            f"[alias: {alias}]" for alias in command.aliases) if command.aliases else ""))
        self.summary.setText(command.summary(self.chinese))

        self._build_inputs(command)
        self.working_box.setText(working_dir or str(Path.home()))
        self._build_rows(command)
        self._build_notes(command)
        self._build_docs(command)
        for section in (self.input_section, self.param_section, self.global_section,
                        self.extra_section, self.notes_section, self.docs_section):
            section.setVisible(True)
        if command.inputs.kind == "none":
            self.input_section.set_title(self.catalog.tr("Input"))
        else:
            self.input_section.set_title(self.catalog.tr("Input files"))
        self.verticalScrollBar().setValue(0)
        self.changed.emit()

    def clear(self) -> None:
        for row in self.rows:
            # A visible widget that loses its parent becomes a top-level
            # window: hide first, or every discarded row flashes on screen as
            # a bare window until deleteLater() gets to it.
            row.setVisible(False)
            row.setParent(None)
            row.deleteLater()
        self.rows = []
        for section in (self.notes_section, self.docs_section):
            while section.body_layout.count():
                item = section.body_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.setVisible(False)
                    widget.setParent(None)
                    widget.deleteLater()

    # -- sections -----------------------------------------------------------
    def _build_inputs(self, command: Command) -> None:
        inputs = command.inputs
        self.file_field.setVisible(inputs.positional)
        hints: list[str] = []
        if inputs.kind == "none":
            hints.append(self.catalog.tr("This command takes no input files"))
        elif inputs.kind == "paths":
            hints.append(self.catalog.tr("Folders are searched recursively"))
        if inputs.min and inputs.max:
            hints.append(self.catalog.tr("exactly") + f" {inputs.min} " + self.catalog.tr("file(s)"))
        elif inputs.min:
            hints.append(self.catalog.tr("at least") + f" {inputs.min} " + self.catalog.tr("file(s)"))
        elif inputs.max:
            hints.append(self.catalog.tr("at most") + f" {inputs.max} " + self.catalog.tr("file(s)"))
        elif inputs.positional:
            hints.append(self.catalog.tr("any number of files"))
            if inputs.allow_stdin:
                hints.append(self.catalog.tr("no_stdin_note"))
        if not inputs.allow_stdin:
            hints.append(self.catalog.tr("STDIN is not supported"))
        if not inputs.allow_compressed:
            hints.append(self.catalog.tr("compressed input is not supported"))
        if inputs.accept and inputs.positional:
            hints.append(inputs.accept)
        self.file_field.set_hint(" · ".join(hints))
        self.file_field.set_single_mode(bool(inputs.max == 1))

    def _build_rows(self, command: Command) -> None:
        required = command.required_names
        local = [flag for flag in command.flags if not flag.hidden]
        for flag in local:
            self._add_row(flag, required, self.param_section)
        inherited = self._global_rows(command)
        for flag in inherited:
            self._add_row(flag, required, self.global_section)
        self.param_section.set_count(str(len(local)))
        self.global_section.set_count(str(len(inherited)))

    def _global_rows(self, command: Command) -> list[Flag]:
        """The inherited flags this command still needs a row for.

        A command that registers its own flag under a global flag's name shadows it,
        and the local definition is the one seqkit actually parses; ``all_flags``
        keeps the first definition of a name, so identity with it is the test. The
        section badge counts this same list, so it can never disagree with the rows.
        """
        return [flag for flag in command.global_flags
                if not flag.hidden and command.flag(flag.name) is flag]

    def _add_row(self, flag: Flag, required: frozenset[str], section: Section) -> None:
        row = FlagRow(flag, self.catalog, self.chinese, flag.name in required)
        row.set_from_defaults()
        row.changed.connect(self._on_change)
        row.setProperty("search", f"{flag.name} {flag.shorthand} {flag.usage}".lower())
        section.add(row)
        self.rows.append(row)

    def _build_notes(self, command: Command) -> None:
        tr = self.catalog.tr
        texts: list[str] = []
        for group in command.requires_any:
            texts.append(tr("one of {names} is required",
                            names=" / ".join(f"--{name}" for name in group)))
        for name in command.requires_all:
            texts.append(tr("{name} is required", name=f"--{name}"))
        for trigger, needed in command.conditional:
            texts.append(tr("{needed} is required because {trigger} is enabled",
                            needed=f"--{needed}", trigger=f"--{trigger}"))
        for left, right in command.forbid_pairs:
            texts.append(tr("{left} and {right} cannot be used together",
                            left=f"--{left}", right=f"--{right}"))
        texts.extend(command.notes)
        for text in texts:
            label = QLabel(text, self.content)
            label.setObjectName("FlagUsage")
            label.setWordWrap(True)
            self.notes_section.add(label)
        self.notes_section.setVisible(bool(texts))
        self.notes_section.set_count(str(len(texts)) if texts else "")

    def _build_docs(self, command: Command) -> None:
        if command.long:
            block = QLabel(_tidy(command.long), self.content)
            block.setObjectName("FlagUsage")
            block.setWordWrap(True)
            block.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.docs_section.add(block)
        if command.example:
            example = QLabel(_tidy(command.example), self.content)
            # The QSS rule for the monospace views is typed ``QPlainTextEdit#OutputView``,
            # so a QLabel wearing the same name needs the font stated here; the stack
            # itself stays in theme.py so it cannot drift from the output panel's.
            example.setObjectName("OutputView")
            example.setStyleSheet(f"font-family: {MONO_FONT}; background: transparent;")
            example.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.docs_section.add(example)
        self.docs_section.setVisible(bool(command.long or command.example))

    # -- state --------------------------------------------------------------
    def _on_change(self) -> None:
        self.changed.emit()

    def _apply_filter(self, text: str) -> None:
        needle = text.strip().lower()
        for row in self.rows:
            row.setVisible(not needle or needle in row.property("search"))

    def _pick_working_dir(self) -> None:
        picked = QFileDialog.getExistingDirectory(
            self, self.catalog.tr("Choose a folder"), self.working_box.text() or str(Path.home()))
        if picked:
            self.working_box.setText(picked)

    def inputs(self) -> tuple[str, ...]:
        return self.file_field.files()

    def collect(self) -> RunRequest:
        if self.command is None:
            raise RuntimeError("collect() requires a command; the form is empty")
        flags: dict[str, FlagState] = {}
        for row in self.rows:
            flags[row.flag.name] = FlagState(
                enabled=row.enabled,
                value=row.value_text() if not row.flag.is_list else "",
                items=row.items(),
            )
        return RunRequest(
            command=self.command,
            inputs=self.file_field.files(),
            flags=flags,
            extra_args=self.extra_box.text(),
            working_dir=self.working_box.text().strip(),
        )

    def set_busy(self, busy: bool) -> None:
        for row in self.rows:
            row.set_busy(busy)
        self.extra_box.setEnabled(not busy)
        self.working_box.setEnabled(not busy)

    def mark_missing(self, names: set[str]) -> None:
        for row in self.rows:
            row.mark_problem(row.flag.name in names and not row.enabled)

    def retranslate(self, chinese: bool) -> None:
        self.chinese = chinese
        self.input_section.set_title(
            self.catalog.tr("Input") if (self.command and self.command.inputs.kind == "none")
            else self.catalog.tr("Input files"))
        self.param_section.set_title(self.catalog.tr("Command parameters"))
        self.global_section.set_title(self.catalog.tr("Global parameters"))
        self.extra_section.set_title(self.catalog.tr("Extra arguments"))
        self.notes_section.set_title(self.catalog.tr("Notes"))
        self.docs_section.set_title(self.catalog.tr("Documentation"))
        self.working_label.setText(self.catalog.tr("Working directory"))
        self.working_button.setText(self.catalog.tr("Browse"))
        self.filter_box.setPlaceholderText(self.catalog.tr("Search parameters"))
        self.extra_box.setPlaceholderText(self.catalog.tr("extra arguments, e.g. --by-seq"))
        self.file_field.retranslate()
        for row in self.rows:
            row.retranslate(chinese)
        if self.command:
            self.summary.setText(self.command.summary(chinese))
            self.set_command(self.command, self.working_box.text())

    def focus_filter(self) -> None:
        self.filter_box.setFocus(Qt.FocusReason.ShortcutFocusReason)


def _tidy(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)
