# 参与贡献

感谢你愿意改进 SeqKit GUI。本文说明本地开发方式与验收标准。英文说明见 [CONTRIBUTING.en.md](CONTRIBUTING.en.md)。

SeqKit GUI 是 [SeqKit](https://github.com/shenwei356/seqkit)（Wei Shen 开发的 MIT 许可序列工具包）的**非官方**桌面图形前端：与 SeqKit 项目无关，未获其认可，也不由其维护。它自身不做任何序列处理，只负责组装参数并调用官方 `seqkit` 可执行文件。

## 环境准备

```bash
python -m pip install -r requirements.txt   # PySide6
python -m pip install pytest pyinstaller    # 可选：测试与打包
python tools/fetch_seqkit.py                # 获取 seqkit（放入 bin/）
python -m seqkit_gui                        # 启动
```

`bin/` 已在 `.gitignore` 中，不要提交 seqkit 可执行文件。

## 代码结构

- `seqkit_gui/core/` 与界面无关：`spec.py` 读参数表，`builder.py` 组装参数向量并做运行前校验（含 `BOUNDED_RUN_FLAGS`：没有退出条件的 `scat` 在子进程创建之前就被拒绝），`runner.py` 用 QProcess 异步执行并 tee 输出，`seqkit_locator.py` 定位可执行文件，`paths.py` 集中处理平台差异，`settings.py` 负责持久化。
- `seqkit_gui/ui/` 全部界面：`main_window.py` 组装窗口，`param_form.py` 依据参数表动态生成表单，`output_view.py` 结果与日志视图，`widgets.py` 参数行控件，`theme.py` 明暗配色令牌，`i18n.py` 语言表。
- 界面代码不直接调用 `subprocess`，也不拼接 shell 命令字符串；执行一律经 `core/runner.py` 的参数列表方式。

## 参数表是生成出来的

`seqkit_gui/data/commands.json` 由 SeqKit 源码生成，**不要手工编辑**：

```bash
python tools/extract_spec.py --build --seqkit-src ../../../seqkit-2.14.0
```

- `tools/spec-dumper`（Go）遍历 cobra 命令树，导出参数名、简写、类型、默认值与 usage 原文；这一步需要 Go 工具链（`go.mod` 声明 `go 1.25.14`，开发机上的 `go version` 输出为 `go1.27.0 windows/amd64`，高于该声明即可）。脚本会在启动 dumper 前把 `GOPROXY` 兜底设为 `https://goproxy.cn,https://proxy.golang.org,direct`（直连 `proxy.golang.org` 在部分网络环境不可达），并设 `GOFLAGS=-mod=mod`；你已经设过 `GOPROXY` 时不会被覆盖。
- `--seqkit-src` 执行的是 `go mod edit -replace=github.com/shenwei356/seqkit/v2=<路径>`，工作目录是 `tools/spec-dumper/`，所以上面那个相对路径是按该目录算的（等价于项目同级检出的 `seqkit-2.14.0`）；目录结构不同就换成你自己的绝对路径。仓库里的 `tools/spec-dumper/go.mod` 已自带一条指向本地检出的 `replace`。
- `tools/extract_spec.py` 判定控件类型、抽取枚举候选、合并中文说明，并写入从各命令 `Run` 函数读出的输入文件契约与必需参数约束（`CONTRACTS` 表，附来源文件与行号）。
- 整条链路是 `seqkit 源码 ─(tools/spec-dumper, Go)→ tools/_build/spec_raw.json ─(tools/extract_spec.py)→ seqkit_gui/data/commands.json`。中间的 `tools/_build/spec_raw.json` 连同 `tools/_build/` 一起被 `.gitignore` 忽略，只有 `commands.json` 入库；因此手上已有 `spec_raw.json` 时，不带 `--build` 就只做规范化，这一步不需要 Go。
- 这条链路由 `tests/test_schema.py` 从两侧钉住：`test_generated_from_dumper_not_handwritten` 要求 `commands.json` 与 `tools/spec-dumper/main.go` 同时存在（入库的生成物必须配得上它的生成器），`test_schema_lists_every_subcommand_from_the_cli`、`test_every_command_help_is_reachable`、`test_global_flags_reach_every_command` 再把表内容与真实 `seqkit` 的命令清单和每条命令的 `--help` 逐项对照，`test_input_contracts_are_recorded_with_source_evidence` 要求每个命令都带 `evidence` 出处。
- 支持的 SeqKit 版本有变化时，重新生成参数表、更新 `CONTRACTS` 中相应的约束，并同步 `seqkit_gui/__init__.py` 里的 `SEQKIT_SUPPORTED_VERSION`。

中文说明表在 `tools/translations/`：`usage_zh.json` 以英文 usage 原文为键，`command_zh.json` 提供命令与分组的中文名。参数缺少中文时，界面回退显示英文原文。

## 测试

```bash
python -m pytest tests -q
python -m pytest tests -q --collect-only          # 只看收集到的用例
QT_QPA_PLATFORM=offscreen python -m pytest tests/test_i18n.py -q
```

测试会调用真实 seqkit：核对命令清单与每个命令的 `--help`、检查参数组装与校验规则、执行若干端到端命令，并在 offscreen 模式下构建窗口；找不到 seqkit 时相关用例自动 skip。用例数量随代码变化，以命令输出为准。请保证新功能有对应测试。界面改动需要截图时，两道开关都要给：

```bash
set SEQKIT_GUI_SHOOT=1             # POSIX shell 下写 export SEQKIT_GUI_SHOOT=1
python -m pytest tests/test_gui.py -q --with-screenshots
```

缺 `--with-screenshots` 或缺 `SEQKIT_GUI_SHOOT=1` 时该用例都会跳过。它写到被忽略的开发期目录 `tools/_build/screenshots/`；`docs/screenshots/` 里的 5 张成品是从真实窗口手工截取的，且目前含有截图机器的绝对路径与用户名，重拍要先在净化过的示例目录里进行。

## 反馈与评审

- 提 issue 前先走 [SUPPORT.md](SUPPORT.md)，里面有支持渠道与「哪些算 bug」的界定；四种模板在 `.github/ISSUE_TEMPLATE/`：[`bug_report.yml`](.github/ISSUE_TEMPLATE/bug_report.yml)（缺陷）、[`feature_request.yml`](.github/ISSUE_TEMPLATE/feature_request.yml)（功能请求）、[`spec_mismatch.yml`](.github/ISSUE_TEMPLATE/spec_mismatch.yml)（参数表与真实 CLI 不一致）和 [`config.yml`](.github/ISSUE_TEMPLATE/config.yml)（额外联系入口）。
- 安全漏洞不要开公开 issue，按 [SECURITY.md](SECURITY.md) 的方式报告。
- 开 PR 时用 [`pull_request_template.md`](.github/pull_request_template.md) 的骨架；它要求的每一项都对应仓库里能跑的验证（测试、版本一致性检查、文档双语同改）。
- 社区行为约定见 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。
- 双语是硬性要求：改了 `docs/zh/` 就同改 `docs/en/`，改了 `README.md` 就同改 `README.en.md`，改了 `CONTRIBUTING.md` 就同改 `CONTRIBUTING.en.md`。

## 界面改动的约定

- 添加可见文字时，同时补 `seqkit_gui/i18n/zh_CN.json`（键即英文原文）；抽象键名（不是完整英文句子、无法靠键名本身回退的）需同时写入 `en_US.json`。
- 主题色只通过 `theme.py` 的令牌引用；实心色块上的文字保持白色，不使用提亮后的填充色。
- 内容类元素左对齐，状态与提示类（进度、空态、提示文案）居中。
- 注释只描述当前设计与意图，不写修改历史。

## 提交与许可

- 分支上完成改动后运行测试，再提交；提交说明写清动机而不是罗列改动。
- 许可相关的自检命令是 `python tools/license_check.py`，它检查发行包是否误含 `bin/`、本项目与 SeqKit 的许可证文件是否齐备，最后一行输出 `SUMMARY: seqkit-license=PASS  project-license=PASS`（其中标注为 advisory 的检查项只提示不拦截）。
- 本项目采用 MIT 许可；SeqKit 的 MIT 声明保留在 `THIRD-PARTY-LICENSES.md`，提交时请勿移除。
- 不要提交 `bin/`、`build/`、`dist/`、`tools/_build/` 中的内容。

## 打包

```bash
python -m pip install pyinstaller
pyinstaller packaging/seqkit_gui.spec
python packaging/check_version.py            # 版本号与命名在各处是否一致
python packaging/check_version.py --tag v1.0.0
```

产物为 onedir 目录 `dist/SeqKit-GUI/`，主程序 `SeqKit-GUI.exe`（`console=False`，无控制台窗口），资源落在 `dist/SeqKit-GUI\_internal\seqkit_gui\{data,i18n,assets}`；把 `seqkit.exe` 放进 `dist/SeqKit-GUI/bin/`——recipe 刻意不收集 seqkit，收集到就会终止构建。采用 onedir 而非 onefile，是为了满足 PySide6 的 LGPL 要求（用户可替换 Qt 库）。`packaging/check_version.py` 只用标准库，逐项打印它从 `seqkit_gui/__init__.py`、`pyproject.toml`、`data/commands.json`、`tools/fetch_seqkit.py` 和 spec 里读到的版本与命名，全部一致时输出 `all declarations agree` 并以 0 退出。
