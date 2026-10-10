"""Finding the seqkit binary the GUI shells out to.

Search order: user-configured path, a binary bundled next to the app, then PATH.
Platform differences are limited to :func:`paths.executable_names` and the extra
macOS locations below, which keeps the Windows build a thin slice of the same code.

The application runs whatever it locates as soon as its window opens, to read
``seqkit version``, so the search is part of the security boundary:

* an automatically discovered candidate has to live in a folder this search chose on
  its own terms -- a bundled directory, a PATH entry that is absolute and is not the
  working directory, or a macOS install prefix. Anything else is refused, which is
  what closes the classic binary-planting hijack: :func:`shutil.which` searches the
  current directory before PATH on Windows and resolves a relative PATH entry against
  it, so a file somebody else dropped next to the app would otherwise be handed to
  ``CreateProcess`` as a PATH hit. Only the path the user picked in Settings escapes
  the rule, and it is inspected as a path instead of as a discovery.
* every candidate has to read as a native executable image (PE, ELF or Mach-O), so
  an HTML error page, a text file or a zero-byte Windows Store alias never reaches
  ``CreateProcess``.
* on Windows, ``.bat`` / ``.cmd`` / ``.ps1`` and similar script files are refused:
  neither ``QProcess`` nor :mod:`subprocess` can start them as a program, and they
  are a standard hijack vehicle.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import paths

#: First bytes of the executable formats each supported platform can run.
_NATIVE_MAGICS = {
    "Windows": (b"MZ",),
    "Darwin": (b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xca\xfe\xba\xbe",
               b"\xbe\xba\xfe\xca", b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xce", b"\x7fELF"),
    "Linux": (b"\x7fELF", b"MZ"),
}

_ALL_MAGICS = tuple(sorted({magic for group in _NATIVE_MAGICS.values() for magic in group}))

#: Windows files that carry a name seqkit could use but cannot be started as a program.
_WINDOWS_SCRIPT_SUFFIXES = {".bat", ".cmd", ".com", ".ps1", ".vbs", ".js", ".lnk", ".url"}

#: Install prefixes a macOS binary usually lives in. Homebrew is frequently absent
#: from the PATH of a process started by Finder, so these are searched by name and
#: counted as trusted folders for the same reason.
_DARWIN_PREFIXES = ("/opt/homebrew/bin", "/usr/local/bin")


@dataclass
class Located:
    path: Path | None
    source: str  # configured | bundled | path | not-found
    detail: str = ""

    @property
    def found(self) -> bool:
        return self.path is not None


def _candidates(configured: str, path_dirs: list[Path]) -> list[tuple[Path, str]]:
    out: list[tuple[Path, str]] = []
    if configured:
        out.append((Path(configured).expanduser(), "configured"))

    for name in paths.executable_names():
        # ``paths.bundled_dir()`` answers ``project_root() / "bin"``, so this one
        # entry is the shipped-binary folder in a source tree and in a bundle alike.
        out.append((paths.bundled_dir() / name, "bundled"))

    for name in paths.executable_names():
        which = shutil.which(name)
        if which:
            out.append((_expand_dir(Path(which)), "path"))
        # which() searches the current directory before PATH on Windows and resolves a
        # relative or empty PATH entry against it, so one of its hits is not evidence
        # that the file came from PATH at all. The directories walked here are, and
        # :func:`locate` accepts a discovered candidate only out of those.
        out.extend((directory / name, "path") for directory in path_dirs)

    if platform.system() == "Darwin":
        for name in paths.executable_names():
            for prefix in _DARWIN_PREFIXES:
                out.append((Path(prefix) / name, "path"))
    return out


def _trusted_directories(path_dirs: list[Path]) -> set[str]:
    """The folders a discovered candidate may legitimately come from.

    The bundled locations, the PATH entries :func:`_search_path` keeps, and the macOS
    install prefixes. A candidate from anywhere else -- the working directory, or a
    relative PATH entry resolved against it -- is a file somebody else put where the
    app would look for it, so it is refused with a reason instead of executed. The
    path the user picked in Settings is the one exception, and it is checked on its
    own terms.
    """
    allowed = [paths.bundled_dir(), *path_dirs]
    if platform.system() == "Darwin":
        allowed.extend(Path(prefix) for prefix in _DARWIN_PREFIXES)
    return {os.path.normcase(str(_expand_dir(item))) for item in allowed}


def locate(configured: str = "") -> Located:
    seen: set[Path] = set()
    refusal = ""
    # Resolving every PATH directory costs a system call each, and both the candidate
    # list and the trust set need that list, so it is walked once per search.
    path_dirs = _search_path()
    trusted = _trusted_directories(path_dirs)
    for candidate, source in _candidates(configured, path_dirs):
        resolved = _expand_dir(candidate)
        if resolved in seen:
            continue
        seen.add(resolved)
        if source != "configured" and os.path.normcase(str(resolved.parent)) not in trusted:
            refusal = refusal or (
                f"{resolved} is not in a folder this search looks in: the working "
                f"directory and relative PATH entries are never trusted")
            continue
        if _runnable(resolved):
            if source != "configured":
                # A native image header says the file is executable, not that it is
                # seqkit: any foreign binary renamed seqkit(.exe) clears every other
                # gate above. A file the user only pointed the PATH at has to answer
                # `version` the way seqkit does, or it is refused rather than handed
                # to all 41 commands. A path chosen in Settings is taken at the user's
                # word, and a version mismatch there is badged in the window instead.
                reported = probe_version(resolved)
                if reported and not looks_like_seqkit(reported):
                    refusal = refusal or (
                        f"{resolved} answered `version` with text seqkit does not print "
                        f"({reported!r}), so it is not used")
                    continue
            return Located(resolved, source)
        if source == "configured":
            reason = _acceptance(resolved)
            if reason and reason != "missing":
                refusal = refusal or f"{resolved} {reason}"
    return Located(None, "not-found", refusal)


def _acceptance(path: Path) -> str:
    """``""`` when this candidate may be executed, otherwise why it may not."""
    try:
        if not path.is_file():
            return "missing"
    except (OSError, ValueError) as exc:            # long path, embedded NUL, no permission
        return f"cannot be inspected ({getattr(exc, 'strerror', None) or type(exc).__name__})"
    if platform.system() == "Windows" and path.suffix.lower() in _WINDOWS_SCRIPT_SUFFIXES:
        return "is a batch or script file, which cannot be started as a program"
    if platform.system() != "Windows" and not os.access(path, os.X_OK):
        return "is not marked executable"
    if not is_native_executable(path):
        return "is not a native executable (expected a PE, ELF or Mach-O image)"
    return ""


def _expand_dir(candidate: Path) -> Path:
    try:
        return candidate.expanduser().resolve()
    except (OSError, ValueError):
        return candidate


def _safe_cwd() -> Path | None:
    try:
        return Path(os.getcwd()).resolve()
    except OSError:
        return None


def _search_path() -> list[Path]:
    """The PATH directories worth searching, in order, with the cwd excluded."""
    cwd = _safe_cwd()
    out: list[Path] = []
    seen: set[str] = set()
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if not entry.strip() or entry in (os.curdir, os.pardir):
            # An empty PATH entry means "the current directory" -- a hijack, not a path.
            continue
        directory = Path(entry)
        if not os.path.isabs(entry):
            # A relative PATH entry is resolved against the working directory, which
            # is exactly the trust the search refuses to extend that far.
            continue
        try:
            resolved = directory.resolve()
        except (OSError, ValueError):
            continue
        if cwd is not None and resolved == cwd:
            continue
        key = os.path.normcase(str(resolved))
        if key in seen:
            continue
        seen.add(key)
        out.append(resolved)
    return out


def is_native_executable(path: Path) -> bool:
    """Whether the file starts with the magic number of a runnable image."""
    try:
        with open(path, "rb") as handle:
            head = handle.read(8)
    except (OSError, ValueError):
        return False
    magics = _NATIVE_MAGICS.get(platform.system(), _ALL_MAGICS)
    if head.startswith(magics):
        return True
    # A shebang script is a normal packaging idiom on POSIX, never on Windows.
    return platform.system() != "Windows" and head.startswith(b"#!")


def _runnable(path: Path) -> bool:
    """The single gate every candidate is put through before it is executed."""
    return _acceptance(path) == ""


def probe_version(path: Path | None, timeout: float = 4.0) -> str:
    """``seqkit version`` output, or an empty string when the binary cannot run."""
    if path is None:
        return ""
    kwargs = {}
    if platform.system() == "Windows":
        # The child is a console program: starting it from a windowed build must not
        # flash a console window on every launch of the app.
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        if flags:
            kwargs["creationflags"] = flags
    try:
        completed = subprocess.run(
            [str(path), "version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            stdin=subprocess.DEVNULL,
            **kwargs,
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        return ""
    first = (completed.stdout or completed.stderr or "").strip().splitlines()
    return first[0].strip() if first else ""


def looks_like_seqkit(text: str) -> bool:
    """Whether ``probe_version`` output came from seqkit rather than some other tool."""
    lowered = (text or "").lower()
    return "seqkit" in lowered and any(char.isdigit() for char in lowered)
