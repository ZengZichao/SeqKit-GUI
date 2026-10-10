# SPDX-License-Identifier: MIT
"""Application window: command list, parameter form, output panel."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl, QTimer
from PySide6.QtGui import QDesktopServices, QAction, QIcon, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMenu,
    QMessageBox, QPushButton, QSplitter, QStatusBar, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)

from .. import APP_NAME
from ..core import paths, seqkit_locator, settings as store
from ..core.builder import build_argv, display_command, validate
from ..core.runner import RunResult, SeqkitRunner
from ..core.settings import Preferences
from ..core.spec import Command, Schema
from .dialogs import AboutDialog, PreferencesDialog, _Choice
from .i18n import LANGUAGES, Catalog
from .output_view import OutputPanel
from .param_form import CommandForm
from .theme import PALETTES, THEME_CHOICES, stylesheet

TREE_COMMAND_ROLE = Qt.ItemDataRole.UserRole + 1


class MainWindow(QMainWindow):
    def __init__(self, catalog: Catalog, prefs: Preferences, schema: Schema):
        super().__init__()
        self.catalog = catalog
        self.prefs = prefs
        self.schema = schema
        self.chinese = prefs.language == "zh_CN"
        self.runner = SeqkitRunner(prefs.output_line_limit, self)
        self.seqkit_path: Path | None = None
        self.seqkit_source = ""
        self.seqkit_version_text = ""

        self.setWindowTitle(catalog.tr("app_title"))
        self.setAcceptDrops(True)
        self.resize(1320, 860)
        # Below this the three columns stop being readable, and nothing in the
        # layout reflows well enough to justify letting the user get there.
        self.setMinimumSize(960, 600)
        icon = paths.assets_dir() / "app.png"
        if icon.is_file():
            self.setWindowIcon(QIcon(str(icon)))

        self._build_header()
        self._build_central()
        self._build_menus()

        status = QStatusBar(self)
        self.status_left = QLabel("", status)
        self.status_right = QLabel("", status)
        status.addWidget(self.status_left, 1)
        status.addPermanentWidget(self.status_right)
        self.setStatusBar(status)

        self.runner.stdout_chunk.connect(self.output.append_stdout)
        self.runner.stderr_chunk.connect(self.output.append_stderr)
        self.runner.finished.connect(self._on_finished)
        self.runner.state_changed.connect(self.output.set_state)

        self.refresh_seqkit()
        self._select_first_command()
        QTimer.singleShot(0, self.apply_theme)
        geometry = store.read(store.KEY_GEOMETRY)
        if geometry is not None:
            # QSettings is outside the program's control: an entry written by another
            # application under the same organization name, or edited by hand, can hold
            # anything, and a window that refuses to start over it is worse than a
            # default-sized one.
            try:
                self.restoreGeometry(geometry)
            except TypeError:
                pass

    # ---------------------------------------------------------------- header
    def _build_header(self) -> None:
        header = QWidget(self)
        header.setObjectName("HeaderBar")

        brand_row = QHBoxLayout()
        brand_row.setSpacing(8)
        icon_file = paths.assets_dir() / "app-32.png"
        if icon_file.is_file():
            brand_icon = QLabel(header)
            brand_icon.setPixmap(QPixmap(str(icon_file)).scaled(
                22, 22,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
            brand_row.addWidget(brand_icon)
        self.brand = QLabel(APP_NAME, header)
        self.brand.setObjectName("CommandTitle")
        brand_row.addWidget(self.brand)

        self.seqkit_chip = QLabel("", header)
        self.seqkit_chip.setObjectName("Badge")

        self.version_warning = QLabel("", header)
        self.version_warning.setObjectName("BadgeWarn")
        self.version_warning.setVisible(False)

        self.language_choice = _Choice(list(LANGUAGES.items()), self.catalog.language)
        self.theme_choice = _Choice(THEME_CHOICES, self.prefs.theme)
        self.language_choice.changed.connect(self._set_language)
        self.theme_choice.changed.connect(self._set_theme)

        self.settings_button = QPushButton(self.catalog.tr("Settings"), header)
        self.settings_button.setObjectName("Ghost")
        self.settings_button.clicked.connect(self.open_settings)
        self.help_button = QPushButton(self.catalog.tr("Documentation"), header)
        self.help_button.setObjectName("Ghost")
        self.help_button.clicked.connect(self.open_docs)

        row = QHBoxLayout(header)
        row.setContentsMargins(16, 10, 16, 10)
        row.setSpacing(12)
        row.addLayout(brand_row)
        row.addWidget(self.seqkit_chip)
        row.addWidget(self.version_warning)
        row.addStretch(1)
        self.language_label = QLabel(self.catalog.tr("Language") + ":", header)
        self.theme_label = QLabel(self.catalog.tr("Theme") + ":", header)
        # Field labels read as captions next to the chips they introduce.
        self.language_label.setObjectName("HeaderLabel")
        self.theme_label.setObjectName("HeaderLabel")
        row.addWidget(self.language_label)
        row.addWidget(self.language_choice)
        row.addWidget(self.theme_label)
        row.addWidget(self.theme_choice)
        row.addWidget(self.settings_button)
        row.addWidget(self.help_button)
        self.header_bar = header

    # --------------------------------------------------------------- central
    def _build_central(self) -> None:
        self.search_box = QLineEdit(self)
        self.search_box.setObjectName("SearchBox")
        self.search_box.setPlaceholderText(self.catalog.tr("Search commands"))
        self.search_box.setClearButtonEnabled(True)
        self.search_box.textChanged.connect(self._filter_commands)

        self.tree = QTreeWidget(self)
        self.tree.setHeaderHidden(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setRootIsDecorated(False)
        self.tree.setIndentation(14)
        self.tree.currentItemChanged.connect(self._on_tree_selection)

        left = QWidget(self)
        layout = QVBoxLayout(left)
        layout.setContentsMargins(10, 10, 6, 10)
        layout.setSpacing(8)
        layout.addWidget(self.search_box)
        layout.addWidget(self.tree, 1)

        self.form = CommandForm(self.catalog, self.chinese)
        self.form.changed.connect(self._update_command_preview)
        self.form.run_requested.connect(self.run)

        self.output = OutputPanel(self.catalog)
        self.output.run_requested.connect(self.run)
        self.output.stop_requested.connect(self.runner.stop)

        right_split = QSplitter(Qt.Orientation.Vertical, self)
        right_split.addWidget(self.form)
        right_split.addWidget(self.output)
        right_split.setStretchFactor(0, 3)
        right_split.setStretchFactor(1, 2)
        right_split.setCollapsible(0, False)
        right_split.setCollapsible(1, False)

        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.splitter.addWidget(left)
        self.splitter.addWidget(right_split)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([280, 1040])
        saved_sizes = store.read(store.KEY_SPLITTER)
        # ``closeEvent`` writes this key, so a launch after the first one restores the
        # columns the user left. Anything that is not exactly one integer per panel is
        # ignored rather than applied: QSettings can hold a value this program never
        # wrote, and a wrong-length size list lays the panels out wrongly.
        if (isinstance(saved_sizes, list)
                and len(saved_sizes) == self.splitter.count()
                and all(isinstance(item, int) for item in saved_sizes)):
            self.splitter.setSizes(saved_sizes)

        shell = QWidget(self)
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)
        shell_layout.addWidget(self.header_bar)
        shell_layout.addWidget(self.splitter, 1)
        self.setCentralWidget(shell)

    def _build_menus(self) -> None:
        bar = self.menuBar()
        bar.clear()

        self.file_menu = bar.addMenu(self.catalog.tr("File"))
        open_action = QAction(self.catalog.tr("Add input files"), self)
        open_action.setShortcut(QKeySequence("Ctrl+O"))
        open_action.triggered.connect(self._menu_add_files)
        run_action = QAction(self.catalog.tr("Run"), self)
        run_action.setShortcut(QKeySequence("Ctrl+R"))
        run_action.triggered.connect(self.run)
        quit_action = QAction(self.catalog.tr("Quit"), self)
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        quit_action.triggered.connect(self.close)
        self.file_menu.addAction(open_action)
        self.file_menu.addAction(run_action)
        self.recent_menu = QMenu(self.catalog.tr("Recent files"), self)
        self._rebuild_recent_menu()
        self.file_menu.addMenu(self.recent_menu)
        self.file_menu.addSeparator()
        self.file_menu.addAction(quit_action)

        self.view_menu = bar.addMenu(self.catalog.tr("View"))
        expand = QAction(self.catalog.tr("Expand all groups"), self)
        expand.triggered.connect(lambda: self.tree.expandAll())
        collapse = QAction(self.catalog.tr("Collapse all groups"), self)
        collapse.triggered.connect(lambda: self.tree.collapseAll())
        clear = QAction(self.catalog.tr("Clear output"), self)
        clear.triggered.connect(self.output.clear)
        command_search = QAction(self.catalog.tr("Search commands"), self)
        command_search.setShortcut(QKeySequence("Ctrl+L"))
        command_search.triggered.connect(
            lambda: (self.search_box.setFocus(Qt.FocusReason.ShortcutFocusReason),
                     self.search_box.selectAll()))
        search = QAction(self.catalog.tr("Search parameters"), self)
        search.setShortcut(QKeySequence("Ctrl+F"))
        search.triggered.connect(self.form.focus_filter)
        for action in (expand, collapse, clear, command_search, search):
            self.view_menu.addAction(action)

        self.tools_menu = bar.addMenu(self.catalog.tr("Tools"))
        settings_action = QAction(self.catalog.tr("Settings"), self)
        settings_action.setShortcut(QKeySequence("Ctrl+,"))
        settings_action.triggered.connect(self.open_settings)
        copy_action = QAction(self.catalog.tr("Copy command line"), self)
        copy_action.setShortcut(QKeySequence("Ctrl+Shift+C"))
        copy_action.triggered.connect(self._copy_command_line)
        locate_action = QAction(self.catalog.tr("Locate seqkit executable"), self)
        locate_action.triggered.connect(self._locate_manually)
        for action in (settings_action, copy_action, locate_action):
            self.tools_menu.addAction(action)

        self.help_menu = bar.addMenu(self.catalog.tr("Help"))
        docs_action = QAction(self.catalog.tr("Open documentation folder"), self)
        docs_action.triggered.connect(self.open_docs)
        upstream_action = QAction(self.catalog.tr("SeqKit official documentation"), self)
        upstream_action.triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://bioinf.shenwei.me/seqkit/")))
        about_action = QAction(self.catalog.tr("About SeqKit GUI"), self)
        about_action.triggered.connect(self.open_about)
        for action in (docs_action, upstream_action, about_action):
            self.help_menu.addAction(action)

    # ------------------------------------------------------------- seqkit
    def refresh_seqkit(self) -> None:
        found = seqkit_locator.locate(self.prefs.seqkit_path)
        self.seqkit_path = found.path
        self.seqkit_source = found.source
        self.seqkit_version_text = seqkit_locator.probe_version(found.path) if found.found else ""

        if found.found:
            detected = self._detected_version()
            self.seqkit_chip.setText(f"SeqKit {detected}")
            self.seqkit_chip.setToolTip(str(found.path))
            mismatch = detected != self.schema.seqkit_version
            self.version_warning.setVisible(mismatch)
            if mismatch:
                self.version_warning.setText(self.catalog.tr("Version mismatch"))
                self.version_warning.setToolTip(self.catalog.tr("mismatch_hint").format(
                    expected=self.schema.seqkit_version, actual=detected or "?"))
            self.status_left.setText(f"{found.path}  ({found.source})")
        else:
            self.seqkit_chip.setText(self.catalog.tr("seqkit not found"))
            self.seqkit_chip.setToolTip("")
            self.version_warning.setVisible(False)
            self.status_left.setText(self.catalog.tr("seqkit_missing_hint"))
        self.status_right.setText(
            f"{len(self.schema.usable)} {self.catalog.tr('commands')} · "
            f"{self.catalog.tr('Schema')} {self.schema.seqkit_version}")

    def _detected_version(self) -> str:
        for token in (self.seqkit_version_text or "").replace(",", " ").split():
            if token.lower().startswith("v") and any(char.isdigit() for char in token):
                return token[1:]
        return ""

    def _locate_manually(self) -> None:
        picked, _ = QFileDialog.getOpenFileName(
            self, self.catalog.tr("Choose the seqkit executable"), str(Path.home()))
        if picked:
            self.prefs.seqkit_path = picked
            self.prefs.save()
            self.refresh_seqkit()

    # ------------------------------------------------------------- commands
    def _populate_tree(self, needle: str) -> None:
        self.tree.blockSignals(True)
        self.tree.clear()
        needle = needle.strip().lower()
        matched = 0
        for group, commands in self.schema.in_groups():
            visible = [
                command for command in commands
                if not needle
                or needle in command.name.lower()
                or needle in command.summary(self.chinese).lower()
                or needle in command.short.lower()
                or any(needle in alias.lower() for alias in command.aliases)
            ]
            if not visible:
                continue
            matched += len(visible)
            parent = QTreeWidgetItem([group.label(self.chinese)])
            parent.setFlags(parent.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            bold = parent.font(0)
            bold.setBold(True)
            parent.setFont(0, bold)
            self.tree.addTopLevelItem(parent)
            for command in visible:
                item = QTreeWidgetItem([f"{command.name}  ·  {command.summary(self.chinese)}"])
                item.setData(0, TREE_COMMAND_ROLE, command.key)
                item.setToolTip(0, f"{command.display}\n{command.short}")
                parent.addChild(item)
        self.tree.expandAll()
        self.search_box.setToolTip(self.catalog.tr("matched_commands").format(count=matched))
        self.tree.blockSignals(False)

    def _filter_commands(self, text: str) -> None:
        current = self.current_command()
        self._populate_tree(text)
        if current is not None:
            self._select_by_key(current.key)

    def _select_first_command(self) -> None:
        self._populate_tree("")
        for index in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(index)
            if group.childCount():
                self.tree.setCurrentItem(group.child(0))
                return
        self.form.set_command(None)

    def _select_by_key(self, key: str) -> None:
        for top in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(top)
            for child in range(group.childCount()):
                item = group.child(child)
                if item.data(0, TREE_COMMAND_ROLE) == key:
                    self.tree.setCurrentItem(item)
                    return

    def _on_tree_selection(self, current, _previous) -> None:
        if current is None:
            return
        key = current.data(0, TREE_COMMAND_ROLE)
        command = self.schema.get(key) if key else None
        if command is None:
            return
        self.form.set_command(command, self.prefs.working_dir or self.default_working_dir())
        self._update_command_preview()

    def current_command(self) -> Command | None:
        return self.form.command

    def default_working_dir(self) -> str:
        files = self.form.inputs()
        if files:
            parent = Path(files[0]).parent
            if parent.is_dir():
                return str(parent)
        return str(Path.home())

    # ----------------------------------------------------------------- run
    def run(self) -> None:
        if self.runner.state.busy:
            return
        if self.seqkit_path is None:
            QMessageBox.warning(self, self.catalog.tr("seqkit not found"),
                                 self.catalog.tr("seqkit_missing_hint"))
            self.open_settings()
            return
        if self.current_command() is None:
            return

        request = self.form.collect()
        problems = validate(request)
        if not problems.ok:
            self.form.mark_missing(problems.problem_flags)
            QMessageBox.warning(self, self.catalog.tr("Incomplete parameters"),
                                "\n".join(problems.messages(self.catalog.tr)))
            return

        argv = build_argv(request)
        program = str(self.seqkit_path)
        command_line = display_command(program, argv)
        working = request.working_dir or str(Path.home())
        self.form.mark_missing(set())
        self.form.set_busy(True)
        self.output.begin_run(command_line, working)
        self.runner.start(program, argv, working, command_line)
        for path in request.inputs:
            store.push_recent_file(path)

    def _on_finished(self, result: RunResult) -> None:
        self.output.end_run(result)
        self.form.set_busy(False)
        if result.succeeded and result.stdout_bytes == 0:
            self.status_left.setText(self.catalog.tr("empty_output_hint"))
        elif result.succeeded and (result.stdout_file or result.working_dir):
            self.status_left.setText(
                self.catalog.tr("done_hint") + f"  {result.stdout_file or ''}".rstrip())
        elif self.seqkit_path is not None:
            self.status_left.setText(f"{self.seqkit_path}  ({self.seqkit_source})")

    def _update_command_preview(self) -> None:
        if self.current_command() is None:
            return
        request = self.form.collect()
        program = str(self.seqkit_path) if self.seqkit_path else "seqkit"
        line = display_command(program, build_argv(request))
        # The status bar clips a long argument vector; the whole line stays readable
        # by hovering, and Ctrl+Shift+C copies the same text from the Command tab.
        self.status_right.setToolTip(line)
        self.status_right.setText(line)

    def _copy_command_line(self) -> None:
        QApplication.clipboard().setText(self.output.command_view.toPlainText())
        self.status_left.setText(self.catalog.tr("Command copied"))

    def _menu_add_files(self) -> None:
        picked, _ = QFileDialog.getOpenFileNames(
            self, self.catalog.tr("Add input files"), self.default_working_dir())
        if picked:
            self.form.file_field.add(picked)

    # ---------------------------------------------------------------- drops
    def dragEnterEvent(self, event) -> None:  # noqa: D102 - Qt override
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: D102 - Qt override
        files = [url.toLocalFile() for url in event.mimeData().urls() if url.toLocalFile()]
        if files:
            self.form.file_field.add(files)
            event.acceptProposedAction()

    # ----------------------------------------------------------- appearance
    def apply_theme(self) -> None:
        palette = PALETTES.get(self.prefs.theme, PALETTES["light"])
        QApplication.instance().setStyleSheet(stylesheet(palette))

    def _set_theme(self, value: str) -> None:
        self.prefs.theme = value
        self.prefs.save()
        self.apply_theme()
        self.theme_choice.set_value(value)

    def _set_language(self, value: str) -> None:
        if value == self.catalog.language:
            return
        self.catalog.set_language(value)
        self.chinese = value == "zh_CN"
        self.prefs.language = value
        self.prefs.save()
        self._populate_tree(self.search_box.text())
        # ``retranslate`` rebuilds the parameter form for the current command;
        # the input-file list and working directory live outside the rebuilt
        # rows, so they survive the rebuild unchanged.
        self.form.retranslate(self.chinese)
        self._build_menus()
        self.output.retranslate()
        self.output.refresh_status()
        self.language_label.setText(self.catalog.tr("Language") + ":")
        self.theme_label.setText(self.catalog.tr("Theme") + ":")
        self.language_choice.set_value(value)
        self.settings_button.setText(self.catalog.tr("Settings"))
        self.help_button.setText(self.catalog.tr("Documentation"))
        self.refresh_seqkit()

    def _rebuild_recent_menu(self) -> None:
        self.recent_menu.clear()
        recent = store.recent_files()
        for path in recent:
            action = QAction(path, self)
            action.triggered.connect(lambda _=False, item=path: self._use_recent(item))
            self.recent_menu.addAction(action)
        if recent:
            self.recent_menu.addSeparator()
            clear = QAction(self.catalog.tr("Clear list"), self)
            clear.triggered.connect(self._clear_recent)
            self.recent_menu.addAction(clear)

    def _use_recent(self, path: str) -> None:
        if Path(path).is_file():
            self.form.file_field.add([path])
        else:
            self.status_left.setText(self.catalog.tr("File no longer exists") + f": {path}")

    def _clear_recent(self) -> None:
        store.remove(store.KEY_RECENT_FILES)
        self._rebuild_recent_menu()

    # -------------------------------------------------------------- dialogs
    def open_settings(self) -> None:
        copy = Preferences(
            seqkit_path=self.prefs.seqkit_path,
            language=self.prefs.language,
            theme=self.prefs.theme,
            output_line_limit=self.prefs.output_line_limit,
            working_dir=self.prefs.working_dir,
        )
        dialog = PreferencesDialog(self.catalog, copy, self)
        if dialog.exec():
            self.prefs = dialog.values()
            self.prefs.save()
            self.runner.set_preview_limit(self.prefs.output_line_limit)
            if self.prefs.language != self.catalog.language:
                self._set_language(self.prefs.language)
            else:
                self._set_theme(self.prefs.theme)
            self.refresh_seqkit()

    def open_docs(self) -> None:
        docs = paths.docs_dir()
        if docs.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(docs)))
        else:
            QMessageBox.information(self, self.catalog.tr("Documentation"), str(docs))

    def open_about(self) -> None:
        AboutDialog(self.catalog, self.schema, self.seqkit_version_text, self).exec()

    # --------------------------------------------------------------- closing
    def closeEvent(self, event) -> None:  # noqa: D102 - Qt override
        if self.runner.state.busy:
            answer = QMessageBox.question(
                self, self.catalog.tr("seqkit is still running"),
                self.catalog.tr("stop seqkit before closing"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.runner.stop()
        store.write(store.KEY_SPLITTER, self.splitter.sizes())
        store.write(store.KEY_GEOMETRY, self.saveGeometry())
        event.accept()
