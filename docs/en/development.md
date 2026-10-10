# Development guide

> This document describes **SeqKit GUI**, an unofficial desktop graphical front end for [SeqKit](https://github.com/shenwei356/seqkit), the sequence toolkit by Wei Shen (MIT). It is not affiliated with, endorsed by, or maintained by the SeqKit project, and it is not the official SeqKit graphical interface.

## 1. Repository layout

| Path | Contents |
| --- | --- |
| `seqkit_gui/main.py`, `__main__.py`, `__init__.py` | entry point (`python -m seqkit_gui`), `__version__ = "1.0.0"`, `SEQKIT_SUPPORTED_VERSION = "2.14.0"` |
| `seqkit_gui/core/` | non-GUI logic: `paths.py`, `spec.py`, `builder.py`, `runner.py`, `seqkit_locator.py`, `settings.py` |
| `seqkit_gui/ui/` | Qt widgets: `main_window.py`, `param_form.py`, `widgets.py`, `output_view.py`, `dialogs.py`, `theme.py`, `i18n.py` |
| `seqkit_gui/data/commands.json` | the generated parameter schema — the single source of truth for the form |
| `seqkit_gui/i18n/zh_CN.json`, `en_US.json` | interface-text catalogues |
| `seqkit_gui/assets/` | window/app icons (`app.png`, `app.ico`, …) |
| `tools/extract_spec.py` | normaliser that writes `commands.json` |
| `tools/spec-dumper/` | Go program that walks seqkit's cobra tree (`main.go`, `go.mod`, `go.sum`) |
| `tools/translations/` | `usage_zh.json` (per flag-usage string) and `command_zh.json` (per command and per group title) |
| `tools/fetch_seqkit.py` | installer-time downloader for the seqkit release binary |
| `tools/_build/` | gitignored scratch: cached `spec_raw.json`, `translation_worklist.json`, developer screenshots |
| `tests/` | pytest suite plus `tests/data/` FASTA/FASTQ samples |
| `packaging/seqkit_gui.spec` | PyInstaller onedir recipe |
| `packaging/entry.py` | frozen-app entry point; imports through the package name so the bundle's absolute imports resolve |
| `docs/en/`, `docs/zh/`, `docs/screenshots/` | documentation and the images they embed |
| `run.bat`, `run.sh`, `requirements.txt`, `pyproject.toml`, `LICENSE`, `THIRD-PARTY-LICENSES.md` | launchers, dependencies, metadata, licensing |

`bin/` is gitignored: the seqkit binary is never committed.

## 2. Development environment

```bash
python -m pip install -r requirements.txt     # PySide6>=6.6,<7 only
python -m seqkit_gui                          # or run.bat / ./run.sh
```

`requirements.txt` deliberately lists runtime dependencies only; `pyinstaller>=6.0` and `pytest>=8.0` are present but commented out, so install them explicitly when you need them. `pyproject.toml` carries metadata and shared tool configuration (`[tool.pytest.ini_options] testpaths = ["tests"]`) but no build backend — the application runs from the source tree.

Run the GUI headlessly with `QT_QPA_PLATFORM=offscreen` (the test suite sets it automatically in `tests/conftest.py`).

## 3. Architecture

### 3.1 Core modules

| Module | Responsibility |
| --- | --- |
| `core/paths.py` | every platform-specific path decision: `is_frozen()`, `package_dir()`, `project_root()`, `spec_path()`, `docs_dir()`, `executable_names()`, `bundled_dir()` |
| `core/spec.py` | frozen dataclasses `Flag`, `Inputs`, `Command`, `Group`, `Schema`; `load()` parses `commands.json` and caches it; `usable`, `in_groups()`, `flag_entries`, `global_flag_names` |
| `core/builder.py` | `RunRequest` + `FlagState` → `build_argv()`; `validate()` → `Validation`; `display_command()` renders the copyable command line with platform-correct quoting; `BOUNDED_RUN_FLAGS` names the subcommands that would never return on their own (`scat` → `find-only` / `time-limit`) and makes `validate()` refuse them before a child exists |
| `core/runner.py` | `SeqkitRunner`: `QProcess` with separate channels, incremental UTF-8 decoding, ANSI stripping, preview line limit, tee to a temp file, `RunResult` |
| `core/seqkit_locator.py` | `locate()` search order and trust gate (`_search_path()`, `_trusted_directories()`, `_acceptance()`, `is_native_executable()`), `probe_version()`, `looks_like_seqkit()` |
| `core/settings.py` | `Preferences` dataclass plus `QSettings` keys (organisation `seqkit-gui`, application `SeqKit GUI`) |

### 3.2 UI modules

| Module | Responsibility |
| --- | --- |
| `ui/main_window.py` | header bar, menus/shortcuts, command tree, run orchestration, language/theme switching, drag & drop |
| `ui/param_form.py` | `Section` (collapsible) and `CommandForm`: builds the sections and flag rows, collects `RunRequest` |
| `ui/widgets.py` | `FileListField` and `FlagRow` plus the editor classes (`bool`/`int`/`float`/`enum`/`text`/`list`/`in_file`/`out_file`/`dir`) |
| `ui/output_view.py` | the four tabs, run controls, truncation note, save/copy/open |
| `ui/dialogs.py` | `PreferencesDialog`, `AboutDialog`, the segmented `_Choice` control |
| `ui/theme.py` | `Palette` dataclass, `LIGHT`/`DARK`, generated `stylesheet()` |
| `ui/i18n.py` | `Catalog` with `tr()`; active language signal |

### 3.3 Request path

```
tree selection
   └─ CommandForm.set_command(command)        rows + notes built from the schema
        └─ user edits → changed signal        status bar shows display_command(argv)
             └─ Run → validate(request)       blocked with a message list on failure
                  └─ build_argv(request)      argv after the program name
                       └─ SeqkitRunner.start(program, argv, cwd)
                            └─ RunResult → OutputPanel.end_run(result)
```

`build_argv` walks `command.all_flags` in schema order, skips rows whose `enabled` is false, emits boolean rows as bare `--flag`, expands list rows into repeated `--flag value`, appends the input files, then the shell-split **Extra arguments**. Values that start with `-` become `--flag=value`.

## 4. Regenerating the parameter schema

```
seqkit source  ──(tools/spec-dumper, Go)──▶  tools/_build/spec_raw.json  ──(tools/extract_spec.py)──▶  seqkit_gui/data/commands.json
```

1. **`tools/spec-dumper/main.go`** imports `github.com/shenwei356/seqkit/v2/seqkit/cmd`, takes `cmd.RootCmd`, and walks the cobra tree. For each command it records `path`, `short`, `long`, `example`, `aliases`, `GroupID`, `Runnable`, `LocalFlags()` in declaration order (`SortFlags = false`) and the root `PersistentFlags()` that the command does not shadow. Nothing is guessed: flag names, shorthands, pflag types and default values are read from seqkit's own registrations.
2. **`tools/extract_spec.py`** turns that raw dump into the application schema. It adds only two kinds of information:
   - *widget hints* — `widget_for()` maps pflag types to a control and consults the name sets `INPUT_FILE_FLAGS`, `OUTPUT_FILE_FLAGS`, `DIR_FLAGS`, `SEQ_LIST_FLAGS`; `enum_options()` harvests choices from a parenthesised `a|b|c` list in the usage text (2–16 tokens), which is what produces the `--seq-type` combo box.
   - *usage contracts* — the `CONTRACTS` table records `inputs` (`files` / `paths` / `none`, `min`, `max`, `allow_stdin`, `allow_compressed`), `requires_any`, `requires_all`, `conditional`, `forbid_pairs`, `notes` and an `evidence` reference such as `grep.go:106,133`, i.e. the file and lines of the `Run` body the rule was read from. `tools/translations/usage_zh.json` and `command_zh.json` supply the Chinese flag and command text; strings with no entry are written to `tools/_build/translation_worklist.json`.

Commands in the schema and on disk:

| Quantity | Value |
| --- | --- |
| Commands | 41 (all runnable, none hidden) |
| Command-local flag rows | 353 |
| Inherited global flags | 11 (`seq-type`, `threads`, `line-width`, `id-regexp`, `id-ncbi`, `out-file`, `quiet`, `alphabet-guess-seq-length`, `infile-list`, `skip-file-check`, `compress-level`) |
| Groups | 8 declared by seqkit + 1 synthetic node **Other** for `version` and `genautocomplete`, which carry no group ID |

Commands:

```bash
python tools/extract_spec.py                 # reuse the cached tools/_build/spec_raw.json
python tools/extract_spec.py --build         # run the Go dumper first (requires Go)
python tools/extract_spec.py --seqkit-src C:/src/seqkit-2.14.0 --build
```

`--build` sets `GOFLAGS=-mod=mod` and a `GOPROXY` of `https://goproxy.cn,https://proxy.golang.org,direct`, then `go run .` inside `tools/spec-dumper/`; `--seqkit-src` applies a `go mod edit -replace github.com/shenwei356/seqkit/v2=<path>` first. `tools/spec-dumper/go.mod` currently pins seqkit v2.14.0, cobra v1.10.2, pflag v1.0.10 and carries a `replace` line pointing at the local source checkout. The script prints what it wrote, for example:

```
commands: 41  local flags: 353  inherited flags: 450
unique usage strings: 0
wrote seqkit_gui\data\commands.json
```

Only `commands.json` is checked in; `tools/_build/` is gitignored. Regenerate it whenever you point the app at a different seqkit release, then re-run the tests — the header bar's **Version mismatch** badge is what users see when the two disagree.

### 4.1 Editing a contract

Add or amend the entry in `CONTRACTS` and regenerate. `tests/test_schema.py::test_input_contracts_are_recorded_with_source_evidence` requires a non-empty `evidence` for **every** command, so a new rule must name the upstream file and lines it came from. Contracts are assertions about seqkit's behaviour, not preferences: `tools/_build/` holds the scratch probes used to confirm them, and the CLI itself is the authority.

## 5. Tests

```bash
python -m pytest tests -q                                  # full suite
python -m pytest tests/test_gui.py -q                      # window only
python -m pytest tests -q --collect-only                   # count and list
```

`tests/conftest.py` forces `QT_QPA_PLATFORM=offscreen` and provides the session fixtures `root`, `schema`, `sample_fasta`, `sample_fasta2`, `sample_fastq`, `seqkit_binary` (locator lookup, `pytest.skip` when the executable is absent), `qapp`, `isolated_settings` (autouse), plus the function fixtures `fresh_settings`, `wait_for`, `process_probe` and `fake_binary`. It registers five markers -- `gui`, `seqkit`, `slow`, `screenshot`, `launcher` -- and skips the screenshot and launcher cases unless `--with-screenshots` / `--with-launchers` are given.

The suite is split by concern; the number of cases in each module moves with the code, so the tables below state what each module checks and never a count. `python -m pytest tests -q --collect-only` prints the current collection.

| Module | What it pins down |
| --- | --- |
| `test_schema.py` | the generated table against the real CLI: command set equals `seqkit __complete`, every command's `--help` is reachable, shorthands appear, flag names spot-checked, version pinned to 2.14.0, all 11 global flags reachable on every command, widget values legal, every usage translated, every contract carries source `evidence`, `commands.json` committed |
| `test_compat_commands.py` | documentation promises versus the shipped binary: the README group table cross-checked against the schema, the minimal argv of every command, and whether the real binary accepts it |
| `test_builder.py` | argument assembly: token order, positional files behind `--`, booleans only when ticked, repeatable rows expanded, `--flag=-1`, extra arguments, paths with spaces, and every validation rule including the bounded-run refusal |
| `test_runner.py` | end-to-end runs against the real executable: version probe, `stats`, `grep` filtering, `--out-file`, stderr capture, a run with no input files, cancellation |
| `test_gui.py` | the window: a form for all 41 commands, flag descriptions shown, ticks flowing into the request, language and theme switching, both filters, files surviving a rebuild, detection, refusal of an incomplete form, one complete run, dialog construction, opt-in screenshots |
| `test_i18n.py` | bilingual coverage: every `tr("…")` key exists in `zh_CN.json`, the abstract keys exist in `en_US.json`, Chinese values really are Chinese, live switching, formatting tolerance, both palettes present |
| `test_locator.py` | seqkit missing, damaged or the wrong version, configured-path precedence, `probe_version` on a non-executable, the window's missing-seqkit path, `QSettings` round-trip, recent-file de-duplication and cap, the schema counts the interface displays, `stats` shadowing, `executable_names()` per platform |
| `test_security_locator.py` | where the application looks for seqkit is a trust decision: the working directory and relative `PATH` entries are never accepted as discoveries |
| `test_security_paths.py` | a Windows path reaches seqkit as exactly the argument the user meant: quoting, backslashes, control characters, long paths |
| `test_security_runner.py` | the refusal paths of `SeqkitRunner` report through `finished` instead of raising |
| `test_security_stdin.py` | no child the GUI starts may wait forever for something that never arrives; argv is passed through without re-parsing |
| `test_reliability_encoding.py` | byte-level behaviour of both channels: split multi-byte sequences, invalid UTF-8, ANSI stripping |
| `test_reliability_lifecycle.py` | what the window does while a child is still running, including close-while-running |
| `test_reliability_output_scale.py` | output far larger than a text widget: preview limit, dropped-line accounting, the full capture |
| `test_reliability_paths.py` | paths a Windows user actually has: Chinese, spaces, quotes, leading dashes, length |
| `test_quality_boundaries.py` | the architecture rules that keep this application a shell around seqkit |
| `test_quality_structure.py` | structural rules over the application code |
| `test_quality_signals.py` | signal wiring of the header bar's segmented controls |
| `test_quality_i18n.py` | catalogue integrity for the two JSON language tables |
| `test_release_consistency.py` | release-time invariants: one version in `__init__.py` and `pyproject.toml`, the recipe scraping it rather than hard-coding it, bundle name versus distribution name, `SEQKIT_SUPPORTED_VERSION` agreeing everywhere, no seqkit tracked by git and none collected into the bundle, documentation versions not contradicting the code |
| `test_fetch_seqkit.py` | the downloader without network: asset names per platform, URL shape, architecture aliases, archive member selection and ambiguity refusal, `sanity_check` rejecting HTML / stub files / the wrong image magic, atomic install and `--force` |

Cases that need seqkit are skipped automatically when no executable can be located, so prepare `bin/` first (see section 2).

`SEQKIT_GUI_SHOOT=1 python -m pytest tests/test_gui.py --with-screenshots -q` writes **developer** screenshots into the gitignored `tools/_build/screenshots/` (`light-zh.png`, `dark-en.png`); without the environment variable, or without `--with-screenshots`, the case skips. The five finished images under `docs/screenshots/` are captured from a real window by hand (grep → run → stats → `seq`, with language and theme switched) and then copied in; nothing in the repository regenerates them automatically, and they show paths from the machine they were taken on, so refreshing them means doing it inside a scrubbed example directory.

## 6. Extension points

| Task | Where |
| --- | --- |
| Support another platform | `core/paths.py` (`executable_names()`, `bundled_dir()`, `docs_dir()`) and the extra search prefixes in `core/seqkit_locator.py`; `tools/fetch_seqkit.py` `SUPPORTED_SYSTEMS`; `run.sh` is already POSIX |
| Add a language | `ui/i18n.py` `LANGUAGES` (and `FALLBACK_LANGUAGE`), a new `seqkit_gui/i18n/<code>.json`, and the `_Choice` built from `list(LANGUAGES.items())` in `ui/main_window.py` and `ui/dialogs.py`; untranslated keys fall back to `en_US.json` and then to the key itself |
| Add a theme | a `Palette` with the identical field set in `ui/theme.py`, registered in `PALETTES`, plus a chip in the header and `PreferencesDialog` |
| Change how a flag renders | `widget_for()` / the name sets in `tools/extract_spec.py`, then regenerate |
| Add an editor | a subclass of `EditorBase` in `ui/widgets.py` and a branch in `_make_editor()`; it must expose `text()`, `items()`, `set_text()`, `value_changed` |
| Add a pre-run rule | `CONTRACTS` in `tools/extract_spec.py`, then regenerate; `builder.validate()` needs no change as long as the rule fits `requires_any` / `requires_all` / `conditional` / `forbid_pairs` / `inputs`. A rule that cannot come from the table -- a command that never terminates -- is added to `BOUNDED_RUN_FLAGS` in `core/builder.py`, which feeds the same `requires_any` reporting path |

## 7. Conventions

- `from __future__ import annotations` everywhere; schema dataclasses are `frozen`, run state is not.
- The UI is built in code — no `.ui` files and no `pyuic` step.
- Interface text is looked up through `catalog.tr("English source text")`; every key you add needs an entry in `seqkit_gui/i18n/zh_CN.json`, which `tests/test_i18n.py` enforces by scanning the sources for `tr("…")` literals.
- Validation messages are rendered through the same catalogue (`Validation.messages(tr)`), so rule text lives in the JSON files, not in Python strings.
- Child processes are launched with an argument vector only; never build a shell string.
- No Windows-only API is used in the application; platform branching stays in `core/paths.py` and `core/seqkit_locator.py`.
- Paths are `pathlib.Path`; stdout/stderr are decoded incrementally as UTF-8 with replacement, and ANSI sequences are stripped before display.

## 8. Packaging

```bash
pip install pyinstaller
pyinstaller packaging/seqkit_gui.spec      # from the repository root
```

The recipe is **onedir** by default and windowed (`console=False`), excludes `tkinter`, and emits `dist/SeqKit-GUI/` with the Python and Qt payload under `dist/SeqKit-GUI/_internal/`. Onedir is a licensing decision as much as a size one: PySide6 is used under LGPLv3, which requires the Qt libraries to stay replaceable, and it avoids the per-launch self-extraction of a onefile bundle. `seqkit_gui/data`, `seqkit_gui/i18n` and `seqkit_gui/assets` are copied into the bundle under a `seqkit_gui/` prefix so `core/paths.py` resolves them exactly as it does in a source checkout. `data` is mandatory: the recipe stops the build with a message pointing at `python tools/extract_spec.py --build` when it is missing or empty. `i18n` and `assets` are optional and are reported and skipped, because the app falls back to the key text and the default icon. `app.ico` is likewise optional -- `icon_path()` picks `app.icns` on macOS and passes no icon when the file is absent, since a `.ico` there would make PyInstaller need Pillow.

A single self-contained executable -- for a USB stick or handing the app to one user -- is the same recipe in onefile mode: `SEQKIT_GUI_BUNDLE=onefile pyinstaller packaging/seqkit_gui.spec` produces `dist/SeqKit-GUI.exe` from the identical entry point, resources, licence texts, GPL filter and icon checks; only the wrapping differs. The costs are the LGPL ones above (the Qt libraries are embedded, not user-replaceable -- use onedir for anything published), a slower first launch while it extracts to the temp directory, and a single large binary that some antivirus scanners inspect more slowly. In this mode put seqkit in a `bin/` folder beside the exe (`dist/bin/seqkit.exe`); the search order is unchanged.

Then place the seqkit binary yourself:

```
dist/SeqKit-GUI/SeqKit-GUI.exe
dist/SeqKit-GUI/bin/seqkit.exe
```

`bin/` beside the executable is the second location the app searches, so no configuration is needed. Users may alternatively run `python tools/fetch_seqkit.py` or set the path in Settings. Keep SeqKit's MIT notice (in `THIRD-PARTY-LICENSES.md`) with any bundled binary and keep the word *unofficial* in the product name and documentation.

The interface icon set (`app-1024.png`, `app.png`, `app-32.png`, `app.ico`) is drawn by code, not shipped as artwork files: `python tools/make_logo.py` repaints the whole set with QPainter from parametric geometry (a black-and-white minimal tile carrying an abstract DNA ladder; the smallest frames drop alternate rungs). Change the colours or the shape and rerun it -- no image editor involved.

## 9. macOS readiness

Everything a Mac build needs that differs from Windows already exists: `core/paths.py` returns `("seqkit",)` for `executable_names()` and the same `bin/` folder for `bundled_dir()`; `core/seqkit_locator.py` adds `/opt/homebrew/bin` and `/usr/local/bin`, and checks executability with `os.access(path, os.X_OK)`; `tools/fetch_seqkit.py` knows Darwin (`seqkit_darwin_amd64.tar.gz`, extensionless member, `chmod +x` on install) and installs through `os.replace` so a crash cannot leave a half-written binary; `run.sh` prefers `python3`, honours `PYTHON`, and checks that PySide6 imports. `QtGui.QDesktopServices` and `QProcess` are cross-platform, and no Windows-specific module is imported anywhere in `seqkit_gui/`.

## 10. Licence and the "unofficial" label

- This project is MIT licensed; the text is in `LICENSE`.
- SeqKit is Wei Shen's MIT project. Its copyright notice and licence text are preserved in `THIRD-PARTY-LICENSES.md`, and the seqkit executable is neither committed here nor redistributed by this project.
- Because of that, `README.md`, `README.en.md` and every file under `docs/zh/` and `docs/en/` opens by saying the project is unofficial and unaffiliated, and the About dialog renders the same statement from two catalogue keys: `unofficial_disclaimer` and `seqkit_attribution` in `seqkit_gui/i18n/`. New documents follow that pattern rather than inventing new wording.
- Never commit the contents of `bin/`, `build/`, `dist/` or `tools/_build/` (`.gitignore` covers them). `seqkit_gui/data/commands.json` is the one generated artifact that has to be committed.

## 11. Next

- User-facing behaviour: [Interface guide](interface-guide.md), [Command guide](command-guide.md) and the [User guide](user-guide.md)
- Install and first run: [Getting started](getting-started.md)
- Limits and troubleshooting: [FAQ](faq.md)

Chinese versions of these documents live in [`docs/zh/`](../zh/).
