"""Asynchronous execution of the seqkit child process.

stdout and stderr are streamed as they arrive so long runs show progress, and every
byte of stdout is additionally tee-d to a temporary file: a converted FASTA can be
far larger than what belongs in a text widget.
"""

from __future__ import annotations

import codecs
import os
import re
import tempfile
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import BinaryIO

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal


class State(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    STOPPING = "stopping"

    @property
    def busy(self) -> bool:
        return self in {State.RUNNING, State.STOPPING}


@dataclass
class RunResult:
    exit_code: int = 0
    crashed: bool = False
    cancelled: bool = False
    elapsed: float = 0.0
    stdout_bytes: int = 0
    dropped_lines: int = 0
    command_line: str = ""
    working_dir: str = ""
    stdout_file: Path | None = None
    start_error: str = ""

    @property
    def succeeded(self) -> bool:
        return self.exit_code == 0 and not self.crashed and not self.cancelled

    @property
    def truncated(self) -> bool:
        return self.dropped_lines > 0


_ERROR_TEXT = {
    QProcess.ProcessError.FailedToStart: "FailedToStart",
    QProcess.ProcessError.Crashed: "Crashed",
    QProcess.ProcessError.Timedout: "Timedout",
    QProcess.ProcessError.ReadError: "ReadError",
    QProcess.ProcessError.WriteError: "WriteError",
    QProcess.ProcessError.UnknownError: "UnknownError",
}


class SeqkitRunner(QObject):
    started = Signal()
    stdout_chunk = Signal(str)
    stderr_chunk = Signal(str)
    state_changed = Signal(object)
    finished = Signal(object)
    tick = Signal(float)

    def __init__(self, preview_line_limit: int = 5000, parent: QObject | None = None):
        super().__init__(parent)
        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)

        self._state = State.IDLE
        self._limit = max(200, int(preview_line_limit))
        self._sink: BinaryIO | None = None
        self._stdout_path: Path | None = None
        self._decoder_out = _new_decoder()
        self._decoder_err = _new_decoder()
        self._previewed = 0
        self._dropped = 0
        self._bytes = 0
        self._started = 0.0
        self._cancelled = False
        self._reported = False
        self._start_error = ""
        self._command_line = ""
        self._working_dir = ""

        self._timer = QTimer(self)
        self._timer.setInterval(200)
        self._timer.timeout.connect(self._tick)

    # -- properties ---------------------------------------------------------
    @property
    def state(self) -> State:
        return self._state

    @property
    def stdout_file(self) -> Path | None:
        return self._stdout_path

    def set_preview_limit(self, limit: int) -> None:
        self._limit = max(200, int(limit))

    # -- running ------------------------------------------------------------
    def start(self, program: str, argv: list[str], working_dir: str = "",
              command_line: str = "") -> None:
        """Launch ``program`` with ``argv`` as separate arguments.

        ``setProgram`` / ``setArguments`` are used instead of ``QProcess.start(command)``:
        the single-string overload is split by Qt's own command parser, which would let
        quotes and spaces inside a file name change what the child receives.
        """
        if self._state.busy:
            return

        problem = _preflight(program, argv, working_dir)
        if problem:
            # Refuse before touching the process, and still report through `finished`
            # so the panel leaves the "running" state it was put into.
            refused = RunResult(exit_code=-1, command_line=command_line,
                                working_dir=working_dir, start_error=problem)
            QTimer.singleShot(0, lambda: self.finished.emit(refused))
            return

        self._previewed = self._dropped = self._bytes = 0
        self._cancelled = False
        self._reported = False
        self._start_error = ""
        self._command_line = command_line
        self._working_dir = working_dir
        self._decoder_out = _new_decoder()
        self._decoder_err = _new_decoder()
        self._started = time.monotonic()

        try:
            # The descriptor is kept open as the file itself: closing it and reopening
            # by name would leave a window in which the predictable-ish temp name can
            # be swapped for a link to another file.
            descriptor, name = tempfile.mkstemp(prefix="seqkit-gui-", suffix=".out")
            self._stdout_path = Path(name)
            self._sink = os.fdopen(descriptor, "wb")
        except OSError as exc:
            self._sink = None
            self._stdout_path = None
            # The text is composed here, not inside the lambda: Python unbinds ``exc``
            # when the except block ends, and the callback runs afterwards.
            reason = f"cannot create the output file ({exc.strerror or exc})"
            QTimer.singleShot(0, lambda: self.finished.emit(
                RunResult(exit_code=-1, command_line=command_line,
                          working_dir=working_dir, start_error=reason)))
            return

        self._process.setProgram(program)
        self._process.setArguments([str(item) for item in argv])
        self._process.setWorkingDirectory(working_dir or os.path.expanduser("~"))
        self._process.setProcessEnvironment(QProcessEnvironment.systemEnvironment())

        self._set_state(State.RUNNING)
        self._process.start()
        # Nothing is ever written to the child's stdin. Closing the channel right away
        # makes seqkit see end-of-input; leaving it open would block a command that was
        # started without input files until the user pressed Stop.
        self._process.closeWriteChannel()
        self._timer.start()
        self.started.emit()

    def stop(self) -> None:
        if not self._state.busy:
            return
        self._cancelled = True
        if self._state is State.RUNNING:
            self._set_state(State.STOPPING)
            self._process.terminate()
            QTimer.singleShot(4000, self._force_kill)

    def _force_kill(self) -> None:
        if self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.kill()

    def _tick(self) -> None:
        self.tick.emit(time.monotonic() - self._started)

    # -- process callbacks --------------------------------------------------
    def _on_stdout(self) -> None:
        data = bytes(self._process.readAllStandardOutput())
        if data:
            self._bytes += len(data)
            if self._sink:
                self._sink.write(data)
            self._feed_stdout(_strip_ansi(self._decoder_out.decode(data)))

    def _on_stderr(self) -> None:
        data = bytes(self._process.readAllStandardError())
        if data:
            text = _strip_ansi(self._decoder_err.decode(data))
            if text:
                self.stderr_chunk.emit(text)

    def _feed_stdout(self, text: str) -> None:
        if not text:
            return
        if self._previewed >= self._limit:
            self._dropped += max(1, text.count("\n"))
            return
        lines = text.splitlines(keepends=True)
        room = self._limit - self._previewed
        if len(lines) > room:
            self._dropped += len(lines) - room
            text = "".join(lines[:room])
            self._previewed = self._limit
        else:
            self._previewed += len(lines)
        self.stdout_chunk.emit(text)

    def _on_error(self, error: QProcess.ProcessError) -> None:
        if error is not QProcess.ProcessError.FailedToStart:
            return
        # A child that never came up is never heard from again: Qt says so through
        # ``errorOccurred`` and holds back ``finished``. The text is composed here and
        # only then handed to a zero timer, so the run is closed out once ``start()``
        # has returned and its timer armed -- and never from inside the signal that
        # describes a process which does not exist.
        reason = _ERROR_TEXT.get(error, "FailedToStart")
        self._start_error = reason
        QTimer.singleShot(0, lambda: self._close_out_unstarted_run(reason))

    def _close_out_unstarted_run(self, reason: str) -> None:
        """Let go of everything a launch that never started is still holding."""
        if self._reported:
            # ``finished`` reached this launch after all and reported it; a second
            # callback for one run would unlock the form a second time.
            return
        self._timer.stop()
        if self._sink:
            self._sink.close()
            self._sink = None
        self._report(RunResult(
            exit_code=-1,
            cancelled=self._cancelled,
            elapsed=time.monotonic() - self._started,
            stdout_bytes=self._bytes,
            dropped_lines=self._dropped,
            command_line=self._command_line,
            working_dir=self._working_dir,
            stdout_file=self._stdout_path,
            start_error=reason,
        ))

    def _on_finished(self, exit_code: int, status: QProcess.ExitStatus) -> None:
        self._timer.stop()
        if self._reported:
            # Already reported, and the sink already released.
            return

        tail_out = bytes(self._process.readAllStandardOutput())
        if tail_out:
            self._bytes += len(tail_out)
            if self._sink:
                self._sink.write(tail_out)
            self._feed_stdout(_strip_ansi(self._decoder_out.decode(tail_out)))
        tail_err = bytes(self._process.readAllStandardError())
        if tail_err:
            text = _strip_ansi(self._decoder_err.decode(tail_err))
            if text:
                self.stderr_chunk.emit(text)
        flush_out = self._decoder_out.decode(b"", final=True)
        if flush_out:
            self._feed_stdout(_strip_ansi(flush_out))
        flush_err = self._decoder_err.decode(b"", final=True)
        if flush_err:
            self.stderr_chunk.emit(_strip_ansi(flush_err))

        if self._sink:
            self._sink.close()
            self._sink = None

        result = RunResult(
            exit_code=exit_code,
            crashed=status is QProcess.ExitStatus.CrashExit,
            cancelled=self._cancelled,
            elapsed=time.monotonic() - self._started,
            stdout_bytes=self._bytes,
            dropped_lines=self._dropped,
            command_line=self._command_line,
            working_dir=self._working_dir,
            stdout_file=self._stdout_path,
            start_error=self._start_error,
        )
        self._report(result)

    def _report(self, result: RunResult) -> None:
        """Hand one run's outcome to the window, once and only once."""
        if self._reported:
            return
        self._reported = True
        self._set_state(State.IDLE)
        self.finished.emit(result)

    def _set_state(self, state: State) -> None:
        self._state = state
        self.state_changed.emit(state)


def _preflight(program: str, argv: object, working_dir: str) -> str:
    """Why this launch must not happen, or ``""`` when it may.

    The child is started from an argument list, never from a command string, so the
    checks here are about the shape of that list: an absolute program path -- a bare
    name would be resolved by the operating system's search order, which starts with
    the current directory on Windows -- and arguments that are plain strings.
    """
    if not str(program or "").strip():
        return "no seqkit executable is configured"
    if not os.path.isabs(str(program)):
        return "the seqkit path must be absolute"
    if not os.path.isfile(str(program)):
        return f"{program} is not a file"
    if not isinstance(argv, (list, tuple)):
        return "the arguments must be a list"
    for item in argv:
        if not isinstance(item, str):
            return "every argument must be a string"
        if "\x00" in item:
            return "an argument contains a NUL character"
    if working_dir and not os.path.isdir(working_dir):
        return f"the working directory {working_dir} is not a folder"
    return ""


_ANSI_RE = re.compile(r"\[[0-9;:?]*[a-zA-Z]|\][^]*|[()][A-Z0-9]")


def _strip_ansi(text: str) -> str:
    """seqkit colours its log lines; the plain-text views must not show the codes."""
    return _ANSI_RE.sub("", text)


def _new_decoder():
    return codecs.getincrementaldecoder("utf-8")("replace")
