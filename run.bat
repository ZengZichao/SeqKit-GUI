@echo off
rem -----------------------------------------------------------------------
rem SeqKit GUI launcher (Windows).
rem Double-click it, or run "run.bat" from a command prompt in this folder. Extra
rem arguments are forwarded to the interface, which is what run.sh does too.
rem
rem The GUI is only a shell around the external seqkit executable: seqkit is
rem not committed to git, so this script says where to get one -- or reports the
rem place the interface itself found one -- and starts the app either way.
rem -----------------------------------------------------------------------
setlocal
cd /d "%~dp0"

set "SEQKIT_BIN=bin\seqkit.exe"

where python >nul 2>nul
if errorlevel 1 (
    echo [error] python was not found on PATH.
    echo [error] Install Python 3.10+ from https://www.python.org/downloads/
    echo [error] and make sure "Add Python to PATH" is ticked.
    pause
    exit /b 1
)

rem Finding the name is not the same as having an interpreter. The Microsoft Store alias
rem answers to "where python", writes nothing and fails; an older interpreter starts and
rem then stops on a syntax error that reads like a missing package. Each of the three
rem states needs its own words, because a user told to install dependencies into an
rem interpreter that cannot run the interface loses the afternoon either way.
set "PYMINOR="
for /f "delims=" %%V in ('python -c "import sys;print(sys.version_info[0]*100+sys.version_info[1])" 2^>nul') do set "PYMINOR=%%V"
if not defined PYMINOR (
    echo [error] "python" is on PATH but does not run as a Python interpreter.
    echo [error] Run "python -V" to see what it is. A Microsoft Store install alias
    echo [error] can sit on PATH in place of a real interpreter: install Python from
    echo [error] https://www.python.org/downloads/ or switch the alias off under
    echo [error] Settings / Apps / Advanced app management / App execution aliases.
    pause
    exit /b 1
)
if %PYMINOR% LSS 310 (
    echo [error] The python on PATH is older than 3.10, which is what this interface
    echo [error] needs. Run "python -V" to check, use "py -3.10 -m seqkit_gui" if a
    echo [error] newer interpreter is already installed, or install one from
    echo [error] https://www.python.org/downloads/ .
    pause
    exit /b 1
)



rem The interface is PySide6 on top of the seqkit executable, so both halves are
rem checked before anything is announced. An import is cheaper to name here than in a
rem traceback: the launch either works or says which piece this interpreter lacks.
python -c "import PySide6" 2>nul
if errorlevel 1 (
    echo [hint] PySide6 does not seem to be installed for the python on PATH.
    echo [hint] Install the dependencies with: python -m pip install -r requirements.txt
    echo.
)

rem The app locates seqkit itself -- a copy in bin\ first, then any absolute PATH
rem folder -- and runs whatever it finds as soon as its window opens. Asking that
rem search is what keeps the advice below true on a machine where seqkit is already
rem installed somewhere the app looks: testing for one file name here would announce
rem an unusable interface that in fact starts and runs commands. The search needs no
rem Qt, so it answers even when the interface itself cannot start, and it reports
rem only the words bundled / path / missing, which survive any console codepage.
set "SEQKIT_PROBE="
for /f "usebackq delims=" %%V in (`python -c "from seqkit_gui.core.seqkit_locator import locate; f = locate(''); print(f.source if f.found else 'missing')" 2^>nul`) do set "SEQKIT_PROBE=%%V"
if not defined SEQKIT_PROBE (
    rem Nothing came back, so the app package itself was not importable from here.
    rem Fall back to the one thing this script can tell on its own.
    if exist "%SEQKIT_BIN%" set "SEQKIT_PROBE=bundled"
)
if not defined SEQKIT_PROBE set "SEQKIT_PROBE=missing"

if "%SEQKIT_PROBE%"=="bundled" echo [seqkit] "%SEQKIT_BIN%"
if "%SEQKIT_PROBE%"=="path" echo [seqkit] found on PATH, so no copy inside bin\ is needed.
if "%SEQKIT_PROBE%"=="missing" (
    echo [hint] No usable seqkit was found: nothing acceptable in bin\, nothing on PATH.
    echo [hint] The interface assembles commands, but only seqkit runs them, so no
    echo [hint] command will produce output until it can be located. Two ways to get it:
    echo [hint]   1. python tools\fetch_seqkit.py   - downloads the official 2.14.0 release into bin\
    echo [hint]   2. copy seqkit.exe into the bin\ folder yourself
    echo [hint] A copy kept anywhere else works too - leave it on PATH, or point the
    echo [hint] app at it under Settings. Starting the interface anyway.
    echo.
)

echo Starting SeqKit GUI ...
python -m seqkit_gui %*
if errorlevel 1 (
    echo.
    echo [error] SeqKit GUI exited with an error, started as: python -m seqkit_gui
    echo [error] The message above names the cause. A missing PySide6 -- or another
    echo [error] module the interface imports -- is fixed by installing into the
    echo [error] interpreter this script just used:
    echo [error]   python -m pip install -r requirements.txt
    pause
    exit /b 1
)

endlocal
