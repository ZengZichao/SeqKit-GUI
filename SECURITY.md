# 安全策略 / Security Policy

[中文](#安全策略) · [English](#security-policy-english)

---

## 安全策略

SeqKit GUI 是一个**非官方**项目：它不做任何序列计算，只收集参数、组装命令行，然后用 `QProcess`
调用你机器上已有的官方 `seqkit` 可执行文件。本策略描述的就是这个薄层，以及它周围真实的信任边界。

### 哪些属于本策略范围

| 属于范围 | 不属于范围 |
| --- | --- |
| `seqkit_gui/` 的 Python 代码（参数表读取、命令行组装、进程调用、偏好持久化） | **seqkit 本体**的解析、算法与崩溃问题 → 上游 <https://github.com/shenwei356/seqkit> |
| `tools/` 与 `packaging/` 中的生成、下载、打包脚本 | PySide6 / Qt 自身的问题 → Qt 官方自行受理，已知清单见 <https://wiki.qt.io/List_of_known_vulnerabilities_in_Qt_products> |
| 界面把哪些内容写到磁盘、写到哪里 | Python 解释器、你的操作系统、你的输入数据本身 |
| GitHub 仓库内容与文档 | 你本机 PATH 里那个 seqkit 是不是真的官方版本 |

一个简单判断法：**把本项目删掉、只在终端里敲同一条命令行，问题还在吗？** 还在的，是上游或环境问题；
只有从界面走才出现的，才是这里要报的。

### 如何报告

**请不要开公开 issue，也不要在已有 issue 下留言。**

- 邮箱：`301673815+ZengZichao@users.noreply.github.com`（GitHub 会把发往该 noreply 地址的邮件转交维护者；若维护者启用了 GitHub 的私有漏洞报告功能，也可直接在仓库页面走 **Report a vulnerability**）。
- 邮件标题写 `SeqKit GUI security`，正文尽量包含：
  1. 版本号：`python -c "import seqkit_gui; print(seqkit_gui.__version__)"`，以及是源码运行还是 `dist/SeqKit-GUI/` 打包版；
  2. 操作系统与架构（Windows `winver` 的输出口述即可）；
  3. 你的 seqkit 版本（`seqkit version`）与它被找到的方式（界面底部状态栏左侧显示 `<路径>  (configured/bundled/path)`）；
  4. 复现步骤 + 界面上「命令行」标签的原文（`Ctrl+Shift+C` 复制）；
  5. 影响面：需要受害者做什么（打开某个文件 / 点某条命令 / 只是启动程序）。
- 涉及真实数据时请**先脱敏**：序列 ID、样本名、文件路径都可能带个人信息或项目信息，
  用假的样例名描述即可，我们需要的是结构而不是内容。
- 若 GitHub 仓库启用了 "Report a vulnerability"（Security → Advisories），也会作为一条入口列在这里；
  该开关属于网页端设置，尚未确认。**在启用之前，邮箱是唯一渠道。**

### 响应时限（现实版本）

本项目由一个人用业余时间维护，没有安全团队、没有资金、没有漏洞赏金。因此这里承诺的是**沟通节奏**而不是 SLA：

- 目标是 **7 个自然日内**回复确认收到；**14 个自然日内**给出初步判断（是否成立、属于哪一侧）。
- 这**不是**保证。假期、本职工作、生病都可能让上面两个数字翻倍。如果你 3 周内没有得到任何回复，
  欢迎再发一封，或改用公开渠道并直接说明"这是一封安全报告的跟进"。
- 修复节奏取决于问题在哪一侧：属于本项目的，会在确认后的下一个版本里修；
  属于 seqkit 本体的，只能转给上游，我们无法代为承诺时间。
- 我们不会提供 CVE 编号、不会主持多方协调披露，也不会签发安全公告。
  需要正式通告时，我们会在确认修复后写一篇说明性文字，如实描述影响范围。

### 在披露完成前

- 请给我们 90 天的私下处理窗口。90 天后你完全可以公开细节，我们不主张任何权利。
- 期间我们不会把你的报告、邮箱或样例数据转给第三方；上游转交时只转技术细节，不带你的联系方式，除非你同意。

### 这些一般不算漏洞（先自查）

写下来是为了省下彼此的时间，这些都是当前设计的既定属性：

1. **seqkit 以你的账号权限执行任何命令。** 这是这个应用的工作原理：它调用的可执行文件由你选择。
   如果有人能改动"工具 → 设置"里的路径、或改动 `bin/` 目录、或改动你的 PATH，那他已经拿到了在你的机器上执行代码的能力，
   不需要借助本应用。
2. **程序不会被 shell 解释。** `core/runner.py` 用 `setProgram()` + `setArguments()` 传参数向量，
   不走 `QProcess.start(command)`，也不拼 shell 字符串。因此"在文件名里塞 `;` 或 `&&`"这类经典注入在这里没有落点。
   如果你找到了绕过这一点、让参数被二次解释的路径，那**是**漏洞，请报。
3. **可执行文件查找会拒绝当前工作目录。** `core/seqkit_locator.py` 明确跳过位于程序启动目录的候选
   （状态栏里会留下 `... is in the current working directory, which is never trusted`），
   Windows 上也会拒绝 `seqkit.cmd` / `seqkit.bat` 这类脚本后缀。传统 DLL 植入 / 二进制种植问题请优先按这两条自查。
4. **偏好设置存在用户级配置里**（`QSettings("seqkit-gui", "SeqKit GUI")`，Windows 上是当前用户的注册表项），
   其中 `files/recent` 会保存最近 20 条输入文件路径。它只影响当前用户，不是凭据存储。
   "最近文件列表泄露了我在做什么"属于隐私话题，可以谈，但按"需要加固"而不是"存在漏洞"处理。
5. **标准输出会完整落到用户临时目录**（`tempfile.mkstemp(prefix="seqkit-gui-", suffix=".out")`），
   用于支持大结果与"保存结果"。这个文件在退出后不会被安全擦除。多用户共享的机器上，你的输出对其他能读你临时目录的人可见——
   这是既有限制，加固建议见下面"我们不做什么"。
6. **界面显示的参数表描述的是 seqkit 2.14.0。** 参数和你的版本对不上属于数据不一致，走
   [参数表不一致模板](.github/ISSUE_TEMPLATE/spec_mismatch.yml)，不是安全事件。
7. **仓库不分发 seqkit。** `bin/` 被 `.gitignore` 忽略，任何构建产物里都不含 seqkit 可执行文件
   （`packaging/seqkit_gui.spec` 与 `release-build.yml` 各有独立检查强制这一点）。
   "从 Releases 下的包里没有 seqkit，是否被篡改"不是漏洞。

### 我们不做什么

- 不做遥测、不做自动更新、不做联网版本检查。应用运行期间不发起任何网络请求；
  唯一的对外动作是你手动点"帮助 → SeqKit 官方文档"时由系统浏览器打开上游文档页。
  这条边界是产品立场，任何"加个检查更新"的提议都会被拒。
- 不提供代码签名、不提供供应链 SBOM 承诺、不宣称支持任何生产级安全认证。
- 无法为 macOS / Linux 的正确性背书：界面只在 Windows x64 上实测过，其他平台上的问题按普通缺陷处理。

如果你不确定某件事算不算安全问题，**直接发邮件问**，问错了没人会怪你。

---

## Security Policy (English)

SeqKit GUI is an **unofficial** project. It performs no sequence computation: it collects arguments,
assembles a command line, and runs the official `seqkit` executable that is already on your machine.
This policy covers that thin shell and the real trust boundaries around it.

### What is in scope

| In scope | Out of scope |
| --- | --- |
| Python code in `seqkit_gui/` (schema loading, argument assembly, process invocation, preference storage) | **seqkit itself** -- parsing, algorithms, crashes → <https://github.com/shenwei356/seqkit> |
| Generation, download and packaging scripts in `tools/` and `packaging/` | PySide6 / Qt themselves -- handled by Qt, published list: <https://wiki.qt.io/List_of_known_vulnerabilities_in_Qt_products> |
| What the interface writes to disk and where | The Python interpreter, your OS, your input data |
| Repository contents and documentation | Whether the `seqkit` on your PATH is really the official binary |

Rule of thumb: *if you deleted this project and typed the same command line in a terminal, would the
problem still be there?* If yes, it is upstream or environmental. If it only happens through the
interface, it belongs here.

### How to report

**Do not open a public issue and do not reply on an existing one.**

- Email: `301673815+ZengZichao@users.noreply.github.com` (GitHub forwards mail sent to this noreply address to the maintainer; if private vulnerability reporting is enabled on the repository, **Report a vulnerability** on the repository page works too).
- Subject: `SeqKit GUI security`. Please include:
  1. version (`python -c "import seqkit_gui; print(seqkit_gui.__version__)"`) and whether you run from source or from `dist/SeqKit-GUI/`;
  2. operating system and architecture;
  3. your seqkit version (`seqkit version`) and how it was located -- the bottom-left status bar shows `<path>  (configured/bundled/path)`;
  4. reproduction steps plus the exact text of the **"Command"** tab (`Ctrl+Shift+C` copies it);
  5. impact -- what a victim has to do (open a file, run one command, or merely start the app).
- **Sanitize your data first.** Sequence IDs, sample names and file paths can carry personal or project
  information. Describe the shape with fake names; we need the structure, not the content.
- If GitHub's "Report a vulnerability" form is enabled for the repository it will be listed here as a
  second route. That switch is a web-side setting and has not been confirmed yet. **Until it is, email is
  the only channel.**

### Response times (the honest version)

One person maintains this project in spare time. There is no security team, no budget and no bug bounty,
so what follows is a communication cadence, not an SLA:

- The goal is an acknowledgement within **7 calendar days** and a first assessment (valid or not, and which
  side it belongs to) within **14 calendar days**.
- This is **not** a guarantee. Holidays, day jobs and illness can double both numbers. If you have heard
  nothing after 3 weeks, send a follow-up, or go public and label it as a follow-up to a security report.
- Fix timing depends on where the defect lives. Problems in this project land in the next release after
  confirmation. Problems in seqkit can only be forwarded upstream, and we cannot promise anyone else's schedule.
- We do not issue CVEs, do not run multi-party coordinated disclosure, and do not publish advisories.
  When a fix is ready we write a plain description of what was affected.

### Before disclosure

- Please give us a 90-day private window. After 90 days you are free to publish details; we claim nothing.
- During that window we will not share your report, your address or your sample data with third parties.
  Anything forwarded upstream carries technical detail only, without your contact information unless you agree.

### Usually not a vulnerability (please self-check first)

These are documented properties of the current design, listed to save both sides time:

1. **seqkit runs with your own account privileges.** That is how the application works: the executable it
   calls is the one you chose. Anyone who can edit the path in Tools → Settings, or the `bin/` folder, or
   your PATH already has code execution on your machine and does not need this app.
2. **Nothing is passed through a shell.** `core/runner.py` uses `setProgram()` + `setArguments()` with an
   argument vector, never `QProcess.start(command)` and never a shell string. Classic `;` / `&&` injection
   through a file name has no landing point. If you do find a way to get arguments re-interpreted, that
   **is** a vulnerability -- please report it.
3. **Executable lookup refuses the current working directory.** `core/seqkit_locator.py` skips candidates
   located where the app started (the status bar records `... is in the current working directory, which is
   never trusted`), and on Windows it refuses script suffixes such as `seqkit.cmd` / `seqkit.bat`. Check
   these two before reporting binary-planting or DLL-hijacking.
4. **Preferences live in per-user storage** (`QSettings("seqkit-gui", "SeqKit GUI")`, a current-user registry
   key on Windows), and `files/recent` keeps the last 20 input file paths. It affects only the current user
   and stores no credentials. "My recent-files list leaks what I work on" is a privacy discussion, handled as
   hardening rather than as a vulnerability.
5. **stdout is written in full** to the per-user temp directory (`tempfile.mkstemp(prefix="seqkit-gui-",
   suffix=".out")`) so that large results and the "Save result" action work. That file is not securely
   erased on exit. On a shared machine, your output is readable by anyone who can read your temp directory.
   Known limitation, not a report-worthy finding.
6. **The parameter table describes seqkit 2.14.0.** Flags that do not match your seqkit are a data mismatch;
   use the [Spec mismatch template](.github/ISSUE_TEMPLATE/spec_mismatch.yml). It is not a security event.
7. **The repository does not redistribute seqkit.** `bin/` is git-ignored and no build artifact contains a
   seqkit executable (`packaging/seqkit_gui.spec` and `release-build.yml` each enforce this separately).
   "The asset in Releases has no seqkit inside" is intended behaviour.

### What we do not do

- No telemetry, no auto-update, no network version check. The application makes no network requests while
  running; the only outbound action is your own click on Help → "SeqKit official documentation", which hands
  a URL to your system browser. This boundary is a product position, and proposals to add an update check
  will be declined.
- No code signing, no supply-chain attestation or SBOM promise, no security certification claims.
- No guarantee for macOS / Linux: the interface has only been tested on Windows x64, and issues elsewhere are
  handled as ordinary defects.

Unsure whether something counts? **Just write.** Asking costs nothing and nobody will blame you for it.
