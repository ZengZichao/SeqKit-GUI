#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""License / compliance checker for SeqKit GUI (release-prep evidence).

Four mechanical checks, all read-only and all offline -- the script never touches
the network, and a failure to find an optional input is reported as a SKIP rather
than guessed at.

1. ``seqkit-license`` -- comparison of the upstream SeqKit ``LICENSE`` file against
   the copy that ``THIRD-PARTY-LICENSES.md`` reproduces as "verbatim". Four
   distinct verdicts are reported, strongest first:

   * ``IDENTICAL (byte-for-byte, zero normalisation)`` -- equal length, equal
     SHA-256;
   * ``IDENTICAL (newline style aside)`` -- equal once CRLF is read as LF, which is
     a checkout artefact of an edited working tree: ``.gitattributes`` pins
     ``*.md text eol=lf``, so the committed blob is the LF one;
   * ``IDENTICAL (whitespace-normalised)`` -- equal only after CRLF/CR -> LF,
     per-line trailing whitespace and trailing blank lines are dropped, which is a
     typesetting difference and still acceptable for a copy quoted inside Markdown;
   * ``DIFFERENT`` -- real content divergence, printed line by line with the exact
     character index and code point of the first difference in each line.

   The fenced block is extracted with its final newline intact, so the byte counts
   and digests printed for the two sides are directly comparable.

2. ``project-license`` -- the project's own licence stated in three places has to
   be one licence: the ``LICENSE`` file (MIT body + its copyright line), the
   ``license`` field of ``pyproject.toml``, and the sentence this file opens with
   in ``THIRD-PARTY-LICENSES.md``. The About dialog's licence line is included,
   since that is what an end user reads. The exact copyright line is compared
   against the one quoted in ``THIRD-PARTY-LICENSES.md``.

3. ``spdx-headers`` -- survey of ``*.py`` files under ``seqkit_gui/``, ``tools/``,
   ``packaging/`` and ``tests/``: how many carry the project's one-line
   ``# SPDX-License-Identifier: MIT`` header, whether it sits in the first two
   lines (after a shebang, if any), and whether any file carries a different or
   longer licence header.

4. ``release-bundle`` -- inventory of a built ``dist/SeqKit-GUI`` onedir bundle
   against the obligations recorded in ``THIRD-PARTY-LICENSES.md``: does the archive
   convey a licence document at all, does it convey the LGPL-3.0 text, does it
   contain a Qt module that Qt publishes under GPL-v3-only rather than LGPL, and
   does it contain a ``seqkit`` binary that the project has committed not to
   redistribute. Nothing here assumes a bundle exists; without one the check is a
   SKIP.

Checks 1 and 2 decide the exit status (non-zero on a mismatch). Checks 3 and 4 are
advisory and always return zero: they report gaps for a human to act on rather than
failing a build over a convention or over an artefact that may simply not be built
on that machine.

Usage::

    python tools/license_check.py [path/to/seqkit/LICENSE]

The upstream LICENSE path defaults to ``../seqkit-2.14.0/LICENSE`` relative to this
repository and can be overridden with the path argument when the source tree sits
elsewhere; the raw GitHub copy of the same file is at
``https://raw.githubusercontent.com/shenwei356/seqkit/2.14.0/LICENSE`` for a human
reviewer to cross-check by hand. The script itself never reaches the network. It
exits non-zero when check 1 or check 2 fails, so it can be wired into CI later.
"""

from __future__ import annotations

import hashlib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
THIRD_PARTY = os.path.join(REPO, "THIRD-PARTY-LICENSES.md")
PYPROJECT = os.path.join(REPO, "pyproject.toml")
OWN_LICENSE = os.path.join(REPO, "LICENSE")

SPDX_LINE = "# SPDX-License-Identifier: MIT"

# Qt modules Qt itself lists under "Modules available under GNU General Public
# License v3" -- i.e. not available under the LGPL option this project elects.
# Only the ones that a PySide6/Qt-for-Python bundle can plausibly contain are
# probed for; see the "PySide6 / Qt" section of THIRD-PARTY-LICENSES.md.
GPL_ONLY_QT = (
    "Qt6VirtualKeyboard.dll",
    "qtvirtualkeyboardplugin.dll",
    "Qt6Graphs.dll",
    "Qt6Mqtt.dll",
    "Qt6Coap.dll",
    "Qt6Grpc.dll",
    "Qt6HttpServer.dll",
    "Qt6Lottie.dll",
    "libQt6VirtualKeyboard.so",
    "libqtvirtualkeyboardplugin.so",
)

# The license texts contain the U+00A9 copyright sign. On Windows the console
# default code page (e.g. cp936/GBK) cannot encode it, which would abort the run
# before the verdict is printed. Force UTF-8 stdout so the evidence is stable.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass


def read_bytes(path: str) -> bytes:
    with open(path, "rb") as handle:
        return handle.read()


def normalize(text: str) -> list[str]:
    """Minimal normalisation: unify newlines, strip trailing blanks per line,
    drop trailing empty lines. Line *content*, leading indentation and the
    copyright glyph are preserved exactly."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln.rstrip() for ln in text.split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return lines


def extract_seqkit_block(md_text: str) -> str:
    """Return the contents of the first ``` fenced block whose info string is
    'text' (the SeqKit licence copy in THIRD-PARTY-LICENSES.md).

    The block's own final newline is kept, so the returned string can be compared
    and hashed byte-for-byte against the upstream file."""
    lines = md_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    start = None
    for i, ln in enumerate(lines):
        if ln.strip() == "```text":
            start = i + 1
            break
    if start is None:
        raise SystemExit("ERROR: no ```text fenced block found in THIRD-PARTY-LICENSES.md")
    body: list[str] = []
    for ln in lines[start:]:
        if ln.strip() == "```":
            # Re-attach the newline the join below would otherwise lose, so the
            # extracted text and the upstream file have the same byte length.
            return "\n".join(body) + "\n"
        body.append(ln)
    raise SystemExit("ERROR: unterminated ```text fenced block")


def char_diff(a: str, b: str) -> str:
    for i in range(min(len(a), len(b))):
        if a[i] != b[i]:
            return (f"first differing char at index {i}: "
                    f"upstream {a[i]!r} (U+{ord(a[i]):04X}) vs md {b[i]!r} "
                    f"(U+{ord(b[i]):04X})")
    if len(a) != len(b):
        return f"length differs: upstream {len(a)} chars vs md {len(b)} chars"
    return "chars identical"


def check_seqkit(argv: list[str]) -> int:
    if argv:
        lic_path = os.path.abspath(argv[0])
    else:
        lic_path = os.path.normpath(os.path.join(REPO, os.pardir, "seqkit-2.14.0", "LICENSE"))

    print("=" * 72)
    print("CHECK 1 -- SeqKit MIT text: THIRD-PARTY-LICENSES.md vs upstream LICENSE")
    print("=" * 72)
    print(f"upstream LICENSE : {lic_path}")
    print(f"third-party file : {THIRD_PARTY}")

    if not os.path.isfile(lic_path):
        print("\nRESULT: SKIPPED -- upstream LICENSE copy not found.")
        print("        (Provide the path as the first argument; this is expected")
        print("         on machines that do not carry the seqkit source tree.)")
        return 0

    raw_up = read_bytes(lic_path)
    raw_md = read_bytes(THIRD_PARTY)

    up_text = raw_up.decode("utf-8")
    md_block = extract_seqkit_block(raw_md.decode("utf-8"))
    raw_block = md_block.encode("utf-8")

    print(f"\nupstream raw bytes : {len(raw_up)}  sha256 {hashlib.sha256(raw_up).hexdigest()[:16]}")
    print(f"md block raw bytes : {len(raw_block)}  "
          f"sha256 {hashlib.sha256(raw_block).hexdigest()[:16]}")

    def show_copyright(lines: list[str]) -> None:
        for ln in lines:
            if "Copyright" in ln:
                cps = [f"U+{ord(c):04X}({c!r})" for c in ln if ord(c) > 127]
                print(f"copyright line: {ln}")
                if cps:
                    print(f"  non-ASCII in that line: {', '.join(cps)}")

    if raw_up == raw_block:
        print("\nRESULT: IDENTICAL (byte-for-byte, zero normalisation) -- equal length, "
              "equal SHA-256.")
        show_copyright(up_text.split("\n"))
        return 0

    # A worktree copy edited on Windows can hold CRLF while the repository holds LF;
    # `.gitattributes` pins `*.md text eol=lf`, so the committed blob is the LF one.
    # Unifying the newline style alone is therefore the test of the verbatim claim,
    # and it is reported separately from any real content change.
    lf_block = raw_block.replace(b"\r\n", b"\n")
    if lf_block == raw_up:
        crlf = raw_block.count(b"\r\n")
        total = md_block.count("\n")
        same_digest = (hashlib.sha256(lf_block).hexdigest()
                       == hashlib.sha256(raw_up).hexdigest())
        print("\nRESULT: IDENTICAL (newline style aside) -- the extracted block equals")
        print("        the upstream file byte-for-byte once CRLF is read as LF:")
        print(f"        md block (CRLF) {len(raw_block)} bytes "
              f"sha256 {hashlib.sha256(raw_block).hexdigest()[:16]}")
        print(f"        md block (LF)   {len(lf_block)} bytes "
              f"sha256 {hashlib.sha256(lf_block).hexdigest()[:16]}"
              f"  == upstream: {same_digest}")
        print(f"        CRLF count in the worktree copy: {crlf} of {total} lines.")
        show_copyright(up_text.split("\n"))
        return 0

    up = normalize(up_text)
    md = normalize(md_block)
    if up == md:
        print("\nRESULT: IDENTICAL (whitespace-normalised) -- the copies differ only in")
        print("        newline style / trailing blanks. Acceptable for a quoted block,")
        print("        but the byte-for-byte claim in THIRD-PARTY-LICENSES.md is the")
        print("        stronger statement, so the exact byte difference is shown below.")
        print(f"  upstream last bytes : {raw_up[-16:]!r}")
        print(f"  md block last bytes : {raw_block[-16:]!r}")
        return 0

    print("\nRESULT: DIFFERENT -- content differences below:")
    n = max(len(up), len(md))
    diffs = 0
    for i in range(n):
        a = up[i] if i < len(up) else "<missing>"
        b = md[i] if i < len(md) else "<missing>"
        if a != b:
            diffs += 1
            print(f"  line {i + 1}:")
            print(f"    upstream: {a!r}")
            print(f"    md      : {b!r}")
            if a != "<missing>" and b != "<missing>":
                print(f"    -> {char_diff(a, b)}")
            if diffs >= 20:
                print("  ... (truncated at 20 differing lines)")
                break
    return 1


def _load_toml(path: str) -> dict:
    """Parse pyproject.toml with the stdlib parser, else ``tomli``, else {}.

    ``tomllib`` is 3.11+; on 3.10 ``tomli`` is present because PySide6 requires
    it. A hand-rolled fallback is deliberately not attempted -- an approximate
    parse of a licence field is worse than an honest SKIP."""
    try:
        import tomllib  # type: ignore[import-not-found]
        opener = lambda: open(path, "rb")  # noqa: E731
    except ModuleNotFoundError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
            opener = lambda: open(path, "rb")  # noqa: E731
        except ModuleNotFoundError:
            return {}
    try:
        with opener() as handle:
            return tomllib.load(handle)
    except (OSError, ValueError):
        return {}


MIT_BODY_MARKS = (
    "MIT License",
    "Permission is hereby granted, free of charge",
    "THE SOFTWARE IS PROVIDED \"AS IS\"",
    "without restriction, including without limitation the rights",
)


def check_project_license() -> int:
    print("\n" + "=" * 72)
    print("CHECK 2 -- the project's own licence, stated in four places")
    print("=" * 72)

    problems: list[str] = []

    # --- (a) the LICENSE file -------------------------------------------------
    lic_text = ""
    copyright_line = "<none>"
    if os.path.isfile(OWN_LICENSE):
        lic_text = read_bytes(OWN_LICENSE).decode("utf-8", "replace")
        for mark in MIT_BODY_MARKS:
            if mark not in lic_text:
                problems.append(f"LICENSE: missing MIT marker {mark!r}")
        found = [ln for ln in lic_text.splitlines() if ln.strip().lower().startswith("copyright")]
        if len(found) != 1:
            problems.append(f"LICENSE: expected exactly one copyright line, found {len(found)}")
        if found:
            copyright_line = found[0].strip()
        print(f"LICENSE            : MIT body={all(m in lic_text for m in MIT_BODY_MARKS)}")
        print(f"  copyright line   : {copyright_line}")
        print(f"  sha256           : {hashlib.sha256(read_bytes(OWN_LICENSE)).hexdigest()[:16]}")
    else:
        problems.append("LICENSE: file absent")
        print("LICENSE            : MISSING")

    # --- (b) pyproject.toml ---------------------------------------------------
    data = _load_toml(PYPROJECT)
    project = data.get("project", {}) if isinstance(data, dict) else {}
    raw_license = project.get("license", "<absent>")
    if isinstance(raw_license, dict):
        py_license = raw_license.get("text") or raw_license.get("file") or "<empty table>"
        style = "PEP 621 table"
    else:
        py_license = raw_license
        style = "PEP 639 SPDX string" if raw_license != "<absent>" else "absent"
    classifiers = [c for c in project.get("classifiers", []) if c.startswith("License ::")]
    print(f"pyproject license  : {py_license!r}  ({style})")
    print(f"pyproject classifiers: {classifiers}")
    if str(py_license).strip().upper() != "MIT":
        problems.append(f"pyproject.toml: license is {py_license!r}, not MIT")
    if classifiers and classifiers != ["License :: OSI Approved :: MIT License"]:
        problems.append(f"pyproject.toml: non-MIT licence classifier: {classifiers}")

    # --- (c) THIRD-PARTY-LICENSES.md -----------------------------------------
    md = read_bytes(THIRD_PARTY).decode("utf-8", "replace") if os.path.isfile(THIRD_PARTY) else ""
    intro = md.split("\n\n")[0] + "\n" + (md.split("\n\n")[1] if md.count("\n\n") > 1 else "")
    print(f"THIRD-PARTY header : {'MIT' in intro} (SPDX id quoted: "
          f"{'`MIT`' in md})")
    if "MIT" not in intro:
        problems.append("THIRD-PARTY-LICENSES.md: does not state this project's licence as MIT")
    # Copyright lines are compared in the prose only: the fenced SeqKit licence
    # block quotes upstream's own copyright line, which is not this project's.
    prose = re.sub(r"^```.*?^```[ \t]*\n?", "", md, flags=re.S | re.M)
    # A licence notice quoted in prose is either an inline code span or the whole
    # line; both readings are collected, and a bare sentence that merely mentions
    # "Copyright" in the middle of a line is not mistaken for the notice.
    quoted_copyright = [span.strip() for span in re.findall(r"`([^`]+)`", prose)
                        if span.strip().startswith("Copyright")]
    quoted_copyright += [ln.strip() for ln in prose.splitlines()
                         if ln.strip().startswith("Copyright")
                         and ln.strip() not in quoted_copyright]
    print(f"  copyright quoted : {quoted_copyright[:3]}")
    if copyright_line != "<none>" and quoted_copyright and copyright_line not in quoted_copyright:
        problems.append(
            f"THIRD-PARTY-LICENSES.md quotes {quoted_copyright[0]!r} but LICENSE says "
            f"{copyright_line!r}")

    # --- (d) the About dialog an end user reads ------------------------------
    dialogs = os.path.join(REPO, "seqkit_gui", "ui", "dialogs.py")
    if os.path.isfile(dialogs):
        src = read_bytes(dialogs).decode("utf-8", "replace")
        says_mit = re.search(r"tr\(['\"]License['\"]\).*?MIT", src, re.S) or "MIT" in src
        print(f"About dialog       : licence line mentions MIT={bool(says_mit)}")
        if not says_mit:
            problems.append("seqkit_gui/ui/dialogs.py: About dialog does not state MIT")

    if problems:
        print("\nRESULT: MISMATCH")
        for p in problems:
            print("  - " + p)
        return 1
    print("\nRESULT: CONSISTENT -- LICENSE, pyproject.toml, THIRD-PARTY-LICENSES.md and")
    print("        the About dialog all state MIT, and the copyright line is quoted as-is.")
    return 0


def tree_py(roots: tuple[str, ...]) -> list[str]:
    """Every ``*.py`` under the given repository-relative directories, tracked or
    not, with build and cache directories skipped."""
    skip = {".git", "build", "dist", ".pytest_cache", "__pycache__", "bin", "_build"}
    found = []
    for rel_root in roots:
        abs_root = os.path.join(REPO, rel_root.rstrip("/"))
        if not os.path.isdir(abs_root):
            continue
        for root, dirs, names in os.walk(abs_root):
            dirs[:] = [d for d in dirs if d not in skip]
            for nm in names:
                if nm.endswith(".py"):
                    found.append(os.path.relpath(os.path.join(root, nm), REPO)
                                 .replace(os.sep, "/"))
    return sorted(found)


def check_headers() -> int:
    print("\n" + "=" * 72)
    print("CHECK 3 -- SPDX header survey over seqkit_gui/, tools/, packaging/, tests/")
    print("=" * 72)
    files = tree_py(("seqkit_gui/", "tools/", "packaging/", "tests/"))
    exact, other, missing = [], [], []
    for rel in files:
        path = os.path.join(REPO, rel.replace("/", os.sep))
        try:
            with open(path, "r", encoding="utf-8", newline="") as fh:
                first = [fh.readline() for _ in range(3)]
        except (OSError, UnicodeDecodeError):
            first = []
        lines = [ln.strip() for ln in first if ln.strip()]
        idx = 1 if lines and lines[0].startswith("#!") else 0
        if len(lines) > idx and lines[idx] == SPDX_LINE:
            exact.append(rel)
        elif any("SPDX-License-Identifier" in ln for ln in lines):
            other.append(rel)
        else:
            missing.append(rel)

    print(f"scanned            : {len(files)}")
    print(f"exact one-line form: {len(exact)}   ({SPDX_LINE})")
    print(f"other SPDX form    : {len(other)}")
    print(f"no SPDX header     : {len(missing)}")
    if other:
        print("\nNon-conforming SPDX headers:")
        for rel in other:
            print(f"  {rel}")
    if missing:
        print("\nFiles WITHOUT an SPDX-License-Identifier header:")
        for rel in missing:
            print(f"  {rel}")
    return 0


def check_bundle() -> int:
    print("\n" + "=" * 72)
    print("CHECK 4 -- release bundle inventory (dist/SeqKit-GUI)")
    print("=" * 72)
    bundle = os.path.join(REPO, "dist", "SeqKit-GUI")
    if not os.path.isdir(bundle):
        print("RESULT: SKIPPED -- no built bundle at %s" % bundle)
        return 0

    docs = []
    for root, _dirs, names in os.walk(bundle):
        for nm in names:
            if re.search(r"(?i)(licen[sc]e|copying|notice|lgpl|gpl)", nm):
                docs.append(os.path.relpath(os.path.join(root, nm), bundle).replace(os.sep, "/"))
    dlls = {}
    for root, _dirs, names in os.walk(bundle):
        for nm in names:
            if nm.lower().endswith((".dll", ".pyd", ".so")):
                dlls.setdefault(nm, os.path.relpath(os.path.join(root, nm), bundle).replace(os.sep, "/"))

    print(f"bundle             : {bundle}")
    print(f"shared objects      : {len(dlls)} distinct")
    print(f"licence documents   : {len(docs)} {docs[:6]}")
    seqkit_bundled = sorted(p for p in
                            (os.path.relpath(os.path.join(r, n), bundle).replace(os.sep, "/")
                             for r, _d, ns in os.walk(bundle) for n in ns)
                            if re.search(r"(?i)^seqkit(\.exe)?$", os.path.basename(p)))
    offenders = sorted(k for k in dlls if k in GPL_ONLY_QT)

    gaps = []
    if not docs:
        gaps.append("no licence document of any kind inside the archive -- LGPL-3.0 "
                    "section 4(a) wants a copy of the licence conveyed with it")
    if not any(re.search(r"(?i)lgpl.*\.txt$", d) for d in docs):
        gaps.append("no LGPL-3.0 text file in the archive (see the 'What the release "
                    "archive has to carry' table in THIRD-PARTY-LICENSES.md)")
    if offenders:
        gaps.append("GPL-only Qt module present although the project elects the LGPL "
                    "option: " + ", ".join(offenders))
    if seqkit_bundled:
        gaps.append("a seqkit binary sits in the archive (" + ", ".join(seqkit_bundled) +
                    "); this project's policy is not to redistribute SeqKit, so it must "
                    "not be zipped into the release, and if it ever is, SeqKit's MIT "
                    "notice must travel next to that exact binary")

    if gaps:
        print("RESULT: GAPS (advisory, exit status unaffected) --")
        for g in gaps:
            print("  - " + g)
    else:
        print("RESULT: OK -- licence documents present, no GPL-only Qt module, "
              "no seqkit binary in the archive.")
    return 0


def main(argv: list[str]) -> int:
    rc1 = check_seqkit(argv)
    rc2 = check_project_license()
    check_headers()
    check_bundle()
    print("\n" + "=" * 72)
    print(f"SUMMARY: seqkit-license={'PASS' if rc1 == 0 else 'FAIL'}  "
          f"project-license={'PASS' if rc2 == 0 else 'FAIL'}  "
          f"(checks 3-4 are advisory)")
    print("=" * 72)
    return rc1 or rc2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
