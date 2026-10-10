"""Shared test infrastructure.

Two properties matter for a suite that drives a real Qt application and a real
child process:

* nothing may leak into the developer's machine -- Qt settings are redirected to a
  temporary ini file, and every artefact a test writes lives in a pytest
  ``tmp_path``;
* the suite has to be runnable headless, on any platform, alongside other test
  processes using the same source tree, so the ``seqkit`` binary and the
  ``QApplication`` are treated as read-only session resources.
"""

import os

# Headless by default: CI (Linux runners) has no display, and a GUI test that
# needs one is a screenshot test, which is opt-in (see --with-screenshots).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.*=false")
# Console output of the launcher tests is compared verbatim.
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import subprocess  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

MARKERS = {
    "gui": "needs a QApplication (PySide6 import and offscreen platform)",
    "seqkit": "invokes the real seqkit executable",
    "slow": "takes seconds rather than milliseconds",
    "screenshot": "renders pixels; skipped unless --with-screenshots is given",
    "launcher": "runs run.bat / run.sh as a subprocess",
}


def pytest_configure(config):
    for name, description in MARKERS.items():
        config.addinivalue_line("markers", f"{name}: {description}")


def pytest_addoption(parser):
    parser.addoption("--with-screenshots", action="store_true", default=False,
                     help="run the tests that render the interface to PNG files")
    parser.addoption("--with-launchers", action="store_true", default=False,
                     help="run the tests that start run.bat / run.sh as subprocesses")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--with-screenshots"):
        skip = pytest.mark.skip(reason="pass --with-screenshots to render interface images")
        for item in items:
            if "screenshot" in item.keywords or "screenshot" in item.name.lower():
                item.add_marker(skip)
    if not config.getoption("--with-launchers"):
        skip = pytest.mark.skip(
            reason="pass --with-launchers to start run.bat / run.sh as subprocesses")
        for item in items:
            if "launcher" in item.keywords:
                item.add_marker(skip)


@pytest.fixture(scope="session")
def root() -> Path:
    return ROOT


@pytest.fixture(scope="session")
def schema():
    from seqkit_gui.core.spec import load
    return load(reload=True)


@pytest.fixture(scope="session")
def sample_fasta() -> Path:
    return ROOT / "tests" / "data" / "short1.fa"


@pytest.fixture(scope="session")
def sample_fasta2() -> Path:
    return ROOT / "tests" / "data" / "short2.fa"


@pytest.fixture(scope="session")
def sample_fastq() -> Path:
    return ROOT / "tests" / "data" / "reads.fq"


@pytest.fixture(scope="session")
def seqkit_binary() -> Path:
    from seqkit_gui.core import seqkit_locator
    found = seqkit_locator.locate("")
    if not found.found:
        pytest.skip("seqkit executable not available")
    return found.path


@pytest.fixture(scope="session")
def qapp():
    """One QApplication per process; tests must not destroy it.

    ``QT_QPA_PLATFORM`` is already pinned to offscreen at import time, so this is
    headless even when the developer's own environment asks for a real platform.
    """
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app
    if QApplication.instance() is not app:  # pragma: no cover - defensive
        raise AssertionError("a test replaced the shared QApplication")


@pytest.fixture(scope="session", autouse=True)
def isolated_settings(tmp_path_factory):
    """Redirect QSettings to a scratch ini file for the whole session.

    ``Preferences.save()`` and the recent-files list write through
    ``QSettings(ORGANIZATION, APPLICATION)``, which on Windows is the registry.
    Without this, every run rewrites the developer's real preferences and two
    concurrent pytest sessions overwrite each other.
    """
    from PySide6.QtCore import QSettings

    from seqkit_gui.core import settings as store

    path = tmp_path_factory.mktemp("qsettings") / "seqkit-gui-tests.ini"
    backup = store.settings

    def factory():
        return QSettings(str(path), QSettings.Format.IniFormat)

    store.settings = factory
    try:
        yield path
    finally:
        store.settings = backup
        if path.is_file():
            path.unlink(missing_ok=True)


@pytest.fixture
def fresh_settings(tmp_path, monkeypatch):
    """A settings store containing nothing but what this one test writes.

    ``isolated_settings`` keeps the suite away from the developer's real
    preferences, but it is one file for the whole session: a test that asserts on
    the *contents* of a stored list would then depend on which tests ran before it,
    because anything that opens a window and runs a command appends to the recent
    files. Tests that count what is in the store take this fixture instead, and no
    test constructs ``QSettings(ORGANIZATION, APPLICATION)`` at all -- that is the
    registry entry a real user's preferences live in.
    """
    from PySide6.QtCore import QSettings

    from seqkit_gui.core import settings as store

    path = tmp_path / "preferences.ini"

    def factory():
        return QSettings(str(path), QSettings.Format.IniFormat)

    monkeypatch.setattr(store, "settings", factory)
    yield path


@pytest.fixture
def wait_for(qapp):
    """Pump the Qt event loop until ``predicate()`` is true or the timeout fires.

    Returns the elapsed seconds, or ``None`` when the predicate never held.
    """
    from PySide6.QtCore import QCoreApplication

    def pump(predicate, timeout=20.0, poll=0.01):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            QCoreApplication.processEvents()
            if predicate():
                return time.monotonic() - (deadline - timeout)
            time.sleep(poll)
        QCoreApplication.processEvents()
        return None

    return pump


@pytest.fixture
def process_probe():
    """Ask the operating system which child processes are alive.

    Used by the tests that close the window mid-run: "no orphan seqkit" has to be
    measured against the process table, not against the QProcess object that the
    test itself owns.
    """
    def children(parent_pid=None):
        parent = parent_pid if parent_pid is not None else os.getpid()
        if os.name == "nt":
            script = ("Get-CimInstance Win32_Process -Filter \"ParentProcessId=%d\" "
                      "| ForEach-Object { \"$($_.ProcessId):$($_.Name)\" }" % parent)
            try:
                out = subprocess.run(["powershell", "-NoProfile", "-Command", script],
                                     capture_output=True, timeout=30,
                                     encoding="utf-8", errors="replace").stdout
            except (OSError, subprocess.SubprocessError):
                return None
            return {int(line.split(":", 1)[0]) for line in out.splitlines() if line.strip()}
        try:
            out = subprocess.run(["ps", "-o", "pid=", "--ppid", str(parent)],
                                 capture_output=True, timeout=30,
                                 encoding="utf-8", errors="replace").stdout
        except (OSError, subprocess.SubprocessError):
            return None
        return {int(token) for token in out.split() if token.isdigit()}

    def alive(pid):
        if os.name == "nt":
            # On a Chinese-locale Windows the "no tasks match" message is GBK text;
            # decoding it strictly raises inside subprocess's reader thread and
            # hands back stdout=None. Only digits matter here, so replace what
            # cannot decode instead of failing the probe.
            out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                                 capture_output=True, timeout=30,
                                 encoding="utf-8", errors="replace").stdout
            return str(pid) in out
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    return type("ProcessProbe", (), {"children": staticmethod(children),
                                     "alive": staticmethod(alive)})()


@pytest.fixture
def fake_binary(tmp_path):
    """Build stand-ins for a broken or unsuitable ``seqkit`` executable.

    Every variant is a real file the locator and the process layer have to cope
    with: a truncation of the shipped binary, a valid native image that is some
    other program, an empty file, plain text, a folder, and a path that does not
    exist.
    """
    real = None
    from seqkit_gui.core import seqkit_locator

    found = seqkit_locator.locate("")
    real = found.path if found.found else None

    class _Factory:
        def missing(self, name="nope.exe"):
            return tmp_path / name

        def zero_bytes(self, name="seqkit_zero.exe"):
            path = tmp_path / name
            path.write_bytes(b"")
            return path

        def text(self, name="seqkit_text.exe"):
            path = tmp_path / name
            path.write_bytes(b"This is not a program, it is a text file.\r\n")
            return path

        def truncated(self, name="seqkit_truncated.exe", keep=4096):
            """A download cut short: the DOS header is there, the image is not."""
            if real is None:
                return None
            path = tmp_path / name
            path.write_bytes(real.read_bytes()[:keep])
            return path

        def native_other(self, name="seqkit_other.exe"):
            """A genuine native executable that is not seqkit."""
            candidates = ([Path(r"C:\Windows\System32\where.exe"),
                           Path(r"C:\Windows\System32\ping.exe")]
                          if os.name == "nt" else
                          [Path(sys.executable), Path("/bin/echo")])
            for source in candidates:
                if source.is_file() and source.stat().st_size > 4096:
                    path = tmp_path / name
                    path.write_bytes(source.read_bytes())
                    path.chmod(0o755)
                    return path
            return None

        def directory(self, name="seqkit_dir.exe"):
            path = tmp_path / name
            path.mkdir(parents=True, exist_ok=True)
            return path

    return _Factory()


def write_records(path: Path, count: int, length: int = 1) -> Path:
    """Write ``count`` tiny FASTA records, each on its own lines.

    Deliberately cheap: 100 000 records of one base cost a few megabytes, which
    keeps the long-output tests honest without being a fixture the size of a
    genome. The whole text is a few megabytes, so one ``write_text`` is simpler
    than an open-and-loop and just as bounded.
    """
    parts: list[str] = []
    for index in range(count):
        parts.append(f">record{index} description\n")
        parts.append("A" * length + "\n")
    Path(path).write_text("".join(parts), encoding="utf-8", newline="\n")
    return path
