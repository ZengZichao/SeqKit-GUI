# SPDX-License-Identifier: MIT
"""Filesystem layout shared by the app, tools and tests.

Everything platform-specific about locating resources lives here, so adding macOS
support means extending :func:`executable_names` and the search folders -- not
touching the UI or the runner.
"""

from __future__ import annotations

import platform
import sys
from pathlib import Path


def is_frozen() -> bool:
    """True when running from a PyInstaller bundle."""
    return getattr(sys, "frozen", False)


def package_dir() -> Path:
    """The ``seqkit_gui`` package directory, bundled resources included."""
    if is_frozen():
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
        return base / "seqkit_gui"
    return Path(__file__).resolve().parent.parent


def project_root() -> Path:
    """Repository root when running from source; app directory when frozen."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return package_dir().parent


def data_dir() -> Path:
    return package_dir() / "data"


def assets_dir() -> Path:
    return package_dir() / "assets"


def i18n_dir() -> Path:
    return package_dir() / "i18n"


def spec_path() -> Path:
    return data_dir() / "commands.json"


def docs_dir() -> Path:
    """The documentation folder the "open documentation" action reveals.

    ``packaging/seqkit_gui.spec`` does not ship ``docs/`` inside the bundle, so a
    bundled build usually falls through to the plain ``project_root()`` result and
    the caller reports the path it could not open.
    """
    if is_frozen():
        for candidate in (project_root() / "docs", package_dir() / "docs"):
            if candidate.is_dir():
                return candidate
        return project_root()
    root = project_root()
    if (root / "docs").is_dir():
        return root / "docs"
    return root


def executable_names() -> tuple[str, ...]:
    """Candidate binary names for the current platform."""
    if platform.system() == "Windows":
        return ("seqkit.exe", "seqkit.cmd", "seqkit.bat", "seqkit")
    return ("seqkit",)


def bundled_dir() -> Path:
    """Folder a shipped seqkit binary is looked up in, before PATH."""
    return project_root() / "bin"
