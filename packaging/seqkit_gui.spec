# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller recipe for SeqKit GUI -- windowed (no console), two bundle modes.

Build from the project root::

    pyinstaller packaging/seqkit_gui.spec                      # onedir (default)
    set SEQKIT_GUI_BUNDLE=onefile&& pyinstaller packaging/seqkit_gui.spec   # single exe

Outputs ``dist/SeqKit-GUI/`` (onedir) or ``dist/SeqKit-GUI.exe`` (onefile), plus
a scratch ``build/`` directory (both are gitignored). Every path below is derived
from ``SPECPATH`` -- the directory holding this file -- so the build works from
the repository root regardless of the current directory PyInstaller was started
in. The app itself resolves either layout the same way: ``core/paths.py`` reads
``sys._MEIPASS`` under onefile and the folder layout under onedir.

Why onedir is the default
-------------------------
PySide6 is used under its LGPL option, which obliges us to let end users replace
the Qt libraries. A onefile bundle hides Qt6*.dll inside a self-extracting blob;
onedir leaves them as ordinary, swappable files -- a measured build put
``Qt6Core.dll``, ``Qt6Gui.dll`` and the rest in ``SeqKit-GUI/_internal/PySide6/``
and the platform plugins in ``SeqKit-GUI/_internal/PySide6/plugins/platforms/``,
each one a loose file a user can substitute. Onedir also skips the per-launch
extraction that makes a Qt app feel slow. ``.github/workflows/release-build.yml``
asserts that ``_internal/PySide6/Qt6Core.dll`` is present as a plain file, so this
stays a checked fact rather than a claim about PyInstaller.

What onefile mode is for
------------------------
``SEQKIT_GUI_BUNDLE=onefile`` packages the identical analysis into one
self-contained ``SeqKit-GUI.exe``: convenient for carrying on a USB stick or
handing to a single user, and the app still finds a ``bin/seqkit.exe`` dropped
next to the exe (``core/paths.py`` searches beside ``sys.executable``). The
trade-offs are the LGPL ones above -- the Qt libraries are embedded and not
user-swappable -- plus slower first launch (extraction into the temp directory)
and a single large binary that some antivirus scanners inspect more slowly. For
a published release the onedir zip remains the canonical artifact; treat onefile
as the personal-convenience packaging of the same, checked ingredients.

SeqKit itself is deliberately NOT bundled
-----------------------------------------
SeqKit is upstream MIT software by Wei Shen, roughly 28 MB, and is not committed
to this repository. **After building, drop ``seqkit.exe`` into a ``bin`` folder
next to the built app**, i.e.::

    dist/SeqKit-GUI/SeqKit-GUI.exe     <- the built GUI (onedir)
    dist/SeqKit-GUI/bin/seqkit.exe     <- you put this here

or, for onefile, ``bin/`` beside the exe itself::

    dist/SeqKit-GUI.exe                <- the built GUI
    dist/bin/seqkit.exe                <- you put this here

That is exactly the second place the app searches (configured path first, then
``bin/`` beside the executable, then PATH); see ``seqkit_gui/core/paths.py``
(``bundled_dir``) and ``seqkit_gui/core/seqkit_locator.py``. Alternatively let
users run ``python tools/fetch_seqkit.py`` or set the path in the Settings
dialog. On macOS the same layout applies with the extensionless ``bin/seqkit``.

Nothing in this file hard-codes a version: ``VERSION`` and ``PRODUCT_NAME`` are
scraped out of ``seqkit_gui/__init__.py``, so a bundle can never disagree with
the source it was built from, and ``tests/test_release_consistency.py`` pins the
last remaining name shared between the two halves of the project (``APP_NAME``
here and the project name in ``pyproject.toml``).
"""

import os
import platform
import re

# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------
# SPECPATH is injected by PyInstaller and is the directory of this spec file.
ROOT = os.path.abspath(os.path.join(SPECPATH, os.pardir))
PKG = os.path.join(ROOT, "seqkit_gui")
# packaging/entry.py imports through the package name; using seqkit_gui/main.py here
# would bundle it without package context and break its relative imports at run time.
ENTRY = os.path.join(SPECPATH, "entry.py")

# ``onedir`` (the release default) or ``onefile`` (one self-contained exe); see
# the docstring. Anything else is a typo and stops the build here rather than
# producing an unintended layout.
BUNDLE_MODE = os.environ.get("SEQKIT_GUI_BUNDLE", "onedir").strip().lower()
if BUNDLE_MODE not in ("onedir", "onefile"):
    raise SystemExit(
        "seqkit_gui.spec: SEQKIT_GUI_BUNDLE must be 'onedir' or 'onefile', got %r"
        % os.environ.get("SEQKIT_GUI_BUNDLE", ""))

# The name of the built folder, of the executable inside it and -- under onefile
# -- of the single exe. The human-facing display name is ``SeqKit GUI`` (with a
# space) and is set by the application itself; the hyphenated spelling here is
# only the file-system name, and it is kept aligned with the ``name`` field of
# pyproject.toml by tests/test_release_consistency.py.
APP_NAME = "SeqKit-GUI"

# Resource folders carried into the bundle, each landing at
# ``<bundle>/seqkit_gui/<folder>`` so that ``seqkit_gui/core/paths.py`` resolves
# them exactly as it does in a source checkout. ``data`` holds commands.json and
# is mandatory -- the app refuses to start without it (exit code 2) -- while
# ``i18n`` and ``assets`` are optional: their absence is reported and the app
# falls back to embedded strings and the default icon. A partial checkout can
# therefore still build; a *release* may not ship without them, and
# ``python packaging/check_version.py`` (the first step of the release job)
# requires commands.json, both language tables and app.ico to exist and be
# non-empty before PyInstaller is started.
RESOURCE_FOLDERS = ("data", "i18n", "assets")
MANDATORY_FOLDERS = ("data",)



def read_project_metadata():
    """``(version, display_name)`` scraped out of ``seqkit_gui/__init__.py``.

    Read as text rather than imported: a spec file runs on the build machine
    before PyInstaller has collected anything, and importing the package would
    drag PySide6 into the build itself. ``seqkit_gui/__init__.py`` stays the one
    place a version is written down; a bundle can therefore never disagree with
    the source it was built from.
    """
    init = os.path.join(PKG, "__init__.py")
    try:
        with open(init, encoding="utf-8") as handle:
            text = handle.read()
    except OSError as error:
        raise SystemExit(f"seqkit_gui.spec: cannot read {init}: {error}")
    version = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
    display = re.search(r'^APP_NAME\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
    if version is None or display is None:
        raise SystemExit(
            "seqkit_gui.spec: seqkit_gui/__init__.py must define __version__ and "
            "APP_NAME; found: "
            + ", ".join(n for n, m in (("__version__", version), ("APP_NAME", display)) if m is None)
        )
    return version.group(1), display.group(1)


VERSION, PRODUCT_NAME = read_project_metadata()


def icon_path():
    """The platform-appropriate icon, or ``None`` to use the PyInstaller default.

    Windows takes the ``.ico`` directly. macOS can only use an ``.icns``: PyInstaller
    would try to convert a ``.ico`` with Pillow and fail the whole build when Pillow
    is absent, so the macOS branch simply passes no icon until a real ``app.icns``
    is added to ``seqkit_gui/assets``.
    """
    assets = os.path.join(PKG, "assets")
    wanted = "app.icns" if platform.system() == "Darwin" else "app.ico"
    candidate = os.path.join(assets, wanted)
    if os.path.isfile(candidate):
        return candidate
    print("seqkit_gui.spec: no %s in seqkit_gui/assets, using the default icon" % wanted)
    return None


ICON = icon_path()


def package_data(folder):
    """Tuple list carrying ``seqkit_gui/<folder>`` into ``seqkit_gui/<folder>``.

    ``data/`` must exist (the app is unusable without the command schema); the
    optional folders are skipped with a notice so a partial checkout still builds.
    """
    source = os.path.join(ROOT, "seqkit_gui", folder)
    destination = os.path.join("seqkit_gui", folder)
    if os.path.isdir(source) and os.listdir(source):
        return [(source, destination)]
    message = "seqkit_gui.spec: resource directory missing or empty: %s" % source
    if folder in MANDATORY_FOLDERS:
        raise SystemExit(message + " -- commands.json has to be generated first "
                                   "(python tools/extract_spec.py --build)")
    print(message + ", skipped")
    return []


# ---------------------------------------------------------------------------
# Licence documents that have to travel with the release
# ---------------------------------------------------------------------------
# LGPL-3.0 sections 4 and 6, and GPLv3 section 4(a), are satisfied only when a
# copy of the licence is conveyed *with* the work; a URL or a promise to supply
# it later is not a copy. The bundle therefore carries this project's own MIT
# ``LICENSE``, the ``THIRD-PARTY-LICENSES.md`` inventory, and a verbatim copy of
# every option the PySide6 wheel offers (``LGPL-3.0-only OR GPL-2.0-only OR
# GPL-3.0-only``), so whichever option a recipient relies on is readable offline.
# ``LICENSES/*.txt`` is byte-for-byte the gnu.org text -- see
# THIRD-PARTY-LICENSES.md -- and nothing below rewrites or reflows it.
#
# Destination mirrors the repository layout, so an archive reader finds the same
# names the compliance notes promise: onedir puts every data file under the
# contents directory, which makes the bundle hold
# ``SeqKit-GUI/_internal/LICENSE``, ``.../_internal/THIRD-PARTY-LICENSES.md`` and
# ``.../_internal/LICENSES/*.txt``. ``_internal/`` is not compressed or hidden --
# it is the directory that holds the swappable ``Qt6*.dll`` the LGPL's replacement
# rights point at, so the texts sit in the very tree a recipient must open to
# exercise those rights. ``tools/license_check.py`` CHECK 4 walks the whole bundle
# and counts these (it wants at least one ``*lgpl*.txt``, which it finds).
LICENCE_DIR = os.path.join(ROOT, "LICENSES")
LICENCE_ROOT_FILES = ("LICENSE", "THIRD-PARTY-LICENSES.md")


def licence_documents():
    """``[(source, destination), ...]`` for the files a release must convey.

    A data destination is a *directory* inside the contents folder, not a file
    name: ``(x, "LICENSE")`` would create ``_internal/LICENSE/LICENSE``. So the
    two repository-root documents go to ``"."`` and the option texts to
    ``"LICENSES"``.

    Absent licence documents fail the build: a bundle without them is not
    shippable, and discovering that after PyInstaller finished wastes a release.
    """
    wanted = [(os.path.join(ROOT, name), ".") for name in LICENCE_ROOT_FILES]
    if os.path.isdir(LICENCE_DIR):
        wanted += [(os.path.join(LICENCE_DIR, name), "LICENSES")
                   for name in sorted(os.listdir(LICENCE_DIR))
                   if name.lower().endswith(".txt")]
    missing = [src for src, _dst in wanted if not os.path.isfile(src)]
    if missing:
        raise SystemExit("seqkit_gui.spec: licence document missing: "
                         + ", ".join(missing))
    if not any("lgpl" in os.path.basename(src).lower() for src, _dst in wanted):
        raise SystemExit("seqkit_gui.spec: LICENSES/ holds no LGPL text, and the "
                         "bundle is conveyed under PySide6's LGPL option.")
    for src, dst in wanted:
        # A destination that repeats the file's own name nests the file inside a
        # directory of the same name (``_internal/LICENSE/LICENSE``), which reads
        # as a missing licence document to anyone opening the bundle.
        if os.path.basename(dst.rstrip("/\\")) == os.path.basename(src):
            raise SystemExit("seqkit_gui.spec: licence destination %r repeats the "
                             "file name %r -- use a directory, not a file name."
                             % (dst, os.path.basename(src)))
    return wanted


# ---------------------------------------------------------------------------
# GPL-only Qt modules are filtered out of the collected binaries
# ---------------------------------------------------------------------------
# Qt publishes VirtualKeyboard under GPL-3.0 only -- it has no LGPL option --
# while this bundle is conveyed under PySide6's LGPL option. Carrying the module
# inside the same archive puts both grant texts on one distribution and pushes
# the whole bundle onto the GPL path, so it goes. The rest of the list is the
# closure it dragged in and nothing else needs (Qt6Quick -> Qt6Qml, Qt6QmlMeta,
# Qt6QmlModels, Qt6QmlWorkerScript, Qt6OpenGL): about 15 MB.
#
# A Python-level ``excludes`` entry cannot remove any of this -- these arrive as
# *binary* dependencies of a Qt plugin, not as importable modules -- so they are
# filtered from the already-collected TOC instead. The removal is safe because
# the chain has exactly one root: ``qtvirtualkeyboardplugin.dll`` is imported by
# nothing, ``Qt6VirtualKeyboard.dll`` is imported only by that plugin, and
# ``platforms/qwindows.dll`` links just Qt6Core/Qt6Gui (verified from the PE
# import tables of the shipped build). Qt's input-context loader finds no plugin
# and falls back to the platform IME handling inside qwindows.dll.
GPL_ONLY_QT_BINARIES = frozenset({
    "qt6virtualkeyboard.dll",
    "qtvirtualkeyboardplugin.dll",
    "qt6quick.dll",
    "qt6qml.dll",
    "qt6qmlmeta.dll",
    "qt6qmlmodels.dll",
    "qt6qmlworkerscript.dll",
    "qt6opengl.dll",
})

# Plugins the app and the release job depend on: ``qwindows`` is the only way a
# Windows GUI opens, ``qoffscreen`` is what CI uses, ``qdirect2d`` and
# ``qminimal`` are Qt's own fallbacks. Asserting them here means a filter that
# is later widened cannot silently produce a bundle that dies on start-up.
REQUIRED_PLATFORM_PLUGINS = {
    # Qt spells one plugin file per OS: a Windows bundle has no libqxcb.so to lose,
    # so each key only asserts the files that platform's build can actually collect.
    "Windows": ("qwindows.dll", "qoffscreen.dll", "qdirect2d.dll", "qminimal.dll"),
    "Darwin": ("libqcocoa.dylib",),
    "Linux": ("libqxcb.so", "libqminimal.so"),
}


def _is_gpl_only_qt(toc_entry):
    """True when a collected TOC entry names one of the GPL-only binaries.

    Both halves are tested because the destination name is the one a bundle
    reader sees while the source name is the one a hook picked.
    """
    for field in toc_entry[:2]:
        base = os.path.basename(str(field).replace("\\", "/")).lower()
        if base in GPL_ONLY_QT_BINARIES:
            return True
    return False


def drop_gpl_only_qt(binaries):
    """Remove the GPL-only binaries from ``a.binaries`` in place, and report it."""
    kept = [entry for entry in binaries if not _is_gpl_only_qt(entry)]
    dropped = [entry for entry in binaries if _is_gpl_only_qt(entry)]
    if dropped:
        binaries[:] = kept
        size = sum(_file_size(entry) for entry in dropped)
        print("seqkit_gui.spec: dropped %d GPL-only Qt binaries, %.1f MB: %s"
              % (len(dropped), size / 1048576.0,
                 ", ".join(sorted(os.path.basename(str(e[0])) for e in dropped))))
    return dropped


def _file_size(toc_entry):
    try:
        return os.path.getsize(str(toc_entry[1]))
    except OSError:
        return 0


def require_platform_plugins(binaries):
    """Fail the build if the filtering removed a plugin the app cannot run without."""
    present = {os.path.basename(str(entry[0]).replace("\\", "/")).lower()
               for entry in binaries}
    absent = [name for name in REQUIRED_PLATFORM_PLUGINS.get(platform.system(), ())
              if name not in present]
    if absent:
        raise SystemExit(
            "seqkit_gui.spec: required Qt platform plugin(s) not collected: "
            + ", ".join(absent)
            + " -- without them the window cannot open, on any backend.")


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------
datas = []
for _folder in RESOURCE_FOLDERS:
    datas += package_data(_folder)
LICENCE_DOCUMENTS = licence_documents()
datas += LICENCE_DOCUMENTS

# The app imports PySide6 (QtCore/QtGui/QtWidgets), its own package and the
# standard library only -- verified across seqkit_gui/ with no dynamic imports --
# so the bundled PyInstaller hooks for PySide6/shiboken6 need no help here.
hiddenimports = []

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
a = Analysis(
    [ENTRY],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Never imported by this app, but easy to pick up transitively on a machine
    # that happens to have them installed (a bioinformatics workstation usually
    # does). Excluding them keeps the bundle identical wherever it is built.
    # Qt's own modules are deliberately NOT excluded: which of them are needed is
    # decided by PySide6's hooks from the real link-time dependencies, and
    # guessing wrong here produces a bundle that dies on start-up.
    # The size question is real and measured, on a Windows onedir build of this
    # recipe: 143 MB in the folder, of which the user-supplied bin/seqkit.exe is
    # 28 MB. Inside _internal, Qt6Quick (6.8 MB), Qt6Qml and its three helpers
    # (6.6 MB), Qt6Pdf (4.6 MB), Qt6OpenGL (2.0 MB), Qt6Network (1.8 MB),
    # Qt6Svg (0.6 MB), Qt6VirtualKeyboard (0.4 MB), opengl32sw.dll (20.6 MB),
    # libcrypto-3-x64.dll (5.8 MB) and the qdirect2d plugin (1.1 MB) are all
    # reachable only through Qt's own plugin dependency graph -- the application
    # imports QtCore, QtGui and QtWidgets and nothing else -- so they arrive as
    # plugins' dependencies, not as Python imports, and a Python-level
    # `excludes` entry does not remove them. The GPL-only ones and the closure
    # they drag in are filtered from the collected TOC below, which is both the
    # licence-correct and the size-reducing move; the LGPL modules that are
    # merely large (Qt6Pdf, Qt6Network, Qt6Svg, opengl32sw.dll) stay, because
    # dropping a module that is merely big risks the window not opening at all.
    excludes=[
        "tkinter",
        "numpy",
        "scipy",
        "pandas",
        "matplotlib",
        "PIL",
        "IPython",
        "pytest",
    ],
    noarchive=False,
)

# SeqKit itself must never end up inside the bundle (see this file's docstring).
# Analysis has already walked the entry script, so every collected entry can be
# checked here: nothing that came from the repository's bin/ may be in the build.
# TOC entries are (destination, source, type) tuples, so both paths are tested.
_forbidden = os.path.normcase(os.path.join(ROOT, "bin") + os.sep)
_collected = [
    os.path.normcase(str(field))
    for entry in list(a.scripts) + list(a.binaries) + list(a.datas)
    for field in entry[:2]
]
_strays = sorted({field for field in _collected if field.startswith(_forbidden)})
if _strays:
    raise SystemExit(
        "seqkit_gui.spec: refusing to bundle seqkit -- these collected files come "
        "from bin/: " + ", ".join(_strays)
        + ". SeqKit is upstream software and is not redistributed from this project."
    )

# GPL-only Qt modules have no place in a bundle conveyed under the LGPL option,
# and filtering the collected TOC is the only lever that reaches them (see the
# comment on GPL_ONLY_QT_BINARIES). The platform-plugin guard runs *after* the
# filter on purpose: it proves the filter left behind what a window needs.
drop_gpl_only_qt(a.binaries)
require_platform_plugins(a.binaries)

print("seqkit_gui.spec: %s %s (%s), bundle=%s, %d resource folders, "
      "%d licence documents, icon=%s"
      % (APP_NAME, VERSION, platform.system(), BUNDLE_MODE,
         len(datas) - len(LICENCE_DOCUMENTS), len(LICENCE_DOCUMENTS),
         ICON or "default"))

pyz = PYZ(a.pure)

# The two modes share every ingredient above -- entry point, resources, licence
# documents, GPL filter, plugin guard and icon -- and differ only in how those
# ingredients are wrapped: onedir keeps binaries/datas as loose files beside a
# stub EXE (COLLECT writes the folder), onefile packs them all into the EXE
# itself and there is no COLLECT step.
_bundle_common = dict(
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # windowed: no console window behind the GUI on Windows. Console output of
    # the seqkit child process is captured by QProcess into the Log tab anyway.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon_path() has already chosen app.ico on Windows or app.icns on macOS when
    # the file is present; None leaves PyInstaller's own icon in place.
    icon=ICON,
)

if BUNDLE_MODE == "onefile":
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        exclude_binaries=False,
        **_bundle_common,
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        **_bundle_common,
    )

    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=False,
        name=APP_NAME,
    )
