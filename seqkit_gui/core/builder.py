"""Turning form state into the argument vector handed to seqkit.

The GUI never builds a shell command string: it produces an argument list passed
straight to the child process, so a file name containing spaces or quotes cannot
change what seqkit does.

Two rules keep the argument list itself honest:

* positional input files are always introduced by ``--``, which ends option
  parsing. Without it, an input whose name begins with ``-`` -- a pasted or
  typed relative path -- would be read by seqkit as a flag, letting a file name
  turn into ``--out-file`` or ``--infile-list``.
* only flag names that survive :func:`is_safe_token` are emitted, so the
  generated schema cannot smuggle a space or a control character into argv.

:func:`validate` additionally refuses to assemble a run that seqkit would never
end on its own; see :data:`BOUNDED_RUN_FLAGS`.
"""

from __future__ import annotations

import os
import re
import shlex
from dataclasses import dataclass, field
from typing import Iterable

from .spec import Command, Flag

#: Token that ends option parsing for seqkit's pflag-based CLI.
TERMINATOR = "--"

#: Characters that must never reach a child process argument. A NUL truncates the
#: argument at the point it appears, so it is dropped rather than passed on.
_UNSAFE_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

#: Subcommands that keep running until they are told how to stop, and the flags that
#: tell them. ``seqkit scat`` puts a filesystem watcher on the given directories and
#: loops forever (SeqKit 2.14.0 ``scat.go:109-125`` feeding the ``MAIN:`` loop at
#: ``scat.go:176-260``); measured against the shipped binary,
#: ``seqkit scat -- <dir>`` was still alive after 8 s while
#: ``seqkit scat -f -- <dir>`` exited 0 in 4 s. A run that cannot finish would leave
#: the interface stuck on "running" with nothing to show, so it is refused before the
#: child starts. ``--wait-pid`` is deliberately not an accepted exit condition: its
#: default value ``-1`` disables the PID timer (``scat.go:145-150``), so an enabled
#: checkbox does not prove the run ends.
BOUNDED_RUN_FLAGS: dict[str, tuple[str, ...]] = {
    "scat": ("find-only", "time-limit"),
}


def sanitize(value: str) -> str:
    """Strip control characters that argv cannot carry."""
    return _UNSAFE_CHARS.sub("", value)


def is_safe_token(name: str) -> bool:
    """Whether ``name`` can be spelled as one whole ``--flag`` argument."""
    return bool(_TOKEN_RE.fullmatch(name))


@dataclass
class FlagState:
    """One form row. ``enabled`` means 'emit this flag at all'."""

    enabled: bool = False
    value: str = ""
    items: tuple[str, ...] = ()


@dataclass
class RunRequest:
    command: Command
    inputs: tuple[str, ...] = ()
    flags: dict[str, FlagState] = field(default_factory=dict)
    extra_args: str = ""
    working_dir: str = ""

    def state(self, flag: Flag) -> FlagState:
        return self.flags.get(flag.name) or FlagState()


def _items(flag: Flag, state: FlagState) -> tuple[str, ...]:
    if flag.is_list:
        raw = state.items or tuple(
            part.strip() for part in state.value.replace("\n", ",").split(",")
        )
        return tuple(part for part in raw if part != "")
    value = state.value
    return (value,) if value != "" else ()


def build_argv(request: RunRequest) -> list[str]:
    """Arguments after the program name, e.g. ``["grep", "-p", "seq1", "a.fa"]``."""
    argv: list[str] = [sanitize(token) for token in request.command.command_tokens()]

    for flag in request.command.all_flags:
        state = request.flags.get(flag.name)
        if state is None or not state.enabled:
            continue
        if not is_safe_token(flag.name):
            continue

        if flag.is_bool:
            truthy = state.value.strip().lower() not in {"false", "0", "off"}
            if truthy:
                argv.append(flag.cli)
            elif flag.default_is_true:
                # Turning a flag whose default is true back off.
                argv.append(f"{flag.cli}=false")
            continue

        values = _items(flag, state)
        if not values:
            continue
        for value in values:
            argv.extend(sanitize(token) for token in _token(flag, value))

    # Extra arguments are options typed by hand, so they stay on the option side
    # of the terminator below.
    if request.extra_args.strip():
        argv.extend(token for token in shlex.split(request.extra_args, posix=False)
                    if token.strip())

    inputs = [item for item in (sanitize(str(path)) for path in request.inputs) if item]
    if inputs:
        argv.append(TERMINATOR)
        argv.extend(inputs)
    return argv


def _token(flag: Flag, value: str) -> list[str]:
    if value.startswith("-"):
        # ``--flag -1`` would read -1 as another option; ``--flag=-1`` cannot.
        return [f"{flag.cli}={value}"]
    return [flag.cli, value]


def display_command(program: str, argv: Iterable[str]) -> str:
    """Copyable command line, quoted the way this platform's shell expects it."""
    parts = [program, *argv]
    if os.name == "nt":
        return " ".join(_windows_quote(part) for part in parts)
    return " ".join(shlex.quote(part) for part in parts)


#: Characters cmd.exe acts on while they sit outside double quotes: ``&`` and ``|``
#: start another command, ``<`` and ``>`` redirect, ``^`` escapes the next character,
#: ``(`` ``)`` group, ``;`` and ``!`` separate or expand. A file name carrying one of
#: them is only pasteable once quoted -- typed into cmd.exe, ``seqkit stats -- a&b.fa``
#: handed seqkit the argument ``a``, then tried to run ``b.fa`` as a program, while
#: ``seqkit stats -- "a&b.fa"`` exited 0 with the whole name as a single argument.
#: ``%`` is quoted along with them, which keeps the words together but cannot stop
#: cmd.exe from expanding ``%NAME%`` inside quotes; a file name with a percent sign
#: therefore displays text that may differ from what it runs.
_WINDOWS_UNQUOTABLE = ' \t\n"\\&|<>^();!%'


def _windows_quote(value: str) -> str:
    """One argv element, as a Windows program reads it back out of a command line.

    MSVCRT -- the rule ``cmd`` hands on to every normal program, and the rule
    ``shell32.CommandLineToArgvW`` implements -- keeps a backslash literally unless
    it sits in front of a double quote, where ``2n+1`` backslashes plus a quote mean
    n backslashes and one literal quote. Doubling every backslash therefore changes
    the path: ``"C:\\tmp\\a.fa"`` parses back as ``C:\\tmp\\a.fa``, not the name that
    ran. Only the runs that precede a quote, or precede the closing quote, grow.
    """
    if value and not any(char in value for char in _WINDOWS_UNQUOTABLE):
        return value
    out = ['"']
    backslashes = 0
    for char in value:
        if char == "\\":
            backslashes += 1
            continue
        if char == '"':
            out.append("\\" * (backslashes * 2 + 1))
            out.append('"')
        else:
            out.append("\\" * backslashes)
            out.append(char)
        backslashes = 0
    out.append("\\" * (backslashes * 2))
    out.append('"')
    return "".join(out)


@dataclass
class Validation:
    """Form-level problems that would make seqkit fail immediately.

    Problems are stored structurally and rendered through the language catalogue,
    so the dialog that refuses a run reads the same in either interface language.
    """

    missing_any: list[list[str]] = field(default_factory=list)
    missing_all: list[str] = field(default_factory=list)
    conditional_missing: list[tuple[str, str]] = field(default_factory=list)
    input_problem: tuple[str, dict] | None = None
    conflicts: list[tuple[str, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not (self.missing_any or self.missing_all or self.conditional_missing
                    or self.input_problem or self.conflicts)

    @property
    def problem_flags(self) -> set[str]:
        names = set(self.missing_all)
        for group in self.missing_any:
            names.update(group)
        for _, needed in self.conditional_missing:
            names.add(needed)
        return names

    def messages(self, tr) -> list[str]:
        out: list[str] = []
        for group in self.missing_any:
            out.append(tr("one of {names} is required",
                          names=" / ".join(f"--{name}" for name in group)))
        for name in self.missing_all:
            out.append(tr("{name} is required", name=f"--{name}"))
        for trigger, needed in self.conditional_missing:
            out.append(tr("{needed} is required because {trigger} is enabled",
                          needed=f"--{needed}", trigger=f"--{trigger}"))
        if self.input_problem is not None:
            key, kwargs = self.input_problem
            out.append(tr(key, **kwargs))
        for left, right in self.conflicts:
            out.append(tr("{left} and {right} cannot be used together",
                          left=f"--{left}", right=f"--{right}"))
        return out


def validate(request: RunRequest) -> Validation:
    command = request.command
    result = Validation()

    for name in command.requires_all:
        flag = command.flag(name)
        if flag and not _satisfied(flag, request.flags.get(name) or FlagState()):
            result.missing_all.append(name)

    for trigger, needed in command.conditional:
        left, right = command.flag(trigger), command.flag(needed)
        if left and right and _satisfied(left, request.flags.get(trigger) or FlagState()) \
                and not _satisfied(right, request.flags.get(needed) or FlagState()):
            result.conditional_missing.append((trigger, needed))

    for group in command.requires_any:
        if not any(
            _satisfied(command.flag(name) or Flag(name=name), request.flags.get(name) or FlagState())
            for name in group
        ):
            result.missing_any.append(list(group))

    for left_name, right_name in command.forbid_pairs:
        left = request.flags.get(left_name) or FlagState()
        right = request.flags.get(right_name) or FlagState()
        flag_left = command.flag(left_name)
        flag_right = command.flag(right_name)
        if flag_left and flag_right and _satisfied(flag_left, left) and _satisfied(flag_right, right):
            result.conflicts.append((left_name, right_name))

    inputs = command.inputs
    count = len(request.inputs)
    if inputs.kind == "none" and count:
        result.input_problem = ("this command does not accept input files as arguments", {})
    elif inputs.positional and count < inputs.min:
        if inputs.max == inputs.min:
            result.input_problem = ("exactly {n} input file(s) required", {"n": inputs.min})
        else:
            result.input_problem = ("at least {min} input file(s) required",
                                    {"min": inputs.min})

    for name, exits in BOUNDED_RUN_FLAGS.items():
        if command.key != name:
            continue
        available = [option for option in exits if command.flag(option) is not None]
        if available and not any(_satisfied(command.flag(option),
                                            request.flags.get(option) or FlagState())
                                 for option in available):
            result.missing_any.append(available)
    return result


def _satisfied(flag: Flag, state: FlagState) -> bool:
    if not state.enabled:
        return False
    if flag.is_bool:
        return state.value.strip().lower() not in {"false", "0", "off"}
    return bool(_items(flag, state))
