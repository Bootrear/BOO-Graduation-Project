# 跨会话交接

先读取 AGENTS、BASELINE_SPEC、IMPLEMENTATION_PLAN、PROGRESS，再读本文件；随后检查实际 Git 状态。

## 当前分支和提交

- 当前任务分支：`baseline/cwe-dpr-reader-mmr`。
- 远端：`origin` → `https://github.com/Bootrear/BOO-Graduation-Project.git`。
- 本文件首次写入时 HEAD：`e02886629f045b3de2eb9b0005e4117487faa1dc`。
- 最近已核验的 P00 阶段提交：尚未创建。
- 推送状态：P00 尚未提交/推送；远端首次检查尚无该任务分支。
- 当前文档提交自身及最新 HEAD 的精确值：运行 `git rev-parse HEAD`。文件不能嵌入其自身哈希；上述“写入时 HEAD”是审计锚点，不冒称包含本文档的最新提交。

恢复时执行：

```bash
git status --short
git branch -vv
git log -1 --format=fuller
git rev-parse HEAD
git ls-remote --heads origin baseline/cwe-dpr-reader-mmr
```

## 本阶段目标

P00：在工程实现前将完整规格、计划、进度和交接纳入 Git 并推送、核验；无需聊天记录即可恢复。当前尚未开始基线工程代码，整体基线未验收。

## 已修改文件

新增 AGENTS.md、docs/BASELINE_SPEC.md、docs/IMPLEMENTATION_PLAN.md、docs/PROGRESS.md、docs/HANDOFF.md；版本化原有 docs/theprompt.md；更新 docs/README.md 导航。

`install.sh` 为原有未跟踪用户文件，保持不动，不暂存。未修改 src、tests、配置或环境代理。

## 已运行命令及结果

| 命令/检查 | 实际结果 |
| --- | --- |
| `git status --short` / `git branch -vv` / `git log -1 --format='%H%n%s'` | 初始仅 theprompt.md 和 install.sh 未跟踪；任务分支已存在；初始 HEAD 见上 |
| `git remote -v` / `git symbolic-ref refs/remotes/origin/HEAD` | origin 指向当前仓库；默认分支 main，当前已是任务分支 |
| `git ls-remote --heads origin baseline/cwe-dpr-reader-mmr` | 退出 0、无匹配分支；证明读取可达，尚未证明可推送 |
| 读取全部 463 行 theprompt 及现有代码/配置/测试/README | 需求已读；DSES 与要求的 MMR 不同；Reader 等仅职责文档 |
| `python --version` | Python 3.12.11 |
| `python -m pytest -q` | 失败：No module named pytest；没有测试通过结论 |
| `PYTHONPATH=src python scripts/smoke_demo.py` | 通过；旧合成 DSES 选两段，190 tokens |
| `python -m compileall -q src scripts tests` | 退出 0；语法检查通过 |
| `df -h .` / `free -h` / `nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader` | 约 48 GiB 磁盘可用、64 GiB 内存、RTX 4090 24564 MiB 显存 |
| importlib.util.find_spec 检查 | torch/numpy 存在；pytest/transformers/faiss 缺失；未测试 CUDA 推理 |
| 检查 data/raw、models、HF cache、data/processed | 当前没有真实 CWE、模型缓存或索引；不能沿用历史快照文档结论 |
| `git config user.name` / `git config user.email` | 未配置提交身份；使用下方本次命令级自动化身份，不冒用历史作者 |

- 文档一致性 Python 检查：PASS；原文逐字一致、SHA-256 一致、本地链接存在、五类状态/六项交接字段/P00–P10 齐全。
- `git diff --check`：退出 0（当时仅已跟踪导航文件）。暂存后默认检查报告 theprompt.md 的原始 CRLF 为行尾空白；保持源文件字节不变，改用 `git -c core.whitespace=trailing-space,space-before-tab,cr-at-eol diff --cached --check`，退出 0；仍检查真实行尾空格。

## 当前失败或阻塞

- pytest 缺失，已有 6 项测试未执行；真实数据/模型/索引缺失，真实基线未验证。
- P00 无需这些资源即可完成文档验收。首次推送尚待执行，不提前宣称成功。
- 提交命令使用 `git -c user.name=Codex -c user.email=codex@localhost commit ...`；仅本次命令生效，不修改用户全局身份。

## 下一步应执行的唯一具体动作

执行下方 `git add AGENTS.md docs/theprompt.md docs/BASELINE_SPEC.md docs/IMPLEMENTATION_PLAN.md docs/PROGRESS.md docs/HANDOFF.md docs/README.md`，暂存 P00 指定文件。随后检查暂存差异、提交并推送；远端核验前不要进入 P01。

## 提交、推送及中断恢复命令

只暂存本阶段指定的 7 个文件；不得 `git add .` 带入 install.sh。

```bash
git add AGENTS.md docs/theprompt.md docs/BASELINE_SPEC.md docs/IMPLEMENTATION_PLAN.md docs/PROGRESS.md docs/HANDOFF.md docs/README.md
git -c core.whitespace=trailing-space,space-before-tab,cr-at-eol diff --cached --check
git diff --cached
git -c user.name=Codex -c user.email=codex@localhost commit -m "docs(baseline): freeze requirements and establish resumable workflow"
git push -u origin baseline/cwe-dpr-reader-mmr
git fetch origin baseline/cwe-dpr-reader-mmr
git rev-parse HEAD
git rev-parse origin/baseline/cwe-dpr-reader-mmr
```

若推送失败，保留本地提交，将 `git rev-parse HEAD` 的哈希、错误摘要和未推送状态写入本文件，再创建本地 checkpoint 文档提交；恢复命令为 `git push -u origin baseline/cwe-dpr-reader-mmr`，先 fetch 并检查远端分叉，禁止强推。
