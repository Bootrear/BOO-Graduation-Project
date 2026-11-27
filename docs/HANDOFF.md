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
- P0A/P0B 主提交 `758e5cf9cf15e2ceb5d33769f8cfda34ca4051ef` 已推送；`git fetch origin step2/crosslingual-rag` 后本地 HEAD、`origin/step2/crosslingual-rag` 和 `git ls-remote --heads origin step2/crosslingual-rag` 三值均为该哈希。
- P1A 提交 `2d8c1975086adecf338b84f219d22a2f601e7020` 已推送；`git fetch origin step2/crosslingual-rag` 后本地 HEAD、`origin/step2/crosslingual-rag` 与 `git ls-remote --heads origin step2/crosslingual-rag` 三值均为该哈希。
- P1B 门禁提交 `4cedbcaf46d6a03b771d54826ff0b9bc1cf576e3` 已推送；`git fetch origin step2/crosslingual-rag` 后本地 HEAD、`origin/step2/crosslingual-rag` 与 `git ls-remote --heads origin step2/crosslingual-rag` 三值均为该哈希。
- 本次门禁核验文档收尾提交创建前 HEAD：`4cedbcaf46d6a03b771d54826ff0b9bc1cf576e3`；本次文档提交自身哈希提交后用 `git rev-parse HEAD` 获取并再次核验。

### 本阶段目标

- 刷新阶段 0 环境记录，保留现有 STEP2 恢复文档和 P0A 草稿；然后按计划核验资源清单/校验器及两个固定模型的上游元数据。

### 已修改文件

- `docs/BASELINE_SPEC_V2.md`：追加 2026-11-27 硬件/磁盘/CUDA 实测，保留 11-26 历史快照。
- `docs/PROGRESS.md`：区分 P0A 元数据验证、单元测试、尚未完成的 7B 权重获取和未执行的模型推理。
- `docs/HANDOFF.md`：记录 P0A 命令结果、下载中断、当前远端核验和唯一下一步。
- `docs/COMMIT_LOG.md`：补录恢复文档提交并追加 P0A checkpoint 行。
- `configs/crosslingual-models.v2.json`：记录两个模型 ID 与不可变 Hugging Face revision。
- `scripts/check_crosslingual_resources.py`：查 Hugging Face 上游 LFS 元数据、核对本地字节数/SHA-256，增加固定 revision 下载入口。
- `tests/test_crosslingual_resources.py`：验证上游身份/LFS 元数据、本地哈希及固定 revision 下载参数。
- `requirements-crosslingual.txt`：单独固定 `huggingface_hub==0.36.2`。
- `src/cyber_qa/crosslingual_resources.py`：抽取共享 Hugging Face pinned revision 上游 LFS 元数据核验逻辑。
- `src/cyber_qa/retrieval/crosslingual.py`、`src/cyber_qa/retrieval/__init__.py`：Qwen3 last-token 编码、索引文件写入/哈希/加载校验、同空间 cosine 检索。
- `scripts/build_crosslingual_index.py`：真实快照索引构建 CLI。
- `tests/test_crosslingual_index.py`：索引兼容性、哈希篡改、非法向量和排序回归。
- `src/cyber_qa/experiments/chinese_probe.py`、`scripts/make_chinese_probe.py`、`tests/test_chinese_probe.py`、`data/annotations/probe-v1-zh/README.md` 与 `qa.v1.zh.jsonl`：用固定 Qwen2.5-7B 离线派生中文问题平行集，核对所有非 question 字段/source hash，标为机器翻译且未人工复核。
- `install.sh` 未修改且未纳入提交；模型目录保持忽略。

### 已运行命令及结果

- `git switch step2/crosslingual-rag && git pull --ff-only`：成功；分支已存在且当时与远端一致。
- 阶段 0 自检：RTX 4090 24GB、磁盘可用 25G、Torch `2.9.1+cu128 True`；`models/dpr`、`cwe-v1`、`dpr-index-v1` 存在。
- `.venv/bin/python -m pytest -q tests/test_crosslingual_resources.py`：先 `5 passed`，补充下载路径回归后 `7 passed`。
- `.venv/bin/python scripts/check_crosslingual_resources.py --config configs/crosslingual-models.v2.json --model-root models/crosslingual`：退出 0。两个 Hugging Face revision 身份匹配；Embedding 模型权重和 tokenizer 文件均匹配上游大小/SHA-256；7B 四个分片上游大小/摘要已读取，本地缺失。
- `.venv/bin/python scripts/check_crosslingual_resources.py --help`：退出 0，`--download` 帮助显示正常。
- `.venv/bin/python scripts/check_crosslingual_resources.py --config configs/crosslingual-models.v2.json --model-root models/crosslingual --download`：已启动后按用户要求中断，退出 130；只留下约 512MB 的两个 `.incomplete` 分片缓存，未有完整 7B 权重。当前无下载进程。
- `git check-ignore -v models/crosslingual/Qwen--Qwen2.5-7B-Instruct`：命中 `.gitignore:21:models/`。
- 7B 模型已由用户从 ModelScope 获取；资源检查器实测四个 `model-0000*-of-00004.safetensors` 字节数/SHA-256 全部与 Hugging Face pinned revision 上游 LFS 元数据一致，Qwen3 权重与 tokenizer 也一致。
- 两套 tokenizer 用 Transformers `4.57.1`、`local_files_only=True` 加载成功；Qwen3 的真实 CUDA 试编码输出 2×1024 有限单位向量。Qwen2.5-7B `bfloat16` 在 RTX 4090 加载成功并完成 80-token 贪心生成探针（不是 P3 端到端或质量验收）。
- `.venv/bin/python -m pytest -q tests/test_crosslingual_index.py tests/test_crosslingual_resources.py`：`14 passed`；构建器 `--help` 和相关 `compileall` 通过。
- `.venv/bin/python scripts/build_crosslingual_index.py --snapshot data/processed/cwe-v1 --model-dir models/crosslingual/Qwen--Qwen3-Embedding-0.6B/97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3 --config configs/crosslingual-models.v2.json --output data/processed/crosslingual-index-v2-final --device cuda --batch-size 16`：退出 0，真实编码 5748 段、1024维 float32，0 段截断；最终 `vectors_sha256=734393d803ed2a31de8c39a17f09e69b61462191d34d27009e3337f39c8b9fa2`，索引目录被 `.gitignore` 排除。较早的 `crosslingual-index-v2` 是归一化试建产物，后续只使用 `crosslingual-index-v2-final` 原始向量索引。
- 新进程调用 `load_index` 通过文件哈希、snapshot 和 model revision 检查；再用真实 Qwen3 对英文 `What causes SQL injection?` 和中文 `SQL 注入是如何产生的？` 查询，Top-3 都包含 CWE-89 description；未计作 P1 Recall 门禁。
- `.venv/bin/python -m pytest -q`：`169 passed in 4.82s`；`.venv/bin/python -m compileall -q src scripts` 和 `git diff --check` 均通过。
- `.venv/bin/python -m pytest -q tests/test_chinese_probe.py`：`9 passed in 1.41s`；平行题 CLI help 与 compileall 通过。
- `.venv/bin/python scripts/make_chinese_probe.py --input data/annotations/probe-v1/qa.v1.jsonl --output data/annotations/probe-v1-zh/qa.v1.zh.jsonl --model-dir models/crosslingual/Qwen--Qwen2.5-7B-Instruct/a09a35458c702b33eeacc393d103063234e8bc28 --device cuda --max-new-tokens 96`：退出 0，真实 Qwen2.5-7B 翻译 40/40 条。实际产物 `validate_parallel` 全字段检查通过；英文源 SHA-256=`bdc2999481cf8680ecfa5cc2ba621947f41bade931e7e23057d54ec3ceca7ebf`，源文件没有差异。翻译题未经人工复核。
- `.venv/bin/python -m pytest -q tests/test_crosslingual_gate.py tests/test_chinese_probe.py tests/test_crosslingual_index.py`：`22 passed`；评测 CLI `--help`、compileall 通过。
- `.venv/bin/python scripts/eval_crosslingual_retrieval.py --english data/annotations/probe-v1/qa.v1.jsonl --chinese data/annotations/probe-v1-zh/qa.v1.zh.jsonl --index data/processed/crosslingual-index-v2-final --snapshot data/processed/cwe-v1 --model-dir models/crosslingual/Qwen--Qwen3-Embedding-0.6B/97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3 --output outputs/crosslingual-gate-v2 --device cuda --n 20 50 100`：退出 0，英语/中文各 40 题真实直接编码；Recall@20/50/100 英语 `.650/.725/.8125`，中文 `.5875/.6875/.775`；中英等价性 `.9371428571`；门禁 verdict `retrieval_gate_pass_exploratory_only`。英文 DPR 历史基线 `.275/.4375/.5` 的 90%线 `.2475/.39375/.45` 均超过。平均池余弦英语 `.6364/.6188/.5986`、中文 `.6306/.6151/.5981`，低于历史对照 `.857`。详细逐题结果只在忽略的 `outputs/crosslingual-gate-v2/`。
- `.venv/bin/python -m pytest -q`：`184 passed in 5.04s`；`compileall` 和 `git diff --check` 通过。
- P1B 实际输出保存在 `outputs/crosslingual-gate-v2/summary.json` 与 `per_question.jsonl`，均在忽略的 outputs 中，不提交模型/索引/运行结果。
- 恢复文档提交 `69676b4265cb19622ba7625961ac6ede46b0d9b1` 已推送；首次 fetch 遇 TLS 握手中断，重试后 `HEAD`、跟踪分支与 `ls-remote` 三值一致。
- 首次 Git 提交因未设置 author identity 失败；重试使用 `Codex <codex@localhost>` 的单次 `git -c` 参数，未修改全局 Git 配置。

### 当前失败或阻塞

- P0A/P0B/P1A 实测通过，P1B 按探索性探针指标达到工作单门槛；P2 MMR 与 P3 ≥10 题回答/引用校验仍待实现和验证。中文题集未经人工复核，P1 数字不能作为论文结论。当前无已知硬件阻塞。
- 磁盘剩余约 11GB；后续 P1/P2 输出应继续写入被忽略的 `outputs/`，不得复制模型或索引。

### 下一步应执行的唯一具体动作

进入 STEP2-P2A：新增 v2 配置/适配器，显式从 Qwen 检索余弦一次性归一化完整候选池相关性，并用 Qwen 同空间段向量生成 Sim；默认对所有非对角 Sim_raw pair 值池内 min-max。用适配器显式构造现有 `PreparedPool` 并调用冻结的 `select_mmr()`，不得改写 `selection/mmr.py`。测试空池、K=0、不足 K、单候选、全同分、NaN/Inf、零向量、lambda 两端、lambda=1 Top-K 完全一致及 Sim 增量等价；本步不扫描真实题集，也不改英文 baseline-v1。

更新时间：2026-11-27T10:57:00+08:00（北京时间）。

## STEP2-P2A 交接（2026-11-27）

### 当前分支与提交

- 分支：`step2/crosslingual-rag`，跟踪 `origin/step2/crosslingual-rag`。
- P2A 代码提交 `5d89c3cbe9e650dace94bbd3bb9b486e4343329c` 已推送；`git fetch origin step2/crosslingual-rag` 后本地 HEAD、`origin/step2/crosslingual-rag` 和 `git ls-remote --heads origin step2/crosslingual-rag` 三值均为该哈希。
- 本次远端核验文档提交创建前 HEAD：`5d89c3cbe9e650dace94bbd3bb9b486e4343329c`；文档提交自身哈希将在提交后更新到 HANDOFF。

### 本阶段目标与已修改文件

- 目标：把 Qwen 检索余弦和同空间向量显式适配到既有 `PreparedPool`/`select_mmr()`，不修改冻结 `src/cyber_qa/selection/mmr.py`。
- `src/cyber_qa/selection/crosslingual_mmr.py`：新增 `crosslingual-rag-v2` 配置对象、完整候选池检索相关性归一化、Qwen 冗余构造及既有 MMR 调用适配；支持默认池内 min-max 与 raw 两种 Sim 尺度。
- `configs/crosslingual-rag.v2.json`：记录 v2 默认参数，`lambda_weight=0.5` 且 `untuned`。
- `tests/test_crosslingual_mmr.py`：7 项测试覆盖空池、K=0、不足 K、单候选、全同分、NaN/Inf、零向量、归一化溢出、lambda=1 Top-K 等价、两种 Sim 尺度及增量/逐轮参考等价。
- `docs/PROGRESS.md`、`docs/HANDOFF.md`、`docs/COMMIT_LOG.md`：本阶段验证分类、交接信息和提交记录。

### 已运行命令及结果

- `.venv/bin/python -m pytest -q tests/test_crosslingual_mmr.py`：`7 passed`。
- `.venv/bin/python -m pytest -q`：`191 passed in 4.85s`。
- `.venv/bin/python -m compileall -q src scripts`：退出 0。
- `git diff --check`：通过。
- 本阶段验证为适配器单元/选择器参考实现回归；没有执行真实模型/真实题集筛选，真实推理和真实端到端状态不变。

### 当前失败或阻塞

- 无代码或硬件阻塞。P1 探针题未经人工复核，后续结果仍只能作为探索性诊断；磁盘/模型索引约束沿用上文记录。

### 下一步应执行的唯一具体动作

进入 STEP2-P2B：新增评测脚本，读取现有索引和中英平行探针，对同一批真实 Qwen3 检索候选池比较 Retrieval Top-K 与 MMR；扫描 lambda=0 到 1，并在默认 pool-minmax 与 raw Sim 下记录逐题结果、Recall@5/全覆盖/Hit/冗余/分歧及配对 bootstrap 95% CI。先只完成评测实现和可验证的脚本/指标测试，再按阶段计划运行真实双语评测；不得把未复核 40 题写成论文结论。

更新时间：2026-11-27T11:10:00+08:00（北京时间）。
