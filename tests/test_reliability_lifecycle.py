"""What the window does while a child process is still running.

Every case here needs a run that is genuinely still going while the interface is poked,
so it uses a command the validator accepts and that stays alive on purpose: ``scat`` with
a directory and ``--time-limit``, which is SeqKit's own "quit after being idle" bound and
the one a user can set. The process is stopped in the test's own teardown, so no case can
leave a watcher running behind it.

The properties under test are the ones a user cannot work around: whether Stop is still
there, whether the form is still locked, whether a second click on Run launches a second
child, and whether closing the window takes the child with it.
"""

import time

import pytest

from seqkit_gui.core.settings import Preferences
from seqkit_gui.core.spec import load
from seqkit_gui.ui.i18n import Catalog
from seqkit_gui.ui.main_window import MainWindow

pytestmark = [pytest.mark.gui]

#: Long enough that every assertion below happens while the child is alive, short
#: enough that a missed teardown cannot outlive the session.
IDLE_BOUND = "30s"


def pump_until(qapp, predicate, timeout=30.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    qapp.processEvents()
    return predicate()


def plain_window(root, language="en_US"):
    catalog = Catalog(language, directory=root / "seqkit_gui" / "i18n")
    return MainWindow(catalog, Preferences(seqkit_path="", language=language), load())


def arm_scatter(window, tmp_path, qapp, bound=True):
    """Point the form at ``scat`` with a folder, optionally with its idle bound."""
    folder = tmp_path / f"watched{len(list(tmp_path.glob('watched*')))}"
    folder.mkdir()
    (folder / "one.fq").write_text("@r1\nATGC\n+\nIIII\n", encoding="utf-8")
    window.form.set_command(window.schema.get("scat"), str(tmp_path))
    window.form.file_field.clear()
    window.form.file_field.add([str(folder)])
    if bound:
        row = next(item for item in window.form.rows if item.flag.name == "time-limit")
        row.set_enabled(True)
        row.editor.set_text(IDLE_BOUND)
    return folder


def start_a_long_run(window, tmp_path, qapp) -> int:
    """Launch a run that stays alive and return the child's pid."""
    arm_scatter(window, tmp_path, qapp)
    window.run()
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        qapp.processEvents()
        pid = window.runner._process.processId()
        if pid:
            return int(pid)
        time.sleep(0.02)
    return 0


@pytest.fixture
def busy_window(qapp, root, fresh_settings, tmp_path):
    """A window with a legal, still-running ``scat`` in it, stopped when the test ends."""
    window = plain_window(root)
    window.show()
    qapp.processEvents()
    start_a_long_run(window, tmp_path, qapp)
    assert window.runner.state.busy, "the reference run is not running"
    try:
        yield window
    finally:
        window.runner.stop()
        pump_until(qapp, lambda: not window.runner.state.busy, 20.0)
        window.deleteLater()


# -------------------------------------------------------------------------- closing
@pytest.mark.slow
def test_closing_is_refused_while_seqkit_is_running(qapp, root, monkeypatch, process_probe,
                                                    tmp_path):
    """Answering "No" keeps the window open and the child alive."""
    from seqkit_gui.ui import main_window as module

    window = plain_window(root)
    window.show()
    qapp.processEvents()
    asked = []
    monkeypatch.setattr(
        module.QMessageBox, "question",
        lambda *a, **k: asked.append(a[2] if len(a) > 2 else "")
        or module.QMessageBox.StandardButton.No)

    pid = start_a_long_run(window, tmp_path, qapp)
    assert pid, "the reference child never started"
    window.close()
    qapp.processEvents()

    assert asked, "closing during a run has to ask first"
    assert window.isVisible(), "answering No must not close the window"
    assert window.runner.state.busy, "answering No must not stop the child either"
    assert process_probe.alive(pid), f"pid {pid} died anyway"
    window.runner.stop()
    assert pump_until(qapp, lambda: not window.runner.state.busy, 20.0)
    window.deleteLater()


@pytest.mark.slow
def test_closing_after_the_child_was_stopped_leaves_no_orphan(qapp, root, monkeypatch,
                                                             process_probe, tmp_path):
    """Answering "Yes" has to take the child with it: no orphaned seqkit process."""
    from seqkit_gui.ui import main_window as module

    window = plain_window(root)
    window.show()
    qapp.processEvents()
    monkeypatch.setattr(module.QMessageBox, "question",
                        lambda *a, **k: module.QMessageBox.StandardButton.Yes)

    pid = start_a_long_run(window, tmp_path, qapp)
    assert pid, "the reference child never started"

    window.close()
    qapp.processEvents()
    assert pump_until(qapp, lambda: not window.runner.state.busy, 20.0), (
        "the runner still reports a running child after the window was closed")
    assert pump_until(qapp, lambda: not process_probe.alive(pid), 20.0), (
        f"seqkit pid {pid} outlived the window")
    survivors = process_probe.children() or set()
    assert pid not in survivors
    window.deleteLater()


# ----------------------------------------------------------------- re-entrancy
def test_a_second_run_click_starts_no_second_child(busy_window, qapp):
    window = busy_window
    first = int(window.runner._process.processId())
    assert first
    window.run()
    window.run()
    qapp.processEvents()
    assert int(window.runner._process.processId()) == first, (
        "clicking Run again replaced the running child")
    assert window.runner.state.busy


def test_the_form_is_locked_while_a_run_is_ongoing(busy_window):
    window = busy_window
    assert not window.form.extra_box.isEnabled()
    assert not window.form.working_box.isEnabled()
    for row in window.form.rows:
        if row.enabled:
            assert not row.editor.isEnabled(), row.flag.name


def test_starting_a_run_while_one_is_live_is_ignored_by_the_runner(qapp, busy_window):
    """The guard sits under the button too, so no caller can bypass it."""
    window = busy_window
    pid = int(window.runner._process.processId())
    window.runner.start(str(window.seqkit_path), ["version"], "", "version")
    qapp.processEvents()
    assert int(window.runner._process.processId()) == pid, (
        "the runner accepted a second launch while busy")


# ------------------------------------------------------- language and theme changes
def test_switching_the_theme_mid_run_leaves_the_child_alone(busy_window, qapp):
    from PySide6.QtWidgets import QApplication

    window = busy_window
    pid = int(window.runner._process.processId())
    window._set_theme("dark")
    qapp.processEvents()
    assert "22252a" in QApplication.instance().styleSheet()
    assert window.runner.state.busy
    assert int(window.runner._process.processId()) == pid
    window._set_theme("light")
    qapp.processEvents()


def test_switching_the_language_mid_run_keeps_the_run_running_and_stoppable(
        busy_window, qapp):
    """A live retranslation must not forget that a child is still out there.

    ``_set_language`` rebuilds the command tree and the parameter form and re-reads the
    seqkit badge; the run itself is untouched by that, so the panel has to keep saying
    Stop, the form has to stay locked, and the run must still be cancellable afterwards.
    The selected command and its input list are carried across on purpose, so they are
    asserted too -- a switch that silently dropped the user's files would be worse.
    """
    window = busy_window
    pid = int(window.runner._process.processId())

    window._set_language("zh_CN")
    qapp.processEvents()

    assert window.catalog.language == "zh_CN"
    assert window.runner.state.busy, (
        "the panel stopped reporting a run that is still running")
    assert int(window.runner._process.processId()) == pid
    assert window.output.stop_button.isVisible(), (
        "Stop disappeared while seqkit was still running")
    assert not window.output.run_button.isVisible()
    assert window.current_command().key == "scat"
    assert window.form.inputs(), "the input list was dropped by the retranslation"
    assert not window.form.working_box.isEnabled(), (
        "the form was unlocked by the retranslation while a run was live")

    window.runner.stop()
    assert pump_until(qapp, lambda: not window.runner.state.busy, 20.0)


# ---------------------------------------------------------------------- input rules
def test_a_run_without_input_files_is_not_blocked_and_says_the_output_was_empty(
        qapp, root, monkeypatch, tmp_path):
    """``min = 0`` means the form lets it through, and the child answers with nothing.

    Measured against the shipped binary through the process layer: with no positional
    input and the write channel closed, ``seqkit seq`` exits 0 immediately having
    produced zero bytes -- it does not wait for a stdin nobody writes to, and it does
    not fail. So the interface must not block the run (commands that legitimately read a
    pipe would be unreachable), must not hang, and has to tell the user the result is
    empty instead of showing a blank pane that looks like a successful conversion.
    """
    from seqkit_gui.ui import main_window as module

    window = plain_window(root)
    window.show()
    qapp.processEvents()
    warned = []
    monkeypatch.setattr(module.QMessageBox, "warning",
                        lambda *a, **k: warned.append(a[2] if len(a) > 2 else ""))
    outcome = []
    window.runner.finished.connect(outcome.append)

    command = window.schema.get("seq")
    assert command.inputs.min == 0, command.inputs.min
    window.form.set_command(command, str(tmp_path))
    window.form.file_field.clear()
    window.form.working_box.setText(str(tmp_path))
    started = time.monotonic()
    window.run()
    qapp.processEvents()

    assert not warned, f"the form refused a legal no-input run: {warned}"
    assert pump_until(qapp, lambda: bool(outcome), 30.0), (
        "a no-input run is still going: the child waited for something")
    result = outcome[-1]
    assert result.elapsed < 15, f"the child blocked on input: {result.elapsed:.1f}s"
    assert result.succeeded and result.stdout_bytes == 0, result
    hint = window.catalog.tr("empty_output_hint")
    assert hint in window.status_left.text(), window.status_left.text()
    assert window.catalog.tr("Failed") not in window.output.status.text()
    window.deleteLater()


def test_an_unbounded_scat_is_refused_before_the_child_starts(qapp, root, tmp_path,
                                                             monkeypatch):
    """The watcher rule is enforced in the window, not only inside the validator."""
    from seqkit_gui.ui import main_window as module

    window = plain_window(root)
    window.show()
    qapp.processEvents()
    warned = []
    monkeypatch.setattr(module.QMessageBox, "warning",
                        lambda *a, **k: warned.append(a[2] if len(a) > 2 else ""))

    arm_scatter(window, tmp_path, qapp, bound=False)
    window.run()
    qapp.processEvents()

    assert warned, "a run that could never finish must be refused with a message"
    assert not window.runner.state.busy, "the endless child was started anyway"
    assert any("--find-only" in message or "--time-limit" in message for message in warned), \
        warned
    window.deleteLater()
