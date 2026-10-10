# FAQ

> This document describes **SeqKit GUI**, an unofficial desktop graphical front end for [SeqKit](https://github.com/shenwei356/seqkit), the sequence toolkit by Wei Shen (MIT). It is not affiliated with, endorsed by, or maintained by the SeqKit project, and it is not the official SeqKit graphical interface.

## Installation and startup

**Does the GUI process sequences itself?**
No. It assembles an argument vector and runs the external `seqkit` binary through `QProcess`, streaming stdout and stderr back into the panel. Every biological result comes from upstream SeqKit; if a result looks wrong, the same command line on a terminal produces it.

**Where do I get `seqkit`? It is not in the repository.**
Upstream release binaries are roughly 28 MB and are not committed (`bin/` is gitignored). Run `python tools/fetch_seqkit.py` (downloads the official 2.14.0 release for your platform into `bin/`), copy a `seqkit.exe` into `bin/`, put seqkit on `PATH`, or point Settings at an existing install.

**The app starts but every run fails with "seqkit not found".**
The header badge and the left status slot show what the lookup found. The order is: the path configured in Settings → `bin/` next to the app and `bin/` at the project root → `PATH` (plus `/opt/homebrew/bin` and `/usr/local/bin` on macOS). Each candidate then has to pass one shared gate: an existing file whose header is an image this machine can execute (`MZ` on Windows, `\x7fELF` on Linux, Mach-O on macOS); Windows additionally refuses `.bat`/`.cmd`/`.com`/`.ps1`/`.vbs`/`.js`/`.lnk`/`.url`, non-Windows requires the execute bit. Anything sitting directly in the working directory is refused unless it is the path you chose in Settings, and empty or relative `PATH` entries are skipped. Use **Tools → Locate seqkit executable**, or Settings → **Auto-detect** / **Test**.

**Antivirus or Windows Defender quarantines `bin/seqkit.exe`.**
A single ~28 MB Go binary that is downloaded at install time is a familiar false positive. Restore the file, add an exclusion for the project's `bin/` folder, and restart the app; or keep seqkit somewhere else entirely and point Settings at it, since that path has the highest precedence in the lookup.

**Which Python and Qt do I need?**
Python 3.10+ and `PySide6>=6.6,<7` — the only runtime dependency (`python -m pip install -r requirements.txt`). No NumPy, no BioPython, no Qt Designer files.

**Language or theme needs a restart?**
It does not. Both switch in place: language re-translates the tree, form, output panel and menus while keeping the selected command, its input files and the working directory; theme re-applies one generated stylesheet.

**Is macOS or Linux supported?**
Windows x64 is the only platform this window has been opened and driven by hand, and the only one any screenshot was taken on. The macOS/Linux branches genuinely exist in the code -- `platform.system()` checks in `seqkit_gui/core/paths.py` and `seqkit_gui/core/seqkit_locator.py`, the Darwin-only `/opt/homebrew/bin` and `/usr/local/bin` prefixes, `run.sh`, the `Darwin`/`Linux` entries of `tools/fetch_seqkit.py` -- but nobody has run the interface interactively on a real macOS or Linux desktop, and no bundle has been produced for either. Linux is in exactly the same position as macOS.

**Double-clicking `run.bat` flashes a window and exits.**
The launcher prints the reason and pauses. `python was not found on PATH` means Python is missing or was installed without "Add Python to PATH"; a second message covers the Microsoft Store alias that answers to `python` but never runs, and a third covers an interpreter older than 3.10 (the requirement in `pyproject.toml`). Install Python 3.10+ from <https://www.python.org/downloads/>, or launch with a specific interpreter: `python -m seqkit_gui`. On POSIX the same checks live in `run.sh`, which also honours `PYTHON=/path/to/python3.12 ./run.sh`.

**Where are my preferences kept?**
In `QSettings` under organisation `seqkit-gui`, application `SeqKit GUI` — on Windows, the registry key `HKEY_CURRENT_USER\Software\seqkit-gui\SeqKit GUI`. Stored values: seqkit path, language, theme, output line limit, default working directory, window geometry, splitter sizes and the recent-file list. The app offers no in-window reset button.

## Running commands

**I never touched a flag, yet its box shows a value. Will that value be sent?**
No. Editors are pre-filled with seqkit's own default purely as a hint. **A flag row whose checkbox is unticked contributes nothing to the command line**, so seqkit applies its built-in default. Tick the box to opt in.

**So how do I turn off a flag whose default is on?**
Boolean rows send nothing when unticked. The builder does have a rule for a true-default boolean — unchecking it emits `--flag=false` — but no flag in the 2.14.0 parameter table declares a `true` default, so in practice this never fires. Use **Extra arguments** if you need an explicit `--flag=false`.

**Why won't my command run? A dialog lists what is missing.**
Pre-run validation, using constraints read out of the body of each seqkit command's `Run` function: `requires_any` (one of a set), `requires_all` (all of a set), `conditional` (enabling A obliges B), `forbid_pairs` (A and B cannot both be on) and the input-file contract. The offending rows are highlighted in red and the dialog quotes them, e.g.:

```
one of --pattern / --pattern-file is required
--range is required
at least 2 input file(s) required
--lower-case and --upper-case cannot be used together
```

The dialog also names the trigger of a conditional rule (`--by-seq is required because --only-positive-strand is enabled`) and refuses a command whose contract bans positional files (`this command does not accept input files as arguments`).

The same rules are always visible in the form's **Notes** section. See [command guide](command-guide.md#0-how-to-read-an-entry) for the per-command list.

**`pair` has no Input files section — a bug?**
Intentional. `pair`, `version` and `genautocomplete` accept no positional arguments (`inputs.kind = "none"`), so the file list is hidden and any file added anyway is rejected with `this command does not accept input files as arguments`. Give `pair` its mates through `-1/--read1` and `-2/--read2`.

**I left the file list empty because the hint says the command takes "any number of files". Nothing happens.**
The GUI closes the child's standard input as soon as the process starts, so an empty list gives seqkit an immediate end of input rather than a hang: the command finishes with no records, which usually means an empty or header-only table. **Add at least one file** for any real run. There is no "pipe from another tool" mode -- seqkit reads files the GUI passes it, not a stream the GUI feeds it. The hint line spells this out: `when the list is empty seqkit reads a standard input that is already at end-of-file; the interface does not type into it`.

**`faidx` refuses my `.fasta.gz`; `common` refuses one file.**
Those are the declared contracts, shown in the hint line under *Input files*: `faidx` sets `STDIN is not supported` and `compressed input is not supported` and needs at least one file; `common` and `concat` need at least two; `sample`, `sample2`, `split` and `split2` accept at most one; `scat` takes paths and reads folders recursively; `watch` needs at least one file and keeps running.

**`scat` refuses to start: `one of --find-only / --time-limit is required`.**
`scat` is not a one-shot command -- upstream puts an fsnotify watcher on the directories you name and loops (`seqkit/cmd/scat.go`), so a run with no exit condition would leave the panel stuck on "Running" with nothing to show. `core/builder.py` therefore treats it like a missing required flag and refuses the run *before* the child is created. Tick `--find-only` to concatenate the files that already exist and exit, or `--time-limit` to watch for a fixed period. `--wait-pid` is not accepted as an exit condition, because its default `-1` means that timer is switched off.

**`watch` looks stuck.**
It genuinely is still running: `watch` polls the file and prints on the interval you set, and only **Stop** ends it. The interface adds no exit condition of its own to `watch`. `bam` is not a watching command -- it exits when its chosen mode finishes; use `--dump` to have it print histogram data to stderr instead of plotting.

**Why can't I type `--pattern a,b` in the pattern box?**
Repeatable rows (`stringSlice`, e.g. `grep -p`, `fx2tab -C`, `translate -f`, `subseq --feature`) use a multi-line editor: **one value per line**, expanded into `--pattern a --pattern b`. Empty lines are ignored. If you prefer comma syntax, put the whole `-p "a,b"` in **Extra arguments**.

**My value starts with a dash and got rejected by seqkit.**
Values beginning with `-` are emitted as `--flag=-1` instead of `--flag -1`, so negative coordinates (`range -r -12:-1`, `mutate -p -1:A`) survive. If you bypass the rows via **Extra arguments**, you are responsible for that quoting.

**Where does the process actually run?**
In the **Working directory** field; when it is empty, in your home folder. Relative paths inside the command resolve there, which is why `rename`'s default output folder `renamed` appears next to the working directory, not next to your input file.

**`--threads` shows `default: 4`. Is that computed from my CPU?**
No. `4` is the literal default seqkit 2.14.0 prints in its own help (`-j, --threads int … (default 4)`), recorded verbatim into the parameter table when the table was generated; the interface never recomputes it from `os.cpu_count()` or any other local information. Leaving the row unticked sends no `--threads` at all, so the thread count is whatever your seqkit decides at run time -- its usage text mentions the `SEQKIT_THREADS` environment variable.

**Can I reuse what the GUI built?**
Yes. The **Command** tab holds the exact command line, quoted for your shell; `Ctrl+Shift+C` (or **Tools → Copy command line**) copies it. Re-running it in a terminal is equivalent. Note what that costs you in privacy: the copied text, the **Log** tab and the status bar all contain the absolute path of your seqkit binary, the absolute paths of your input and output files, the working directory and the temporary file path -- strings that normally embed your user name and drive letter. Strip them before pasting into an issue, a chat or a manuscript.

## Command-specific pitfalls

| Command | Pitfall | What to do |
| --- | --- | --- |
| `faidx` | accepts neither stdin nor compressed input | give at least one uncompressed FASTA file |
| `pair` | takes no positional files | use `-1/--read1` and `-2/--read2` |
| `sample`, `sample2`, `split`, `split2` | accept at most one input file | run once per file; `split2`'s paired input still goes through `--read1`/`--read2` |
| `split2` | interleaved and paired output files overwrite each other | the output name must contain `{read}` |
| `sample`, `sample2` | paired mates sampled to different reads | use the same `--rand-seed` for both runs |
| `sliding` | `--window` without `--step` | both are required together |
| `subseq` | `--bed` ticked with `--feature` | mutually exclusive; `--feature` applies only to `--gtf` |
| `locate` | `--use-regexp` or `--degenerate` with `--max-mismatch` | mutually exclusive; drop `--max-mismatch` |
| `seq` | `--lower-case` with `--upper-case`, or `--dna2rna` with `--rna2dna` | mutually exclusive; pick one |
| `sort`, `shuffle`, `split` | `--keep-temp` or `--update-faidx` ticked alone | both require `--two-pass`; the Notes section also states that two-pass mode takes one file |
| `watch` | looks stuck | it polls and prints on the `--print-freq` interval until **Stop**; the interface adds no exit condition of its own |
| `scat` | refuses to start | see the `scat` entry above: tick `--find-only` or `--time-limit` |
| `bam` | wanted data rather than a plot | `--dump` prints the histogram data to stderr; `bam` itself exits when its mode finishes |
| `merge-slides` | output file same as an input file | choose a different output path |
| `version` | `--check-update` reaches out to the network | leave it unticked on an offline machine |
| `genautocomplete` | `--file` is pre-filled from the neutral placeholder the table stores, `$HOME/.bash_completion.d/seqkit.sh`, which the interface resolves to your own home directory | tick `--file` and confirm or edit the destination before running |

## Output and files

**The Result tab is empty but the run says `Done`.**
seqkit wrote to a file instead of stdout. Typical cases: `-o/--out-file` ticked, `faidx` (creates `x.fa.fai` and prints nothing), `rename -m`, `genautocomplete`, `split`/`split2`/`pair` (write into an output directory), `watch`/`bam` with `-O/--img`. When the exit code is 0 and no bytes were produced, the status bar reports `Finished without writing anything to standard output`.

**What does "Output preview truncated" mean?**
The Result tab shows only the first *N* lines (default 5000; Settings range 500–200000, and the runner floors the limit at 200). All stdout bytes are written through to a temporary file during the run, so nothing is lost. Use **Save result** to copy it, or **Open output file** to open it with the system default handler.

**Where is that temporary file and is it cleaned up?**
`seqkit-gui-<random>.out` in your system temp directory (on Windows typically `C:\Users\<you>\AppData\Local\Temp`). SeqKit GUI leaves it in place after the run; the operating system's temp policy removes it.

**Red text in the Errors tab, but exit code 0.**
seqkit logs `[INFO] ...` and progress to stderr. The Errors tab shows stderr verbatim, so informational lines appear there. The Log tab merges stderr with the command line and the run outcome. ANSI colour codes are stripped for both.

**A very long line is cut off at the right edge.**
Views start unwrapped so that FASTA and TSV columns line up; toggle **Word wrap** to fit lines to the panel. Each view also keeps only the most recent 20000 blocks of text.

**The Command tab shows a quoted path with spaces — is that what ran?**
The GUI passes an argument *vector* to `QProcess`, never a shell string, so `"C:/tmp/my reads 1.fa"` reaches seqkit as one argv entry. The quoting you see in the Command tab is only for human copy-paste.

**My run is stuck. How do I abort?**
**Stop** sends a terminate request and escalates to a kill after 4 seconds; the outcome line reads `Cancelled`. Closing the window while seqkit is running asks whether to stop it and quit; answering No keeps the window open.

## Appearance and behaviour

**Why do some flags get a drop-down and others a plain box?**
A row becomes an editable combo box only when seqkit's own usage text enumerates the choices in parentheses as `a|b|c` (between 2 and 16 tokens). That catches `--seq-type` (`dna|rna|protein|unlimit|auto`) and `genautocomplete --shell`. Descriptions written as prose lists — `stats -E/--fq-encoding` (`'sanger', 'solexa', 'illumina-1.3+', …`) — stay plain text boxes. Every combo box remains editable, so a value seqkit did not advertise can still be typed in.

**The parameter filter does not find anything when I type Chinese.**
The filter matches the flag name, the shorthand and the **English** usage text. Search by `--name` or `-x` in either interface language.

**What is the amber "Version mismatch" badge?**
The detected binary reports a different version than 2.14.0, the release the parameter table was generated from. The form still runs commands, but a flag may be missing, added or renamed relative to your binary. Either install 2.14.0 or regenerate the schema ([development guide](development.md#4-regenerating-the-parameter-schema)).

**`genautocomplete --file` shows a path with `$HOME` in it.**
Upstream defines that flag's default as a runtime expansion of the home directory, so the schema stores the neutral form `$HOME/.bash_completion.d/seqkit.sh` rather than any one machine's path. The interface resolves `$HOME` to your own home directory when it pre-fills the field; no shell is involved in the command it builds, so check the resolved destination before running it.

**Are gaps, case and ambiguous bases handled by the GUI?**
No. Those are seqkit options (`-G/--gap-letters`, `-i/--ignore-case`, `-v/--validate-seq`, …) exposed as rows exactly as seqkit declares them.

## Packaged build and source tree

**The packaged build says seqkit is missing.**
By design: `packaging/seqkit_gui.spec` never collects seqkit, so after building, place the executable in `dist/SeqKit-GUI/bin/seqkit.exe`. That folder is the second stop in the lookup order, so no configuration is needed.

**Double-clicking the built exe shows no window at all.**
The bundle is windowed (`console=False`), so a start-up failure has no console to complain in. Run the source tree instead (`python -m seqkit_gui`) to read the traceback, and check that `dist/SeqKit-GUI/_internal/seqkit_gui/data/commands.json` survived the copy -- the app exits with code 2 without it.

**Preferences did not survive the move to another machine.**
They live in the registry (`HKEY_CURRENT_USER\Software\seqkit-gui\SeqKit GUI`), not in the project folder, so copying the folder copies nothing. Re-point the seqkit path in Settings.

**Where do I get a build?**
The repository publishes none: releases, tags and hosted artifacts are out of scope here. Build it yourself with `pyinstaller packaging/seqkit_gui.spec`, described in [development guide](development.md).

## Project and licence

**Is this an official SeqKit product?**
No. It is an unofficial desktop shell, unrelated to and not endorsed by SeqKit's author Wei Shen. The About dialog and every document state this.

**Can I redistribute the two together?**
The GUI is MIT (see [`LICENSE`](../../LICENSE)); SeqKit is MIT as well, and its notice is preserved in [`THIRD-PARTY-LICENSES.md`](../../THIRD-PARTY-LICENSES.md). Ship the GUI and let users supply seqkit themselves (`python tools/fetch_seqkit.py`), or keep SeqKit's notice next with its binary and label the combination as unofficial. PySide6/Qt is used under its LGPLv3 option, which is why packaged builds are onedir, not onefile.

**How many commands and options does the interface cover?**
41 commands across the eight seqkit groups (plus `version` and `genautocomplete`, which seqkit leaves ungrouped and which the tree shows under **Other**), 353 command-local flags and 11 inherited root flags — the About dialog reports them as `353 parameters · 11 global parameters`. All of it is generated from the CLI's own definition rather than written by hand.

## Next

- [Getting started](getting-started.md) · [Interface guide](interface-guide.md) · [Command guide](command-guide.md) · [User guide](user-guide.md)
- Build, test and packaging details: [Development guide](development.md)
- Where to ask for help and how to report a vulnerability: [SUPPORT.md](../../SUPPORT.md) · [SECURITY.md](../../SECURITY.md)

Chinese versions of these documents live in [`docs/zh/`](../zh/).
