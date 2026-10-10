"""A Windows path must reach seqkit as exactly the argument the user meant.

The interface hands ``QProcess`` a list and never a command string, so no layer
re-parses an argument on the way to the child. Two things do still re-parse, and
both are pinned here: seqkit's own option parser, which reads a name starting with
``-`` as a flag unless the ``--`` terminator comes first; and whatever shell the
user pastes the displayed command line into.

Names are split by whether NTFS can hold them. Windows forbids ``" * / \\ : < > | ?``
in a file name, so a pipe or a double quote can only arrive as typed or pasted text
-- those are asserted against :func:`build_argv` and against the rendered command
line, and never against the filesystem.

Measured against the shipped binary for the record: ``stats -- -rf.fa`` exits 0 with
``-rf.fa`` in the table, while ``stats -rf.fa`` exits non-zero with ``unknown
shorthand flag: 'r' in -rf.fa``; one ``stats`` call over nine awkward paths returns
one table row per path, byte for byte.
"""

from __future__ import annotations

import os
import subprocess

import pytest

from seqkit_gui.core.builder import FlagState, RunRequest, build_argv, display_command, sanitize
from seqkit_gui.core.spec import load

RECORD = ">s1\nACGT\n>s2\nACGTACGT\n"

#: Names NTFS accepts, so the real binary can be asked to read them.
CREATABLE_NAMES = [
    "-rf.fa",                    # reads as a flag without the terminator
    "--out-file.fa",             # a whole option name, as a file
    "my seqs.fa",                # spaces
    "it's.fa",                   # apostrophe
    "a;b.fa",                    # cmd argument separator
    "a&b.fa",                    # cmd command separator
    "%PATH%.fa",                 # cmd expansion, kept verbatim by the child
    "中文 序列.fa",     # non-ASCII plus a space
    "très long 名称 with spaces & (parens).fa",
]

#: Names Windows cannot store; the assertion is that argv and the display string
#: treat them as one opaque argument anyway.
UNSTOREABLE_NAMES = [
    'a"b.fa',
    "a;b|c.fa",
    "tab\tname.fa",
]

SLASH = chr(92)


def unc_path() -> str:
    """A real UNC shape: two leading backslashes, host, share, file."""
    return SLASH * 2 + "no-such-host.example" + SLASH + "share" + SLASH + "seqs.fa"


def stats(inputs, flags=None):
    command = load().get("stats")
    return RunRequest(command=command, inputs=tuple(inputs), flags=flags or {})


@pytest.fixture
def workspace(tmp_path):
    for name in CREATABLE_NAMES:
        (tmp_path / name).write_text(RECORD, encoding="utf-8")
    return tmp_path


# --------------------------------------------------------------------- argv ----
def test_every_awkward_path_is_one_argv_element(workspace):
    """build_argv neither splits nor rewrites any element of the file list."""
    paths = [str(workspace / name) for name in CREATABLE_NAMES + UNSTOREABLE_NAMES]
    paths.append(unc_path())
    argv = build_argv(stats(paths))

    assert argv[0] == "stats"
    assert argv.count("--") == 1, "exactly one terminator, no matter the list length"
    terminator = argv.index("--")
    assert terminator == len(argv) - len(paths) - 1
    assert argv[terminator + 1:] == paths
    assert all(isinstance(item, str) and item for item in argv)


def test_a_single_path_does_not_gain_or_lose_elements(workspace):
    """The count is fixed by the input count, not by what the names contain."""
    for name in CREATABLE_NAMES + UNSTOREABLE_NAMES + [unc_path()]:
        path = str(workspace / name)
        argv = build_argv(stats([path]))
        assert len(argv) == 3, (name, argv)
        assert argv == ["stats", "--", path], name


def test_positional_paths_come_after_the_terminator_and_flags_before(workspace):
    """A flag value with a space stays its own element, ahead of ``--``."""
    path = str(workspace / "my seqs.fa")
    out = str(workspace / "result table.txt")
    argv = build_argv(stats([path], flags={
        "out-file": FlagState(enabled=True, value=out),
        "id-regexp": FlagState(enabled=True, value=r"^(\S+)\s?"),
    }))
    terminator = argv.index("--")
    assert "--out-file" in argv[:terminator]
    assert argv[argv.index("--out-file") + 1] == out
    assert argv[argv.index("--id-regexp") + 1] == r"^(\S+)\s?"
    assert argv[terminator + 1:] == [path]


def test_a_nul_truncates_nothing_and_survives_as_one_argument(workspace):
    """A NUL would end the argument inside the child, silently dropping the tail."""
    pasted = str(workspace / "-rf.fa") + "\x00tail\nmore\x1b[31m"
    tail = build_argv(stats([pasted]))[2:]
    assert len(tail) == 1
    assert "\x00" not in tail[0] and "\x1b" not in tail[0]
    assert "tail" in tail[0], "the text after the NUL must not be swallowed"
    assert tail[0] == sanitize(pasted)


# ------------------------------------------------------------- the real child --
@pytest.mark.seqkit
def test_the_binary_reads_every_creatable_path_once(seqkit_binary, workspace):
    """One launch per spelling, nine awkward names each: separate, uncut arguments.

    Both spellings matter. Absolute paths are what the file dialog and drag & drop
    produce; the relative names are what a typed or pasted list holds, and only the
    relative form lets a leading ``-`` reach seqkit as an option.
    """
    for label, paths in (("absolute", [str(workspace / name) for name in CREATABLE_NAMES]),
                         ("relative", list(CREATABLE_NAMES))):
        argv = build_argv(stats(paths))
        done = subprocess.run([str(seqkit_binary), *argv], capture_output=True,
                              timeout=120, cwd=str(workspace), stdin=subprocess.DEVNULL)

        assert done.returncode == 0, (label, done.stderr.decode("utf-8", "replace"))
        text = done.stdout.decode("utf-8", "replace")
        rows = [line for line in text.splitlines()[1:] if line.strip()]
        assert len(rows) == len(paths), (label, text)
        for name in CREATABLE_NAMES:
            assert name in text, (label, name, text)


@pytest.mark.seqkit
def test_the_terminator_is_load_bearing(seqkit_binary, workspace):
    """Without ``--`` the same argv is parsed as flags: the guard is not decoration."""
    guarded = subprocess.run([str(seqkit_binary), "stats", "--", "-rf.fa"],
                             capture_output=True, timeout=120, cwd=str(workspace),
                             stdin=subprocess.DEVNULL)
    assert guarded.returncode == 0, guarded.stderr.decode("utf-8", "replace")
    assert "-rf.fa" in guarded.stdout.decode("utf-8", "replace")

    unguarded = subprocess.run([str(seqkit_binary), "stats", "-rf.fa"],
                               capture_output=True, timeout=120, cwd=str(workspace),
                               stdin=subprocess.DEVNULL)
    assert unguarded.returncode != 0, unguarded.stdout.decode("utf-8", "replace")
    assert "unknown shorthand flag" in unguarded.stderr.decode("utf-8", "replace")


@pytest.mark.seqkit
def test_an_unreachable_unc_share_is_an_argument_not_a_hang(seqkit_binary):
    """A dead UNC name is reported by seqkit, not sat on in a network timeout."""
    target = unc_path()
    assert build_argv(stats([target]))[2] == target
    done = subprocess.run([str(seqkit_binary), "stats", "--", target],
                          capture_output=True, timeout=30, stdin=subprocess.DEVNULL)
    assert done.returncode != 0


# ------------------------------------------------------------ display string --
#: cmd.exe acts on these while they sit outside double quotes.
CMD_METACHARS = "&|<>^"


def bare_metacharacters(line: str) -> list[str]:
    """The cmd.exe metacharacters that are *not* inside a quoted region."""
    inside = False
    found: list[str] = []
    for index, char in enumerate(line):
        if char == '"':
            # A run of backslashes escapes the quote that follows them, which is how
            # MSVCRT -- and therefore cmd -- reads the string back.
            backslashes = 0
            cursor = index - 1
            while cursor >= 0 and line[cursor] == "\\":
                backslashes += 1
                cursor -= 1
            if backslashes % 2:
                continue
            inside = not inside
        elif not inside and char in CMD_METACHARS:
            found.append(char)
    return found


def test_displayed_command_line_cannot_chain_a_second_command():
    """The copyable line is re-parsed by a shell, so it must quote what shells act on.

    Typed into cmd.exe, ``seqkit stats -- a&b.fa`` handed seqkit the argument ``a``
    and then tried to run ``b.fa`` as a program; a name arriving from somebody
    else's repository must not be able to do that to a copied command line.
    """
    argv = build_argv(stats(["a&b.fa", "x|y.fa", "a b<c>d.fa", "e^f.fa", unc_path()]))
    line = display_command("seqkit.exe", argv)
    assert bare_metacharacters(line) == [], line


@pytest.mark.skipif(os.name != "nt", reason="cmd.exe quoting only applies to Windows")
def test_displayed_command_line_parses_back_to_the_same_argv(workspace):
    """The OS's own command-line parser reads the copied text as the run argv.

    ``shell32.CommandLineToArgvW`` implements the rule Windows programs use to split
    their command line, which is the rule cmd applies after its own metacharacter
    pass. If the rendered string came back as a different list, then a name with a
    quote or a backslash in it would run something else once pasted.
    """
    import ctypes

    to_argv = ctypes.windll.shell32.CommandLineToArgvW
    to_argv.restype = ctypes.POINTER(ctypes.c_wchar_p)
    for name in CREATABLE_NAMES + UNSTOREABLE_NAMES + [unc_path()]:
        path = str(workspace / name)
        argv = build_argv(stats([path]))
        line = display_command("seqkit.exe", argv)
        argc = ctypes.c_int(0)
        parsed = to_argv(ctypes.c_wchar_p(line), ctypes.byref(argc))
        assert parsed, f"CommandLineToArgvW refused {line!r}"
        try:
            back = [parsed[index] for index in range(argc.value)]
        finally:
            ctypes.windll.kernel32.LocalFree(parsed)
        assert back == ["seqkit.exe", *argv], (name, line, back)
