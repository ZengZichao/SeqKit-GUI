# SPDX-License-Identifier: MIT
"""Language catalogues and live retranslation.

Interface strings come from JSON catalogues (``i18n/*.json``) rather than Qt's
``.ts`` toolchain, so switching language does not need a restart and the catalogues
stay reviewable in a pull request. Missing keys fall back to the English catalogue,
then to the key itself, so a half-translated build is still usable.
"""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from ..core import paths

LANGUAGES = {
    "zh_CN": "简体中文",
    "en_US": "English",
}
DEFAULT_LANGUAGE = "zh_CN"
FALLBACK_LANGUAGE = "en_US"


class Catalog(QObject):
    """Holds the active language and re-emits it so widgets can retranslate."""

    language_changed = Signal(str)

    def __init__(self, language: str = DEFAULT_LANGUAGE, directory: Path | None = None):
        super().__init__()
        self.directory = Path(directory) if directory else paths.i18n_dir()
        self._tables: dict[str, dict[str, str]] = {}
        self._language = language if language in LANGUAGES else DEFAULT_LANGUAGE

    # ---- loading -----------------------------------------------------------
    def _table(self, language: str) -> dict[str, str]:
        if language not in self._tables:
            file = self.directory / f"{language}.json"
            data = {}
            if file.is_file():
                data = json.loads(file.read_text(encoding="utf-8"))
            self._tables[language] = {
                key: value for key, value in data.items() if isinstance(value, str)
            }
        return self._tables[language]

    @property
    def language(self) -> str:
        return self._language

    def set_language(self, language: str) -> None:
        if language not in LANGUAGES or language == self._language:
            return
        self._language = language
        self.language_changed.emit(language)

    # ---- lookup ------------------------------------------------------------
    def tr(self, key: str, **fmt: object) -> str:
        table = self._table(self._language)
        text = table.get(key)
        if text is None:
            text = self._table(FALLBACK_LANGUAGE).get(key)
        if text is None:
            text = key
        if fmt:
            try:
                return text.format(**fmt)
            except (KeyError, IndexError, ValueError):
                return text
        return text

