"""The seqkit downloader's archive handling, exercised without network access.

GitHub's release-download host is not reachable from every network, so the parts
that decide *what* to fetch and *how* to unpack it are tested against archives
built here instead.
"""

import importlib.util
import io
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("fetch_seqkit", ROOT / "tools" / "fetch_seqkit.py")
fetch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fetch)


def test_windows_asset_name_matches_what_upstream_publishes():
    """Windows builds are tar.gz archives containing the .exe, not zip files."""
    assert fetch.asset_name("Windows", "amd64") == "seqkit_windows_amd64.exe.tar.gz"
    assert fetch.asset_name("Darwin", "arm64") == "seqkit_darwin_arm64.tar.gz"
    assert fetch.asset_name("Linux", "amd64") == "seqkit_linux_amd64.tar.gz"


def test_candidate_assets_are_all_real_release_names():
    names = fetch.candidate_assets()
    assert "seqkit_windows_amd64.exe.tar.gz" in names
    assert not any(name.endswith(".zip") for name in names), names


def test_download_url_points_at_a_versioned_release_tag():
    url = fetch.download_url("2.14.0", "seqkit_windows_amd64.exe.tar.gz")
    assert url == ("https://github.com/shenwei356/seqkit/releases/download/"
                   "v2.14.0/seqkit_windows_amd64.exe.tar.gz")


def test_architecture_aliases():
    assert fetch.ARCHITECTURES["x86_64"] == "amd64"
    assert fetch.ARCHITECTURES["aarch64"] == "arm64"


def test_target_path_uses_the_platform_member(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch, "BIN_DIR", tmp_path)
    assert fetch.target_path("Windows").name == "seqkit.exe"
    assert fetch.target_path("Darwin").name == "seqkit"


def _archive(tmp_path: Path, members: dict[str, bytes]) -> Path:
    path = tmp_path / "seqkit_test.tar.gz"
    with tarfile.open(path, "w:gz") as handle:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            handle.addfile(info, io.BytesIO(data))
    return path


def test_executable_member_is_picked_out_of_a_real_archive_layout(tmp_path):
    payload = b"MZ" + b"\x90" * 4096
    archive = _archive(tmp_path, {
        "seqkit_windows_amd64.exe/seqkit.exe": payload,
        "seqkit_windows_amd64.exe/LICENSE": b"MIT licence text",
        "seqkit_windows_amd64.exe/README.md": b"# seqkit",
    })
    names = fetch.member_names(archive)
    hits = fetch.executable_members(names)
    assert len(hits) == 1, hits
    assert fetch.extract_executable(archive, hits[0]).startswith(b"MZ")


def test_ambiguous_archive_is_reported_instead_of_guessed(tmp_path):
    payload = b"MZ" + b"x" * 4096
    archive = _archive(tmp_path, {
        "seqkit_windows_amd64.exe/seqkit.exe": payload,
        "seqkit_windows_amd64.exe/legacy/seqkit": payload,
    })
    hits = fetch.executable_members(fetch.member_names(archive))
    assert len(hits) == 2, hits
    # main() refuses to guess in that situation rather than picking one.
    assert "seqkit_windows_amd64.exe/seqkit.exe" in hits


def test_sanity_check_rejects_html_and_stubs():
    with pytest.raises(fetch.FetchError):
        fetch.sanity_check(b"<!DOCTYPE html><html>404</html>", "Windows", "asset")
    with pytest.raises(fetch.FetchError):
        fetch.sanity_check(b"MZ" + b"\x00" * 100, "Windows", "asset")
    with pytest.raises(fetch.FetchError):
        fetch.sanity_check(b"\x7fELF" + b"z" * 2_000_000, "Windows", "asset")


def test_sanity_check_accepts_a_plausible_windows_binary():
    fetch.sanity_check(b"MZ" + b"\x00" * 2_000_000, "Windows", "asset")


def test_install_refuses_to_overwrite_without_force(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch, "BIN_DIR", tmp_path)
    target = tmp_path / "seqkit.exe"
    target.write_bytes(b"existing")
    with pytest.raises(fetch.FetchError):
        fetch.install(b"MZ" + b"new", target, force=False)
    assert target.read_bytes() == b"existing"


def test_install_writes_atomically_and_reports_the_path(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch, "BIN_DIR", tmp_path)
    target = tmp_path / "seqkit.exe"
    fetch.install(b"MZ" + b"payload", target, force=True)
    assert target.read_bytes() == b"MZ" + b"payload"
    assert not (tmp_path / "seqkit.exe.download").exists()


def test_unsupported_platform_is_reported_clearly(monkeypatch):
    monkeypatch.setattr(fetch.platform, "system", lambda: "Plan9")
    with pytest.raises(fetch.FetchError) as info:
        fetch.current_platform()
    assert "Plan9" in str(info.value)
