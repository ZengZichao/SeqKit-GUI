"""Release-time invariants: one version, one name, no seqkit in the bundle.

The project states the same few facts in several places -- the application
package, ``pyproject.toml``, the PyInstaller recipe, the generated command
schema, and the documentation. Nothing keeps them in step at write time, so this
file keeps them in step at test time.

Two rules shape what is asserted here:

* A disagreement between the source, the packaging metadata and the recipe is a
  defect: it decides what a user's installed bundle claims about itself.
* A disagreement with the documentation is reported by a separate test, so a
  prose edit and a version bump never look like the same failure.

It reads files as text and never imports the application, so it runs on an
interpreter with nothing installed but pytest -- which is how the CI
``consistency`` job uses it.
"""

from __future__ import annotations

import json
import re
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SEMVER = r"(\d+\.\d+\.\d+)"

INIT = "seqkit_gui/__init__.py"
PYPROJECT = "pyproject.toml"
SPEC = "packaging/seqkit_gui.spec"
FETCH = "tools/fetch_seqkit.py"
SCHEMA = "seqkit_gui/data/commands.json"

# The names seqkit_gui.core.paths.executable_names() would locate on any platform.
SEQKIT_BASENAMES = {"seqkit", "seqkit.exe", "seqkit.cmd", "seqkit.bat"}


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8", errors="replace")


def assigned(relative: str, name: str) -> str:
    """The string literal assigned to ``name`` at the top level of a file."""
    match = re.search(rf'^{name}\s*=\s*["\']([^"\']+)["\']', read(relative), re.MULTILINE)
    assert match is not None, f"{relative} no longer assigns a string literal to {name}"
    return match.group(1)


def pyproject_field(name: str) -> str:
    """A key of the ``[project]`` table, found without a TOML parser."""
    inside = False
    pattern = re.compile(rf'^{name}\s*=\s*["\']([^"\']+)["\']')
    for line in read(PYPROJECT).splitlines():
        if line.strip().startswith("["):
            inside = line.strip() == "[project]"
            continue
        if inside:
            match = pattern.match(line)
            if match:
                return match.group(1)
    raise AssertionError(f"{PYPROJECT}: no {name} = \"...\" inside the [project] table")


# ---------------------------------------------------------------------------
# source <-> packaging metadata <-> PyInstaller recipe
# ---------------------------------------------------------------------------
def test_package_version_is_the_pyproject_version() -> None:
    package = assigned(INIT, "__version__")
    metadata = pyproject_field("version")
    assert package == metadata, (
        f"seqkit_gui/__init__.py says {package!r} but {PYPROJECT} says {metadata!r}. "
        f"The package constant is what ends up inside the built bundle, and the "
        f"metadata is what a solver sees; change both to the same value."
    )


def test_recipe_has_no_version_of_its_own() -> None:
    spec = read(SPEC)
    literal = re.search(r'^VERSION\s*=\s*["\']' + SEMVER + r'["\']', spec, re.MULTILINE)
    assert literal is None, (
        f"{SPEC} hard-codes VERSION = {literal.group(0)!r}. The recipe reads "
        f"__version__ out of {INIT} instead, which is what stops a built bundle from "
        f"claiming a version its source never had."
    )
    assert re.search(r'^VERSION, PRODUCT_NAME = read_project_metadata\(\)', spec, re.MULTILINE), (
        f"{SPEC} must derive VERSION from {INIT} (see read_project_metadata) so the "
        f"bundle and the package can never disagree."
    )


def test_artifact_name_matches_the_distribution_name() -> None:
    artifact = assigned(SPEC, "APP_NAME")
    distribution = pyproject_field("name")
    normalised = artifact.lower().replace(" ", "-").replace("_", "-")
    assert normalised == distribution.lower().replace("_", "-"), (
        f"the built folder/executable is named {artifact!r} (from {SPEC}), which "
        f"normalises to {normalised!r}, while {PYPROJECT} calls the distribution "
        f"{distribution!r}. Docs and CI name artifacts after both."
    )


def test_recipe_run_with_stubs_produces_the_expected_build() -> None:
    """Execute the spec file against stand-ins and inspect what it would build.

    Running the recipe is the only way to test it without waiting on a real
    PyInstaller build: everything below is the spec's own logic, not a copy of it.
    """
    built = run_spec()

    analysis = built["Analysis"]
    collected = [str(entry[1]) for entry in analysis["datas"]]
    destinations = sorted({str(entry[0]).replace("\\", "/") for entry in analysis["datas"]})
    assert destinations == [".", "LICENSES", "seqkit_gui/assets", "seqkit_gui/data",
                            "seqkit_gui/i18n"], (
        f"the recipe carries {destinations}; the app resolves its resources under "
        f"seqkit_gui/data, seqkit_gui/i18n and seqkit_gui/assets (core/paths.py) and "
        f"conveys its licence texts under . and LICENSES, so a different spelling means "
        f"a bundle that starts with an empty command list or ships no licence text."
    )
    liced = [str(entry[1]).replace("\\", "/").rsplit("/", 1)[-1].lower()
             for entry in analysis["datas"]
             if str(entry[0]).replace("\\", "/") in (".", "LICENSES")]
    assert any(name.startswith("lgpl") for name in liced), (
        f"nothing conveying an LGPL option is collected ({liced}); the PySide6 wheels "
        f"ship no licence text of their own, so the bundle itself has to carry it"
    )
    for folder, sample in (("data", "commands.json"), ("i18n", "zh_CN.json"),
                          ("i18n", "en_US.json"), ("assets", "app.ico")):
        assert any((Path(source) / sample).is_file() for source in collected), (
            f"seqkit_gui/{folder} is collected but {sample} is not in it, so the "
            f"bundle would be missing it too"
        )

    assert "tkinter" in analysis["excludes"], (
        f"excludes = {analysis['excludes']!r}: tkinter must stay excluded, it is never "
        f"imported and a stray import would add Tk to a Qt application."
    )
    assert analysis["hiddenimports"] == [], (
        f"hiddenimports = {analysis['hiddenimports']!r}. The application imports "
        f"PySide6, its own package and the standard library only, with no dynamic "
        f"imports; a non-empty list means either that changed (and the recipe should "
        f"say why) or that an obsolete entry is still shipping code nobody uses."
    )

    exe = built["EXE"]
    assert exe["name"] == assigned(SPEC, "APP_NAME"), "the executable name is the artifact name"
    assert exe["console"] is False, (
        "the recipe must build a windowed executable; a console window behind the GUI "
        "is a Windows-only defect that only shows up in the shipped bundle."
    )
    icon = exe["icon"]
    if icon is not None:
        assert Path(icon).is_file(), f"the recipe passes icon={icon!r}, which does not exist"
        expected = "app.ico" if sys.platform == "win32" else "app.icns"
        assert Path(icon).name == expected, (
            f"icon must be {expected} on this platform (got {Path(icon).name!r}); "
            f"PyInstaller only converts other formats when Pillow is installed, and "
            f"a release machine that happens to lack Pillow would then fail the build."
        )
    assert built["COLLECT"]["name"] == exe["name"], (
        "the onedir folder and the executable inside it must share one name"
    )


def test_recipe_refuses_to_bundle_anything_from_bin() -> None:
    """The non-redistribution guard is armed, not decorative."""
    smuggled = str(ROOT / "bin" / "seqkit.exe")
    with pytest.raises(SystemExit) as raised:
        run_spec(extra_binaries=[(smuggled, smuggled, "BINARY")])
    message = " ".join(str(arg) for arg in raised.value.args)
    assert "bin" in message and "seqkit" in message.lower(), (
        f"the guard fired with an unhelpful message: {message!r}"
    )


# ---------------------------------------------------------------------------
# the seqkit release this GUI is built around
# ---------------------------------------------------------------------------
def test_supported_seqkit_version_agrees_everywhere_in_the_code() -> None:
    declared = assigned(INIT, "SEQKIT_SUPPORTED_VERSION")
    schema_version = json.loads(read(SCHEMA)).get("seqkit_version")
    fetcher = assigned(FETCH, "DEFAULT_VERSION")
    assert schema_version == declared, (
        f"{SCHEMA} was generated from seqkit {schema_version!r} while "
        f"{INIT} declares {declared!r} as the supported release. The forms would "
        f"offer parameters for one version and the version badge would warn about "
        f"users of the other; regenerate the schema or retarget the declaration."
    )
    assert fetcher == declared, (
        f"tools/fetch_seqkit.py installs {fetcher!r} by default but the interface "
        f"describes {declared!r}; the default download would trip the mismatch badge."
    )


def test_packaging_checker_accepts_the_tree_and_rejects_a_wrong_tag() -> None:
    script = ROOT / "packaging" / "check_version.py"
    assert script.is_file(), f"{script} is what the release workflow runs"
    ok = subprocess.run([sys.executable, str(script)], capture_output=True, text=True,
                        cwd=str(ROOT))
    assert ok.returncode == 0, (
        f"packaging/check_version.py disagrees with itself:\n{ok.stdout}\n{ok.stderr}"
    )
    wrong = subprocess.run([sys.executable, str(script), "--quiet", "--tag", "v0.0.0"],
                           capture_output=True, text=True, cwd=str(ROOT))
    assert wrong.returncode != 0, (
        "the checker accepted a tag that cannot match the declared version; the "
        "release workflow relies on it to stop a mis-tagged build."
    )


# ---------------------------------------------------------------------------
# seqkit stays out of the repository
# ---------------------------------------------------------------------------
def test_repository_tracks_no_seqkit_executable() -> None:
    try:
        tracked = subprocess.run(["git", "ls-files", "--", "bin"],
                                 capture_output=True, text=True, cwd=str(ROOT))
    except OSError:
        pytest.skip("git is not available, cannot list tracked files")
    assert tracked.returncode == 0, tracked.stderr
    assert tracked.stdout.strip() == "", (
        f"these files are tracked in git and would be redistributed with the source: "
        f"{tracked.stdout.strip()}"
    )


# ---------------------------------------------------------------------------
# documentation (separate from the code checks above on purpose)
# ---------------------------------------------------------------------------
def documentation_files() -> list[Path]:
    candidates = [ROOT / "README.md", ROOT / "README.en.md",
                  ROOT / "CONTRIBUTING.md", ROOT / "CONTRIBUTING.en.md"]
    candidates += sorted((ROOT / "docs").rglob("*.md"))
    return [path for path in candidates if path.is_file()]


def test_docs_do_not_claim_a_different_seqkit_version() -> None:
    """No prose file may name a 2.x.Y SeqKit release other than the supported one.

    Lines that fetch some other release deliberately (``--version 2.9.0`` as a
    worked example) are exempt; a plain statement about the version the interface
    describes is not.
    """
    expected = assigned(INIT, "SEQKIT_SUPPORTED_VERSION")
    token = re.compile(r"(?<![\d.])2\.\d+\.\d+(?![\d.])")
    stale = []
    for path in documentation_files():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for found in token.findall(line):
                if found == expected or "--version" in line:
                    continue
                stale.append(f"{path.relative_to(ROOT)}:{number}: {found} | {line.strip()[:90]}")
    assert not stale, (
        f"these lines name a SeqKit release other than the supported {expected}:\n  "
        + "\n  ".join(stale)
    )


def test_docs_do_not_claim_a_different_application_version() -> None:
    expected = assigned(INIT, "__version__")
    patterns = (
        re.compile(r"__version__\s*=\s*[\"']" + SEMVER + r"[\"']"),
        re.compile(r"(?i)seqkit gui\s+v?" + SEMVER),
    )
    stale = []
    for path in documentation_files():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for pattern in patterns:
                for found in pattern.findall(line):
                    if found != expected:
                        stale.append(
                            f"{path.relative_to(ROOT)}:{number}: {found} | {line.strip()[:90]}"
                        )
    assert not stale, (
        f"these lines state an application version other than {expected}:\n  "
        + "\n  ".join(stale)
    )


# ---------------------------------------------------------------------------
# the workflows themselves
# ---------------------------------------------------------------------------
def _stub_binaries():
    """A collected binary TOC shaped like a real PyInstaller run on this OS.

    The platform plugins are what the recipe's own guard looks for; the two
    GPL-only names are what its filter is supposed to remove.
    """
    import platform
    system = platform.system()
    plugins = {
        "Windows": ["qwindows.dll", "qoffscreen.dll", "qdirect2d.dll", "qminimal.dll"],
        "Darwin": ["libqcocoa.dylib"],
        "Linux": ["libqxcb.so", "libqminimal.so"],
    }.get(system, ["qoffscreen.so"])
    gpl_only = {
        "Windows": ["Qt6VirtualKeyboard.dll", "qtvirtualkeyboardplugin.dll"],
    }.get(system, [])
    toc = [(f"PySide6/plugins/platforms/{name}", f"/fake/stage/{name}", "BINARY")
           for name in plugins]
    toc += [(f"PySide6/{name}", f"/fake/stage/{name}", "BINARY") for name in gpl_only]
    return toc


def run_spec(extra_binaries=None):
    """Execute packaging/seqkit_gui.spec with stubbed build callables.

    Returns the keyword arguments each PyInstaller class was handed, so the test
    can assert what the recipe would produce without building it.

    ``extra_binaries=None`` stands for "a collected TOC a real run would produce":
    the recipe refuses to build a bundle with no Qt platform plugin, so an empty
    stub would fail that check for the wrong reason.
    """
    if extra_binaries is None:
        extra_binaries = _stub_binaries()
    recorded: dict = {}

    class Analysis:
        def __init__(self, scripts, pathex=(), binaries=(), datas=(), hiddenimports=(),
                     hookspath=(), hooksconfig=None, runtime_hooks=(), excludes=(),
                     noarchive=False):
            self.scripts = [(script, script, "SCRIPT") for script in scripts]
            self.binaries = list(binaries) + list(extra_binaries)
            self.datas = [(dest, source, "DATA") for source, dest in datas]
            self.pure = []
            # The recipe filters this list in place, so holding the object here lets
            # the test read the TOC as it stands after that filtering ran.
            recorded["binaries"] = self.binaries
            recorded["Analysis"] = {
                "scripts": list(scripts), "datas": list(self.datas),
                "hiddenimports": list(hiddenimports), "excludes": list(excludes),
            }

    class PYZ:
        def __init__(self, *args, **kwargs):
            pass

    class EXE:
        def __init__(self, *args, **kwargs):
            recorded["EXE"] = dict(kwargs)

    class COLLECT:
        def __init__(self, *args, **kwargs):
            recorded["COLLECT"] = dict(kwargs)

    namespace = {
        "SPECPATH": str(ROOT / "packaging"),
        "Analysis": Analysis,
        "PYZ": PYZ,
        "EXE": EXE,
        "COLLECT": COLLECT,
    }
    # runpy is the standard-library way to execute one script file in a prepared
    # namespace: it compiles and runs the recipe the same way PyInstaller does,
    # then hands back the globals the recipe went on to define.
    recipe_globals = runpy.run_path(str(SPEC), init_globals=namespace,
                                    run_name="<spec-under-test>")
    recorded["APP_NAME"] = recipe_globals["APP_NAME"]
    recorded["VERSION"] = recipe_globals["VERSION"]
    recorded["PRODUCT_NAME"] = recipe_globals["PRODUCT_NAME"]
    assert recorded["VERSION"] == assigned(INIT, "__version__"), (
        "the recipe resolved a version that is not the package's"
    )
    return recorded


def test_workflow_files_are_valid_and_stay_read_only() -> None:
    """GitHub Actions syntax plus the permissions and pinning this project promises.

    PyYAML is a CI-side tool, not an application dependency, so the check is
    skipped rather than failed where it is not installed; the ``consistency`` job
    installs it precisely so that this does not stay skipped there.
    """
    yaml = pytest.importorskip("yaml", reason="workflow files are only parsed when PyYAML is available")
    workflows = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
    assert workflows, ".github/workflows disappeared"

    pinned = re.compile(r"^[^@\s]+@([0-9a-f]{40})$")
    for path in workflows:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(document, dict), f"{path.name} did not parse to a mapping"
        relative = path.relative_to(ROOT)
        text = path.read_text(encoding="utf-8")

        assert document.get("permissions") == {"contents": "read"}, (
            f"{relative}: permissions must stay `contents: read`. This project's CI "
            f"reads the repository and uploads artifacts; nothing in it needs to write "
            f"to the repository, create a release, or touch a registry."
        )

        jobs = document["jobs"]
        assert jobs, f"{relative} declares no jobs"
        for job_id, job in jobs.items():
            assert job.get("timeout-minutes"), f"{relative}: job {job_id} needs a timeout"
            # A job may name its permissions or leave them out; what is not allowed is a
            # job that ends up holding more than read. GitHub applies the workflow-level
            # grant to every job that declares none, so both spellings of "read only" are
            # correct, and an explicit per-job `contents: read` is the same effective
            # privilege restated where a reader of that job alone can see it. Checking the
            # *value* rather than its *absence* is what keeps this honest: it still fails
            # any job that asks for write, and it no longer fails a workflow that spells
            # the inheritance out job by job.
            granted = job.get("permissions")
            if granted is not None:
                if isinstance(granted, str):
                    assert granted == "read-all", (
                        f"{relative}: job {job_id} sets permissions to the bare string "
                        f"{granted!r}; only `read-all` is acceptable"
                    )
                else:
                    assert isinstance(granted, dict), (
                        f"{relative}: job {job_id} permissions is neither a mapping nor "
                        f"a bare scope string"
                    )
                    over_reach = {
                        scope: level for scope, level in granted.items()
                        if level not in ("read", "none")
                    }
                    assert not over_reach, (
                        f"{relative}: job {job_id} grants {over_reach}; this project's CI "
                        f"reads the repository and uploads artifacts -- no job may hold a "
                        f"write or execute scope"
                    )
            for step in job["steps"]:
                uses = step.get("uses")
                if not uses:
                    continue
                assert pinned.match(uses), (
                    f"{relative} / {job_id}: action reference {uses!r} is not pinned to a "
                    f"full commit SHA. A floating tag (even a major version, and "
                    f"certainly @latest) can change what runs between two pushes."
                )
                # A comment is dropped when the file is parsed, so the pin's label is
                # checked against the source text.
                lines = [line for line in text.splitlines() if f"uses: {uses}" in line]
                assert lines and all("# v" in line for line in lines), (
                    f"{relative}: {uses!r} is pinned by SHA without a `# vN.N.N` label, "
                    f"which makes the next refresh of that pin impossible to review."
                )
        assert "@latest" not in text, f"{relative} references a floating @latest action"

    release_path = ROOT / ".github" / "workflows" / "release-build.yml"
    release_document = yaml.safe_load(release_path.read_text(encoding="utf-8"))
    # YAML 1.1 reads the `on:` key as the boolean True; accept either spelling.
    triggers = release_document.get("on", release_document.get(True))
    assert triggers.get("push", {}).get("tags") == ["v*"], (
        "release-build.yml is supposed to run on a version tag push and nothing else; "
        f"its trigger block reads {triggers}"
    )
    release = release_path.read_text(encoding="utf-8")
    assert "contents: write" not in release, (
        "release-build.yml must not ask for write permission: it produces an artifact, "
        "and attaching it to a release is a human decision with human wording."
    )
    for forbidden in ("gh release", "softprops/action-gh-release", "github-script"):
        assert forbidden not in release, (
            f"release-build.yml mentions {forbidden!r}; creating or editing a Release "
            f"from CI is deliberately out of scope here"
        )


def test_ci_matrix_and_declared_support_match() -> None:
    yaml = pytest.importorskip("yaml", reason="workflow files are only parsed when PyYAML is available")
    document = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml")
                              .read_text(encoding="utf-8"))
    matrix = document["jobs"]["test"]["strategy"]["matrix"]
    assert document["jobs"]["test"]["strategy"].get("fail-fast") is False, (
        "one platform's outage must not cancel the evidence from the other eight runs"
    )
    for runner in ("windows-latest", "macos-latest", "ubuntu-latest"):
        assert runner in matrix["os"], f"{runner} is not in the CI matrix"

    floor = pyproject_field("requires-python")
    declared = re.search(r">=\s*(\d+\.\d+)", floor)
    assert declared, f"{PYPROJECT} declares requires-python = {floor!r}, which is not a >= floor"
    assert declared.group(1) in matrix["python-version"], (
        f"{PYPROJECT} promises {floor!r} but the CI matrix runs "
        f"{matrix['python-version']!r}; the promised floor is never tested."
    )


# ---------------------------------------------------------------------------
# declared dependencies
# ---------------------------------------------------------------------------
def canonical(name: str) -> str:
    """A requirement name in the form PEP 503 compares it in."""
    return re.sub(r"[-_.]+", "-", name).lower()


def split_requirement(text: str) -> tuple[str, str]:
    """``(canonical name, specifier)`` of one requirement line, extras dropped."""
    match = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(\[[^\]]*\])?\s*(.*)", text)
    assert match, f"not a requirement line: {text!r}"
    return canonical(match.group(1)), match.group(3).strip()


def pyproject_dependencies() -> dict[str, str]:
    """The ``dependencies`` list of the ``[project]`` table, as name to specifier."""
    text = read(PYPROJECT)
    block = re.search(r"dependencies\s*=\s*\[(.*?)\]", text, re.DOTALL)
    assert block, f"{PYPROJECT}: no dependencies = [...] list found"
    out = {}
    for item in re.findall(r'["\']([^"\']+)["\']', block.group(1)):
        name, specifier = split_requirement(item)
        out[name] = specifier
    return out


def requirements_txt() -> dict[str, str]:
    """The uncommented, non-continuation lines of ``requirements.txt``."""
    out = {}
    for line in read("requirements.txt").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("-"):
            continue
        name, specifier = split_requirement(stripped)
        out[name] = specifier
    return out


def test_requirements_file_and_project_metadata_declare_the_same_things() -> None:
    """``pip install -r requirements.txt`` and ``pip install .`` install one set.

    The two lists are written by hand and read by different people -- the docs tell one
    group to use the file, the packaging metadata tells the other to use the project --
    so a version range that drifts between them means a user installs a build the tests
    never ran against.
    """
    declared = pyproject_dependencies()
    pinned = requirements_txt()
    assert declared, f"{PYPROJECT} declares no runtime dependencies at all"
    assert pinned, "requirements.txt declares no runtime dependencies at all"
    assert set(pinned) == set(declared), (
        f"requirements.txt covers {sorted(pinned)} while the project metadata covers "
        f"{sorted(declared)}")
    for name in sorted(declared):
        assert pinned[name] == declared[name], (
            f"{name}: requirements.txt says {pinned[name]!r}, "
            f"{PYPROJECT} says {declared[name]!r}")


def imported_names(path: Path) -> list[tuple[str, int]]:
    """``(top-level module, line)`` for every absolute import in one file."""
    import ast

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            # A relative import lives inside this project; ``from . import x`` has no
            # module name at all.
            names = [node.module] if node.level == 0 and node.module else []
        else:
            continue
        out.extend((name.split(".")[0], node.lineno) for name in names if name)
    return out


#: Standard library from 3.11 on, so a ``try: import tomllib`` fallback is not a package.
LATER_STDLIB = {"tomllib"}

#: Repository tooling that is never shipped to a user: pytest for the suite, PyYAML for
#: the workflow checks, ``tomli`` for a TOML read on an interpreter older than 3.11, and
#: the two names the packaging recipe pulls in.
TOOLING = {"pytest", "yaml", "tomli", "PyInstaller", "pyinstaller"}


def test_the_shipped_code_imports_only_what_the_metadata_declares() -> None:
    """An import of the application that is not in the metadata fails on a user's machine.

    Only ``seqkit_gui`` and the packaging entry point are scanned: they are what a bundle
    carries, so what they import is exactly what ``pip install`` has to provide. Names are
    told apart from the standard library by ``sys.stdlib_module_names`` rather than by a
    list that goes stale.
    """
    allowed = set(map(canonical,
                      list(pyproject_dependencies()) + ["seqkit_gui", "packaging"]))
    allowed |= LATER_STDLIB
    offenders = {}
    for directory in ("seqkit_gui", "packaging"):
        for path in sorted((ROOT / directory).rglob("*.py")):
            if "_build" in path.parts or "__pycache__" in path.parts:
                continue
            for name, line in imported_names(path):
                if name in sys.stdlib_module_names or canonical(name) in allowed:
                    continue
                offenders.setdefault(name, []).append(
                    f"{path.relative_to(ROOT).as_posix()}:{line}")
    assert offenders == {}, (
        "imported by the shipped code without being declared in "
        f"{PYPROJECT} or requirements.txt: "
        + "; ".join(f"{name} at {where[0]}" for name, where in sorted(offenders.items())))


def test_the_repository_tools_import_only_tooling_or_the_standard_library() -> None:
    """``tools/`` runs in CI and on a maintainer's box, never inside a user's bundle.

    Its imports are held to the standard library plus a named set of tooling, so a new
    dependency there is a decision somebody writes down in ``requirements.txt``'s optional
    section instead of an outage in a workflow forty minutes later.
    """
    allowed = set(map(canonical,
                      list(pyproject_dependencies()) + ["seqkit_gui", "tools"]
                      + list(TOOLING)))
    allowed |= LATER_STDLIB
    offenders = {}
    for path in sorted((ROOT / "tools").rglob("*.py")):
        if "_build" in path.parts or "__pycache__" in path.parts:
            continue
        for name, line in imported_names(path):
            # Requirement names compare in PEP 503 form, exactly as in
            # ``test_the_shipped_code_imports_only_what_the_metadata_declares``:
            # ``PySide6`` and ``pyside6`` are one dependency, and comparing the
            # raw spelling would let a declared import fail the survey.
            if name in sys.stdlib_module_names or canonical(name) in allowed:
                continue
            offenders.setdefault(name, []).append(
                f"{path.relative_to(ROOT).as_posix()}:{line}")
    assert offenders == {}, (
        f"imported by a repository tool without being named as tooling: "
        + "; ".join(f"{name} at {where[0]}" for name, where in sorted(offenders.items())))


def test_the_code_is_writable_on_the_python_the_metadata_declares() -> None:
    """``requires-python`` is a promise about syntax, and the cheap half of it is checkable.

    Every module is parsed on the interpreter running the tests, so anything newer than
    this interpreter's grammar -- a ``type`` statement, ``except*`` -- fails here before
    it fails on a user's machine. What a floor below 3.10 additionally demands is
    deferred annotations wherever a ``X | Y`` union is written, because that union is
    only a runtime object from 3.10 on; both halves are asserted per file.
    """
    import ast

    floor = re.search(r">=\s*(\d+)\.(\d+)", pyproject_field("requires-python"))
    assert floor, "requires-python does not declare a >= floor"
    wanted = (int(floor.group(1)), int(floor.group(2)))
    assert sys.version_info[:2] >= wanted, (
        f"this run happens on {sys.version_info[0]}.{sys.version_info[1]}, which is below "
        f"the declared floor {wanted[0]}.{wanted[1]}; nothing here proves the floor works")

    scanned = 0
    for directory in ("seqkit_gui", "tools", "packaging"):
        for path in sorted((ROOT / directory).rglob("*.py")):
            if "_build" in path.parts or "__pycache__" in path.parts:
                continue
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))       # a SyntaxError is the failure
            scanned += 1
            if wanted >= (3, 10):
                continue
            deferred = any(isinstance(node, ast.ImportFrom) and node.module == "__future__"
                           and any(alias.name == "annotations" for alias in node.names)
                           for node in tree.body)
            unions = [node for node in ast.walk(tree)
                      if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr)
                      and isinstance(node.left, (ast.Name, ast.Subscript))
                      and isinstance(node.right, (ast.Name, ast.Subscript, ast.Constant))]
            if unions and not deferred:
                raise AssertionError(
                    f"{path.relative_to(ROOT).as_posix()} writes {unions[0].lineno}: X | Y "
                    f"without deferring annotations, which {wanted[0]}.{wanted[1]} cannot "
                    "evaluate at runtime")
    assert scanned > 20, f"only {scanned} modules were scanned"
