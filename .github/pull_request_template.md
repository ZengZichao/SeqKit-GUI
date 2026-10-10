<!--
本模板面向 SeqKit GUI —— 一个非官方的 SeqKit 桌面图形套壳。
填写前请先读 CONTRIBUTING.md（English: CONTRIBUTING.en.md）。
This template is for SeqKit GUI, an unofficial desktop shell around SeqKit.
Read CONTRIBUTING.en.md before filling it in.
-->

## 这个 PR 改了什么 / What this changes

<!-- 1-3 句说清动机与结果：解决什么问题、影响哪一块（参数表单 / 命令组装 / 运行与输出 / 界面与主题 / 打包 / 文档 / 测试 / 工具链）。
     不要只罗列文件清单 —— 那 git diff 自己会显示。
     State the motivation and the outcome. Which part is affected: parameter form, command assembly,
     run & output, UI & theme, packaging, docs, tests, tooling. Skip file inventories. -->

-

## 关联的 issue / Related issue

<!-- Fixes #123 / Closes #123；没有关联 issue 就直接说明动机来源（自己遇到、文档缺口、上游变更）。
     No related issue: say what prompted this instead. -->

-

## 改动范围自查 / Scope check

- [ ] 改动只涉及本 PR 描述的那一件事，没有夹带无关重命名或格式化（**no drive-by refactors**）
- [ ] 没有把 `bin/`、`build/`、`dist/`、`tools/_build/` 里的任何内容加入版本控制
- [ ] 没有引入 seqkit 可执行文件、也没有引入任何"重新分发 seqkit"的表述（本项目不分发 seqkit）
- [ ] 没有引入遥测、自动更新、联网版本检查或任何形式的运行期网络请求（项目立场，不接受此类改动）
- [ ] 没有删除或改写 `LICENSE`、`THIRD-PARTY-LICENSES.md` 中的第三方许可声明
- [ ] 注释与文档只描述**当前设计与意图**，不写"原先/之前/本次新增/改为"这类修改历史叙述
- [ ] 新增依赖已同步进 `requirements.txt`（运行期）或说明为何只在开发/CI 侧使用

## 测试 / Tests

本地真实跑过：

```
python -m pytest tests -q
```

结果（**必须粘贴真实输出末行，不要写"全部通过"** / paste the real tail line, not "all passed"）：

```
<!-- 例如：142 passed, 3 skipped in 61.42s -->
```

- [ ] 我**没有**为了让测试通过而修改断言、跳过用例或加 `xfail`；如果调整了测试，理由写在下面
- [ ] `python packaging/check_version.py` 通过（`all declarations agree`）—— 改动涉及版本号、包名、产物名或 `packaging/` 时必跑
- [ ] `python -m pytest tests/test_release_consistency.py -q` 通过 —— 同上
- [ ] 新增/修改的行为有对应测试；纯文档改动可以没有测试，但请说明

运行环境与失败情况（失败请**如实**写明在哪个 OS / Python 版本失败，不要只报喜）：

| 项 | 值 |
| --- | --- |
| 操作系统 / OS | Windows 11 x64 / macOS / Linux: |
| Python | 3.10 / 3.11 / 3.12: |
| PySide6 | |
| seqkit（`seqkit version`） | |
| 是源码运行还是打包版 | |

> CI 会在 windows / macOS / ubuntu × Python 3.10–3.12 九个组合上跑同一套测试，
> 并且当上游 seqkit 二进制无法下载时会**取消勾选**两个依赖真实二进制的 GUI 用例
> （见 `.github/workflows/ci.yml`）。CI 绿不代表所有用例都跑过 —— 请看那个 job 的 summary 表格。
> CI runs nine matrix combinations and deselects two binary-dependent GUI tests when the upstream
> download fails, so a green job means "everything that could run, passed".

## 参数表 / The parameter table is generated

`seqkit_gui/data/commands.json` 是**生成产物**，由 `tools/spec-dumper`（Go）遍历 seqkit 源码的 cobra 命令树导出，
再由 `tools/extract_spec.py` 整理。它不应手工编辑。

- [ ] 本 PR **不影响**参数表生成（默认选项）
- [ ] 本 PR **影响**参数表 —— 那么请逐项回答：
  - 是否重跑了生成命令，完整命令贴在这里（含 `--seqkit-src` 指向的版本）：
    ```
    python tools/extract_spec.py --build --seqkit-src ../../../seqkit-2.14.0
    ```
  - 只改了 Python 侧的控件判定 / 契约表（`CONTRACTS`）、还是 Go 侧 `spec-dumper` 也改了？
  - 改了 `CONTRACTS` 的话，来源文件与行号（`evidence`）是否同步更新？
  - 是否同步更新 `seqkit_gui/__init__.py` 的 `SEQKIT_SUPPORTED_VERSION` 与
    `seqkit_gui/data/commands.json` 顶层的 `seqkit_version`？两者必须一致，
    `tests/test_release_consistency.py` 与 `packaging/check_version.py` 都会检查。
  - 新增的中文译文是否写进 `tools/translations/usage_zh.json` / `command_zh.json`？
    缺译文时界面会回退显示英文原文，这是预期行为，不是 bug。
  - [ ] 若改的是界面里"参数怎么渲染"的判定（`tools/extract_spec.py` 的 widget 表），
        请贴一张改动前后的界面对照截图（真机，见下）。

## 双语文档与界面文案 / Bilingual docs and strings

界面是中英双语，文档也是中英文两份，必须同步。

- [ ] 新增/修改的可见文字都同时补齐了两种语言：
  - 以英文原文作键写入 `seqkit_gui/i18n/zh_CN.json`（键就是英文原句）
  - 抽象键名（如 `mismatch_hint`）同时写入 `seqkit_gui/i18n/en_US.json` 与 `zh_CN.json`
  - [ ] 两个 json 的键集合对齐，没有只存在于一侧的键
- [ ] 中英文文档成对更新，五篇对应关系：
  | 中文 | English |
  | --- | --- |
  | `docs/zh/getting-started.md` | `docs/en/getting-started.md` |
  | `docs/zh/interface-guide.md` | `docs/en/interface-guide.md` |
  | `docs/zh/command-guide.md` | `docs/en/command-guide.md` |
  | `docs/zh/faq.md` | `docs/en/faq.md` |
  | `docs/zh/development.md` | `docs/en/development.md` |
  另外顶层 `README.md` / `README.en.md`、`CONTRIBUTING.md` / `CONTRIBUTING.en.md` 也要成对。
- [ ] 文档里出现的版本号、命令、快捷键、菜单项名称与代码现状一致
      （例：「工具 → 复制完整命令」的快捷键是 `Ctrl+Shift+C`，它复制的是「命令行」标签，不是「复制结果」按钮）
- [ ] 文档没有断言本项目分发 seqkit，也没有把界面描述成会自己做序列计算

## 界面截图 / Screenshots

**界面改动必须附截图；CI 生成的截图不可用。** offscreen Qt（Linux runner 上的 `QT_QPA_PLATFORM=offscreen`）
没有字体库，`SEQKIT_GUI_SHOOT=1` 在 CI 里会产出豆腐块，因此 `.github/workflows/ci.yml` 把它固定为 `"0"`。
截图只能在装有字体的真机上生成。

- [ ] 截图来自**真实桌面环境**（Windows 真机，或你本机带字体的 macOS / Linux），不是 offscreen 产物
- [ ] 截图是整窗：左侧命令树、参数表单、输出面板四个标签、底部状态栏都在画面内
- [ ] 界面/主题/语言改动同时给出**浅色与深色**两张，并说明涉及中文界面还是英文界面
- [ ] 若需要刷新 `docs/screenshots/` 里的文档配图，命令是：
  ```
  SEQKIT_GUI_SHOOT=1 python -m pytest tests/test_gui.py
  ```
  并在 PR 里说明你替换了哪几张、为什么。

## 打包与平台 / Packaging and platforms

- [ ] 改动涉及打包时，我确认过 `packaging/seqkit_gui.spec` 的产物里**不含**任何 seqkit 可执行文件
      （`test_recipe_refuses_to_bundle_anything_from_bin` 会守住这条）
- [ ] 涉及平台差异（路径、可执行文件名、字体、编码）时，改动只落在 `seqkit_gui/core/paths.py`
      或 `seqkit_gui/core/seqkit_locator.py`，没有在 UI 层散落 `if os.name == "nt"`
- [ ] macOS / Linux 上如果没实测，我在"测试"一节明确写了"未实测"，没有替它背书

## 维护者备注 / For the maintainer

<!-- 需要 reviewer 特别验证的一件事；如何回滚（单提交还是多提交）；是否改变用户可见行为从而影响文档。 -->

-

<!--
最后一条诚实提醒 / one last honesty note:
这个项目由一个人业余维护。小、聚焦、带真实测试输出的 PR 会被优先处理；
大而杂、"顺手清理一下"、贴不出真实测试输出的 PR 更可能被关闭而不是被拆开读。
Small and focused with real test output gets looked at first.
-->
