"""The refusal paths of :class:`SeqkitRunner` have to report, never raise.

``SeqkitRunner.start()`` has two ways to turn down a run before the child exists:
the argument preflight, and a temporary output file that cannot be created. Both
announce themselves through ``finished`` with a ``RunResult`` carrying
``start_error`` -- the window unlocks its form from that signal alone, so a refusal
that escapes as an exception, or that is never delivered, leaves the interface
stuck on "running".

The output-file path is the delicate one. The refusal is delivered by
``QTimer.singleShot(0, ...)``: the callback runs after ``start()`` has returned,
which is after Python has unbound the ``except ... as exc`` name, so the message has
to be composed inside the handler and only then handed to the timer. These tests
refuse ``mkstemp`` and pump the event loop, so a message that cannot be built shows
up as a refusal that never arrives rather than as a traceback Qt swallows.
"""

from __future__ import annotations

import errno
import sys
import tempfile

from PySide6.QtCore import QCoreApplication, QProcess

from seqkit_gui.core.runner import RunResult, SeqkitRunner, State


def _refusing_mkstemp(*_args, **_kwargs):
    """What a read-only or full temporary directory does to ``mkstemp``."""
    raise OSError(errno.EACCES, "Permission denied", "seqkit-gui-out")


def _write_program(tmp_path):
    """An absolute existing file: all the preflight asks of this path."""
    program = tmp_path / "seqkit.exe"
    program.write_bytes(b"MZ\x90\x00\x03\x00\x00\x00 placeholder image header")
    return program


def _start_refused_run(tmp_path, monkeypatch):
    """Put a runner down the output-file refusal and hand back what it reported."""
    program = _write_program(tmp_path)
    instance = SeqkitRunner(2000)
    results: list[RunResult] = []
    instance.finished.connect(results.append)
    escaped: list[str] = []

    def record(kind, value, _traceback):
        escaped.append(f"{kind.__name__}: {value}")

    # An exception inside a Qt callback reaches sys.excepthook, not the caller.
    monkeypatch.setattr(sys, "excepthook", record)
    monkeypatch.setattr(tempfile, "mkstemp", _refusing_mkstemp)

    instance.start(str(program), ["version"], str(tmp_path), "seqkit version")
    for _ in range(20):                     # the zero-timer lands on the next pass
        QCoreApplication.processEvents()
        if results:
            break
    return instance, results, escaped


def test_a_refused_temp_file_reports_through_finished(qapp, tmp_path, monkeypatch):
    """No child is started, and the refusal still arrives as a result."""
    instance, results, escaped = _start_refused_run(tmp_path, monkeypatch)

    assert escaped == [], f"the deferred message raised: {escaped}"
    assert len(results) == 1, "the refusal never reached finished"
    result = results[0]
    assert result.exit_code == -1
    assert "cannot create the output file" in result.start_error, result.start_error
    assert "Permission denied" in result.start_error, result.start_error
    assert not result.succeeded
    assert result.stdout_file is None
    assert result.command_line == "seqkit version"
    assert result.working_dir == str(tmp_path)
    assert instance.state is State.IDLE
    assert not instance.state.busy


def test_a_refused_temp_file_leaves_no_process_and_no_sink(qapp, tmp_path, monkeypatch):
    """The runner stays idle between calls: nothing spawned, nothing left open."""
    instance, results, escaped = _start_refused_run(tmp_path, monkeypatch)

    assert results, "the window has nothing to unlock the form with"
    assert escaped == []
    assert instance._process.state() is QProcess.ProcessState.NotRunning
    assert instance._sink is None
    assert instance.stdout_file is None
