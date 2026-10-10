"""Every command in the table has to assemble a real argv the real binary accepts.

The schema in ``seqkit_gui/data/commands.json`` is generated from SeqKit 2.14.0, and
the shipped executable is the only honest referee: each of the 41 usable subcommands
is asked for its ``--help``, every flag name the GUI can emit has to appear in that
help text, and the smallest argument vector the form would produce must not be
rejected by SeqKit for shape reasons.

The subprocess work is grouped by *what can go wrong*: reading help pages, launching
a vector to completion, and the vectors that are built never to complete. Those three
have different failure modes and different costs, so they are separate cases -- a
command whose vector runs forever must not be able to hide the other forty, and must
not be able to quietly become one of them. The structural half is parameterised,
because that is where a single bad command has to be named.
"""

import subprocess
import time

import pytest

from seqkit_gui.core.builder import FlagState, RunRequest, build_argv, validate
from seqkit_gui.core.spec import Command, load

pytestmark = [pytest.mark.seqkit]

#: Read at collection time so pytest can name each of the 41 cases individually.
ALL_KEYS = [pytest.param(command.key, id=command.key) for command in load().usable]

_PLACEHOLDER_SEQUENCE = "seq1"

#: Seconds a command gets to run its minimal vector to completion. Measured on the
#: shipped binary: every command that ends at all ends in under a second, so this is
#: a wide margin and the cost of one non-terminating case stays bounded.
LAUNCH_TIMEOUT = 15

#: Seconds to watch a vector that is known not to finish before concluding that it
#: does not finish.
WATCH_BUDGET = 8

#: stderr phrases that mean "this argument vector is malformed", as opposed to
#: "this vector is fine but has nothing to work on".
REJECTED_BY_SHAPE = ("required flag", "unknown flag", "unrecognized flag",
                     "invalid argument", "unknown shorthand")

#: Measured on the shipped 2.14.0 binary: minimal vectors that start a process only a
#: Stop can end, with the option fragments that bound each. ``seqkit scat -- <folder>``
#: installs a filesystem watcher and stays alive (stderr: ``[INFO] Watcher (fastq)
#: launched on root: ...``) -- it is not waiting for stdin, which is closed for every
#: launch here and in the application. The same vector with ``--find-only`` concatenates
#: and exits in under a second; ``--time-limit 1s`` bounds it by going idle.
#:
#: A command in this table is a defect the parameter table can close: declaring one of
#: these flags in ``requires_any`` makes the form refuse to run until the user has
#: bounded it, which is what :func:`test_a_vector_that_cannot_finish_is_bounded_by_the_table`
#: demands. Entries are expected to become redundant as that happens, and
#: :func:`test_a_bounding_option_leaves_the_run_ending` measures each one, so a stale
#: entry cannot sit here unchallenged.
UNBOUNDED = {
    "scat": [("--find-only",), ("--time-limit", "1s")],
}


def placeholder_value(flag, workspace: dict) -> str:
    """One plausible, non-empty value for ``flag``: enough to satisfy validation."""
    if flag.is_bool:
        return "true"
    if flag.widget == "in_file":
        return str(workspace["fasta"])
    if flag.widget == "out_file":
        return str(workspace["out"] / f"out-{flag.name}.txt")
    if flag.widget == "dir":
        return str(workspace["folder"])
    if flag.widget == "enum":
        return flag.options[0] if flag.options else "1"
    if flag.widget in {"int", "float"} or flag.type in {"int", "int64", "float64"}:
        return "1"
    if flag.widget == "list":
        return _PLACEHOLDER_SEQUENCE
    if flag.name in {"pattern", "f-pattern", "sequence", "motif", "query-sequences"}:
        return _PLACEHOLDER_SEQUENCE
    if flag.name in {"range", "region", "by-region", "by-id"}:
        return "1..2"
    return "1"


def minimal_request(command: Command, workspace: dict) -> RunRequest:
    """A request that satisfies every requirement the validator declares.

    ``requires_any`` groups need one member, not all of them, and the pick must not
    walk into a ``forbid_pairs`` trap -- both rules are what the validator on the other
    side of this test is meant to enforce.

    The requirements are read back from :func:`validate` rather than only from the
    command entry, because a rule can live in either place: ``requires_any`` comes from
    the parameter table, while a rule the dumper cannot express (``scat`` running
    forever) sits in the validator itself. Satisfying whatever it reports is what makes
    this the "minimum the form is allowed to submit" and not an approximation of it.
    """
    flags: dict[str, FlagState] = {}

    def enable(name: str) -> None:
        flag = command.flag(name)
        if flag is None:
            return
        value = placeholder_value(flag, workspace)
        flags[name] = FlagState(
            enabled=True, value="" if flag.is_list else value,
            items=(value,) if flag.is_list else ())

    def pick(group) -> None:
        for name in group:
            chosen = set(flags) | {name}
            if any(a in chosen and b in chosen for a, b in command.forbid_pairs):
                continue
            enable(name)
            return

    def build() -> RunRequest:
        if command.inputs.kind == "none":
            inputs = ()
        elif command.inputs.kind == "paths":
            # A `paths` contract takes directories as well as files, and the field lets
            # a folder be pasted or dropped, so this is what the form can really produce.
            inputs = tuple([str(workspace["folder"])] * max(1, command.inputs.min))
        else:
            inputs = tuple([str(workspace["fasta"])] * max(command.inputs.min, 0))
        return RunRequest(command=command, inputs=inputs, flags=flags,
                          working_dir=str(workspace["out"]))

    for name in command.requires_all:
        enable(name)
    for group in command.requires_any:
        pick(group)
    for _ in range(6):
        problems = validate(build())
        if problems.ok:
            break
        before = set(flags)
        for group in problems.missing_any:
            pick(group)
        if set(flags) == before:
            break
    return build()


def without(request: RunRequest, names) -> RunRequest:
    """The same request with ``names`` switched back off."""
    flags = {name: state for name, state in request.flags.items() if name not in names}
    return RunRequest(command=request.command, inputs=request.inputs, flags=flags,
                      extra_args=request.extra_args, working_dir=request.working_dir)



@pytest.fixture(scope="module")
def workspace(tmp_path_factory):
    root = tmp_path_factory.mktemp("commands-argv")
    fasta = root / "in.fa"
    fasta.write_text(">seq1 first\nATGAAAGCAGGGCTGTAA\n>seq2 second\nCCCGGATTACA\n",
                     encoding="utf-8")
    folder = root / "sequences"
    folder.mkdir()
    (folder / "nested.fa").write_text(">seq3\nACGT\n", encoding="utf-8")
    out = root / "out"
    out.mkdir()
    return {"fasta": fasta, "folder": folder, "out": out}


def test_command_table_matches_the_release_claims(schema):
    """The release claims 41 subcommands / 353 command parameters / 2.14.0."""
    assert len(schema.commands) == 41
    assert len(schema.usable) == 41
    assert schema.seqkit_version == "2.14.0"
    assert schema.flag_entries == 353
    assert len(schema.groups) == 8
    assert len(schema.global_flag_names) == 11


@pytest.mark.parametrize("key", ALL_KEYS)
def test_minimal_argv_structure_for_every_command(schema, workspace, key):
    """build_argv(command + its minimum legal input) is a clean, all-string argv."""
    command = schema.get(key)
    assert command is not None, key
    request = minimal_request(command, workspace)
    problems = validate(request)
    assert problems.ok, f"{key}: {problems.messages(lambda k, **kw: k)}"

    argv = build_argv(request)
    assert argv[:len(command.command_tokens())] == list(command.command_tokens())
    assert all(isinstance(token, str) for token in argv), key
    assert all(token != "" for token in argv), key
    assert all("\x00" not in token and "\n" not in token for token in argv), key
    for name, state in request.flags.items():
        if state.enabled:
            assert f"--{name}" in " ".join(argv), (key, name)
    if request.inputs:
        assert "--" in argv, f"{key}: inputs must sit behind the terminator"
        tail = argv[argv.index("--") + 1:]
        assert tail == list(request.inputs), key
        assert not any(token.startswith("-") for token in tail), key
    else:
        assert "--" not in argv, f"{key}: an empty file list must not emit --"


def test_binary_advertises_every_command(schema, seqkit_binary):
    """``seqkit --help`` must know every command the GUI offers, by name."""
    done = subprocess.run([str(seqkit_binary), "--help"], capture_output=True,
                          timeout=60, stdin=subprocess.DEVNULL)
    text = done.stdout.decode("utf-8", "replace")
    missing = [command.key for command in schema.usable
               if f"\n  {command.name} " not in text]
    assert not missing, f"the binary does not advertise: {missing}"


@pytest.mark.seqkit
@pytest.mark.slow
def test_every_help_page_lists_the_flags_the_form_can_emit(schema, seqkit_binary):
    """41 ``--help`` calls: every flag name the GUI may write exists in the CLI.

    Split from launching on purpose: reading a help page cannot hang, so this half
    keeps reporting even when one command refuses to return its argument vector.
    """
    failures = []
    checked = 0
    started = time.monotonic()
    for command in schema.usable:
        help_call = subprocess.run([str(seqkit_binary), *command.command_tokens(), "--help"],
                                   capture_output=True, timeout=60, stdin=subprocess.DEVNULL)
        if help_call.returncode != 0:
            failures.append(f"{command.key}: --help exited {help_call.returncode}")
            continue
        text = help_call.stdout.decode("utf-8", "replace")
        for flag in command.all_flags:
            checked += 1
            if f"--{flag.name}" not in text:
                failures.append(f"{command.key}: --{flag.name} absent from --help")
    elapsed = time.monotonic() - started
    print(f"\n{checked} flag rows checked against 41 help pages, {elapsed:.1f}s, "
          f"{len(failures)} failure(s)")
    assert checked >= 353, f"only {checked} flag rows were compared"
    assert not failures, "\n".join(failures)


@pytest.mark.parametrize("key", ALL_KEYS)
def test_minimal_argv_accepted_by_the_real_binary(schema, seqkit_binary, workspace, key):
    """Every command's smallest legal vector must run to completion inside the budget.

    One case per command so a single command that will not finish is named in the
    report and costs the suite one timeout instead of hiding the other forty.
    """
    command = schema.get(key)
    argv = build_argv(minimal_request(command, workspace))
    completed = _launch(seqkit_binary, argv, workspace, LAUNCH_TIMEOUT)
    assert completed is not None, (
        f"{key}: this vector starts something only a Stop can end, and the table lets "
        f"the form produce it: {argv}")
    error = completed.stderr.decode("utf-8", "replace")
    for phrase in REJECTED_BY_SHAPE:
        assert phrase not in error, (
            f"{key}: seqkit rejected {argv}\n    {error.strip()[:200]}")


def test_a_vector_that_cannot_finish_is_bounded_by_the_validator(schema, workspace):
    """A command whose vector never returns must be refused before the child starts.

    Measured on the shipped binary: ``scat -- <folder>`` installs a filesystem watcher
    and is still alive after :data:`WATCH_BUDGET` seconds, while ``--find-only`` makes
    the same vector finish. SeqKit therefore offers a way to bound it, and the form has
    to demand that bound the way it demands ``grep``'s ``--pattern`` -- through
    :func:`validate`, so nothing reaches ``QProcess`` and the user sees a message in
    their own language instead of a run that never ends.

    This is the executable form of what the source is expected to do. It reads the
    refusal out of the validator instead of waiting on the binary, so it costs
    milliseconds, and it goes green with the declaration in ``core/builder.py`` with no
    change here. A validator may bound more commands than this table measures; it may
    not bound fewer.
    """
    from seqkit_gui.core import builder

    declared = getattr(builder, "BOUNDED_RUN_FLAGS", None)
    assert isinstance(declared, dict), (
        "core/builder.py declares no table of commands that need a bound, so a run that "
        "cannot finish is still reachable from the form")

    for key, bounds in sorted(UNBOUNDED.items()):
        command = schema.get(key)
        assert command is not None, f"{key} is no longer an offered command"
        names = {fragment[0].lstrip("-") for fragment in bounds}

        bounded = minimal_request(command, workspace)
        assert validate(bounded).ok, (
            f"{key}: even the request that picks a bound is refused: "
            f"{validate(bounded).messages(lambda k, **kw: k)}")

        unbounded = without(bounded, names)
        problems = validate(unbounded)
        assert not problems.ok, (
            f"{key}: {build_argv(unbounded)} runs forever and the validator accepted it")
        assert problems.problem_flags & names, (
            f"{key}: refused for the wrong reason -- {problems.problem_flags}, "
            f"expected one of {sorted(names)}")

    assert set(UNBOUNDED) <= set(declared), (
        f"measured as never-finishing but not bounded by the validator: "
        f"{sorted(set(UNBOUNDED) - set(declared))}")




@pytest.mark.parametrize("key", sorted(UNBOUNDED))
def test_a_bounding_option_leaves_the_run_ending(schema, seqkit_binary, workspace, key):
    """Each bounding option in :data:`UNBOUNDED` is measured, not taken on trust.

    Two directions are covered here. If the plain vector still runs forever, every
    option listed beside it has to make the very same vector finish. If it already
    finishes -- because the table now forces one of those options into it -- the entry
    has done its job, and this checks that it finishes *because of* one of them rather
    than because seqkit changed under us.
    """
    command = schema.get(key)
    plain = build_argv(minimal_request(command, workspace))
    names = [fragment[0].lstrip("-") for fragment in UNBOUNDED[key]]

    if not _still_running(seqkit_binary, plain, workspace, WATCH_BUDGET):
        present = [name for name in names if any(token == f"--{name}" for token in plain)]
        assert present, (
            f"{key}: {plain} finishes on its own although it contains none of {names}; "
            f"seqkit changed, so this entry no longer describes anything the table has "
            f"to bound and should be removed from UNBOUNDED")
        return

    for fragment in UNBOUNDED[key]:
        bounded = list(plain)
        for position, token in enumerate(fragment):
            bounded.insert(len(command.command_tokens()) + position, token)
        done = _launch(seqkit_binary, bounded, workspace, LAUNCH_TIMEOUT)
        assert done is not None, f"{key}: {' '.join(fragment)} did not bound the run"
        assert done.returncode == 0, (
            f"{key}: {' '.join(fragment)} exited {done.returncode}: "
            f"{done.stderr.decode('utf-8', 'replace').strip()[:200]}")



def _launch(seqkit_binary, argv, workspace, timeout):
    """Run to completion, or ``None`` when the child outlives ``timeout``.

    The child is killed and reaped either way: a sweep that leaves a seqkit running
    behind it poisons the next case and the process-table checks elsewhere.
    """
    handle = subprocess.Popen([str(seqkit_binary), *argv],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              stdin=subprocess.DEVNULL, cwd=str(workspace["out"]))
    try:
        out, err = handle.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        handle.kill()
        handle.communicate(timeout=timeout)
        return None
    return type("Done", (), {"returncode": handle.returncode, "stdout": out, "stderr": err})()


def _still_running(seqkit_binary, argv, workspace, budget):
    """Whether the child survives ``budget`` seconds of watching (and is killable)."""
    handle = subprocess.Popen([str(seqkit_binary), *argv],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              stdin=subprocess.DEVNULL, cwd=str(workspace["out"]))
    try:
        handle.communicate(timeout=budget)
        return False
    except subprocess.TimeoutExpired:
        return True
    finally:
        handle.kill()
        handle.wait(timeout=budget)


