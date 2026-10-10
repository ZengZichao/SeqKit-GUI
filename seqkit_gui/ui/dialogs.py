# SPDX-License-Identifier: MIT
"""Preferences and About dialogs."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from .. import APP_NAME, __version__
from ..core import seqkit_locator
from ..core.settings import Preferences
from ..core.spec import Schema
from .i18n import LANGUAGES
from .theme import THEME_CHOICES


class PreferencesDialog(QDialog):
    def __init__(self, catalog, prefs: Preferences, parent: QWidget | None = None):
        super().__init__(parent)
        self.catalog = catalog
        self.prefs = prefs
        self.setWindowTitle(catalog.tr("Settings"))
        self.setMinimumWidth(560)

        self.seqkit_box = QLineEdit(prefs.seqkit_path, self)
        self.seqkit_box.setPlaceholderText(catalog.tr("Leave empty to auto-detect"))
        detect = QPushButton(catalog.tr("Auto-detect"), self)
        detect.clicked.connect(self._autodetect)
        browse = QPushButton(catalog.tr("Browse"), self)
        browse.clicked.connect(self._browse)
        path_row = QHBoxLayout()
        path_row.setSpacing(6)
        path_row.addWidget(self.seqkit_box, 1)
        path_row.addWidget(detect)
        path_row.addWidget(browse)

        self.version_label = QLabel("", self)
        self.version_label.setObjectName("VersionInfo")
        test = QPushButton(catalog.tr("Test"), self)
        test.clicked.connect(self._test)
        test_row = QHBoxLayout()
        test_row.addWidget(self.version_label, 1)
        test_row.addWidget(test)

        self.language_combo = _Choice(list(LANGUAGES.items()), prefs.language)
        self.theme_combo = _Choice(THEME_CHOICES, prefs.theme)
        self.output_limit = QSpinBox(self)
        self.output_limit.setRange(500, 200000)
        self.output_limit.setSingleStep(500)
        self.output_limit.setValue(prefs.output_line_limit)
        self.working_box = QLineEdit(prefs.working_dir, self)
        self.working_box.setPlaceholderText(str(Path.home()))

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.addRow(catalog.tr("SeqKit executable"), path_row)
        form.addRow("", test_row)
        form.addRow(catalog.tr("Language"), self.language_combo)
        form.addRow(catalog.tr("Theme"), self.theme_combo)
        form.addRow(catalog.tr("Output line limit"), self.output_limit)
        form.addRow(catalog.tr("Default working directory"), self.working_box)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        _localise(buttons, catalog)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _autodetect(self) -> None:
        found = seqkit_locator.locate("")
        if found.found:
            self.seqkit_box.setText(str(found.path))
            self._test()
        else:
            self.version_label.setText(self.catalog.tr("seqkit not found"))

    def _browse(self) -> None:
        picked, _ = QFileDialog.getOpenFileName(
            self, self.catalog.tr("Choose the seqkit executable"), str(Path.home()))
        if picked:
            self.seqkit_box.setText(picked)
            self._test()

    def _test(self) -> None:
        text = self.seqkit_box.text().strip()
        if not text:
            self.version_label.setText(self.catalog.tr("Auto-detect will be used"))
            return
        path = Path(text)
        if not path.is_file():
            self.version_label.setText(self.catalog.tr("seqkit not found"))
            return
        version = seqkit_locator.probe_version(path)
        self.version_label.setText(version or self.catalog.tr("Could not run this file"))

    def values(self) -> Preferences:
        self.prefs.seqkit_path = self.seqkit_box.text().strip()
        self.prefs.language = self.language_combo.value()
        self.prefs.theme = self.theme_combo.value()
        self.prefs.output_line_limit = self.output_limit.value()
        self.prefs.working_dir = self.working_box.text().strip()
        return self.prefs


class AboutDialog(QDialog):
    def __init__(self, catalog, schema: Schema, seqkit_text: str,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.catalog = catalog
        self.setWindowTitle(catalog.tr("About SeqKit GUI"))
        self.setMinimumWidth(520)

        title = QLabel(APP_NAME, self)
        title.setObjectName("CommandTitle")
        version = QLabel(f"{catalog.tr('version')} {__version__}", self)
        version.setObjectName("Hint")

        disclaimer = QLabel(catalog.tr("unofficial_disclaimer"), self)
        disclaimer.setWordWrap(True)
        disclaimer.setObjectName("CommandDesc")

        attribution = QLabel(catalog.tr("seqkit_attribution"), self)
        attribution.setWordWrap(True)
        attribution.setObjectName("FlagUsage")

        detected = QLabel(seqkit_text or catalog.tr("seqkit not found"), self)
        detected.setObjectName("VersionInfo")
        detected.setWordWrap(True)
        detected.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        schema_line = QLabel(
            f"{catalog.tr('Schema')}: {schema.seqkit_version} · "
            f"{len(schema.usable)} {catalog.tr('commands')} · "
            f"{schema.flag_entries} {catalog.tr('parameters')} · "
            f"{len(schema.global_flag_names)} {catalog.tr('global parameters')}", self)
        schema_line.setObjectName("VersionInfo")

        license_line = QLabel(
            f"{catalog.tr('License')}: MIT · " + catalog.tr("third party licenses"), self)
        license_line.setObjectName("VersionInfo")
        license_line.setWordWrap(True)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        # A Close-role button is emitted through rejected(); the box has no accept path.
        buttons.rejected.connect(self.reject)
        _localise(buttons, catalog)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(10)
        for widget in (title, version, disclaimer, attribution, detected, schema_line,
                       license_line, buttons):
            layout.addWidget(widget)


def _localise(buttons: QDialogButtonBox, catalog) -> None:
    """Qt ships no Chinese text for standard buttons unless a QTranslator is loaded."""
    pairs = {
        QDialogButtonBox.StandardButton.Ok: "OK",
        QDialogButtonBox.StandardButton.Cancel: "Cancel",
        QDialogButtonBox.StandardButton.Close: "Close",
    }
    for role, key in pairs.items():
        button = buttons.button(role)
        if button is not None:
            button.setText(catalog.tr(key))


class _Choice(QWidget):
    """Segmented toggle group reporting the selected key through ``changed``.

    ``set_value`` moves the selection without emitting: a widget whose state was
    changed elsewhere (the Settings dialog, a preference loaded at startup) has to
    sync these chips, and emitting would bounce the change back to its own owner.
    """

    changed = Signal(str)

    def __init__(self, choices: list[tuple[str, str]], current: str,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._value = current if any(key == current for key, _ in choices) else choices[0][0]
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.buttons: dict[str, QPushButton] = {}
        for key, label in choices:
            button = QPushButton(label, self)
            button.setObjectName("Chip")
            button.setCheckable(True)
            button.setChecked(key == self._value)
            button.clicked.connect(lambda _=False, value=key: self._select(value))
            layout.addWidget(button)
            self.buttons[key] = button
        layout.addStretch(1)

    def _select(self, value: str) -> None:
        self.set_value(value)
        self.changed.emit(value)

    def set_value(self, value: str) -> None:
        self._value = value
        for key, button in self.buttons.items():
            button.setChecked(key == value)

    def value(self) -> str:
        return self._value
