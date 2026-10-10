# SPDX-License-Identifier: MIT
"""Program entry point."""

from __future__ import annotations

import sys

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication, QMessageBox

from . import APP_NAME, __version__
from .core.settings import APPLICATION, ORGANIZATION, Preferences
from .core.spec import Schema, load
from .ui.i18n import Catalog
from .ui.main_window import MainWindow


def main(argv: list[str] | None = None) -> int:
    QCoreApplication.setOrganizationName(ORGANIZATION)
    QCoreApplication.setApplicationName(APPLICATION)
    QCoreApplication.setApplicationVersion(__version__)

    app = QApplication(list(argv) if argv is not None else sys.argv)
    app.setApplicationDisplayName(APP_NAME)

    prefs = Preferences.load()
    try:
        schema: Schema = load()
    except (OSError, ValueError) as error:
        # The schema is generated data read from the bundle; a missing or truncated
        # commands.json means the forms would offer no parameters at all, so the app
        # says where to regenerate it instead of opening an empty window.
        QMessageBox.critical(
            None, APP_NAME,
            f"Command schema could not be loaded.\n{error}\n\n"
            "Regenerate it with: python tools/extract_spec.py --build",
        )
        return 2

    catalog = Catalog(prefs.language)
    window = MainWindow(catalog, prefs, schema)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
