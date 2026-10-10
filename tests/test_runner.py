"""End-to-end runs against the real seqkit executable.

Two groups live here. The first runs genuine commands and reads back what the process
layer reported. The second puts damaged, foreign and missing executables in front of it,
because a shell around a child process is only as good as what it does when the child
cannot be started: it has to answer with a result and an idle state, never with a panel
that stays on "running".
"""

import time

import pytest
from PySide6.QtCore import QCoreApplication, QEventLoop, QProcess, QTimer

from seqkit_gui.core import seqkit_locator
from seqkit_gui.core.builder import RunRequest, build_argv
from seqkit_gui.core.runner import SeqkitRunner


def wait_until_finished(runner: SeqkitRunner, timeout: int = 60000):
    loop = QEventLoop()
    outcome = {}

    def on_finished(result):
        outcome["result"] = result
        loop.quit()

    runner.finished.connect(on_finished)
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(timeout)
    loop.exec()
    timer.stop()
    runner.finished.disconnect(on_finished)
    if "result" not in outcome:
        pytest.fail("seqkit did not finish within the timeout")
    return outcome["result"]


def settle(runner: SeqkitRunner, timeout: int = 10000):
    """Give the runner its budget and report what came back, or ``None``.

    Used where the question is whether a result arrives at all. A launch that reports
    nothing leaves its tee file open behind it, so the file is closed and dropped here
    either way; a suite that wedged a child would otherwise accumulate temp files.
    """
    loop = QEventLoop()
    outcome = {}

    def on_finished(result):
        outcome["result"] = result
        loop.quit()

    runner.finished.connect(on_finished)
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(timeout)
    loop.exec()
    timer.stop()
    runner.finished.disconnect(on_finished)

    path = runner.stdout_file
    sink = getattr(runner, "_sink", None)
    if sink is not None:
        try:
            sink.close()
        except OSError:
            pass
        runner._sink = None
    if path is not None and path.is_file():
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
    return outcome.get("result")



def test_probe_version_reports_the_supported_release(seqkit_binary):
    text = seqkit_locator.probe_version(seqkit_binary)
    assert "seqkit" in text.lower()
    assert "2.14.0" in text


def test_stats_run_produces_tabular_output(qapp, seqkit_binary, sample_fasta):
    from seqkit_gui.core.spec import load
    command = load().get("stats")
    request = RunRequest(command=command, inputs=(str(sample_fasta),))
    runner = SeqkitRunner(2000)
    runner.start(str(seqkit_binary), build_argv(request), str(sample_fasta.parent), "stats")
    result = wait_until_finished(runner)

    assert result.succeeded, result
    text = result.stdout_file.read_text(encoding="utf-8", errors="replace")
    assert "file" in text and "short1.fa" in text
    assert "4" in text


def test_grep_run_filters_records(qapp, seqkit_binary, sample_fasta):
    from seqkit_gui.core.spec import load
    command = load().get("grep")
    request = RunRequest(command=command, inputs=(str(sample_fasta),),
                         flags={"pattern": _state(command, "pattern", "seq1")})
    runner = SeqkitRunner(2000)
    runner.start(str(seqkit_binary), build_argv(request), str(sample_fasta.parent), "grep")
    result = wait_until_finished(runner)

    assert result.succeeded, result
    text = result.stdout_file.read_text(encoding="utf-8", errors="replace")
    assert text.count(">seq1") == 1
    assert ">seq2" not in text


def test_output_file_flag_writes_a_real_file(qapp, seqkit_binary, sample_fasta, tmp_path):
    from seqkit_gui.core.spec import load
    command = load().get("seq")
    target = tmp_path / "lower.fa"
    request = RunRequest(
        command=command,
        inputs=(str(sample_fasta),),
        flags={
            "lower-case": _state(command, "lower-case", None, enabled=True),
            "out-file": _state(command, "out-file", str(target)),
        },
    )
    runner = SeqkitRunner(2000)
    runner.start(str(seqkit_binary), build_argv(request), str(tmp_path), "seq")
    result = wait_until_finished(runner)

    assert result.succeeded, result
    assert target.is_file()
    body = target.read_text(encoding="utf-8")
    assert "atgaaagcagggctgtaa" in body


def test_stderr_is_captured_when_seqkit_complains(qapp, seqkit_binary, sample_fasta):
    from seqkit_gui.core.spec import load
    command = load().get("grep")
    request = RunRequest(command=command, inputs=(str(sample_fasta),))
    runner = SeqkitRunner(2000)
    chunks = []
    runner.stderr_chunk.connect(chunks.append)
    runner.start(str(seqkit_binary), build_argv(request), str(sample_fasta.parent), "grep")
    result = wait_until_finished(runner)

    assert not result.succeeded
    assert any("pattern" in chunk.lower() for chunk in chunks), chunks


def test_run_without_input_terminates_instead_of_waiting(qapp, seqkit_binary, tmp_path):
    """An empty file list must not leave seqkit blocked on a stdin nobody writes to."""
    from seqkit_gui.core.spec import load
    command = load().get("stats")
    request = RunRequest(command=command, inputs=())
    runner = SeqkitRunner(2000)
    runner.start(str(seqkit_binary), build_argv(request), str(tmp_path), "stats")
    result = wait_until_finished(runner, timeout=20000)
    assert not runner.state.busy
    assert result.elapsed < 15, f"the child waited for input: {result.elapsed:.1f}s"


def test_cancel_stops_a_long_run(qapp, seqkit_binary, sample_fasta):
    from seqkit_gui.core.spec import load
    command = load().get("watch")
    request = RunRequest(command=command, inputs=(str(sample_fasta),),
                         flags={"print-freq": _state(command, "print-freq", 1)})
    runner = SeqkitRunner(2000)
    runner.start(str(seqkit_binary), build_argv(request), str(sample_fasta.parent), "watch")
    loop = QEventLoop()
    QTimer.singleShot(1500, loop.quit)
    loop.exec()
    runner.stop()
    result = wait_until_finished(runner)
    assert result.cancelled or not result.succeeded


def test_cancel_terminates_a_run_without_leaving_an_orphan(qapp, seqkit_binary,
                                                           sample_fasta, process_probe):
    """Stop has to end the child, not merely stop listening to it.

    Measured cost: ``QProcess.terminate()`` asks a GUI application to close, and seqkit
    is a console program with no window to close, so the runner's own force-kill timer
    is what actually ends it. The wait below is the budget that fallback needs.
    """
    from seqkit_gui.core.spec import load
    command = load().get("watch")
    request = RunRequest(command=command, inputs=(str(sample_fasta),),
                         flags={"print-freq": _state(command, "print-freq", 1)})
    runner = SeqkitRunner(2000)
    runner.start(str(seqkit_binary), build_argv(request), str(sample_fasta.parent), "watch")
    loop = QEventLoop()
    QTimer.singleShot(1200, loop.quit)
    loop.exec()
    pid = int(runner._process.processId())
    assert pid, "the reference child never reported a pid"
    assert process_probe.alive(pid)

    runner.stop()
    result = wait_until_finished(runner)
    assert result.cancelled, result
    assert not result.succeeded
    assert not runner.state.busy
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline and process_probe.alive(pid):
        QCoreApplication.processEvents()
        time.sleep(0.05)
    assert not process_probe.alive(pid), f"seqkit pid {pid} survived Stop"

    runner.stop()
    assert not runner.state.busy, "a second Stop must not resurrect anything"


def test_every_run_reports_its_result_file(qapp, seqkit_binary, sample_fasta):
    """Whatever happens, the tee-ed file has to be reachable for the panel to show."""
    from seqkit_gui.core.spec import load
    request = RunRequest(command=load().get("stats"), inputs=(str(sample_fasta),))
    runner = SeqkitRunner(2000)
    runner.start(str(seqkit_binary), build_argv(request), str(sample_fasta.parent), "stats")
    result = wait_until_finished(runner)
    assert result.stdout_file is not None and result.stdout_file.is_file()
    assert result.command_line == "stats"
    assert result.elapsed > 0


# ------------------------------------------------------- damaged or unsuitable binaries
DAMAGED = pytest.mark.parametrize(
    "kind", ["plain text", "zero bytes", "truncated download"])


def damaged_path(fake_binary, kind):
    if kind == "plain text":
        return fake_binary.text()
    if kind == "zero bytes":
        return fake_binary.zero_bytes()
    if kind == "truncated download":
        return fake_binary.truncated()
    raise AssertionError(kind)


@DAMAGED
def test_an_unstartable_binary_still_reports_a_result(qapp, fake_binary, kind):
    """A child that never came up must still end the run, one way or the other.

    Every one of these files is a real path that passes the pre-flight checks, and none
    of them can be executed: the Windows loader answers
    ``FailedToStart`` / "not a valid Win32 application". QProcess emits ``errorOccurred``
    and no ``finished`` for that, so the runner closes the launch out on its own --
    :class:`SeqkitRunner` is the only thing between the child and the window, and the
    window unlocks the form and closes the panel from its ``finished`` signal alone.

    The contract asserted here is the one the interface needs: a result arrives inside
    the budget, the runner is no longer busy, and the result says the start failed. That
    is what keeps a user whose ``bin/seqkit.exe`` is damaged from sitting on "Running"
    with a locked form, a Stop button that does nothing and no option but to restart the
    application.
    """
    path = damaged_path(fake_binary, kind)
    if path is None:
        pytest.skip(f"no reference binary to build a {kind}")
    runner = SeqkitRunner(2000)
    runner.start(str(path), ["version"], str(path.parent), kind)

    result = settle(runner, timeout=6000)
    assert result is not None, (
        f"{kind}: the runner never reported anything, so the window stays unlocked by "
        f"nothing and the form stays locked forever")
    assert not runner.state.busy, f"{kind}: still busy after reporting a result"
    assert not result.succeeded, result
    assert result.start_error, f"{kind}: the failure was not described: {result}"


def test_a_folder_cannot_be_run_and_says_why(qapp, fake_binary):
    """A directory is caught before the process is touched, so it reports at once."""
    path = fake_binary.directory()
    runner = SeqkitRunner(2000)
    runner.start(str(path), ["version"], str(path.parent), "folder")
    result = wait_until_finished(runner, timeout=20000)
    assert not result.succeeded
    assert "not a file" in result.start_error, result.start_error
    assert not runner.state.busy


def test_a_foreign_native_program_is_run_and_fails_on_its_own_merit(qapp, fake_binary,
                                                                    sample_fasta):
    """A real PE that is not seqkit does start; the error has to come back as output.

    The magic-number gate cannot tell seqkit from ``where.exe``, so this is the case
    where the process layer is the only thing reporting anything. It must not raise, and
    it must not leave the runner busy.
    """
    other = fake_binary.native_other()
    if other is None:
        pytest.skip("no foreign native executable available to copy")
    runner = SeqkitRunner(2000)
    runner.start(str(other), ["stats", "--", str(sample_fasta)], str(sample_fasta.parent),
                 "not-seqkit")
    result = wait_until_finished(runner, timeout=30000)
    assert not runner.state.busy
    assert not result.succeeded, f"a non-seqkit binary appeared to work: {result}"


# ------------------------------------------------------------------ pre-flight refusals
def test_a_program_path_that_is_not_absolute_is_refused(qapp):
    """A bare name would be resolved by the operating system's search order."""
    runner = SeqkitRunner(2000)
    outcome = []
    runner.finished.connect(outcome.append)
    runner.start("seqkit", ["version"])
    QCoreApplication.processEvents()
    assert outcome, "a refused launch must still report through finished"
    assert "absolute" in outcome[0].start_error, outcome[0].start_error
    assert not runner.state.busy


def test_a_missing_program_path_is_refused(qapp, fake_binary):
    runner = SeqkitRunner(2000)
    outcome = []
    runner.finished.connect(outcome.append)
    runner.start(str(fake_binary.missing()), ["version"])
    QCoreApplication.processEvents()
    assert outcome, "a refused launch must still report through finished"
    assert "not a file" in outcome[0].start_error, outcome[0].start_error


def test_a_relative_path_never_reaches_the_process(qapp, seqkit_binary):
    runner = SeqkitRunner(2000)
    outcome = []
    runner.finished.connect(outcome.append)
    runner.start("bin/seqkit.exe", ["version"])
    QCoreApplication.processEvents()
    assert outcome and "absolute" in outcome[0].start_error, outcome


def test_a_working_directory_that_is_not_a_folder_is_refused(qapp, seqkit_binary, tmp_path):
    runner = SeqkitRunner(2000)
    outcome = []
    runner.finished.connect(outcome.append)
    runner.start(str(seqkit_binary), ["version"], str(tmp_path / "absent"))
    QCoreApplication.processEvents()
    assert outcome and "not a folder" in outcome[0].start_error, outcome


def test_arguments_must_be_strings_and_free_of_nul(qapp, seqkit_binary):
    runner = SeqkitRunner(2000)
    outcome = []
    runner.finished.connect(outcome.append)
    runner.start(str(seqkit_binary), ["stats", 7])
    QCoreApplication.processEvents()
    assert outcome and "string" in outcome[0].start_error, outcome

    runner.start(str(seqkit_binary), ["stats", "--", "a\x00b.fa"])
    QCoreApplication.processEvents()
    assert len(outcome) == 2 and "NUL" in outcome[1].start_error, outcome


def test_no_program_at_all_is_refused(qapp):
    runner = SeqkitRunner(2000)
    outcome = []
    runner.finished.connect(outcome.append)
    runner.start("", ["version"])
    QCoreApplication.processEvents()
    assert outcome and "no seqkit executable" in outcome[0].start_error, outcome


def test_a_refused_launch_starts_no_process(qapp, fake_binary):
    """A refusal is a refusal: no child, no pid, nothing left in the Starting state."""
    runner = SeqkitRunner(2000)
    outcome = []
    runner.finished.connect(outcome.append)
    runner.start(str(fake_binary.missing()), ["version"])
    QCoreApplication.processEvents()
    assert outcome, "the refusal was not reported"
    assert runner._process.processId() == 0, "a refused launch still had a pid"
    assert runner._process.state() == QProcess.ProcessState.NotRunning



def _state(command, name, value, enabled=True):
    from seqkit_gui.core.builder import FlagState
    flag = command.flag(name)
    assert flag is not None, name
    if flag.is_bool:
        return FlagState(enabled=enabled, value="true" if value is None else str(value))
    return FlagState(enabled=enabled, value="" if value is None else str(value))
