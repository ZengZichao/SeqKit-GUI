# SPDX-License-Identifier: MIT
"""Persisted user preferences."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QCoreApplication, QSettings

from .. import APP_NAME, APP_ORGANIZATION

# Aliased rather than re-declared: ``seqkit_gui/__init__.py`` is the only place these
# two identifiers are written down, and ``packaging/seqkit_gui.spec`` scrapes
# ``APP_NAME`` out of that file when it names the bundle.
ORGANIZATION = APP_ORGANIZATION
APPLICATION = APP_NAME

KEY_SEQKIT_PATH = "general/seqkit_path"
KEY_LANGUAGE = "general/language"
KEY_THEME = "general/theme"
KEY_OUTPUT_LIMIT = "ui/output_line_limit"
KEY_WORKING_DIR = "general/working_dir"
KEY_GEOMETRY = "ui/geometry"
KEY_SPLITTER = "ui/splitter"
KEY_RECENT_FILES = "files/recent"

#: One number for the recent-files menu, the stored list and the tests: the menu
#: shows ``recent_files()`` and the store keeps exactly that many entries.
RECENT_FILES_LIMIT = 15


def settings() -> QSettings:
    return QSettings(ORGANIZATION, APPLICATION)


@dataclass
class Preferences:
    seqkit_path: str = ""
    language: str = "zh_CN"
    theme: str = "light"
    output_line_limit: int = 5000
    working_dir: str = ""

    @classmethod
    def load(cls) -> "Preferences":
        store = settings()
        return cls(
            seqkit_path=str(store.value(KEY_SEQKIT_PATH, "") or ""),
            language=str(store.value(KEY_LANGUAGE, "zh_CN") or "zh_CN"),
            theme=str(store.value(KEY_THEME, "light") or "light"),
            output_line_limit=int(store.value(KEY_OUTPUT_LIMIT, 5000) or 5000),
            working_dir=str(store.value(KEY_WORKING_DIR, "") or ""),
        )

    def save(self) -> None:
        store = settings()
        store.setValue(KEY_SEQKIT_PATH, self.seqkit_path)
        store.setValue(KEY_LANGUAGE, self.language)
        store.setValue(KEY_THEME, self.theme)
        store.setValue(KEY_OUTPUT_LIMIT, self.output_line_limit)
        store.setValue(KEY_WORKING_DIR, self.working_dir)
        store.sync()


def read(key: str, default=None):
    return settings().value(key, default)


def write(key: str, value) -> None:
    settings().setValue(key, value)


def remove(key: str) -> None:
    settings().remove(key)


def recent_files(limit: int = RECENT_FILES_LIMIT) -> list[str]:
    value = settings().value(KEY_RECENT_FILES, [])
    if isinstance(value, str):
        value = [value] if value else []
    return [str(item) for item in (value or [])][:limit]


def push_recent_file(path: str) -> None:
    items = [path] + [item for item in recent_files() if item != path]
    settings().setValue(KEY_RECENT_FILES, items[:RECENT_FILES_LIMIT])
    # QSettings needs an application object to flush; harmless when absent.
    if QCoreApplication.instance() is not None:
        settings().sync()
