# 从源码运行与二次开发

> 本文是**非官方 SeqKit GUI** 的简体中文文档，面向想读代码、改界面、重新生成参数表或打包分发的开发者。SeqKit GUI 是 [SeqKit](https://github.com/shenwei356/seqkit)（Wei Shen 开发的 MIT 许可序列工具包）的桌面图形前端；本项目与 SeqKit 项目无关，未获其认可，也不由其维护，不是 SeqKit 的官方图形界面。

## 1. 目录结构

```text
SeqKit-GUI/
├─ run.bat / run.sh          启动脚本（Windows / POSIX）
├─ requirements.txt          运行时依赖（PySide6），开发工具以注释形式列出
├─ pyproject.toml            项目元数据 + pytest 配置（无构建后端，源码直接运行）
├─ LICENSE                   本项目 MIT 许可
├─ THIRD-PARTY-LICENSES.md   第三方许可声明（含 SeqKit 的 MIT 原文）
├─ bin/                      seqkit 可执行文件的放置位置（被 .gitignore 忽略）
├─ seqkit_gui/
│  ├─ main.py / __main__.py  入口：加载偏好与参数表，创建主窗口
│  ├─ core/
│  │  ├─ paths.py            所有平台相关的路径判断集中在这里
│  │  ├─ spec.py             参数表数据模型（Flag / Inputs / Command / Group / Schema）
│  │  ├─ builder.py          表单状态 → 参数数组，以及运行前校验
│  │  ├─ runner.py           QProcess 异步执行、流式读取、输出落盘与截断
│  │  ├─ seqkit_locator.py   查找 seqkit 可执行文件、校验候选是否真的可执行、探测版本
│  │  └─ settings.py         QSettings 持久化的偏好
│  ├─ ui/
│  │  ├─ main_window.py      顶栏、菜单、命令树、运行流程
│  │  ├─ param_form.py       动态参数表单与各分区
│  │  ├─ widgets.py          文件列表与单行参数控件（各类型编辑器）
│  │  ├─ output_view.py      结果/错误/日志/命令行四标签与运行按钮
│  │  ├─ dialogs.py          设置对话框、关于对话框、分段选择控件
│  │  ├─ theme.py            浅色/深色调色板与 QSS
│  │  └─ i18n.py             语言目录与即时重翻译
│  ├─ data/commands.json     生成的参数表（提交进仓库，是命令与参数的权威来源）
│  ├─ i18n/{zh_CN,en_US}.json 界面文字表
│  └─ assets/                图标（`app.png` 窗口图标、`app.ico` Windows 构建图标、`app-32.png` 与 `app-1024.png` 源图）
├─ tools/
│  ├─ fetch_seqkit.py        下载官方 seqkit 发行包到 bin/（仅标准库）
│  ├─ extract_spec.py        把 spec-dumper 的原始输出规范化为 commands.json
│  ├─ spec-dumper/           Go 程序，遍历 seqkit 的 cobra 命令树
│  ├─ translations/          usage_zh.json（参数说明）、command_zh.json（命令与分组名）
│  └─ _build/                中间产物与开发期截图（被 .gitignore 忽略）
├─ tests/                    pytest 用例与示例数据
└─ docs/                     文档与截图
```

## 2. 从源码运行

```bat
cd <项目目录>
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python tools/fetch_seqkit.py
python -m seqkit_gui
```

- 入口是 `seqkit_gui/main.py` 的 `main()`：先设置 `QCoreApplication` 的组织/应用名（决定 `QSettings` 落点），加载偏好，读取 `data/commands.json`，再构建主窗口。参数表加载失败时弹框并返回退出码 `2`。
- `run.bat` / `run.sh` 只是带检查的外壳：确认 `python` 存在、提示 seqkit 缺失的解决办法，然后执行 `python -m seqkit_gui`；`run.sh` 支持 `PYTHON=... ./run.sh` 并透传额外参数。
- 无头环境（CI）下运行界面相关代码时设置 `QT_QPA_PLATFORM=offscreen`，`tests/conftest.py` 已经默认这么做了。

## 3. 参数表：唯一的命令/参数来源

`seqkit_gui/data/commands.json` 决定界面上能看到哪些命令、哪些参数、什么控件、什么约束。它由 seqkit 源码自动生成，不是手写的。

```text
seqkit 源码 ──(tools/spec-dumper, Go)──▶ tools/_build/spec_raw.json ──(tools/extract_spec.py)──▶ seqkit_gui/data/commands.json
```

### 3.1 重新生成

```bat
:: 需要 Go（spec-dumper 的 go.mod 声明 go 1.25.x）
python tools/extract_spec.py --build

:: 用本地解压的 seqkit 源码（改写 go.mod 的 replace 指令后构建）
python tools/extract_spec.py --build --seqkit-src D:\src\seqkit-2.14.0

:: 已有缓存的 spec_raw.json 时，只做规范化（不需要 Go）
python tools/extract_spec.py
```

产物写入 `seqkit_gui/data/commands.json`，同时把「未翻译的 usage 文本清单」写到 `tools/_build/translation_worklist.json`，终端会打印命令数、命令专属参数数、继承的全局参数数等信息。清单为空即代表所有 usage 都已翻译（当前就是空列表）。

Go 侧的现实约束：`extract_spec.py` 在拉起 dumper 前会用 `env.setdefault` 把 `GOPROXY` 设为 `https://goproxy.cn,https://proxy.golang.org,direct`，并设 `GOFLAGS=-mod=mod`——直连 `proxy.golang.org` 在部分网络环境下不可达，`goproxy.cn` 可达，所以这里以镜像为首位；你自己已经设了 `GOPROXY` 时脚本不会覆盖。`--seqkit-src` 走的是 `go mod edit -replace=github.com/shenwei356/seqkit/v2=<路径>`，该命令在 `tools/spec-dumper/` 目录下执行，因此相对路径要按那个目录来算；仓库里 `tools/spec-dumper/go.mod` 本身就带一条 `replace` 指向同级检出的 seqkit 源码，换机器时要么传 `--seqkit-src`，要么自己改这一行。`go.mod` 固定 `github.com/shenwei356/seqkit/v2 v2.14.0`、`cobra v1.10.2`、`pflag v1.0.10`。上游模块路径以 `seqkit-2.14.0/go.mod` 首行 `module github.com/shenwei356/seqkit/v2` 与 `main.go` 的 import 为准。

### 3.2 spec-dumper 负责什么

`tools/spec-dumper/main.go` 导入 `seqkit/cmd`，遍历 cobra 命令树，把每个命令的 `path / name / short / long / example / aliases / group / hidden` 和每个 flag 的 `name / shorthand / type / default / usage / hidden / required` 原样导出。因此参数名、短选项、类型、默认值不可能与 CLI 漂移。

### 3.3 extract_spec.py 额外补了什么

| 处理 | 说明 |
| --- | --- |
| `widget_for()` | 依据 flag 类型与名字决定控件：`bool`/`int`/`float`/`stringSlice`→`list`，`out-dir`、`tmp-dir`→`dir`，`--seq-type` 及带括号枚举的→`enum`，输入/输出文件名单→`in_file`/`out_file`，其余 `text` |
| `enum_options()` | 从 seqkit 自己的 usage 文本括号里提取 `a|b|c` 形式的候选值（2–16 个、且每项都像合法 token 才采纳） |
| `CONTRACTS` | 逐个命令登记运行前约束：`inputs`（`files`/`paths`/`none`、`min`/`max`、`allow_stdin`、`allow_compressed`、`accept`）、`requires_any`、`requires_all`、`forbid_pairs`、`conditional`、`notes`，并用 `evidence` 记录来自 seqkit 源码哪个文件哪几行 |
| 翻译注入 | 用 `tools/translations/usage_zh.json`（以英文 usage 为键）填 `usage_zh`；用 `command_zh.json` 填 `short_zh` 与分组 `title_zh`（键为 `group:<id>`） |

`CONTRACTS` 只覆盖 seqkit 各命令 `Run` 体里的硬性约束（例如 `grep` 需要 `-p` 或 `-f`、`sliding` 需要 `-W` 与 `-s`、`pair` 不接受位置参数），命令有变化或 seqkit 版本有变化时需同步补充，并保留 `evidence` 出处——`tests/test_schema.py` 会检查每个命令都有 `evidence`。

### 3.4 数据模型字段

| 类 | 关键字段 |
| --- | --- |
| `Flag` | `name`、`shorthand`、`type`、`default`、`usage`、`usage_zh`、`widget`、`options`、`required`、`hidden`；`cli` 恒为 `--name` |
| `Inputs` | `kind`（`files`/`paths`/`none`）、`min`、`max`、`allow_stdin`、`allow_compressed`、`accept` |
| `Command` | `path`、`name`、`group`、`short`/`short_zh`、`long`、`example`、`aliases`、`flags`、`global_flags`、`requires_any`、`requires_all`、`forbid_pairs`、`conditional`、`notes`、`evidence`、`runnable`、`hidden`；`all_flags` 做「同名去重、隐藏排除」 |
| `Group` | `id`、`title`、`title_zh` |
| `Schema` | `seqkit_version`、`groups`、`commands`；`usable`、`in_groups()`（命令树分组顺序，并为 seqkit 未声明分组的命令合成一个末尾节点，中文 `其他` / 英文 `Other`）、`flag_entries`（命令专属参数计数）、`global_flag_names` |

## 4. 参数组装与校验（core/builder.py）

- `build_argv()` 依次输出：子命令 token → `all_flags` 顺序（命令专属参数在前、未被同名专属参数遮蔽的全局参数在后）→ 附加参数（`shlex.split(posix=False)`）→ 终止符 `--` → 位置输入文件。只有存在输入文件时才会追加 `--`。
- 只有 `FlagState.enabled` 为真的行才会被输出；布尔行为真时只输出 `--flag`，默认即为真的布尔参数取消勾选时输出 `--flag=false`（当前参数表里没有任何参数声明默认值为真，所以这条分支实际不会触发）；列表类型按 `items` 逐个展开为重复的 `--flag 值`；值以 `-` 开头时输出 `--flag=值`。
- 从不构造 shell 字符串，因此含空格、引号、中文的路径不会改变命令语义。
- `validate()` 做的检查：`requires_all`、`conditional`、`requires_any`、`forbid_pairs`，外加输入文件数量与「不接受位置参数」。问题以结构化形式保存，再由 `Validation.messages(tr)` 经界面文案表渲染，因此弹窗在中文界面下是中文、英文界面下是英文；不通过时不会启动进程，并调用 `form.mark_missing()` 高亮缺失行。
- `BOUNDED_RUN_FLAGS`（`core/builder.py:49-51`）是这一层里唯一写在代码中的规则：`{"scat": ("find-only", "time-limit")}`。上游 `scat` 用 fsnotify 对给定目录建监听器并循环，没有退出条件就永不返回，所以 `validate()` 会在 `scat` 的两个退出参数都没勾选时往 `missing_any` 里追加这一组，让弹窗输出 `必须设置其中之一：--find-only / --time-limit`，子进程根本不会创建。`--wait-pid` 被有意排除在退出条件之外——它的默认值 `-1` 表示该计时器未启用，勾上复选框不能证明这次运行会结束。这条规则不在参数表里，也不渲染到注意事项分区（`ui/param_form.py` 的 `_build_notes()` 只读参数表的四类约束）。
- 修改这里的语义时，`tests/test_builder.py` 是主要防线。

## 5. 执行与输出（core/runner.py）

- `QProcess` 分离通道读取 stdout/stderr，增量 UTF-8 解码（错误字节替换），并用正则剥离 ANSI 颜色码。
- 每次运行创建临时文件 `seqkit-gui-XXXX.out`，stdout 全量写入；界面只投递前 N 行（`preview_line_limit`，最小值被夹到 200，默认 5000），超出部分计入 `dropped_lines` 并在结束时提示截断。
- `stop()` 先 `terminate()`，4 秒后仍在运行则 `kill()`；`RunResult` 汇总退出码、耗时、字节数、临时文件路径、启动错误等。
- 工作目录为空时回落到用户主目录；子进程继承系统环境变量。

## 6. 界面与文案约定

- 界面完全用代码构建，没有 `.ui` 文件；配色集中在 `ui/theme.py` 的两套调色板 + QSS，添加控件时复用其中的对象名（`Card`、`Badge`、`Hint`、`FlagUsage`、`OutputView`、`SearchBox`、`RunButton` 等）。
- 所有可见文字走 `catalog.tr("English key")`：键就是英文原文，`i18n/zh_CN.json` 提供中文，缺键回退 `en_US.json`，再回退键本身。添加文案时三个地方都要动：代码里的 `tr()`、`zh_CN.json`，以及（抽象键名才需要）`en_US.json`。
- `core/` 不依赖 `ui/`，`builder.py` 是纯逻辑，便于在无界面情况下测试。
- `ui/i18n.py` 的 `Catalog` 持有当前语言并提供 `tr()` 回退链（当前语言 → 英文 → 键本身），同时暴露 `language_changed` 信号；实际的界面重翻译由 `MainWindow._set_language()` 驱动，它会重建命令树与表单并回填输入文件与工作目录。

### 6.1 扩展点

| 想做的事 | 改哪里 |
| --- | --- |
| 支持另一个平台 | `core/paths.py`（`executable_names()`、`bundled_dir()`、`docs_dir()`）与 `core/seqkit_locator.py` 的额外查找前缀；`tools/fetch_seqkit.py` 的 `SUPPORTED_SYSTEMS`；`run.sh` 本身就是 POSIX 的 |
| 添加一门语言 | `ui/i18n.py` 的 `LANGUAGES`（以及 `FALLBACK_LANGUAGE`）、新建 `seqkit_gui/i18n/<code>.json`，还有 `ui/main_window.py` 与 `ui/dialogs.py` 里用 `list(LANGUAGES.items())` 构造的 `_Choice`；缺译的键回退 `en_US.json`，再回退键本身 |
| 添加一套主题 | `ui/theme.py` 里一份字段完全相同的 `Palette`，注册进 `PALETTES`，顶栏与设置对话框各加一枚 chip |
| 改变某个参数的渲染方式 | `tools/extract_spec.py` 的 `widget_for()` 与那几个名字集合，然后重新生成参数表 |
| 添加一种编辑器 | `ui/widgets.py` 里 `EditorBase` 的子类 + `_make_editor()` 的一个分支；必须实现 `text()`、`items()`、`set_text()` 并发出 `value_changed` |
| 添加一条运行前规则 | `tools/extract_spec.py` 的 `CONTRACTS`，然后重新生成；只要规则落在这几类里（`requires_any` / `requires_all` / `conditional` / `forbid_pairs` / `inputs`），`builder.validate()` 不用动。落不进参数表的规则（永不返回的命令）写进 `core/builder.py` 的 `BOUNDED_RUN_FLAGS`，它复用 `requires_any` 的上报路径 |

## 7. 测试

```bat
python -m pytest tests -q
python -m pytest tests -q --collect-only -p no:cacheprovider
```

用例数量随功能增删而变化，文档里不写死具体数字，以 `--collect-only` 的输出为准。`pyproject.toml` 里 `testpaths = ["tests"]`。`tests/conftest.py` 强制 `QT_QPA_PLATFORM=offscreen`，提供 `schema`、`qapp`、`seqkit_binary`（找不到可执行文件时自动 skip）、`sample_fasta`、`sample_fasta2`、`sample_fastq`、`root` 等会话级 fixture，并注册 `gui`/`seqkit`/`slow`/`screenshot`/`launcher` 五个标记；截图与启动脚本用例默认跳过，需显式加 `--with-screenshots` / `--with-launchers`。

| 文件 | 覆盖内容 |
| --- | --- |
| `tests/test_schema.py` | 参数表与真实 CLI 的交叉校验：命令集合与 `seqkit __complete` 一致、每个命令 `--help` 可达且短选项出现、抽查 flag 名、版本等于 2.14.0、11 个全局参数覆盖每个命令、widget 取值合法、所有 usage 都有中文且中文不是英文原文、每个命令都有源码出处 `evidence`、`commands.json` 已随仓库提交 |
| `tests/test_compat_commands.py` | 文档承诺与真实二进制的一致性：README 里那张分组表逐项核对参数表、每条命令的最小 argv 结构、二进制是否宣告出全部命令、真实二进制是否接受全部命令的最小参数组合 |
| `tests/test_builder.py` | 参数组装与校验：命令 token 顺序、位置参数排在 `--` 之后、布尔只在勾选时输出、列表展开为重复选项、负值的 `=` 形式、全局参数、附加参数切分、含空格路径、`grep`/`sliding`/`pair`/数量/互斥等各条校验规则，以及有界运行的拒绝 |
| `tests/test_runner.py` | 真实 seqkit 端到端：版本探测、`stats` 输出、`grep` 过滤、`--out-file` 落盘、stderr 捕获、不给输入文件时的行为、取消长任务 |
| `tests/test_gui.py` | 界面构建：每个命令都能建表单、参数行有说明、勾选影响请求、语言/主题切换、命令与参数搜索、输入文件在重建后保留、seqkit 检测、参数不完整时拒绝启动、从窗口跑完整一次、设置与关于对话框、可选的文档截图用例 |
| `tests/test_i18n.py` | 每个 `tr()` 用到的键都有中文、英文回退键存在、中文目录确实是中文、即时切换、未知键回退、格式化容错、主题两套齐备且色板字段一致 |
| `tests/test_locator.py` | seqkit 缺失、损坏或版本不对时的行为、配置路径优先、`probe_version` 对非可执行文件返回空、缺少 seqkit 时界面提示并拒绝运行、`QSettings` 往返、最近文件去重与上限、界面显示的参数统计口径、`stats` 遮蔽同名全局参数、`executable_names()` 的平台差异 |
| `tests/test_security_locator.py` | 去哪里找 seqkit 是信任决策而非便利：当前工作目录与相对 `PATH` 项永远不会作为自动发现的结果被接受 |
| `tests/test_security_paths.py` | Windows 路径必须以用户想表达的那一个参数到达 seqkit：引号、反斜杠、控制字符、超长路径 |
| `tests/test_security_runner.py` | `SeqkitRunner` 的拒绝分支通过 `finished` 上报，不抛异常 |
| `tests/test_security_stdin.py` | 界面启动的任何子进程都不该无限等待一个永远不会到达的输入；参数列表不被重新解析 |
| `tests/test_reliability_encoding.py` | 两个输出通道在字节层面的表现：跨块的多字节序列、非法 UTF-8、ANSI 剥离 |
| `tests/test_reliability_lifecycle.py` | 子进程仍在运行时窗口的行为，含运行中关闭 |
| `tests/test_reliability_output_scale.py` | 输出远大于一个文本控件时：预览上限、丢弃行数记账、完整落盘文件 |
| `tests/test_reliability_paths.py` | Windows 用户真实会有的路径：中文、空格、引号、短横线开头、超长 |
| `tests/test_quality_boundaries.py` | 让这个应用保持「seqkit 的外壳」的架构边界规则 |
| `tests/test_quality_structure.py` | 应用代码的结构质量规则 |
| `tests/test_quality_signals.py` | 顶栏分段选择控件的信号接线 |
| `tests/test_quality_i18n.py` | 两份 JSON 语言表的完整性 |
| `tests/test_release_consistency.py` | 发布期不变量：`__version__` 与 `pyproject` 一致、recipe 不写死版本、产物名与发行名一致、以桩执行 spec 检查收集到的资源目录与不包含 `bin/`、`SEQKIT_SUPPORTED_VERSION` 在各处一致、仓库不跟踪 seqkit 可执行文件、文档里的版本号不与代码冲突、workflow 语法与只读权限、CI 矩阵与声明的支持范围一致 |
| `tests/test_fetch_seqkit.py` | 不依赖网络的下载器测试：各平台资源名（Windows 为 `seqkit_windows_amd64.exe.tar.gz`）、URL 形式、架构别名、归档内可执行文件的识别与歧义拒绝、`sanity_check` 拒绝 HTML/过小文件/错误平台镜像、原子写入与 `--force` 保护 |

依赖 seqkit 的用例在找不到可执行文件时会自动 skip（`tests/conftest.py` 的 `seqkit_binary`），所以请先按第 2 节准备 `bin/`。

### 7.1 更新截图

```bat
set SEQKIT_GUI_SHOOT=1
python -m pytest tests/test_gui.py -q --with-screenshots
```

两道开关都要满足：`--with-screenshots` 让 conftest 放行截图用例，`SEQKIT_GUI_SHOOT=1` 让用例本身真正渲染；两者缺一该用例就 skip。它把 `light-zh.png`、`dark-en.png` 两张写到开发期目录 `tools/_build/screenshots/`（被 `.gitignore` 忽略），确认无误后再挑选、复制到 `docs/screenshots/`。`docs/screenshots/` 下的 5 张成品是从真实窗口逐张手工截取的（grep → 运行 → stats → `seq`，并切换语言与主题），仓库里没有任何脚本会自动重生成它们；这些图里含有截图那台机器的绝对路径与用户名，重新截取要先准备一个净化过的示例目录（不含真实用户名与项目路径），再把生成的文件挑进 `docs/screenshots/`。

## 8. 打包

```bat
python -m pip install pyinstaller
pyinstaller packaging/seqkit_gui.spec
```

- 产物为 **onedir** 目录 `dist\SeqKit-GUI\`，主程序 `SeqKit-GUI.exe`（`console=False`，无控制台窗口）；同时生成暂存目录 `build\`，两者都被忽略。
- 选择 onedir 的原因：PySide6 以 LGPL 发布，需要让用户能替换 Qt 库；onedir 把 `Qt6*.dll` 留在 `SeqKit-GUI\_internal\` 明面上，也避免 onefile 每次启动自解压的延迟。
- 需要单个自包含 exe（U 盘、单文件分发的自用场景）时，用同一份配方的 onefile 模式：`set SEQKIT_GUI_BUNDLE=onefile&& pyinstaller packaging/seqkit_gui.spec`，产物为 `dist\SeqKit-GUI.exe`。入口、资源、许可文本、GPL 模块过滤与图标校验和 onedir 完全一致，差别只在封装方式；代价是 Qt 库被嵌入、用户不可替换（对外分发请回到 onedir），首次启动要解压到临时目录，单个大文件也更容易被杀毒软件慢速扫描。此模式下 seqkit 放在 exe 旁的 `bin\` 里（`dist\bin\seqkit.exe`），查找顺序不变。
- 随包携带的资源目录为 `seqkit_gui/data`（参数表）、`seqkit_gui/i18n`（界面文字）、`seqkit_gui/assets`（图标），在包内保持同样的相对路径 `SeqKit-GUI\_internal\seqkit_gui\<目录>`，好让 `core/paths.py` 用同一套逻辑定位。三者待遇不同：`data` 是必需项，缺失或为空时 recipe 直接终止构建并提示先运行 `python tools/extract_spec.py --build`；`i18n` 与 `assets` 是可选项，缺失时打印一行提示后跳过，因为程序会回退到键名文字与默认图标。图标同样可选：`icon_path()` 在 Windows 取 `app.ico`、在 macOS 取 `app.icns`，文件不存在时不传图标（macOS 上传 `.ico` 会让 PyInstaller 尝试用 Pillow 转换并因缺少 Pillow 而整场构建失败）。构建还会拒绝任何被收集进来的 seqkit 可执行文件，命中即终止。
- **SeqKit 不在打包范围内**：构建完成后需要手动把可执行文件放到 `dist\SeqKit-GUI\bin\`：

```text
dist/SeqKit-GUI/SeqKit-GUI.exe
dist/SeqKit-GUI/bin/seqkit.exe      <- 自己放
```

这正是查找顺序里的第二站（第一站是设置中指定的路径，第三站是 PATH）。

界面图标（`app-1024.png`、`app.png`、`app-32.png`、`app.ico`）是代码画出来的，不是外部素材：`python tools/make_logo.py` 用 QPainter 按参数化几何逐尺寸重绘全套（黑白极简磁贴 + 抽象 DNA 扭梯，小尺寸自动省略部分横档），改配色或形状后重跑一次即可，无需任何图像编辑器。

## 9. 平台差异与 macOS 迁移

平台相关判断被集中到最小范围，改 macOS/Linux 时不需要动 UI 与 runner：

| 位置 | 内容 |
| --- | --- |
| `core/paths.py` | `executable_names()`（Windows 返回 `seqkit.exe/.cmd/.bat/seqkit`，其他系统只有 `seqkit`）、`bundled_dir()`、`package_dir()`/`project_root()`/`docs_dir()` 对 PyInstaller 冻结状态的处理 |
| `core/seqkit_locator.py` | 查找顺序与 macOS 的 `/opt/homebrew/bin`、`/usr/local/bin`；非 Windows 用 `os.access(..., X_OK)` 判断可执行 |
| `tools/fetch_seqkit.py` | 按平台选择官方资源名（Windows 为 `seqkit_windows_amd64.exe.tar.gz`，归档内取 `seqkit.exe`；Darwin/Linux 为 `.tar.gz` 取 `seqkit`），下载后先按上游 `.md5.txt` 校验再原子写入 `bin/`，已存在时需 `--force` 才覆盖；`--list` 可查看全部可下载资源名 |
| `run.sh` | POSIX 启动脚本，含 Python 探测与依赖/seqkit 缺失提示 |

代码里没有使用任何 Windows 专用 API：GUI 依赖 PySide6，其余为标准库；文件路径统一走 `pathlib`。macOS 打包时同样使用 `pyinstaller packaging/seqkit_gui.spec`（`app.ico` 缺失时自动回退默认图标，需要 `.icns` 时自行替换）。

## 10. 许可与「非官方」声明

- 本项目采用 MIT 许可（`LICENSE`）。
- SeqKit 是 Wei Shen 的 MIT 项目，其许可证原文与署名保留在 `THIRD-PARTY-LICENSES.md`；SeqKit 可执行文件不随仓库分发、不由本项目重新分发。
- 因此 `README` 与 `docs/` 下的文档都必须明确写出「非官方」：本仓库只是 SeqKit 命令行程序的图形外壳，自身不实现任何序列处理逻辑。每篇文档在开头一行说明即可，关于对话框里的声明来自 `i18n` 的 `unofficial_disclaimer` 与 `seqkit_attribution` 两个键。
- 不要在仓库里提交 `bin/`、`build/`、`dist/`、`tools/_build/` 下的内容（`.gitignore` 已覆盖）；`seqkit_gui/data/commands.json` 是必须提交的生成产物。

## 相关文档

- [安装与第一次运行](getting-started.md)
- [界面逐区说明](interface-guide.md)
- [详细使用手册](user-guide.md)
- [命令与参数指南](command-guide.md)
- [常见问题与故障排查](faq.md)

英文文档见 `docs/en/`。
