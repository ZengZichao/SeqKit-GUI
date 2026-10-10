# SeqKit GUI

**非官方** 的 [SeqKit](https://github.com/shenwei356/seqkit) 桌面图形界面。用 Python 3.10 + PySide6 编写，当前发布平台为 Windows（x64），代码结构为 macOS 预留；界面只在 Windows 上实测过，详见[已知限制](#已知限制与诚实声明)。

> 本项目与 SeqKit 作者无关，也不是 SeqKit 官方产品。界面本身**不做任何序列处理**：它只负责收集参数、组装命令行，然后调用官方的 `seqkit` 可执行文件，并把它的标准输出与错误信息呈现出来。所有生物学计算结果与直接使用命令行完全一致。

English README: [README.en.md](README.en.md)

![主界面](docs/screenshots/light-zh.png)

> 截图里出现的本机绝对路径与用户名已做打码处理。

---

## 目录

- [它做什么](#它做什么)
- [快速开始](#快速开始)
- [界面速览](#界面速览)
- [参数模型：不勾选就不传](#参数模型不勾选就不传)
- [支持的命令](#支持的命令)
- [运行前校验](#运行前校验)
- [语言与主题](#语言与主题)
- [已知限制与诚实声明](#已知限制与诚实声明)
- [从源码运行 / 测试 / 打包](#从源码运行--测试--打包)
- [参数表从哪里来](#参数表从哪里来)
- [项目结构](#项目结构)
- [macOS 与 Linux 支持现状](#macos-与-linux-支持现状)
- [文档](#文档)
- [许可与致谢](#许可与致谢)

## 它做什么

- 选择输入文件：文件对话框、多选、拖拽进窗口、粘贴路径，也可清空与逐条移除。
- 设置 seqkit 参数：41 个子命令的每一个参数都会按其真实类型渲染成对应控件，并带中文/英文说明。
- 运行命令：子进程异步执行，不阻塞界面，可随时停止。
- 查看结果与错误：结果、错误、日志、命令行四个标签页，附带退出码、耗时与输出字节数；大输出全量落盘，界面显示可配置行数上限的预览。

## 快速开始

不想配置 Python？仓库根目录带了可直接运行的 `SeqKit-GUI.exe`（PyInstaller 单文件构建，自包含 Python 与 Qt 运行时，双击即用）；它仍然只是图形外壳，执行命令前还需按下文第 3 步准备好 seqkit。

1. 安装 Python 3.10 或更高版本。
2. 安装依赖：

   ```bash
   python -m pip install -r requirements.txt
   ```

3. 准备 seqkit 可执行文件。仓库里**不包含** seqkit（可执行文件解压后约 28 MB，官方压缩包约 8.6 MB），任选一种方式：

   ```bash
   python tools/fetch_seqkit.py        # 下载官方 2.14.0 发行包并放入 bin/
   ```

   - 手动把 `seqkit.exe` 放进项目的 `bin/` 目录；
   - 或让 seqkit 位于系统 `PATH`；
   - 或在 **设置 → SeqKit 可执行文件** 里指定路径。

   `tools/fetch_seqkit.py` 的可用参数：`--version`（默认 `2.14.0`，标签先经过形状校验才拼进下载 URL，不允许斜杠、`..` 之类）、`--sha256 <64 位十六进制>`（一旦给出就强制比对压缩包的 sha256，是上游 md5 之外的第二道校验）、`--force`（覆盖 `bin/` 里已存在的文件）、`--list`（打印本平台可下载的发行资产名后退出）与 `--timeout`（每个网络请求的秒级超时）。

   查找顺序为：**设置里的路径 → 程序旁的 `bin/` → 系统 `PATH`**（macOS 追加 `/opt/homebrew/bin`、`/usr/local/bin`）。候选名在 Windows 上是 `seqkit.exe`、`seqkit.cmd`、`seqkit.bat`、`seqkit`，其他平台只有 `seqkit`；`seqkit.cmd`/`seqkit.bat` 虽然会被列为候选名，却总是被下面那道判定拒掉。每个候选都要过同一道判定（`seqkit_gui/core/seqkit_locator.py`）：必须是真实存在的文件，且文件头是这台机器真正能执行的镜像格式——Windows 要 `MZ`、Linux 要 `\x7fELF`、macOS 要 Mach-O 魔数；Windows 上 `.bat`/`.cmd`/`.com`/`.ps1`/`.vbs`/`.js`/`.lnk`/`.url` 这类脚本文件被直接拒绝（`QProcess` 无法把它们当程序启动），非 Windows 平台要求 `os.access(..., X_OK)`（`#!` 脚本除外）。除**设置里由用户亲手选定**的那条之外，直接位于程序当前工作目录里的候选一律拒绝，`PATH` 中的空项与相对项也一并跳过——这些都是为了防止二进制种植劫持。重复路径只判一次。状态栏左下角显示命中的完整路径与来源标签 `configured` / `bundled` / `path`。

4. 启动：

   ```bash
   python -m seqkit_gui
   ```

   Windows 下也可以直接运行 `run.bat`。

## 界面速览

| 区域 | 内容 |
| --- | --- |
| 顶栏 | 品牌标识、检测到的 SeqKit 版本徽标、版本不匹配警示徽标（仅在版本不一致时出现）、语言切换、主题切换、设置、使用文档 |
| 菜单栏 | 文件（添加输入文件 / 运行 / 最近使用的文件 / 退出）、视图（展开全部命令分组 / 折叠全部命令分组 / 清空输出 / 搜索参数）、工具（设置 / 复制完整命令 / 手动指定 seqkit 可执行文件）、帮助（打开文档目录 / SeqKit 官方文档 / 关于 SeqKit GUI）。界面没有右键上下文菜单 |
| 左侧命令树 | seqkit 自身的 8 个命令分组，外加末尾一个由界面合成的 `其他` 节点（收 `version` 与 `genautocomplete`），共 9 个顶层节点、41 条命令；顶部搜索框可按命令名、中文/英文说明或别名过滤 |
| 右侧表单 | 输入文件、工作目录、命令参数、全局参数、附加参数、注意事项、文档（命令的完整说明与示例） |
| 底部输出面板 | 结果 / 错误 / 日志 / 命令行 四个标签页；运行、停止、保存结果、复制结果、打开输出文件、自动换行、清空；最右侧是 `退出码 · 耗时 · 输出字节数` 的运行汇总 |
| 状态栏 | 左侧显示当前使用的 seqkit 路径与来源（或运行结果提示），右侧显示即将执行的完整命令；刚完成一次检测时右侧短暂显示 `41 个命令 · Schema 2.14.0` |

全部快捷键：`Ctrl+Enter` 与 `Ctrl+R` 运行、`Ctrl+O` 添加输入文件、`Ctrl+F` 搜索参数、`Ctrl+Shift+C` 复制命令行、`Ctrl+,` 打开设置、`Ctrl+Q` 退出。

![带结果的界面](docs/screenshots/light-zh-result.png)

## 参数模型：不勾选就不传

这是本界面唯一需要理解的规则：

- **非布尔参数**行的左侧有一个启用勾选框。不勾选时该参数**完全不会传给 seqkit**，由 seqkit 使用自己的默认值；勾选后编辑器里的值才会被传入。
- **布尔参数**行的勾选框就是这个开关本身，勾选即追加 `--flag`。
- **可重复参数**（如 `grep -p/--pattern`）使用多行文本框，**每行一个值**，会展开为 `--pattern a --pattern b`。
- **枚举参数**的下拉候选值取自 seqkit 自己 usage 文本中括号里的枚举（例如 `--seq-type` 的 `dna|rna|protein|unlimit|auto`），下拉框仍可手动输入其他内容。
- **文件与目录参数**带浏览按钮，输入文件与输出文件使用不同的对话框。
- 需要完全自由的控制时，用 **附加参数** 行直接写额外选项，它会被按 shell 规则切分成独立参数（不经过 shell 解释）。

含 27 个参数的 `seq` 命令，以及展开后的全局参数分组：

![多参数命令](docs/screenshots/light-zh-many-flags.png)

## 支持的命令

覆盖 SeqKit 2.14.0 的全部 41 个子命令，分组与数量与 seqkit 自身的命令分组一致：

| 分组 | 命令数 | 命令 |
| --- | --- | --- |
| 基础操作命令 | 8 | `faidx` `scat` `seq` `sliding` `stats` `subseq` `translate` `watch` |
| 格式转换命令 | 5 | `convert` `fa2fq` `fq2fa` `fx2tab` `tab2fx` |
| 搜索命令 | 4 | `amplicon` `fish` `grep` `locate` |
| 集合操作命令 | 11 | `common` `duplicate` `head` `head-genome` `pair` `range` `rmdup` `sample` `sample2` `split` `split2` |
| 编辑命令 | 6 | `concat` `mutate` `rename` `replace` `restart` `sana` |
| 排序命令 | 2 | `shuffle` `sort` |
| BAM 处理命令 | 1 | `bam` |
| 杂项命令 | 2 | `merge-slides` `sum` |
| 其他（界面合成节点） | 2 | `genautocomplete` `version` |

分组名称与归属直接取自 seqkit 自身的命令分组，未作调整。`version` 与 `genautocomplete` 在 seqkit 的 cobra 定义里没有分组 ID（`seqkit --help` 把它们列在 `Additional Commands` 下），界面为它们合成了一个末尾节点，中文显示 `其他`、英文显示 `Other`。

逐命令的必需参数与界面填写示例见 [docs/zh/command-guide.md](docs/zh/command-guide.md)。

## 运行前校验

表单在启动进程前会检查从 seqkit 源码里读出的约束，不通过时给出缺失项列表并让对应参数行的说明文字变红，进程**不会启动**：

- 多选一（`requires_any`）：`grep`/`locate` 需要 `--pattern` 或 `--pattern-file`；`sample`/`sample2` 需要 `--number` 或 `--proportion`；`split` 需要 `--by-size`/`--by-part`/`--by-id`/`--by-region` 之一；`split2` 需要 `--by-size`/`--by-part`/`--by-length` 之一；`subseq` 需要 `--region`/`--bed`/`--gtf` 之一；`restart` 需要 `--new-start` 或 `--start-with`；`amplicon` 需要 `--bed`/`--primer-file`/`--forward`/`--reverse` 之一；`fish` 需要 `--query-fastx` 或 `--query-sequences`；`mutate` 需要 `--point`/`--insertion`/`--deletion`/`--pattern`/`--pattern-file` 之一；`replace` 需要 `--pattern` 或 `--f-pattern`；`bam` 需要 `--stat`/`--idx-stat`/`--idx-count`/`--count`/`--grep-ids`/`--dump`/`--top-bam`/`--tool`/`--list-fields` 之一。
- 全部必填（`requires_all`）：`sliding` 需要 `--window` 与 `--step`；`pair` 需要 `--read1` 与 `--read2`；`range` 需要 `--range`；`fa2fq` 需要 `--fasta-file`。
- 互斥组合（`forbid_pairs`）：`seq` 的 `--lower-case`✕`--upper-case` 与 `--dna2rna`✕`--rna2dna`；`mutate` 的 `--insertion`✕`--deletion`；`locate` 的 `--degenerate`✕`--max-mismatch` 与 `--use-regexp`✕`--max-mismatch`；`subseq` 的 `--bed`✕`--feature` 与 `--only-flank`✕`--up-stream`。
- 条件依赖（`conditional`）：`common`/`rmdup` 启用 `--only-positive-strand` 或 `--check-embedded-seqs` 时必须给 `--by-seq`；`replace` 启用 `--keep-key` 时必须给 `--pattern`；`shuffle`/`sort`/`split` 启用 `--keep-temp` 或 `--update-faidx` 时必须给 `--two-pass`。
- 输入文件数量：`common`、`concat` 至少 2 个；`faidx`、`scat`、`watch` 至少 1 个；`sample`、`sample2`、`split`、`split2` 最多 1 个；`faidx` 不支持标准输入也不支持压缩文件；`pair`、`version`、`genautocomplete` 不接受位置参数。
- 有界运行（`BOUNDED_RUN_FLAGS`，`seqkit_gui/core/builder.py:49-51`）：`scat` 用 fsnotify 对给定目录建立监听器并循环到收到停止条件，因此界面要求它至少勾选 `--find-only`（拼接已有文件后退出）或 `--time-limit`（在指定时长内无活动后退出）之一，否则进程**不会启动**，弹窗文案为 `必须设置其中之一：--find-only / --time-limit`。`--wait-pid` 不算退出条件：它的默认值 `-1` 表示不启用该计时器。这条规则由 `validate()` 与上面几类约束一起返回，但**不显示在注意事项分区**里——注意事项只渲染参数表中的 `requires_any` / `requires_all` / `conditional` / `forbid_pairs`。

上面前几类约束全部来自参数表里逐命令记录的 seqkit 源码出处（`commands.json` 的 `requires_any` / `requires_all` / `forbid_pairs` / `conditional` / `inputs` 字段与 `evidence` 行号），界面不额外发明规则，也不替代 seqkit 自身的检查；有界运行那条是界面唯一一条写在代码里的规则（`builder.py` 的 `BOUNDED_RUN_FLAGS`），它的依据同样是上游 `scat` 的实现。

## 语言与主题

- 界面语言：简体中文 / English，顶栏即时切换，无需重启。界面文案见 `seqkit_gui/i18n/`，参数与命令的中文说明由 `tools/translations/` 生成进参数表；353 个命令专属参数与 11 个全局参数的中文说明均已覆盖。
- 主题：Light / Dark，配色令牌集中在 `seqkit_gui/ui/theme.py`，实心色块上始终使用白色文字以保证对比度。
- 语言、主题、seqkit 路径、输出预览行数、默认工作目录、窗口尺寸与最近文件都会记住。

![深色主题英文界面](docs/screenshots/dark-en.png)

## 已知限制与诚实声明

以下限制是对代码行为的直接描述，不是待办事项。

1. **只有 Windows 经过实测。** 全部截图、全部端到端人工验证都在 Windows x64 上完成。macOS 与 Linux 的代码路径确实存在（`seqkit_gui/core/paths.py` 的 `executable_names()`、`seqkit_gui/core/seqkit_locator.py` 里 Darwin 专用的 `/opt/homebrew/bin`、`/usr/local/bin` 前缀、`run.sh`、`tools/fetch_seqkit.py` 的 `Darwin`/`Linux` 分支），但**没有人在真实的 macOS 或 Linux 机器上打开过这个窗口、看过它的渲染、手动跑过一次命令**，也没有为这两个平台产出过打包程序。Linux 与 macOS 一样只有代码分支，没有桌面实测记录。
2. **不代理标准输入，没有管道模式。** 输入必须是文件路径：文件列表、`--infile-list`，或各命令的文件型参数。子进程一启动就调用 `closeWriteChannel()`（`seqkit_gui/core/runner.py` 的 `SeqkitRunner.start()`），seqkit 看到的是一个立即到达结尾的标准输入。因此不给输入文件的运行会以退出码 0 正常结束、结果为空，状态栏显示“运行成功，但没有标准输出内容”，而不是无限等待。不存在 `cat x.fa | SeqKit-GUI` 这种用法，界面也不会往子进程里写任何数据。真正会停不下来的命令是 `scat`——它对目录建立 fsnotify 监听器并循环——界面在启动前就要求它带上退出条件（见“运行前校验”）。
3. **参数表绑定 seqkit 2.14.0。** `seqkit_gui/data/commands.json` 的 `seqkit_version` 是 `2.14.0`。换成其他版本的 seqkit：新版本独有的参数在界面上不存在，旧版本没有的参数界面上仍会列出。顶栏因此有“版本不匹配”警示。若界面组装出的参数被手上的 seqkit 拒绝，seqkit 会以非零退出码结束，界面把它写在 stderr 的原话放进**错误**标签、状态行显示 `失败 · 退出码 N` 并自动切到**错误**标签——不会重试，也不会替它解释。
4. **`--threads` 的默认值是被记录下来的 `4`，不按本机 CPU 数计算。** 参数表里 `--threads` 的 `default` 字段是 `4`，即 seqkit 2.14.0 自己在 `--help` 里打印的字面默认值（`-j, --threads int … (default 4)`，本机 16 核的实测输出同样是 4）。界面把它原样预填进整数框并标注 `默认值: 4`，不会用 `os.cpu_count()` 之类的本机信息重算它；不勾选 `--threads` 时界面完全不传该参数，线程数由手上的 seqkit 自己决定。上游的真实取值规则是 `min(NumCPU, 4)`，环境变量 `SEQKIT_THREADS` 会覆盖它（`seqkit/cmd/root.go:113-128`）——也就是说 `4` 只在 4 核及以上的机器上等于 seqkit 的实际默认值，在更少核的机器上不是。
5. **个别默认值是家目录占位。** `genautocomplete` 的 `--file` 在参数表里存的是中性形式 `$HOME/.bash_completion.d/seqkit.sh`（上游把该默认值定义成运行时的家目录展开，直接抓取就会把生成参数表那台机器的真实路径固化进参数表，所以这里保存的是占位形式）。界面预填时会把 `$HOME` 展开成你这台机器上的家目录；运行该命令前请确认展开后的目标路径就是你要写的位置。
6. **不重新分发 seqkit。** `bin/` 被 `.gitignore` 忽略，仓库与打包产物都不含 seqkit 可执行文件（解压后约 28 MB 的上游程序）。用户需自行把二进制放进 `bin/`、放进 `PATH`、在设置里指定路径，或运行 `python tools/fetch_seqkit.py` 从官方 GitHub Releases 下载。
7. **复制到剪贴板的内容带本机痕迹。** **命令行**标签、**工具 → 复制完整命令**、**日志**标签与状态栏里的内容都包含 seqkit 可执行文件的绝对路径、输入输出文件的绝对路径、工作目录以及临时文件路径——这些字符串里通常有用户名（`C:\Users\<你>\…`）和盘符。把命令或日志贴到 issue、聊天或论文附件时，请先抹掉这些路径。
8. **界面显示是有上限的。** 结果标签只显示前 N 行（默认 5000，设置范围 500–200000）；每个文本视图最多保留最近 20000 个文本块。完整 stdout 始终写入系统临时目录里的 `seqkit-gui-*.out`，**保存结果**与**打开输出文件**取的是这份完整数据；程序不会主动删除这些临时文件。
9. **非 UTF-8 输出会被替换。** stdout/stderr 按 UTF-8 增量解码，无法解码的字节显示为替换字符；临时文件保存的是原始字节，需要未改写的内容时用**保存结果**取出再看。ANSI 颜色码在显示前统一剥离。
10. **一次只能跑一条命令。** `SeqkitRunner` 只持有一个 `QProcess`，运行期间的再次触发被直接忽略，表单与输入框同时锁定。需要并行请开多个程序实例。
11. **界面文案的英文覆盖是“键即英文”策略。** `seqkit_gui/i18n/zh_CN.json` 与 `en_US.json` 的条目数并不相等——中文表明显更大，英文表只收录了一部分，两表的实际条数以文件内容为准。代码用到的界面文案键在 `zh_CN.json` 里全部有译文，中文界面的文字因此不回退英文。英文界面下未收录的键直接显示键名（键名本身就是英文原文），个别控件文字因此保持源文本的大小写风格，不做二次润色：缺 seqkit 时，顶栏徽标和运行弹窗标题在英文界面显示 `seqkit not found`，在中文界面显示 `未找到 seqkit`。
12. **参数过滤器只匹配英文。** 表单顶部的“搜索参数”框匹配参数长名、短选项与**英文** usage 文本；中文界面下按中文名搜索会搜不到，请用 `--name` 或 `-x`。
13. **seqkit 侧的软约束界面不校验。** 例如 `bam` 除 `--stat`/`--idx-stat` 外的模式只接受一个文件、`merge-slides` 的输出不能是输入之一、`shuffle`/`sort` 的 `--two-pass` 只接受一个文件：这些写在**注意事项**分区里供参考，但运行前校验只管上面列出的那几类硬约束，其余交给 seqkit 报错。
14. **没有右键上下文菜单。** 可点的菜单只有菜单栏的 文件 / 视图 / 工具 / 帮助；文件列表通过工具按钮与拖放操作，没有上下文菜单。
15. **不联网、不更新自己。** 程序自身没有任何网络访问，也不会检查自身新版本。唯一可能联网的是你主动勾选 seqkit 自己的 `version --check-update`，那是上游 seqkit 的行为，与本界面无关。

## 从源码运行 / 测试 / 打包

```bash
python -m pip install -r requirements.txt
python -m seqkit_gui                      # 从源码启动

python -m pytest tests -q                 # 运行全部用例；用例会随功能增删变化，数量以本命令的实际输出为准

pip install pyinstaller
pyinstaller packaging/seqkit_gui.spec     # 产物目录 dist/SeqKit-GUI/
```

测试会拿真实的 seqkit 可执行文件做交叉校验：命令清单、每个命令的 `--help`、参数名是否存在，以及若干端到端运行，因此运行测试前需要先准备好 `bin/seqkit.exe`。

打包产物是 **onedir**（一个目录，不是单个 exe）：主程序 `dist/SeqKit-GUI/SeqKit-GUI.exe`，参数表、界面文案与图标在 `dist/SeqKit-GUI/_internal/seqkit_gui/{data,i18n,assets}` 下。发布时把该目录压缩成 `SeqKit-GUI-<version>-windows-x64.zip`（`<version>` 取自 `seqkit_gui/__init__.py` 的 `__version__`，当前为 `1.0.0`），并附带一份同名的摘要文件 `SeqKit-GUI-<version>-windows-x64.zip.sha256`，内容是 `sha256sum -c` 可直接校验的那一行。压缩包里**不含 `seqkit.exe`**——`packaging/seqkit_gui.spec` 会检查所有被收集的文件，只要有一个来自仓库的 `bin/` 就直接终止构建。所以解压之后要自己把 `seqkit.exe` 放进程序旁边的 `bin/`，即 `dist/SeqKit-GUI/bin/seqkit.exe`，那正是程序查找的第二站。

## 参数表从哪里来

界面里的每一个参数都不是手写的，而是从 SeqKit 2.14.0 源码生成：

1. `tools/spec-dumper`（Go）引用 seqkit 的 `cmd` 包，遍历 cobra 命令树，导出每个命令与其 pflag 参数的名称、简写、类型、默认值与 usage 原文。
2. `tools/extract_spec.py` 把它规整成 `seqkit_gui/data/commands.json`：为每个参数判定控件类型、抽取枚举候选、合并中文说明，并附上从各命令 `Run` 函数里读出的输入文件契约与必需参数约束（记录来源文件与行号）。

重新生成：

```bash
python tools/extract_spec.py --build --seqkit-src ../../../seqkit-2.14.0
```

这一步需要 Go 工具链；普通使用与运行测试都不需要。

## 项目结构

```
seqkit_gui/
  core/       与界面无关的部分：参数表、命令组装、子进程、可执行文件定位、配置
  ui/         PySide6 界面：主窗口、动态表单、输出面板、主题、语言
  data/       commands.json —— 由源码生成的命令与参数表
  i18n/       界面文案表
  assets/     图标
tools/
  spec-dumper/  导出 cobra 命令树的 Go 工具
  extract_spec.py  生成 data/commands.json
  fetch_seqkit.py  下载官方 seqkit 发行包
  translations/    参数与命令的中文说明表
tests/        参数表一致性、命令组装、校验规则、真实运行、界面构建
docs/         中英文文档与截图
packaging/    PyInstaller 配置
```

## macOS 与 Linux 支持现状

平台差异被集中处理，移植时不需要改动界面代码：

- `seqkit_gui/core/paths.py` 决定可执行文件候选名（Windows 为 `seqkit.exe`、`seqkit.cmd`、`seqkit.bat`、`seqkit`，其他平台只有 `seqkit`）、`bin/` 位置与资源目录。
- `seqkit_gui/core/seqkit_locator.py` 的搜索路径在 Darwin 上追加 `/opt/homebrew/bin` 与 `/usr/local/bin`；判定用的镜像魔数按平台切换（Linux 取 `\x7fELF`/`MZ`，macOS 取 Mach-O 各变体），非 Windows 平台额外要求 `os.access(..., X_OK)` 执行位并允许 `#!` 脚本，而 `.bat`/`.cmd` 之类的后缀黑名单只在 Windows 生效。
- 子进程通过参数列表启动，不使用任何平台专用 API，也不经过 shell；命令行展示按平台选用不同的引号规则。
- `run.sh` 与 `tools/fetch_seqkit.py` 已按 POSIX 分支编写；下载器认识的平台是 `Windows`、`Darwin`、`Linux` 三种（CPU 架构认识 `amd64`/`x86_64` 与 `arm64`/`aarch64`）。上游另外还发布 `freebsd`、`openbsd` 的构建，本下载器不认识它们，需要手动放入 `bin/`。
- 上述代码路径没有人在真实的 macOS / Linux 桌面上人工运行并验证过（见[已知限制](#已知限制与诚实声明)第 1 条）。

## 文档

- 中文：[入门](docs/zh/getting-started.md) · [界面说明](docs/zh/interface-guide.md) · [命令指南](docs/zh/command-guide.md) · [使用手册](docs/zh/user-guide.md) · [常见问题](docs/zh/faq.md) · [开发指南](docs/zh/development.md)
- English: [Getting started](docs/en/getting-started.md) · [Interface guide](docs/en/interface-guide.md) · [Command guide](docs/en/command-guide.md) · [User guide](docs/en/user-guide.md) · [FAQ](docs/en/faq.md) · [Development](docs/en/development.md)
- 参与贡献：[CONTRIBUTING.md](CONTRIBUTING.md)（中文）· [CONTRIBUTING.en.md](CONTRIBUTING.en.md)（English）；提 issue 与 PR 的模板在仓库的 `.github/ISSUE_TEMPLATE/` 与 `.github/pull_request_template.md`
- 遇到使用问题该去哪里问：[SUPPORT.md](SUPPORT.md)；发现安全漏洞请按 [SECURITY.md](SECURITY.md) 描述的方式报告；社区行为约定见 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- SeqKit 本身的参数含义请查阅上游文档：<https://bioinf.shenwei.me/seqkit/>

## 许可与致谢

- 本项目以 **MIT** 许可证发布，见 [LICENSE](LICENSE)。
- [SeqKit](https://github.com/shenwei356/seqkit) 是 Wei Shen（`shenwei356`）主导的上游项目，同样采用 MIT 许可证；其版权声明与许可全文保留在 [THIRD-PARTY-LICENSES.md](THIRD-PARTY-LICENSES.md)。本项目不重新分发 SeqKit 程序本体，也没有得到上游的任何背书。
- 界面基于 PySide6（Qt for Python，LGPLv3）构建，第三方许可说明同样见 [THIRD-PARTY-LICENSES.md](THIRD-PARTY-LICENSES.md)。
- 上游 `seqkit --help` 与仓库 README 给出的引用格式（SeqKit 2.14.0 对应的是 SeqKit2 论文）：

  > Wei Shen\*, Botond Sipos, and Liuyang Zhao. 2024. *SeqKit2: A Swiss Army Knife for Sequence and Alignment Processing.* **iMeta** e191. <https://doi.org/10.1002/imt2.191>

**再次说明：本项目是非官方作品，与 SeqKit 作者无关，也不是 SeqKit 官方图形界面。**
