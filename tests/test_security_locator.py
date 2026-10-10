"""Where the application looks for ``seqkit`` is a trust decision, not a convenience.

The located binary is executed as soon as the window opens (``seqkit version``), so a
planted file that merely *looks* like seqkit is enough to run code. The rules under
test here are the ones in :mod:`seqkit_gui.core.seqkit_locator` that keep the search
inside the folders the user chose: a candidate sitting in the working directory is
never trusted, PATH entries that mean "the working directory" are dropped, and a
candidate has to read as a native image.

Measured on this machine's Python 3.10: with ``PATH`` pointing somewhere else,
``shutil.which("a2whichprobe.exe")`` still returned ``.\\a2whichprobe.exe`` for a file
sitting in the current directory -- the Windows behaviour that makes the working
directory rule necessary rather than decorative.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from seqkit_gui.core import paths, seqkit_locator

def native_head() -> bytes:
    """The first magic number this platform's loader accepts."""
    import platform

    group = seqkit_locator._NATIVE_MAGICS.get(platform.system())
    return (group or seqkit_locator._ALL_MAGICS)[0]


def plant(directory, name=None) -> str:
    """A file shaped like a native image, under the name the search looks for."""
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / (name or paths.executable_names()[0])
    target.write_bytes(native_head() + b"\x00" * 512)
    if os.name != "nt":
        target.chmod(0o755)
    return str(target)


@pytest.fixture
def isolated(monkeypatch, tmp_path):
    """No bundled folder, no project bin/, and PATH held by the test."""
    def use(path_dirs=()):
        empty = tmp_path / "no-bundle"
        empty.mkdir(exist_ok=True)
        monkeypatch.setattr(paths, "bundled_dir", lambda: empty)
        monkeypatch.setattr(paths, "project_root", lambda: tmp_path / "no-project")
        monkeypatch.setenv("PATH", os.pathsep.join(str(item) for item in path_dirs))
    return use


def test_a_binary_in_the_working_directory_is_never_used(isolated, monkeypatch, tmp_path):
    """Even with the cwd named on PATH, the candidate next to the app is refused."""
    cwd = tmp_path / "launch-dir"
    planted = plant(cwd)
    isolated([cwd])
    monkeypatch.chdir(cwd)

    found = seqkit_locator.locate("")

    assert not found.found, found
    assert found.source == "not-found"
    assert "not in a folder this search looks in" in found.detail, found.detail
    # The file itself would pass every content check; only the folder rule stops it.
    assert seqkit_locator._runnable(Path(planted))


def test_a_relative_path_entry_is_not_a_way_back_into_the_working_directory(
        isolated, monkeypatch, tmp_path):
    """``PATH=bin`` resolved against the launch folder is the same plant by another road.

    This is the case a hand-walked PATH handles and ``shutil.which`` does not: the
    entry is relative, so which() answers with a file under the working directory and
    reports it as a PATH hit.
    """
    cwd = tmp_path / "launch-dir"
    nested = cwd / "bin"
    planted = plant(nested)
    isolated([])
    monkeypatch.setenv("PATH", "bin")
    monkeypatch.chdir(cwd)

    found = seqkit_locator.locate("")

    assert not found.found, found
    assert seqkit_locator._runnable(Path(planted)), "the refusal should be about the folder"


def test_the_path_hit_is_still_found_after_the_working_directory_is_refused(
        isolated, monkeypatch, tmp_path):
    """Refusing one candidate must not end the search: PATH is walked to the end."""
    cwd = tmp_path / "launch-dir"
    plant(cwd)
    real = tmp_path / "installed"
    expected = plant(real)
    isolated([real])
    monkeypatch.chdir(cwd)

    found = seqkit_locator.locate("")

    assert found.found, found.detail
    assert found.source == "path"
    assert str(found.path) == expected


def test_the_search_walks_path_itself_rather_than_trusting_which(
        isolated, monkeypatch, tmp_path):
    """The folder list is built from PATH entries, not from what which() volunteers.

    ``shutil.which`` is stubbed out here to prove the walk is what finds the binary:
    a search that only asked which() would answer "not found", and would have been
    trusting a channel that resolves relative entries against the working directory.
    """
    directory = tmp_path / "installed"
    expected = plant(directory)
    isolated([directory])
    monkeypatch.setattr(seqkit_locator.shutil, "which", lambda name: None)

    found = seqkit_locator.locate("")

    assert found.found, found.detail
    assert str(found.path) == expected
    assert found.source == "path"


def test_relative_and_empty_path_entries_are_not_searched(isolated, monkeypatch, tmp_path):
    """A ``PATH`` entry of "" or a relative name means "here", which is not trusted."""
    cwd = tmp_path / "launch-dir"
    nested = cwd / "subdir"
    plant(nested)
    isolated([])
    monkeypatch.setenv("PATH", os.pathsep.join(["", "subdir", "."]))
    monkeypatch.chdir(cwd)

    assert not seqkit_locator.locate("").found


def test_a_non_executable_payload_named_like_seqkit_is_refused(isolated, tmp_path):
    """An HTML error page saved as the binary name must not reach CreateProcess."""
    directory = tmp_path / "installed"
    plant(directory, name="not-seqkit")
    target = directory / paths.executable_names()[0]
    target.write_text("<!DOCTYPE html><html><h1>404 Not Found</h1></html>", encoding="utf-8")
    if os.name != "nt":
        target.chmod(0o755)
    isolated([directory])

    found = seqkit_locator.locate("")

    assert not found.found, found


def test_a_configured_path_in_the_working_directory_is_accepted(
        isolated, monkeypatch, tmp_path):
    """The one exception is the file the user picked in Settings, cwd included.

    Naming the rule's edge keeps it honest: the refusal is about an *automatic*
    discovery, not about the folder itself.
    """
    cwd = tmp_path / "launch-dir"
    chosen = plant(cwd)
    isolated([])
    monkeypatch.chdir(cwd)

    found = seqkit_locator.locate(chosen)

    assert found.found, found.detail
    assert found.source == "configured"
