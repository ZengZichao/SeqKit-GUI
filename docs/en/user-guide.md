# Detailed user guide

> This document is the English manual for **SeqKit GUI**, an unofficial desktop front end for [SeqKit](https://github.com/shenwei356/seqkit), the MIT-licensed sequence toolkit by Wei Shen. It is not affiliated with, endorsed by, or maintained by the SeqKit project, and it is not the official SeqKit graphical interface.

## 0. Which document to read

| You want to… | Read |
| --- | --- |
| Install the program and launch it once | [Getting started](getting-started.md) |
| Look up what one part of the window does | [Interface guide](interface-guide.md) |
| Look up how to fill one specific command | [Command guide](command-guide.md) |
| **Follow a scenario end to end** | **This guide** |
| Understand an error or odd behaviour | [FAQ](faq.md) |
| Change the code, rebuild the bundle | [Development](development.md) |

Everything here rests on one fact: **the interface only assembles an argument vector and calls the official `seqkit` executable; it performs no sequence work of its own.** Every "fill in X" below therefore corresponds to a real command line you can verify in the status-bar preview or the Command tab.

## 1. Prepare and launch

1. Install the Python dependency and obtain a `seqkit` executable as described in [getting started](getting-started.md) — via `python tools/fetch_seqkit.py`, by dropping it into `bin\`, or by having it on `PATH`.
2. Double-click `run.bat` (Windows) or run `./run.sh` (macOS/Linux); alternatively run `python -m seqkit_gui` from the project directory.
3. Check the header badge after launch: `SeqKit 2.14.0` means everything is ready. "seqkit not found" is covered by section 3.3 of the getting-started guide. A "Version mismatch" badge means the detected binary is not 2.14.0 — the interface still works, but flags may not line up exactly; hover the badge for the wording.

seqkit is located in the order **the path configured in Settings → the project's `bin\` folder → `PATH`**. A file you point Settings at is taken on your word; candidates from the other two sources must also answer `seqkit version` correctly, and an impostor binary is refused with the reason in the status bar.

## 2. Five concepts that cover every form

| Concept | Meaning |
| --- | --- |
| Tick = send | The checkbox decides whether the flag appears on the command line. Unticked, nothing is sent and seqkit applies its own default; the value pre-filled in the editor is a hint only |
| Boolean rows have no editor | Ticking the box sends `--flag`, e.g. `--by-seq` |
| One value per line | Repeatable flags (like `grep --pattern`) use a multi-line editor; each line becomes another `--pattern a --pattern b` |
| Combo boxes stay free-typable | The choices come from seqkit's own usage text, but you can type anything else |
| Negative values get an equals sign | A value starting with `-` is written `--flag=value` (like `--frame=-1`) so seqkit cannot misread it as a flag |

Positional input files always follow a standalone `--` terminator, so a file named `-weird.fa` is safe. Text in the **Extra arguments** box is split with shell-like quoting rules and appended before the terminator — use it for options the form does not model.

## 3. One full run in six steps

1. **Pick a command** in the left tree, or filter by name, summary, or alias (`stat`, `dup`, `concate`, `rotate`) in the search box.
2. **Add input files** with **Add files**, drag & drop from Explorer, or **Paste paths** (one per line from the clipboard). An empty list makes seqkit read an immediately-ended standard input — the interface never types into it — so add at least one file except for `version`, `genautocomplete` and `pair`.
3. **Check the working directory**: it is the child process's current directory (relative paths and `split` output land there); it defaults to the first input file's folder.
4. **Tick parameters**: expand *Command parameters* and tick only what this run needs; open *Global parameters* for `--out-file` and friends. Use `Ctrl+F` to focus the parameter filter.
5. **Run** with the Run button, `Ctrl+R`, or `Ctrl+Enter`. Failed validation names the problems in a dialog, marks the offending rows red, and no process is created.
6. **Read the output** across the Result / Errors / Log / Command tabs. The left status slot reports the outcome; the right one previews the command line (`Ctrl+Shift+C` copies it).

## 4. Task recipes

Verify every recipe in the Command tab; substitute your own file names.

### 4.1 Basic statistics

**Goal**: per-file sequence counts, total length, N50 and friends.

1. Select `stats` (alias `stat`).
2. Add one or more FASTA/FASTQ files.
3. Tick `--all` (the default table is the short one).
4. Run; the table appears in the Result tab.

```text
seqkit stats --all a.fa b.fq
```

For a file on disk, expand *Global parameters*, tick `--out-file` and type `stats.tsv`.

### 4.2 Pull out records by ID

**Goal**: extract a known set of IDs from `reads.fa`.

1. Select `grep`.
2. Add `reads.fa`.
3. Tick `--pattern` and put **one ID per line** in the multi-line editor (three lines become three `--pattern` flags).
4. Run.

```text
seqkit grep --pattern seq1 --pattern seq2 -- reads.fa
```

For many IDs, save them one per line into `ids.txt` and tick `--pattern-file` instead. Searching by sequence content: tick `--by-seq`; allow mismatches with `--max-mismatch`.

```text
seqkit grep --by-seq --max-mismatch 2 --pattern ATGG --pattern TTCG a.fa
```

### 4.3 Locate a motif and export coordinates

**Goal**: find every occurrence of `GGTT` as BED output.

1. Select `locate`.
2. Add `ref.fa`.
3. Tick `--pattern` with `GGTT`, and tick `--bed`.
4. Run; feed the coordinates to `subseq` or any BED consumer.

```text
seqkit locate --bed --pattern GGTT ref.fa
```

### 4.4 Length filtering and ID-only output

**Goal**: keep sequences of 100–500 bp and print only their IDs.

1. Select `seq`.
2. Add `a.fa`.
3. Tick `--min-len` with `100`, `--max-len` with `500`, and `--only-id`.
4. Run.

```text
seqkit seq --max-len 500 --min-len 100 --only-id a.fa
```

Reverse complement is the same command: tick `--reverse` and `--complement`.

### 4.5 To TSV and back

**Goal**: turn FASTA into an "ID, length, GC" table.

1. Select `fx2tab`, add `a.fa`.
2. Tick `--name`, `--length`, `--gc`.
3. Run; add a global `--out-file` to keep it.

```text
seqkit fx2tab --gc --length --name a.fa
```

The way back is `tab2fx` (give it the table); if huge rows raise `token too long`, tick `--buffer-size` with `2G`.

### 4.6 Deduplicate, sample, sort

| Goal | Command | Form |
| --- | --- | --- |
| Remove duplicates by sequence | `rmdup` | tick `--by-seq` (by ID: `--by-name`) |
| Draw 1000 records, reproducible | `sample` | tick `--number` with `1000`, leave `--rand-seed` at its default `11`, tick `--two-pass` (avoids loading everything into memory) |
| Sort by length, descending | `sort` | tick `--by-length` and `--reverse` |

```text
seqkit rmdup --by-seq a.fa
seqkit sample --number 1000 --rand-seed 11 --two-pass big.fq
seqkit sort --by-length --reverse a.fa
```

`sample`/`sample2`/`split`/`split2` accept **one** input file; extra entries are refused at validation.

### 4.7 Sliding-window subsequences

**Goal**: windows of 100 with step 50, including a shorter tail piece.

1. Select `sliding`, add `c.fa`.
2. Tick `--window` with `100`, `--step` with `50` (they must come together), and `--greedy`.
3. Run.

```text
seqkit sliding --greedy --step 50 --window 100 c.fa
```

### 4.8 Extract subsequences

**Goal A**: positions 100–200 of a record. Select `subseq`, tick `--region` with `1:100..200` (`record-index:start..end`).

```text
seqkit subseq --region 1:100..200 g.fa
```

**Goal B**: every CDS from a GTF annotation. Tick `--gtf` with `genes.gtf`, `--feature` with `CDS`, and leave `--gtf-tag` at its default `gene_id` (IDs then carry the gene name).

```text
seqkit subseq --feature CDS --gtf genes.gtf --gtf-tag gene_id genome.fa
```

`faidx` also extracts by region: tick `--region-file` and pick a text file with one region per line (like `chr1:1..100`). Note that `faidx` supports neither standard input nor gz/xz/zst compressed files.

### 4.9 Translate to protein

**Goal**: translation table 11, both strands, frame in the ID.

1. Select `translate`, add `cds.fa`.
2. Tick `--frame`, two lines: `1` and `-1`.
3. Tick `--append-frame`.
4. Tick `--transl-table` with `11`.
5. Run.

```text
seqkit translate --append-frame --frame 1 --frame=-1 --transl-table 11 cds.fa
```

Tick `--list-transl-table` and run once to list the available tables.

### 4.10 Split large files

**Goal A**: `one.fa` into 4 parts. Select `split`, tick `--by-part` with `4`.

**Goal B**: paired FASTQ, a million records per part. Select `split2`, tick `--by-size` with `1000000`, `--read1` with `r1.fq.gz`, `--read2` with `r2.fq.gz`, `--out-prefix` with `part_{read}` — **the prefix must contain the `{read}` placeholder for paired output**.

```text
seqkit split --by-part 4 one.fa
seqkit split2 --by-size 1000000 --out-prefix part_{read} --read1 r1.fq.gz --read2 r2.fq.gz
```

Split output lands in the **working directory**; aim it elsewhere with `--out-dir`.

### 4.11 Rename and edit

**Rename an ID prefix**: select `replace`, tick `--pattern` with `^seq` and `--replacement` with `sample_`.

**Point mutations**: select `mutate`, tick `--point`, two lines `2:C` and `-1:A` (position 2 becomes C, the last base becomes A).

```text
seqkit replace --pattern ^seq --replacement sample_ a.fa
seqkit mutate --point 2:C --point=-1:A ref.fa
```

### 4.12 Quick BAM statistics

**Prerequisite**: the BAM needs an index (`.bai`). Select `bam`, add one or more `.bam` files, tick `--stat`, run.

```text
seqkit bam --stat a.bam b.bam
```

Index-based counting into a file: tick `--idx-count`, and `--count` with `counts.txt`.

### 4.13 Generate a shell completion script

1. Select `genautocomplete` (takes no input files).
2. Choose a shell in `--shell` (`bash`/`zsh`/`fish`/`powershell`).
3. Tick `--file` and set the destination — the row is pre-filled with seqkit's own default, `$HOME/.bash_completion.d/seqkit.sh` (already expanded to your home folder), which you can override.

### 4.14 Also worth knowing

| Goal | Command | One-line recipe |
| --- | --- | --- |
| Sequences shared by several files | `common` | at least 2 input files; by sequence: `--by-seq` |
| Concatenate records with the same ID | `concat` (alias `concate`) | at least 2 input files |
| Pair up paired-end data | `fa2fq` / `pair` | `pair` takes no positional input — pick files with `--read1`/`--read2` |
| Restart a circular genome | `restart` (alias `rotate`) | one of `--new-start` or `--start-with` |
| Watch a live feature histogram | `watch` | it streams until you press **Stop** |

Flag-level detail for all 41 commands lives in the [command guide](command-guide.md).

## 5. Rules for input files

- **Formats**: FASTA/FASTQ, compressed as `.gz`, `.bgzip`, `.bz2`, `.xz` or `.zst`; the `bam` command accepts `.bam`/`.sam`. Per-command exceptions (`faidx` refuses compression and standard input) are spelled out in the grey hint line of the form.
- **Folders**: `scat` takes path lists and reads folders recursively; every other command's list is plain files.
- **De-duplication**: duplicate paths collapse to one; the list caps at 2000 entries and anything beyond is reported in the notice line.
- **In-place editing**: double-click an entry to correct it in a dialog; **Remove** drops the selection, **Clear** empties the list.
- **Quoted paths**: Explorer's "Copy as path" output (`"C:\...\a b.fa"`) loses its wrapping quotes automatically.
- **Long paths**: entries beyond 259 characters raise a Windows long-path warning rather than failing quietly inside seqkit.
- **Recent files**: the **File → Recent files** submenu keeps the last 15; clicking one adds it to the list, and **Clear list** empties the record.

## 6. Running and stopping

- While a run is active the form and output buttons lock (**Stop** excepted). You may still switch commands or filter — that only changes the view, not the running process.
- **Stop** first asks the process to terminate and force-kills it after 4 seconds if it is still alive; continuously streaming commands like `watch` need a manual stop.
- **The `scat` rule**: it watches a directory with fsnotify and never returns without an exit condition, so validation refuses to start it unless `--find-only` or `--time-limit` is ticked — no process is created at all.
- **Failed launches** show `Failed to start` in the status line, plus a localised hint in the Errors and Log tabs.
- **Exit codes**: a non-zero exit (not a manual cancel) switches the panel to the Errors tab. The complete stdout/stderr is always written to a temporary file; the on-screen preview is only the first N lines.

## 7. Handling results

| You want to… | Do this |
| --- | --- |
| See everything | The preview defaults to 5000 lines (500–200000 in Settings); past that, a truncation note appears at the end of the Result view — use **Open output file** or **Save result** for the full data |
| Keep the result | **Save result** copies the temporary file verbatim (suggested name `~/seqkit-result.txt`) |
| Copy the result | **Copy result**; when the view is empty it reads the saved file back, so truncation never limits the copy |
| Reproduce the run in a terminal | The Command tab, or `Ctrl+Shift+C` — the text is escaped per the platform's quoting rules |
| Keep columns aligned | leave **Word wrap** unticked |
| Clear the views | the **Clear** button, or **View → Clear output** |

## 8. Settings

Open with the header **Settings** button or `Ctrl+,`.

| Setting | What it does |
| --- | --- |
| SeqKit executable | empty means auto-detect; **Auto-detect** searches `bin\` then `PATH` again, **Browse** picks a file, **Test** runs `seqkit version` to verify |
| Language / Theme | take effect immediately, no restart; switchable from the header chips or here |
| Output line limit | preview only; the saved file always holds the complete output |
| Default working directory | the initial value of the working-directory field whenever a new command is selected |

Settings and window layout (size, splitter ratios) are remembered; on Windows they live under `HKEY_CURRENT_USER\Software\seqkit-gui\SeqKit GUI`.

## 9. Keyboard shortcuts

| Shortcut | Action |
| --- | --- |
| `Ctrl+O` | add input files |
| `Ctrl+R` | run |
| `Ctrl+Enter` | run (form-level) |
| `Ctrl+L` | focus the command search box |
| `Ctrl+F` | focus the parameter filter |
| `Ctrl+,` | open Settings |
| `Ctrl+Shift+C` | copy the full command line |
| `Ctrl+Q` | quit (confirms over a running process) |

## 10. Quick troubleshooting

| Symptom | Start here |
| --- | --- |
| "seqkit not found" badge | section 3.3 of [getting started](getting-started.md), or set the path in Settings |
| "Version mismatch" badge | detected binary is not 2.14.0; it runs, but flags may not match exactly |
| "Incomplete parameters" dialog | it lists what is missing and the rows turn red; per-command requirements in the [command guide](command-guide.md) |
| Exit code 0 but empty result | the status bar says so explicitly; check the Errors tab for stderr output |
| Output truncated | see section 7; **Open output file** has everything |
| Chinese keywords find no parameters | the filter matches English usage text — search `--name` or `-x` instead |
| Anything else | [FAQ](faq.md) |

## Related documents

- [Getting started](getting-started.md)
- [Interface guide](interface-guide.md)
- [Command guide](command-guide.md)
- [FAQ](faq.md)
- [Development](development.md)

Chinese documents live in `docs/zh/`.
