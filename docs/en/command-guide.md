# Command guide

> This document describes **SeqKit GUI**, an unofficial desktop graphical front end for [SeqKit](https://github.com/shenwei356/seqkit), the sequence toolkit by Wei Shen (MIT). It is not affiliated with, endorsed by, or maintained by the SeqKit project, and it is not the official SeqKit graphical interface.

All 41 seqkit 2.14.0 commands exposed by the interface, with the parameters each one requires and worked examples phrased as actions in the form. The data is the content of `seqkit_gui/data/commands.json`, which is generated from the SeqKit 2.14.0 source.

## 0. How to read an entry

**Required parameters** are enforced before the process starts. The GUI blocks the run and shows a dialog naming what is missing:

| Rule type | Meaning in the form | Message you see |
| --- | --- | --- |
| `requires_any` | at least one row of the listed set must be enabled | `one of --pattern / --pattern-file is required` |
| `requires_all` | every listed row must be enabled | `--range is required` |
| `conditional` | enabling the first row obliges the second | `--by-seq is required because --only-positive-strand is enabled` |
| `forbid_pairs` | the two rows cannot both be enabled | `--lower-case and --upper-case cannot be used together` |
| input contract | file count / positional argument rules | `at least 2 input file(s) required`, `this command does not accept input files as arguments` |
| bounded run (`BOUNDED_RUN_FLAGS`) | a command that would never return must be given an exit condition | `one of --find-only / --time-limit is required` |

The four table-recorded families are listed under **Notes** in the form as soon as you select the command, and the rows involved carry an amber **required** badge. The bounded-run rule is not in the parameter table and therefore not in Notes (`_build_notes()` in `ui/param_form.py` renders `requires_any` / `requires_all` / `conditional` / `forbid_pairs` only); it surfaces from `validate()` when you press **Run**.

**Global parameters.** Every command inherits the 11 root persistent flags of seqkit. They appear in the collapsed *Global parameters* section unless the command declares its own flag of the same name.

| Flag | Short | Type | Default | Purpose |
| --- | --- | --- | --- | --- |
| `--seq-type` | `-t` | enum | `auto` | sequence type: `dna`, `rna`, `protein`, `unlimit`, `auto` |
| `--threads` | `-j` | int | `4` | number of CPUs. `4` is the literal default seqkit 2.14.0 prints in its own `--help` and was recorded verbatim into the table; the interface never recomputes it from the local CPU count. Unticked, nothing is sent at all -- upstream's usage text also mentions the `SEQKIT_THREADS` environment variable |
| `--line-width` | `-w` | int | `60` | FASTA line width, `0` for no wrap |
| `--id-regexp` | — | text | `^(\S+)\s?` | regular expression used to parse the ID |
| `--id-ncbi` | — | bool | `false` | FASTA headers are NCBI-style |
| `--out-file` | `-o` | out_file | `-` | output file; `-` is stdout, a `.gz` suffix gzips |
| `--quiet` | — | bool | `false` | suppress extra information |
| `--alphabet-guess-seq-length` | — | int | `10000` | prefix length of the first record used to guess the sequence type |
| `--infile-list` | `-X` | in_file | empty | file listing one input path per line; the interface passes it as `--infile-list <file>`, i.e. as an option before the positional files |
| `--skip-file-check` | — | bool | `false` | skip existence checks for a file list |
| `--compress-level` | — | int | `-1` | compression level for gzip/zstd/xz/bzip2 |

`stats` shadows `--skip-file-check` with its own `-S` flag, so that row lives under *Command parameters* there and the inherited section holds ten rows.

Anything not covered by a row can be typed into **Extra arguments**; it is split with shell-like rules and appended after every flag option but *before* the positional input files, which themselves always follow a standalone `--` terminator.

> From the per-command sections on, the **Flags:** lines are an edited list of commonly used options, not the complete set -- the complete set is what the form's *Command parameters* / *Global parameters* sections render (353 command flags generated from the seqkit 2.14.0 source; by upstream convention the table and the interface both leave out the `-h/--help` that Cobra injects).

### 0.1 Parameter model

Six rules decide what actually reaches seqkit:

| Rule | Meaning |
| --- | --- |
| 1. Ticked = passed | the row's checkbox decides whether the flag appears at all. Unticked → nothing is sent and seqkit applies its own default; the pre-filled editor value is a hint only |
| 2. Boolean rows are the switch | rows with no editor (`--by-seq`, `--all`, …) send `--flag` when ticked and nothing when not |
| 3. Multi-line = repeated | `stringSlice` rows (`grep -p`, `mutate -p`, `translate -f`, `stats -N`, `subseq --feature`, …) take one value per line and expand to `--pattern a --pattern b` |
| 4. Combos only suggest | choices come from the `a\|b\|c` list seqkit itself prints in its usage text; the combo stays editable |
| 5. Leading `-` gets an `=` | a value starting with `-` is emitted as `--flag=value` (`--compress-level=-1`, `--frame=-1`, `--point=-1:A`) so seqkit cannot read it as another option |
| 6. Fixed order | command token → command-local flags → inherited global flags → extra arguments → `--` → positional input files |

### 0.2 General workflow

1. Pick the command in the tree, or filter it in the **Search commands** box (it matches names, aliases such as `stat`/`dup`/`concate`/`rotate`, and summaries in either language).
2. Add input files in the **Input files** section, by drag & drop or with **Paste paths**. An empty list gives seqkit a standard input that is already at end-of-file, so add at least one file for any real run.
3. Expand **Command parameters** and tick only the rows this run needs.
4. Need to steer the output? Expand **Global parameters** and tick `--out-file` (`-o`) and friends.
5. Need an option the form does not model? Type it into **Extra arguments**.
6. Press **Run** (`Ctrl+R` / `Ctrl+Enter`) and read **Result / Errors / Log / Command**.

---

## 1. Commands for Basic Operation

`faidx`, `scat`, `seq`, `sliding`, `stats`, `subseq`, `translate`, `watch`

### `faidx`

Create the FASTA index file and extract subsequences.

- **Required:** none.
- **Inputs:** at least 1 file; **STDIN is not supported** and **compressed input is not supported**.
- **Flags:** `-f/--full-head`, `-i/--ignore-case`, `-I/--immediate-output`, `-l/--region-file`, `-U/--update-faidx`, `-r/--use-regexp`.

**Index a genome**

1. Select `faidx`; add `genome.fa`.
2. Run. Nothing is printed to the Result tab; seqkit writes `genome.fa.fai` beside the input and logs `create FASTA index ...` to the Errors/Log tab.

**Extract a list of regions**

1. Tick `-l/--region-file` and browse to `regions.txt` (one ID or region per line). The extracted sequences now go to stdout.
2. Tick `-U/--update-faidx` when the FASTA may have changed since it was indexed.
3. Tick `-f/--full-head` to write full header lines instead of bare IDs.

### `scat`

Real-time recursive concatenation and streaming of FASTA/FASTQ files.

- **Required:** none.
- **Inputs:** at least 1 **path** — folders are searched recursively, so drop a directory in the list.
- **Flags:** `-i/--format` (`fastq` by default), `-I/--in-format`, `-O/--out-format`, `-b/--qual-ascii-base`, `-d/--delta`, `-D/--drop-time`, `-A/--allow-gaps`, `-f/--find-only`, `-g/--gz-only`, `-r/--regexp`, `-T/--time-limit`, `-p/--wait-pid`.

**Stream a sequencing run folder as FASTQ**

1. Select `scat`; add the run directory to Input files.
2. Leave `-i/--format` at `fastq`, or type `fasta` into it.
3. Tick `-r/--regexp` and enter a pattern (e.g. `_R1_`) to restrict which files are picked up.
4. Run, then **Stop** when the stream should end; tick `-f/--find-only` if you only want the list of files it would read.

### `seq`

Transform sequences: extract IDs, filter by length, remove gaps, reverse complement, and more.

- **Required:** none.
- **Forbidden together:** `-l/--lower-case` ✕ `-u/--upper-case`, `--dna2rna` ✕ `--rna2dna`.
- **Flags:** 27 local rows; length filters `-m/--min-len`, `-M/--max-len`; output shape `-i/--only-id`, `-n/--name`, `-s/--seq`, `-q/--qual`, `-k/--color`; transforms `-p/--complement`, `-r/--reverse`, `-g/--remove-gaps` (with `-G/--gap-letters`), `-v/--validate-seq`, `-b/--qual-ascii-base`; the `f-`-prefixed target-filter group (`--f-pattern`, `--f-pattern-file`, `--f-by-name`, `--f-by-seq`, `--f-use-regexp`, `--f-ignore-case`, `--f-invert-match`, `--f-only-positive-strand`).

**Keep records of at least 1000 bp and print only their IDs**

1. Select `seq`; add `contigs.fa`.
2. Tick `-m/--min-len` and set it to `1000`.
3. Tick `-i/--only-id`.
4. Run.

**Reverse-complement a FASTA in lower case**

1. Tick `-p/--complement` and `-r/--reverse`.
2. Tick `-l/--lower-case` and `--dna2rna` only if the input is DNA you want as RNA.
3. Tick `-w/--line-width` under *Global parameters* and set `0` to emit a single line per record.

### `sliding`

Extract subsequences in sliding windows.

- **Required:** `-s/--step` **and** `-W/--window` (both rows must be enabled).
- **Flags:** `-c/--circular`, `-C/--circular-genome`, `-g/--greedy`, `-S/--suffix`.

**Slide a 150 bp window with a 50 bp step**

1. Select `sliding`; add `genome.fa`.
2. Tick `-W/--window`, enter `150`; tick `-s/--step`, enter `50`.
3. Tick `-g/--greedy` to also emit the trailing window that falls short of 150 bp.
4. Run — record IDs gain the `_sliding:START-END` suffix, which `merge-slides` understands.

### `stats` (alias `stat`)

Simple statistics of FASTA/Q files.

- **Required:** none.
- **Flags:** `-a/--all`, `-T/--tabular`, `-b/--basename`, `-E/--fq-encoding`, `-e/--skip-err`, `-G/--gap-letters`, `-i/--stdin-label`, `-N/--N`, `-S/--skip-file-check`.

**Per-file summary table**

1. Select `stats`; add one or more FASTA/FASTQ files.
2. Tick `-a/--all` to add the length quartiles, `sum_gap` and N50.
3. Run. The Result tab holds the TSV; **Save result** writes it out.

**Machine-friendly output with custom N-ranges**

1. Tick `-T/--tabular`.
2. Tick `-N/--N` and put `50` and `90` on separate lines to append N50 and N90 columns.
3. Tick `-j/--threads` under *Global parameters* and raise it above the default `4` for many large files.

### `subseq`

Get subsequences by region/GTF/BED, including flanking sequences.

- **Required:** one of `-r/--region`, `--bed`, `--gtf`.
- **Forbidden together:** `--bed` ✕ `--feature`, `-f/--only-flank` ✕ `-u/--up-stream`.
- **Conditional:** none.
- **Flags:** `-d/--down-stream`, `-f/--only-flank`, `-R/--region-coord`, `-U/--update-faidx`, `--chr`, `--feature`, `--gtf-tag`.

**Pull a gene with 200 bp of upstream context**

1. Select `subseq`; add `genome.fa.gz` (compression keeps output order stable).
2. Tick `-r/--region` and enter `chr1:1000-2000`.
3. Tick `-u/--up-stream` and set `200`.
4. Tick `-U/--update-faidx` if the FASTA may have changed since it was indexed.

**Extract all CDS features from a GTF**

1. Tick `--gtf` and browse to `annotation.gtf`.
2. Tick `--feature`; type `CDS` on one line and `exon` on the next to restrict feature types (GTF only).
3. Tick `-f/--only-flank` to return only the flanking sequence, dropping the feature itself.

### `translate`

Translate DNA/RNA to protein, supporting ambiguous bases.

- **Required:** none.
- **Flags:** `-T/--transl-table`, `-l/--list-transl-table`, `-f/--frame`, `-m/--min-len`, `-s/--out-subseqs`, `-x/--allow-unknown-codon`, `-F/--append-frame`, `-M/--init-codon-as-M`, `-e/--skip-translate-errors`, `--clean`, `--trim`.

**Six-frame translation**

1. Select `translate`; add `cds.fa`.
2. Tick `-f/--frame` and replace the prefilled `1` with `6` — the value `6` means all six frames.
3. Tick `-F/--append-frame` so each output ID records its frame.

**Inspect a genetic code table, then translate with it**

1. Tick `-l/--list-transl-table` and set `0` to print every table; run once to read the numbering.
2. Re-select the command, clear the `-l/--list-transl-table` row, tick `-T/--transl-table` and set the table number you want.
3. Tick `--clean` to turn stop-codon `*` characters into `X`, and `--trim` to strip trailing `*`/`X`.

### `watch`

Monitoring and online histograms of sequence features.

- **Required:** none.
- **Inputs:** at least 1 file. The process monitors a file being written and **runs until you press Stop**.
- **Flags:** `-f/--fields` (`ReadLen` by default), `-H/--list-fields`, `-B/--bins`, `-W/--delay`, `-p/--print-freq`, `-O/--img`, `-y/--dump`, `-L/--log`, `-x/--pass`, `-Q/--quiet-mode`, `-R/--reset`, `-b/--qual-ascii-base`, `-v/--validate-seq`.

**Histogram of read lengths for a growing FASTQ**

1. Select `watch`; add the file being written.
2. Tick `-f/--fields` if you want something other than `ReadLen`; tick `-H/--list-fields` first to print the available fields.
3. Tick `-p/--print-freq` and set a record count (for example `1000`) so a report is produced periodically instead of only at end of file.
4. Run, watch the Log tab, then click **Stop**.

---

## 2. Commands for Format Conversion

`convert`, `fa2fq`, `fq2fa`, `fx2tab`, `tab2fx`

### `convert`

Convert FASTQ quality encoding between Sanger, Solexa and Illumina variants.

- **Required:** none; the source encoding is guessed unless you set `--from`.
- **Flags:** `--from`, `--to` (default `Sanger`), `-d/--dry-run`, `-f/--force`, `-n/--nrecords`, `-N/--thresh-B-in-n-most-common`, `-F/--thresh-illumina1.5-frac`.

**Normalise an old run to Sanger (Phred+33)**

1. Select `convert`; add `old_reads.fq`.
2. Tick `--from` and enter the source encoding when automatic detection fails (for example `illumina-1.5`).
3. Leave `--to` at `Sanger`, tick `-d/--dry-run` first and run to see what would happen without writing records.

### `fa2fq`

Retrieve the corresponding FASTQ records for a FASTA file.

- **Required:** `-f/--fasta-file`.
- **Inputs:** the Input files list holds the **FASTQ** file(s); the FASTA comes from the flag.

**Recover qualities for a filtered FASTA**

1. Select `fa2fq`; add `all_reads.fq` to Input files.
2. Tick `-f/--fasta-file` and browse to `kept_reads.fa`.
3. Tick `-P/--only-positive-strand` to skip searching the reverse complement.
4. Run.

### `fq2fa`

Convert FASTQ to FASTA.

- **Required:** none. **Local flags:** none — this command has only the inherited global flags.

**Convert and write straight to a file**

1. Select `fq2fa`; add `reads.fq`.
2. Tick `-o/--out-file` under *Global parameters*, browse to `reads.fa`.
3. Run. The Result tab stays empty because seqkit wrote to the file.

### `fx2tab`

Convert FASTA/Q to tabular format, adding length, GC content, average quality and more.

- **Required:** none.
- **Flags:** `-l/--length`, `-g/--gc`, `-G/--gc-skew`, `-q/--avg-qual`, `-a/--alphabet`, `-s/--seq-hash`, `-C/--base-count`, `-B/--base-content`, `-n/--name`, `-i/--only-id`, `-H/--header-line`, `-Q/--no-qual`, `-b/--qual-ascii-base`, `-f/--file-name`, `--basename`, `-I/--case-sensitive`, `--stdin-label`.

**ID, length and GC per record**

1. Select `fx2tab`; add `contigs.fa`.
2. Tick `-i/--only-id`, `-l/--length`, `-g/--gc`.
3. Tick `-H/--header-line` to prefix the TSV with column names.

**Per-base counts for selected letters**

1. Tick `-C/--base-count` and enter `A`, `C`, `G`, `T` on four separate lines — one value per line becomes `-C A -C C -C G -C T`.
2. Use `-B/--base-content` the same way for percentages, and `-I/--case-sensitive` if soft-masked case matters.

### `tab2fx`

Convert tabular format (first two/three columns) back to FASTA/Q.

- **Required:** none.
- **Flags:** `-b/--buffer-size` (default `1G`), `-p/--comment-line-prefix` (repeatable, defaults to `#` and `//`).

**Rebuild a FASTA from an ID/sequence table**

1. Select `tab2fx`; add `table.tsv`.
2. Run; the FASTA appears in the Result tab.
3. If the input contains header or comment lines that should be skipped, tick `-p/--comment-line-prefix` and list one prefix per line.

---

## 3. Commands for Searching

`amplicon`, `fish`, `grep`, `locate`

### `amplicon`

Extract amplicons (or a specific region around them) by primer sequence.

- **Required:** at least one of `--bed`, `-p/--primer-file`, `-F/--forward`, `-R/--reverse`.
- **Flags:** `-m/--max-mismatch`, `-f/--flanking-region`, `-r/--region`, `-s/--strict-mode`, `-M/--output-mismatches`, `-u/--save-unmatched`, `-I/--immediate-output`, `-P/--only-positive-strand`.

**Amplify with one primer pair typed into the form**

1. Select `amplicon`; add `reads.fq`.
2. Tick `-F/--forward` and enter the forward primer, e.g. `ATGCTTAAAGGGAAG`.
3. Tick `-R/--reverse` and enter the reverse primer.
4. Tick `-m/--max-mismatch` and set `2` to allow two mismatches per primer.
5. Run.

**Batch primer pairs, keep what did not match**

1. Tick `-p/--primer-file` and browse to a 3- or 2-column tab-separated primer table.
2. Tick `-u/--save-unmatched` to also output records matching no primer.
3. Tick `-M/--output-mismatches` to append mismatch counts to the sequence IDs.

### `fish`

Look for short sequences inside larger sequences using local alignment.

- **Required:** one of `-f/--query-fastx`, `-F/--query-sequences`.
- **Flags:** `-q/--min-qual` (default `5`), `-p/--aln-params` (default `4,-4,-2,-1`), `-a/--all`, `-i/--invert`, `-g/--print-aln`, `-D/--print-desc`, `-b/--out-bam`, `-r/--ranges`, `-s/--stranded`, `-x/--pass`, `-v/--validate-seq`.

**Find a short bait inside contigs**

1. Select `fish`; add `contigs.fa`.
2. Tick `-F/--query-sequences` and enter the bait sequence (one query per line if you have several).
3. Tick `-q/--min-qual` and raise it above `5` to cut weak hits.
4. Tick `-g/--print-aln` to see the alignment beneath each hit.

**Query from a file, restricted to a range**

1. Tick `-f/--query-fastx` and browse to `baits.fa`.
2. Tick `-r/--ranges` and enter a target range such as `:10,30:40,-20:`.
3. Tick `-b/--out-bam` and set a BAM path to keep every alignment (memory-intensive).

### `grep`

Search sequences by ID/name/sequence/sequence motif, mismatch allowed.

- **Required:** one of `-p/--pattern`, `-f/--pattern-file`.
- **Flags:** `-s/--by-seq`, `-n/--by-name`, `-r/--use-regexp`, `-i/--ignore-case`, `-v/--invert-match`, `-m/--max-mismatch`, `-d/--degenerate`, `-C/--count`, `-R/--region`, `-c/--circular`, `-I/--immediate-output`, `-P/--only-positive-strand`, `-D/--allow-duplicated-patterns`, `--delete-matched`.

**Extract records whose ID is in a list**

1. Select `grep`; add `all_sequences.fa`.
2. Tick `-f/--pattern-file` and browse to `ids.txt` (one ID per line).
3. Run. Without `-s/--by-seq`, patterns are matched against sequence IDs, not the bases.

**Motif search on both strands**

1. Tick `-p/--pattern`; enter `ATGCAA` on the first line and `TTGACA` on the second. One value per line becomes `--pattern ATGCAA --pattern TTGACA`.
2. Tick `-s/--by-seq` to search inside the sequences.
3. Tick `-m/--max-mismatch` and set `1` to tolerate one mismatch.
4. Add `-P/--only-positive-strand` if the reverse complement should be skipped; tick `-v/--invert-match` to output the records that did **not** match.

### `locate`

Locate subsequences/motifs, mismatch allowed, and report their positions.

- **Required:** one of `-p/--pattern`, `-f/--pattern-file`.
- **Forbidden together:** `-d/--degenerate` ✕ `-m/--max-mismatch`, `-r/--use-regexp` ✕ `-m/--max-mismatch`.
- **Flags:** `-s/--max-len-to-show`, `-G/--non-greedy`, `-M/--hide-matched`, `--bed`, `--gtf`, `-F/--use-fmi`, `-c/--circular`, `-i/--ignore-case`, `-I/--immediate-output`, `-P/--only-positive-strand`.

**Where is this motif?**

1. Select `locate`; add `genome.fa`.
2. Tick `-p/--pattern` and enter the motif.
3. Tick `-m/--max-mismatch` and set `2`. Do not enable `-d/--degenerate` or `-r/--use-regexp` at the same time — the form refuses the combination.

**Emit matches as BED**

1. Tick `--bed` to write BED6 positions instead of text lines.
2. Tick `-M/--hide-matched` to keep the output short.
3. For thousands of motifs, tick `-F/--use-fmi` to build and use an FM-index.

---

## 4. Commands for Set Operation

`common`, `duplicate`, `head`, `head-genome`, `pair`, `range`, `rmdup`, `sample`, `sample2`, `split`, `split2`

### `common`

Find common/shared sequences across multiple files, by ID, name or sequence.

- **Required:** none. **Inputs: at least 2 files.**
- **Conditional:** `-P/--only-positive-strand` → `-s/--by-seq`; `-e/--check-embedded-seqs` → `-s/--by-seq`.
- **Flags:** `-n/--by-name`, `-s/--by-seq`, `-i/--ignore-case`, `-e/--check-embedded-seqs`, `-P/--only-positive-strand`.

**Sequences present in all three files**

1. Select `common`; add three FASTA/FASTQ files to Input files.
2. Leave `-s/--by-seq` off to compare by ID; tick it to compare the bases themselves.
3. Run.

**Compare by sequence, ignoring case**

1. Tick `-s/--by-seq`, then `-i/--ignore-case`.
2. Tick `-P/--only-positive-strand` — enabling it requires `-s/--by-seq`, which the validator enforces.

### `duplicate` (alias `dup`)

Duplicate each sequence N times.

- **Required:** none. **Flag:** `-n/--times` (default `1`).

**Write every record three times**

1. Select `duplicate`; add `spike_in.fa`.
2. Tick `-n/--times` and set `3`.
3. Run.

### `head`

Print the first N records, or the leading records whose cumulative length reaches L.

- **Required:** none. **Flags:** `-n/--number` (default `10`), `-l/--length` (supports K/M/G suffixes and overrides `-n`).

**First 50 records**

1. Select `head`; add `reads.fq`.
2. Tick `-n/--number` and set `50`.
3. Run.

**Leading records up to 1 Mbp**

1. Tick `-l/--length` and enter `1M`. Leave `-n/--number` unchecked — `-l` overrides it.

### `head-genome`

Print the sequences of the first genome whose name shares a common prefix.

- **Required:** none. **Flag:** `-m/--mini-common-words` (default `1`).

**First strain out of a mixed assembly file**

1. Select `head-genome`; add a multi-contig FASTA whose descriptions share a per-strain prefix (e.g. `... Vibrio cholerae strain M29 Contig_1 ...`).
2. Run: the records of the first strain are printed, no ID list needed.
3. Tick `-m/--mini-common-words` and raise it above the default `1` when short prefixes collide between strains, so more words must match before two records count as the same genome.

### `pair`

Match up paired-end reads from two FASTQ files.

- **Required:** `-1/--read1` **and** `-2/--read2`.
- **Inputs:** **positional arguments are rejected** — the Input files list is hidden, and adding a file anyway produces `this command does not accept input files as arguments`.
- **Flags:** `-O/--out-dir`, `-f/--force`, `-u/--save-unpaired`.

**Pair two FASTQ files**

1. Select `pair`.
2. Tick `-1/--read1` and browse to `sample_R1.fq.gz`.
3. Tick `-2/--read2` and browse to `sample_R2.fq.gz`.
4. Tick `-O/--out-dir` and choose the destination folder; add `-f/--force` if that folder already holds output.
5. Tick `-u/--save-unpaired` to also write reads that have no mate. Run.

### `range`

Print records in a range (start:end).

- **Required:** `-r/--range`. **Flag count:** one local row only.

**Records 5 to 20**

1. Select `range`; add `contigs.fa`.
2. Tick `-r/--range` and enter `5:20`.
3. Run. Ranges are 1-based; `-12:-1` means the last twelve records.

### `rmdup`

Remove duplicated sequences by ID, name or sequence.

- **Required:** none.
- **Conditional:** `-P/--only-positive-strand` → `-s/--by-seq`.
- **Flags:** `-n/--by-name`, `-s/--by-seq`, `-i/--ignore-case`, `-D/--dup-num-file`, `-d/--dup-seqs-file`, `-P/--only-positive-strand`.

**Drop repeated IDs and report what was dropped**

1. Select `rmdup`; add `reads.fa`.
2. Tick `-d/--dup-seqs-file` and set a path to receive the duplicate sequences.
3. Tick `-D/--dup-num-file` to write the counts and ID lists of duplicated entries.
4. Run; stdout carries the de-duplicated records.

### `sample`

Sample sequences by number or proportion.

- **Required:** one of `-n/--number`, `-p/--proportion`. **Inputs: at most 1 file.**
- **Flags:** `-s/--rand-seed` (default `11`), `-r/--non-deterministic`, `-2/--two-pass`.

**Take 1000 records reproducibly**

1. Select `sample`; add one FASTA/FASTQ file.
2. Tick `-n/--number` and set `1000`.
3. Tick `-s/--rand-seed` and set a seed so a second run picks the same records.

**Take 5 % of a large file with low memory**

1. Tick `-p/--proportion` and set `0.05`.
2. Tick `-2/--two-pass` — for `-n` it counts the records first instead of loading them all, and it requires an input file rather than STDIN.

### `sample2`

Sample sequences by number or proportion (version 2).

- **Required:** one of `-n/--number`, `-p/--proportion`. **Inputs: at most 1 file.**
- **Flags:** `-s/--rand-seed`, `-r/--non-deterministic`, `-2/--two-pass`.

**Take exactly N records**

1. Select `sample2`; add one file.
2. Tick `-n/--number` and set `500`. `sample2` returns `min(N, total)` records, where `sample` may return fewer than requested.
3. Run.

**Sampled paired runs**

1. Use `-p/--proportion` with a fixed `-s/--rand-seed`; apply the same seed to each mate file so the same pairs are kept.

### `split`

Split sequences into files by ID, sequence region, size or number of parts (mainly FASTA).

- **Required:** one of `-s/--by-size`, `-p/--by-part`, `-i/--by-id`, `-r/--by-region`. **Inputs: at most 1 file.**
- **Conditional:** `-k/--keep-temp` → `-2/--two-pass`; `-U/--update-faidx` → `-2/--two-pass`.
- **Flags:** `-O/--out-dir`, `-P/--out-prefix`, `-W/--part-width` (default `3`), `--by-id-prefix`, `--by-part-prefix`, `--by-region-prefix`, `--by-size-prefix`, `-e/--extension`, `-f/--force`, `-d/--dry-run`, `-I/--ignore-case`.

**Split into 5 equal parts**

1. Select `split`; add `genomes.fa`.
2. Tick `-p/--by-part` and set `5`.
3. Tick `-O/--out-dir` and choose a destination; leaving it unset writes to `<input>.split`.
4. Tick `-d/--dry-run` first to preview the plan.

**One file per sequence ID**

1. Tick `-i/--by-id`.
2. Tick `-W/--part-width` only when splitting by size or parts and you need a different number of digits in the file names.

### `split2`

Split sequences into files by size, parts or cumulative length; handles paired-end FASTQ.

- **Required:** one of `-s/--by-size`, `-p/--by-part`, `-l/--by-length`. **Inputs: at most 1 file.**
- **Flags:** `-1/--read1`, `-2/--read2`, `-N/--seqid-as-filename`, `-O/--out-dir`, `-P/--out-prefix`, `-W/--part-width`, `-e/--extension`, `-f/--force`.

**Round-robin a paired run into 4 lanes**

1. Select `split2`; leave Input files empty.
2. Tick `-p/--by-part` and set `4`.
3. Tick `-1/--read1` and `-2/--read2` with the two mate files.
4. Tick `-P/--out-prefix` and include the `{read}` placeholder in the prefix, which is what separates the R1 and R2 output names.

**Split by cumulative length**

1. Tick `-l/--by-length` and enter `10M` to close a chunk once it reaches 10 megabases.
2. Tick `-N/--seqid-as-filename` to name each chunk after the first ID inside it.

---

## 5. Commands for Edit

`concat`, `mutate`, `rename`, `replace`, `restart`, `sana`

### `concat` (alias `concate`)

Concatenate sequences sharing the same ID across multiple files.

- **Required:** none. **Inputs: at least 2 files.**
- **Flags:** `-f/--full`, `-F/--fill`, `-s/--separator` (default `|`).

**Join the same genes from several annotation files**

1. Select `concat`; add at least two FASTA files with overlapping IDs.
2. Leave `-s/--separator` at `|`, or type the string that should join the descriptions.
3. Run; sequences with the same ID are concatenated in file order.

**Keep IDs missing from some files**

1. Tick `-f/--full` for a full/outer join.
2. Tick `-F/--fill` and enter the filler residue (for example `N`) used when an ID is absent from a file.

### `mutate`

Edit sequences: point mutations, insertions, deletions.

- **Required:** one of `-p/--point`, `-i/--insertion`, `-d/--deletion`, `-s/--pattern`, `-f/--pattern-file`.
- **Forbidden together:** `-i/--insertion` ✕ `-d/--deletion`.
- **Flags:** `-n/--by-name`, `-r/--use-regexp`, `-v/--invert-match`, `-I/--ignore-case`.

**Change the second base to C**

1. Select `mutate`; add `plasmid.fa`.
2. Tick `-p/--point` and enter `2:C` — one edit per line, e.g. `-1:A` for the last base.
3. Run.

**Only mutate records carrying a marker motif**

1. Tick `-s/--pattern` and enter the motif that selects the records to edit.
2. Tick `-d/--deletion` and enter a range such as `1:2` to drop the leading two bases; `-i/--insertion` cannot be enabled at the same time.
3. Tick `-v/--invert-match` to edit the records that do **not** match instead.

### `rename`

Rename duplicated IDs.

- **Required:** none. **Flags:** `-O/--out-dir` (default `renamed`), `-s/--separator` (default `_`), `-N/--start-num` (default `2`), `-n/--by-name`, `-m/--multiple-outfiles`, `-1/--rename-1st-rec`, `-f/--force`.

**Make every ID unique**

1. Select `rename`; add `contigs.fa`.
2. Run — the renamed records are printed to the Result tab, or written by `-o/--out-file`.

**One output file per input file**

1. Add several inputs and tick `-m/--multiple-outfiles`; results are then written as separate files inside the folder given by `-O/--out-dir`, whose default is `renamed` relative to the working directory.
2. Tick `-n/--by-name` to detect duplication across full names instead of IDs, and `-1/--rename-1st-rec` to suffix the first occurrence as well.
3. Add `-f/--force` if the destination folder already holds files.

### `replace`

Replace name or sequence using a regular expression.

- **Required:** one of `-p/--pattern`, `--f-pattern`.
- **Conditional:** `-K/--keep-key` → `-p/--pattern`.
- **Flags:** `-r/--replacement`, `-s/--by-seq`, `-i/--ignore-case`, `-k/--kv-file`, `--nr-width`, `-I/--key-capt-idx`, `-U/--keep-untouch`, `-m/--key-miss-repl`, and the `f-`-prefixed filter group (`--f-pattern`, `--f-pattern-file`, `--f-by-name`, `--f-by-seq`, `--f-use-regexp`, `--f-ignore-case`, `--f-invert-match`, `--f-only-positive-strand`).

**Rewrite IDs with a capture group**

1. Select `replace`; add `reads.fa`.
2. Tick `-p/--pattern` and enter `sample_(\d+)`.
3. Tick `-r/--replacement` and enter `run_${1}`; `{nr}` and `{fn}` are also available as record-number and file-name symbols.
4. Tick `-i/--ignore-case` if needed.

**Replace using a lookup table**

1. Tick `-k/--kv-file` and browse to a tab-separated key/value file, then reference `{kv}` in `-r/--replacement`.
2. Tick `-K/--keep-key` to keep the original key when the table has no entry — enabling it requires `-p/--pattern`, which the validator enforces.
3. Tick `-s/--by-seq` to apply the replacement to the sequence rather than the name.

### `restart` (alias `rotate`)

Reset the start position (rotate) of a circular genome.

- **Required:** one of `-i/--new-start`, `-s/--start-with`.
- **Flags:** `-m/--max-mismatch`, `-I/--ignore-case`.

**Rotate to a fixed position**

1. Select `restart`; add `genome.fa`.
2. Tick `-i/--new-start` and set the 1-based position that should become the first base; negative values count from the end.

**Rotate to a known motif**

1. Tick `-s/--start-with` and enter the subsequence the genome should begin with.
2. Tick `-m/--max-mismatch` and allow one or two mismatches when the motif is not exact.

### `sana`

Sanitize broken single-line FASTQ files.

- **Required:** none. **Flags:** `-i/--format` (default `fastq`), `-I/--in-format`, `-O/--out-format`, `-b/--qual-ascii-base` (default `33`), `-A/--allow-gaps`.

**Repair a one-line-per-record FASTQ**

1. Select `sana`; add the broken `.fq` file.
2. Leave `-i/--format` at `fastq`, or set `-I/--in-format` / `-O/--out-format` separately when converting while repairing.
3. Tick `-A/--allow-gaps` if the records contain gap characters.
4. Run.

---

## 6. Commands for Ordering

`shuffle`, `sort`

### `shuffle`

Shuffle the order of sequences.

- **Required:** none.
- **Conditional:** `-k/--keep-temp` → `-2/--two-pass`; `-U/--update-faidx` → `-2/--two-pass`.
- **Flags:** `-s/--rand-seed` (default `23`), `-r/--non-deterministic`, `-2/--two-pass`, `--tmp-dir` (default `./`).

**Deterministic shuffle**

1. Select `shuffle`; add `reads.fa`.
2. Tick `-s/--rand-seed` and set a seed; the same seed always gives the same order.
3. Tick `-r/--non-deterministic` instead if you want a time-based seed.

**Low-memory shuffle of a large FASTA**

1. Tick `-2/--two-pass` (FASTA only) — this also restricts the command to one input file.
2. Tick `--tmp-dir` and point it at a fast volume.
3. Add `-k/--keep-temp` only to inspect the temporary FASTA after the run.

### `sort`

Sort sequences by ID, name, sequence or length.

- **Required:** none.
- **Conditional:** `-k/--keep-temp` → `-2/--two-pass`; `-U/--update-faidx` → `-2/--two-pass`.
- **Flags:** `-n/--by-name`, `-l/--by-length`, `-s/--by-seq`, `-b/--by-bases`, `-N/--natural-order`, `-r/--reverse`, `-i/--ignore-case`, `-L/--seq-prefix-length` (default `10000`), `-G/--gap-letters`, `-2/--two-pass`, `-k/--keep-temp`, `-U/--update-faidx`.

**Longest sequence first**

1. Select `sort`; add `contigs.fa`.
2. Tick `-l/--by-length` and `-r/--reverse`.
3. Run.

**Natural order on chromosome names**

1. Tick `-N/--natural-order` so `chr2` sorts before `chr10`.
2. Tick `-n/--by-name` to compare full names instead of bare IDs; `-s/--by-seq` sorts by the bases and `-b/--by-bases` by base composition.
3. Tick `-2/--two-pass` for large FASTA files where memory matters (one input file only).

---

## 7. Commands for BAM Processing

### `bam`

Monitor and plot histograms of BAM record features, plus index-based statistics.

- **Required:** at least one mode flag: `-s/--stat`, `-i/--idx-stat`, `-C/--idx-count`, `-c/--count`, `-g/--grep-ids`, `-y/--dump`, `-T/--tool`, `-H/--list-fields`, `-@/--top-bam`.
- **Inputs:** `-s/--stat` and `-i/--idx-stat` accept several files; the other modes require exactly one BAM/SAM file.
- **Flags:** 29 local rows, including `-f/--field`, `-B/--bins`, `-W/--delay`, `-p/--print-freq`, `-O/--img`, `-L/--log`, `-x/--pass`, `-k/--pretty`, `-F/--prim-only`, `-Q/--quiet-mode`, `-Z/--silent-mode`, `-R/--reset`, `-q/--map-qual`, `-m/--range-min`, `-M/--range-max`, `-N/--bundle`, `-G/--exclude-ids`, `-?/--top-size`, `-e/--exec-after`, `-E/--exec-before`.

**BAM statistics**

1. Select `bam`; add `sample.bam` (or several files for this mode).
2. Tick `-s/--stat` for full statistics, or `-i/--idx-stat` for the faster index-based numbers.
3. Tick `-C/--idx-count` to count reads per reference.
4. Run.

**Histogram of one numeric field**

1. Tick `-f/--field` and enter the field to plot; tick `-H/--list-fields` first to print the available names.
2. Add `-B/--bins` to fix the bin count and `-L/--log` for a log10 transform.
3. Tick `-O/--img` to save the plot to a PDF/image file, or `-y/--dump` to print histogram data instead of plotting.

---

## 8. Commands for Miscellaneous

`merge-slides`, `sum`

### `merge-slides`

Merge sliding windows produced by `seqkit sliding`.

- **Required:** none.
- **Flags:** `-l/--min-overlap` (default `1`), `-g/--max-gap` (default `0`), `-r/--regexp` (default `^(.+)_sliding:(\d+)\-(\d+)`), `-b/--buffer-size` (default `1G`), `-p/--comment-line-prefix`.

**Collapse windows into covered regions**

1. Select `merge-slides`; add the FASTA written by `sliding`.
2. Tick `-l/--min-overlap` and set it to the sliding step minus one — the value the tool recommends.
3. Tick `-g/--max-gap` to refuse merging regions farther than N bases apart.
4. Do **not** point `-o/--out-file` at one of the input files; seqkit rejects that.

### `sum`

Compute a message digest over all sequences in FASTA/Q files.

- **Required:** none. **Flags:** `-a/--all`, `-b/--basename`, `-i/--include-id`, `-c/--circular`, `-k/--kmer-size` (default `1000`), `-g/--remove-gaps`, `-G/--gap-letters`, `--rna2dna`, `-s/--single-strand`.

**Stable checksum of a dataset**

1. Select `sum`; add one or more files.
2. Tick `-a/--all` to include sequence count and total length in the output.
3. Run; identical sequence sets produce identical digests regardless of record order.

**Checksum of a circular genome, insensitive to rotation**

1. Tick `-c/--circular` and, for a single-stranded genome such as an ssRNA virus, also tick `-s/--single-strand`.
2. Tick `-g/--remove-gaps` when alignments contributed gap characters; `-G/--gap-letters` defines which characters count as gaps.
3. Keep `-k/--kmer-size` constant — the digest changes with the k-mer size.

---

## 9. Ungrouped commands

seqkit declares these two without a group ID, so the command tree puts them under their own final node, titled **Other** (其他).

### `genautocomplete`

Generate a shell autocompletion script.

- **Required:** none. **Inputs:** none — the command rejects positional arguments.
- **Flags:** `--shell` (combo box: `bash`, `zsh`, `fish`, `powershell`) and `--file` (the script path; the row is pre-filled with seqkit's own default, `$HOME/.bash_completion.d/seqkit.sh`, with `$HOME` expanded to your home folder).

**Write a bash completion script**

1. Select `genautocomplete`.
2. Leave `--shell` at `bash`, or pick another value from the combo box — you can also type over it.
3. Tick `--file` and set the destination path, then Run and check the Errors tab for the location seqkit reports.

### `version`

Print version information and optionally check for an update.

- **Required:** none. **Inputs:** none. **Flag:** `-u/--check-update` (reaches out to the network).

**Print the version**

1. Select `version`; run with no rows checked — the Result tab shows the seqkit build banner.
2. Tick `-u/--check-update` to ask upstream whether a newer release exists.

---

## 10. Common tasks index

| What you want | Command | What to tick in the form |
| --- | --- | --- |
| Pull a few records by ID | `grep` | `--pattern` (one ID per line) |
| Pull the IDs listed in a file | `grep` | `--pattern-file` |
| Keep only the non-matching records | `grep` | `--pattern` + `--invert-match` |
| Search a motif / a regex | `grep` or `locate` | `--by-seq` / `--use-regexp` |
| Basic FASTA/Q statistics | `stats` | `--all` |
| Drop short sequences | `seq` | `--min-len` |
| Reverse-complement | `seq` | `--reverse` + `--complement` |
| Remove gap characters | `seq` | `--remove-gaps` (adjust `--gap-letters` if needed) |
| Extract a region plus 50 bp upstream | `subseq` | `--region` + `--up-stream` |
| Cut sliding windows | `sliding` | `--window` + `--step` |
| Re-merge sliding windows | `merge-slides` | `--min-overlap` |
| Random subsampling | `sample` / `sample2` | `--number` or `--proportion` (with `--rand-seed`) |
| Split a large file | `split` / `split2` | `--by-part` / `--by-size` / `--by-id` |
| Split paired-end data by read count | `split2` | `--by-size` + `--read1` + `--read2` + `--out-prefix` containing `{read}` |
| Pair two fastq files | `pair` | `--read1` + `--read2` (no positional files) |
| Remove duplicates | `rmdup` | `--by-seq` or `--by-name` |
| Intersect several files | `common` | at least 2 input files, `--by-seq` if needed |
| Concatenate records with the same ID | `concat` | at least 2 input files, optionally `--full` + `--fill` |
| Sort records | `sort` | `--by-length` / `--by-name` / `--by-seq` + `--reverse` |
| Shuffle records | `shuffle` | `--rand-seed` |
| Translate CDS | `translate` | `--transl-table`, `--frame`, `--append-frame` |
| Convert FASTQ quality encoding | `convert` | `--from`, `--to`, try `--dry-run` first |
| FASTQ to FASTA | `fq2fa` | no parameters |
| Table <-> sequences | `fx2tab` / `tab2fx` | `--length`, `--gc`, `--name` / `--buffer-size` |
| Rename duplicated IDs | `rename` | `--multiple-outfiles`, `--separator` |
| Point mutations | `mutate` | `--point` (one per line) |
| Regex rename / rewrite | `replace` | `--pattern` + `--replacement` (add `--by-seq`) |
| Rotate a circular genome's start | `restart` | `--new-start` or `--start-with` |
| Build a FASTA index / fetch by index | `faidx` | `--region-file` |
| Concatenate everything under a folder | `scat` | the directory as a positional path |
| Watch a file being written | `watch` | `--fields`, `--dump`, then press **Stop** |
| BAM statistics | `bam` | `--stat` / `--idx-stat` / `--idx-count` |
| Check a file fingerprint | `sum` | `--all` |
| Generate a shell completion script | `genautocomplete` | `--shell` |

## 11. Next

- Which control does what: [Interface guide](interface-guide.md)
- Task recipes, step by step: [User guide](user-guide.md)
- Rules, defaults and surprises: [FAQ](faq.md)
- Install and first run: [Getting started](getting-started.md)

Chinese versions of these documents live in [`docs/zh/`](../zh/).
