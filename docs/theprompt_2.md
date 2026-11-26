```text
=== 提示词开始 ===

# 任务：新建分支实现「中英跨语言免翻译」技术路线（STEP2）

## 0. 先恢复上下文，再动手

严格按 AGENTS.md 的恢复顺序完整读取：
AGENTS.md → docs/BASELINE_SPEC.md → docs/IMPLEMENTATION_PLAN.md → docs/PROGRESS.md
→ docs/HANDOFF.md → docs/COMMIT_LOG.md → docs/EXPERIMENT_RUNBOOK.md
→ docs/RETRIEVAL_EXPERIMENTS.md → data/annotations/probe-v1/README.md

然后检查并记录：`git status --short`、`git branch -vv`、`git log --oneline -5`、`git remote -v`。
确认工作区干净、当前在 `step1/dataset-optimization` 且与 origin 同步。

发现未提交改动或未跟踪文件，**先报告，不要自行清理、不要 stash、不要丢弃**。

---

## 1. 背景

已完成的资产（**全部不可改动**）：

- **英文基线（P00–P10）**：DPR single-nq 召回 → DPR Reader 打分 → Reader Top-K / MMR →
  抽取式答案。`baseline-v1` 的公式与参数**已冻结**，有 155 项测试和 12 题真实端到端验收。
- **probe-v1**：40 题探针集（A12/B8/C8/D4/E8，40 个不同 CWE），`auto_drafted_needs_human_review`，
  **机器起草、未经人工复核**。
- **R01**：四方案检索对照（dpr/hybrid/subquery/hierarchical × N20/50/100，480 次流程），结果在 PROGRESS.md。

已知事实（**不要重新推导，也不要美化**）：

| 事实 | 数值 |
| --- | --- |
| DPR 检索瓶颈 | 必选证据 Recall@20 = 27.5%，中位排名 23 |
| BM25+DPR 可把召回拉到 | 73.75%（N=20）/ 91.25%（N=100），但未转化为最终收益 |
| MMR vs Reader Top-K | 40 题 0 胜 0 负 40 平，但策略分歧 order 29/40 |
| 池内冗余极高 | 平均两两余弦 ≈ 0.857 |

---

## 2. 目标与技术路线

用户已确定模型选型，**不得替换**：

```
中文问题（或英文问题）
        │  不翻译
        ▼
Qwen3-Embedding-0.6B 跨语言向量检索 ── 5748 段英文 CWE 段落
        │  召回 N=20
        ▼
MMR 证据筛选（保留 MMR，相关性来自检索相似度）
        │  K=5
        ▼
Qwen2.5-7B-Instruct 读英文证据、用中文作答 + 编号引用
        │
        ▼
引用校验 + 英文原文并排展示
```

**唯一目标**：让中文用户在不经过任何机器翻译的前提下，得到可读的中文答案，
并且每句话都能追溯到英文原文的具体段落。

---

## 3. 不可违反的约束

1. **整条链路不得出现任何翻译/机翻/翻译 API**。中文由作答模型直接基于英文证据生成。
2. **不得修改**：`configs/baseline-v1.json`、`src/cyber_qa/selection/mmr.py`、
   `src/cyber_qa/reader/`、`src/cyber_qa/retrieval/dpr.py`、`data/processed/dpr-index-v1/`、
   `scripts/eval_probe.py`、`scripts/eval_retrieval.py`、`scripts/compare_retrieval.py`、
   `data/annotations/probe-v1/qa.v1.jsonl`、以及 R01 的实验代码。
   它们是英文对照臂和历史结论的依据。
3. **不得删除或降级英文抽取路径**。普通模式必须继续可用——它是"输出是原文子串、
   结构上不可能编造"的唯一保证，也是本课题的核心卖点。
4. **`Rel` 与 `Sim` 必须来自同一向量空间**（都用 Qwen3-Embedding 的余弦）。
   禁止把检索相似度与 Reader logit 混用做 MMR。
5. **不得用 LLM 做相关性打分或任何筛选依据**。筛选只由 MMR 决定，保证可复现、可解释。
6. **不得复制第二份 MMR 实现**。逐轮选择逻辑必须复用现有 `select_mmr()`，
   只允许替换"相关性的来源"。
7. **不得声称 MMR 优于 Top-K**，除非配对 bootstrap 的 95% 区间不含 0。
   差异不显著时必须如实写"无显著差异"。
8. **不得把 probe-v1 的 40 题结果当作论文测试结果**，所有指标必须标注为探索性诊断。
9. 不得强推、不得破坏性重置、不得丢弃用户改动。

---

## 4. 实现范围与自由度

**文件组织、模块划分、函数签名、类名由你决定**，但需满足以下原则：

- 新增代码按职责分包，放在 `src/cyber_qa/` 下与现有风格一致的位置；
  脚本放 `scripts/`，配置放 `configs/`，测试放 `tests/`，说明放 `docs/`。
- 新增入口**不得改变既有 CLI 与既有脚本的行为**；新功能走新命令/新参数。
- 模型权重、索引、`outputs/` 一律不入库（沿用现有 `.gitignore`）。
- 新增依赖单独固定版本（如 serving 侧另建 requirements 文件），**不得改动
  `requirements-inference.txt` 的现有约束**。

功能上需要覆盖（如何拆分由你判断）：

1. **跨语言检索**：加载 Qwen3-Embedding-0.6B，对 5748 段英文段落建向量索引并支持加载校验；
   中文/英文问题都能直接编码检索，**不做翻译**。
2. **证据筛选**：保留 MMR，把相关性项换成检索相似度；其余（逐轮更新、同分规则、
   去重、K、归一化 epsilon）与现有实现保持一致。
3. **中文作答**：英文证据 + 编号 → 中文答案 + 编号引用；输出结构可序列化，含证据原文与来源。
4. **引用校验**：**必须是确定性代码**，不能靠 LLM 自评。至少覆盖：编号是否越界、
   有无不含编号的陈述句、被引段落与该句是否有词面重合（弱检查）。
5. **LLM 客户端**：固定 `temperature=0`、`top_p=1`、`max_tokens`，固定模型 revision，
   记录原始响应、prompt 哈希、token 数、延迟、服务端返回的真实模型标识。
6. **资源获取与校验**：下载两个模型时沿用现有"上游 LFS 大小 + SHA-256"的校验思路，
   不允许只凭本地自记哈希。
7. **评测脚本**：支持按语言（中文/英文）、N、λ 切换，输出与现有 `eval_probe.py` 同口径的指标，
   以便与历史结果直接对照。
8. **中文平行题集**：从 `qa.v1.jsonl` 逐条翻译 `question` 字段，
   `passage_id`、`gold_facts`、`required_evidence_ids`、`optional_evidence_ids`、
   `source_snapshot` **一律不变**；新增标记字段说明是翻译稿、未经人工复核。
9. **测试与文档**：新组件都要有回归测试；写一份路线说明文档（方法、契约、参数、指标、限制）。

### 几个必须守住的技术判断

- **相关性来源**：检索相似度必须显式传入筛选阶段，**不得从 Reader 字段隐式读取**，
  以免与 v1 混淆。相关性对完整候选池只做一次 min-max，`d <= 1e-12` 时全部为 0，
  非有限值或溢出必须失败。
- **两项尺度**：`Rel` 与 `Sim` 都落在 [0,1] 且必须可比。实测若发现 `Sim` 明显高于 `Rel`
  导致惩罚项压死相关性，你需要实现并对比两种处理，并在文档中报告：
  （a）`Sim` 也做池内 min-max；（b）保持原始余弦、上调 λ。**默认取（a），但（b）的
  λ 敏感性曲线也要跑出来。**
- **配置版本**：新配置必须是新版本号，**不能**写 `baseline-v1`（v1 字段在
  `__post_init__` 里被冻结）。
- **自检断言**（写成测试）：`λ=1.0` 时选择顺序与按检索分数排序的 Top-K **完全一致**；
  空池、K=0、候选不足 K、单候选、全同分、NaN/Inf、零向量都要有明确行为。
- **LLM 提示词**必须包含四条硬约束：只用给定证据、用简体中文、每句标 `[n]`、
  证据不足时明说"现有资料无法确认"。CWE 编号与技术术语保留英文。

---

## 5. 执行阶段与门禁

### P0 资源与索引
下载并校验两个模型；为中英文都能编码的检索器建好索引。
记录模型 revision、权重 SHA-256、维度、度量、索引哈希。

### P1 检索替换（**决定性门禁**，1–2 天内应出结果）

用同一批题、同一快照，比较新旧检索器：

| 指标 | 门禁 |
| --- | --- |
| 英文 Recall@N（对比 DPR 的 27.5% / 43.75% / 50.00%） | 不低于 DPR 的 90% |
| **中英等价性** = mean(Recall@N 中文) / mean(Recall@N 英文) | **≥ 0.85** |
| 池内平均两两余弦 | 报告并与 0.857 对比 |

**等价性 < 0.60 时停止后续阶段**，把数字与失败分析写进文档并报告阻塞，不要强行继续。

### P2 MMR 与筛选评测
在同一候选池下比较 MMR 与 Top-K：Evidence Recall@5、全覆盖率、Hit@5、逐题胜负、
池内与选中集合冗余度、策略分歧、配对 bootstrap 95%CI。
λ 从 0.0 扫到 1.0，**中英文各跑一遍**——否则无法区分"中文掉点"和"换检索器掉点"。
λ 只在开发语义下选；`λ=1.0` 必须与 Top-K 完全一致。

### P3 中文作答端到端
至少 10 道题完整走通：中文问题 → 跨语言检索 → MMR → Qwen2.5-7B 中文作答 → 引用校验。
报告引用有效率、无引用陈述率、弱支持率，并人工抽查 10 条核对引用是否真的支持该句
（只记录事实，不夸大）。

### P4 文档与收尾
更新路线文档、`docs/PROGRESS.md`（新增小节 + 北京时间时间线）、`docs/HANDOFF.md`
（当前分支、哈希、唯一下一步）、`docs/README.md`、`README.md`、`scripts/README.md`、
`data/annotations/README.md`。

---

## 6. 验证与完成定义

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q src scripts
git diff --check
```

加上：新旧评测脚本的 `--help`、索引与模型的加载校验、旧脚本仍可正常运行。

全部满足才算完成：

1. 新分支已推送，远端哈希与本地一致。
2. 中文问题端到端可跑，链路中无任何翻译调用，产出中文答案 + 引用 + 校验结果。
3. MMR 与 Top-K 在中英文下都有配对比较结果，含 95%CI。
4. 中英等价性数字已产出并写进文档；若 < 0.60 已按要求停止并报告。
5. `pytest` 全绿、`compileall` 通过、`git diff --check` 通过。
6. 文档更新完整：路线、契约、参数、指标、门禁结果、限制。
7. **英文 v1 路径未被破坏**：旧测试全过、旧脚本仍可运行。

---

## 7. 提交规范（每次提交都必须执行）

### 7.1 只提交本任务相关文件
不得提交模型、数据、索引、日志、`outputs/`。暂存前先 `git status --short` 逐项确认。

### 7.2 每次提交都要在 `docs/COMMIT_LOG.md` 追加一行

这是用户的硬性要求，**每个提交都要做，不能跳过，不能改写已有行**：

1. 在表格**末尾新增一行**，列为：
   `#` | `提交时间（+08:00）` | `任务名称` | `主要做了什么` | `提交哈希`
2. 「主要做了什么」只写可核对的事实，不写未验证的结论。
3. **哈希列**：提交无法把自己的哈希写进自己的内容，所以最新一行填「见下」，
   由**下一次提交**补填；也可用 `git log --oneline` 查。
4. **时间必须与 `git log` 一致**。做法：先定一个时间字符串 `T`，先写进记录表，
   再用同一时间提交：

```bash
GIT_COMMITTER_DATE="$T" git commit --date="$T" -m "<message>"
git log --format="%h|%cI|%s" -1     # 核对提交时间与记录表一致
```

5. 每次提交（包括 checkpoint、fix、docs）都要追加行，**不要只记录主提交**。

### 7.3 推送并核验

```bash
git push -u origin step2/crosslingual-rag
git fetch origin step2/crosslingual-rag
git rev-parse HEAD
git rev-parse origin/step2/crosslingual-rag
git ls-remote --heads origin step2/crosslingual-rag
```

三个哈希必须一致。**不得强推。**

---

## 8. 阻塞与诚实要求

| 情况 | 处理 |
| --- | --- |
| 显存不足 | 先降 batch size；仍不足则 7B 用 AWQ 4bit；**不得静默换成更小的模型** |
| 模型下载失败 | 重跑续传；连续失败则记录 revision 与错误摘要，提交 `checkpoint(STEP2): incomplete - <原因>` |
| 中英等价性过低 | 停止 P2/P3，写清数字与失败分析，报告阻塞 |
| 新依赖冲突 | 单独建 requirements 文件，不改 `requirements-inference.txt` |
| 无法访问外网 | 记录缺失资源与恢复命令，不伪造结果 |

**绝对禁止**：
- 用模拟模型或合成数据替代真实推理后宣称通过
- 用中文结果掩盖英文退化
- 把未跑通的阶段标记为完成
- 修改已冻结的 v1 公式或历史实验结论
- 跳过或漏记 `docs/COMMIT_LOG.md`

---

## 9. 明确不做的事

- 不做模板档 / 离线中文预生成包（下一阶段）
- 不做前端与 API 服务
- 不做中文题集的人工复核（只标注 `not_reviewed` 并如实报告）
- 不改 MMR 的 K、同分规则、逐轮更新逻辑
- 不引入第二套 LLM 或第二个检索模型做 ensemble
- 不把 40 题结果写成论文结论

===
```
