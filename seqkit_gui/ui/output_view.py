# SPDX-License-Identifier: MIT
"""Result, error, log and command-line views plus the run controls."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QClipboard, QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QTabWidget,
    QVBoxLayout, QWidget,
)

from ..core.runner import RunResult, State

MAX_BLOCKS = 20000


class OutputPanel(QWidget):
    """Four views over one run: stdout, stderr, a merged log, and the argv used."""

    run_requested = Signal()
    stop_requested = Signal()

    def __init__(self, catalog, parent: QWidget | None = None):
        super().__init__(parent)
        self.catalog = catalog

        self.result_view = _view(catalog.tr("Result is shown here"))
        self.error_view = _view(catalog.tr("No errors"))
        self.error_view.setObjectName("ErrorView")
        self.log_view = _view(catalog.tr("No runs yet"))
        self.command_view = _view("")

        self.tabs = QTabWidget(self)
        self.tabs.addTab(self.result_view, catalog.tr("Result"))
        self.tabs.addTab(self.error_view, catalog.tr("Errors"))
        self.tabs.addTab(self.log_view, catalog.tr("Log"))
        self.tabs.addTab(self.command_view, catalog.tr("Command"))

        self.run_button = QPushButton(catalog.tr("Run"), self)
        self.run_button.setObjectName("RunButton")
        self.run_button.setToolTip(catalog.tr("run_shortcut_hint"))
        self.run_button.clicked.connect(self.run_requested.emit)
        self.stop_button = QPushButton(catalog.tr("Stop"), self)
        self.stop_button.setObjectName("StopButton")
        self.stop_button.setVisible(False)
        self.stop_button.clicked.connect(self.stop_requested.emit)

        self.save_button = QPushButton(catalog.tr("Save result"), self)
        self.save_button.clicked.connect(self._save)
        self.copy_button = QPushButton(catalog.tr("Copy result"), self)
        self.copy_button.clicked.connect(self._copy)
        self.wrap_button = QPushButton(catalog.tr("Word wrap"), self)
        self.wrap_button.setCheckable(True)
        self.wrap_button.setChecked(False)
        self.wrap_button.toggled.connect(self._set_wrap)
        self.clear_button = QPushButton(catalog.tr("Clear"), self)
        self.clear_button.clicked.connect(self.clear)
        self.open_output_file_button = QPushButton(catalog.tr("Open output file"), self)
        self.open_output_file_button.clicked.connect(self._open_stdout_file)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.addWidget(self.run_button)
        actions.addWidget(self.stop_button)
        actions.addSpacing(10)
        actions.addWidget(self.save_button)
        actions.addWidget(self.copy_button)
        actions.addWidget(self.open_output_file_button)
        actions.addWidget(self.wrap_button)
        actions.addWidget(self.clear_button)
        actions.addStretch(1)
        self.status = QLabel("", self)
        self.status.setObjectName("Hint")
        self.status.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        actions.addWidget(self.status)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(8)
        layout.addLayout(actions)
        layout.addWidget(self.tabs, 1)

        self._stdout_path: Path | None = None
        self._last_result: RunResult | None = None

    # -- streaming ----------------------------------------------------------
    def begin_run(self, command_line: str, working_dir: str) -> None:
        for view in (self.result_view, self.error_view, self.log_view):
            view.clear()
        self.command_view.setPlainText(command_line)
        self.tabs.setCurrentIndex(0)
        self._log(f"$ {command_line}")
        if working_dir:
            self._log(f"cd {working_dir}")
        self.status.setText(self.catalog.tr("Running"))
        self.run_button.setVisible(False)
        self.stop_button.setVisible(True)

    def append_stdout(self, text: str) -> None:
        self.result_view.appendPlainText(text)

    def append_stderr(self, text: str) -> None:
        self.error_view.appendPlainText(text)
        self._log(text.rstrip("\n"))

    def end_run(self, result: RunResult) -> None:
        self._last_result = result
        self.run_button.setVisible(True)
        self.stop_button.setVisible(False)
        self._stdout_path = result.stdout_file

        if result.start_error:
            outcome = self.catalog.tr("Failed to start")
        elif result.cancelled:
            outcome = self.catalog.tr("Cancelled")
        elif result.exit_code == 0 and not result.crashed:
            outcome = self.catalog.tr("Done")
        else:
            outcome = self.catalog.tr("Failed")

        self.status.setText(
            f"{outcome} · {self.catalog.tr('exit code')} {result.exit_code} · "
            f"{self.catalog.tr('elapsed')} {result.elapsed:.2f}s · "
            f"{self.catalog.tr('output')} {_human(result.stdout_bytes)}"
        )
        self._log(
            f"[{outcome}] exit={result.exit_code} elapsed={result.elapsed:.2f}s "
            f"bytes={result.stdout_bytes}"
        )
        if result.start_error:
            # The raw reason is a Qt token in English ("FailedToStart"); the readable
            # version of what to do next belongs in the error view and the log.
            hint = self.catalog.tr("failed_to_start_hint")
            self.error_view.appendPlainText(hint)
            self._log(hint)
        if result.truncated:
            note = self.catalog.tr(
                "Output preview truncated, the full result is in the saved file"
            )
            self.result_view.appendPlainText(f"\n… {note} …")
            self._log(note)
        if result.exit_code != 0 and not result.cancelled:
            self.tabs.setCurrentIndex(1)

    def set_state(self, state: State) -> None:
        if state is State.IDLE:
            self.run_button.setVisible(True)
            self.stop_button.setVisible(False)

    def clear(self) -> None:
        for view in (self.result_view, self.error_view, self.log_view, self.command_view):
            view.clear()
        self.status.setText("")

    def refresh_status(self) -> None:
        if self._last_result is not None:
            self.end_run(self._last_result)

    def retranslate(self) -> None:
        self.tabs.setTabText(0, self.catalog.tr("Result"))
        self.tabs.setTabText(1, self.catalog.tr("Errors"))
        self.tabs.setTabText(2, self.catalog.tr("Log"))
        self.tabs.setTabText(3, self.catalog.tr("Command"))
        self.run_button.setText(self.catalog.tr("Run"))
        self.run_button.setToolTip(self.catalog.tr("run_shortcut_hint"))
        self.stop_button.setText(self.catalog.tr("Stop"))
        self.save_button.setText(self.catalog.tr("Save result"))
        self.copy_button.setText(self.catalog.tr("Copy result"))
        self.wrap_button.setText(self.catalog.tr("Word wrap"))
        self.clear_button.setText(self.catalog.tr("Clear"))
        self.open_output_file_button.setText(self.catalog.tr("Open output file"))

    # -- helpers ------------------------------------------------------------
    def _log(self, text: str) -> None:
        if text:
            self.log_view.appendPlainText(text)

    def _set_wrap(self, wrapped: bool) -> None:
        mode = (QPlainTextEdit.LineWrapMode.WidgetWidth if wrapped
                else QPlainTextEdit.LineWrapMode.NoWrap)
        for view in (self.result_view, self.error_view, self.log_view, self.command_view):
            view.setLineWrapMode(mode)

    def _copy(self) -> None:
        text = self.result_view.toPlainText()
        if not text and self._stdout_path and self._stdout_path.is_file():
            text = self._stdout_path.read_text(encoding="utf-8", errors="replace")
        QGuiApplication.clipboard().setText(text, QClipboard.Mode.Clipboard)
        self.status.setText(self.catalog.tr("Result copied"))

    def _save(self) -> None:
        start = self._suggest_name()
        picked, _ = QFileDialog.getSaveFileName(self, self.catalog.tr("Save result"), start)
        if not picked:
            return
        if self._stdout_path and self._stdout_path.is_file():
            Path(picked).write_bytes(self._stdout_path.read_bytes())
        else:
            Path(picked).write_text(self.result_view.toPlainText(), encoding="utf-8")
        self.status.setText(self.catalog.tr("Saved") + f": {picked}")

    def _suggest_name(self) -> str:
        return str(Path.home() / "seqkit-result.txt")

    def _open_stdout_file(self) -> None:
        if self._stdout_path and self._stdout_path.is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._stdout_path)))


def _view(placeholder: str) -> QPlainTextEdit:
    widget = QPlainTextEdit()
    widget.setObjectName("OutputView")
    widget.setReadOnly(True)
    widget.setMaximumBlockCount(MAX_BLOCKS)
    widget.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
    widget.setPlaceholderText(placeholder)
    return widget


def _human(count: int) -> str:
    value = float(count)
    for unit in ("B", "KB", "MB"):
        if value < 1024:
            return f"{value:.0f}{unit}" if unit == "B" else f"{value:.1f}{unit}"
        value /= 1024
    return f"{value:.1f}GB"
