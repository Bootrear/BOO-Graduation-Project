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
| 4 | 2026-11-24T09:28:58 | feat(eval): add probe gate evaluation scripts and GPU runbook | 新增门禁评测脚本 `scripts/eval_probe.py`（同池比较 Top-K 与 MMR 的 Evidence Recall@5、全覆盖率、Hit@5、池内与选中集合冗余度、策略分歧、配对 bootstrap 95%CI，并支持 `--n`/`--lam` 运行期覆盖）与纯检索诊断脚本 `scripts/eval_retrieval.py`（必选证据排名分布与 Recall@N 曲线）。补 `docs/EXPERIMENT_RUNBOOK.md`：GPU 机器从取代码、装依赖、下模型、预处理校验、建索引到 N/λ 扫描与判读规则的完整指令。**未提交任何实验结果**；`outputs/` 中的 CPU 预演结果仍为本地未跟踪产物。 | `16fc82a` |
| 5 | 2026-11-24T10:24:09 | feat(retrieval): add isolated four-way retrieval comparison | 新增独立 R01 实验包与一键脚本，按序比较 DPR、BM25+DPR、子问题 DPR、CWE 条目级检索；默认 N=20/50/100，共用既有 Reader/Top-K/MMR/答案流程。增加 20 项回归、实验方法文档和 40×4×3 CUDA 真实模型对照。最终运行 12 组/480 题零失败，DPR 与旧结果精确匹配；机器标注尚未人工复核，结果仍为探索性。 | `56208ff` |
| 6 | 2026-11-24T10:25:41 | docs(retrieval): record experiment commit and handoff | 更新 R01 实验主提交哈希及阶段交接状态，记录四方案实验已完成、提交待推送。 | `28277b2` |
| 7 | 2026-11-24T10:26:16 | docs(retrieval): record remote verification | 补记 R01 两个提交的远端推送与哈希核验结果；详见 HANDOFF。 | `a4dcc92` |
| 8 | 2026-11-26T15:37:33 | docs(step2): add the STEP2 cross-lingual route work order | 新增 `docs/theprompt_2.md`：交给远端实现会话使用的 STEP2 工作单，规定跨语言免翻译路线（Qwen3-Embedding-0.6B 检索 + 保留 MMR 筛选 + Qwen2.5-7B-Instruct 中文作答）、不可违反的 9 条约束、P0–P4 门禁指标、验证与完成定义、每次提交追加本表的规范、阻塞与诚实要求、明确不做的事。本提交只新增文档并补填第 7 行哈希，未改动任何代码、配置或实验产物。 | 见下 |
| 9 | 2026-11-26T16:19:25 | docs(step2): establish cross-session recovery baseline | 新建 `BASELINE_SPEC_V2.md`；追加 STEP2 小阶段计划、进度五类状态、交接记录和规格导航；在 v1 规格顶部增加 v2 链接；记录阶段 0 的分支、资源和 CUDA 自检结果。未修改代码、模型、数据、索引或输出产物。 | `f6d68e8` |
| 10 | 2026-11-26T16:23:27 | docs(step2): record recovery baseline remote verification | 记录 STEP2-DOC 提交 `f6d68e8` 已推送，以及本地 HEAD、跟踪分支与 `ls-remote` 三值一致；把下一步更新为 P0A 上游资源核验。 | 见下 |
| 11 | 2026-11-27T09:43:00 | docs(step2): refresh recovery state for resumed P0A | 更新 STEP2 当前硬件/磁盘/CUDA 自检记录、P0A 未跟踪文件状态和跨会话唯一下一步；保留 2026-11-26 历史环境记录。 | `69676b4` |
| 12 | 2026-11-27T09:58:00 | checkpoint(STEP2): incomplete - 7B weights pending ModelScope download | 新增独立 Qwen revision/LFS 校验与下载入口、资源配置和 7 项测试；记录 Qwen3 本地 LFS 校验结果、Qwen2.5-7B 上游分片元数据及被中断的下载状态。未提交模型文件。 | `6beb923` |
| 13 | 2026-11-27T10:35:00 | feat(step2): build and validate crosslingual Qwen index | 增加 Qwen3 原始向量索引编码/持久化/兼容校验/余弦检索及回归测试；真实构建 5748×1024 索引并在新进程验证中英文查询；记录两个模型真实推理探针。全套测试 169 passed；未提交权重、索引或 outputs。 | `758e5cf` |
| 14 | 2026-11-27T10:38:00 | docs(step2): record P0A P0B remote verification | 记录 P0A/P0B 提交 `758e5cf` 推送后本地 HEAD、远端跟踪分支与 `ls-remote` 三值一致，并登记 STEP2-P1A 唯一下一步。 | `eaafe9b` |
| 15 | 2026-11-27T10:45:00 | feat(step2): create unreviewed Chinese probe parallel set | 新增离线 Qwen2.5-7B 中文问题派生 CLI、字段/source hash 校验及 9 项回归；生成 40 条机器翻译平行记录并保留原英文标注字段。题集未经人工复核；源 `qa.v1.jsonl` 未修改。 | `2d8c197` |
| 16 | 2026-11-27T10:47:00 | docs(step2): record P1A remote verification | 记录 P1A 提交 `2d8c197` 已推送以及本地、远端跟踪分支、`ls-remote` 三值一致；指定下一步为 STEP2-P1B 双语检索门禁。 | `c5a9c4c` |
| 17 | 2026-11-27T10:55:00 | test(step2): measure bilingual retrieval gate | 新增独立直接编码双语检索指标/门禁 CLI 和测试；真实中英各 40 题 N=20/50/100 检索，记录 Recall@N、等价性、两两余弦与判读，逐题结果保存在忽略的 outputs。 | `4cedbca` |
| 18 | 2026-11-27T10:57:00 | docs(step2): record P1B remote verification | 记录 P1B 提交 `4cedbca` 的远端推送与三值哈希核验，并把唯一下一步更新为 P2A 适配既有 MMR。 | `a3bb949` |
| 19 | 2026-11-27T11:05:00 | feat(step2): adapt retrieval relevance to shared MMR selector | 新增 `crosslingual-rag-v2` MMR 配置与适配器，提供检索相关性归一化、pool-minmax/raw 冗余矩阵并调用冻结 `select_mmr()`；新增 7 项测试；全套测试 191 passed。 | `5d89c3c` |
| 20 | 2026-11-27T11:10:00 | docs(step2): record P2A remote verification | 记录 P2A 提交 `5d89c3c` 已推送且本地 HEAD、跟踪分支与 `ls-remote` 三值一致；登记 STEP2-P2B 为唯一下一步。 | `9c900ee` |
| 21 | 2026-11-27T11:15:00 | test(step2): compare bilingual MMR and retrieval top-k | 新增双语 MMR/Top-K 评测 CLI、两种 Sim 尺度和 11 档 lambda 配对评测及 bootstrap CI；真实 Qwen3 中英各 40 题运行完成，lambda=1 均与 Top-K 顺序一致；全套测试 194 passed。 | 见下 |
