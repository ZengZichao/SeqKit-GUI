"""Structural quality rules for the application code.

These are the invariants that make a change in one file show up in the right other
file: persisted keys named in exactly one place, the application name declared once,
every preference field actually stored, and the generated schema actually generated.

The checks read source files rather than importing the widgets, so they run headless
and cost milliseconds.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "seqkit_gui"
RAW_DUMP = ROOT / "tools" / "_build" / "spec_raw.json"

#: A QSettings key is spelled as a section plus a slash, e.g. ``general/language``.
SETTING_KEY = re.compile(r"""["'](?:general|ui|files)/[A-Za-z0-9_]+["']""")

#: The start of a line that was a statement before somebody commented it out.
CODE_AFTER_HASH = re.compile(
    r"^(?:def |class |import |from |if |for |while |return |try:|except |else:|raise |"
    r"[A-Za-z_][\w.]*\s*=\s*\S)")


def app_modules() -> list[Path]:
    return sorted(APP.rglob("*.py"))


def load_tool(name: str):
    path = ROOT / "tools" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_quality_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------- #
# persisted state
# --------------------------------------------------------------------------- #
def test_qsettings_keys_are_named_only_in_core_settings() -> None:
    """A key spelled in two files is a key one of them can rename silently.

    ``ui/main_window.py`` restores the window geometry and the column widths, so it
    has to read back through the same constants that wrote them.
    """
    offenders = []
    for path in app_modules():
        if path.name == "settings.py":
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if SETTING_KEY.search(line):
                offenders.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()}")
    assert offenders == [], f"QSettings keys spelled outside core/settings.py: {offenders}"


def test_every_declared_settings_key_is_used() -> None:
    """A declared key nobody reads or writes is a value stuck in the user's registry."""
    source = (APP / "core" / "settings.py").read_text(encoding="utf-8")
    declared = {node.targets[0].id
                for node in ast.parse(source).body
                if isinstance(node, ast.Assign)
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id.startswith("KEY_")}
    used = {node.id for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Name) and node.id.startswith("KEY_")}
    callers = set()
    for path in app_modules():
        if path.name == "settings.py":
            continue
        callers |= {node.attr for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
                    if isinstance(node, ast.Attribute) and node.attr.startswith("KEY_")}
    untracked = sorted(declared - used - callers)
    assert untracked == [], f"settings keys declared but never read or written: {untracked}"


def test_preferences_stores_every_field_it_declares() -> None:
    """A field nobody persists reads back as its default on every start."""
    source = (APP / "core" / "settings.py").read_text(encoding="utf-8")
    model = next(node for node in ast.parse(source).body
                 if isinstance(node, ast.ClassDef) and node.name == "Preferences")
    declared = {node.target.id for node in model.body
                if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)}

    saved: set[str] = set()
    loaded: set[str] = set()
    for method in model.body:
        if not isinstance(method, (ast.FunctionDef, ast.ClassDef)):
            continue
        bucket = {"load": loaded, "save": saved}.get(method.name)
        if bucket is None:
            continue
        for node in ast.walk(method):
            if isinstance(node, ast.keyword) and node.arg in declared:
                bucket.add(node.arg)
            elif (isinstance(node, ast.Attribute) and node.attr in declared
                  and isinstance(node.ctx, ast.Load) and method.name == "save"):
                bucket.add(node.attr)

    assert saved == declared, (
        f"Preferences.save() writes {sorted(saved)} but the dataclass declares "
        f"{sorted(declared)}")
    assert loaded == declared, (
        f"Preferences.load() reads {sorted(loaded)} but the dataclass declares "
        f"{sorted(declared)}")


# --------------------------------------------------------------------------- #
# one declaration per fact
# --------------------------------------------------------------------------- #
def test_application_name_is_literal_in_one_place() -> None:
    """``seqkit_gui/__init__.py`` is the source, and the spec file scrapes it there."""
    offenders = []
    for path in app_modules():
        if path.name == "__init__.py":
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if '"SeqKit GUI"' in line or "'SeqKit GUI'" in line:
                offenders.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()}")
    assert offenders == [], f"the application name spelled a second time: {offenders}"


def test_theme_choices_come_from_the_palette_table() -> None:
    """``ui/theme.py`` promises adding a palette is the only place a theme appears."""
    from seqkit_gui.ui.theme import PALETTES, THEME_CHOICES

    assert [key for key, _label in THEME_CHOICES] == list(PALETTES)
    header = (APP / "ui" / "main_window.py").read_text(encoding="utf-8")
    assert "THEME_CHOICES" in header, "the header bar must build its chips from theme.py"
    assert '("light", "Light")' not in header, "the header bar repeats the palette table"


def test_every_palette_token_is_emitted_by_the_stylesheet() -> None:
    """A colour no rule reads is a colour that drifts: the theme file claims otherwise.

    ``ui/theme.py`` says every widget style is derived from the palette, so a field
    the QSS builder never interpolates is either a missing rule or dead weight.
    """
    import inspect

    from seqkit_gui.ui.theme import Palette, stylesheet

    body = inspect.getsource(stylesheet)
    unused = [name for name in Palette.__dataclass_fields__
              if name != "name" and not re.search(rf"\bp\.{name}\b", body)]
    assert unused == [], f"palette tokens the stylesheet never uses: {unused}"


def test_stylesheet_object_names_match_the_widgets() -> None:
    """A rule for a name nobody sets is dead CSS; a set name nobody rules is decoration.

    ``setObjectName`` is how this interface selects what to style, so the two sides
    have to be kept in step or a widget silently loses its card, chip or badge look.
    """
    css = (APP / "ui" / "theme.py").read_text(encoding="utf-8")
    styled = set(re.findall(r"[A-Za-z][A-Za-z0-9]*#([A-Za-z][A-Za-z0-9]*)", css))
    named: set[str] = set()
    for path in app_modules():
        named |= set(re.findall(
            r'setObjectName\("([A-Za-z0-9]+)"\)', path.read_text(encoding="utf-8")))
    assert styled == named, (
        f"styled but never set: {sorted(styled - named)}; "
        f"set but never styled: {sorted(named - styled)}")


# --------------------------------------------------------------------------- #
# the generated schema
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(not RAW_DUMP.is_file(),
                    reason="needs the cached dumper output in tools/_build/")
def test_committed_schema_is_what_the_generator_produces() -> None:
    """commands.json must be the generator's output, byte for byte.

    The schema drives every parameter form, and it is only trustworthy while it is
    normalisation of the dumper's raw dump rather than something edited by hand.
    """
    generator = load_tool("extract_spec")
    raw = json.loads(RAW_DUMP.read_text(encoding="utf-8"))
    payload, _worklist = generator.normalise(raw)
    produced = json.dumps(payload, ensure_ascii=False, indent=1) + "\n"
    committed = (APP / "data" / "commands.json").read_text(encoding="utf-8")
    assert produced == committed, (
        "seqkit_gui/data/commands.json is not what tools/extract_spec.py produces from "
        "tools/_build/spec_raw.json; regenerate it instead of editing the JSON")


# --------------------------------------------------------------------------- #
# leftovers
# --------------------------------------------------------------------------- #
def test_no_commented_out_code_blocks() -> None:
    """Three commented statements in a row are dead code or a lie about what runs."""
    offenders = []
    for path in app_modules():
        streak = 0
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            looks_like_code = (stripped.startswith("#")
                               and CODE_AFTER_HASH.match(stripped.lstrip("#").strip()))
            streak = streak + 1 if looks_like_code else 0
            if streak == 3:
                offenders.append(f"{path.relative_to(ROOT)}:{number}")
    assert offenders == [], "commented-out code blocks at: " + ", ".join(offenders)
