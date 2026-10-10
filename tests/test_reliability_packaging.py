"""The packaging and platform declarations a user's machine actually has to satisfy.

These are the four statements the project makes about *its environment* rather than
about seqkit: what Python it needs, what third-party package it pulls in, what has to
travel inside the wheel, and what the locator claims about a binary it found. Each one
is asserted against the repository as it sits on disk, so a change to one file without
the matching change to the other shows up here instead of on a user's machine.

Nothing in this file needs the network, a display, seqkit, or a second interpreter.
It reads declarations and compares them to the tree, which is what makes it safe to run
on every CI backend and to leave on by default.
"""

import ast
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _pyproject() -> dict:
    """Parse ``pyproject.toml`` with the stdlib parser, else ``tomli``, else skip.

    ``tomllib`` is 3.11+; the declared floor is 3.10, so the fallback is not decoration
    here -- it is the same path ``tools/license_check.py`` takes.
    """
    try:
        import tomllib  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ModuleNotFoundError:
            pytest.skip("no TOML parser: neither stdlib tomllib (3.11+) nor tomli is installed")
    with open(ROOT / "pyproject.toml", "rb") as handle:
        return tomllib.load(handle)


def _requirement_lines() -> list[str]:
    """Uncommented, non-empty lines of ``requirements.txt``, lower-cased."""
    lines = []
    for raw in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        text = raw.strip()
        if not text or text.startswith("#"):
            continue
        lines.append(text)
    return lines


def test_the_two_dependency_declarations_are_equivalent():
    """``requirements.txt`` and ``pyproject.toml`` must name the same range.

    These are the two ways a user installs the app -- ``pip install -r requirements.txt``
    from a clone, and ``pip install .`` from the metadata. A range that only lives in one
    of them means one of those two routes installs a PySide6 the other route never tested,
    and the API the interface happens to use is the thing that breaks first.
    """
    declared = _requirement_lines()
    assert declared, "requirements.txt holds nothing but comments"
    project = _pyproject()["project"]

    def split(name_and_spec: str) -> tuple[str, str]:
        match = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)\s*(.*)$", name_and_spec.strip())
        assert match, f"unparseable requirement: {name_and_spec!r}"
        return match.group(1).lower().replace("_", "-"), match.group(2).strip()

    from_file = dict(split(item) for item in declared)
    from_meta = dict(split(item) for item in project["dependencies"])
    assert from_file == from_meta, (
        f"requirements.txt says {from_file} but pyproject.toml says {from_meta}; "
        "the two install routes must not diverge")

    # The one runtime dependency is Qt, and it is bounded on both sides: an unbounded
    # `PySide6>=x` lets a future major release break the bindings under a running app.
    pyside = from_meta.get("pyside6")
    assert pyside is not None, "PySide6 is not declared as a runtime dependency"
    assert ">=" in pyside and "<" in pyside, (
        f"PySide6 needs both a floor and a major-version ceiling, got {pyside!r}")


def test_requires_python_is_a_floor_the_tree_can_be_parsed_at():
    """The declared minimum has to be a version this code really runs on.

    ``ast.parse(..., feature_version=...)`` applies that version's grammar, so a file
    using newer syntax raises here instead of on a user's older interpreter. The test
    asserts the direction that can be proved from the tree: nothing in ``seqkit_gui`` is
    newer than the floor it declares, and the floor is not above the interpreter the
    suite actually exercises (a floor of 3.12 would be a promise nobody here has kept).

    Measured, not assumed: the interface does write PEP 604 unions such as
    ``-> Path | None``, but every module that does also carries
    ``from __future__ import annotations``, which postpones evaluation -- so the unions
    are not by themselves a 3.10 requirement, and this test deliberately does not claim
    they are. The floor 3.10 is the oldest interpreter the project has actually been run
    on, which is what ``>=`` is for.
    """
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'requires-python\s*=\s*">=\s*(\d+)\.(\d+)"', text)
    assert match, f"requires-python missing or oddly spelled: {text[:300]}"
    floor = (int(match.group(1)), int(match.group(2)))

    assert floor >= (3, 9), (
        f"requires-python {floor[0]}.{floor[1]} is below the 3.9 spelling the app's own "
        "dict-merging and builtin generics need")
    assert floor <= sys.version_info[:2], (
        f"requires-python declares {floor} but this run is {sys.version_info[:2]}: the "
        "declared floor is newer than anything the suite has evidence for")

    sources = sorted((ROOT / "seqkit_gui").rglob("*.py"))
    assert sources, "no sources found"
    late_union = []
    for path in sources:
        source = path.read_text(encoding="utf-8")
        try:
            ast.parse(source, filename=str(path), feature_version=floor)
        except SyntaxError as error:
            raise AssertionError(
                f"{path.relative_to(ROOT).as_posix()} uses syntax newer than the declared "
                f"floor {floor[0]}.{floor[1]}: {error}") from error
        if re.search(r"->\s*[A-Za-z_][\w.]*\s*\|\s*[A-Za-z_]", source):
            late_union.append(path.name)
    assert late_union, (
        "no PEP 604 unions found at all; if the annotations changed, revisit what the "
        "floor is supposed to protect")
    postponed = [
        path.name for path in sources
        if "from __future__ import annotations" in path.read_text(encoding="utf-8")]
    assert set(late_union) <= set(postponed), (
        f"{sorted(set(late_union) - set(postponed))} use `X | Y` in an annotation without "
        "postponed evaluation, which needs the floor to be 3.10 and not lower")


def test_the_package_metadata_ships_every_resource_the_app_reads():
    """An installed copy has to start *and* find its catalogue: the wheel needs the JSON.

    ``pip install .`` fails twice over without this -- flat-layout auto-discovery aborts
    on ``bin/ docs/ packaging/ tests/ tools/`` sitting at the top level, and neither
    ``data/`` nor ``i18n/`` is a Python package, so without declared package data an
    installed app imports cleanly and then shows an empty command list.
    """
    config = _pyproject()
    project = config["project"]
    tool = config.get("tool", {})

    # The PEP 621 table form, not the PEP 639 bare string: the SPDX one-liner is only
    # understood by setuptools >= 77 and raises
    #   configuration error: `project.license` must be valid exactly by one definition
    # on the 68.x frontend this project is built with, taking `pip install .` down with it.
    license_value = project.get("license")
    assert isinstance(license_value, str) or isinstance(license_value, dict), license_value
    if isinstance(license_value, dict):
        assert set(license_value) == {"text"}, f"unexpected license table: {license_value}"
    else:
        pytest.skip("license is the PEP 639 string form, which needs setuptools>=77 to build")

    assert "packages" in tool.get("setuptools", {}) or \
        "packages" in tool.get("setuptools", {}).get("find", {}), \
        "no explicit package discovery: auto-discovery aborts on this flat layout"

    found = tool["setuptools"]["packages"]["find"]
    assert found.get("include") == ["seqkit_gui*"], (
        f"package discovery is {found}; it must name the one importable package")
    discovered = [p.parent.name for p in (ROOT / "seqkit_gui").glob("*/__init__.py")]
    for subpackage in discovered:
        assert subpackage in {"core", "ui"}, f"unexpected subpackage {subpackage}"

    data = tool["setuptools"].get("package-data", {}).get("seqkit_gui", [])
    # Every non-Python file inside the package is something the app reads at runtime --
    # the command table, the catalogues, the window icon -- and none of them is picked up
    # unless a glob names it. Built from the tree, not from a list written here, so adding
    # a resource without declaring it is what fails.
    resources = sorted(
        p.relative_to(ROOT / "seqkit_gui").as_posix()
        for p in (ROOT / "seqkit_gui").rglob("*")
        if p.is_file() and p.suffix != ".py" and "__pycache__" not in p.parts)
    assert resources, "the package holds no runtime resource, which cannot be right"

    def covered(resource: str) -> bool:
        import fnmatch
        return any(fnmatch.fnmatch(resource, glob) for glob in data)

    missed = [item for item in resources if not covered(item)]
    assert not missed, (
        f"seqkit_gui/{missed} exists but no package-data glob ships it "
        f"(declared: {data}); an installed copy would run without it")

    # And the glob must not be so broad that it also ships the source tree's own tests.
    for glob in data:
        assert not glob.startswith(".."), f"package-data escapes the package: {glob}"


def test_a_bundled_copy_is_still_bounded_by_the_version_probe(tmp_path, monkeypatch):
    """A native file that is not seqkit is refused before anything can run it.

    ``looks_like_seqkit`` is the classifier that tells seqkit's ``version`` output
    from some other program's. ``_runnable`` only reads a native image header, so a
    foreign binary renamed ``seqkit`` clears it; what bounds the search is ``locate()``
    putting every discovered candidate through the classifier, because otherwise that
    impostor is handed all 41 commands in the interface.
    """
    from seqkit_gui.core import paths, seqkit_locator

    assert not seqkit_locator.looks_like_seqkit("where: could not find files")
    assert seqkit_locator.looks_like_seqkit("seqkit v2.14.0 867f2c5")

    caller = getattr(seqkit_locator, "_acceptance", None)
    source = (ROOT / "seqkit_gui" / "core" / "seqkit_locator.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    used = [node.lineno for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(getattr(node, "func", None), ast.Name)
            and node.func.id == "looks_like_seqkit"]
    assert used, (
        "locate() has to put every discovered candidate through looks_like_seqkit; "
        "without it a renamed foreign binary is accepted on its file header alone")
    assert caller is not None and seqkit_locator._runnable(Path(sys.executable)) in (True, False)

    nowhere = tmp_path / "nowhere"
    nowhere.mkdir()
    monkeypatch.setattr(paths, "bundled_dir", lambda: nowhere)
    monkeypatch.setattr(paths, "project_root", lambda: nowhere)
    monkeypatch.setattr(seqkit_locator, "_DARWIN_PREFIXES", (str(nowhere / "opt"),))
    monkeypatch.setattr(seqkit_locator.shutil, "which", lambda name: None)
    monkeypatch.setattr(seqkit_locator, "probe_version",
                        lambda path, timeout=4.0: "2.0.0  unrelated tool reporting a number")

    impostor = tmp_path / "onpath"
    impostor.mkdir()
    planted = impostor / paths.executable_names()[0]
    planted.write_bytes(Path(sys.executable).read_bytes())
    if os.name != "nt":
        planted.chmod(0o755)
    monkeypatch.setenv("PATH", str(impostor))

    found = seqkit_locator.locate("")
    assert not found.found, (
        f"{planted} was accepted as seqkit without its version text being read")
    assert "version" in found.detail, (
        f"the refusal has to name the check that failed, got {found.detail!r}")
