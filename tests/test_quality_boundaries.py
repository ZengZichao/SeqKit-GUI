"""Architecture rules that keep this application a shell around seqkit.

Each check here is a rule the project promises in its documentation and that a
convenient-looking shortcut would silently break:

* every child process is started by the process layer, from an argument list, so
  no code path can hand a command string to a shell;
* ``core/`` stays importable without a display, so the schema, the argument
  builder and the settings can be tested and reused without Qt widgets;
* nothing ships a version-history comment, because the source and the generated
  schema describe one supported seqkit release and nothing else.

The checks read source files rather than importing them, so they run on an
interpreter with only pytest installed.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "seqkit_gui"

#: Modules allowed to start a child process. ``core/runner.py`` runs seqkit itself
#: through QProcess; ``core/seqkit_locator.py`` runs one synchronous
#: ``seqkit --version`` probe, which cannot go through the asynchronous runner.
#: A new entry here means a new process boundary and needs a review.
PROCESS_ENTRY_POINTS = {"core/runner.py", "core/seqkit_locator.py"}

#: Words that turn a comment into a changelog. The source states what the code
#: does now; anything else belongs in git history. Present-tense UI wording is not
#: listed here ("a file no longer exists" describes this run, not a release).
HISTORY_MARKERS = (
    "TODO", "FIXME", "XXX", "HACK",
    "原先", "之前", "本次", "当前版本", "旧版", "以前", "历史遗留",
    "changed from", "previously", "used to be",
)


def app_modules() -> list[Path]:
    return sorted(APP.rglob("*.py"))


def tools_scripts() -> list[Path]:
    return sorted((ROOT / "tools").glob("*.py")) + sorted((ROOT / "packaging").glob("*.py"))


def imported_names(path: Path) -> dict[str, int]:
    """``{bound name: line}`` for every import statement in a module."""
    found: dict[str, int] = {}
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found[alias.asname or alias.name.split(".")[0]] = node.lineno
        elif isinstance(node, ast.ImportFrom):
            if node.module == "__future__":
                continue  # a compiler directive, never referenced as a name
            for alias in node.names:
                if alias.name == "*":
                    continue
                found[alias.asname or alias.name] = node.lineno
    return found


def referenced_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}


def source_of(path: Path) -> str:
    return path.read_text(encoding="utf-8")


#: Only code-shaped spellings count, so prose that names the module
#: (``core/seqkit_locator.py`` explains why it cannot use the runner) is not a false hit.
PROCESS_CODE = re.compile(
    r"import subprocess|subprocess\.[a-z_]+\(|Popen\(|os\.system\(|os\.popen\(|shell\s*=\s*True")
PROCESS_OBJECT = re.compile(r"QProcess\(")


# --------------------------------------------------------------------------- #
# process boundary
# --------------------------------------------------------------------------- #
def test_ui_code_never_starts_a_process_itself() -> None:
    """Every run goes through core.runner, so preview and execution cannot diverge."""
    offenders = []
    for path in (APP / "ui").glob("*.py"):
        for number, line in enumerate(source_of(path).splitlines(), 1):
            if PROCESS_CODE.search(line) and not line.lstrip().startswith("#"):
                offenders.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()}")
    assert offenders == [], f"ui/ would bypass core.runner: {offenders}"


def test_declared_process_entry_points_are_the_only_spawners() -> None:
    spawners = set()
    for path in app_modules():
        text = source_of(path)
        if PROCESS_CODE.search(text) or PROCESS_OBJECT.search(text):
            spawners.add(path.relative_to(APP).as_posix())
    assert spawners == PROCESS_ENTRY_POINTS, (
        f"child processes are started in {sorted(spawners)} but the reviewed set is "
        f"{sorted(PROCESS_ENTRY_POINTS)}; a second spawn site needs its own preflight"
    )


def test_no_shell_string_can_reach_a_child_process() -> None:
    """QProcess is driven by setProgram/setArguments, never by a command string."""
    offenders = []
    for path in app_modules():
        for number, line in enumerate(source_of(path).splitlines(), 1):
            if "shell=True" in line or re.search(r"\.start\(\s*f?[\"']", line):
                offenders.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()}")
    assert offenders == [], (
        f"a command string would be split by a shell/Qt parser: {offenders}")


# --------------------------------------------------------------------------- #
# layering
# --------------------------------------------------------------------------- #
def test_core_never_imports_qt_gui_or_widgets() -> None:
    """core/ must stay usable without a display server.

    QtCore alone is the rule: QProcess, QSettings, QTimer and the Qt:: enums live
    there and carry no widget or painting dependency. QtWidgets or QtGui would make
    the schema, the argument builder and the settings untestable headless.
    """
    offenders = []
    for path in (APP / "core").glob("*.py"):
        for number, line in enumerate(source_of(path).splitlines(), 1):
            match = re.search(r"from PySide6\.(Qt\w+) import|import PySide6\.(\w+)", line)
            if not match:
                continue
            module = match.group(1) or match.group(2)
            if module in {"QtWidgets", "QtGui"}:
                offenders.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()}")
    assert offenders == [], f"core/ would need a display: {offenders}"


# --------------------------------------------------------------------------- #
# imports
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("path", app_modules(),
                         ids=lambda path: path.relative_to(ROOT).as_posix())
def test_application_package_has_no_unused_imports(path: Path) -> None:
    """An unused import is a false dependency and a PyInstaller bundle entry.

    Only ``seqkit_gui/`` is scanned: it is what ships, and the recipe records it as
    imported code. ``tools/`` scripts run on a release machine only.
    """
    imports = imported_names(path)
    used = referenced_names(path)
    dead = [f"{path.relative_to(ROOT)}:{line}: {name}"
            for name, line in imports.items() if name not in used]
    assert dead == [], "\n".join(dead)


# --------------------------------------------------------------------------- #
# exceptions
# --------------------------------------------------------------------------- #
def test_no_bare_or_catch_all_except_in_the_application() -> None:
    """A swallowed error in the shell is a run that looks like it produced nothing."""
    offenders = []
    for path in app_modules():
        tree = ast.parse(source_of(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            if node.type is None:
                offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}: bare except")
                continue
            names = [ast.unparse(item) for item in (
                node.type.elts if isinstance(node.type, ast.Tuple) else [node.type])]
            if any(name in {"Exception", "BaseException"} for name in names):
                offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}: {names}")
    assert offenders == [], f"catch-all handlers hide seqkit failures: {offenders}"


# --------------------------------------------------------------------------- #
# comments that describe a version instead of the code
# --------------------------------------------------------------------------- #
def comments_and_docstrings(path: Path) -> list[tuple[int, str]]:
    """``(line, text)`` for every comment and every string literal in a module.

    ``tokenize`` is used rather than a per-line scan because a multi-line docstring
    has to be reported from the line its text really starts on.
    """
    source = source_of(path)
    out: list[tuple[int, str]] = []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type not in (tokenize.COMMENT, tokenize.STRING):
            continue
        for offset, line in enumerate(token.string.splitlines()):
            out.append((token.start[0] + offset, line))
    return out


def test_sources_carry_no_version_history_markers() -> None:
    """The tree describes one seqkit release; it does not describe how it got here.

    ``改为`` and ``不再`` are deliberately not on the marker list: they appear in
    translated seqkit flag descriptions, where they describe what the *tool* does.
    """
    offenders = []
    for path in app_modules() + tools_scripts():
        for number, text in comments_and_docstrings(path):
            for marker in HISTORY_MARKERS:
                if marker in text:
                    offenders.append(
                        f"{path.relative_to(ROOT)}:{number}: {marker} | {text.strip()[:80]}")
    assert offenders == [], (
        "these lines narrate a change rather than the current behaviour:\n  "
        + "\n  ".join(offenders))
