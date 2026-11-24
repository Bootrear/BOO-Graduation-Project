# 提交记录

本文件记录**每次提交**的时间、任务名称与主要内容。用户要求：自 2026-11-23 起，
每次提交都在本表**末尾新增一行**，不修改历史行。

- 提交时间为 `Asia/Shanghai`（UTC+08:00），与 `git log --format=%cI` 一致。
- 任务名称取自 commit 标题前缀，便于和 `git log` 对照。
- “主要做了什么”只写可核对的事实，不写未验证的结论。
- **提交哈希列**：一次提交无法把自己的哈希写进自己的内容（会改变哈希）。因此最新一行
  标为“见下”，由**下一次提交**补填；也可随时用 `git log --oneline` 查。

| # | 提交时间（+08:00） | 任务名称 | 主要做了什么 | 提交哈希 |
| --- | --- | --- | --- | --- |
| 1 | 2026-11-23T14:23:42 | feat(eval): add 40-question probe skeleton for MMR discrimination (STEP1) | 新建分支 `step1/dataset-optimization`；新增探针集骨架 `data/annotations/probe-v1/`（40 题，模板 A12/B8/C8/D4/E8，40 个不同 CWE）、候选段落索引与清单；新增生成器 `scripts/make_probe_skeleton.py` 与 ID 校验脚本 `scripts/verify_probe_ids.py`。`question` 与 `gold_facts` 当时为空。 | `d56eb88` |
| 2 | 2026-11-23T14:26:40 | fix(eval): balance probe candidate pools per field | 修正“候选池全局最多 6 条”造成的跨字段塌陷：模板 C 原有 8 道题候选池全为 `detection_methods`、`potential_mitigations` 为 0；改为按字段分别设上限（A 1+4、B/C 3+3、D 6、E 单字段 4）。条目选择不变，候选段落索引 219→200。 | `3b55b7c` |
| 3 | 2026-11-23T14:37:57 | docs(eval): draft probe questions and gold facts, add commit log | 为 40 题起草 `question` 与 `gold_facts`：新增 `draft.v1.json`（机器起草稿）与合并校验脚本 `scripts/apply_probe_annotations.py`，产出 `qa.v1.jsonl`（40 条、72 条 gold fact、8 条 `single_span` 带 `answer_span`）。8 个 `answer_span` 按原文逐字符核对通过；40 条 fact 均覆盖各自必选证据。标注人记为 `deepseek-auto-draft`，状态 `auto_drafted_needs_human_review`，**未经人工复核**。同时新增本提交记录表并更新 STEP1 文档。 | `03de12b` |
| 4 | 2026-11-24T09:28:58 | feat(eval): add probe gate evaluation scripts and GPU runbook | 新增门禁评测脚本 `scripts/eval_probe.py`（同池比较 Top-K 与 MMR 的 Evidence Recall@5、全覆盖率、Hit@5、池内与选中集合冗余度、策略分歧、配对 bootstrap 95%CI，并支持 `--n`/`--lam` 运行期覆盖）与纯检索诊断脚本 `scripts/eval_retrieval.py`（必选证据排名分布与 Recall@N 曲线）。补 `docs/EXPERIMENT_RUNBOOK.md`：GPU 机器从取代码、装依赖、下模型、预处理校验、建索引到 N/λ 扫描与判读规则的完整指令。**未提交任何实验结果**；`outputs/` 中的 CPU 预演结果仍为本地未跟踪产物。 | 见下 |
