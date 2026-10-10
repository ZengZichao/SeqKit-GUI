#!/usr/bin/env bash
# -----------------------------------------------------------------------
# SeqKit GUI launcher (POSIX; macOS-ready).
#
# The GUI is only a shell around the external seqkit executable: seqkit is
# not committed to git, so this script points out where to get it and then
# starts the app regardless. Extra arguments are forwarded to the app.
# -----------------------------------------------------------------------
set -u

# The script's own folder, worked out without calling `dirname`: a launcher should keep
# answering even when PATH does not resolve the usual utilities, and the two expansions
# below are all bash and POSIX sh agree on. Failing here is worth a line of its own,
# because `bin/`, `tools/` and the app package are all found relative to it.
case "${0}" in
    */*) SCRIPT_DIR="${0%/*}" ;;
    *) SCRIPT_DIR="." ;;
esac
[ -n "${SCRIPT_DIR}" ] || SCRIPT_DIR="/"
cd "${SCRIPT_DIR}" || {
    echo "[error] cannot enter ${SCRIPT_DIR}, so bin/ and the seqkit_gui package are out of reach." >&2
    exit 1
}

BIN_DIR="bin"
SEQKIT_BIN="${BIN_DIR}/seqkit"

PYTHON="${PYTHON:-}"
if [ -z "${PYTHON}" ]; then
    if command -v python3 >/dev/null 2>&1; then
        PYTHON="python3"
    elif command -v python >/dev/null 2>&1; then
        PYTHON="python"
    else
        echo "[error] python3 was not found on PATH." >&2
        echo "[error] Install Python 3.10+ (macOS: brew install python) and try again." >&2
        exit 1
    fi
fi

if ! "${PYTHON}" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
    echo "[error] ${PYTHON} does not run as a working Python 3.10+ interpreter." >&2
    echo "[error] Run \"${PYTHON} -V\" to check what it is. Install Python 3.10 or newer" >&2
    echo "[error] (macOS: brew install python), or name the interpreter to use:" >&2
    echo "[error]   PYTHON=/path/to/python3.12 ./run.sh" >&2
    exit 1
fi

if ! "${PYTHON}" -c "import PySide6" >/dev/null 2>&1; then
    echo "[hint] PySide6 does not seem to be installed for ${PYTHON}."
    echo "[hint] Install the dependencies with: ${PYTHON} -m pip install -r requirements.txt"
fi

# The app locates seqkit itself -- a copy in bin/ first, then any absolute PATH
# directory -- and runs whatever it finds as soon as its window opens. Asking that
# search, instead of testing one file name here, is what keeps the advice below true
# on a machine where seqkit is already installed somewhere the app looks. It is also
# the search's own rules that decide a stray bin/seqkit.exe on a Windows filesystem
# counts for nothing on macOS. The probe needs no Qt, so it answers even when the
# interface itself cannot start, and it reports only bundled / path / missing: words
# that survive any console encoding, unlike a path.
SEQKIT_STATE="$("${PYTHON}" -c 'from seqkit_gui.core.seqkit_locator import locate; f = locate(""); print(f.source if f.found else "missing")' 2>/dev/null)"
if [ -z "${SEQKIT_STATE}" ]; then
    # Nothing came back, so the app package was not importable from here. Fall back to
    # the one thing this script can tell on its own.
    if [ -f "${SEQKIT_BIN}" ]; then
        SEQKIT_STATE="bundled"
    else
        SEQKIT_STATE="missing"
    fi
fi

case "${SEQKIT_STATE}" in
    bundled)
        echo "[seqkit] ${SEQKIT_BIN}"
        ;;
    path)
        echo "[seqkit] found on PATH, so no copy inside ${BIN_DIR}/ is needed."
        ;;
    *)
        echo "[hint] No usable seqkit was found: nothing acceptable in ${BIN_DIR}/, nothing on PATH."
        echo "[hint] The interface assembles commands, but only seqkit runs them, so no"
        echo "[hint] command will produce output until it can be located. Two ways to get it:"
        echo "[hint]   1. ${PYTHON} tools/fetch_seqkit.py   - downloads the official 2.14.0 release into ${BIN_DIR}/"
        echo "[hint]   2. copy the seqkit binary into the ${BIN_DIR}/ folder yourself"
        echo "[hint] A copy kept anywhere else works too - leave it on PATH, or point the"
        echo "[hint] app at it under Settings. Starting the interface anyway."
        echo
        ;;
esac

echo "Starting SeqKit GUI ..."
exec "${PYTHON}" -m seqkit_gui "$@"
