"""``run.bat`` and ``run.sh`` started as the processes a user actually starts.

A launcher is the only part of this project whose output nobody can see from inside the
interface, so its advice is tested by reading what it really prints. Three failures a
machine can be in are measured -- no interpreter on PATH, an interpreter that answers
without being Python, and an interpreter that has no PySide6 -- along with the seqkit
advice, which is the one message a launcher has to reach by the app's own rules rather
than by testing whether one file name exists.

Every case runs against a scratch copy of the project holding the real
:mod:`seqkit_gui.core.seqkit_locator`, so the search the launcher reports on is the
search the interface performs. The stand-in entry point prints and leaves: nothing here
can open a window, and a launcher that hangs fails instead of blocking the suite.

``run.sh`` is exercised wherever a bash exists, which on a Windows host means its logic
through MSYS bash rather than its macOS behaviour: the platform's own paths are what
differ, and the assertions read only the words the launcher prints.
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.launcher]

ROOT = Path(__file__).resolve().parent.parent

#: The files the locator needs, and nothing that imports Qt.
SEARCH_PACKAGE = ("__init__.py", "core/__init__.py", "core/paths.py", "core/seqkit_locator.py")

#: Stands in for the interface: it imports the dependency the launchers check for, then
#: leaves without touching the display, and repeats any arguments so forwarding is visible.
ENTRY_POINT = '''"""Scratch entry point: imports what the real launcher-dependent code imports, reports."""

import sys

import PySide6

print("PROBE-STARTED", "argv=" + ",".join(sys.argv[1:]))
sys.exit(0)
'''


def _system_directories() -> list[str]:
    """The Windows folders every batch built-in and helper this test needs."""
    system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    return [str(system_root / "System32"), str(system_root)]


def _interpreter_directory() -> str:
    return str(Path(sys.executable).resolve().parent)


def _store_alias() -> Path | None:
    """The real Microsoft Store ``python.exe`` alias, when this machine has one.

    It answers ``where python``, writes nothing and fails, which is the case the
    launcher has to name. Nothing synthetic reproduces it as well.
    """
    local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    for name in ("python.exe", "python3.exe"):
        candidate = Path(local) / "Microsoft" / "WindowsApps" / name
        if candidate.is_file():
            return candidate
    return None


def _native_payload() -> bytes:
    if sys.platform == "win32":
        return b"MZ\x90\x00\x03\x00\x00\x00 scratch image header"
    return b"\x7fELF\x02\x01\x01\x00 scratch image header"


def _seqkit_file(directory: Path, text: bool = False) -> Path:
    """Drop a stand-in seqkit into ``directory``, native or plainly not."""
    from seqkit_gui.core.paths import executable_names

    directory.mkdir(parents=True, exist_ok=True)
    path = directory / executable_names()[0]
    path.write_bytes(b"not a program, a text file" if text else _native_payload())
    if sys.platform != "win32" and not text:
        path.chmod(0o755)
    return path


@pytest.fixture
def launcher_project(tmp_path) -> Path:
    """A project folder holding the real search code and an inert entry point."""
    project = tmp_path / "project"
    package = project / "seqkit_gui"
    for relative in SEARCH_PACKAGE:
        target = package / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / "seqkit_gui" / relative, target)
    (package / "__main__.py").write_text(ENTRY_POINT, encoding="utf-8")
    (package / "__init__.py").write_text(
        (ROOT / "seqkit_gui" / "__init__.py").read_text(encoding="utf-8"), encoding="utf-8")
    for script in ("run.bat", "run.sh"):
        shutil.copyfile(ROOT / script, project / script)
    (project / "run.sh").chmod(0o755)
    (project / "requirements.txt").write_text("PySide6\n", encoding="utf-8")
    return project


def _environment(directories: list[str], **extra) -> dict[str, str]:
    env = {
        "SystemRoot": os.environ.get("SystemRoot", r"C:\Windows"),
        "PATH": os.pathsep.join(directories),
        "PATHEXT": os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD"),
        "COMSPEC": os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe"),
        # A console codepage the child can encode ASCII advice into, whatever the user's
        # machine is set to: these assertions read English text, not a locale.
        "PYTHONIOENCODING": "utf-8",
    }
    for key, value in extra.items():
        if value is not None:
            env[key] = value
    return env


def _start(project: Path, script: str, directories: list[str], args=(),
           env_extra=None, timeout=90):
    """Run one launcher and hand back its exit code plus both output channels.

    Standard input is closed rather than inherited: a launcher that reaches for a key
    press on ``pause`` has to see end-of-file and move on, which is also what makes the
    whole file safe to run unattended.
    """
    env_extra = dict(env_extra or {})
    bash = _bash()
    if script.endswith(".bat"):
        command = [os.environ.get("COMSPEC", "cmd.exe"), "/c", script, *args]
    else:
        if bash is None:
            raise AssertionError("run.sh needs a bash to be started")
        command = [bash, script, *args]
    env = _environment(directories, **env_extra)
    try:
        completed = subprocess.run(command, cwd=str(project), env=env, stdin=subprocess.DEVNULL,
                                   capture_output=True, text=True, encoding="utf-8",
                                   errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired as error:
        raise AssertionError(
            f"{script} did not finish within {timeout}s; a launcher that waits on a "
            f"window or a key press is itself the failure being tested") from error
    return completed.returncode, (completed.stdout or "") + (completed.stderr or "")


def _bash() -> str | None:
    return shutil.which("bash") or ("/bin/bash" if Path("/bin/bash").is_file() else None)


needs_windows = pytest.mark.skipif(os.name != "nt", reason="run.bat is a cmd.exe script")
needs_bash = pytest.mark.skipif(_bash() is None, reason="no bash interpreter on this host")


# --------------------------------------------------------------------------- run.bat


@needs_windows
def test_run_bat_stops_and_says_so_when_there_is_no_interpreter(launcher_project):
    """The first failure a fresh Windows machine has: nothing called ``python``."""
    code, out = _start(launcher_project, "run.bat", _system_directories())
    assert code != 0
    assert "[error] python was not found on PATH." in out, out
    assert "www.python.org/downloads" in out, out
    assert "Starting SeqKit GUI" not in out, out


@needs_windows
def test_run_bat_names_an_interpreter_that_answers_without_being_python(launcher_project,
                                                                       tmp_path):
    """``where python`` finding a name is not the same as having an interpreter.

    Measured against the real Microsoft Store alias when the machine has one, because
    it is the file that actually sits on PATH in place of Python; otherwise against a
    batch file that prints nothing for ``-c``, which is the same observable behaviour.
    """
    alias = _store_alias()
    if alias is not None:
        directories = [str(alias.parent), *_system_directories()]
    else:
        stub = tmp_path / "stub"
        stub.mkdir()
        (stub / "python.bat").write_bytes(b"@echo off\r\nexit /b 9009\r\n")
        directories = [str(stub), *_system_directories()]
    code, out = _start(launcher_project, "run.bat", directories)
    assert code != 0
    assert "does not run as a Python interpreter" in out, out
    assert "App execution aliases" in out, out
    assert "PySide6" not in out, out
    assert "Starting SeqKit GUI" not in out, out


@needs_windows
def test_run_bat_refuses_an_interpreter_older_than_the_floor_it_declares(launcher_project,
                                                                         tmp_path):
    """An old interpreter would fail on its own with a message about a module.

    The stub reports a version number below the floor run.bat enforces, which is what a
    Python 3.8 install does when the interface asks it for ``match`` or ``X | Y``.
    """
    floor = _batch_version_floor()
    fake = floor - 1
    stub = tmp_path / "stub"
    stub.mkdir()
    (stub / "python.bat").write_bytes(
        f'@echo off\r\nif "%~1"=="-c" (echo {fake}& exit /b 0)\r\nexit /b 0\r\n'.encode())
    code, out = _start(launcher_project, "run.bat", [str(stub), *_system_directories()])
    assert code != 0
    assert "older than 3.10" in out, out
    assert "requirements.txt" not in out, out


@needs_windows
@pytest.mark.slow
def test_run_bat_says_which_dependency_the_interpreter_lacks(launcher_project, no_dependency_env):
    """An interpreter with no PySide6 is the common first run after a clone."""
    bin_dir = no_dependency_env
    code, out = _start(launcher_project, "run.bat", [str(bin_dir), *_system_directories()])
    assert code != 0, out
    assert "[hint] PySide6 does not seem to be installed" in out, out
    assert "python -m pip install -r requirements.txt" in out, out
    assert "[error] SeqKit GUI exited with an error" in out, out
    assert "No module named" in out, out
    assert "Starting SeqKit GUI ..." in out, out


@pytest.fixture(scope="session")
def no_dependency_env(tmp_path_factory):
    """A real interpreter with no PySide6 in it: an env without site-packages.

    ``python -m venv --without-pip`` takes about a second and cannot reach the network,
    so this is the actual state of a fresh clone rather than a stub pretending to be one.
    """
    root = tmp_path_factory.mktemp("no-deps-env")
    completed = subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(root)],
                               capture_output=True, text=True, timeout=300)
    if completed.returncode != 0:
        pytest.skip(f"this interpreter cannot create a virtualenv: {completed.stderr.strip()[:200]}")
    bin_dir = root / ("Scripts" if os.name == "nt" else "bin")
    python = bin_dir / ("python.exe" if os.name == "nt" else "python")
    if not python.is_file():
        pytest.skip(f"the virtualenv has no interpreter at {python}")
    check = subprocess.run([str(python), "-c", "import PySide6"], capture_output=True, text=True)
    if check.returncode == 0:
        pytest.skip("the virtualenv inherited PySide6 from the base interpreter")
    return bin_dir


@needs_windows
def test_run_bat_starts_the_interface_and_reports_where_seqkit_came_from(launcher_project):
    """The healthy path, on the machine that has both halves installed."""
    _seqkit_file(launcher_project / "bin")
    code, out = _start(launcher_project, "run.bat",
                       [_interpreter_directory(), *_system_directories()])
    assert code == 0, out
    assert '[seqkit] "bin\\seqkit.exe"' in out, out
    assert "Starting SeqKit GUI ..." in out, out
    assert "PROBE-STARTED" in out, out
    assert "[hint]" not in out, out
    assert "[error]" not in out, out


@needs_windows
def test_run_bat_announces_a_seqkit_it_can_reach_through_path(launcher_project):
    """A seqkit reachable through PATH is an installation, not a missing one.

    ``bin\\seqkit.exe`` is not the only place the interface looks: its search walks every
    absolute PATH folder too, so a machine-wide install runs every command fine. The
    search answers here, and its answer is what the launcher prints.
    """
    on_path = _seqkit_file(launcher_project.parent / "installed")
    code, out = _start(launcher_project, "run.bat",
                       [str(on_path.parent), _interpreter_directory(), *_system_directories()])
    assert code == 0, out
    assert "[seqkit] found on PATH, so no copy inside bin\\ is needed." in out, out
    assert "[hint] No usable seqkit was found" not in out, out


@needs_windows
def test_run_bat_says_where_it_looked_when_seqkit_is_nowhere(launcher_project):
    """Neither folder holds one: the advice has to name both places it checked."""
    code, out = _start(launcher_project, "run.bat",
                       [_interpreter_directory(), *_system_directories()])
    assert code == 0, out
    assert "[hint] No usable seqkit was found" in out, out
    assert "nothing acceptable in bin\\" in out, out
    assert "nothing on PATH" in out, out
    assert "python tools\\fetch_seqkit.py" in out, out
    assert "leave it on PATH" in out, out
    assert "Starting the interface anyway" in out, out


@needs_windows
def test_run_bat_treats_a_bin_copy_the_app_would_refuse_as_not_installed(
        launcher_project):
    """A text file named seqkit.exe is present and unusable; the hint has to fire.

    Existence is not the app's rule -- it reads a native image header -- so a launcher
    that checks only for the file promises a run that the locator then refuses.
    """
    _seqkit_file(launcher_project / "bin", text=True)
    code, out = _start(launcher_project, "run.bat",
                       [_interpreter_directory(), *_system_directories()])
    assert code == 0, out
    assert "[hint] No usable seqkit was found" in out, out
    assert "PROBE-STARTED" in out, out


@needs_windows
def test_run_bat_forwards_arguments_to_the_interface(launcher_project):
    """``run.bat --help`` reaches the interface instead of being eaten by the script."""
    _seqkit_file(launcher_project / "bin")
    code, out = _start(launcher_project, "run.bat",
                       [_interpreter_directory(), *_system_directories()],
                       args=["--probe-flag", "value with spaces"])
    assert code == 0, out
    assert "argv=--probe-flag,value with spaces" in out, out


@needs_windows
def test_run_bat_keeps_working_with_unix_line_endings(launcher_project):
    """The repository stores these files as LF and ``eol=crlf`` only rewrites a checkout.

    cmd.exe reads the script as it sits on disk, so the block structure the launcher
    depends on -- nested ``if`` blocks and a ``for /f`` around a quoted command -- has to
    survive without carriage returns, which is the state a fresh clone is in.
    """
    script = launcher_project / "run.bat"
    text = script.read_text(encoding="utf-8")
    assert "\r\n" not in text
    _seqkit_file(launcher_project / "bin")
    code, out = _start(launcher_project, "run.bat",
                       [_interpreter_directory(), *_system_directories()])
    assert code == 0, out
    assert '[seqkit] "bin\\seqkit.exe"' in out, out
    assert "PROBE-STARTED" in out, out


def _posix_path(path: Path) -> str:
    """``path`` in the spelling a shell on this host takes as an absolute location.

    A launcher splits ``$0`` on forward slashes only, which is right for POSIX; a test
    that hands bash a Windows drive path has to hand it the mount-style form bash itself
    uses, or the launcher is being tested against a spelling no user types.
    """
    text = path.as_posix()
    if os.name == "nt" and len(text) > 2 and text[1] == ":":
        return f"/{text[0].lower()}{text[2:]}"
    return text


def _bash_directories() -> list[str]:
    """A PATH a shell can start from: an interpreter plus the platform's own tools.

    Under MSYS bash the two notations mix inside one semicolon-separated value, which is
    how the host's own PATH already arrives.
    """
    core = _system_directories() if os.name == "nt" else ["/usr/bin", "/bin"]
    if os.name == "nt":
        core = [*core, "/usr/bin", "/bin"]
    return [_interpreter_directory(), *core]


# --------------------------------------------------------------------------- run.sh


@needs_bash
def test_bash_reads_the_posix_launcher_as_a_script():
    """A launcher with a syntax error never reaches a single error message."""
    completed = subprocess.run([_bash(), "-n", str(ROOT / "run.sh")],
                               capture_output=True, text=True, timeout=60)
    assert completed.returncode == 0, completed.stderr
    assert completed.stderr.strip() == ""


@needs_bash
def test_the_posix_launcher_is_a_shell_script_with_unix_line_endings():
    """``run.sh`` with a CRLF breaks before it runs: the shebang line itself is unreadable."""
    data = (ROOT / "run.sh").read_bytes()
    assert data.startswith(b"#!/usr/bin/env bash\n"), data[:24]
    assert b"\r" not in data, "run.sh must stay LF: bash on macOS refuses a CRLF shebang"
    assert (ROOT / "run.bat").read_bytes().startswith(b"@echo off"), "run.bat needs its cmd header"


@needs_bash
def test_the_posix_launcher_asks_python_about_the_same_things_cmd_is_asked():
    """The two launchers are one contract in two dialects, so they say the same things.

    Both have to look for an interpreter, name a missing dependency, hand the seqkit
    search to the app's own code, and forward the arguments.
    """
    sh = (ROOT / "run.sh").read_text(encoding="utf-8")
    bat = (ROOT / "run.bat").read_text(encoding="utf-8")
    for needle in ("seqkit_locator", "fetch_seqkit", "requirements.txt", "PySide6"):
        assert needle in sh, needle
        assert needle in bat, needle
    assert 'locate("")' in sh, sh
    assert "locate('')" in bat, bat


def _batch_version_floor() -> int:
    """The interpreter floor ``run.bat`` enforces, as ``sys.version_info`` arithmetic."""
    text = (ROOT / "run.bat").read_text(encoding="utf-8")
    match = re.search(r"LSS\s*(\d+)", text)
    assert match, "run.bat declares no interpreter floor"
    return int(match.group(1))


def test_the_launchers_enforce_the_floor_the_project_declares():
    """``requires-python``, ``run.bat`` and ``run.sh`` state one minimum, not three.

    A launcher that refuses an interpreter the metadata allows -- or accepts one the
    metadata rules out -- sends users to install something the project does not need, or
    lets them start something it cannot run on.
    """
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'requires-python\s*=\s*">=\s*(\d+)\.(\d+)"', text)
    assert match, f"pyproject.toml declares requires-python in an unexpected form: {text[:400]}"
    major, minor = int(match.group(1)), int(match.group(2))

    assert _batch_version_floor() == major * 100 + minor, (
        f"run.bat refuses anything below {_batch_version_floor()} while pyproject says "
        f">= {major}.{minor}")
    sh = (ROOT / "run.sh").read_text(encoding="utf-8")
    assert f"sys.version_info >= ({major}, {minor})" in sh, "run.sh enforces another floor"
    bat = (ROOT / "run.bat").read_text(encoding="utf-8")
    assert f"older than {major}.{minor}" in bat, "run.bat names another floor in its message"


@needs_bash
def test_run_sh_stops_and_says_so_when_there_is_no_interpreter(launcher_project, tmp_path):
    """``PATH`` without python3 or python is the fresh-macOS-without-homebrew case."""
    empty = tmp_path / "empty-path"
    empty.mkdir()
    code, out = _start(launcher_project, "./run.sh", [str(empty)])
    assert code != 0
    assert "[error] python3 was not found on PATH." in out, out
    assert "brew install python" in out, out
    assert "Starting SeqKit GUI" not in out, out


@needs_bash
def test_run_sh_names_a_python_that_is_on_path_without_working(launcher_project):
    """The Microsoft Store alias and a broken venv both land here.

    ``PYTHON`` is pointed at a program that fails every interpreter test -- ``false`` --
    because that is exactly what an app-execution alias does from a shell.
    """
    stand_in = shutil.which("false") or "/usr/bin/false"
    if not Path(stand_in).is_file():
        pytest.skip("this host has no program that reliably fails")
    code, out = _start(launcher_project, "./run.sh", [str(Path(stand_in).parent)],
                       env_extra={"PYTHON": stand_in})
    assert code != 0
    assert "does not run as a working Python" in out, out
    assert "PYTHON=" in out, out


@needs_bash
def test_run_sh_announces_a_seqkit_it_can_reach_through_path(launcher_project):
    """The same contract in the POSIX launcher: installed, just not inside bin/."""
    on_path = _seqkit_file(launcher_project.parent / "installed")
    directories = [str(on_path.parent), *_bash_directories()]
    code, out = _start(launcher_project, "./run.sh", directories)
    assert code == 0, out
    assert "[seqkit] found on PATH, so no copy inside bin/ is needed." in out, out
    assert "No usable seqkit was found" not in out, out


@needs_bash
def test_run_sh_says_where_it_looked_when_seqkit_is_nowhere(launcher_project):
    directories = _bash_directories()
    code, out = _start(launcher_project, "./run.sh", directories)
    assert code == 0, out
    assert "[hint] No usable seqkit was found" in out, out
    assert "nothing acceptable in bin/" in out, out
    assert "tools/fetch_seqkit.py" in out, out
    assert "leave it on PATH" in out, out


@needs_bash
def test_run_sh_reports_a_bundled_copy_and_starts_the_interface(launcher_project):
    _seqkit_file(launcher_project / "bin")
    directories = _bash_directories()
    code, out = _start(launcher_project, "./run.sh", directories)
    assert code == 0, out
    assert "[seqkit] bin/" in out, out
    assert "PROBE-STARTED" in out, out
    assert "[hint]" not in out, out


@needs_bash
def test_run_sh_treats_a_bin_copy_the_app_would_refuse_as_not_installed(launcher_project):
    if sys.platform == "win32":
        pytest.skip("the executable-bit rule that makes this case visible is not Windows'")
    directory = launcher_project / "bin"
    _seqkit_file(directory, text=True)
    (directory / "seqkit").chmod(0o644)
    code, out = _start(launcher_project, "./run.sh",
                       _bash_directories())
    assert code == 0, out
    assert "[hint] No usable seqkit was found" in out, out


@needs_bash
def test_run_sh_forwards_arguments_to_the_interface(launcher_project):
    _seqkit_file(launcher_project / "bin")
    code, out = _start(launcher_project, "./run.sh",
                       _bash_directories(),
                       args=["--probe-flag", "value with spaces"])
    assert code == 0, out
    assert "argv=--probe-flag,value with spaces" in out, out


@needs_bash
def test_run_sh_starts_from_any_folder_and_needs_no_core_utilities(launcher_project, tmp_path):
    """A launcher locates its own folder with shell expansions, not with external tools.

    Run from a different working directory, with a PATH that resolves nothing but an
    interpreter and the system tools, the script still has to find its own folder --
    ``bin/``, ``tools/`` and the app package are all located from there -- and still has
    to leave the folder it was called from alone.
    """
    _seqkit_file(launcher_project / "bin")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    script = launcher_project / "run.sh"
    completed = subprocess.run(
        [_bash(), _posix_path(script)], cwd=str(elsewhere),
        env=_environment(_bash_directories()),
        stdin=subprocess.DEVNULL, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=90)
    out = (completed.stdout or "") + (completed.stderr or "")
    assert completed.returncode == 0, out
    assert "command not found" not in out, out
    assert '[seqkit] "bin' in out or "[seqkit] bin/" in out, out
    assert "PROBE-STARTED" in out, out
    assert not list(elsewhere.iterdir()), "the launcher wrote into the calling directory"


@pytest.fixture
def launcher_without_a_package(tmp_path) -> Path:
    """A folder holding the launcher and nothing else: the copy-run.bat-alone case.

    The seqkit advice comes from the app's own search, and that search needs the app
    package. What the launcher does when it cannot get an answer is the difference
    between a useful fallback and silence.
    """
    lonely = tmp_path / "lonely"
    lonely.mkdir()
    for script in ("run.bat", "run.sh"):
        shutil.copyfile(ROOT / script, lonely / script)
    (lonely / "run.sh").chmod(0o755)
    return lonely


@needs_windows
def test_run_bat_falls_back_to_its_own_file_test_when_the_app_is_absent(
        launcher_without_a_package):
    """No importable package: the one thing left is whether the file is there.

    The launcher still has to speak, because a machine running `python -m seqkit_gui`
    with no package to run has two problems and the seqkit half of them must not go
    unmentioned.
    """
    project = launcher_without_a_package
    code, out = _start(project, "run.bat", [_interpreter_directory(), *_system_directories()])
    assert code != 0, out
    assert "[hint] No usable seqkit was found" in out, out
    assert "No module named seqkit_gui" in out, out

    _seqkit_file(project / "bin")
    code, out = _start(project, "run.bat", [_interpreter_directory(), *_system_directories()])
    assert code != 0, out
    assert '[seqkit] "bin\\seqkit.exe"' in out, out
    assert "[hint] No usable seqkit was found" not in out, out


@needs_bash
def test_run_sh_falls_back_to_its_own_file_test_when_the_app_is_absent(
        launcher_without_a_package):
    """The same fallback in the POSIX launcher, including its exit status."""
    project = launcher_without_a_package
    code, out = _start(project, "./run.sh", _bash_directories())
    assert code != 0, out
    assert "[hint] No usable seqkit was found" in out, out

    _seqkit_file(project / "bin")
    code, out = _start(project, "./run.sh", _bash_directories())
    assert code != 0, out
    assert "[seqkit] bin/" in out, out
    assert "[hint] No usable seqkit was found" not in out, out
