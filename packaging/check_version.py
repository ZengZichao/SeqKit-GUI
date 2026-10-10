#!/usr/bin/env python3
"""Reconcile every version and name the packaging pipeline declares.

The project states the same handful of facts in four places: the application
package, the packaging metadata, the PyInstaller recipe and the generated
command schema. This script reads them all without importing anything, so it
runs on a bare interpreter on a build machine before the dependencies are
installed::

    python packaging/check_version.py                 # inspect the tree
    python packaging/check_version.py --tag v1.0.0    # plus: a tag matches
    python packaging/check_version.py --quiet         # only the disagreements
    python packaging/check_version.py --get app-version    # one bare token

Exit code 0 when everything agrees, 1 with one line per disagreement, 2 when a
declaration cannot be read at all. Used by
``.github/workflows/release-build.yml`` -- a tag push must never produce a
bundle whose embedded version differs from the tag it was cut from -- and by
``.github/workflows/ci.yml`` as a cheap pre-test gate. Standard library only,
and it never touches the network.

``--get`` is how the workflows read a declaration. A name or version printed
here has already passed the shape checks below, so a workflow can put it into a
file name or a download URL without repeating the regular expression that
guards it; the alternative, an inline ``re.search`` in a ``run:`` block, is one
place per workflow where a bad value reaches a shell before anything notices.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SEMVER = r"(\d+\.\d+\.\d+)"

CI_WORKFLOW = ".github/workflows/ci.yml"
RELEASE_WORKFLOW = ".github/workflows/release-build.yml"

#: Labels accepted by ``--get``, mapped to the key of :func:`collect` they print.
GETTABLE = {
    "app-version": "seqkit_gui.__version__",
    "seqkit-version": "commands.json.seqkit_version",
    "app-name": "seqkit_gui.APP_NAME",
    "artifact-stem": "spec.APP_NAME",
    "build-python": "release_build.python_version",
}

#: ``seqkit_gui/core/paths.py`` :func:`executable_names` -- none of these names may
#: ever be produced by this repository, let alone shipped inside a bundle.
SEQKIT_NAMES = {"seqkit", "seqkit.exe", "seqkit.cmd", "seqkit.bat"}

#: Folders ``packaging/seqkit_gui.spec`` copies into ``_internal/seqkit_gui/``, and
#: the files inside them that the built application cannot start without. Absence
#: is checked here, at the front of the release job, because a missing resource
#: costs a full build to discover otherwise.
BUNDLE_RESOURCES = (
    "seqkit_gui/data/commands.json",
    "seqkit_gui/i18n/zh_CN.json",
    "seqkit_gui/i18n/en_US.json",
    "seqkit_gui/assets/app.ico",
)


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8", errors="replace")


def _first(pattern: str, relative: str, label: str) -> str:
    """One capture group from the first line matching ``pattern``."""
    match = re.search(pattern, _text(relative), re.MULTILINE)
    if match is None:
        raise LookupError(f"{relative}: no {label} (expected {pattern!r})")
    return match.group(1)


def collect() -> dict:
    """Every declared version/name this project cares about, keyed by label."""
    init = "seqkit_gui/__init__.py"
    spec = "packaging/seqkit_gui.spec"
    values = {
        "seqkit_gui.__version__": _first(r'^__version__\s*=\s*["\']' + SEMVER + r'["\']',
                                        init, "__version__"),
        "seqkit_gui.APP_NAME": _first(r'^APP_NAME\s*=\s*["\']([^"\']+)["\']',
                                      init, "APP_NAME"),
        "seqkit_gui.SEQKIT_SUPPORTED_VERSION": _first(
            r'^SEQKIT_SUPPORTED_VERSION\s*=\s*["\']' + SEMVER + r'["\']',
            init, "SEQKIT_SUPPORTED_VERSION"),
        "pyproject.version": _first(r'^version\s*=\s*["\']' + SEMVER + r'["\']',
                                    "pyproject.toml", "project version"),
        "pyproject.name": _first(r'^name\s*=\s*["\']([^"\']+)["\']',
                                 "pyproject.toml", "project name"),
        "spec.APP_NAME": _first(r'^APP_NAME\s*=\s*["\']([^"\']+)["\']',
                                spec, "APP_NAME"),
        "commands.json.seqkit_version": json.loads(_text("seqkit_gui/data/commands.json"))
                                        .get("seqkit_version", ""),
        "fetch_seqkit.DEFAULT_VERSION": _first(r'^DEFAULT_VERSION\s*=\s*["\']' + SEMVER + r'["\']',
                                               "tools/fetch_seqkit.py", "DEFAULT_VERSION"),
        # What the packaging layer promises a user, as opposed to what it claims:
        # the interpreter the release bundle is built with, and the floor the
        # metadata advertises.
        "pyproject.requires_python": _first(r'^requires-python\s*=\s*["\']>?=\s*(\d+\.\d+)',
                                            "pyproject.toml", "requires-python floor"),
        "release_build.python_version": _first(r"python-version:\s*[\"'](\d+\.\d+)[\"']",
                                               RELEASE_WORKFLOW, "pinned build interpreter"),
        "ci_matrix.python_versions": _first(r"python-version:\s*\[([0-9'\"., ]+)\]",
                                            CI_WORKFLOW,
                                            "the flow-style python-version matrix list "
                                            "(a block-style list needs this reader to "
                                            "grow a YAML parser)"),
    }
    return values


def _as_tuple(text: str) -> tuple:
    """``"3.12"`` -> ``(3, 12)`` so version floors compare numerically, not as text."""
    return tuple(int(part) for part in text.split("."))


def _matrix_python_versions(raw: str) -> list:
    """The quoted entries of a flow-style ``python-version: ['3.10', ...]`` list."""
    out = []
    for item in raw.split(","):
        cleaned = item.strip().strip("'\"")
        if re.fullmatch(r"\d+\.\d+", cleaned):
            out.append(cleaned)
    return out


def bundle_contents() -> list:
    """What the recipe collects, checked before a build spends its time on it.

    ``packaging/seqkit_gui.spec`` treats ``i18n`` and ``assets`` as optional and
    prints a notice when one is absent, which is right for a partial checkout and
    wrong for a release: a bundle without the language tables is an interface that
    lost half of its users, and one without ``data/commands.json`` exits 2 on
    start-up.
    """
    problems = []
    for relative in BUNDLE_RESOURCES:
        path = ROOT / relative
        if not path.is_file():
            problems.append(f"{relative} is missing; the bundle would not contain it.")
        elif path.stat().st_size == 0:
            problems.append(f"{relative} is empty; the bundle would ship an empty file.")

    # seqkit is upstream software and is not redistributed. The recipe refuses to
    # collect anything from bin/, and these three folders are the only others it
    # copies wholesale, so a binary planted in one of them is how it could slip in.
    for relative in ("seqkit_gui/data", "seqkit_gui/i18n", "seqkit_gui/assets"):
        directory = ROOT / relative
        if not directory.is_dir():
            continue
        for stray in sorted(directory.rglob("*")):
            if stray.is_file() and stray.name.lower() in SEQKIT_NAMES:
                problems.append(
                    f"{stray.relative_to(ROOT)} would be collected into the bundle; "
                    f"seqkit is not redistributed with this GUI."
                )
    return problems


def compare(values: dict, tag: str | None) -> list:
    """Human-readable disagreements between the declared values."""
    problems = []

    if values["seqkit_gui.__version__"] != values["pyproject.version"]:
        problems.append(
            f"application version differs: seqkit_gui/__init__.py says "
            f"{values['seqkit_gui.__version__']!r}, pyproject.toml says "
            f"{values['pyproject.version']!r} -- pick one and make the other match it "
            f"(the package is the source of truth for the built bundle)."
        )

    # The artifact folder/executable name comes from the spec; the distribution
    # name comes from pyproject. They must be the same words, only spelled for
    # the filesystem instead of for PyPI.
    from_spec = values["spec.APP_NAME"].lower().replace(" ", "-").replace("_", "-")
    from_pyproject = values["pyproject.name"].lower().replace("_", "-")
    if from_spec != from_pyproject:
        problems.append(
            f"artifact name differs: packaging/seqkit_gui.spec APP_NAME="
            f"{values['spec.APP_NAME']!r} normalises to {from_spec!r}, but "
            f"pyproject.toml name is {values['pyproject.name']!r}."
        )

    for label in ("seqkit_gui.SEQKIT_SUPPORTED_VERSION", "fetch_seqkit.DEFAULT_VERSION"):
        if values[label] != values["commands.json.seqkit_version"]:
            problems.append(
                f"SeqKit version differs: {label} = {values[label]!r} but the generated "
                f"schema seqkit_gui/data/commands.json records "
                f"{values['commands.json.seqkit_version']!r}. Either retarget the tooling "
                f"to the schema's release or regenerate the schema."
            )

    # A spec that carries its own version string drifts from the package the
    # moment either one is bumped; the recipe reads it out of __init__.py instead.
    if re.search(r'^VERSION\s*=\s*["\']', _text("packaging/seqkit_gui.spec"), re.MULTILINE):
        problems.append(
            "packaging/seqkit_gui.spec assigns a literal VERSION; it must read "
            "__version__ from seqkit_gui/__init__.py so the bundle can never disagree "
            "with the source it was built from."
        )

    # The spec that names the built folder and executable is a filesystem name: a
    # space or a slash in it lands in a path the release workflow then globs for.
    artifact = values["spec.APP_NAME"]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", artifact):
        problems.append(
            f"packaging/seqkit_gui.spec APP_NAME = {artifact!r} is not a usable file or "
            f"folder name: only letters, digits, dot, underscore and hyphen are allowed, "
            f"starting with a letter. It becomes dist/<name>/<name>.exe and the artifact "
            f"file name."
        )
    # Two spellings of one product name: the display string the window shows and the
    # hyphenated name the bundle carries. Same words, or a user cannot tell that
    # SeqKit-GUI/ is the folder SeqKit GUI opened.
    from_display = values["seqkit_gui.APP_NAME"].lower().replace(" ", "-").replace("_", "-")
    if from_display != from_spec:
        problems.append(
            f"product name differs: seqkit_gui/__init__.py APP_NAME = "
            f"{values['seqkit_gui.APP_NAME']!r} normalises to {from_display!r}, but "
            f"packaging/seqkit_gui.spec APP_NAME = {artifact!r} normalises to "
            f"{from_spec!r}. Documentation and the Settings dialog name the folder the "
            f"user is told to put seqkit in."
        )

    # A bundle built with an interpreter this repository never tested is a claim the
    # test matrix does not back up.
    build_python = values["release_build.python_version"]
    floor = values["pyproject.requires_python"]
    if _as_tuple(build_python) < _as_tuple(floor):
        problems.append(
            f"the release bundle is built with Python {build_python}, below the "
            f"{floor!r} floor pyproject.toml declares. The artifact would carry a "
            f"runtime the metadata says is unsupported."
        )
    tested = _matrix_python_versions(values["ci_matrix.python_versions"])
    if tested and build_python not in tested:
        problems.append(
            f"the release bundle is built with Python {build_python}, which is not in "
            f"the CI matrix {tested}. Whatever ships has never run the suite it is "
            f"supposed to have passed."
        )

    if tag is not None:
        cleaned = tag.strip()
        if cleaned.startswith("refs/tags/"):
            cleaned = cleaned[len("refs/tags/"):]
        if not cleaned.startswith("v"):
            problems.append(
                f"tag {tag!r} does not start with 'v'; this repository tags releases as "
                f"v<major>.<minor>.<patch> (for example v{values['seqkit_gui.__version__']})."
            )
        elif cleaned[1:] != values["seqkit_gui.__version__"]:
            problems.append(
                f"tag {cleaned!r} does not match the application version "
                f"{values['seqkit_gui.__version__']!r} declared in seqkit_gui/__init__.py. "
                f"Bump the version in the source, merge it, and only then tag."
            )

    return problems


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check_version",
        description="Fail if the version or name declared in one file disagrees with another.",
    )
    parser.add_argument("--tag", default=None,
                        help="release tag to reconcile against seqkit_gui.__version__ "
                             "(with or without the refs/tags/ prefix)")
    parser.add_argument("--quiet", action="store_true",
                        help="print only disagreements, not the table of values")
    parser.add_argument("--get", choices=tuple(sorted(GETTABLE)), default=None,
                        help="print exactly one declaration, as a bare token, and nothing "
                             "else. The tree is reconciled first: a disagreement is a "
                             "non-zero exit rather than a value a workflow would name an "
                             "artifact after.")
    args = parser.parse_args(argv)

    try:
        values = collect()
    except (OSError, LookupError, ValueError, json.JSONDecodeError) as error:
        print(f"error: could not read the declarations: {error}", file=sys.stderr)
        return 2

    problems = compare(values, args.tag) + bundle_contents()

    if args.get:
        for problem in problems:
            print(f"MISMATCH: {problem}", file=sys.stderr)
        if problems:
            return 1
        print(values[GETTABLE[args.get]])
        return 0

    if not args.quiet:
        print("declared values:")
        for label in sorted(values):
            print(f"  {label:42s} = {values[label]!r}")
        if args.tag:
            print(f"  {'tag':42s} = {args.tag!r}")
        for relative in BUNDLE_RESOURCES:
            path = ROOT / relative
            size = path.stat().st_size if path.is_file() else None
            print(f"  {'bundle resource ' + relative:42s} = {size!r} bytes")

    for problem in problems:
        print(f"MISMATCH: {problem}", file=sys.stderr)
    if problems:
        print(f"{len(problems)} disagreement(s) found", file=sys.stderr)
        return 1

    print("all declarations agree" + (f" with tag {args.tag}" if args.tag else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
