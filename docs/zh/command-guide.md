# 命令与参数指南

> 本文是**非官方 SeqKit GUI** 的简体中文文档，说明界面的参数模型、运行前校验规则，以及全部 41 个子命令在 GUI 中的填法。SeqKit GUI 是 [SeqKit](https://github.com/shenwei356/seqkit)（Wei Shen 开发的 MIT 许可序列工具包）的桌面图形前端；本项目与 SeqKit 项目无关，未获其认可，也不由其维护，不是 SeqKit 的官方图形界面。

## 1. 先理解参数模型

本界面自身不做任何序列处理：它把表单状态组装成参数数组，用 `QProcess` 启动 `seqkit`，再流式读取它的 `stdout` / `stderr`。命令能不能跑对，取决于你是否理解了下面 6 条规则。

| 规则 | 说明 |
| --- | --- |
| 1. 勾选 = 传参 | 每个参数行左侧的勾选框决定**这个参数是否出现在命令行里**。不勾选 → 完全不传，seqkit 使用它自己的默认值；界面上预填的值只是提示，不会生效 |
| 2. 布尔行 = 开关本身 | 没有编辑器的行（如 `--by-seq`、`--all`），勾选即传 `--flag`，不勾选即不传 |
| 3. 多行框 = 重复传参 | 可重复参数（`stringSlice`，如 `grep -p`、`mutate -p`、`translate -f`）用多行文本框，**每行一个值**，展开成 `--pattern a --pattern b` |
| 4. 下拉框只是建议 | 候选值取自 seqkit 自己 usage 文本括号里的枚举（如 `--seq-type` 的 `dna\|rna\|protein\|unlimit\|auto`），下拉框可编辑，仍可手动输入其他值 |
| 5. 负值自动加等号 | 值以 `-` 开头时写成 `--flag=值`，例如 `--frame=-1`、`--point=-1:A`、`--compress-level=-1`、`--separator=-` |
| 6. 参数顺序固定 | 命令行依次为：子命令 token → 命令专属参数 → 未被同名遮蔽的全局参数 → 附加参数 → 独立的 `--` 终止符 → 位置输入文件。专属参数与全局参数按参数表里的记录顺序输出；附加参数按 shell 规则切分后原样追加，不做求值 |

一条直观对照（`--` 是界面固定插入的选项终止符，保证以 `-` 开头的文件名不会被当成参数解析）：

| 界面操作 | 生成的命令 |
| --- | --- |
| 勾选 `--pattern`，填一行 `seq1`，其余全部不勾选 | `seqkit grep --pattern seq1 -- reads.fa` |
| 再勾选 `--by-seq`、`--ignore-case` | `seqkit grep --by-seq --ignore-case --pattern seq1 -- reads.fa` |
| 把 `--pattern` 框里改成两行 `seq1` / `seq2` | `seqkit grep --by-seq --ignore-case --pattern seq1 --pattern seq2 -- reads.fa` |

> 下文各命令条目里的示例命令行为了简短省去了这个 `--`；界面上**命令行**标签与状态栏预览显示的是含 `--` 的完整形式。

> 想确认界面到底传了什么，运行前看状态栏右下角的实时预览，运行后看输出面板的**命令行**标签（`Ctrl+Shift+C` 可复制）。

## 2. 通用工作流

1. 左侧选命令（或用“搜索命令”框过滤，支持中文名与别名 `stat`/`dup`/`concate`/`rotate`）。
2. 在**输入文件**区添加文件（或拖放、粘贴路径）。留空时 seqkit 读到的是一个立即结束的标准输入（界面不会代你输入内容），因此实际运行请至少添加一个文件；`faidx` 更是明确不支持标准输入。
3. 展开**命令参数**，只勾选这次需要的行并填值。
4. 需要控制输出时展开**全局参数**，勾选 `--out-file`（`-o`）等。
5. 需要 seqkit 未在本界面建模的选项时，用**附加参数**框直接写，例如 `--by-seq`。
6. 点**运行**（`Ctrl+R` / `Ctrl+Enter`），在**结果 / 错误 / 日志 / 命令行**四个标签间查看。

## 3. 全局参数（11 个）

每个命令都有这 11 行（`stats` 显示 10 行，因为它的 `-S/--skip-file-check` 属于命令专属参数）。

| 参数行 | 短选项 | 控件 | seqkit 默认值 | 作用 |
| --- | --- | --- | --- | --- |
| `--seq-type` | `-t` | 可编辑下拉 | `auto` | 序列类型 `dna\|rna\|protein\|unlimit\|auto`，`auto` 按第一条序列自动检测 |
| `--threads` | `-j` | 整数 | `4` | CPU 数目；这个 `4` 是 seqkit 2.14.0 自己在 `--help` 里打印的字面默认值，被原样记进参数表，界面不会按本机 CPU 数重算。不勾选就完全不传，实际线程数由 seqkit 决定，也可用环境变量 `SEQKIT_THREADS` |
| `--line-width` | `-w` | 整数 | `60` | 输出 FASTA 的行宽，`0` 表示不换行 |
| `--id-regexp` | — | 文本 | `^(\S+)\s?` | 解析 ID 的正则 |
| `--id-ncbi` | — | 布尔 | `false` | 头部为 NCBI 风格（`>gi\|...\|ref\|NC_002516.2\| ...`） |
| `--out-file` | `-o` | 输出文件 + 浏览 | `-` | 输出文件，`-` 为标准输出，文件名以 `.gz` 结尾则输出 gzip 压缩内容 |
| `--quiet` | — | 布尔 | `false` | 静默，不显示额外信息 |
| `--alphabet-guess-seq-length` | — | 整数 | `10000` | 用第一条序列的该前缀长度推断序列类型，`0` 为整条 |
| `--infile-list` | `-X` | 输入文件 + 浏览 | 空 | 每行一个输入文件的列表；界面把它作为 `--infile-list 列表文件` 选项传下去，排在 `--` 终止符前面 |
| `--skip-file-check` | — | 布尔 | `false` | 确信文件存在时跳过输入文件检查 |
| `--compress-level` | — | 整数 | `-1` | gzip / zstd / xz / bzip2 的压缩级别 |

## 4. 运行前校验

点**运行**时界面先按参数表里记录的 seqkit 源码约束做检查；不通过时**不会启动进程**，弹窗列出缺失项并把对应参数行的说明文字标红。下面几类规则的含义与它们在弹窗/注意事项里渲染成的句子：

| 规则类型 | 界面上的含义 | 你会看到的句子（英文原文 / 中文） |
| --- | --- | --- |
| `requires_any` | 所列参数行至少勾选一个 | `one of --pattern / --pattern-file is required` / 必须设置其中之一：--pattern / --pattern-file |
| `requires_all` | 所列参数行全部都要勾 | `--range is required` / --range 为必填项 |
| `conditional` | 勾选前者就必须给后者 | `--by-seq is required because --only-positive-strand is enabled` / 启用 --only-positive-strand 时必须同时设置 --by-seq |
| `forbid_pairs` | 两者不能同时勾选 | `--lower-case and --upper-case cannot be used together` / --lower-case 与 --upper-case 不能同时使用 |
| 输入文件契约 | 文件数量与是否接受位置参数 | `at least 2 input file(s) required` / 至少需要 2 个输入文件；`this command does not accept input files as arguments` / 该命令不接受以位置参数传入输入文件 |
| 有界运行（`BOUNDED_RUN_FLAGS`） | 永不返回的命令必须给出退出条件 | `one of --find-only / --time-limit is required` / 必须设置其中之一：--find-only / --time-limit |

这些句子由 `i18n` 文案表渲染，所以弹窗在两种界面语言下都是本地化的；参数表里记录的规则也实时列在表单的**注意事项**分区里，涉及的参数行带“必填”红标。有界运行那条不在注意事项里（`ui/param_form.py` 的 `_build_notes()` 只渲染前四类），只在点**运行**时由 `validate()` 报出。下面是逐命令的清单：

| 命令 | 约束 |
| --- | --- |
| `grep`、`locate` | `--pattern` 与 `--pattern-file` 至少一个；`locate` 另有 `--degenerate ✕ --max-mismatch`、`--use-regexp ✕ --max-mismatch` |
| `range` | 必填 `--range` |
| `sliding` | `--window` 与 `--step` 必须同时给 |
| `sample`、`sample2` | `--number` 与 `--proportion` 至少一个；最多 1 个输入文件 |
| `split` | `--by-size` / `--by-part` / `--by-id` / `--by-region` 至少一个；`--keep-temp → --two-pass`、`--update-faidx → --two-pass`；最多 1 个输入文件 |
| `split2` | `--by-size` / `--by-part` / `--by-length` 至少一个；最多 1 个输入文件 |
| `subseq` | `--region` / `--bed` / `--gtf` 至少一个；`--bed ✕ --feature`、`--only-flank ✕ --up-stream` |
| `restart` | `--new-start` 与 `--start-with` 至少一个 |
| `fa2fq` | 必填 `--fasta-file`（位置参数是 FASTQ 文件） |
| `pair` | 必填 `--read1` 与 `--read2`；**不接受位置参数**，输入文件列表里放了文件会被拦下 |
| `amplicon` | `--bed` / `--primer-file` / `--forward` / `--reverse` 至少一个 |
| `fish` | `--query-fastx` 与 `--query-sequences` 至少一个 |
| `mutate` | `--point` / `--insertion` / `--deletion` / `--pattern` / `--pattern-file` 至少一个；`--insertion ✕ --deletion` |
| `replace` | `--pattern` 与 `--f-pattern` 至少一个；`--keep-key → --pattern` |
| `common`、`concat` | 至少 2 个输入文件；`common` 另有 `--only-positive-strand → --by-seq`、`--check-embedded-seqs → --by-seq` |
| `rmdup`、`shuffle`、`sort` | `--only-positive-strand → --by-seq`（`rmdup`）；`--keep-temp → --two-pass`、`--update-faidx → --two-pass`（`shuffle`/`sort`） |
| `bam` | `--stat` / `--idx-stat` / `--idx-count` / `--count` / `--grep-ids` / `--dump` / `--top-bam` / `--tool` / `--list-fields` 至少一个 |
| `seq` | `--lower-case ✕ --upper-case`、`--dna2rna ✕ --rna2dna` |
| `faidx` | 至少 1 个文件，不支持 stdin，不支持 gz/xz/zst 压缩文件 |
| `scat`、`watch` | 至少 1 个输入（`scat` 的位置参数可为目录，递归读取）；`scat` 还要 `--find-only` 与 `--time-limit` 至少勾一个，否则运行被拒绝 |
| `version`、`genautocomplete`、`pair` | 不接受输入文件作为位置参数 |

---

> 自本节起，每条命令的“**常用**”行列出的是**精选的常用参数**，不是该命令的完整清单——完整清单以界面“命令参数 / 全局参数”分区里的参数行为准（参数表由 seqkit 2.14.0 源码生成，共 353 个命令参数；按上游惯例，参数表与界面都不收录 cobra 注入的 `-h/--help`）。

## 5. 基础操作命令

### `faidx` — 创建 FASTA 索引文件并提取子序列

- **输入**：至少 1 个文件；不支持 stdin，不支持压缩文件 ｜ **必需**：无
- **常用**：`-l/--region-file`、`-r/--use-regexp`、`-i/--ignore-case`、`-U/--update-faidx`、`-f/--full-head`、`-I/--immediate-output`

示例 A（只建索引）：输入文件加 `genome.fa`，不勾选任何参数。

```text
seqkit faidx genome.fa
```

示例 B（按区域列表提取）：输入文件加 `genome.fa`；勾选 `--region-file` 并浏览选中 `regions.txt`（每行一个区域）。

```text
seqkit faidx --region-file regions.txt genome.fa
```

### `scat` — 实时递归拼接并流式输出 fastx 文件

- **输入**：至少 1 个路径，目录会被递归读取 ｜ **必需**：`--find-only` 与 `--time-limit` 至少一个（`BOUNDED_RUN_FLAGS`，不在参数表的 `requires_any` 里）
- **常用**：`-i/--format`、`-I/--in-format`、`-O/--out-format`、`-f/--find-only`、`-g/--gz-only`、`-r/--regexp`、`-T/--time-limit`、`-p/--wait-pid`

`scat` 对给定目录建立 fsnotify 监听器并循环输出，不给退出条件就永不返回。界面把这种情况当作缺失的必需项，在创建子进程**之前**就拒绝运行，因此不存在“GUI 里挂着监听”这种用法。

示例 A（只拼接目录里已有的文件，然后退出）：输入文件里加目录 `D:\data\runs`，勾选 `--find-only`。

```text
seqkit scat --find-only -- D:\data\runs
```

示例 B（监听一段时间，无活动即退出）：勾选 `--time-limit` 并填 `30s`。

```text
seqkit scat --time-limit 30s -- D:\data\runs
```

`--wait-pid` 不能作为退出条件：它的默认值 `-1` 表示这条计时器根本没启用。

### `seq` — 转换序列（提取 ID、按长度过滤、去除 gap、反向互补等）

- **输入**：任意数量文件 ｜ **必需**：无 ｜ **互斥**：`--lower-case ✕ --upper-case`、`--dna2rna ✕ --rna2dna`
- **常用**：`-m/--min-len`、`-M/--max-len`、`-i/--only-id`、`-n/--name`、`-s/--seq`、`-q/--qual`、`-r/--reverse`、`-p/--complement`、`-g/--remove-gaps`、`-G/--gap-letters`、`--f-pattern` 系列筛选参数

示例 A（保留 100–500 bp 的序列，只输出 ID）：勾选 `--min-len` 填 `100`、`--max-len` 填 `500`、勾选 `--only-id`。

```text
seqkit seq --max-len 500 --min-len 100 --only-id a.fa
```

示例 B（反向互补）：勾选 `--reverse` 与 `--complement`。

```text
seqkit seq --complement --reverse a.fa
```

### `sliding` — 按滑动窗口提取子序列

- **输入**：任意数量文件 ｜ **必需**：`--window` 与 `--step` 必须同时给
- **常用**：`-g/--greedy`、`-S/--suffix`、`-c/--circular`

示例（窗口 100、步长 50，导出末尾不足窗口的片段）：勾选 `--window` 填 `100`、`--step` 填 `50`、勾选 `--greedy`。

```text
seqkit sliding --greedy --step 50 --window 100 c.fa
```

### `stats` — FASTA/Q 文件的简易统计（别名 `stat`）

- **输入**：任意数量文件 ｜ **必需**：无
- **常用**：`-a/--all`、`-T/--tabular`、`-N/--N`（多行，每行一个值）、`-b/--basename`、`-i/--stdin-label`、`-E/--fq-encoding`；本命令的**全局参数**只有 10 行

示例 A（全量统计多个文件）：输入文件加 `a.fa`、`b.fq`，勾选 `--all`。

```text
seqkit stats --all a.fa b.fq
```

示例 B（结果写文件、FASTA 不换行、8 线程）：展开**全局参数**，勾选 `--out-file` 填 `stats.tsv`、勾选 `--line-width` 填 `0`、勾选 `--threads` 填 `8`。

```text
seqkit stats --threads 8 --line-width 0 --out-file stats.tsv a.fa
```

### `subseq` — 按区域/GTF/BED 获取子序列（含侧翼）

- **输入**：任意数量文件 ｜ **必需**：`--region` / `--bed` / `--gtf` 至少一个 ｜ **互斥**：`--bed ✕ --feature`、`--only-flank ✕ --up-stream`
- **常用**：`-u/--up-stream`、`-d/--down-stream`、`-R/--region-coord`、`--gtf-tag`、`--chr`（多行）、`-U/--update-faidx`

示例 A（取一条区域）：勾选 `--region` 填 `1:100..200`。

```text
seqkit subseq --region 1:100..200 g.fa
```

示例 B（按 GTF 提取 CDS 并带上基因名注释）：勾选 `--gtf` 选 `genes.gtf`，勾选 `--feature` 填一行 `CDS`，勾选 `--gtf-tag` 保持默认 `gene_id`。

```text
seqkit subseq --feature CDS --gtf genes.gtf --gtf-tag gene_id genome.fa
```

### `translate` — 将 DNA/RNA 翻译为蛋白质序列

- **输入**：任意数量文件 ｜ **必需**：无
- **常用**：`-T/--transl-table`、`-f/--frame`（多行，可填 `1`、`-1`、`6` 等）、`-F/--append-frame`、`-m/--min-len`、`--trim`、`-x/--allow-unknown-codon`、`-l/--list-transl-table`

示例（正反两个阅读框、把阅读框写进 ID、用表 11）：勾选 `--frame` 填两行 `1` 与 `-1`，勾选 `--append-frame`，勾选 `--transl-table` 填 `11`。

```text
seqkit translate --append-frame --frame 1 --frame=-1 --transl-table 11 cds.fa
```

### `watch` — 监控序列特征并实时绘制直方图

- **输入**：至少 1 个文件 ｜ **必需**：无 ｜ 该命令持续运行，需点**停止**
- **常用**：`-f/--fields`（`ReadLen`/`MeanQual`/`GC`/`GCSkew`）、`-y/--dump`、`-p/--print-freq`、`-B/--bins`、`-O/--img`、`-H/--list-fields`、`-x/--pass`

示例（统计 GC 并把直方图数据打到错误流）：输入文件加正在写入的 `growing.fq`，勾选 `--fields` 填 `GC`，勾选 `--dump`。

```text
seqkit watch --dump --fields GC growing.fq
```

## 6. 格式转换命令

### `convert` — 在 Sanger、Solexa、Illumina 之间转换 FASTQ 质量值编码

- **输入**：任意数量文件 ｜ **必需**：无 ｜ 无法推断来源编码时需显式勾选 `--from`
- **常用**：`--from`、`--to`（默认 `Sanger`）、`-d/--dry-run`、`-f/--force`、`-n/--nrecords`

示例（先看会不会被转换，再转成 Sanger）：勾选 `--dry-run` 与 `--to`（值 `Sanger`）。

```text
seqkit convert --dry-run --to Sanger x.fq
```

### `fa2fq` — 根据 FASTA 文件检索对应的 FASTQ 记录

- **输入**：位置参数是 FASTQ 文件 ｜ **必需**：`--fasta-file`
- **可用**：`-P/--only-positive-strand`

示例：勾选 `--fasta-file` 选 `sub.fa`；输入文件里加 `all.fq`。

```text
seqkit fa2fq --fasta-file sub.fa all.fq
```

### `fq2fa` — 将 FASTQ 转换为 FASTA

- **输入**：任意数量文件 ｜ **必需**：无 ｜ 该命令没有任何专属参数，只需选文件运行

示例：

```text
seqkit fq2fa a.fq
```

### `fx2tab` — 将 FASTA/Q 转换为表格（长度、GC、平均质量值等）

- **输入**：任意数量文件 ｜ **必需**：无
- **常用**：`-l/--length`、`-g/--gc`、`-G/--gc-skew`、`-q/--avg-qual`、`-n/--name`、`-i/--only-id`、`-s/--seq-hash`、`-C/--base-count`（多行）、`-B/--base-content`（多行）、`-f/--file-name`、`-Q/--no-qual`

示例（输出 ID、长度、GC 三列）：勾选 `--name`、`--length`、`--gc`。

```text
seqkit fx2tab --gc --length --name a.fa
```

### `tab2fx` — 将表格转换回 FASTA/Q

- **输入**：任意数量文件 ｜ **必需**：无
- **常用**：`-b/--buffer-size`（默认 `1G`，报 `token too long` 时增大）、`-p/--comment-line-prefix`（多行，默认 `#`、`//`）

示例：勾选 `--buffer-size` 填 `2G`。

```text
seqkit tab2fx --buffer-size 2G table.txt
```

## 7. 搜索命令

### `amplicon` — 通过引物提取扩增子（或其周围区域）

- **输入**：任意数量文件 ｜ **必需**：`--bed` / `--primer-file` / `--forward` / `--reverse` 至少一个
- **常用**：`-F/--forward`、`-R/--reverse`、`-p/--primer-file`、`-m/--max-mismatch`、`-r/--region`、`-f/--flanking-region`、`-u/--save-unmatched`、`-M/--output-mismatches`

示例（一对引物、允许 2 处错配）：勾选 `--forward` 填 `GGTT`、`--reverse` 填 `AACC`、勾选 `--max-mismatch` 填 `2`。

```text
seqkit amplicon --forward GGTT --max-mismatch 2 --reverse AACC amp.fa
```

### `fish` — 用局部比对在长序列中查找短序列

- **输入**：任意数量文件（参考序列） ｜ **必需**：`--query-fastx` 与 `--query-sequences` 至少一个
- **常用**：`-f/--query-fastx`、`-F/--query-sequences`（单值文本框，只填一条）、`-q/--min-qual`（默认 `5`）、`-p/--aln-params`（默认 `4,-4,-2,-1`）、`-g/--print-aln`、`-b/--out-bam`、`-i/--invert`

示例：勾选 `--query-fastx` 选 `query.fa`，勾选 `--min-qual` 填 `30`。

```text
seqkit fish --min-qual 30 --query-fastx query.fa ref.fa
```

### `grep` — 按 ID/name/序列/motif 搜索序列，允许错配

- **输入**：任意数量文件 ｜ **必需**：`--pattern` 与 `--pattern-file` 至少一个
- **常用**：`-p/--pattern`（多行）、`-f/--pattern-file`、`-s/--by-seq`、`-n/--by-name`、`-i/--ignore-case`、`-v/--invert-match`、`-m/--max-mismatch`、`-r/--use-regexp`、`-C/--count`、`-P/--only-positive-strand`、`-c/--circular`、`-R/--region`

示例 A（按 ID 取若干条）：勾选 `--pattern`，在多行框里每行写一个 ID。

```text
seqkit grep --pattern seq1 reads.fa
```

示例 B（按序列 motif 搜索，允许 2 处错配）：勾选 `--by-seq`、`--max-mismatch` 填 `2`，在 `--pattern` 里填两行 `ATGG`、`TTCG`。

```text
seqkit grep --by-seq --max-mismatch 2 --pattern ATGG --pattern TTCG a.fa
```

### `locate` — 定位子序列/motif，允许错配

- **输入**：任意数量文件 ｜ **必需**：`--pattern` 与 `--pattern-file` 至少一个 ｜ **互斥**：`--degenerate ✕ --max-mismatch`、`--use-regexp ✕ --max-mismatch`
- **常用**：`-p/--pattern`（多行）、`-r/--use-regexp`、`-d/--degenerate`、`-m/--max-mismatch`、`--bed`、`--gtf`、`-M/--hide-matched`、`-F/--use-fmi`、`-G/--non-greedy`

示例（把匹配位置输出成 BED）：勾选 `--pattern` 填 `GGTT`，勾选 `--bed`。

```text
seqkit locate --bed --pattern GGTT ref.fa
```

## 8. 集合操作命令

### `common` — 按 id/name/序列查找多个文件的共有序列

- **输入**：**至少 2 个文件** ｜ **必需**：无 ｜ **条件**：`--only-positive-strand → --by-seq`、`--check-embedded-seqs → --by-seq`
- **可用**：`-s/--by-seq`、`-n/--by-name`、`-i/--ignore-case`、`-P/--only-positive-strand`、`-e/--check-embedded-seqs`

示例（按序列比较三个文件）：输入文件加 `a.fa`、`b.fa`、`c.fa`，勾选 `--by-seq`。

```text
seqkit common --by-seq a.fa b.fa c.fa
```

### `duplicate` — 将序列复制 N 次（别名 `dup`）

- **输入**：任意数量文件 ｜ **必需**：无 ｜ 可用参数只有 `-n/--times`（默认 `1`）

示例：勾选 `--times` 填 `3`。

```text
seqkit duplicate --times 3 a.fa
```

### `head` — 打印前 N 条记录，或总长度达到 L 的前导记录

- **输入**：任意数量文件 ｜ **必需**：无
- **常用**：`-n/--number`（默认 `10`）、`-l/--length`（支持 K/M/G 后缀，给出后会覆盖 `-n`）

示例：勾选 `--number` 填 `5`。

```text
seqkit head --number 5 a.fa
```

### `head-genome` — 打印具有相同前缀的第一条基因组

- **输入**：任意数量文件 ｜ **必需**：无 ｜ 可用参数只有 `-m/--mini-common-words`（默认 `1`）

示例：勾选 `--mini-common-words` 填 `2`。

```text
seqkit head-genome --mini-common-words 2 multi.fa
```

### `pair` — 匹配两个 fastq 文件中的双端 reads

- **输入**：**不接受位置参数**（输入文件列表里放文件会被拦下） ｜ **必需**：`--read1` 与 `--read2`
- **常用**：`-1/--read1`、`-2/--read2`、`-O/--out-dir`、`-f/--force`、`-u/--save-unpaired`

示例：勾选 `--read1` 选 `r1.fq`、`--read2` 选 `r2.fq`、`--out-dir` 填 `paired`、勾选 `--save-unpaired`。

```text
seqkit pair --out-dir paired --read1 r1.fq --read2 r2.fq --save-unpaired
```

### `range` — 打印指定范围（start:end）内的记录

- **输入**：任意数量文件 ｜ **必需**：`--range`

示例（取前 12 条）：勾选 `--range` 填 `1:12`。

```text
seqkit range --range 1:12 a.fa
```

### `rmdup` — 按 ID/name/序列去除重复

- **输入**：任意数量文件 ｜ **必需**：无 ｜ **条件**：`--only-positive-strand → --by-seq`
- **常用**：`-s/--by-seq`、`-n/--by-name`、`-i/--ignore-case`、`-d/--dup-seqs-file`、`-D/--dup-num-file`

示例（按序列去重）：勾选 `--by-seq`。

```text
seqkit rmdup --by-seq a.fa
```

### `sample` — 按数目或比例抽取序列

- **输入**：**最多 1 个文件** ｜ **必需**：`--number` 与 `--proportion` 至少一个
- **常用**：`-n/--number`、`-p/--proportion`、`-s/--rand-seed`（默认 `11`）、`-2/--two-pass`、`-r/--non-deterministic`

示例（固定种子抽 1000 条，先用两遍模式避免全部载入内存）：勾选 `--number` 填 `1000`、`--rand-seed` 填 `11`、勾选 `--two-pass`。

```text
seqkit sample --number 1000 --rand-seed 11 --two-pass big.fq
```

### `sample2` — 按数目或比例抽取序列（version 2）

- **输入**：**最多 1 个文件** ｜ **必需**：`--number` 与 `--proportion` 至少一个
- **常用**：同 `sample`；`-n` 语义为精确抽取 `min(N, total)` 条

示例（按 10% 比例）：勾选 `--proportion` 填 `0.1`。

```text
seqkit sample2 --proportion 0.1 big.fa
```

### `split` — 按 id/区域/大小/份数拆分为文件（主要用于 FASTA）

- **输入**：**最多 1 个文件** ｜ **必需**：`--by-size` / `--by-part` / `--by-id` / `--by-region` 至少一个 ｜ **条件**：`--keep-temp → --two-pass`、`--update-faidx → --two-pass`
- **常用**：`-i/--by-id`、`-p/--by-part`、`-s/--by-size`、`-r/--by-region`、`-O/--out-dir`、`-P/--out-prefix`、`-W/--part-width`、`-f/--force`、`-d/--dry-run`、`-e/--extension`、`-2/--two-pass`

示例 A（拆成 4 份）：勾选 `--by-part` 填 `4`。

```text
seqkit split --by-part 4 one.fa
```

示例 B（每条序列一个文件，输出到指定目录并覆盖）：勾选 `--by-id`、`--out-dir` 填 `byID`、勾选 `--force`。

```text
seqkit split --by-id --force --out-dir byID genome.fa
```

### `split2` — 按大小/份数/长度拆分为文件（FASTA、双端/单端 FASTQ）

- **输入**：**最多 1 个文件** ｜ **必需**：`--by-size` / `--by-part` / `--by-length` 至少一个
- **常用**：`-s/--by-size`、`-p/--by-part`、`-l/--by-length`、`-1/--read1`、`-2/--read2`、`-O/--out-dir`、`-P/--out-prefix`、`-N/--seqid-as-filename`、`-W/--part-width`、`-e/--extension`、`-f/--force`

示例（拆分双端数据，每份 100 万条；配对输出时前缀必须含 `{read}`）：勾选 `--by-size` 填 `1000000`、`--read1` 选 `r1.fq.gz`、`--read2` 选 `r2.fq.gz`、`--out-prefix` 填 `part_{read}`。

```text
seqkit split2 --by-size 1000000 --out-prefix part_{read} --read1 r1.fq.gz --read2 r2.fq.gz
```

## 9. 编辑命令

### `concat` — 拼接多个文件中相同 ID 的序列（别名 `concate`）

- **输入**：**至少 2 个文件** ｜ **必需**：无
- **常用**：`-f/--full`（类似 full/outer join）、`-F/--fill`（缺失处填充，如 `N`）、`-s/--separator`（默认 `|`）

示例：输入文件加 `a.fa`、`b.fa`，勾选 `--full`，勾选 `--fill` 填 `N`。

```text
seqkit concat --fill N --full a.fa b.fa
```

### `mutate` — 编辑序列（点突变、插入、缺失）

- **输入**：任意数量文件 ｜ **必需**：`--point` / `--insertion` / `--deletion` / `--pattern` / `--pattern-file` 至少一个 ｜ **互斥**：`--insertion ✕ --deletion`
- **常用**：`-p/--point`（多行，如 `2:C`、`-1:A`）、`-i/--insertion`（如 `0:ACGT`）、`-d/--deletion`（如 `1:2`）、`-s/--pattern`（多行）、`-r/--use-regexp`、`-n/--by-name`、`-v/--invert-match`

示例（第 2 个碱基改为 C，最后一个改为 A）：勾选 `--point`，在多行框填两行 `2:C` 与 `-1:A`。

```text
seqkit mutate --point 2:C --point=-1:A ref.fa
```

### `rename` — 重命名重复 ID

- **输入**：任意数量文件 ｜ **必需**：无
- **常用**：`-O/--out-dir`（默认 `renamed`）、`-m/--multiple-outfiles`、`-s/--separator`（默认 `_`）、`-N/--start-num`（默认 `2`）、`-1/--rename-1st-rec`、`-n/--by-name`、`-f/--force`

示例（多个输入文件分别输出）：勾选 `--multiple-outfiles`。

```text
seqkit rename --multiple-outfiles a.fa b.fa
```

### `replace` — 用正则表达式替换名称/序列

- **输入**：任意数量文件 ｜ **必需**：`--pattern` 与 `--f-pattern` 至少一个 ｜ **条件**：`--keep-key → --pattern`
- **常用**：`-p/--pattern`、`-r/--replacement`（支持 `$1`、`{kv}`、`{nr}`）、`-s/--by-seq`、`-i/--ignore-case`、`-k/--kv-file`、`--nr-width`、`-m/--key-miss-repl`、`-K/--keep-key`、`-U/--keep-untouch`；`--f-pattern`（多行，无短选项）与 `--f-pattern-file`、`--f-by-name` 等 `--f-` 前缀参数用于筛选目标记录

示例（把 ID 前缀 `seq` 换成 `sample_`）：勾选 `--pattern` 填 `^seq`，勾选 `--replacement` 填 `sample_`。

```text
seqkit replace --pattern ^seq --replacement sample_ a.fa
```

### `restart` — 重置环状基因组的起始位置（别名 `rotate`）

- **输入**：任意数量文件 ｜ **必需**：`--new-start` 与 `--start-with` 至少一个
- **常用**：`-i/--new-start`（默认 `1`，支持负数从末尾计数）、`-s/--start-with`、`-m/--max-mismatch`、`-I/--ignore-case`

示例（从第 100 个碱基开始）：勾选 `--new-start` 填 `100`。

```text
seqkit restart --new-start 100 cir.fa
```

### `sana` — 修复损坏的单行 FASTQ 文件

- **输入**：任意数量文件 ｜ **必需**：无
- **常用**：`-i/--format`、`-I/--in-format`、`-O/--out-format`、`-A/--allow-gaps`、`-b/--qual-ascii-base`

示例（直接修复）：输入文件加 `broken.fq`，不勾选任何参数。

```text
seqkit sana broken.fq
```

## 10. 排序命令

### `shuffle` — 打乱序列顺序

- **输入**：任意数量文件；`--two-pass` 模式下只接受一个文件 ｜ **必需**：无 ｜ **条件**：`--keep-temp → --two-pass`、`--update-faidx → --two-pass`
- **常用**：`-s/--rand-seed`（默认 `23`）、`-r/--non-deterministic`、`-2/--two-pass`、`--tmp-dir`（默认 `./`）、`-k/--keep-temp`、`-U/--update-faidx`

示例（可复现的打乱）：勾选 `--rand-seed` 填 `42`。

```text
seqkit shuffle --rand-seed 42 a.fa
```

### `sort` — 按 id/name/序列/长度排序

- **输入**：任意数量文件；`--two-pass` 模式下只接受一个文件 ｜ **必需**：无 ｜ **条件**：`--keep-temp → --two-pass`、`--update-faidx → --two-pass`
- **常用**：`-l/--by-length`、`-s/--by-seq`、`-n/--by-name`、`-b/--by-bases`、`-r/--reverse`、`-N/--natural-order`、`-i/--ignore-case`、`-L/--seq-prefix-length`、`-2/--two-pass`、`-G/--gap-letters`

示例（按长度从大到小）：勾选 `--by-length` 与 `--reverse`。

```text
seqkit sort --by-length --reverse a.fa
```

## 11. BAM 处理命令

### `bam` — BAM 记录特征统计与实时直方图

- **输入**：BAM/SAM 文件；`--stat`、`--idx-stat` 可多文件，其余模式只接受一个文件 ｜ **必需**：`--stat` / `--idx-stat` / `--idx-count` / `--count` / `--grep-ids` / `--dump` / `--top-bam` / `--tool` / `--list-fields` 至少一个
- **常用**：`-s/--stat`、`-i/--idx-stat`、`-C/--idx-count`、`-c/--count`、`-f/--field`、`-g/--grep-ids`、`-G/--exclude-ids`（单值文本框）、`-q/--map-qual`、`-m/--range-min`、`-M/--range-max`、`-F/--prim-only`、`-x/--pass`、`-O/--img`、`-y/--dump`、`-H/--list-fields`

示例 A（多文件统计）：输入文件加 `a.bam`、`b.bam`，勾选 `--stat`。

```text
seqkit bam --stat a.bam b.bam
```

示例 B（基于索引快速计数并写文件）：勾选 `--idx-count`，勾选 `--count` 填 `counts.txt`。

```text
seqkit bam --count counts.txt --idx-count a.bam
```

## 12. 杂项命令

### `merge-slides` — 合并 `seqkit sliding` 生成的滑动窗口

- **输入**：任意数量文件；输出文件不能是输入文件之一 ｜ **必需**：无
- **常用**：`-l/--min-overlap`（默认 `1`，建议为 `步长-1`）、`-g/--max-gap`（默认 `0`）、`-r/--regexp`、`-b/--buffer-size`、`-p/--comment-line-prefix`（多行）

示例（窗口 100、步长 50 时最小重叠取 49）：勾选 `--min-overlap` 填 `49`。

```text
seqkit merge-slides --min-overlap 49 slides.fa
```

### `sum` — 计算文件中所有序列的摘要（消息指纹）

- **输入**：任意数量文件 ｜ **必需**：无
- **常用**：`-a/--all`、`-c/--circular`、`-k/--kmer-size`、`-i/--include-id`、`-g/--remove-gaps`、`-b/--basename`、`--rna2dna`、`-s/--single-strand`

示例：勾选 `--all`。

```text
seqkit sum --all a.fa
```

## 13. 未分组命令（命令树末尾的合成节点，中文 `其他` / 英文 `Other`）

### `genautocomplete` — 生成 shell 自动补全脚本

- **输入**：不接受输入文件 ｜ **必需**：无
- **可用**：`--shell`（可编辑下拉，候选 `bash|zsh|fish|powershell`，默认 `bash`）、`--file`（补全脚本写入路径；参数表里保存的是中性占位 `$HOME/.bash_completion.d/seqkit.sh`，界面预填时展开成你这台机器上的家目录，运行前确认目标路径）

示例（生成 zsh 的补全脚本）：勾选 `--shell` 选 `zsh`。

```text
seqkit genautocomplete --shell zsh
```

### `version` — 打印版本信息并检查更新

- **输入**：不接受输入文件 ｜ **必需**：无 ｜ 可用参数：`-u/--check-update`（联网检查更新）

示例：不勾选任何参数直接运行，结果标签显示 seqkit 的版本信息。

```text
seqkit version
```

---

## 14. 常见任务索引

| 想做的事 | 命令 | 在 GUI 里勾选 |
| --- | --- | --- |
| 按 ID 提取若干条序列 | `grep` | `--pattern`（多行填 ID） |
| 把一批 ID 存成文件再提取 | `grep` | `--pattern-file` |
| 只要不匹配的序列 | `grep` | `--pattern` + `--invert-match` |
| 按 motif / 正则搜索 | `grep` 或 `locate` | `--by-seq` / `--use-regexp` |
| 统计 FASTA/Q 基本信息 | `stats` | `--all` |
| 过滤短序列 | `seq` | `--min-len` |
| 反向互补 | `seq` | `--reverse` + `--complement` |
| 去掉 gap 字符 | `seq` | `--remove-gaps`（必要时改 `--gap-letters`） |
| 提取某条区域并带上游 50 bp | `subseq` | `--region` + `--up-stream` |
| 滑动窗口切片段 | `sliding` | `--window` + `--step` |
| 合并滑动窗口 | `merge-slides` | `--min-overlap` |
| 随机抽样 | `sample` / `sample2` | `--number` 或 `--proportion`（配 `--rand-seed`） |
| 拆分大文件 | `split` / `split2` | `--by-part` / `--by-size` / `--by-id` |
| 双端数据按 reads 数拆分 | `split2` | `--by-size` + `--read1` + `--read2` + `--out-prefix`（含 `{read}`） |
| 配对双端文件 | `pair` | `--read1` + `--read2`（不放位置参数） |
| 去重复 | `rmdup` | `--by-seq` 或 `--by-name` |
| 取多文件交集 | `common` | 至少 2 个输入文件，必要时 `--by-seq` |
| 拼接相同 ID 的序列 | `concat` | 至少 2 个输入文件，可加 `--full` + `--fill` |
| 排序 | `sort` | `--by-length` / `--by-name` / `--by-seq` + `--reverse` |
| 打乱顺序 | `shuffle` | `--rand-seed` |
| 翻译 | `translate` | `--transl-table`、`--frame`、`--append-frame` |
| FASTQ 质量编码转换 | `convert` | `--from`、`--to`，先用 `--dry-run` 试 |
| FASTQ → FASTA | `fq2fa` | 无参数 |
| 表格 ↔ 序列 | `fx2tab` / `tab2fx` | `--length`、`--gc`、`--name` / `--buffer-size` |
| 重命名重复 ID | `rename` | `--multiple-outfiles`、`--separator` |
| 定点突变 | `mutate` | `--point`（多行） |
| 正则改名/改序列 | `replace` | `--pattern` + `--replacement`（可加 `--by-seq`） |
| 环状基因组旋转起点 | `restart` | `--new-start` 或 `--start-with` |
| 建 FASTA 索引 / 按索引取序列 | `faidx` | `--region-file` |
| 合并目录内所有文件 | `scat` | 位置参数填目录 |
| 监控正在写入的文件 | `watch` | `--fields`、`--dump`，跑完点**停止** |
| BAM 统计 | `bam` | `--stat` / `--idx-stat` / `--idx-count` |
| 校验文件指纹 | `sum` | `--all` |
| 生成 shell 补全 | `genautocomplete` | `--shell` |

## 相关文档

- [安装与第一次运行](getting-started.md)
- [界面逐区说明](interface-guide.md)
- [详细使用手册](user-guide.md)
- [常见问题与故障排查](faq.md)
- [从源码运行与二次开发](development.md)

英文文档见 `docs/en/`。
