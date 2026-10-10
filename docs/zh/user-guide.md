# 详细使用手册

> 本文是**非官方 SeqKit GUI** 的简体中文文档，按任务组织：从启动程序到拿到结果，一步一步走完每个常用场景。SeqKit GUI 是 [SeqKit](https://github.com/shenwei356/seqkit)（Wei Shen 开发的 MIT 许可序列工具包）的桌面图形前端；本项目与 SeqKit 项目无关，未获其认可，也不由其维护，不是 SeqKit 的官方图形界面。

## 0. 文档地图

| 你想做什么 | 看哪篇 |
| --- | --- |
| 装好程序、第一次跑起来 | [安装与第一次运行](getting-started.md) |
| 查窗口某个角落是干什么的 | [界面逐区说明](interface-guide.md) |
| 查某个命令该怎么填 | [命令与参数指南](command-guide.md) |
| **照着场景一步步做** | **本手册** |
| 出错了、行为奇怪 | [常见问题与故障排查](faq.md) |
| 改代码、重新打包 | [从源码运行与二次开发](development.md) |

本手册的所有操作都基于同一件事实：**界面只组装参数数组并调用官方 `seqkit` 可执行文件，自己做任何序列计算。** 所以手册里每个"填法"都对应一条真实命令行，随时可以用状态栏右侧的实时预览或**命令行**标签核对。

## 1. 准备与启动

1. 按[入门文档](getting-started.md)装好 Python 依赖并准备好 `seqkit` 可执行文件（用 `python tools/fetch_seqkit.py` 下载、手动放进 `bin\`、或已在 PATH 里均可）。
2. 双击 `run.bat`（Windows）或运行 `./run.sh`（macOS/Linux）；也可以在项目目录里执行 `python -m seqkit_gui`。
3. 启动后看顶栏徽标：显示 `SeqKit 2.14.0` 即一切就绪；显示"未找到 seqkit"时按[入门文档第 3.3 节](getting-started.md)处理；出现"版本不匹配"徽标说明检测到的版本与参数表版本（2.14.0）不一致，功能可用但参数可能对不上，悬停徽标看说明。

程序按**设置里指定的路径 → 项目 `bin\` 目录 → PATH** 的顺序找 seqkit。"设置里指定"的文件以你的选择为准；后两处来源的候选文件还必须正确回答 `seqkit version` 才会被采用，冒名文件会被拒绝并在状态栏说明原因。

## 2. 五个核心概念

理解这五条，41 个命令的表单就是同一个表单：

| 概念 | 含义 |
| --- | --- |
| 勾选 = 传参 | 参数行左侧的勾选框决定该参数是否出现在命令行里。不勾选就完全不传，seqkit 用自己的默认值；编辑器里预填的值只是提示 |
| 布尔行没有编辑器 | 勾选即传 `--flag`，例如 `--by-seq` |
| 多行框每行一个值 | 可重复参数（如 `grep --pattern`）的编辑器是多行框，每行一个值，展开成重复的 `--pattern a --pattern b` |
| 下拉框可自由输入 | 候选值来自 seqkit 自己的 usage 文本，但你可以直接键入其他值 |
| 负值自动带等号 | 值以 `-` 开头时界面写成 `--flag=值`（如 `--frame=-1`），避免被当成选项 |

位置输入文件始终排在独立的 `--` 终止符之后，所以名字以 `-` 开头的文件不会被误当成参数。**附加参数**框里的内容按 shell 引用规则切分后追加在终止符之前，适合启用界面没有建模的选项。

## 3. 一次完整运行（六步法）

1. **选命令**：在左侧命令树点一条命令，或在上方的搜索框按名称/中文摘要/别名（如 `stat`、`dup`、`concate`、`rotate`）过滤。
2. **加输入文件**：点**添加文件**多选，或把文件/文件夹从资源管理器拖进窗口，或点**粘贴路径**按行导入剪贴板文本。留空时 seqkit 读到的是一个立即结束的标准输入（界面不会代你输入内容），因此除了 `version`、`genautocomplete`、`pair` 之外，请至少添加一个文件。
3. **检查工作目录**：它决定 seqkit 子进程的当前目录（相对路径、`split` 等命令的输出位置都基于它），默认取首个输入文件所在目录。
4. **勾参数**：展开**命令参数**，只勾选本次需要的行并填值；需要控制输出时展开**全局参数**勾 `--out-file` 等。找参数用 `Ctrl+F` 聚焦"搜索参数"框。
5. **运行**：点**运行**按钮，或 `Ctrl+R`，或 `Ctrl+Enter`。校验不通过时弹窗列出缺失项、涉及的行标红，进程不会被创建。
6. **看结果**：在**结果 / 错误 / 日志 / 命令行**四个标签之间切换。状态栏左侧显示完成提示，右侧实时预览命令行（`Ctrl+Shift+C` 可复制）。

## 4. 常用任务配方

以下每个配方都可以在**命令行**标签里核对生成的命令。示例中的文件名换成你自己的。

### 4.1 查看文件的基本统计

**目标**：知道每个文件有多少条序列、总长度、N50 等摘要。

1. 选命令 `stats`（别名 `stat`）。
2. 输入文件加入一个或多个 FASTA/FASTQ。
3. 勾选 `--all`（输出全部统计列，默认只有基础几列）。
4. 运行。表格出现在**结果**标签。

```text
seqkit stats --all a.fa b.fq
```

想直接得到文件：展开**全局参数**，勾选 `--out-file` 填 `stats.tsv`。

### 4.2 按 ID 提取序列子集

**目标**：从 `reads.fa` 里取出若干条已知 ID 的序列。

1. 选命令 `grep`。
2. 输入文件加 `reads.fa`。
3. 勾选 `--pattern`，在多行框里**每行写一个 ID**（三行就是三个 `--pattern`）。
4. 运行。

```text
seqkit grep --pattern seq1 --pattern seq2 -- reads.fa
```

ID 很多时改用文件：把 ID 一行一个存进 `ids.txt`，勾选 `--pattern-file` 选它。按序列内容而不是 ID 搜时，勾选 `--by-seq`；允许错配再勾 `--max-mismatch` 填数字。

```text
seqkit grep --by-seq --max-mismatch 2 --pattern ATGG --pattern TTCG a.fa
```

### 4.3 找 motif 并输出位置

**目标**：定位序列里 `GGTT` 出现的位置，得到 BED 格式坐标。

1. 选命令 `locate`。
2. 输入文件加 `ref.fa`。
3. 勾选 `--pattern` 填 `GGTT`，勾选 `--bed`。
4. 运行，结果可作为 BED 交给 `subseq` 等下游工具。

```text
seqkit locate --bed --pattern GGTT ref.fa
```

### 4.4 长度过滤与取 ID

**目标**：保留 100–500 bp 的序列，只输出 ID 行。

1. 选命令 `seq`。
2. 输入文件加 `a.fa`。
3. 勾选 `--min-len` 填 `100`、`--max-len` 填 `500`、勾选 `--only-id`。
4. 运行。

```text
seqkit seq --max-len 500 --min-len 100 --only-id a.fa
```

反向互补是同一命令：勾选 `--reverse` 与 `--complement`。

### 4.5 转 TSV 再转回来

**目标**：把 FASTA 转成"ID、长度、GC"三列的表格。

1. 选命令 `fx2tab`，输入文件加 `a.fa`。
2. 勾选 `--name`、`--length`、`--gc`。
3. 运行；要留文件就配合全局 `--out-file`。

```text
seqkit fx2tab --gc --length --name a.fa
```

反向转换用 `tab2fx`（输入文件给表格），表格太大报 `token too long` 时勾选 `--buffer-size` 填 `2G`。

### 4.6 去重、抽样、排序

| 目标 | 命令 | 表单填法 |
| --- | --- | --- |
| 按序列去重 | `rmdup` | 勾选 `--by-seq`（按 ID 用 `--by-name`） |
| 固定种子抽 1000 条 | `sample` | 勾选 `--number` 填 `1000`、`--rand-seed` 保持默认 `11`、勾选 `--two-pass`（大文件先过索引省内存） |
| 按长度从大到小排序 | `sort` | 勾选 `--by-length` 与 `--reverse` |

```text
seqkit rmdup --by-seq a.fa
seqkit sample --number 1000 --rand-seed 11 --two-pass big.fq
seqkit sort --by-length --reverse a.fa
```

`sample`/`sample2`/`split`/`split2` 只接受**一个**输入文件，多放会被校验拦下。

### 4.7 滑动窗口切片

**目标**：按窗口 100、步长 50 切出全部片段，末尾不足窗口的也要。

1. 选命令 `sliding`，输入文件加 `c.fa`。
2. 勾选 `--window` 填 `100`、`--step` 填 `50`（两者必须同时给）、勾选 `--greedy`。
3. 运行。

```text
seqkit sliding --greedy --step 50 --window 100 c.fa
```

### 4.8 提取子序列

**目标 A**：取某条序列第 100–200 位。选 `subseq`，勾选 `--region` 填 `1:100..200`（`序列编号:起点..终点`）。

```text
seqkit subseq --region 1:100..200 g.fa
```

**目标 B**：按 GTF 注释提取全部 CDS。勾选 `--gtf` 选 `genes.gtf`、`--feature` 填 `CDS`、`--gtf-tag` 保持默认 `gene_id`（提取出的 ID 带基因名）。

```text
seqkit subseq --feature CDS --gtf genes.gtf --gtf-tag gene_id genome.fa
```

也可以用 `faidx` 直接按区域提取：勾选 `--region-file` 选一个每行一个区域（如 `chr1:1..100`）的文本文件。注意 `faidx` 不支持标准输入，也不支持 gz/xz/zst 压缩文件。

### 4.9 翻译成蛋白质

**目标**：用第 11 号密码子表，按正反两个阅读框翻译，把阅读框写进 ID。

1. 选命令 `translate`，输入文件加 `cds.fa`。
2. 勾选 `--frame`，多行框填两行：`1` 和 `-1`。
3. 勾选 `--append-frame`。
4. 勾选 `--transl-table` 填 `11`。
5. 运行。

```text
seqkit translate --append-frame --frame 1 --frame=-1 --transl-table 11 cds.fa
```

不确定有哪些密码子表时，勾选 `--list-transl-table` 跑一次即可。

### 4.10 拆分大文件

**目标 A**：把 `one.fa` 均分成 4 份。选 `split`，勾选 `--by-part` 填 `4`。

**目标 B**：拆双端 FASTQ，每份 100 万条。选 `split2`，勾选 `--by-size` 填 `1000000`、`--read1` 选 `r1.fq.gz`、`--read2` 选 `r2.fq.gz`、`--out-prefix` 填 `part_{read}`——**配对输出时前缀必须含 `{read}` 占位符**。

```text
seqkit split --by-part 4 one.fa
seqkit split2 --by-size 1000000 --out-prefix part_{read} --read1 r1.fq.gz --read2 r2.fq.gz
```

拆分输出默认写在**工作目录**下，需要指定时勾选 `--out-dir`。

### 4.11 改名与改序列

**改 ID 前缀**：选 `replace`，勾选 `--pattern` 填 `^seq`、`--replacement` 填 `sample_`。

**点突变**：选 `mutate`，勾选 `--point`，多行框填 `2:C` 和 `-1:A`（第 2 位改成 C、最后一位改成 A）。

```text
seqkit replace --pattern ^seq --replacement sample_ a.fa
seqkit mutate --point 2:C --point=-1:A ref.fa
```

### 4.12 BAM 文件快速统计

**前提**：BAM 需要已建索引（`.bai`）。选命令 `bam`，输入文件加一个或多个 `.bam`，勾选 `--stat` 运行。

```text
seqkit bam --stat a.bam b.bam
```

基于索引快速计数并写文件：勾选 `--idx-count`，勾选 `--count` 填 `counts.txt`。

### 4.13 生成 shell 补全脚本

1. 选命令 `genautocomplete`（无输入文件）。
2. `--shell` 下拉选一种（`bash`/`zsh`/`fish`/`powershell`）。
3. 勾选 `--file` 填目标路径——参数表预填的是 seqkit 自己的默认 `$HOME/.bash_completion.d/seqkit.sh`（界面上已展开成你的家目录），确认后再运行。

### 4.14 其他值得一试的

| 想做的事 | 命令 | 一句话填法 |
| --- | --- | --- |
| 求多个文件的共有序列 | `common` | 至少 2 个输入文件；按序列用 `--by-seq` |
| 串联相同 ID 的序列 | `concat`（别名 `concate`） | 至少 2 个输入文件 |
| 双端数据配对 | `fa2fq` / `pair` | `pair` 不接受位置输入，用 `--read1`/`--read2` 选文件 |
| 重置环状基因组起点 | `restart`（别名 `rotate`） | 勾选 `--new-start` 或 `--start-with` 之一 |
| 监控序列特征直方图 | `watch` | 需要手动**停止**；它按间隔持续输出 |

全部 41 个命令的参数级说明见[命令与参数指南](command-guide.md)。

## 5. 输入文件的规则

- **支持的格式**：FASTA/FASTQ（含 `.gz`、`.bgzip`、`.bz2`、`.xz`、`.zst` 压缩），`bam` 命令接受 `.bam`/`.sam`。个别命令例外（`faidx` 不支持压缩与标准输入），表单下方的灰色提示行会逐条写明。
- **文件夹**：`scat` 的输入是路径列表，文件夹会被递归读取；其他命令的文件列表就是文件本身。
- **自动去重**：列表内重复路径只保留一份；最多 2000 条，超出的会在提示行报告。
- **就地修改**：双击列表中的一条路径可以在弹出的对话框里改；**移除**删选中项，**清空**清整个列表。
- **带引号的路径**：从资源管理器"复制文件地址"得来的 `"C:\...\a b.fa"` 会自动剥掉外层引号。
- **超长路径**：超过 259 字符的路径会提示需要 Windows 长路径支持，避免 seqkit 静默失败。
- **最近使用的文件**：**文件 → 最近使用的文件**子菜单保留最近 15 条，点击即加入列表；**清除列表**清空记录。

## 6. 运行控制

- **运行期间**表单与输出按钮锁定（**停止**除外），可以继续切换命令、改搜索——那只影响界面，不影响正在跑的进程。
- **停止**先发终止信号，4 秒后仍未退出则强制结束；`watch` 这类持续输出的命令要手动停。
- **`scat` 的特殊规则**：它对目录建监听器、没有退出条件就永不返回，所以界面在**校验阶段**就要求勾选 `--find-only` 或 `--time-limit`，否则根本不会创建进程。
- **启动失败**（找不到/无法执行 seqkit）时，状态行显示"启动失败"，**错误**与**日志**标签会补一行排查提示。
- **退出码**：非 0 且非手动取消时自动跳到**错误**标签；stdout/stderr 全文始终落盘到临时文件，界面预览只是前 N 行。

## 7. 结果处理

| 操作 | 怎么做 |
| --- | --- |
| 看完整输出 | 预览默认 5000 行（设置里 500–200000 可调）；超出时结果末尾提示"输出预览已截断"，点**打开输出文件**或**保存结果**拿全量 |
| 保存结果 | **保存结果**把临时文件原样另存（默认建议名 `~/seqkit-result.txt`） |
| 复制结果 | **复制结果**；界面为空时自动回读落盘文件，截断不影响复制全量 |
| 复制命令行 | **命令行**标签或 `Ctrl+Shift+C`，得到的是按平台引号规则转义、可直接贴进终端的形式 |
| 对齐列 | 保持**自动换行**不勾选 |
| 清屏 | **清空**按钮或**视图 → 清空输出** |

## 8. 设置项

入口：顶栏**设置**或 `Ctrl+,`。

| 设置 | 作用 |
| --- | --- |
| SeqKit 可执行文件 | 留空走自动检测；**自动检测**重新按 `bin\` → PATH 找一遍，**浏览**手选，**测试**跑 `seqkit version` 验证 |
| 语言 / 主题 | 即时生效，无需重启；两处（顶栏与设置）任选一处切换 |
| 输出预览行数上限 | 只影响界面显示，不影响落盘的完整输出 |
| 默认工作目录 | 每次选中新命令时填入"工作目录"的初值 |

设置与窗口布局（尺寸、分栏比例）都会记住；Windows 上存于注册表 `HKEY_CURRENT_USER\Software\seqkit-gui\SeqKit GUI`。

## 9. 快捷键总表

| 快捷键 | 动作 |
| --- | --- |
| `Ctrl+O` | 添加输入文件 |
| `Ctrl+R` | 运行 |
| `Ctrl+Enter` | 运行（表单内） |
| `Ctrl+L` | 聚焦"搜索命令"框 |
| `Ctrl+F` | 聚焦"搜索参数"框 |
| `Ctrl+,` | 打开设置 |
| `Ctrl+Shift+C` | 复制完整命令行 |
| `Ctrl+Q` | 退出（有进程在跑时先确认） |

## 10. 疑难速查

| 现象 | 先看这里 |
| --- | --- |
| 顶栏"未找到 seqkit" | [入门文档第 3.3 节](getting-started.md)；或设置里手动指定 |
| "版本不匹配"徽标 | 检测到的版本与参数表 2.14.0 不一致；能跑但参数可能对不上 |
| 运行弹出"参数不完整" | 弹窗列出缺失项，对应行说明变红；各命令必需项见[命令指南](command-guide.md) |
| 结果为空但退出码 0 | 状态栏会提示"运行成功，但没有标准输出内容"；看**错误**标签里的 stderr |
| 输出被截断 | 见第 7 节，用**打开输出文件**取全量 |
| 中文关键词搜不到参数 | 参数过滤搜的是英文说明，用 `--name` 或 `-x` 这类英文关键词 |
| 其他 | [常见问题与故障排查](faq.md) |

## 相关文档

- [安装与第一次运行](getting-started.md)
- [界面逐区说明](interface-guide.md)
- [命令与参数指南](command-guide.md)
- [常见问题与故障排查](faq.md)
- [从源码运行与二次开发](development.md)

英文文档见 `docs/en/`。
