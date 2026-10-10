#!/usr/bin/env python3
"""Fetch the official seqkit release binary for this machine into ``bin/``.

SeqKit GUI is a shell around the ``seqkit`` command-line tool and reimplements
none of its logic, so a working ``seqkit`` executable is required. Upstream
releases are binaries of roughly 28 MB, so they are **not** committed to this
repository -- this helper downloads the right one for the current platform from
the official GitHub releases and puts it where ``seqkit_gui.core.seqkit_locator``
already looks::

    python tools/fetch_seqkit.py                     # seqkit 2.14.0 for this machine
    python tools/fetch_seqkit.py --version 2.9.0     # another release
    python tools/fetch_seqkit.py --sha256 <hex>      # pin the archive digest
    python tools/fetch_seqkit.py --force             # replace bin/seqkit[.exe]
    python tools/fetch_seqkit.py --list              # asset names, no network

What it downloads becomes the program the GUI runs, so the pipeline is built to
fail closed: the release tag is validated before it is put into the URL, the URL
is only ever assembled from that tag and a known asset name, the response has to
come back to an official GitHub host, upstream's ``.md5.txt`` has to be fetched
and to match before anything is unpacked, and there is no option that skips that
step. An archive is refused when it holds path-traversal names, links, unexpected
file types or more members than a release should have, every member is read
through a byte ceiling, and the bytes that are finally installed have to start
with a real executable signature for this platform. ``--sha256`` adds a second
digest of your own -- use it when you read the digest from the release page over a
channel you trust more than the one carrying the archive.

Standard library only: it must run on a bare Python 3.10 on Windows or macOS,
with no venv and no third-party packages installed yet. Nothing here is used by
the application itself; this is an installer-time convenience.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import platform
import re
import stat
import sys
import tarfile
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIN_DIR = ROOT / "bin"

OWNER = "shenwei356"
REPO = "seqkit"
DEFAULT_VERSION = "2.14.0"
TIMEOUT = 30.0  # seconds, applied to every network call
USER_AGENT = "seqkit-gui-fetch/1.0 (+https://github.com/shenwei356/seqkit)"

# Every release asset lives on GitHub: the download URL is github.com and it
# redirects to a *.githubusercontent.com blob host. Both ends are checked, so a
# redirect to somewhere else is an error rather than an installation source.
OFFICIAL_HOSTS = {"github.com", "api.github.com", "raw.githubusercontent.com"}
OFFICIAL_HOST_SUFFIXES = (".githubusercontent.com",)

# platform.system() -> (asset infix, archive suffix, member name inside it).
# Upstream names the Windows asset "seqkit_windows_amd64.exe.tar.gz": a tar.gz
# holding the .exe, not a zip. These are the assets v2.14.0 really publishes.
SUPPORTED_SYSTEMS = {
    "Windows": (".exe", "tar.gz", "seqkit.exe"),
    "Darwin": ("", "tar.gz", "seqkit"),
    "Linux": ("", "tar.gz", "seqkit"),
}

# platform.machine() values -> the architecture token used in asset names.
ARCHITECTURES = {
    "amd64": "amd64",
    "x86_64": "amd64",
    "arm64": "arm64",
    "aarch64": "arm64",
}

# Basenames that count as "the executable" inside a release archive. Anything
# else upstream ships (LICENSE, README.md, ...) is ignored.
EXECUTABLE_BASENAMES = {"seqkit", "seqkit.exe"}

#: tar member-type bytes that are not a plain file or a directory. ``TarInfo.type``
#: is bytes, so the name has to be looked up rather than string-stripped: a symlink
#: entry used to raise TypeError out of :func:`inspect_archive` instead of the
#: polite refusal, and a traceback is not a rejection the user can act on.
_TAR_SPECIAL_TYPES = {b"1": "hard link", b"2": "symbolic link", b"3": "character device",
                      b"4": "block device", b"6": "FIFO", b"g": "GNU sparse file"}

# A real seqkit build is several megabytes; anything much smaller is an error
# page or a truncated download, never a usable binary.
MINIMUM_SIZE = 1_000_000

# Ceilings for the archive and what it expands to. The published v2.14.0 Windows
# asset is 8.6 MB compressed and holds one 21 MB executable plus a handful of
# documents; anything far above these numbers is not that archive.
MAX_DOWNLOAD_BYTES = 200 * 1024 * 1024
MAX_MEMBERS = 64
MAX_MEMBER_BYTES = 96 * 1024 * 1024
MAX_EXPANDED_BYTES = 256 * 1024 * 1024

# A version is spliced straight into the URL path, so it is restricted to what a
# release tag can actually be: no slash, no dot-dot, no query or fragment.
VERSION_RE = re.compile(r"^[0-9][0-9A-Za-z._+-]{0,63}$")
HEX_RE = re.compile(r"^[0-9a-f]{32}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

# Magic numbers of the images each platform can execute.
EXECUTABLE_MAGICS = {
    "Windows": (b"MZ",),
    "Darwin": (b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xca\xfe\xba\xbe",
               b"\xbe\xba\xfe\xca", b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xce"),
    "Linux": (b"\x7fELF",),
}

_TRAVERSAL_RE = re.compile(r"(^|[/\\])\.\.([/\\]|$)")
#: A member name is never URL-decoded by anything here, so this catches only an
#: archive whose own tooling encoded its paths. The real reason a traversal name
#: cannot do damage is that no member is ever written to disk by its archived name:
#: :func:`extract_executable` returns bytes and :func:`install` writes one fixed
#: target inside ``bin/``. Both are still a reason to stop, because an archive
#: containing one is not the archive upstream published.
_ENCODED_TRAVERSAL_RE = re.compile(r"(?:%2e){2}(?:%2f|/|%5c|\\)", re.IGNORECASE)


class FetchError(RuntimeError):
    """Any problem this script reports politely instead of with a traceback."""


# ---------------------------------------------------------------------------
# Naming
# ---------------------------------------------------------------------------
def current_platform() -> tuple[str, str]:
    """``(system, architecture)`` for this machine, in upstream asset spelling."""
    system = platform.system()
    if system not in SUPPORTED_SYSTEMS:
        raise FetchError(
            f"unsupported platform: {system!r}; this helper knows "
            f"{', '.join(sorted(SUPPORTED_SYSTEMS))}. Get seqkit from "
            f"https://github.com/{OWNER}/{REPO}/releases and drop it in {BIN_DIR}."
        )
    raw = platform.machine().lower()
    arch = ARCHITECTURES.get(raw)
    if arch is None:
        raise FetchError(
            f"unsupported CPU architecture: {raw!r}; run "
            f"'python {Path(__file__).name} --list' to see the assets this script "
            f"can use and download the matching one by hand."
        )
    return system, arch


def check_version(version: str) -> str:
    """Validate a release tag before it becomes part of a URL."""
    value = (version or "").strip()
    if not VERSION_RE.fullmatch(value) or ".." in value:
        raise FetchError(
            f"{version!r} is not a seqkit release tag; expected something like "
            f"{DEFAULT_VERSION}. The tag is put into the download URL, so it may "
            f"not contain slashes, spaces or punctuation beyond . _ + -"
        )
    return value


def asset_name(system: str, arch: str) -> str:
    """Release asset name for one platform, e.g. ``seqkit_windows_amd64.exe.tar.gz``.

    Upstream names its assets by platform only -- the release tag lives in the URL
    path -- so a version here would either be ignored or invent a name that is not
    published.
    """
    infix, suffix, _ = SUPPORTED_SYSTEMS[system]
    return f"{REPO}_{system.lower()}_{arch}{infix}.{suffix}"


def candidate_assets() -> list[str]:
    """Every asset name this script is able to fetch, for ``--list``."""
    return [
        asset_name(system, arch)
        for system in sorted(SUPPORTED_SYSTEMS)
        for arch in sorted(set(ARCHITECTURES.values()))
    ]


def download_url(version: str, asset: str) -> str:
    return f"https://github.com/{OWNER}/{REPO}/releases/download/v{version}/{asset}"


def is_official_url(url: str) -> bool:
    """Whether ``url`` is served by GitHub itself, after any redirect."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https":
        return False
    host = (parts.hostname or "").lower()
    if not host:
        return False
    return host in OFFICIAL_HOSTS or any(host.endswith(suffix)
                                         for suffix in OFFICIAL_HOST_SUFFIXES)


# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------
def parse_md5(payload: bytes, url: str) -> str:
    """The digest out of an ``.md5.txt``: ``<hex32>  <asset name>`` plus a newline."""
    text = payload.decode("ascii", "replace").strip()
    fields = text.split()
    if not fields or not HEX_RE.fullmatch(fields[0].lower()):
        raise FetchError(
            f"{url} did not hold an md5 digest (read {text[:60]!r}); refusing to "
            f"guess what the archive should hash to."
        )
    return fields[0].lower()


class _OfficialRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Allow a redirect only while every hop stays on the official hosts.

    ``urllib`` follows a redirect chain before the caller ever sees a response,
    so checking ``geturl()`` after the fact happens too late: the connection to
    whatever host the redirect named has already been made. Deciding inside the
    redirect handler keeps every hop on the allowlist; the post-flight
    ``geturl()`` check then stays in as a second, independent gate.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not is_official_url(newurl):
            raise FetchError(
                f"{req.full_url} redirected outside GitHub ({newurl}); "
                f"nothing was fetched from the redirect target."
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_OfficialRedirectHandler())


def open_official(url: str, timeout: float):
    """Open ``url`` for reading, refusing it and every redirect hop off-list.

    The allowlist is checked before the first connection and again inside the
    redirect handler for every hop, so no connection is ever made to a host
    outside GitHub.
    """
    if not is_official_url(url):
        raise FetchError(f"refusing to fetch a non-official URL: {url}")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        return _OPENER.open(request, timeout=timeout)
    except urllib.error.HTTPError:
        raise
    except (urllib.error.URLError, OSError) as exc:
        raise FetchError(f"could not fetch {url}: {exc}") from exc


def fetch(url: str, timeout: float, limit: int = 64 * 1024) -> tuple[bytes, str]:
    """GET ``url`` and return its bytes together with the URL that served them."""
    try:
        response = open_official(url, timeout)
        with response:
            final = response.geturl()
            if not is_official_url(final):
                raise FetchError(
                    f"{url} redirected outside GitHub ({final}); nothing was installed."
                )
            body = response.read(limit)
    except urllib.error.HTTPError as exc:
        raise FetchError(f"HTTP {exc.code} for {url}") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise FetchError(f"could not fetch {url}: {exc}") from exc
    return body, final


def verify_md5(data: bytes, url: str, timeout: float) -> None:
    """Compare against the ``<asset>.md5.txt`` published next to the archive.

    Upstream publishes one for every asset of every supported platform, so a
    missing or unreadable checksum file stops the install instead of waving it
    through: it is the only thing here that says the bytes are the bytes GitHub
    shipped.
    """
    checksum_url = url + ".md5.txt"
    payload, served = fetch(checksum_url, timeout)
    expected = parse_md5(payload, served)
    actual = hashlib.md5(data).hexdigest()
    if actual != expected:
        raise FetchError(
            f"checksum mismatch: archive md5 is {actual}, upstream says {expected}. "
            f"Nothing was written to bin/; the download was corrupt or unexpected."
        )
    print(f"md5 verified: {actual}")


def verify_sha256(data: bytes, expected: str) -> None:
    """Compare against a digest the caller read from the release page itself."""
    want = expected.strip().lower()
    if not SHA256_RE.fullmatch(want):
        raise FetchError(f"--sha256 expects 64 hex digits, got {expected!r}")
    actual = hashlib.sha256(data).hexdigest()
    if actual != want:
        raise FetchError(
            f"sha256 mismatch: archive is {actual}, you asked for {want}. "
            f"Nothing was written to bin/."
        )
    print(f"sha256 verified: {actual}")


def download(url: str, timeout: float) -> Path:
    """Stream ``url`` into a temporary file and return its path."""
    if not is_official_url(url):
        raise FetchError(f"refusing to download from a non-official URL: {url}")
    descriptor, temp_name = tempfile.mkstemp(prefix="seqkit-", suffix=".archive")
    temp = Path(temp_name)
    # The descriptor is closed by the context manager before the file is ever
    # removed, otherwise Windows keeps the handle open and unlink() fails with
    # a permission error that hides the real reason for the failure.
    handed_over = False
    try:
        with os.fdopen(descriptor, "wb") as destination:
            response = open_official(url, timeout)
            with response:
                final = response.geturl()
                if not is_official_url(final):
                    raise FetchError(
                        f"{url} was redirected outside GitHub ({final}); the "
                        f"archive was discarded and nothing was installed."
                    )
                written = _copy_capped(response, destination, MAX_DOWNLOAD_BYTES)
        handed_over = True
    except urllib.error.HTTPError as exc:
        raise FetchError(
            f"HTTP {exc.code} for {url}. Check the version and platform against "
            f"--list, or download from https://github.com/{OWNER}/{REPO}/releases by hand."
        ) from exc
    except (urllib.error.URLError, OSError) as exc:
        raise FetchError(f"could not download {url}: {exc}") from exc
    finally:
        # Removing a half-written archive is the part that cannot be conditional on
        # the kind of failure: a redirect outside GitHub, a body over the byte cap,
        # an interrupted run and an unlisted error all leave this file behind, and
        # only the ones named above carry a message worth showing the user.
        if not handed_over:
            _discard(temp)

    if written == 0:
        _discard(temp)
        raise FetchError(f"downloaded an empty file from {url}")
    print(f"downloaded {written / (1024 * 1024):.1f} MB")
    return temp


def _copy_capped(source, destination, limit: int) -> int:
    """Copy at most ``limit`` bytes, so an endless body cannot fill the disk."""
    total = 0
    while True:
        chunk = source.read(1024 * 256)
        if not chunk:
            return total
        total += len(chunk)
        if total > limit:
            raise FetchError(
                f"the download grew past {limit} bytes and was abandoned; that is "
                f"not a seqkit release archive."
            )
        destination.write(chunk)


def _discard(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Archive inspection and extraction
# ---------------------------------------------------------------------------
def is_safe_member_name(name: str) -> bool:
    """Whether an archive member could ever be written inside the intended folder."""
    if not name or "\x00" in name:
        return False
    if name.startswith(("/", "\\")):            # absolute POSIX path, or UNC
        return False
    if re.match(r"^[A-Za-z]:", name):           # C:\Windows\...
        return False
    if _TRAVERSAL_RE.search(name) or _ENCODED_TRAVERSAL_RE.search(name):
        return False
    return True


def _open_archive(archive: Path):
    """``("zip", handle)`` or ``("tar", handle)``, or a polite failure."""
    if zipfile.is_zipfile(archive):
        return "zip", zipfile.ZipFile(archive)
    try:
        return "tar", tarfile.open(archive, mode="r:*")
    except tarfile.TarError as exc:
        raise FetchError(
            f"not a readable zip or tar archive: {exc}. A seqkit release asset is "
            f"a .tar.gz holding one executable; this file is something else."
        ) from exc


def inspect_archive(archive: Path) -> list[str]:
    """Names of the regular files in an archive, after rejecting unsafe ones.

    Nothing here writes to disk, so a traversal name could not escape on its own;
    it is still a reason to stop, because an archive that contains one is not the
    archive upstream published.
    """
    kind, handle = _open_archive(archive)
    try:
        with handle:
            if kind == "zip":
                members = [(info.filename, info.file_size, False)
                           for info in handle.infolist()]
                types = {info.filename: "symlink"
                         for info in handle.infolist()
                         if info.external_attr >> 16 & 0o170000 == 0o120000}
            else:
                members = [(member.name, member.size, member.isdir())
                           for member in handle.getmembers()]
                types = {member.name: _TAR_SPECIAL_TYPES.get(member.type, "special file")
                         for member in handle.getmembers()
                         if not (member.isfile() or member.isdir())}
    except (zipfile.BadZipFile, tarfile.TarError, EOFError, OSError, ValueError) as exc:
        # Listing the members of a damaged archive (a body cut short by a proxy,
        # say) raises out of the decompression layer. FetchError is the only error
        # this script puts in front of a user, so the raw exception becomes one.
        raise FetchError(
            f"{archive.name} could not be read as a zip or tar archive ({exc}); "
            f"nothing was installed."
        ) from exc

    if len(members) > MAX_MEMBERS:
        raise FetchError(
            f"the archive lists {len(members)} members, more than the {MAX_MEMBERS} "
            f"a seqkit release should hold; it is not installed."
        )
    total = sum(size for _, size, _ in members)
    if total > MAX_EXPANDED_BYTES:
        raise FetchError(
            f"the archive claims {total:,} bytes expanded, over the "
            f"{MAX_EXPANDED_BYTES:,} byte ceiling for a seqkit release."
        )
    for name, size, _ in members:
        if not is_safe_member_name(name):
            raise FetchError(
                f"the archive holds the member {name!r}, which is an absolute path, a "
                f"parent-directory reference or otherwise not a plain file name; the "
                f"archive is not installed."
            )
        if size > MAX_MEMBER_BYTES:
            raise FetchError(
                f"the member {name!r} claims {size:,} bytes, over the "
                f"{MAX_MEMBER_BYTES:,} byte ceiling; refusing to unpack it."
            )
    for name, kind_name in types.items():
        raise FetchError(
            f"the archive holds a {kind_name} entry ({name!r}); links and device "
            f"nodes have no place in a seqkit release, so it is not installed."
        )
    return [name for name, _, is_dir in members if not is_dir]


def member_names(archive: Path) -> list[str]:
    """Regular-file members of a zip or tar.gz archive, as forward-slash paths."""
    return inspect_archive(archive)


def executable_members(names: list[str]) -> list[str]:
    """Members whose basename looks like the seqkit executable."""
    return [name for name in names if os.path.basename(name).lower() in EXECUTABLE_BASENAMES]


def extract_executable(archive: Path, member: str,
                       limit: int = MAX_MEMBER_BYTES) -> bytes:
    """The bytes of one archive member, chosen by the caller as the executable."""
    try:
        data = _read_member(archive, member, limit)
    except (zipfile.BadZipFile, tarfile.TarError, EOFError, OSError, ValueError) as exc:
        # Passing the name and size screening does not mean the body is intact: a
        # truncated download or a flipped byte surfaces here as a decompression
        # error. It is a refusal with a reason, not a traceback to read.
        raise FetchError(
            f"{member} could not be unpacked from {archive.name} ({exc}); the "
            f"archive is damaged or is not a seqkit release. Nothing was installed."
        ) from exc
    if len(data) > limit:
        raise FetchError(
            f"{member} kept expanding past the {limit:,} byte limit; it is not the "
            f"executable this archive should contain."
        )
    return data


def _read_member(archive: Path, member: str, limit: int) -> bytes:
    """At most ``limit + 1`` bytes of one member, so overruns are detectable."""
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as handle:
            info = handle.getinfo(member)
            if info.file_size > limit:
                raise FetchError(
                    f"{member} expands to {info.file_size:,} bytes, past the "
                    f"{limit:,} byte limit set before reading it."
                )
            # ``info.file_size`` is a claim made by the archive, and a crafted one
            # claims little while expanding to a great deal, so the read is capped
            # by bytes actually produced rather than by that number alone.
            with handle.open(member) as source:
                return source.read(limit + 1)
    with tarfile.open(archive, mode="r:*") as handle:
        extracted = handle.extractfile(member)
        if extracted is None:
            raise FetchError(f"could not read {member} out of the archive")
        with extracted:
            return extracted.read(limit + 1)


def sanity_check(data: bytes, system: str, asset: str) -> None:
    """Reject the common silent failures: an HTML error page or a stub file."""
    head = data[:64].lstrip()
    if head.startswith(b"<") or b"<!DOCTYPE" in head or b"Not Found" in head:
        raise FetchError(
            f"{asset} did not contain a binary (it looked like a web page). "
            f"Check the version number, or download from "
            f"https://github.com/{OWNER}/{REPO}/releases manually."
        )
    if len(data) < MINIMUM_SIZE:
        raise FetchError(
            f"the extracted executable is only {len(data)} bytes; a real seqkit "
            f"build is several megabytes. Refusing to install it."
        )
    magics = EXECUTABLE_MAGICS.get(system)
    if magics and not data.startswith(magics):
        raise FetchError(
            f"the extracted file does not start with a {system} executable "
            f"signature ({', '.join(repr(magic) for magic in magics)}); it is not "
            f"installed. Windows wants 'MZ', Linux '\\x7fELF', macOS a Mach-O magic."
        )


# ---------------------------------------------------------------------------
# Installing
# ---------------------------------------------------------------------------
def target_path(system: str) -> Path:
    """Where the locator expects the bundled binary on this platform."""
    return BIN_DIR / SUPPORTED_SYSTEMS[system][2]


def _check_inside_bin(target: Path) -> Path:
    """The folder the target resolves to, proven to be ``bin/`` and nothing deeper."""
    base = BIN_DIR.resolve()
    directory = target.parent.resolve()
    try:
        directory.relative_to(base)
    except ValueError as exc:
        raise FetchError(f"refusing to write outside {base}: {target}") from exc
    return directory


def install(data: bytes, target: Path, force: bool) -> None:
    if target.is_symlink():
        raise FetchError(
            f"{target} is a symbolic link; replacing it could write through to "
            f"somewhere else. Remove the link and run again."
        )
    directory = _check_inside_bin(target)
    if target.exists() and not force:
        raise FetchError(
            f"{target} already exists. Re-run with --force to overwrite it, or "
            f"point the app at a different executable in Settings."
        )
    directory.mkdir(parents=True, exist_ok=True)
    # An unpredictable name created exclusively (0600) rather than a fixed
    # "<target>.download", which anyone able to write this folder could pre-create
    # as a link to another file.
    descriptor, staging_name = tempfile.mkstemp(prefix=f"{target.name}.", suffix=".download",
                                                dir=directory)
    staging = Path(staging_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if os.name != "nt":  # macOS / Linux: 0755, as a shipped binary should be
            os.chmod(staging, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP |
                     stat.S_IROTH | stat.S_IXOTH)
        os.replace(staging, target)  # atomic, so a crash cannot leave half a binary
        staging = None
    finally:
        if staging is not None:
            _discard(staging)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fetch_seqkit",
        description="Download the official seqkit release binary into bin/.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--version",
        default=DEFAULT_VERSION,
        help="seqkit release to fetch, without the leading 'v'",
    )
    parser.add_argument(
        "--sha256",
        default="",
        metavar="HEX",
        help="require the downloaded archive to hash to this sha256 digest, in "
             "addition to upstream's own md5 file",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite bin/seqkit(.exe) if it is already there",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        dest="list_assets",
        help="print the release asset names this script can fetch, then exit",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=TIMEOUT,
        help="network timeout, in seconds, for each request",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # The tag is pasted into the path part of the download URL, so it is checked
    # here once, before anything uses it: `..` in a tag would otherwise ask GitHub
    # for a different path than the release this command names.
    version = check_version(args.version)

    if args.list_assets:
        print("release assets this script can fetch:")
        for name in candidate_assets():
            print(f"  {name}")
        try:
            system, arch = current_platform()
            print(f"this platform would use: {asset_name(system, arch)}")
        except FetchError as exc:
            print(f"this platform is not supported: {exc}")
        return 0

    system, arch = current_platform()
    asset = asset_name(system, arch)
    url = download_url(version, asset)
    target = target_path(system)

    if target.exists() and not args.force:
        # Checked before spending bandwidth on a 10-30 MB download.
        raise FetchError(
            f"{target} already exists. Re-run with --force to overwrite it, or "
            f"point the app at a different executable in Settings."
        )

    print(f"fetching {asset} (seqkit {version}, {system}/{arch})")
    print(f"  {url}")
    archive = download(url, args.timeout)
    try:
        payload = archive.read_bytes()
        verify_md5(payload, url, args.timeout)
        if args.sha256:
            verify_sha256(payload, args.sha256)
        names = member_names(archive)
        hits = executable_members(names)
        if len(hits) != 1:
            raise FetchError(
                f"expected exactly one seqkit executable inside {asset}, found "
                f"{len(hits)}: {', '.join(hits) if hits else '(none)'}. "
                f"Archive members: {', '.join(sorted(names)) or '(empty)'}"
            )
        data = extract_executable(archive, hits[0])
        sanity_check(data, system, asset)
    finally:
        archive.unlink(missing_ok=True)

    install(data, target, args.force)
    print(f"installed: {target}")
    print("SeqKit GUI looks for the binary in the app settings, then bin/, then PATH.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FetchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
    except urllib.error.HTTPError as exc:
        print(
            f"error: HTTP {exc.code} from GitHub -- is that seqkit version released, "
            f"and is there a {platform.system().lower()} build for "
            f"{platform.machine()}? See --list.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    except urllib.error.URLError as exc:
        print(f"error: network failure: {exc.reason}", file=sys.stderr)
        print("Hint: check your connection or a proxy; nothing was written to bin/.", file=sys.stderr)
        raise SystemExit(1)
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        raise SystemExit(130)
