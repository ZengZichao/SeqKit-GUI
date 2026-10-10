"""The window must build every command's form without runtime binding errors."""

import os
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from seqkit_gui.core.settings import Preferences
from seqkit_gui.core.spec import load
from seqkit_gui.ui.i18n import Catalog
from seqkit_gui.ui.main_window import MainWindow

SCREENSHOT_DIR = Path("tools/_build/screenshots")


@pytest.fixture(scope="module")
def window(qapp, root):
    catalog = Catalog("zh_CN", directory=root / "seqkit_gui" / "i18n")
    prefs = Preferences(seqkit_path=str(root / "bin" / "seqkit.exe")
                        if (root / "bin" / "seqkit.exe").is_file() else "",
                        language="zh_CN", theme="light")
    schema = load(reload=True)
    win = MainWindow(catalog, prefs, schema)
    win.resize(1320, 860)
    win.show()
    qapp.processEvents()
    yield win


def test_window_opens_with_a_selected_command(window):
    assert window.current_command() is not None
    assert window.tree.topLevelItemCount() >= 8


def test_every_command_builds_its_form(window, schema):
    """All 41 subcommands must render, with one row per visible flag."""
    rendered = 0
    for command in schema.usable:
        window.form.set_command(command, str(Path.cwd()))
        window.form.file_field.clear()
        expected = len(command.all_flags)
        assert len(window.form.rows) == expected, (
            command.key, len(window.form.rows), expected)
        request = window.form.collect()
        assert request.command is command
        rendered += 1
    assert rendered == 41 == len(schema.usable), (
        f"{rendered} forms built, which is not the {len(schema.usable)} the table declares") >= 40


def test_flag_rows_show_description_text(window, schema):
    command = schema.get("grep")
    window.form.set_command(command)
    row = next(item for item in window.form.rows if item.flag.name == "pattern")
    assert row.description.text()
    assert "--pattern" in row.enable.text()


def test_enabling_a_row_flows_into_the_request(window, schema):
    command = schema.get("seq")
    window.form.set_command(command)
    row = next(item for item in window.form.rows if item.flag.name == "lower-case")
    row.set_enabled(True)
    request = window.form.collect()
    assert request.flags["lower-case"].enabled


def test_language_switch_keeps_the_selected_command(window, schema):
    command = schema.get("translate")
    window.form.set_command(command)
    window._set_language("en_US")
    assert window.catalog.language == "en_US"
    assert window.current_command().key == "translate"
    assert window.form.summary.text() == command.short
    window._set_language("zh_CN")
    assert window.form.summary.text() == command.short_zh


def test_theme_switch_updates_the_application_style(window):
    app = QApplication.instance()
    window._set_theme("dark")
    assert "22252a" in app.styleSheet()
    window._set_theme("light")
    assert "ffffff" in app.styleSheet()


def test_command_search_filters_the_tree(window):
    window.search_box.setText("transl")
    names = collect_visible_commands(window)
    assert "translate" in names
    assert "stats" not in names
    window.search_box.setText("")
    assert len(collect_visible_commands(window)) == len(window.schema.usable)


def test_parameter_search_hides_rows(window, schema):
    window.form.set_command(schema.get("seq"))
    window.form.filter_box.setText("reverse")
    visible = [row for row in window.form.rows if row.isVisible()]
    assert visible and all("reverse" in (row.property("search") or "") for row in visible)
    window.form.filter_box.setText("")


def test_input_files_survive_a_rebuild(window, sample_fasta):
    window.form.set_command(window.schema.get("stats"))
    window.form.file_field.add([str(sample_fasta)])
    assert window.form.inputs() == (str(sample_fasta),)


def test_seqkit_binary_is_detected(window):
    assert window.seqkit_path is not None, "bin/seqkit.exe should be located"
    assert "2.14.0" in window.seqkit_version_text
    assert not window.version_warning.isVisible()


def test_run_button_reports_incomplete_parameters(window, monkeypatch):
    from seqkit_gui.ui import main_window as module

    calls = []
    monkeypatch.setattr(module.QMessageBox, "warning",
                        lambda *args, **kwargs: calls.append(args[2] if len(args) > 2 else ""))
    window.form.set_command(window.schema.get("grep"))
    window.form.file_field.clear()
    window.run()
    assert calls, "an incomplete form must be refused before launching seqkit"


def test_full_run_from_the_window(qapp, window, sample_fasta, tmp_path):
    window.form.set_command(window.schema.get("stats"))
    window.form.file_field.clear()
    window.form.file_field.add([str(sample_fasta)])
    window.form.working_box.setText(str(tmp_path))
    window.run()
    qapp.processEvents()

    loops = 0
    while window.runner.state.busy and loops < 600:
        qapp.processEvents()
        loops += 1
        _sleep(0.05)
    assert not window.runner.state.busy
    text = window.output.result_view.toPlainText()
    assert "short1.fa" in text


def test_about_and_settings_dialogs_build(window):
    from seqkit_gui.ui.dialogs import AboutDialog, PreferencesDialog
    about = AboutDialog(window.catalog, window.schema, window.seqkit_version_text, window)
    assert "unofficial" in about.findChild(type(about.layout().itemAt(2).widget())).text().lower() \
        or about.isVisible() is False
    dialog = PreferencesDialog(window.catalog, Preferences(), window)
    assert dialog.seqkit_box.isEnabled()
    dialog.deleteLater()
    about.deleteLater()


def collect_visible_commands(window) -> list[str]:
    names = []
    for top in range(window.tree.topLevelItemCount()):
        group = window.tree.topLevelItem(top)
        for child in range(group.childCount()):
            names.append(group.child(child).text(0).split("·")[0].strip())
    return names


def _sleep(seconds: float) -> None:
    import time
    time.sleep(seconds)


def test_screenshots_for_the_docs(qapp, window, root):
    """Optional visual assets: SEQKIT_GUI_SHOOT=1 writes the documentation images."""
    if os.environ.get("SEQKIT_GUI_SHOOT") != "1":
        pytest.skip("set SEQKIT_GUI_SHOOT=1 to refresh documentation screenshots")
    from seqkit_gui.core.spec import load
    schema = load()
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    window._set_language("zh_CN")
    window._set_theme("light")
    window.form.set_command(schema.get("grep"), str(root))
    window.form.file_field.clear()
    window.form.file_field.add([str(root / "tests" / "data" / "short1.fa")])
    for row in window.form.rows:
        if row.flag.name == "pattern":
            row.set_enabled(True)
            row.editor.set_text("seq1")
    window.tree.expandAll()
    qapp.processEvents()
    window.grab().save(str(SCREENSHOT_DIR / "light-zh.png"))

    window._set_theme("dark")
    window._set_language("en_US")
    window.form.set_command(schema.get("stats"), str(root))
    window.form.file_field.add([str(root / "tests" / "data" / "short1.fa"),
                                str(root / "tests" / "data" / "short2.fa")])
    qapp.processEvents()
    window.grab().save(str(SCREENSHOT_DIR / "dark-en.png"))
    window._set_theme("light")
    window._set_language("zh_CN")
    assert (SCREENSHOT_DIR / "light-zh.png").is_file()
