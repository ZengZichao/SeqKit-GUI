"""Behaviour when seqkit is missing, damaged or the wrong version, and persistence.

The store-dependent cases take ``fresh_settings``: the recent-files list is written
by every windowed run, so a session-wide store would make the expected length depend
on which tests happened to run first.
"""

import os
import platform
import sys
from pathlib import Path

import pytest

from seqkit_gui.core import seqkit_locator
from seqkit_gui.core.paths import executable_names
from seqkit_gui.core.settings import Preferences
from seqkit_gui.core.spec import load
from seqkit_gui.ui.i18n import Catalog
from seqkit_gui.ui.main_window import MainWindow


def _native_payload(name: str) -> tuple[bytes, bool]:
    """Bytes a native-image check accepts on this platform, plus the exec bit."""
    if platform.system() == "Windows":
        return b"MZ\x90\x00\x03\x00\x00\x00 placeholder image header", False
    return b"#!/bin/sh\nexit 0\n", True


def _write_seqkit(directory: Path) -> Path:
    """A file that reads as a runnable seqkit, dropped into ``directory``."""
    directory.mkdir(parents=True, exist_ok=True)
    payload, executable = _native_payload(executable_names()[0])
    path = directory / executable_names()[0]
    path.write_bytes(payload)
    if executable:
        path.chmod(0o755)
    return path


def _search_confined_to(monkeypatch, tmp_path, path_dirs: tuple[Path, ...] = (),
                        stub_which: bool = True):
    """Cut the search down to the folders this test names.

    ``locate()`` walks bundled locations, the configured path, ``shutil.which`` and
    every absolute PATH entry, plus the macOS install prefixes. Each of those reaches
    outside the test: a machine with seqkit installed -- a developer laptop, a CI
    image that ran the fetch tool once -- answers a "nothing exists" assertion with a
    real binary. Stubbing ``shutil.which`` alone is not enough, because the PATH walk
    is a second, independent route to the same file.
    """
    from seqkit_gui.core import paths

    nowhere = tmp_path / "nowhere"
    nowhere.mkdir(exist_ok=True)
    monkeypatch.setattr(paths, "bundled_dir", lambda: nowhere)
    monkeypatch.setattr(paths, "project_root", lambda: nowhere)
    monkeypatch.setattr(seqkit_locator, "_DARWIN_PREFIXES", (str(nowhere / "opt"),))
    if stub_which:
        monkeypatch.setattr(seqkit_locator.shutil, "which", lambda name: None)
    monkeypatch.setenv("PATH", os.pathsep.join(str(item) for item in path_dirs))
    return nowhere


def test_locator_reports_not_found_when_nothing_exists(tmp_path, monkeypatch):
    """No binary anywhere reachable, and the reason is reported rather than guessed."""
    nowhere = _search_confined_to(monkeypatch, tmp_path)
    found = seqkit_locator.locate(str(nowhere / "nope" / "seqkit.exe"))
    assert not found.found
    assert found.source == "not-found"
    assert found.path is None


def test_a_seqkit_reachable_only_through_path_is_discovered(tmp_path, monkeypatch):
    """A binary that lives on PATH has to be found there, not just in bin/.

    The counterpart of the case above: PATH is walked by the search itself, so a
    machine-wide seqkit install is a location the launcher's "leave it on PATH" hint
    can honestly point at. ``shutil.which`` is stubbed out here so the only route to
    the file is the hand-walked PATH list.
    """
    on_path = _write_seqkit(tmp_path / "onpath")
    _search_confined_to(monkeypatch, tmp_path, path_dirs=(on_path.parent,))
    found = seqkit_locator.locate("")
    assert found.found, found.detail
    assert found.source == "path"
    assert found.path == on_path.resolve()


def test_a_seqkit_reachable_only_through_path_is_discovered_without_which(
        tmp_path, monkeypatch):
    """The same file is found when ``shutil.which`` is left working.

    Two independent routes into the same folder have to agree; the ``which`` result is
    expanded to the directory the search walks, so both end on one candidate.
    """
    from seqkit_gui.core import paths

    on_path = _write_seqkit(tmp_path / "onpath")
    nowhere = tmp_path / "nowhere"
    nowhere.mkdir(exist_ok=True)
    monkeypatch.setattr(paths, "bundled_dir", lambda: nowhere)
    monkeypatch.setattr(paths, "project_root", lambda: nowhere)
    monkeypatch.setattr(seqkit_locator, "_DARWIN_PREFIXES", (str(nowhere / "opt"),))
    monkeypatch.setenv("PATH", str(on_path.parent) + os.pathsep + str(nowhere))
    found = seqkit_locator.locate("")
    assert found.found, found.detail
    assert found.source == "path"
    assert found.path == on_path.resolve()


def test_a_seqkit_next_to_the_app_is_not_reported_as_a_path_hit(tmp_path, monkeypatch):
    """The folder the app was started from is not one of the PATH locations.

    This is the boundary the launcher's "leave it on PATH" hint depends on: a seqkit
    found that way is found in a real PATH directory, while a file somebody dropped
    into the launch folder is refused with a reason instead of being executed as
    though it had come from PATH.
    """
    launched_from = tmp_path / "launch"
    planted = _write_seqkit(launched_from)
    _search_confined_to(monkeypatch, tmp_path, path_dirs=(tmp_path,), stub_which=False)
    monkeypatch.chdir(launched_from)
    found = seqkit_locator.locate("")
    assert not found.found, f"{planted} was discovered from the working directory"
    assert found.source == "not-found"
    assert "never trusted" in found.detail, found.detail


def test_a_stale_configured_path_falls_back_instead_of_failing(tmp_path, seqkit_binary):
    """A remembered path that no longer exists must not break the search."""
    found = seqkit_locator.locate(str(tmp_path / "removed" / "seqkit.exe"))
    assert found.found
    assert found.source in {"bundled", "path"}


def test_locator_prefers_the_configured_path_over_bundled(tmp_path, monkeypatch):
    configured = tmp_path / executable_names()[0]
    configured.write_bytes(b"placeholder")
    monkeypatch.setattr(seqkit_locator, "_runnable", lambda path: True)
    found = seqkit_locator.locate(str(configured))
    assert found.source == "configured"
    assert found.path == configured


def test_probe_version_survives_a_non_executable(tmp_path):
    bogus = tmp_path / "not-a-program.exe"
    bogus.write_text("hello", encoding="utf-8")
    assert seqkit_locator.probe_version(bogus) == ""


def _isolated_search(monkeypatch, tmp_path):
    """Leave the search with nothing but the path the user configured."""
    _search_confined_to(monkeypatch, tmp_path)


def test_a_text_file_configured_as_seqkit_is_refused_with_a_reason(tmp_path, monkeypatch,
                                                                   fake_binary):
    """A non-native file may never be handed to CreateProcess, and must say why."""
    _isolated_search(monkeypatch, tmp_path)
    for label, path in (("plain text", fake_binary.text()), ("zero bytes", fake_binary.zero_bytes())):
        found = seqkit_locator.locate(str(path))
        assert not found.found, f"{label} was accepted as the configured binary"
        assert found.source == "not-found"
        assert "native executable" in found.detail, (label, found.detail)


def test_a_folder_configured_as_seqkit_is_refused(tmp_path, monkeypatch, fake_binary):
    _isolated_search(monkeypatch, tmp_path)
    found = seqkit_locator.locate(str(fake_binary.directory()))
    assert not found.found
    assert found.source == "not-found"


def test_a_batch_file_named_seqkit_is_refused_on_windows(tmp_path, monkeypatch):
    """``seqkit.bat`` is locatable by name and is the standard hijack vehicle."""
    _isolated_search(monkeypatch, tmp_path)
    script = tmp_path / "nowhere" / "seqkit.bat"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_bytes(b"@echo off\r\necho planted\r\n")
    found = seqkit_locator.locate(str(script))
    if executable_names()[0] != "seqkit.exe":
        pytest.skip("the script-suffix refusal is a Windows rule")
    assert not found.found
    assert "batch or script" in found.detail, found.detail


def test_a_truncated_download_still_reads_as_a_native_image(fake_binary):
    """What the magic-number gate cannot catch, the version probe has to.

    A download cut short keeps its ``MZ`` header, so :func:`is_native_executable`
    accepts it; the reason it must still be reported to the user is that running it
    fails, and :func:`probe_version` is the only step that notices before the first
    command does.
    """
    truncated = fake_binary.truncated()
    if truncated is None:
        pytest.skip("no reference seqkit binary to truncate")
    assert seqkit_locator.is_native_executable(truncated)
    assert seqkit_locator.probe_version(truncated, timeout=10) == ""
    assert not seqkit_locator.looks_like_seqkit("")


def test_another_native_program_is_not_mistaken_for_seqkit(fake_binary):
    other = fake_binary.native_other()
    if other is None:
        pytest.skip("no foreign native executable available to copy")
    assert seqkit_locator.is_native_executable(other)
    assert not seqkit_locator.looks_like_seqkit(seqkit_locator.probe_version(other, timeout=10))
    assert seqkit_locator.looks_like_seqkit("seqkit v2.14.0 867f2c5")
    assert not seqkit_locator.looks_like_seqkit("where: could not find files")
    assert not seqkit_locator.looks_like_seqkit("seqkit")


def test_a_version_that_is_not_the_one_the_table_describes_is_badged(
        seqkit_binary, qapp, root, monkeypatch):
    """The forms come from 2.14.0 source; another binary has to be flagged, not hidden."""
    catalog = Catalog("en_US", directory=root / "seqkit_gui" / "i18n")
    monkeypatch.setattr(seqkit_locator, "probe_version",
                        lambda path, timeout=4.0: "seqkit v2.9.0 1f2e3d4")
    window = MainWindow(catalog, Preferences(seqkit_path="", language="en_US"), load())
    try:
        window.show()
        qapp.processEvents()
        assert window.seqkit_path is not None, "a mismatching version must still be located"
        assert window.version_warning.isVisible()
        assert window.version_warning.text() == catalog.tr("Version mismatch")
        tip = window.version_warning.toolTip()
        assert "2.14.0" in tip and "2.9.0" in tip, tip
        assert window.seqkit_chip.text() == "SeqKit 2.9.0"
    finally:
        window.deleteLater()


def test_the_matching_version_shows_no_warning(seqkit_binary, qapp, root):
    catalog = Catalog("en_US", directory=root / "seqkit_gui" / "i18n")
    window = MainWindow(catalog, Preferences(seqkit_path="", language="en_US"), load())
    try:
        window.show()
        qapp.processEvents()
        assert window.seqkit_version_text, "the shipped binary should report a version"
        assert not window.version_warning.isVisible()
        assert window.seqkit_chip.text() == f"SeqKit {window._detected_version()}"
    finally:
        window.deleteLater()


def test_missing_seqkit_is_surfaced_in_the_window(qapp, root, monkeypatch):
    monkeypatch.setattr(seqkit_locator, "locate",
                        lambda configured="": seqkit_locator.Located(None, "not-found"))
    catalog = Catalog("zh_CN", directory=root / "seqkit_gui" / "i18n")
    window = MainWindow(catalog, Preferences(seqkit_path="", language="zh_CN"), load())
    assert window.seqkit_path is None
    assert window.seqkit_chip.text() == catalog.tr("seqkit not found")
    assert catalog.tr("seqkit_missing_hint") in window.status_left.text()

    warnings = []
    from seqkit_gui.ui import main_window as module
    monkeypatch.setattr(module.QMessageBox, "warning",
                        lambda *args, **kwargs: warnings.append(args[2] if len(args) > 2 else ""))
    # run() offers to open Settings after the warning; the dialog is modal.
    monkeypatch.setattr(window, "open_settings", lambda: None)
    window.run()
    assert warnings, "running without seqkit must be reported, not silently ignored"
    window.deleteLater()


def test_preferences_round_trip(fresh_settings):
    original = Preferences(
        seqkit_path="C:/example/seqkit.exe",
        language="en_US",
        theme="dark",
        output_line_limit=12345,
        working_dir="C:/work",
    )
    original.save()
    restored = Preferences.load()
    assert restored.seqkit_path == original.seqkit_path
    assert restored.language == "en_US"
    assert restored.theme == "dark"
    assert restored.output_line_limit == 12345
    assert restored.working_dir == "C:/work"


def test_recent_files_are_deduplicated_and_capped(fresh_settings):
    from seqkit_gui.core import settings as store
    for index in range(30):
        store.push_recent_file(f"C:/data/seq{index % 5}.fa")
    recent = store.recent_files()
    assert len(recent) == 5
    assert recent[0] == "C:/data/seq4.fa", "most recent first"
    assert len(set(recent)) == len(recent)


def test_recent_files_stop_growing_at_the_declared_limit(fresh_settings):
    """The cap is what keeps the File menu and the stored list bounded.

    ``push_recent_file`` reads through ``recent_files()`` and writes back the same
    ``RECENT_FILES_LIMIT``, so what the File menu shows and what the store keeps
    are the same list. This pins the constant rather than restating the source.
    """
    from seqkit_gui.core import settings as store
    from seqkit_gui.core.settings import KEY_RECENT_FILES, RECENT_FILES_LIMIT

    for index in range(60):
        store.push_recent_file(f"C:/data/unique{index}.fa")
    recent = store.recent_files()
    assert len(recent) == RECENT_FILES_LIMIT, "the interface reaches at most recent_files()'s limit"
    assert recent[0] == "C:/data/unique59.fa"
    stored = store.read(KEY_RECENT_FILES, [])
    if isinstance(stored, str):
        stored = [stored]
    assert len(stored) <= RECENT_FILES_LIMIT, f"the stored list grew past the cap: {len(stored)}"


def test_a_fresh_store_holds_nothing_from_the_developers_machine(fresh_settings):
    from seqkit_gui.core import settings as store
    assert store.recent_files() == []
    assert Preferences.load() == Preferences()


def test_the_store_a_run_writes_into_is_a_file_in_pythons_own_scratch_area(
        tmp_path_factory):
    """Preferences and the recent-files list go to a scratch ini, never to the user's.

    ``QSettings(ORGANIZATION, APPLICATION)`` on Windows is a registry key and on the
    other platforms the very file the application reads at startup, so a suite that
    reached it would rewrite the preferences of whoever ran it -- and two concurrent
    runs would overwrite each other. ``conftest`` replaces the one function that builds
    a store, which puts every read and write in this run inside pytest's temporary root;
    this pins that the replacement is actually in force and points where it claims to.
    """
    from seqkit_gui.core import settings as store

    basetemp = Path(tmp_path_factory.getbasetemp()).resolve()
    live = store.settings()
    location = Path(live.fileName())
    assert location.suffix == ".ini", (
        f"the store is not an ini file but {live.fileName()!r}: a registry or XDG path "
        "here means the session isolation is not installed")
    assert basetemp in location.parents or location.is_relative_to(basetemp), (
        f"{location} is outside this run's scratch root {basetemp}")
    assert "HKEY" not in live.fileName().upper(), live.fileName()


def test_a_value_written_by_a_test_lands_in_that_file_and_nowhere_else(
        fresh_settings, tmp_path):
    """The proof is the bytes on disk: a write appears in the scratch ini, key and all."""
    from seqkit_gui.core import settings as store

    store.write("a3-hygiene-probe", "written-by-the-suite")
    store.settings().sync()
    text = fresh_settings.read_text(encoding="utf-8", errors="replace")
    assert "a3-hygiene-probe" in text and "written-by-the-suite" in text, text
    assert store.read("a3-hygiene-probe", "") == "written-by-the-suite"


def _construction_lines(path: Path) -> list[str]:
    """Lines where ``QSettings`` is *called*, ignoring imports, annotations and prose.

    ``tokenize`` rather than a text scan: a docstring explaining what the real store is
    must not read like a test that builds one.
    """
    import io
    import tokenize

    tokens = [item for item in tokenize.generate_tokens(
        io.StringIO(path.read_text(encoding="utf-8")).readline)
        if item.type in (tokenize.NAME, tokenize.OP)]
    lines = []
    for index, token in enumerate(tokens[:-1]):
        if token.string == "QSettings" and tokens[index + 1].string == "(":
            lines.append(token.line.strip())
    return lines


def test_only_core_settings_builds_a_store_and_no_test_builds_the_real_one(root):
    """One construction site, one redirection, and nothing in ``tests/`` that bypasses it.

    A store built anywhere else would be built at import time or in a fixture that ran
    before the session isolation took hold, and would write to the developer's registry
    entry or preferences file either way.
    """
    app_sites = []
    for path in sorted((root / "seqkit_gui").rglob("*.py")):
        built = _construction_lines(path)
        if built:
            app_sites.append((path.relative_to(root).as_posix(), len(built)))
    assert app_sites == [("seqkit_gui/core/settings.py", 1)], (
        f"a store is constructed outside the one redirected factory: {app_sites}")

    offenders = {}
    for path in sorted((root / "tests").glob("test_*.py")):
        built = _construction_lines(path)
        if built:
            offenders[path.name] = built
    assert offenders == {}, (
        f"these test files build their own store instead of taking the conftest "
        f"fixture: {offenders}")

    conftest = root / "tests" / "conftest.py"
    built = _construction_lines(conftest)
    assert built, "conftest is expected to build the redirected store"
    for line in built:
        assert "IniFormat" in line, line




def test_schema_reports_the_counts_the_interface_shows():
    schema = load()
    assert len(schema.usable) == 41
    assert schema.flag_entries == 353
    assert len(schema.global_flag_names) == 11
    assert len(schema.groups) == 8


def test_stats_shadows_the_inherited_skip_file_check():
    """stats declares its own -S, so the flag must not be offered twice."""
    schema = load()
    command = schema.get("stats")
    local = {flag.name for flag in command.flags}
    assert "skip-file-check" in local
    assert "skip-file-check" not in {flag.name for flag in command.global_flags}
    names = [flag.name for flag in command.all_flags]
    assert len(names) == len(set(names))


def test_executable_names_are_platform_specific():
    names = executable_names()
    assert names[0] in {"seqkit.exe", "seqkit"}
    assert Path("seqkit").name in names
