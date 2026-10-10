# 获取帮助 / Getting help

[中文](#获取帮助) · [English](#getting-help-english)

---

## 获取帮助

### 先说清楚：这是非官方项目

SeqKit GUI 是**非官方**的 SeqKit 桌面图形界面，与 SeqKit 作者无关，也没有得到上游的认可或支持。
它自己**不做任何序列处理**：只收集参数、组装命令行，然后调用你机器上已有的官方 `seqkit` 可执行文件，
把它的标准输出与标准错误显示出来。同一条命令在终端里跑，结果与从界面跑是完全一致的。

由此决定了两件事：

1. **seqkit 本身怎么用、某个参数是什么意思、结果为什么是这样** —— 这些是上游的问题，请查上游文档
   <http://bioinf.shenwei.me/seqkit/>，或到 <https://github.com/shenwei356/seqkit/issues> 提问。
   在这里问，我们大概率也只能把同一个链接发给你。
2. **本项目不重新分发 seqkit。** 仓库里没有 `seqkit.exe`（`bin/` 被 `.gitignore` 忽略），
   Releases 里的打包版里也没有。你需要自己准备 seqkit：`python tools/fetch_seqkit.py` 会把官方 2.14.0
   发布版下载到 `bin/`，或者手动放进 `bin/`、留在 PATH 里、或在「工具 → 设置」（`Ctrl+,`）里指定路径。
   "下载的安装包里怎么没有 seqkit" 不是缺陷。

### 获取帮助的渠道

**唯一的公开渠道是 GitHub issue。** 提问前请先按下面的文档自查——这一步真的能省下几天的来回追问。

| 你的情况 | 去哪里 |
| --- | --- |
| 先看文档，自己排查 | [docs/zh/faq.md](docs/zh/faq.md) —— 第 1 节就是"排查顺序速查" |
| 装不起来、找不到 seqkit、第一次运行 | [docs/zh/getting-started.md](docs/zh/getting-started.md) |
| 想知道界面某个区域、按钮、快捷键做什么 | [docs/zh/interface-guide.md](docs/zh/interface-guide.md) |
| 想知道某个命令的某个参数在界面里怎么填 | [docs/zh/command-guide.md](docs/zh/command-guide.md) |
| 想改代码、想重新生成参数表、想提 PR | [docs/zh/development.md](docs/zh/development.md) 与 [CONTRIBUTING.md](CONTRIBUTING.md) |
| 确认是界面的缺陷（启动失败、参数拼装不对、显示异常） | 新建 issue → 选 **Bug 报告 / Bug report** 模板 |
| 想要新功能、想改进界面 | 新建 issue → 选 **功能请求 / Feature request** 模板 |
| 界面参数和你本机 seqkit 的 `--help` 对不上 | 新建 issue → 选 **参数表不一致 / Spec mismatch** 模板 |
| 疑似安全漏洞 | **不要开 issue**，见 [SECURITY.md](SECURITY.md) |
| 行为准则相关投诉 | 见 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) 里的联系方式 |

英文界面 / 英文使用者对应 `docs/en/` 下的同五篇：
[getting-started](docs/en/getting-started.md) · [interface-guide](docs/en/interface-guide.md) ·
[command-guide](docs/en/command-guide.md) · [faq](docs/en/faq.md) · [development](docs/en/development.md)。
中文贡献指南见 [CONTRIBUTING.md](CONTRIBUTING.md)，English contributors see
[CONTRIBUTING.en.md](CONTRIBUTING.en.md)。

**空白 issue 已关闭**（`.github/ISSUE_TEMPLATE/config.yml` 里 `blank_issues_enabled: false`）。
不是设置障碍：这个项目的每一个问题都要先知道操作系统、Python / PySide6 / seqkit 三个版本，
以及界面「命令行」标签里实际拼出来的那一整行，否则没人能给出有用的回答。模板会一步步问你要这些。

### 提问时请带上这些

Bug 模板会逐项引导，这里先列出来，你可以一次备齐：

- 操作系统与版本（Windows 按 `Win+R` 输入 `winver`）；
- `python -V` 的输出；
- `python -c "import PySide6; print(PySide6.__version__)"` 的输出；
- `seqkit version` 的完整输出；
- 界面底部状态栏**左侧**那行 `<seqkit 完整路径>  (configured/bundled/path)`；
- 输出面板「命令行」标签里的原文（`Ctrl+Shift+C` 复制）。这一行最关键——
  它是界面真正交给 seqkit 的东西，有它就能立刻区分"界面拼错了"和"seqkit 本来就这样"。

> ⚠️ 命令行和路径里会包含你的用户名以及数据文件所在的目录结构。是否删减由你决定；
> 若删减，请保留结构（例如 `C:\Users\<you>\data\sample.fastq`），因为路径里的空格与中文本身就是常见故障源。
> 序列内容请一律脱敏：给我们样例的**形状**（条数、格式、ID 风格），不要给真实数据。

### 响应时间：不做任何保证

本项目由一个人用业余时间维护，没有支持团队、没有工单系统、没有付费支持渠道。

- **不承诺任何响应时间，也不承诺每个 issue 都会被处理。**
- 目标是尽量在几天内对新建的 issue 做出第一次回应，但繁忙期可能几周；如果超过一个月没有任何回复，
  你可以直接 ping 一句，也可以自行提 PR——未响应的 issue 不等于拒绝。
- 我们可能会直接关闭下列 issue 并简短说明理由：只写"不好用"而没有环境与复现信息的；
  实际是 seqkit 本体用法问题的；与参数表版本不一致但走错模板的；重复的。
- **不接受付费支持请求、不接受"帮忙跑个分析"之类的委托**。这里只有开源软件本身。

### 支持范围（明确边界）

| 会帮 | 不会帮 |
| --- | --- |
| 界面装不起来、启动报错、找不到 seqkit | seqkit 命令本身怎么用、参数生物学含义 |
| 参数显示 / 默认值 / 必填判定 / 命令行拼装的问题 | 你的分析结论对不对、数据该用什么参数处理 |
| 运行、停止、结果与日志显示、编码、大文件截断 | 数据恢复——请务必先备份再对真实数据动手 |
| 语言、主题、字号、布局问题 | macOS / Linux 上的问题定位——界面只在 Windows x64 上实测过，其他平台按能力尽力，不承诺 |
| 打包版（`dist/SeqKit-GUI/`）的启动与资源缺失 | 代码签名、SmartScreen 提示的根除、杀毒软件误报的正式豁免 |
| 参数表如何重新生成（需要 Go 与 seqkit 源码） | 替你升级/维护你机器上的 seqkit |

### 其他渠道的现状

- **未启用 GitHub Discussions。** 是否需要启用由维护者在网页端 Settings 决定；
  在启用之前，issue 是唯一入口（`.github/ISSUE_TEMPLATE/config.yml` 里预留了带占位符的注释块，
  启用后再填仓库地址）。
- **没有邮件支持、没有即时聊天群、没有论坛。** 文档里出现的第三方链接只有上游 seqkit 的仓库与文档页。
- **本应用不联网。** 运行期间不发起任何网络请求，没有遥测、没有自动更新、没有联网版本检查；
  唯一的对外动作是你手动点「帮助 → SeqKit 官方文档」时由系统浏览器打开上游文档页。
  因此我们也**不知道**你装了什么版本、有多少人用——只有你主动开的 issue 才是反馈来源。
  如果你觉得某个功能重要，请说出来，不要沉默。

---

## Getting help (English)

### First: this is an unofficial project

SeqKit GUI is an **unofficial** desktop front end for SeqKit. It is not affiliated with or endorsed by
the SeqKit author, and it performs **no sequence computation**: it collects arguments, assembles a command
line, runs the official `seqkit` executable already on your machine, and shows that program's stdout and
stderr. The same command run in a terminal produces the same result.

That determines two things:

1. **How to use seqkit, what a flag means, why a result looks like that** are upstream questions. Read
   <http://bioinf.shenwei.me/seqkit/> or ask at <https://github.com/shenwei356/seqkit/issues>. Asking here
   usually earns you a link to the same place.
2. **This project does not redistribute seqkit.** There is no `seqkit.exe` in the repository (`bin/` is
   git-ignored) and none in the packaged build under Releases. Bring your own: `python tools/fetch_seqkit.py`
   downloads the official 2.14.0 release into `bin/`, or place it in `bin/`, leave it on PATH, or point
   Tools → Settings (`Ctrl+,`) at it. "The download has no seqkit inside" is intended behaviour, not a defect.

### Where to get help

**GitHub issues are the only public channel.** Check the documentation first — it genuinely saves days of
back-and-forth.

| Your situation | Where to go |
| --- | --- |
| Self-service troubleshooting | [docs/en/faq.md](docs/en/faq.md) — section 1 is the triage order |
| Installation, seqkit not found, first run | [docs/en/getting-started.md](docs/en/getting-started.md) |
| What a region, button or shortcut does | [docs/en/interface-guide.md](docs/en/interface-guide.md) |
| How to fill a specific flag of a specific command | [docs/en/command-guide.md](docs/en/command-guide.md) |
| Hacking the code, regenerating the parameter table, opening a PR | [docs/en/development.md](docs/en/development.md) and [CONTRIBUTING.en.md](CONTRIBUTING.en.md) |
| Confirmed defect in the interface | New issue → **Bug report** template |
| A new or improved interface capability | New issue → **Feature request** template |
| The GUI's flags do not match your seqkit's `--help` | New issue → **Spec mismatch** template |
| A suspected vulnerability | **Do not open an issue** — see [SECURITY.md](SECURITY.md) |
| A code-of-conduct report | Contact details in [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) |

Chinese readers have the same five documents under `docs/zh/`:
[getting-started](docs/zh/getting-started.md) · [interface-guide](docs/zh/interface-guide.md) ·
[command-guide](docs/zh/command-guide.md) · [faq](docs/zh/faq.md) · [development](docs/zh/development.md).
Contributor notes: [CONTRIBUTING.en.md](CONTRIBUTING.en.md) / [CONTRIBUTING.md](CONTRIBUTING.md).

**Blank issues are disabled** (`blank_issues_enabled: false` in
`.github/ISSUE_TEMPLATE/config.yml`). This is not a barrier: every question about this project needs the
operating system, the Python / PySide6 / seqkit versions, and the exact line the interface assembled. Without
them nobody can give a useful answer. The templates ask for each item step by step.

### What to include

The bug template walks you through it; gather these in advance:

- operating system and version (Windows: `Win+R` → `winver`);
- output of `python -V`;
- output of `python -c "import PySide6; print(PySide6.__version__)"`;
- full output of `seqkit version`;
- the bottom-left status bar line `<full seqkit path>  (configured/bundled/path)`;
- the exact contents of the **"Command"** tab (`Ctrl+Shift+C` copies it). This is the single most important
  item: it is what the interface actually handed to seqkit, and it instantly separates "the GUI assembled it
  wrong" from "seqkit behaves like this on its own".

> ⚠️ The command line and paths contain your username and the shape of your data directories. Redacting is
> your call; if you do, keep the structure (e.g. `C:\Users\<you>\data\sample.fastq`) — spaces and non-ASCII
> characters in paths are themselves a common failure source. Always sanitize sequence content: give us the
> **shape** (count, format, ID style), never real data.

### Response times: no promises

One person maintains this project in spare time. There is no support team, no ticketing system, no paid channel.

- **No response time is guaranteed, and no issue is guaranteed to be actioned.**
- The aim is a first reply within a few days, but busy periods stretch that to weeks. If a month passes with
  no reply, ping the issue or open a pull request — silence is not a rejection.
- Issues may be closed with a short reason: "does not work" with no environment or reproduction info;
  questions about seqkit usage; a parameter-table mismatch filed with the wrong template; duplicates.
- **No paid support and no "please run my analysis" requests.** Only the software itself is offered.

### Support boundary

| Covered | Not covered |
| --- | --- |
| Installation, startup errors, seqkit not found | How to use seqkit, the biological meaning of a flag |
| Flag display, defaults, required checks, command assembly | Whether your analysis conclusion is right |
| Running, stopping, result/error/log views, encoding, large output | Data recovery — back up before running anything on real data |
| Language, theme, font size, layout | Diagnosing macOS / Linux — the interface is only tested on Windows x64; best effort, no promise |
| The packaged build in `dist/SeqKit-GUI/`: startup and missing resources | Code signing, eliminating SmartScreen warnings, getting antivirus exemptions |
| How the parameter table is regenerated (needs Go and seqkit source) | Maintaining or upgrading the seqkit on your machine |

### Status of other channels

- **GitHub Discussions is not enabled.** Whether to enable it is a web-side decision in the repository's
  Settings. Until then, issues are the only entry point; `.github/ISSUE_TEMPLATE/config.yml` keeps a
  commented-out block with a placeholder ready for it.
- **There is no email support, no chat group, no forum.** The only third-party links in these documents are
  the upstream seqkit repository and its documentation site.
- **The application does not use the network.** No requests while running, no telemetry, no auto-update, no
  online version check; the only outbound action is your own click on Help → "SeqKit official documentation",
  which hands a URL to your system browser. Consequently we do **not** know which version you installed or
  how many people use it — an issue you choose to open is the only feedback we get. If a capability matters to
  you, say so instead of staying quiet.
