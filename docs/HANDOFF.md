# 跨会话交接

## 当前仓库状态

- 分支：`step1/dataset-optimization`，远端 `origin/step1/dataset-optimization`。
- 本轮 R01 开始时 HEAD：`16fc82aa57bd67684eaad182654bd9f9bfb5b3a3`，开始时工作区除保护文件外干净；`install.sh` 原有未跟踪且保持未改动。
- 新增独立检索实验，不修改原 DPR 主线、baseline 配置、原评测代码/文件、DPR 向量索引或冻结 MMR 公式。变更及算法契约见 [RETRIEVAL_EXPERIMENTS.md](RETRIEVAL_EXPERIMENTS.md)。
- R01 主提交：`56208ff358d7196e8c7aa2698c3f1e0634adfc0c`。本轮文档收尾写入时 HEAD 为该提交；其后续文档提交哈希按要求在提交后用 `git rev-parse HEAD` 记录。主提交尚待推送并核验。

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

## 唯一下一步

唯一下一步是提交本次文档收尾，再推送当前分支、fetch 并用 `git rev-parse` 与 `git ls-remote` 核验远端包含 R01 主提交及文档提交。实验 manifest `status=completed`、12 个组合全部在 `completed_runs`、逐题均成功、DPR replay 三个 N 均 matched；全套测试和受保护哈希检查通过。`install.sh` 仍为原有未跟踪文件，不纳入提交。

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

更新时间：2026-11-24T10:24:31+08:00（北京时间）。
