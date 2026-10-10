"""Bilingual interface coverage: no English may leak into the Chinese UI."""

import re
from pathlib import Path

import pytest

KEY_RE = re.compile(r'tr\("([^"]+)"\)')


def used_keys(root) -> set[str]:
    keys: set[str] = set()
    for file in Path(root).glob("seqkit_gui/**/*.py"):
        keys.update(KEY_RE.findall(file.read_text(encoding="utf-8")))
    return keys


def test_every_ui_key_has_a_chinese_text(root):
    catalog = json_load(root / "seqkit_gui" / "i18n" / "zh_CN.json")
    missing = sorted(key for key in used_keys(root) if key not in catalog)
    assert not missing, f"keys without Chinese text: {missing}"


def test_english_fallback_keys_are_defined(root):
    """Keys that are not literal English sentences must exist in en_US.json too."""
    catalog = json_load(root / "seqkit_gui" / "i18n" / "en_US.json")
    abstract = [key for key in used_keys(root) if "_" in key]
    missing = sorted(key for key in abstract if key not in catalog)
    assert not missing, missing


def test_chinese_catalog_is_actually_chinese(root):
    catalog = json_load(root / "seqkit_gui" / "i18n" / "zh_CN.json")
    offenders = [key for key, value in catalog.items()
                 if key != "app_title" and not has_cjk(str(value))]
    assert not offenders, offenders


def test_language_switch_is_live(qapp, root):
    from seqkit_gui.ui.i18n import Catalog
    catalog = Catalog("zh_CN", directory=root / "seqkit_gui" / "i18n")
    assert "序列" in catalog.tr("seqkit_attribution") or has_cjk(catalog.tr("Settings"))
    catalog.set_language("en_US")
    assert catalog.tr("Settings") == "Settings"
    catalog.set_language("zh_CN")
    assert catalog.tr("Settings") == "设置"


def test_unknown_key_falls_back_to_the_key_itself(qapp, root):
    from seqkit_gui.ui.i18n import Catalog
    catalog = Catalog("zh_CN", directory=root / "seqkit_gui" / "i18n")
    assert catalog.tr("a key that does not exist") == "a key that does not exist"


def test_catalog_formatting_is_tolerated(qapp, root):
    from seqkit_gui.ui.i18n import Catalog
    catalog = Catalog("zh_CN", directory=root / "seqkit_gui" / "i18n")
    assert catalog.tr("matched_commands", count=41) == "匹配到 41 个命令"
    assert catalog.tr("mismatch_hint", expected="2.14.0", actual="2.15.0").count("2.1") == 2


def test_themes_cover_both_light_and_dark(root):
    from seqkit_gui.ui.theme import PALETTES, stylesheet
    assert set(PALETTES) == {"light", "dark"}
    for palette in PALETTES.values():
        css = stylesheet(palette)
        assert palette.on_accent.lower() == "#ffffff", "filled accents must carry white text"
        assert "QPushButton#RunButton" in css


def test_palette_tokens_are_consistent(root):
    from seqkit_gui.ui.theme import DARK, LIGHT
    light_fields = set(LIGHT.__dataclass_fields__)
    assert light_fields == set(DARK.__dataclass_fields__)
    # White-on-accent is intentionally identical in both themes.
    shared = {"on_accent"}
    for name in light_fields - {"name"} - shared:
        assert getattr(LIGHT, name) != getattr(DARK, name), name


def json_load(path: Path) -> dict:
    import json
    if not path.is_file():
        pytest.fail(f"missing catalogue: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def has_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)
