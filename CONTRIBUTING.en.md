# Contributing

Thanks for improving SeqKit GUI. This document covers local development and what a change must satisfy. Chinese version: [CONTRIBUTING.md](CONTRIBUTING.md).

SeqKit GUI is an **unofficial** desktop graphical front end for [SeqKit](https://github.com/shenwei356/seqkit), the sequence toolkit by Wei Shen (MIT). It is not affiliated with, endorsed by, or maintained by the SeqKit project. It performs no sequence processing itself: it assembles arguments and runs the official `seqkit` executable.

## Setup

```bash
python -m pip install -r requirements.txt   # PySide6
python -m pip install pytest pyinstaller    # optional: tests and packaging
python tools/fetch_seqkit.py                # obtain seqkit into bin/
python -m seqkit_gui                        # launch
```

`bin/` is gitignored -- never commit the seqkit executable.

## Code layout

- `seqkit_gui/core/` holds everything interface-free: `spec.py` reads the parameter table, `builder.py` assembles the argument vector and validates before running (including `BOUNDED_RUN_FLAGS`, which refuses a `scat` run that has no exit condition before any child is created), `runner.py` executes asynchronously with QProcess and tees output, `seqkit_locator.py` finds the executable, `paths.py` isolates platform differences, `settings.py` persists preferences.
- `seqkit_gui/ui/` holds the widgets: `main_window.py` assembles the window, `param_form.py` builds the form from the parameter table, `output_view.py` shows results and logs, `widgets.py` contains the per-flag rows, `theme.py` defines the light/dark colour tokens, `i18n.py` loads the language catalogues.
- UI code never calls `subprocess` directly and never builds a shell command string; execution always goes through `core/runner.py` with an argument list.

## The parameter table is generated

`seqkit_gui/data/commands.json` is generated from SeqKit source -- **do not edit it by hand**:

```bash
python tools/extract_spec.py --build --seqkit-src ../../../seqkit-2.14.0
```

- `tools/spec-dumper` (Go) walks the cobra command tree and exports flag names, shorthands, types, defaults and verbatim usage text. This step needs the Go toolchain (`go.mod` declares `go 1.25.14`; the development machine reports `go1.27.0 windows/amd64`, and any toolchain at or above the declared version works). Before launching the dumper the script gives `GOPROXY` the fallback `https://goproxy.cn,https://proxy.golang.org,direct` (a direct connection to `proxy.golang.org` is unreachable on some networks) and sets `GOFLAGS=-mod=mod`; a `GOPROXY` you already exported is left alone.
- `--seqkit-src` runs `go mod edit -replace=github.com/shenwei356/seqkit/v2=<path>` with `tools/spec-dumper/` as the working directory, so the relative path above is resolved from there (it is the sibling `seqkit-2.14.0` checkout); use your own absolute path if your layout differs. The committed `tools/spec-dumper/go.mod` already carries a `replace` pointing at a local checkout.
- `tools/extract_spec.py` decides each control type, extracts enumerated choices, merges Chinese descriptions, and attaches the input-file contract and required-parameter constraints read from each command's `Run` body (the `CONTRACTS` table, with source file and line references).
- The whole chain is `seqkit source --(tools/spec-dumper, Go)--> tools/_build/spec_raw.json --(tools/extract_spec.py)--> seqkit_gui/data/commands.json`. The intermediate `tools/_build/spec_raw.json` is gitignored along with the rest of `tools/_build/`, and only `commands.json` is checked in; so when a `spec_raw.json` is already on hand, running the script without `--build` performs only the normalisation step and needs no Go.
- `tests/test_schema.py` pins that chain from both ends: `test_generated_from_dumper_not_handwritten` requires `commands.json` and `tools/spec-dumper/main.go` to exist together (a checked-in generated file must still have the generator it came from), while `test_schema_lists_every_subcommand_from_the_cli`, `test_every_command_help_is_reachable` and `test_global_flags_reach_every_command` compare the table against a real seqkit's command list and each command's `--help`, and `test_input_contracts_are_recorded_with_source_evidence` requires every command to carry an `evidence` reference.
- When the supported SeqKit version changes, regenerate the table, update the affected entries in `CONTRACTS`, and bump `SEQKIT_SUPPORTED_VERSION` in `seqkit_gui/__init__.py`.

Chinese text lives in `tools/translations/`: `usage_zh.json` is keyed by the English usage string, `command_zh.json` supplies command and group names. A parameter with no Chinese entry falls back to the English original.

## Tests

```bash
python -m pytest tests -q
python -m pytest tests -q --collect-only          # collection only
QT_QPA_PLATFORM=offscreen python -m pytest tests/test_i18n.py -q
```

The suite drives a real seqkit: it checks the command list and each command's `--help`, verifies argument assembly and validation rules, runs several end-to-end commands, and builds the window offscreen; cases needing seqkit skip themselves when no executable can be located. The case count moves with the code, so trust the command output. Add tests for new behaviour. Interface work that needs screenshots requires both switches:

```bash
export SEQKIT_GUI_SHOOT=1          # Windows cmd: set SEQKIT_GUI_SHOOT=1
python -m pytest tests/test_gui.py -q --with-screenshots
```

Without `--with-screenshots`, or without `SEQKIT_GUI_SHOOT=1`, the case skips. It writes into the gitignored developer folder `tools/_build/screenshots/`; the five finished images in `docs/screenshots/` were captured by hand from a real window and currently contain absolute paths and a user name from that machine, so refreshing them means working inside a scrubbed example directory first.

## Feedback and review

- Read [SUPPORT.md](SUPPORT.md) before opening an issue -- it lists where to ask and what counts as a bug. The forms are [`bug_report.yml`](.github/ISSUE_TEMPLATE/bug_report.yml), [`feature_request.yml`](.github/ISSUE_TEMPLATE/feature_request.yml), [`spec_mismatch.yml`](.github/ISSUE_TEMPLATE/spec_mismatch.yml) (schema versus CLI) and [`config.yml`](.github/ISSUE_TEMPLATE/config.yml) (extra contact links), all under `.github/ISSUE_TEMPLATE/`.
- Do not file a public issue for a vulnerability; follow the reporting route in [SECURITY.md](SECURITY.md).
- Use [`pull_request_template.md`](.github/pull_request_template.md) when opening a PR; every item it asks for corresponds to something you can run in this repository (tests, the version-consistency check, both language versions of a document).
- Community behaviour is covered by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
- Bilingual delivery is mandatory: a change to `docs/zh/` comes with its `docs/en/` counterpart, `README.md` with `README.en.md`, `CONTRIBUTING.md` with `CONTRIBUTING.en.md`.

## Interface conventions

- When adding visible text, also add it to `seqkit_gui/i18n/zh_CN.json` (keys are the English source text); abstract keys -- identifiers that are not already an English sentence, so falling back to the key would read badly -- need an entry in `en_US.json` too.
- Reference theme colours only through the tokens in `theme.py`. Text on filled surfaces stays white; do not use a lightened fill colour.
- Content is left-aligned; status and hint elements (progress, empty states, notices) are centred.
- Comments describe the current design and intent, not the history of changes.

## Commits and licensing

- Run the tests on your branch before committing; write commit messages that explain the motivation rather than listing edits.
- The licence self-check is `python tools/license_check.py`: it verifies that a release archive does not carry `bin/`, and that this project's and SeqKit's licence files are in place. Its last line reads `SUMMARY: seqkit-license=PASS  project-license=PASS` (the checks marked advisory report without failing).
- This project is MIT licensed; SeqKit's MIT notice is preserved in `THIRD-PARTY-LICENSES.md` and must stay.
- Do not commit anything from `bin/`, `build/`, `dist/` or `tools/_build/`.

## Packaging

```bash
python -m pip install pyinstaller
pyinstaller packaging/seqkit_gui.spec
python packaging/check_version.py            # do the version and name declarations agree?
python packaging/check_version.py --tag v1.0.0
```

This produces the onedir bundle `dist/SeqKit-GUI/` with a windowed `SeqKit-GUI.exe` (`console=False`) and the resources under `dist/SeqKit-GUI\_internal\seqkit_gui\{data,i18n,assets}`; put `seqkit.exe` into `dist/SeqKit-GUI/bin/` -- the recipe deliberately never collects seqkit and aborts the build if any of its files were collected. The bundle is onedir rather than onefile so that PySide6's LGPL requirement -- users must be able to replace the Qt libraries -- is met. `packaging/check_version.py` is standard library only: it prints the version and name it reads from `seqkit_gui/__init__.py`, `pyproject.toml`, `data/commands.json`, `tools/fetch_seqkit.py` and the spec, then exits 0 with `all declarations agree` when none of them disagree.
