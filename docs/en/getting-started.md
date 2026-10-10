# Getting started

> This document describes **SeqKit GUI**, an unofficial desktop graphical front end for [SeqKit](https://github.com/shenwei356/seqkit), the sequence toolkit by Wei Shen (MIT). It is not affiliated with, endorsed by, or maintained by the SeqKit project, and it is not the official SeqKit graphical interface.

## 1. What this application is

SeqKit GUI is a **shell**, nothing more. It performs no sequence processing itself.

| Concern | Who handles it |
| --- | --- |
| Reading FASTA/FASTQ, parsing flags, computing statistics, filtering, converting | the official `seqkit` executable (external program) |
| Building the argument vector, launching the child process, streaming stdout/stderr | SeqKit GUI (`seqkit_gui/core/builder.py`, `seqkit_gui/core/runner.py`) |
| Presenting parameters and results | SeqKit GUI (`seqkit_gui/ui/`) |

Concretely: the form on the right of the window is converted into an argument list, that list is handed to `seqkit` through `QProcess`, and whatever `seqkit` prints is streamed back into the Result, Errors and Log tabs. The GUI never builds a shell string, so a file name containing spaces or quotes cannot change what `seqkit` does.

If `seqkit` is missing, the window still starts, but no command can run.

## 2. Requirements

| Requirement | Detail |
| --- | --- |
| Operating system | Windows 10/11 x64 -- the only platform this window has been opened and driven by hand. The macOS/Linux launchers and path code exist (`platform.system()` branches, Darwin-only search prefixes, `run.sh`, the downloader's `Darwin`/`Linux` branches) but nobody has run the interface on a real macOS or Linux desktop, and no packaged build exists for them; see [development guide](development.md). |
| Python | 3.10 or newer (`requires-python = ">=3.10"`) |
| Python packages | `PySide6>=6.6,<7` — the only runtime dependency |
| SeqKit | an official `seqkit` build; the parameter table is generated from SeqKit **2.14.0** |

`seqkit` is **not** distributed in this repository: upstream release binaries are roughly 28 MB and are covered by SeqKit's own MIT notice (see [`THIRD-PARTY-LICENSES.md`](../../THIRD-PARTY-LICENSES.md)), so `bin/` is gitignored.

## 3. Install

1. Obtain the source tree and open a terminal in its root directory (the folder containing `run.bat` / `run.sh`).

2. Install the Python dependency:

   ```bash
   python -m pip install -r requirements.txt
   ```

3. Obtain the `seqkit` executable. Use any one of these:

   **a. Fetch the official release (recommended).** Standard library only — it works before step 2:

   ```bash
   python tools/fetch_seqkit.py
   ```

   This downloads the SeqKit 2.14.0 asset matching your platform and CPU, verifies it against the `.md5.txt` published beside the archive, extracts the single executable, sanity-checks it (minimum size, no HTML error page, `MZ` header on Windows) and installs it as `bin/seqkit.exe` on Windows or `bin/seqkit` on macOS/Linux. Upstream ships tar.gz archives for every platform — the Windows one is `seqkit_windows_amd64.exe.tar.gz` and holds `seqkit.exe`. Useful options:

   | Option | Effect |
   | --- | --- |
   | `--version 2.9.0` | fetch a different release |
   | `--sha256 HEX` | besides upstream's own `.md5.txt`, require the archive to hash to this SHA-256 digest |
   | `--force` | overwrite an existing `bin/seqkit[.exe]` |
   | `--list` | print the asset names the script can fetch and the one this machine would use; no network access |
   | `--timeout 60` | per-request network timeout in seconds (default 30) |

   **b. Copy it yourself** into the project's `bin/` folder as `seqkit.exe` (Windows) or `seqkit` (macOS/Linux).

   **c. Put it anywhere on `PATH`.**

   **d. Point Settings at an existing copy** (see step 5).

## 4. Start

| Method | Command |
| --- | --- |
| Windows launcher | double-click `run.bat`, or run `run.bat` from a prompt in the project root |
| POSIX launcher | `./run.sh` (forwards extra arguments to the app; honours a `PYTHON` environment variable) |
| Module invocation | `python -m seqkit_gui` |

Both launchers check for `python`, warn when `bin/seqkit[.exe]` is absent, and start the app anyway — the warning is informational, not fatal.

The window opens roughly 1320×860, split into a command list on the left and a parameter form above an output panel on the right.

![Main window, Chinese interface, light theme](../screenshots/light-zh.png)

## 5. Confirm that seqkit was found

Three places report the state of the lookup:

| Where | Expected value when everything is in place |
| --- | --- |
| Header bar badge | `SeqKit 2.14.0` (the tooltip shows the full path of the binary) |
| Status bar, left | the full path of the binary plus how it was found, e.g. `...\bin\seqkit.exe  (bundled)` |
| Area beside the badge | empty; an amber **Version mismatch** badge appears there when the detected version is not 2.14.0, and the badge itself reads `seqkit not found` when nothing was located |

The version badge is live: it reports what `<binary> version` prints, and a second amber **Version mismatch** badge appears when that differs from the 2.14.0 schema the form was generated from (its tooltip explains that some options may not match).

Search order used by `seqkit_gui/core/seqkit_locator.py`:

| Order | Source label shown in the status bar | Location |
| --- | --- | --- |
| 1 | `configured` | the path stored in Settings (empty means "skip this step") |
| 2 | `bundled` | `bin/` beside the application; the schema probes two candidate bases there and they resolve to the same folder. Windows tries `seqkit.exe`, `seqkit.cmd`, `seqkit.bat`, `seqkit`; other systems try `seqkit` |
| 3 | `path` | the first executable found on `PATH`; on macOS the search also tries `/opt/homebrew/bin` and `/usr/local/bin` |

A candidate is accepted only when it is an existing file whose first bytes form an image this machine can execute: `MZ` on Windows, `\x7fELF` on Linux, a Mach-O magic on macOS. Script files (`.bat`, `.cmd`, `.com`, `.ps1`, `.vbs`, `.js`, `.lnk`, `.url`) are refused outright on Windows -- neither `QProcess` nor `subprocess` can start them as a program -- which is why the `seqkit.cmd` and `seqkit.bat` names listed in step 2 are always rejected by this gate. Off Windows the file additionally needs the `os.access(path, os.X_OK)` execute bit, with `#!` scripts excepted. Apart from the entry you picked in Settings, any candidate sitting directly in the working directory is refused; empty and relative `PATH` entries are skipped, and so is the current-directory hit `shutil.which` prefers on Windows, after which the real `PATH` is still walked. Repeated paths are tested once. The whole gate exists to block binary-planting hijacks, as `seqkit_gui/core/seqkit_locator.py` states in its module docstring.

To set the path manually: **Settings → SeqKit executable** (or **Tools → Locate seqkit executable**). Leave the field empty to fall back to auto-detection; the **Test** button runs `seqkit version` on the typed path and reports the output, "Could not run this file", or "seqkit not found".

## 6. First run: extracting one record with grep

The repository ships sample data at `tests/data/short1.fa`, so the very first run needs nothing you have to download.

1. **Pick the command**: in the left tree open the **Commands for Searching** group and click `grep · Search for sequences by ID/name/sequence/motif` (groups start expanded). Typing `grep` into the **Search commands** box above the tree works too -- it matches command names, summaries in either language, and aliases.
2. **Add the input file**: press **Add files** in the **Input files** section and select `tests/data/short1.fa`. Files can also be dragged in from the file manager, or imported line by line with **Paste paths**.
3. **Set the parameters**: expand **Command parameters** (the number `16` beside the heading is the command's own flag count),
   - tick `--pattern` (shorthand `-p`) and type `seq1` in the multi-line editor that appears;
   - tick `--ignore-case` (shorthand `-i`) -- a boolean row is just the checkbox.
   - **Leave every other row unticked**: an unticked parameter is not passed at all, and seqkit uses its own default.
4. **Run**: press **Run** in the output panel (or `Ctrl+R` / `Ctrl+Enter`).
5. **Read the result**: the panel stays on the **Result** tab, showing the matching records; the status label at the end of the button row reads, for example, `Done · exit code 0 · elapsed 0.16s · output 52B`; the **Command** tab holds the line that actually ran:

```text
"D:\SeqKit-GUI\bin\seqkit.exe" grep --ignore-case --pattern seq1 -- "D:\SeqKit-GUI\tests\data\short1.fa"
```

That standalone `--` is the terminator the interface always inserts: positional input files are placed behind it so a file name starting with `-` cannot be read by seqkit as a flag (see `TERMINATOR` in `seqkit_gui/core/builder.py`).

The right status slot previews this line live as you change the form. **Copy result** puts the sequence data on the clipboard; **Copy command line** (`Ctrl+Shift+C`) puts the command line there instead, ready to reproduce in a terminal.

![The grep form in the Chinese light theme](../screenshots/light-zh.png)

![The Result tab after a run](../screenshots/light-zh-result.png)

The screenshots in these documents are captured from a real window, with machine-local paths and user names masked or substituted; a clean, unmasked image has to be re-shot inside a scrubbed example directory that carries no real user name or project path.

## 7. Second task: statistics written to a file

1. Select `stats` in **Commands for Basic Operation** (the tree shows it as `stats · …`; its alias `stat` also matches the search box).
2. Add `tests/data/short1.fa` and `tests/data/short2.fa` to **Input files**.
3. Expand **Command parameters** and tick `--all` (`-a`).
4. Expand **Global parameters**, tick `--out-file` (`-o`), press **Browse** and pick a destination such as `D:\tmp\stats.tsv`.
5. Run. An empty **Result** tab plus the status message `Finished without writing anything to standard output` is the expected outcome -- seqkit wrote the table into `-o` instead of stdout.

> Tick `--out-file` and seqkit writes the result into that file instead of stdout; leave it unticked and the result shows in the **Result** tab while still being captured in full in a temporary file (the one **Open output file** and **Save result** read).

## 8. Interface at a glance

| Region | Contents |
| --- | --- |
| Header bar | brand text, SeqKit version badge, version-mismatch badge, language (简体中文 / English), theme (Light / Dark), **Settings**, **Documentation** |
| Menu bar | File / View / Tools / Help (there is no right-click context menu anywhere in the window) |
| Left | command search box + command tree: the eight groups seqkit declares, plus a final node the interface synthesises (**Other**, `其他` in Chinese) holding `version` and `genautocomplete` -- nine top-level nodes |
| Right, top | parameter form: Input files, Working directory, Command parameters, Global parameters, Extra arguments, Notes, Documentation |
| Right, bottom | output panel: Result / Errors / Log / Command tabs with Run, Stop, Save result, Copy result, Open output file, Word wrap, Clear |
| Status bar | left: seqkit path and run notices; right: live preview of the command line |

Region-by-region detail: [interface guide](interface-guide.md).

## 9. When something goes wrong

| Symptom | What to do |
| --- | --- |
| Header badge reads `seqkit not found` | supply the executable by any route in step 3, then press **Auto-detect** + **Test** in **Settings** |
| Pressing **Run** opens an "Incomplete parameters" dialog | the dialog lists what is missing and the offending rows turn red; per-command requirements are in [command guide](command-guide.md) |
| Selecting `scat` and pressing Run gives `one of --find-only / --time-limit is required` | `scat` puts an fsnotify watcher on the directories it is given and loops, so with no exit condition it never returns; the interface refuses the run before creating a process. Tick `--find-only` (concatenate what already exists, then exit) or `--time-limit` (exit after this long with no activity); `--wait-pid` does not count, its default `-1` leaves that timer disabled |
| An amber **Version mismatch** badge appears | the parameter table was generated from SeqKit 2.14.0 and the detected binary differs, so individual options may not match; use 2.14.0 or regenerate the table ([development guide](development.md)) |
| Non-zero exit code and an empty **Result** tab | seqkit writes its complaint to stderr; read it verbatim in the **Errors** tab (the **Log** tab repeats it next to the full command line) |
| You left the file list empty and got nothing back | the interface does not proxy standard input; an empty list means seqkit reads an already-ended stdin. Add at least one file |
| Chinese text leaking into the English interface | none today: every key the code looks up exists in `i18n/zh_CN.json`; English mode deliberately renders untranslated keys as their own (English) key text |

Full checklist: [FAQ](faq.md).

## 10. Known limitations

Boundaries worth knowing before and after the first run; the complete list lives in [README.en.md](../../README.en.md#known-limitations):

- Only Windows x64 has been opened and driven by hand; macOS/Linux have code paths but no desktop verification and no packaged build.
- No stdin proxying and no pipe mode: input has to be file paths. The child's write channel closes the moment it starts, so a run with no input files exits 0 with nothing to show. The command that genuinely cannot stop on its own is `scat` (an fsnotify directory watcher), and pre-run validation refuses it without an exit condition.
- The parameter table is pinned to seqkit 2.14.0; other versions may lack flags or add unknown ones.
- The `default: 4` shown for `--threads` is the literal value recorded from seqkit 2.14.0's own `--help`; the interface never recomputes it from the local CPU count. Upstream's rule is `min(NumCPU, 4)`, overridden by `SEQKIT_THREADS` (`seqkit/cmd/root.go:113-128`). `genautocomplete --file` is pre-filled from the neutral placeholder the table stores (`$HOME/.bash_completion.d/seqkit.sh`), which the interface resolves to your own home directory.
- SeqKit is not redistributed: put it in `bin/` yourself or run `tools/fetch_seqkit.py`.
- The **Command** tab, **Copy command line**, the **Log** tab and the status bar all embed absolute paths to seqkit, to your input/output files, the working directory and the temporary file -- strings that normally contain your user name. Clean them before sharing.
- The preview is bounded by line and block limits; the complete stdout is in `seqkit-gui-*.out` in the system temp folder, and non-UTF-8 bytes are replaced on screen.
- Only one command runs at a time.

## 11. Where to go next

- Read every control in the window: [Interface guide](interface-guide.md)
- Follow a scenario step by step: [Detailed user guide](user-guide.md)
- What each of the 41 commands needs and how to set it up in the form: [Command guide](command-guide.md)
- Odd behaviour, limits and errors: [FAQ](faq.md)
- Schema regeneration, tests, packaging, macOS readiness: [Development guide](development.md)

Chinese versions of these documents live in [`docs/zh/`](../zh/).
