# 跨会话交接

## 当前仓库状态

- 分支：`step1/dataset-optimization`，远端 `origin/step1/dataset-optimization`。
- 本轮 R01 开始时 HEAD：`16fc82aa57bd67684eaad182654bd9f9bfb5b3a3`，开始时工作区除保护文件外干净；`install.sh` 原有未跟踪且保持未改动。
- 新增独立检索实验，不修改原 DPR 主线、baseline 配置、原评测代码/文件、DPR 向量索引或冻结 MMR 公式。变更及算法契约见 [RETRIEVAL_EXPERIMENTS.md](RETRIEVAL_EXPERIMENTS.md)。
- R01 主提交：`56208ff358d7196e8c7aa2698c3f1e0634adfc0c`；文档收尾提交：`28277b2d1c2c4277ee32c5979a207d4930409c87`。推送后 `git fetch origin step1/dataset-optimization`、`git rev-parse HEAD`、`git rev-parse origin/step1/dataset-optimization` 与 `git ls-remote --heads origin step1/dataset-optimization` 均核验为 `28277b2d1c2c4277ee32c5979a207d4930409c87`。本次核验收尾文档写入时 HEAD 与最近已核验提交均为该哈希。

## R01 交付内容

- `src/cyber_qa/experiments/retrieval.py`：保留基线 DPR 的独立 BM25+DPR RRF、规则子问题 DPR RRF、预测 CWE 条目内排序+全库保底。
- `src/cyber_qa/experiments/comparison.py`：逐题共享 Reader/Top-K/MMR/普通回答，宏/微指标、分组、配对 bootstrap、失败记账与历史基线核对。
- `scripts/compare_retrieval.py`：一键四方案，默认 N=20/50/100，每次建立新输出目录，复制只读旧基线，逐题 JSONL 与汇总 JSON/CSV/Markdown。
- `tests/test_retrieval_experiments.py`：20 项实验边界、检索隔离、指标及 CLI 回归。
- `docs/RETRIEVAL_EXPERIMENTS.md` 及 README/导航/计划/进度：命令、算法参数、控制变量、结果与限制。
- 用户要求的远端更新前置 Git 状态：当前分支起始 HEAD=`16fc82aa57bd67684eaad182654bd9f9bfb5b3a3`，`origin/step1/dataset-optimization` 同步；无远端新提交。

## 验证与真实实验

- `.venv/bin/python -m pytest -q tests/test_retrieval_experiments.py`：`20 passed`。
- `.venv/bin/python -m pytest -q`：`155 passed in 5.18s`。
- `compileall`、比较脚本 `--help`、`git diff --check`：通过。
- `.venv/bin/python scripts/compare_retrieval.py --device cuda --output outputs/retrieval-comparison-v1-final`：完成 480/480，manifest 为 `completed`，12 组×40 题均成功。第二次运行与首轮非计时汇总完全相同。
- 每个 N 的 DPR replay 为 `matched`；候选池、gold ID、Top-K/MMR 顺序与历史逐题一致，Reader logit 最大差异为 0，logit 容差字段也通过。
- 最终运行 stdout/stderr：`outputs/retrieval-comparison-v1-final.log`。所有 outputs 被 gitignore；旧 `probe-eval-N20/50/100.json`、原 eval 脚本、`docs/theprompt.md` 与 `install.sh` SHA-256 在实现前后保持不变。
- 已完成首轮结果的核心表已写进 PROGRESS；探针 40 题全部 `auto_drafted_needs_human_review`。结论仅作探索性诊断，不能声称答案准确率或正式算法有效性。

## 已知实测与限制

最终运行仍为四方案×N20/50/100 共 480 题全部成功；新 DPR 与历史 20/50/100 的 pool、Top-K/MMR 顺序逐题相同，Reader relevance 最大差值为 0。混合检索将 Recall@N 从 DPR 的 27.50/43.75/50.00% 提高到 73.75/85.00/91.25%，而 MMR Recall@5 为 38.75/33.75/22.50%；CWE 层级 Recall@N 为 40/60/70%，MMR Recall@5 为 26.25/22.50/26.25%；子问题 Recall@N 为 30/45/52.5%，MMR Recall@5 为 20/21.25/25%。差异与 CI 的完整数字、全覆盖率与方法限制见 PROGRESS 和运行产物。单段/多段与普通答案语义正确性不可从未复核标签推出。

复核发现并修正 `historical_check` 的判定：现同时区分候选/选择结构一致和 Reader logit 在 1e-6 内一致；对应测试避免浅拷贝造成的假阳性。最终完整重跑刷新 manifest 的源码哈希。

## 阶段状态

R01 已完成、提交并推送核验。实验 manifest `status=completed`、12 个组合全部在 `completed_runs`、逐题均成功、DPR replay 三个 N 均 matched；全套测试和受保护哈希检查通过。`install.sh` 仍为原有未跟踪文件，不纳入提交。

最终完成后，无新的实现工作。下一阶段是否人工复核标注或拓展正式评测，待用户指定；不可把本机机器草稿结果当作正式测试。

## 恢复检查命令

```bash
git status --short
git branch -vv
git log -1 --format=fuller
.venv/bin/python -m pytest -q
cat outputs/retrieval-comparison-v1-final/manifest.json
cat outputs/retrieval-comparison-v1-final/comparison.md
git push origin step1/dataset-optimization
git fetch origin step1/dataset-optimization
git rev-parse HEAD
git rev-parse origin/step1/dataset-optimization
git ls-remote --heads origin step1/dataset-optimization
```

更新时间：2026-11-24T10:26:16+08:00（北京时间）。

## STEP2 当前交接

### 当前分支与提交

- 分支：`step2/crosslingual-rag`，远端：`origin/step2/crosslingual-rag`。
- STEP2-DOC 提交：`f6d68e86286a53c6517e69a50815b1fd87977c84`，时间 `2026-11-26T16:19:25+08:00`。
- `git push -u origin step2/crosslingual-rag`、`git fetch origin step2/crosslingual-rag` 后，`git rev-parse HEAD`、`git rev-parse origin/step2/crosslingual-rag` 与 `git ls-remote --heads origin step2/crosslingual-rag` 均为 `f6d68e86286a53c6517e69a50815b1fd87977c84`。
- 本收尾提交会更新交接文件；提交后其 HEAD 使用 `git rev-parse HEAD` 获取，不在内容中自引用。

### 本阶段目标

完成 STEP2-DOC：冻结跨语言免翻译规格、拆分可恢复小阶段、记录阶段 0 自检结果，并先提交推送恢复文档；不实现模型或新代码。

### 已修改文件

- `docs/BASELINE_SPEC_V2.md`：新增 STEP2 完整规格，包含跨语言余弦、Rel/Sim 归一化、MMR、索引/候选/作答/引用字段、边界、提示词、平行题集与 P0–P4 门禁。
- `docs/BASELINE_SPEC.md`：顶部新增 v2 链接，v1 原文未重写。
- `docs/IMPLEMENTATION_PLAN.md`：追加 STEP2-DOC、P0A/P0B、P1、P2A/P2B、P3、P4。
- `docs/PROGRESS.md`：追加 STEP2 五类状态、文件用途和北京时间时间线。
- `docs/HANDOFF.md`：追加本 STEP2 交接信息。
- `docs/README.md`：新增 v2 规格导航。
- `docs/COMMIT_LOG.md`：回填 STEP2-DOC 提交短哈希并追加远端核验提交行。

### 已运行命令及结果

- `git fetch origin && git switch step1/dataset-optimization && git pull --ff-only`：首次 pull 遇 TLS 中断，重试后 `Already up to date`。
- `test -f docs/theprompt_2.md`、`git show 92b1543 -- docs/theprompt_2.md`：通过，文件由 `92b1543` 引入。
- `git status --short`：仅有受保护未跟踪 `install.sh`。
- `git branch -vv`、`git remote -v`、`git log --oneline -5`：分支/远端/最近历史已登记。
- `git switch -c step2/crosslingual-rag && git push -u origin step2/crosslingual-rag`：成功。
- 阶段 0 硬件/资源检查：磁盘约 27G 可用；torch `2.9.1+cu128`；`torch.cuda.is_available()` 为 `False`；`nvidia-smi -L` 无 GPU 行；`models/` 只有 DPR；`data/processed` 已有 v1 快照和索引。
- `git diff --check`、`git diff --cached --check` 通过；冻结文件 SHA-256 未变化；STEP2-DOC 提交已推送且三值核验一致。本收尾提交尚未创建。

### 当前失败或阻塞

- 本机没有可见 NVIDIA GPU，内存约 4 GiB；STEP2 Qwen3/Qwen2.5 真实索引和 7B 推理不能在此环境宣称通过。
- STEP2 两个模型资源尚未获取，必须等待可用 GPU/服务和上游资源访问；不能用模拟模型或本地自记哈希替代。
- `install.sh` 是已有保护项，必须保持未跟踪，不得清理或提交。

### 下一步应执行的唯一具体动作

开始 STEP2-P0A：核查两个固定 Qwen 模型仓库的上游 revision、权重文件大小/SHA-256 与 tokenizer 元数据，并据此实现独立资源校验/获取契约；若无法获得可真实推理的硬件或服务，只完成可验证的上游资源部分并如实保持后续推理受阻。

## STEP2 当前恢复记录（2026-11-27，取代上方旧环境快照作为当前状态）

### 当前分支与提交

- 分支：`step2/crosslingual-rag`，跟踪 `origin/step2/crosslingual-rag`。这是恢复时已存在的分支，本次从 `step1/dataset-optimization` 切换并确认 `git pull --ff-only` 为 `Already up to date`；没有重复创建分支。
- 本次文档更新写入时 HEAD：`50c89def6dc7d80375f8803d4d0df37687618a95`；最近已核验的远端提交同为该哈希。后续提交哈希以实际 `git rev-parse HEAD` 和远端三值核验补记。

### 本阶段目标

- 刷新阶段 0 环境记录，保留现有 STEP2 恢复文档和 P0A 草稿；然后按计划核验资源清单/校验器及两个固定模型的上游元数据。

### 已修改文件

- `docs/BASELINE_SPEC_V2.md`：将 2026-11-27 硬件/磁盘/Torch 自检作为新快照追加，保留 2026-11-26 的历史环境记录。
- `docs/PROGRESS.md`：修正当前 P0A 状态，登记未跟踪文件、当前环境和时间线；没有把历史 R01 或未验证事项改记为通过。
- `docs/HANDOFF.md`：追加本次恢复的分支、精确状态、命令结果、失败/阻塞与唯一下一步。
- `docs/COMMIT_LOG.md`：按要求追加本阶段提交记录；提交哈希遵循“见下”规则。
- 未暂存或改写 `configs/crosslingual-models.v2.json`、`scripts/check_crosslingual_resources.py`、`tests/test_crosslingual_resources.py`、`install.sh`。

### 已运行命令及结果

- `git switch step2/crosslingual-rag && git pull --ff-only`：成功；该分支已存在且与远端一致。
- `git status --short`：仅列出四个未跟踪文件：三个上述 P0A 文件和受保护的 `install.sh`；均未清理或暂存。
- `git branch -vv`：当前分支为 `step2/crosslingual-rag`，起始 HEAD/远端为 `50c89def6dc7d80375f8803d4d0df37687618a95`。
- `git remote -v`：origin fetch/push 均指向配置的 GitHub 仓库。
- `git log -1 --format=fuller`：最近提交为 `docs(step2): record recovery baseline remote verification`，时间 `2026-11-26T16:23:27+08:00`。
- `nvidia-smi`：NVIDIA GeForce RTX 4090，24GB 显存；无运行进程。
- `df -h .`：50G 文件系统，可用 25G。
- `.venv/bin/python -c "import torch;print(torch.__version__, torch.cuda.is_available())"`：`2.9.1+cu128 True`。
- `ls models/dpr data/processed data/annotations/probe-v1`：DPR 模型目录、`cwe-v1`/`dpr-index-v1` 及探针文件存在；没有列出 STEP2 模型目录。
- 已读取三个未跟踪 P0A 文件；内容包括固定 revision 配置及 Hugging Face LFS 元数据/本地 SHA-256 检查草稿，尚未运行其测试或执行真实上游检查。
- 首次 `git commit` 因本地未设置 author identity 失败；后续提交使用历史提交身份 `Codex <codex@localhost>` 的单次 `git -c user.name=... -c user.email=...` 参数，不改全局配置。

### 当前失败或阻塞

- 当前 GPU 不再是阻塞。Qwen 上游访问、两模型权重下载/核验、tokenizer 加载及真实模型推理仍未验证；不能将配置中的 revision 视为权重已验证。
- 三个 P0A 文件为未跟踪状态；保留它们，但本次只提交上述文档路径。`install.sh` 是保护项，始终不提交。

### 下一步应执行的唯一具体动作

先运行 `.venv/bin/python -m pytest -q tests/test_crosslingual_resources.py` 验证现有 P0A 校验器草稿；测试结果记录后，再用 `scripts/check_crosslingual_resources.py` 对配置中的两个不可变 revision 查询上游 LFS 元数据并检查本地模型文件状态。不得下载或提交模型前先核对容量与上游文件清单。

更新时间：2026-11-27T09:40:38+08:00（北京时间）。
