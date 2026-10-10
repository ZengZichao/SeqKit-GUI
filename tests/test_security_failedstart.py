"""A launch that never came up has to be closed out by the runner itself.

``QProcess`` announces a failed launch through ``errorOccurred`` and, with no child in
existence, never emits ``finished``. Everything that launch still holds -- the 200 ms
tick timer, the open tee descriptor, and the running state the form was locked in --
belongs to the runner alone, and the window unlocks itself from ``finished`` alone.

The accumulator here is attached before ``start()`` and keeps counting after the first
result lands, because exactly one callback per launch is the contract: a second one,
unlocking the form a second time, is the same class of bug as none at all.
"""

from __future__ import annotations

import time

from PySide6.QtCore import QCoreApplication, QEventLoop, QProcess, QTimer

from seqkit_gui.core.runner import RunResult, SeqkitRunner, State


def _pump(milliseconds: int) -> None:
    """Run a nested event loop for a fixed while."""
    loop = QEventLoop()
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(milliseconds)
    loop.exec()
    timer.stop()


def _wait_for_reports(reports: list, count: int, timeout: int = 20000,
                      quiet_window: int = 1500) -> None:
    """Pump until ``count`` callbacks are in, then give a duplicate room to show up."""
    deadline = time.monotonic() + timeout / 1000
    while time.monotonic() < deadline and len(reports) < count:
        QCoreApplication.processEvents()
        time.sleep(0.005)
    _pump(quiet_window)


def _discard(runner: SeqkitRunner) -> None:
    """Drop the tee file a closed-out run left behind."""
    path = runner.stdout_file
    if path is not None and path.is_file():
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def _failed_launch(fake_binary):
    """Start a real absolute file that passes the preflight and cannot be executed.

    Returns the runner and the list every ``finished`` callback is appended to.
    """
    runner = SeqkitRunner(2000)
    reports: list[RunResult] = []
    runner.finished.connect(reports.append)
    path = fake_binary.text()
    runner.start(str(path), ["version"], str(path.parent), "plain text")
    return runner, reports


def test_a_failed_launch_reports_a_result_exactly_once(qapp, fake_binary):
    """The damaged ``bin/seqkit.exe`` case: an answer, once, and no locked form."""
    runner, reports = _failed_launch(fake_binary)
    try:
        _wait_for_reports(reports, 1)

        assert len(reports) == 1, f"one launch, {len(reports)} callbacks: {reports}"
        result = reports[0]
        assert result.exit_code == -1, result
        assert result.start_error == "FailedToStart", result.start_error
        assert not result.succeeded
        assert result.command_line == "plain text", result.command_line
        assert result.elapsed >= 0
        assert runner.state is State.IDLE
        assert not runner.state.busy
    finally:
        _discard(runner)


def test_a_failed_launch_releases_the_timer_and_the_sink(qapp, fake_binary):
    """The close-out lets go of the whole run, not merely talks about it."""
    runner, reports = _failed_launch(fake_binary)
    try:
        _wait_for_reports(reports, 1)

        assert reports, "nothing was reported, so nothing was released"
        assert not runner._timer.isActive(), "the tick timer outlived the launch"
        assert runner._sink is None, "the tee descriptor stayed open"
        assert runner._process.state() is QProcess.ProcessState.NotRunning
        assert runner._process.processId() == 0
        assert runner._reported, "the launch stayed unmarked as reported"
    finally:
        _discard(runner)


def test_a_finished_that_arrives_anyway_adds_no_second_result(qapp, fake_binary):
    """Deduplication: the close-out and ``finished`` cannot both report one launch."""
    runner, reports = _failed_launch(fake_binary)
    try:
        _wait_for_reports(reports, 1)
        assert len(reports) == 1, reports

        # A late ``finished`` for the very same launch -- the Qt behaviour this path
        # has to be ready for -- must find nothing left to say.
        runner._on_finished(0, QProcess.ExitStatus.NormalExit)
        QCoreApplication.processEvents()
        _pump(500)
        assert len(reports) == 1, f"the same launch reported {len(reports)} times"
        assert runner.state is State.IDLE
        assert runner._sink is None

        runner.stop()
        QCoreApplication.processEvents()
        _pump(500)
        assert len(reports) == 1, "Stop on an idle runner reported again"
    finally:
        _discard(runner)


def test_a_failed_launch_leaves_the_runner_reusable(qapp, fake_binary, seqkit_binary,
                                                  tmp_path):
    """One closed-out launch must not cost the user every later run of the session."""
    runner, reports = _failed_launch(fake_binary)
    try:
        _wait_for_reports(reports, 1)
        assert len(reports) == 1, reports
        assert not reports[0].succeeded

        runner.start(str(seqkit_binary), ["version"], str(tmp_path), "seqkit version")
        _wait_for_reports(reports, 2, timeout=30000)

        assert len(reports) == 2, f"the second run reported {len(reports) - 1} time(s)"
        second = reports[1]
        assert second.command_line == "seqkit version", second
        assert second.succeeded, second
        assert second.start_error == "", second.start_error
        assert second.stdout_file is not None
        assert "seqkit" in second.stdout_file.read_text(
            encoding="utf-8", errors="replace").lower()
    finally:
        _discard(runner)
