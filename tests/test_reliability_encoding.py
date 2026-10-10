"""Byte-level robustness of the two channels the child process writes into.

``seqkit`` is a Go program: it copies sequence bytes through unchanged, so a FASTQ
quality line or a description can carry bytes that are not valid UTF-8, and a terminal
program run through the same process layer can emit ANSI colours. The decode path is
one incremental UTF-8 decoder per channel with the ``replace`` handler, which means
three things this file pins down: nothing may crash, nothing may be lost from the
saved result (bytes are tee-d before they are decoded), and a character whose bytes
straddle two reads must still arrive as one character.

Where a test needs a byte stream of its own rather than whatever seqkit happens to
emit, it runs the current interpreter as the child. The process layer takes any
absolute executable path, and that keeps the emitted bytes exact instead of leaving
them to whatever a third-party binary decides to print.
"""

import subprocess
import sys
import time
from pathlib import Path

import pytest

from seqkit_gui.core.builder import RunRequest, build_argv
from seqkit_gui.core.runner import SeqkitRunner
from seqkit_gui.core.spec import load

REPLACEMENT = "\ufffd"

#: The bytes seqkit itself keeps verbatim in a FASTA description (measured against the
#: shipped binary: ``seq`` returned the same ``\xff\xfe\x80`` it was given).
NON_UTF8 = b"\xff\xfe\x80"


def emit(child_code: str, preview_limit: int = 2000) -> tuple:
    """Run ``python -c child_code`` through the process layer; return (result, texts)."""
    runner = SeqkitRunner(preview_limit)
    out, err = [], []
    runner.stdout_chunk.connect(out.append)
    runner.stderr_chunk.connect(err.append)

    from PySide6.QtCore import QCoreApplication

    outcome = []
    runner.finished.connect(outcome.append)
    runner.start(sys.executable, ["-X", "utf8", "-c", child_code], str(Path.cwd()), "child")
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline and not outcome:
        QCoreApplication.processEvents()
        time.sleep(0.01)
    QCoreApplication.processEvents()
    assert outcome, "the child did not finish"
    return outcome[0], "".join(out), "".join(err)


def test_invalid_utf8_on_stdout_is_replaced_and_never_fails(qapp):
    """A lone invalid byte must not be able to break the reader."""
    result, text, _err = emit("import sys; sys.stdout.buffer.write("
                              f"{NON_UTF8!r} + b'read1\\n'); sys.stdout.flush()")
    assert result.succeeded, result
    assert REPLACEMENT in text, repr(text)
    assert "read1" in text
    # The saved result is byte-for-byte what the child wrote: decoding only feeds the
    # preview, it never replaces the file a user is told to open.
    assert result.stdout_file.read_bytes().startswith(NON_UTF8)


def test_invalid_utf8_on_stderr_is_replaced_too(qapp):
    """The second channel has its own decoder, and it gets the same treatment.

    Writing to stderr is not a failure in itself, so the exit code stays the child's
    own; what is asserted is that the bytes arrive as text and that the bad byte does
    not take the reader down with it.
    """
    result, _out, err = emit("import sys; sys.stderr.buffer.write("
                             f"{NON_UTF8!r} + b'bad quality\\n'); sys.stderr.flush()")
    assert result.succeeded, "a child that only wrote to stderr still exited 0"
    assert REPLACEMENT in err and "bad quality" in err


def test_a_character_split_across_reads_arrives_whole(qapp):
    """The decoder is incremental: ``e4`` / ``b8`` / ``ad`` is one 中, not three errors.

    This is the failure mode a fixed-size pipe read produces at every chunk boundary,
    and the reason the decoder is kept on the runner instead of decoding each read on
    its own.
    """
    script = ("import sys, time\n"
              "w = sys.stdout.buffer.write\n"
              "w(b'\\xe4'); sys.stdout.flush(); time.sleep(0.3)\n"
              "w(b'\\xb8'); sys.stdout.flush(); time.sleep(0.3)\n"
              "w(b'\\xad\\n'); sys.stdout.flush()\n")
    result, text, _err = emit(script)
    assert result.succeeded, result
    assert text.strip() == "中", repr(text)
    assert REPLACEMENT not in text


def test_ansi_colour_codes_are_stripped_from_both_channels(qapp):
    """seqkit colours its log lines; the plain-text views must not show the codes."""
    script = ("import sys\n"
              "sys.stdout.buffer.write(b'\\x1b[31mOUT\\x1b[0m\\n'); sys.stdout.flush()\n"
              "sys.stderr.buffer.write(b'\\x1b[1;33mERR\\x1b[0m\\n'); sys.stderr.flush()\n")
    result, out, err = emit(script)
    assert result.succeeded, result
    assert out.strip() == "OUT", repr(out)
    assert err.strip() == "ERR", repr(err)
    for text in (out, err):
        assert "\x1b" not in text and "[31m" not in text


def test_a_nul_and_control_byte_output_does_not_stall_the_reader(qapp):
    """Control bytes in *output* are the child's business; only argv has to be clean."""
    result, text, _err = emit("import sys; sys.stdout.buffer.write("
                              "b'a\\x00b\\x07c\\n'); sys.stdout.flush()")
    assert result.succeeded, result
    assert "a" in text and "c" in text


@pytest.mark.seqkit
def test_a_fastq_with_non_utf8_qualities_round_trips_through_the_real_binary(
        qapp, seqkit_binary, tmp_path):
    """The FASTA/FASTQ pass-through case: raw bytes in, raw bytes out, no crash.

    The saved result is compared against a direct subprocess capture of the same
    command, so "nothing was lost" is checked against the binary's own output rather
    than against a number the test invented.
    """
    fastq = tmp_path / "raw.fastq"
    fastq.write_bytes(b"@read1 " + NON_UTF8 + b"\nATGC\n+\n\x93\x9c\x88\x9e\n")
    argv = build_argv(RunRequest(command=load().get("seq"), inputs=(str(fastq),)))

    direct = subprocess.run([str(seqkit_binary), *argv], capture_output=True,
                            stdin=subprocess.DEVNULL, timeout=60)
    runner = SeqkitRunner(2000)
    preview = []
    runner.stdout_chunk.connect(preview.append)
    outcome = []
    runner.finished.connect(outcome.append)

    from PySide6.QtCore import QCoreApplication

    runner.start(str(seqkit_binary), argv, str(tmp_path), "seq")
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline and not outcome:
        QCoreApplication.processEvents()
        time.sleep(0.01)
    result = outcome[0] if outcome else pytest.fail("the child did not finish")

    assert result.stdout_file.read_bytes() == direct.stdout, (
        "the tee-ed result file differs from what the binary wrote")
    assert NON_UTF8 in result.stdout_file.read_bytes()
    text = "".join(preview)
    assert text, "the preview showed nothing at all"
    assert REPLACEMENT in text or "read1" in text, repr(text)


def test_the_saved_result_is_re_readable_by_the_panel_with_errors_replace(qapp, tmp_path):
    """Whatever the child wrote, the recovery path used to read it back has to survive."""
    path = tmp_path / "result.out"
    path.write_bytes(b"header " + NON_UTF8 + b" tail\n")
    text = path.read_text(encoding="utf-8", errors="replace")
    assert REPLACEMENT in text and text.endswith("tail\n")
