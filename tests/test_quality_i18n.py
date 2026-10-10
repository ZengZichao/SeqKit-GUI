"""Catalogue integrity for the two JSON language tables.

``tests/test_i18n.py`` finds the keys it can see with a regular expression over
``tr("…")`` calls. That expression needs the closing parenthesis right after the
string, so it misses every call that passes formatting arguments
(``tr("one of {names} is required", names=…)``), every call made through a local
alias (``tr = self.catalog.tr`` in ``ui/param_form.py``), and every key handed over
through a table (``ui/dialogs.py::_localise``, ``ui/widgets.py::FileListField``).
This file walks the syntax tree instead, and adds the checks a JSON reader cannot
make on its own: duplicate keys and value shapes.

Nothing here rewrites the catalogues: ``seqkit_gui/i18n/*.json`` is data reviewed on
its own, and the interface falls back to the key itself, so an untranslated literal
English key is legitimate while an abstract one is not.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
I18N_DIR = ROOT / "seqkit_gui" / "i18n"
APP = ROOT / "seqkit_gui"

#: ``ui/i18n.py`` builds its own tables from the language codes; its string values
#: are endonyms (``简体中文``, ``English``), not translation keys.
SELF_TABLE_MODULE = "i18n.py"


def load_catalogue(name: str) -> dict:
    path = I18N_DIR / f"{name}.json"
    assert path.is_file(), f"{path} is missing"
    return json.loads(path.read_text(encoding="utf-8"))


def _is_tr_call(node: ast.Call) -> bool:
    """``catalog.tr(...)`` and a local alias bound to it both count."""
    callee = node.func
    if isinstance(callee, ast.Attribute):
        return callee.attr == "tr"
    return isinstance(callee, ast.Name) and callee.id == "tr"


def translation_keys(path: Path) -> set[str]:
    """Keys the code can ask the catalogue for.

    Two shapes reach the catalogue through a variable rather than a literal:
    a dict that maps something else to a key, and ``**fmt`` kwargs (which are
    placeholder names, not keys). Only the first is collected here, as a key.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    keys: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _is_tr_call(node) and node.args:
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                keys.add(first.value)
        if isinstance(node, ast.Dict) and path.parent.name == "ui" \
                and path.name != SELF_TABLE_MODULE:
            for value in node.values:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    keys.add(value.value)
    return keys


def used_keys() -> set[str]:
    keys: set[str] = set()
    for path in sorted(APP.rglob("*.py")):
        keys |= translation_keys(path)
    return keys


def test_every_key_the_interface_asks_for_has_a_chinese_text() -> None:
    chinese = load_catalogue("zh_CN")
    missing = sorted(key for key in used_keys() if key not in chinese)
    assert missing == [], f"asked for by the code, absent from zh_CN.json: {missing}"


def test_abstract_keys_are_defined_in_the_fallback_catalogue() -> None:
    """A key with an underscore is not readable English, so it must be translated.

    Keys spelled as a whole sentence (``Save result``) render themselves in the
    English interface, which is why only the abstract ones are required here.
    """
    english = load_catalogue("en_US")
    abstract = {key for key in used_keys() if "_" in key}
    missing = sorted(key for key in abstract if key not in english)
    assert missing == [], f"abstract keys with no English text: {missing}"


def test_english_catalogue_introduces_no_key_the_chinese_one_lacks() -> None:
    """``ui/i18n.py`` falls back English -> key, never English -> Chinese.

    A key that exists only in ``en_US.json`` therefore shows English text in the
    Chinese interface, which is the leak this test closes.
    """
    chinese = set(load_catalogue("zh_CN"))
    english = set(load_catalogue("en_US"))
    only_english = sorted(english - chinese)
    assert only_english == [], f"keys the Chinese interface would show in English: {only_english}"


def test_catalogues_are_flat_string_maps() -> None:
    """``Catalog._table`` drops every value that is not a string, silently."""
    for name in ("zh_CN", "en_US"):
        path = I18N_DIR / f"{name}.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        wrong = {key: type(value).__name__ for key, value in document.items()
                 if not isinstance(value, str)}
        assert wrong == {}, f"{path.name} has non-string values: {wrong}"


def test_catalogues_have_no_duplicate_keys() -> None:
    """json keeps the last duplicate silently, so a translation can vanish unnoticed."""
    for name in ("zh_CN", "en_US"):
        path = I18N_DIR / f"{name}.json"
        pairs = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=list)
        seen: dict[str, int] = {}
        for key, _value in pairs:
            seen[key] = seen.get(key, 0) + 1
        duplicated = {key: count for key, count in seen.items() if count > 1}
        assert duplicated == {}, f"{path.name} declares these keys twice: {duplicated}"


def test_fallback_language_is_a_real_catalogue_file() -> None:
    """The fallback is what a missing Chinese key lands on, so its file must exist."""
    from seqkit_gui.ui.i18n import DEFAULT_LANGUAGE, FALLBACK_LANGUAGE, LANGUAGES

    for code in LANGUAGES:
        assert (I18N_DIR / f"{code}.json").is_file(), code
    assert DEFAULT_LANGUAGE in LANGUAGES
    assert FALLBACK_LANGUAGE in LANGUAGES
    assert FALLBACK_LANGUAGE != DEFAULT_LANGUAGE
