# 常见问题与故障排查

> 本文是**非官方 SeqKit GUI** 的简体中文文档，按“现象 → 原因 → 处理”的方式整理排查清单。SeqKit GUI 是 [SeqKit](https://github.com/shenwei356/seqkit)（Wei Shen 开发的 MIT 许可序列工具包）的桌面图形前端；本项目与 SeqKit 项目无关，未获其认可，也不由其维护，不是 SeqKit 的官方图形界面。

## 1. 排查顺序速查

| 步骤 | 检查 | 看哪里 |
| --- | --- | --- |
| 1 | seqkit 是否被找到 | 顶栏徽标是否显示 `SeqKit 2.14.0`；状态栏左下角的路径与来源 `(configured/bundled/path)` |
| 2 | 版本是否与参数表一致 | 顶栏是否出现“版本不匹配”徽标 |
| 3 | 参数是否满足该命令的硬性约束 | 表单的**注意事项**分区；点运行时的弹窗 |
| 4 | 界面到底传了什么 | 状态栏右下角的实时预览；输出面板的**命令行**标签 |
| 5 | seqkit 自己怎么说 | 输出面板的**错误**标签与**日志**标签 |

## 2. 启动与依赖

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 双击 `run.bat` 后窗口闪退，提示 `python was not found on PATH` | 未安装 Python 或安装时没勾选 “Add Python to PATH” | 重装 Python 3.10+ 并勾选加入 PATH；或改用完整解释器路径执行 `python -m seqkit_gui` |
| 启动时报缺少 PySide6 | 依赖未装进当前解释器 | 在项目目录执行 `python -m pip install -r requirements.txt`；有多个 Python 时确认 `python -V` 与 pip 装到同一个环境 |
| 弹出“Command schema could not be loaded” | `seqkit_gui/data/commands.json` 缺失或损坏 | 该文件随仓库分发，恢复它；仍不行则按提示用 `python tools/extract_spec.py --build` 重新生成（需要 Go，见 [开发说明](development.md)） |
| 程序能开，但所有命令都跑不了 | 没找到 seqkit | 见下一节 |
| 窗口打开后一片空白或文字错位 | 分栏被拖到极窄、或字体缩放 | 用**视图 → 展开全部命令分组**恢复命令树；拖动中间的分隔条；必要时重置偏好（见 8.3） |

## 3. 找不到 seqkit

顶栏显示“未找到 seqkit”、状态栏提示“未找到 seqkit 可执行文件……”时，按查找顺序逐条确认：**设置中的路径 → 程序旁的 `bin\` → 系统 `PATH`**（macOS 额外看 `/opt/homebrew/bin`、`/usr/local/bin`）。每一站命中的候选还要通过同一道判定（真实存在的文件 + 本机可执行镜像的文件头魔数；Windows 还拒绝 `.bat`/`.cmd` 等脚本后缀，非 Windows 要求执行位），且除设置里亲手选的那条之外，位于当前工作目录里的候选会被直接拒绝、`PATH` 中的空项与相对项会被跳过。

| 情况 | 处理 |
| --- | --- |
| 想最省事 | 在项目目录执行 `python tools/fetch_seqkit.py`，它会把官方 2.14.0 发行包里的可执行文件放进 `bin\`；已有文件时加 `--force` |
| 离线机器 | 手动把 `seqkit.exe` 放进 `<项目目录>\bin\`；打包版则放进 `dist\SeqKit-GUI\bin\` |
| 机器上已装 seqkit | 顶栏仍显示未找到时，用**工具 → 手动指定 seqkit 可执行文件**选到那个文件，或在**设置**里填完整路径后点**测试** |
| 设置里填了路径但显示“无法运行该文件” | 该路径不是可执行文件、被占用、或缺少依赖；用**自动检测**重新定位，或先在终端里直接运行该文件确认它本身可用 |
| 杀毒软件/Windows Defender 拦截 | `bin\seqkit.exe` 是约 28 MB 的 Go 单文件程序，容易被误报；添加信任后重开程序 |
| 状态栏显示 `path` 但版本不对 | PATH 里存在另一个 seqkit，优先级低于 `bin\`；删掉多余副本或在设置里固定路径（优先级最高） |

## 4. 版本不匹配

顶栏出现“版本不匹配”表示：参数表按 SeqKit 2.14.0 源码生成，而检测到的可执行文件是别的版本。

- 表现：只有新版本才有的参数在界面上不存在；或手上的 seqkit 不认识界面传过去的参数，seqkit 报 `unknown flag`。
- 处理：换回 2.14.0（`python tools/fetch_seqkit.py --version 2.14.0 --force`）；或继续使用手上这个版本，把差异参数写进**附加参数**框；若要彻底对齐，按 [开发说明](development.md) 重新生成参数表。

## 5. 点“运行”后没有启动进程

| 弹窗/提示 | 原因 | 处理 |
| --- | --- | --- |
| “参数不完整”，列出 `one of --pattern / --pattern-file is required` 之类 | 未满足该命令的运行前约束，进程**不会启动** | 按提示勾选被标红的参数行；每个命令的必需项见 [命令指南](command-guide.md) 第 4 节 |
| 提示 `at least 2 input file(s) required` | `common`、`concat` 需要至少 2 个输入文件 | 在**输入文件**里补齐 |
| 提示 `必须设置其中之一：--find-only / --time-limit` | 选中的是 `scat`，而它没有可退出的条件（详见第 7 节） | 勾选 `--find-only` 或 `--time-limit` 再运行 |
| 提示 `this command does not accept input files as arguments` | `pair`、`version`、`genautocomplete` 不接受位置参数 | 清空输入文件列表；`pair` 改用 `--read1` / `--read2` |
| 只弹了“未找到 seqkit”并自动打开设置 | 没有可执行文件 | 见第 3 节 |
| 什么都没发生 | 上一次运行仍在进行（按钮区显示“运行中”），或没有选中命令 | 点**停止**，或在左侧重新选择一个命令 |
| 状态显示 `启动失败`（FailedToStart） | 路径失效、文件被占用或不是可执行文件 | 重新**自动检测** + **测试** |

## 6. 运行了但结果不对

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 退出码非 0，**结果**标签是空的 | seqkit 把错误写在 stderr | 切到**错误**标签看具体报错；**日志**标签里有同样的内容与完整命令行 |
| **结果**标签为空但退出码 0，状态提示“运行成功，但没有标准输出内容” | 勾选了 `--out-file`，输出被 seqkit 直接写进文件 | 去那个文件里看结果；想看界面输出就别勾选 `--out-file` |
| 结果末尾出现“输出预览已截断，完整结果保存在输出文件中” | 输出行数超过界面显示上限（默认 5000） | 点**打开输出文件**或**保存结果**取全量；或在设置里调高“输出预览行数上限” |
| 生成的文件不见了 | 相对路径是相对**工作目录**解析的 | 看**命令行**标签里的 `cd` 行（**日志**标签也有），或把输出路径写成绝对路径 |
| 明明勾了参数却没生效 | 值填了但没勾选该行的复选框；或勾选了但值被清空 | 只有勾选的行才会被传；确认复选框为选中状态 |
| 多个值只生效一个 | 该参数不是可重复参数：`replace --pattern`、`fish --query-sequences`、`bam --grep-ids` 在 seqkit 里都是单值 `string`，界面按单行文本框渲染 | 换成可重复的那一类参数（`stringSlice`，如 `grep -p`、`mutate -p`、`seq --f-pattern`、`stats -N`），在**多行框**里每行写一个值 |
| 想传 `-1`、`-1:A` 这类以短横线开头的值 | 会被误认为选项 | 界面已自动改成 `--flag=值` 形式；若自己写在**附加参数**里，也要用 `--frame=-1` 这种等号写法 |
| 文件名里有空格/中文导致失败 | — | 本界面不拼接 shell 字符串，路径会作为单个参数传递，正常无需处理；问题多出在**附加参数**里的手写引号 |
| 结果里出现乱码 | seqkit 输出非 UTF-8 字节 | 以 UTF-8 解码，无法解码的字节显示为替换字符；用**保存结果**取原始字节文件再看 |
| 进度条把界面刷屏 | seqkit 的进度信息走 stderr | 属于正常，**结果**标签不受影响；勾选全局参数 `--quiet` 可减少额外输出 |

## 7. 特定命令的常见坑

| 命令 | 坑 | 正确做法 |
| --- | --- | --- |
| `faidx` | 不支持标准输入，也不支持 gz/xz/zst 压缩文件 | 必须给出至少 1 个未压缩 FASTA 文件 |
| `pair` | 不接受位置参数 | 用 `--read1` / `--read2` 指定两个 fastq |
| `split` / `split2` / `sample` / `sample2` | 只接受 1 个输入文件 | 需要处理多文件时逐个运行；`split2` 的双端输入用 `--read1`/`--read2` |
| `split2` 配对输出 | 文件名会互相覆盖 | 输出前缀里必须含 `{read}` |
| `sample` / `sample2` 双端 | 两个文件抽到不同的 read | 两次运行使用相同的 `--rand-seed` |
| `sliding` | 只给 `--window` 不给 `--step` | 两者必须同时勾选 |
| `subseq` | 勾选 `--bed` 又勾选 `--feature` | 互斥；`--feature` 仅对 `--gtf` 有效 |
| `locate` | `--use-regexp` 或 `--degenerate` 与 `--max-mismatch` 同时勾选 | 互斥，去掉 `--max-mismatch` |
| `seq` | `--lower-case` 与 `--upper-case`、`--dna2rna` 与 `--rna2dna` 同时勾选 | 互斥，二选一 |
| `sort` / `shuffle` / `split` | 勾选 `--keep-temp` 或 `--update-faidx` 却没勾 `--two-pass` | 这两个开关必须与 `--two-pass` 同时勾选；`sort`/`shuffle` 的**注意事项**还写明 `--two-pass` 模式下只接受一个文件 |
| `watch` | 看起来“卡住” | 它是轮询型命令，会按 `--print-freq` 的间隔持续输出直到被停止，点**停止**结束。界面不会给它加退出条件 |
| `scat` | 点运行弹窗“必须设置其中之一：--find-only / --time-limit” | `scat` 对目录建立 fsnotify 监听器并循环，不给出退出条件就永远不会结束，所以界面在启动子进程前就拒绝这次运行。想一次性拼接已有文件请勾 `--find-only`，想监听一段时间再退出请勾 `--time-limit`；`--wait-pid` 不算退出条件（默认值 `-1` 表示该计时器未启用） |
| `bam` | 想拿数据而不是绘图 | `--dump` 会把直方图数据打印到 stderr 而不绘图；`bam` 本身不是监听型命令，跑完自然退出 |
| `merge-slides` | 输出文件与输入文件相同 | 换一个输出路径 |
| `version --check-update` | 需要联网 | 内网环境不要勾选 |
| `genautocomplete` | `--file` 预填的是参数表里保存的中性占位 `$HOME/.bash_completion.d/seqkit.sh`，界面会把它展开成你这台机器上的家目录 | 运行前确认展开后的目标路径，必要时改成自己要写的位置 |

## 8. 界面、语言与设置

### 8.1 中文界面里夹杂英文

- 界面文字表在 `seqkit_gui/i18n/zh_CN.json`，键就是英文原文；代码用到的键在这里全部有译文。两份表并不对称：不变量是 `en_US.json` 的键集合是 `zh_CN.json` 键集合的**子集**，而不是两者相等——写作本文时 `zh_CN.json` 有 125 个键、`en_US.json` 有 53 个，两个数字都随界面改动变化，以文件实际内容为准。缺键时先回退 `en_US.json`，再回退键本身。
- 仍是英文的是代码字面写出的部分：参数行悬停提示里的 `type:` / `default:` 与第四行的英文 usage、**文档**分区里 seqkit 自己的长说明与示例、输入文件提示末尾的 `fasta|fastq|fa|fq(+ compressed)` 格式串、状态栏里的 `(configured/bundled/path)` 与右侧的 `Schema`。
- 参数说明与命令摘要的中文来自 `tools/translations/usage_zh.json` 与 `command_zh.json`；某条参数没有译文时显示 seqkit 的英文 usage。
- 命令树末尾的合成节点在中文里显示 `其他`、英文里显示 `Other`（`seqkit_gui/core/spec.py` 的 `in_groups()`），收 `version` 与 `genautocomplete` 这两条 seqkit 未声明分组的命令，两种语言都有本地化标题。

### 8.2 切换语言/主题需要重启吗

不需要。顶栏的语言与主题即时生效；切换语言时会保留当前命令、输入文件列表与工作目录。

### 8.3 重置偏好设置

偏好由 Qt 的 `QSettings` 保存（组织 `seqkit-gui`，应用 `SeqKit GUI`）。Windows 上位于注册表 `HKEY_CURRENT_USER\Software\seqkit-gui\SeqKit GUI`，删除该项即回到默认（简体中文、浅色主题、5000 行预览、自动检测 seqkit）。窗口大小位置在 `ui/geometry`，左右分栏在 `ui/splitter`，最近文件在 `files/recent`（也可用**文件 → 最近使用的文件 → 清除列表**）。

### 8.4 其他界面问题

| 现象 | 处理 |
| --- | --- |
| 找不到某个参数 | `Ctrl+F` 聚焦“搜索参数”，按名字/短选项/说明过滤；注意“全局参数”分区默认折叠 |
| 参数行显示为红色 | 校验失败标记，说明该行是缺失的必需项；勾选并填值后红色消失 |
| 想关掉一个默认即为真的布尔开关 | 组装器确实有这条规则（取消勾选会输出 `--flag=false`），但 2.14.0 参数表里没有任何布尔参数声明默认值为真，所以这条分支实际不会触发；需要显式写 `--flag=false` 时用**附加参数**框 |
| 输入文件列表里重复添加同一文件 | 自动去重，不会重复传参 |
| 拖文件夹进去没反应 | 只有 `scat` 会把位置参数当目录递归读取，其他命令需要选文件 |
| 想只复制命令去终端跑 | `Ctrl+Shift+C`（复制的是“命令行”标签内容，含 seqkit 与输入输出文件的绝对路径，通常带本机用户名；外发前先清理） |

## 9. 性能与大文件

| 场景 | 建议 |
| --- | --- |
| 输出很大（例如转换整个基因组） | 勾选 `--out-file` 直接写文件，避免把大结果读进界面；界面预览只是前 N 行 |
| 内存吃紧 | 对支持 `--two-pass` 的命令（`sort`、`shuffle`、`split`、`sample`、`sample2`）勾选它，用两遍读取换低内存；注意参数表里 `shuffle`/`sort` 的**注意事项**明确写了该模式只接受一个文件 |
| 多线程 | 勾选全局参数 `--threads`（参数表记录的默认值是 seqkit 2.14.0 自己在 `--help` 里打印的 `4`，界面不按本机 CPU 数重算），或设置环境变量 `SEQKIT_THREADS` |
| 运行很久想中断 | 点**停止**：先发终止信号，4 秒内未退出则强制结束 |
| 关闭程序时提示“seqkit 仍在运行” | 选择“是”会先停止子进程再退出 |
| 临时文件堆积 | 每次运行会在系统临时目录生成 `seqkit-gui-*.out`，可自行清理；程序不主动删除 |

## 10. 打包版与源码版

| 现象 | 处理 |
| --- | --- |
| 打包版提示找不到 seqkit | 把 `seqkit.exe` 放进 `dist\SeqKit-GUI\bin\`（打包产物刻意不含 seqkit） |
| 双击 exe 没有窗口 | 打包版是无控制台程序，出错不弹命令行窗口；用 `python -m seqkit_gui` 跑源码版看报错，或检查 `dist\SeqKit-GUI\_internal\` 是否完整拷贝 |
| 换电脑后设置丢失 | 设置存在注册表里，不随目录迁移；重新指定 seqkit 路径即可 |
| 想在 macOS 上跑 | POSIX 启动脚本 `./run.sh` 与平台分支都已写好，但**没有任何人在真实 macOS 桌面上打开过这个窗口**，所以这是未验证路径；平台差异集中在 `seqkit_gui/core/paths.py` 与 `seqkit_gui/core/seqkit_locator.py`，打包需自行执行 PyInstaller，详见 [开发说明](development.md) |
| 去哪里拿现成的安装包 | 本仓库不发布任何安装包（不发 Release、不打 tag、不挂托管产物）。自己构建：`pyinstaller packaging/seqkit_gui.spec`，见 [开发说明](development.md) |

## 相关文档

- [安装与第一次运行](getting-started.md)
- [界面逐区说明](interface-guide.md)
- [详细使用手册](user-guide.md)
- [命令与参数指南](command-guide.md)
- [从源码运行与二次开发](development.md)
- 求助入口与安全漏洞报告方式见 [SUPPORT.md](../../SUPPORT.md) 与 [SECURITY.md](../../SECURITY.md)

英文文档见 `docs/en/`。
