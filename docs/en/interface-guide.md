# Interface guide

> This document describes **SeqKit GUI**, an unofficial desktop graphical front end for [SeqKit](https://github.com/shenwei356/seqkit), the sequence toolkit by Wei Shen (MIT). It is not affiliated with, endorsed by, or maintained by the SeqKit project, and it is not the official SeqKit graphical interface.

SeqKit GUI has one window. Everything on it maps to one `seqkit` invocation: *pick a command, describe the run, press Run*.

## 0. Layout at a glance

```text
+--------------------------------------------------------------------------+
| Menu bar:  File   View   Tools   Help                                     |
+--------------------------------------------------------------------------+
| SeqKit GUI  [SeqKit 2.14.0]      Language: [简体中文|English]  Theme: [Light|Dark]  Settings  Documentation |
+---------------+----------------------------------------------------------+
| Search        |  seqkit grep                                             |
| +-----------+ |  Search for sequences by ID/name/sequence/motif          |
| | Basic ops | |  + parameter filter ----------------------------------+  |
| |  faidx    | |  v Input files   Add files Remove Clear Paste paths   |  |
| |  scat     | |    Working directory [____________________] Browse     |  |
| |  ...      | |  v Command parameters  16                              |  |
| | Searching | |  > Global parameters  11                               |  |
| |  ...      | |  > Extra arguments    v Notes       > Documentation    |  |
| +-----------+ +----------------------------------------------------------+
|   (left)      | Run Stop Save result Copy result Open output file        |
|               | Word wrap Clear                                  status  |
|               | [Result] [Errors] [Log] [Command]                        |
|               |   (bottom right: the output panel)                       |
+---------------+----------------------------------------------------------+
| Status bar left: seqkit path / run notice   right: live command preview   |
+--------------------------------------------------------------------------+
```

The window opens at 1320x860; the left/right split starts at 280 / 1040 and the form/output split uses stretch factors 3:2. Window geometry and the left/right splitter sizes are written on close and restored on the next start (`ui/geometry` and `ui/splitter`); the form/output split is not persisted — it is laid out from its 3:2 stretch factors on every start. Neither panel of the form/output split can be dragged to zero (`setCollapsible(..., False)`).

| Region | Contents |
| --- | --- |
| Header bar | brand `SeqKit GUI`, seqkit version badge, **Version mismatch** warning badge, `Language:` chips, `Theme:` chips, **Settings**, **Documentation** |
| Menu bar | **File**, **View**, **Tools**, **Help** |
| Left panel | command search box + command tree (width 280 px at first launch, resizable) |
| Right panel, top | the scrollable parameter form (`CommandForm`) |
| Right panel, bottom | the output panel (`OutputPanel`) |
| Status bar | left slot: seqkit path/source and run outcome; right slot: the command line that would be executed |

The left/right split and the form/output split are both `QSplitter`s; the form and the output panel never collapse to zero.

![Main window, English interface, dark theme](../screenshots/dark-en.png)

The screenshots referenced in this document are captured from a real window, with machine-local paths and user names masked or substituted; a clean, unmasked image has to be re-shot inside a scrubbed example directory that carries no real user name or project path.

## 1. Header bar

| Control | Behaviour |
| --- | --- |
| `SeqKit 2.14.0` badge | the version reported by `<binary> version`; tooltip is the full path. Reads `seqkit not found` when no binary was located |
| **Version mismatch** badge | appears only when the detected binary reports a version other than the 2.14.0 the parameter table was generated from; tooltip names both versions |
| **Language**: `简体中文` / `English` | switches the interface text immediately; no restart, no re-selection of the current command |
| **Theme**: `Light` / `Dark` | re-applies the stylesheet immediately |
| **Settings** | opens the preferences dialog (same as `Tools → Settings`, `Ctrl+,`) |
| **Documentation** | opens the `docs/` folder in the system file manager |

## 2. Menus and keyboard shortcuts

| Menu | Item | Shortcut | Action |
| --- | --- | --- | --- |
| File | Add input files | `Ctrl+O` | multi-select dialog; the chosen paths are appended to the Input files list |
| File | Run | `Ctrl+R` | validate and launch, same as the Run button |
| File | Recent files ▸ | — | the last input files, most recent first (15 kept and shown); picking one that has gone missing reports it in the status bar. **Clear list** empties it |
| File | Quit | `Ctrl+Q` | closes the window (stops a running seqkit after confirmation) |
| View | Expand all groups / Collapse all groups | — | command tree |
| View | Clear output | — | empties Result, Errors, Log and Command views and the output status line |
| View | Search commands | `Ctrl+L` | focuses the tree's search box and selects its text |
| View | Search parameters | `Ctrl+F` | focuses the form's parameter filter box |
| Tools | Settings | `Ctrl+,` | preferences dialog |
| Tools | Copy command line | `Ctrl+Shift+C` | copies the Command tab text to the clipboard |
| Tools | Locate seqkit executable | — | file dialog that stores the chosen path as the seqkit executable |
| Help | Open documentation folder | — | same as the header **Documentation** button |
| Help | SeqKit official documentation | — | opens <https://bioinf.shenwei.me/seqkit/> in the browser |
| Help | About SeqKit GUI | — | version, unofficial disclaimer, attribution, detected seqkit version, schema summary (`2.14.0 · 41 commands · 353 parameters · 11 global parameters`), MIT licence note |
| — | Run (form-level shortcut) | `Ctrl+Enter` | registered as `Ctrl+Return` on the form, with Qt's window shortcut context, so it fires anywhere in the window |

## 3. Command tree

Commands are listed under their seqkit group, sorted alphabetically inside each group. Rows read `name · summary`; hovering shows the full command path (`seqkit grep`) and the English summary. Group rows are bold and cannot be selected.

The search box above the tree filters by command name, alias, summary in the current interface language, and the English one-line description — substrings, case-insensitive, applied to every group at once. The tooltip of the search box reports how many commands matched. The selected command stays selected while you filter.

Nine top-level nodes appear for 41 commands: the eight seqkit groups plus a final node titled **Other** (其他 in Chinese) holding `genautocomplete` and `version`, which seqkit declares without a group ID.

| Group | Commands |
| --- | --- |
| Commands for Basic Operation | faidx, scat, seq, sliding, stats, subseq, translate, watch |
| Commands for Format Conversion | convert, fa2fq, fq2fa, fx2tab, tab2fx |
| Commands for Searching | amplicon, fish, grep, locate |
| Commands for Set Operation | common, duplicate, head, head-genome, pair, range, rmdup, sample, sample2, split, split2 |
| Commands for Edit | concat, mutate, rename, replace, restart, sana |
| Commands for Ordering | shuffle, sort |
| Commands for BAM Processing | bam |
| Commands for Miscellaneous | merge-slides, sum |
| Other (ungrouped) | genautocomplete, version |

## 4. The parameter form

The form is one scrollable column of collapsible sections. Clicking a section header toggles it; `▾` means open, `▸` means closed.

| Section | Default state | Contents |
| --- | --- | --- |
| **Input files** | open | file list plus the Working directory row; a hint line states the command's input contract. Titled **Input** for commands that take no files |
| **Command parameters** | open | one row per command-local flag; header shows the count |
| **Global parameters** | closed | the root persistent flags this command inherits (up to 11); header shows the count |
| **Extra arguments** | closed | free-text field, split with shell-like rules and appended after every flag option but *before* the positional input files |
| **Notes** | open, hidden when empty | the machine-read constraints, rendered as sentences through the interface catalogue: `one of --pattern / --pattern-file is required`, `--range is required`, `--by-seq is required because --only-positive-strand is enabled`, `--lower-case and --upper-case cannot be used together`, plus the Chinese/English guidance lines recorded per command |
| **Documentation** | closed | seqkit's own long help body and its worked examples (usage notes, region arithmetic, attention lists) |

Above the sections: the command title (`seqkit stats`, with `[alias: stat]` when aliases exist), its one-line summary, and the parameter filter box.

### 4.1 Input files

| Control | Behaviour |
| --- | --- |
| **Add files** | multi-select dialog; the default filter lists `*.fa *.fasta *.fq *.fastq *.gz *.bgzip *.bz2 *.xz *.zst *.sam *.bam` plus "All files" |
| **Remove** | drops the selected rows |
| **Clear** | empties the list |
| **Paste paths** | adds one path per line from the clipboard, tolerating surrounding quotes |
| Drag & drop | files dropped on the window or on the list are appended |
| Double-click | opens an edit dialog for that entry; the replacement goes through the same cleaning and de-duplication as adding, and an edit that would duplicate an existing entry is refused |

The list keeps entries in insertion order — that order is the order of positional arguments on the command line. Duplicate paths are ignored. For commands that take at most one file (`sample`, `sample2`, `split`, `split2`) the list switches to single selection.

The hint line states the contract, joined with ` · `, e.g. `at least 2 file(s)`, `at least 1 file(s)`, `at most 1 file(s)`, `Folders are searched recursively`, `This command takes no input files`, `STDIN is not supported`, `compressed input is not supported`, and for commands with no count limit `any number of files` followed by `when the list is empty seqkit reads a standard input that is already at end-of-file; the interface does not type into it`. The accepted-format string recorded in the schema (`fasta|fastq|fa|fq(+ compressed)`, or `bam|sam` for `bam`) is appended last and is always English.

### 4.2 Working directory

Plain text field with a **Browse** button. It is the child process's working directory, not a search path for the input files; relative paths given to seqkit resolve against it. When a command is selected, the field is filled with the default working directory from Settings, falling back to the folder of the first input file and then to your home folder. Leaving it empty at run time also falls back to your home folder.

### 4.3 Flag rows

Every flag becomes one row:

```
[ ] --pattern      -p            default: []        (right-aligned hint)
    <editor>
    search pattern. Multiple values supported: …    (usage text)
```

| Element | Notes |
| --- | --- |
| Checkbox labelled `--name` | the enable switch; see the semantics below |
| Shorthand label | monospace `-p`, empty for long-only flags |
| **required** badge | amber, on rows implicated in a `requires_all` / `requires_any` constraint |
| Editor | depends on the pflag type (table below) |
| Usage line | English usage as registered by seqkit, or the Chinese translation in Chinese mode |
| Tooltip | `-p, --pattern` / `type: stringSlice` / `default: []` / full usage text |

| Widget used by the schema | Control |
| --- | --- |
| `bool` | none — the row's checkbox is the flag itself |
| `int` | spin box, range ±2147483647, pre-filled with seqkit's default |
| `float` | double spin box, six decimals |
| `enum` | editable combo box populated from the choices seqkit enumerates in its usage text |
| `text` | line edit, pre-filled with seqkit's default |
| `list` | multi-line editor, placeholder "one value per line" |
| `in_file` | line edit + **Browse** (open dialog) |
| `out_file` | line edit + **Browse** (save dialog) |
| `dir` | line edit + **Browse** (folder dialog) |

### 4.4 Form semantics

These four rules are the whole contract; they are implemented in `seqkit_gui/core/builder.py`.

1. **An unchecked flag is not passed at all.** The editor keeps seqkit's default value as a visual pre-fill, but nothing goes on the command line, so seqkit applies its own default. This is why the form can start with every box cleared.
2. **For boolean flags the checkbox *is* the flag.** Ticked → `--lower-case` is emitted. Unticked → the flag is absent.
3. **Repeatable flags take one value per line.** A `stringSlice` row such as `grep -p` expands to `--pattern a --pattern b --pattern c`. Empty lines are dropped.
4. **Combo boxes stay editable.** `--seq-type` offers `dna | rna | protein | unlimit | auto`, taken from seqkit's own usage text, and accepts anything you type over it. The same holds for `genautocomplete --shell` (`bash | zsh | fish | powershell`).

Two further behaviours worth knowing:

- A value beginning with `-` (e.g. a negative coordinate in `range -r -12:-1`, or `mutate -p -1:A`) is passed as `--flag=value` so seqkit does not read it as another option.
- The **Extra arguments** field is split with shell-like rules and appended after every flag option but *before* the positional input files, which themselves always follow the standalone `--` terminator. It is never evaluated, so `--by-seq` and `--seq-type dna` arrive as separate tokens.

### 4.5 Parameter filter

The filter box at the top of the form hides rows whose name, shorthand or **English** usage text does not contain the needle — useful on `seq` (27 flags) or `bam` (29). Matching is case-insensitive, so in Chinese mode a Chinese-language needle finds nothing and you search by `--name` or `-x`. `Ctrl+F` focuses the box. Hiding a row never clears it: the value stays in the request.

### 4.6 Validation before a run

Before launching, the form is checked against `requires_any`, `requires_all`, `conditional`, `forbid_pairs` and the input-file contract -- all read out of seqkit's own source -- plus the bounded-run rule for `scat`. A failing form produces a dialog listing each problem in the current interface language, marks the offending rows red, and does not start a process.

The `scat` rule lives in code rather than in the parameter table (`BOUNDED_RUN_FLAGS` in `seqkit_gui/core/builder.py`): `scat` installs an fsnotify watcher on the directories it is given and loops until told how to stop, so the run is refused unless `--find-only` or `--time-limit` is ticked. Notes renders the four table-recorded families only (`_build_notes()` in `ui/param_form.py`), so selecting `scat` shows an empty Notes section while **Run** still reports `one of --find-only / --time-limit is required`. Per-command rules: [command guide](command-guide.md).

![Form sections for the stats command](../screenshots/dark-en-params.png)

## 5. Output panel

| Tab | Source |
| --- | --- |
| **Result** | stdout, live |
| **Errors** | stderr, live (red text) |
| **Log** | stderr plus the command line and the run outcome, one merged history |
| **Command** | the exact command line that was launched, quoted for the current shell |

| Button | Behaviour |
| --- | --- |
| **Run** | validates the form and launches seqkit; replaced by **Stop** while a run is active |
| **Stop** | asks the child process to terminate; escalates to kill after 4 s |
| **Save result** | saves the complete stdout capture to a file you choose (default name `seqkit-result.txt` in your home folder) |
| **Copy result** | copies the **Result** tab text to the clipboard; when that preview is empty it reads the temporary file instead, so a truncated or `-o` run still yields the full data |
| **Open output file** | opens the temporary file holding the complete stdout with the system default handler |
| **Word wrap** | toggle; views start unwrapped with a horizontal scrollbar, which keeps FASTA and TSV columns readable |
| **Clear** | empties all four views |

The right-hand status label summarises the last run: outcome (`Done` / `Failed` / `Cancelled` / `Failed to start`) · `exit code N` · `elapsed N.NNs` · `output <bytes>`. A non-zero exit switches the panel to the **Errors** tab automatically; when the launch itself failed, the Errors and Log tabs each gain a localised hint about what to check (the executable path, antivirus interference).

### 5.1 Large output

stdout is always written through to a temporary file (`seqkit-gui-<random>.out` in the system temp folder) while the bytes are simultaneously streamed into the preview. The Result tab stops after the preview line limit (default 5000, set in **Settings → Output line limit**, range 500–200000) and appends a notice that the preview was truncated. The complete data is always available through **Save result** and **Open output file**; the byte count in the status line refers to the whole run, not to the preview. Each view additionally keeps at most the most recent 20000 blocks of text, and ANSI colour codes emitted by seqkit are stripped before display.

## 6. Status bar

| Slot | Normally | After a run |
| --- | --- | --- |
| Left | `<seqkit path>  (configured/bundled/path)`; when nothing was found, the retrieval hint instead | success with output: `Finished, see the Result tab` plus the temporary file path; success with no output: `Finished without writing anything to standard output`; failure: the seqkit path again |
| Right | the command line the current form assembles, updated with every tick and keystroke (hover the label to read one that is too long to fit); straight after a lookup it reads `41 commands · Schema 2.14.0` | unchanged |

The `(configured/bundled/path)` label and the word `Schema` are literals in `ui/main_window.py`, not catalogued text, so they stay English in both interface languages.

## 7. Settings

`Settings` (also `Tools → Settings`, `Ctrl+,`) holds six values:

| Field | Effect |
| --- | --- |
| **SeqKit executable** | path used before `bin/` and `PATH`; empty means auto-detect. **Auto-detect** calls the locator with an empty configuration, so it searches `bin/` and then `PATH` (plus the macOS prefixes) and fills the box with whatever it finds; **Browse** opens a file dialog |
| *(version line)* **Test** | runs `seqkit version` on the typed path and shows the version string, `Could not run this file`, or `seqkit not found` |
| **Language** | `简体中文` / `English`, applied immediately |
| **Theme** | `Light` / `Dark`, applied immediately |
| **Output line limit** | preview lines in the Result tab, 500–200000 in steps of 500 (default 5000); it changes only the preview, never the captured file |
| **Default working directory** | pre-fills the Working directory field; empty defaults to the first input file's folder, then your home folder |

The dialog works on a copy and writes on **OK** only; **Cancel** discards.

## 8. The About dialog

**Help → About SeqKit GUI** (`ui/dialogs.py`) shows, in this order: the name `SeqKit GUI`, the application version, the unofficial disclaimer, the SeqKit attribution, the detected seqkit version string (mouse-selectable, or `seqkit not found`), the schema summary line, and the licence line. The schema summary is computed from the loaded table, not typed in:

```
Schema: 2.14.0 · 41 commands · 353 parameters · 11 global parameters
```

In Chinese mode the same line reads `参数表: 2.14.0 · 41 个命令 · 353 个参数 · 11 个全局参数`. The licence line reads `License: MIT` plus a pointer to `THIRD-PARTY-LICENSES.md`, and the two disclaimer paragraphs are the `unofficial_disclaimer` and `seqkit_attribution` catalogue entries.

## 9. Language, theme and stored preferences

Interface strings are read from JSON catalogues (`seqkit_gui/i18n/zh_CN.json`, `en_US.json`) rather than Qt translation files. Keys are the English source text, so a key missing from a catalogue falls back to the English catalogue and then to the key itself. The two catalogues are not symmetric: the invariant is that the `en_US.json` key set is a **subset** of the `zh_CN.json` key set, not that they are equal — at the time of writing `zh_CN.json` holds 125 keys and `en_US.json` 53, and both counts move with the interface, so treat `python -c "import json;print(len(json.load(open('seqkit_gui/i18n/zh_CN.json',encoding='utf-8'))))"` as the authority rather than any number here. Every key the code looks up exists in `zh_CN.json`, so Chinese mode never shows fallback text; English mode renders the keys that are absent from `en_US.json` as their own key text, which is already an English sentence. What still reads as English inside a Chinese interface is what the code writes literally: the flag tooltip's `type:` / `default:` lines and its fourth line, the **Documentation** section (seqkit's own long help and examples), the accepted-format hint `fasta|fastq|fa|fq(+ compressed)`, the `(configured/bundled/path)` and `Schema` status strings. Command summaries and flag descriptions come from the generated schema, which carries both languages.

Switching language keeps the current command, its input files and the working directory, and re-translates tree, form, output panel and menus in place. Switching theme re-applies a single generated stylesheet built from a palette: light uses a `#f5f6f8` window with `#ffffff` surfaces, dark a `#1b1d21` window with `#22252a` surfaces, and both share one accent treatment with white text on filled surfaces.

![Chinese interface with a flag-heavy command](../screenshots/light-zh-many-flags.png)

Preferences persist through `QSettings` under organisation `seqkit-gui`, application `SeqKit GUI` -- on Windows the registry key `HKEY_CURRENT_USER\Software\seqkit-gui\SeqKit GUI`.

| Key | Meaning |
| --- | --- |
| `general/seqkit_path` | the configured seqkit path |
| `general/language` / `general/theme` | interface language and theme |
| `general/working_dir` | default working directory |
| `ui/output_line_limit` | preview line limit |
| `ui/geometry` / `ui/splitter` | window size and position, left/right split |
| `files/recent` | recent input files (15 kept, the same 15 listed in the menu) |

There is no reset button in the window; deleting that registry key is what returns the application to its defaults.

## 10. Tips

| What you want | How |
| --- | --- |
| Run it once, then reproduce it in a terminal | `Ctrl+Shift+C`, or read the live preview in the right status slot |
| Find a parameter | `Ctrl+F` to focus the filter, then type a flag name or shorthand |
| Find a command | type into the **Search commands** box -- it also matches Chinese summaries and the aliases `stat`, `dup`, `concate`, `rotate` |
| See more of a large output | raise the line limit in Settings, or press **Open output file** |
| Keep FASTA/TSV columns aligned | leave **Word wrap** off; the views start unwrapped |
| Move to another machine | copy the project folder plus `bin/seqkit[.exe]`; preferences live in the registry, not in the folder |

## 11. Next

- Every command and its required parameters: [Command guide](command-guide.md)
- Task recipes, step by step: [Detailed user guide](user-guide.md)
- Behaviour under stress: [FAQ](faq.md)
- Getting started from scratch: [Getting started](getting-started.md)

Chinese versions of these documents live in [`docs/zh/`](../zh/).
