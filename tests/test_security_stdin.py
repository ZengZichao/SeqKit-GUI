"""No child the GUI starts may wait forever for something that never arrives.

Two independent mechanisms, tested separately because they cover different bugs:

* the write channel of the child is closed the moment it starts, so a command
  launched without input files reads end-of-input and fails at once. Measured with
  the shipped binary and no file arguments: an stdin pipe the parent keeps open
  leaves ``seqkit seq`` blocked (still alive when killed at 6 s); the same child with
  its write channel closed exits 0 in 0.4 s having read nothing; with stdin at
  ``NUL`` it exits non-zero with ``fastx: stdin not detected``. Only the first case
  is a stuck interface, which is what the closed channel prevents.
* :func:`validate` refuses to assemble a run that seqkit would keep alive no matter
  what stdin does. ``scat`` is that case: it installs a filesystem watcher on the
  directories it is given and loops (SeqKit 2.14.0 ``scat.go:109-125`` feeding the
  ``MAIN:`` loop at ``scat.go:176-260``). Measured: ``scat -- <dir>`` was still alive
  when killed at 8 s, with stdin at end-of-file as well as left open, while
  ``scat -f -- <dir>`` exited 0 in 4 s. Closing stdin cannot fix that, and using it
  to paper over a parameter table would hide the real problem, so the run is refused
  before the child starts.

The last group pins the pre-launch gates in :func:`seqkit_gui.core.runner._preflight`
-- they decide what may reach ``CreateProcess`` at all, and they answer without ever
starting a process.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QEventLoop, QProcess, QTimer

from seqkit_gui.core.builder import FlagState, RunRequest, build_argv, validate
from seqkit_gui.core.runner import SeqkitRunner
from seqkit_gui.core.spec import load

FASTQ = "@read1\nACGT\n+\nIIII\n"


def run_to_end(runner: SeqkitRunner, timeout_ms: int = 30_000):
    """Drive the event loop until the child reports finished, or give up."""
    loop = QEventLoop()
    outcome: dict = {}

    def on_finished(result):
        outcome["result"] = result
        loop.quit()

    runner.finished.connect(on_finished)
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(timeout_ms)
    loop.exec()
    timer.stop()
    runner.finished.disconnect(on_finished)
    if "result" not in outcome:
        runner.stop()
        pytest.fail("the child never reported finished within the timeout")
    return outcome["result"]


def enable(value=None):
    return FlagState(enabled=True, value="true" if value is None else str(value))


@pytest.fixture
def watched_dir(tmp_path):
    folder = tmp_path / "reads"
    folder.mkdir()
    (folder / "batch.fq").write_text(FASTQ, encoding="utf-8")
    return folder


# ------------------------------------------------------------- unbounded runs --
def test_scat_without_an_exit_condition_is_refused():
    """The GUI must not start a watcher it has given seqkit no reason to leave."""
    command = load().get("scat")
    problems = validate(RunRequest(command=command, inputs=("C:/data/reads",)))
    assert not problems.ok
    assert problems.problem_flags == {"find-only", "time-limit"}
    text = " ".join(problems.messages(lambda key, **fmt: key.format(**fmt) if fmt else key))
    assert "--find-only" in text and "--time-limit" in text


def test_wait_pid_alone_does_not_count_as_an_exit_condition():
    """``--wait-pid`` defaults to -1, which switches the PID timer off entirely."""
    command = load().get("scat")
    request = RunRequest(command=command, inputs=("C:/data/reads",),
                         flags={"wait-pid": enable("-1")})
    assert not validate(request).ok


def test_an_enabled_flag_without_a_value_is_not_an_exit_condition():
    """A ticked ``--time-limit`` with nothing in it emits no argument at all."""
    command = load().get("scat")
    request = RunRequest(command=command, inputs=("C:/data/reads",),
                         flags={"time-limit": enable("")})
    assert not validate(request).ok


def test_scat_with_an_exit_condition_is_accepted():
    command = load().get("scat")
    for name, value in (("find-only", None), ("time-limit", "30s")):
        request = RunRequest(command=command, inputs=("C:/data/reads",),
                             flags={name: enable(value)})
        assert validate(request).ok, name
        argv = build_argv(request)
        assert f"--{name}" in argv, argv
        assert argv[argv.index("--") + 1:] == ["C:/data/reads"], argv


def test_the_rule_is_scoped_to_the_one_command_that_watches():
    """No other subcommand is told to find an exit condition."""
    for command in load().usable:
        problems = validate(RunRequest(command=command, inputs=("C:/data/x.fa",)))
        demanded = set(problems.missing_all)
        for group in problems.missing_any:
            demanded.update(group)
        if command.key == "scat":
            assert demanded == {"find-only", "time-limit"}, command.key
        else:
            assert not demanded & {"find-only", "time-limit"}, command.key


@pytest.mark.seqkit
def test_a_bounded_scat_run_finishes(qapp, seqkit_binary, watched_dir, tmp_path):
    """The accepted spelling really does terminate, watcher included."""
    command = load().get("scat")
    request = RunRequest(command=command, inputs=(str(watched_dir),),
                         flags={"find-only": enable()})
    runner = SeqkitRunner(2000)
    runner.start(str(seqkit_binary), build_argv(request), str(tmp_path), "scat")
    result = run_to_end(runner, timeout_ms=60_000)

    assert result.succeeded, result
    assert result.elapsed < 45, f"the watcher outlasted its exit condition: {result.elapsed:.1f}s"
    assert "read1" in result.stdout_file.read_text(encoding="utf-8", errors="replace")


# ------------------------------------------------------------------- stdin ------
@pytest.mark.seqkit
def test_a_child_without_input_reads_end_of_file_instead_of_waiting(
        qapp, seqkit_binary, tmp_path):
    """seqkit with no file arguments reads stdin, and nothing here will ever write it."""
    command = load().get("seq")
    runner = SeqkitRunner(2000)
    runner.start(str(seqkit_binary), build_argv(RunRequest(command=command)),
                 str(tmp_path), "seq")
    result = run_to_end(runner)

    assert result.elapsed < 20, f"the child waited for input: {result.elapsed:.1f}s"
    assert result.stdout_bytes == 0, "an empty stdin must not produce a record"
    assert runner.state.busy is False
    assert runner._process.state() is QProcess.ProcessState.NotRunning


def test_qprocess_gets_the_list_without_any_reparsing(qapp):
    """``setArguments`` takes a list; the single-string overload would split it again."""
    argv = ["stats", "--", 'C:/tmp/my dir/"quoted".fa', "C:/tmp/a&b.fa"]
    process = QProcess()
    process.setProgram("seqkit")
    process.setArguments(argv)
    assert process.arguments() == argv


# ------------------------------------------------------------ launch gates -----
def test_a_relative_program_is_refused(qapp, tmp_path):
    """A bare name would be resolved by the OS, whose search starts in the cwd."""
    runner = SeqkitRunner(2000)
    runner.start("seqkit", build_argv(RunRequest(command=load().get("version"))),
                 str(tmp_path), "seqkit version")
    result = run_to_end(runner, timeout_ms=10_000)

    assert result.exit_code == -1
    assert "absolute" in result.start_error, result.start_error
    assert not runner.state.busy
    assert runner._process.state() is QProcess.ProcessState.NotRunning


def test_a_missing_program_is_refused(qapp, tmp_path):
    runner = SeqkitRunner(2000)
    runner.start(str(tmp_path / "nope" / "seqkit.exe"),
                 build_argv(RunRequest(command=load().get("version"))), str(tmp_path), "")
    result = run_to_end(runner, timeout_ms=10_000)
    assert "not a file" in result.start_error


def test_arguments_that_are_not_plain_strings_are_refused(qapp, seqkit_binary, tmp_path):
    runner = SeqkitRunner(2000)
    runner.start(str(seqkit_binary), ["stats", 42], str(tmp_path), "")
    assert "must be a string" in run_to_end(runner, 10_000).start_error

    runner.start(str(seqkit_binary), ["stats", "--", "a\x00b.fa"], str(tmp_path), "")
    assert "NUL" in run_to_end(runner, 10_000).start_error

    runner.start(str(seqkit_binary), "stats -- a.fa", str(tmp_path), "")
    assert run_to_end(runner, 10_000).start_error == "the arguments must be a list"


def test_a_working_directory_that_is_not_a_folder_is_refused(qapp, seqkit_binary, tmp_path):
    runner = SeqkitRunner(2000)
    runner.start(str(seqkit_binary), build_argv(RunRequest(command=load().get("version"))),
                 str(tmp_path / "not-created"), "")
    assert "not a folder" in run_to_end(runner, 10_000).start_error
