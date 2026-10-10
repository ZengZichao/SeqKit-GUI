"""Signal wiring for the header bar's segmented controls.

The theme and language chips are the only interface elements that change a
preference with a single click, and they are also the only place where
``_Choice``'s own state and the window's state have to agree. ``tests/test_gui.py``
drives ``_set_theme`` and ``_set_language`` directly, which leaves the click path --
``_Choice.clicked`` -> ``_Choice._select`` -> ``changed`` -> the window -- untested.
These cases cover it, because a widget whose signal is disconnected keeps painting
the right chip while every preference behind it silently stops moving.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from seqkit_gui.core.settings import Preferences
from seqkit_gui.ui.dialogs import _Choice
from seqkit_gui.ui.i18n import Catalog
from seqkit_gui.ui.main_window import MainWindow
from seqkit_gui.ui.theme import PALETTES

pytestmark = pytest.mark.gui


@pytest.fixture(scope="module")
def shell(qapp, root, schema):
    catalog = Catalog("zh_CN", directory=root / "seqkit_gui" / "i18n")
    prefs = Preferences(language="zh_CN", theme="light")
    window = MainWindow(catalog, prefs, schema)
    window.show()
    qapp.processEvents()
    yield window
    window.close()


def _click(button) -> None:
    """Press the button the way a user does: toggle, then emit ``clicked``.

    ``_Choice._select`` sets the checked state of the whole group afterwards, so the
    toggle this performs is corrected by the widget's own handler.
    """
    button.click()


# --------------------------------------------------------------------------- #
# the window's own wiring
# --------------------------------------------------------------------------- #
def test_clicking_the_theme_chip_changes_the_application_style(shell, qapp) -> None:
    before = shell.prefs.theme
    other = next(name for name in PALETTES if name != before)
    _click(shell.theme_choice.buttons[other])
    qapp.processEvents()

    assert shell.prefs.theme == other
    assert PALETTES[other].surface.strip("#").lower() in QApplication.instance().styleSheet()
    assert shell.theme_choice.value() == other, (
        "the chip's own value must follow the click, or a later read disagrees with the screen")

    _click(shell.theme_choice.buttons[before])
    qapp.processEvents()
    assert shell.prefs.theme == before


def test_clicking_the_language_chip_retranslates_the_window(shell, qapp) -> None:
    before = shell.catalog.language
    other = "en_US" if before == "zh_CN" else "zh_CN"
    _click(shell.language_choice.buttons[other])
    qapp.processEvents()

    assert shell.catalog.language == other
    assert shell.prefs.language == other
    assert shell.chinese is (other == "zh_CN")
    assert shell.settings_button.text() == shell.catalog.tr("Settings")
    assert shell.tree.topLevelItemCount() >= 8

    _click(shell.language_choice.buttons[before])
    qapp.processEvents()
    assert shell.catalog.language == before


def test_a_preference_changed_elsewhere_syncs_the_chip_without_echoing(shell) -> None:
    """The Settings dialog reaches the header chips through ``set_value``.

    Echoing back through ``changed`` would send the value to the window again, so a
    dialog that already stored it would be asked to store it a second time.
    """
    target = next(name for name in PALETTES if name != shell.prefs.theme)
    seen = []
    shell.theme_choice.changed.connect(seen.append)
    shell.theme_choice.set_value(target)

    assert seen == [], "set_value must not emit changed"
    assert shell.theme_choice.buttons[target].isChecked()
    assert not shell.theme_choice.buttons[shell.prefs.theme].isChecked()
    assert shell.theme_choice.value() == target

    shell.theme_choice.set_value(shell.prefs.theme)
    assert seen == []


# --------------------------------------------------------------------------- #
# _Choice itself
# --------------------------------------------------------------------------- #
def test_choice_click_emits_once_and_tracks_the_selection(qapp) -> None:
    choices = [("light", "Light"), ("dark", "Dark")]
    picker = _Choice(choices, "light")
    emitted = []
    picker.changed.connect(emitted.append)

    _click(picker.buttons["dark"])

    assert emitted == ["dark"], "a click must reach its owner exactly once"
    assert picker.value() == "dark"
    assert picker.buttons["dark"].isChecked()
    assert not picker.buttons["light"].isChecked()


def test_choice_ignores_a_value_that_is_not_on_it(qapp) -> None:
    """An unknown preference falls back to the first choice instead of an empty group."""
    picker = _Choice([("light", "Light"), ("dark", "Dark")], "midnight")
    assert picker.value() == "light"
