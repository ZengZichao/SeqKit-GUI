"""Paths a Windows user actually has: Chinese, spaces, quotes, dashes and length.

The interface assembles an argument list rather than a shell string, which is what makes
these names survivable at all. Each case here puts the awkward name in front of the real
binary, because the interesting failure is not "did the string survive Python" but "did
the child read it as one file rather than as a flag, a glob or two arguments".

The dash case is the one with a security edge: an input whose name begins with ``-``
would be parsed by seqkit's flag reader as an option, so a file called ``--out-file``
could redirect where the result goes. The terminator in
:func:`seqkit_gui.core.builder.build_argv` is the defence, and it is measured here
against the binary rather than asserted against the list.
"""

import os
import subprocess
import time
from pathlib import Path

import pytest

from seqkit_gui.core import seqkit_locator
from seqkit_gui.core.builder import RunRequest, build_argv, display_command, sanitize
from seqkit_gui.core.runner import SeqkitRunner
from seqkit_gui.core.spec import load
from seqkit_gui.ui import widgets

CJK_FOLDER = "中文目录 测试"
SPACED_NAME = "reads 一号 1.fa"

pytestmark = [pytest.mark.seqkit]


def start_and_wait(runner, program, argv, working_dir, label, timeout=60.0):
    """Arm the ``finished`` connection before launching, then spin the event loop.

    QProcess reports through the application object, so a test that starts a child
    without the ``qapp`` fixture would sit here until the timeout instead of learning
    that nothing was pumping its events.
    """
    from PySide6.QtCore import QCoreApplication

    assert QCoreApplication.instance() is not None, (
        f"{label}: a process test needs the qapp fixture")

    outcome = []
    runner.finished.connect(outcome.append)
    runner.start(program, argv, working_dir, label)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and not outcome:
        QCoreApplication.processEvents()
        time.sleep(0.01)
    QCoreApplication.processEvents()
    if not outcome:
        pytest.fail(f"{label}: seqkit did not finish within {timeout:.0f}s")
    return outcome[0]



@pytest.fixture
def awkward_input(tmp_path) -> Path:
    """``<tmp>/中文目录 测试/reads 一号 1.fa`` with two records in it."""
    folder = tmp_path / CJK_FOLDER
    folder.mkdir()
    path = folder / SPACED_NAME
    path.write_text(">seq1 first\nATGAAAGCAGGGCTGTAA\n>seq2 second\nCCCGGATTACA\n",
                    encoding="utf-8")
    return path


def test_such_a_path_is_one_argument_and_is_quoted_for_display(awkward_input):
    argv = build_argv(RunRequest(command=load().get("stats"), inputs=(str(awkward_input),)))
    assert argv[-1] == str(awkward_input), "the name must not be split or rewritten"
    assert argv[argv.index("--") + 1:] == [str(awkward_input)]
    line = display_command(str(seqkit_locator.locate("").path), argv)
    assert f'"{awkward_input}"' in line or str(awkward_input) in line
    assert argv.count(str(awkward_input)) == 1


def test_the_real_binary_reads_a_chinese_and_spaced_path(qapp, awkward_input,
                                                             seqkit_binary):
    """The name has to work through QProcess, not just through ``str``."""
    runner = SeqkitRunner(2000)
    argv = build_argv(RunRequest(command=load().get("stats"), inputs=(str(awkward_input),)))
    result = start_and_wait(runner, str(seqkit_binary), argv,
                           str(awkward_input.parent), "stats")
    assert result.succeeded, (result, result.start_error)
    text = result.stdout_file.read_text(encoding="utf-8", errors="replace")
    assert SPACED_NAME in text, text[:400]
    assert "2" in text, "the sequence count should be in the table"


def test_a_result_written_into_a_chinese_and_spaced_directory(qapp, awkward_input,
                                                              seqkit_binary, tmp_path):
    target = tmp_path / CJK_FOLDER / "结果 输出.fa"
    command = load().get("seq")
    from seqkit_gui.core.builder import FlagState
    request = RunRequest(command=command, inputs=(str(awkward_input),),
                         flags={"out-file": FlagState(enabled=True, value=str(target))})
    runner = SeqkitRunner(2000)
    result = start_and_wait(runner, str(seqkit_binary), build_argv(request),
                           str(tmp_path), "seq")
    assert result.succeeded, (result, result.start_error)
    assert target.is_file(), f"{target} was not written"
    assert ">seq1" in target.read_text(encoding="utf-8")


def test_a_working_directory_in_chinese_passes_the_preflight(qapp, awkward_input,
                                                                seqkit_binary):
    working = str(awkward_input.parent)
    runner = SeqkitRunner(2000)
    argv = build_argv(RunRequest(command=load().get("seq"), inputs=(str(awkward_input),)))
    result = start_and_wait(runner, str(seqkit_binary), argv, working, "seq")
    assert result.succeeded, result
    assert Path(result.working_dir) == awkward_input.parent


def test_a_file_named_like_a_flag_cannot_become_one(qapp, seqkit_binary, tmp_path):
    """The terminator is what stops a file name being read as ``--out-file``.

    A file literally called ``--out-file`` is written in the working directory -- the
    way a pasted or dragged relative name arrives -- and run twice. Behind ``--``
    seqkit opens it as data. Without the ``--`` the same token reaches pflag as an
    option, which is the injection the builder exists to prevent: it is then a
    ``flag needs an argument`` error at best and a result written to a path the user
    never chose at worst. Both halves are measured against the binary.
    """
    planted = tmp_path / "--out-file"
    planted.write_text(">planted\nATGAAAGCAGGGCTGTAA\n", encoding="utf-8")
    command = load().get("seq")
    argv = build_argv(RunRequest(command=command, inputs=(str(planted),)))
    assert "--" in argv and argv[argv.index("--") + 1:] == [str(planted)]

    runner = SeqkitRunner(2000)
    result = start_and_wait(runner, str(seqkit_binary), argv, str(tmp_path), "seq")
    assert result.succeeded, (result, result.start_error)
    body = result.stdout_file.read_text(encoding="utf-8", errors="replace")
    assert ">planted" in body, body[:300]

    relative = build_argv(RunRequest(command=command, inputs=("--out-file",)))
    guarded = subprocess.run([str(seqkit_binary), *relative], capture_output=True,
                             cwd=str(tmp_path), stdin=subprocess.DEVNULL, timeout=60)
    assert guarded.returncode == 0, guarded.stderr[:300]
    assert b">planted" in guarded.stdout

    naked = [token for token in relative if token != "--"]
    assert naked == ["seq", "--out-file"], naked
    injected = subprocess.run([str(seqkit_binary), *naked], capture_output=True,
                              cwd=str(tmp_path), stdin=subprocess.DEVNULL, timeout=60)
    complaint = injected.stderr.decode("utf-8", "replace")
    assert injected.returncode != 0, (
        f"without the terminator the name was still read as a file: {guarded.stdout[:80]}")
    assert "flag needs an argument" in complaint, complaint[:200]



def test_a_field_entry_beginning_with_a_dash_is_made_absolute(qapp, root):
    """Typing ``-reads.fa`` is a relative path, not a flag."""
    from seqkit_gui.ui.i18n import Catalog

    field = widgets.FileListField(Catalog("en_US", directory=root / "seqkit_gui" / "i18n"))
    try:
        field.add(["-relative.fa"])
        files = field.files()
        assert len(files) == 1
        assert os.path.isabs(files[0]), files
        assert not files[0].startswith("-")
        assert field.repaired == (files[0],)
        assert field.notice.text()
    finally:
        field.deleteLater()


def test_pasted_paths_lose_quotes_and_control_characters(qapp, root):
    from seqkit_gui.ui.i18n import Catalog

    field = widgets.FileListField(Catalog("en_US", directory=root / "seqkit_gui" / "i18n"))
    try:
        field.add(['"C:/data/one fa.fa"', "C:/data/tw\x00o.fa", "   ", "x" * 5000])
        files = field.files()
        assert '"' not in "".join(files)
        assert "\x00" not in "".join(files)
        assert "C:/data/one fa.fa" in files
        assert len(files) == 2, f"blank and oversized entries were kept: {files}"
    finally:
        field.deleteLater()


def test_the_input_list_is_capped_and_says_so(qapp, root):
    """A paste of a hundred thousand paths would otherwise freeze the widget."""
    from seqkit_gui.ui.i18n import Catalog

    field = widgets.FileListField(Catalog("en_US", directory=root / "seqkit_gui" / "i18n"))
    try:
        first = [f"C:/data/a{i}.fa" for i in range(widgets.MAX_INPUT_FILES)]
        extra = [f"C:/data/b{i}.fa" for i in range(5)]
        field.add(first)
        field.add(extra)
        assert field.list.count() == widgets.MAX_INPUT_FILES
        assert len(field.refused) == 5, field.refused
        assert str(widgets.MAX_INPUT_FILES) in field.notice.text()
    finally:
        field.deleteLater()


def test_an_over_long_path_is_reported_rather_than_failing_quietly(qapp, root):
    """>259 characters needs long-path support turned on in Windows; say so up front."""
    from seqkit_gui.ui.i18n import Catalog

    field = widgets.FileListField(Catalog("en_US", directory=root / "seqkit_gui" / "i18n"))
    long_path = "C:/" + "/".join(f"directory{index}" for index in range(30)) + "/x.fa"
    assert len(long_path) > widgets.LONG_PATH_WARNING, len(long_path)
    try:
        field.add([long_path])
        assert field.files() == (long_path,), "the path was dropped instead of flagged"
        assert str(widgets.LONG_PATH_WARNING) in field.notice.text()
    finally:
        field.deleteLater()


def test_duplicated_entries_are_not_added_twice(qapp, root):
    from seqkit_gui.ui.i18n import Catalog

    field = widgets.FileListField(Catalog("en_US", directory=root / "seqkit_gui" / "i18n"))
    try:
        field.add(["C:/data/same.fa", "C:/data/same.fa"])
        assert field.files() == ("C:/data/same.fa",)
    finally:
        field.deleteLater()


def test_sanitize_keeps_argv_free_of_the_bytes_a_process_cannot_carry():
    """A NUL ends an argument at the Win32 boundary; the others corrupt it silently.

    A tab is not one of them: it is a legal character in a Windows file name, and a
    file name nobody could otherwise open.
    """
    assert sanitize("a\x00b") == "ab"
    assert sanitize("a\x07b\x1fb") == "abb"
    assert sanitize("ok\tvalue") == "ok\tvalue"
    argv = build_argv(RunRequest(command=load().get("seq"),
                                 inputs=["C:/x/a\x00b.fa"]))
    assert all("\x00" not in token for token in argv), argv
