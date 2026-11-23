# probe-v1：40 题探针集（MMR 可分辨性验证）

**这批题不是正式数据集。** 它是用来回答一个问题的 40 道探针：

> 在"需要多段证据"的题型上，MMR 到底能不能赢 Reader Top-K？

如果这 40 题上 MMR 也打平，说明方法假设有问题，**先改方向，不要继续做正式 120 题**
（依据见 `docs/` 中现有冒烟结论：原 12 题 100% 只考 `description` 一个字段，
在数学上不可能体现 MMR 的价值）。

- `split` 一律为 `probe`，**不属于**正式开发集 80 / 冻结测试集 40，不参与调参记账。
- 全部 40 题取自 **40 个不同 CWE 条目**，避免跨题泄漏。
- 生成的 `skeleton.jsonl` 不含问题文本与 gold facts —— 这两项是标注的核心判断，必须人工填写。

## 文件

| 文件 | 内容 | 需要手改吗 |
| --- | --- | --- |
| `skeleton.jsonl` | 40 条骨架：条目、模板、answer_type、候选段落 ID | **是**（填 question / required / optional / gold_facts） |
| `passage_index.json` | 219 个候选段落的可读索引（字段、定位器、词数、原文预览、内容哈希） | 否 |
| `manifest.json` | 生成清单：快照、条目列表、文件哈希 | 否 |

重新生成（确定性，同一输入产生逐字节相同的 `skeleton.jsonl`）：

```bash
py scripts/make_probe_skeleton.py --out data/annotations/probe-v1
```

## 40 题构成

| 模板 | 题数 | 题型 | 跨越的字段 | 目的 |
| --- | --- | --- | --- | --- |
| **A** | 12 | `cause_and_consequence` | description ↔ common_consequences | 主战场：成因 + 后果 |
| **B** | 8 | `consequence_and_detection` | common_consequences ↔ detection_methods | 后果 + 检测 |
| **C** | 8 | `detection_and_mitigation` | detection_methods ↔ potential_mitigations | 检测 + 缓解 |
| **D** | 4 | `mitigation_by_phase` | potential_mitigations（同字段不同 Phase） | 高风险对照，单独统计 |
| **E** | 8 | `field_comprehension` | 单个非 description 段 | 对照：Top-K 应当赢 |

选条目时的三条硬约束（脚本自动保证）：

1. 至少 3 个不同字段 —— 才有可能出跨字段题。
2. 竞争字段至少 2 个兄弟段 —— 让 Top-K 的 5 个名额有被同类段占满的风险。
3. 每个候选段 ≤ 120 词 —— 保证单块成段，`passage_id` 可离线算准。

---

# 一、怎么填 `question`（问题文本）

## 硬性要求

| 要求 | 原因 |
| --- | --- |
| **英文** | DPR 使用 `facebook/dpr-*-nq-base` 英文模型；中文题召回会失效（需另行验证） |
| **问的必须是"那几段里写着的"** | 标完必须能用必选证据答出来；不能问原文没有的推论 |
| **不出现字段名** | 不要写 "according to Common_Consequences…"；用户不会这么问 |
| **一题只问一件事** | 两个不相干的子问题会让 gold_facts 无法判分 |
| **≤ 64 token** | [chunking.py](../../../src/cyber_qa/data/chunking.py#L16) 规定超长问题直接拒绝查询，不截断 |

## 句式公式

```
模板 A（成因 + 后果）
  How does <weakness> arise, and what <具体后果> impact can it have?
  How does <weakness> occur, and what can an attacker accomplish?

模板 B（后果 + 检测）
  What <影响> can <weakness> cause, and how can it be detected?
  If <某后果> happens, what techniques reveal it?

模板 C（检测 + 缓解）
  What methods detect <weakness>, and how should it be fixed?
  Once <weakness> is detected, which mitigations apply?

模板 D（同字段不同阶段）
  How should <weakness> be mitigated during <阶段一> versus <阶段二>?
  （阶段名取自文献里的 Phase 值，如 Architecture and Design / Implementation / Operation）

模板 E（单段）
  What <具体对象> does <字段> describe for <weakness>?
  Which detection technique targets <weakness>?
```

## 正例 / 反例

| 判定 | 例子 | 原因 |
| --- | --- | --- |
| ✅ | `How does SQL injection arise, and what authentication-related impact can it have?` | 两问各对应一个字段，后果限定为 authentication，能落在 Consequence[3] |
| ❌ | `What is SQL injection?` | 单段题，Top-K 必赢，浪费一个探头 |
| ❌ | `How dangerous is SQL injection and how do I secure my PHP app?` | 第二问依赖具体技术栈，CWE 原文不保证覆盖 |
| ❌ | `According to the Common Consequences field, what happens?` | 泄漏了知识库结构，真实用户不会这样问 |
| ❌ | `What are the causes, consequences, detection methods, and mitigations of SQL injection?` | 一次问四件事，无法用 2 段证据判对 |

## 写完自问三句

1. 只用我选的必选证据，能不能答出来？
2. 不看必选证据，有没有别的段也能答对？→ 有就补进 `optional_evidence_ids`
3. 这题需要 ≥2 段吗？还是 1 段就够？→ 1 段就是错的模板，换条目

---

# 二、怎么填 `gold_facts`（判分的地基）

`gold_facts` 是**打分时唯一的依据**。写不好，整套实验就退化成"看哪个答案顺眼"。

## 定义：一条 gold fact 必须是

> **一句能被原文某一句话直接证实、且不写出来就算答错的原子陈述。**

- 一条 fact 只讲**一个**事实
- 必须是**原文能支撑**的（`supported_by` 指向具体 passage）
- 不能是同义反复（`SQL injection is a security problem` 不算）
- 不能是常识（`databases store data` 不算）
- 不要求与原文措辞一致，但**不得加入原文没有的前提**

## 结构

```json
{
  "fact_id": "f1",
  "text": "the product constructs a SQL command from externally-influenced input",
  "supported_by": ["cwe-passage:8ff28e34..."]
}
```

- `fact_id`：题内唯一，`f1` `f2` …
- `text`：小写英文短语或短句；**判分时按"是否被答案覆盖"人工核验**，不做字符串精确匹配
- `supported_by`：必须是 `required_evidence_ids` 或 `optional_evidence_ids` 里的 ID

## 正例 / 反例（同一个条目 CWE-89）

| 判定 | gold fact | 原因 |
| --- | --- | --- |
| ✅ | `the product builds a SQL command from externally-influenced input` | 单一事实，原文可直证 |
| ✅ | `an attacker can gain privileges or assume identity` | 单一事实，落在 Consequence[3] |
| ✅ | `parameterized queries prevent injection` | 单一事实，落在某条 Mitigation |
| ❌ | `SQL injection is a critical vulnerability` | 原文没做严重性判断，属外部知识 |
| ❌ | `it is dangerous` | 没有可核对的具体内容，无法判分 |
| ❌ | `the product builds SQL commands and attackers can read or modify data` | 两个事实挤在一条，无法给分粒度 |
| ❌ | `attackers often use SQLMap` | 常见但不是 CWE 原文陈述，属编造 |

## 数量

| 模板 | gold_facts 条数 | 说明 |
| --- | --- | --- |
| A / B / C | **2–3 条**，且**必须每条覆盖不同 evidence** | 这是 MMR 与 Top-K 拉开差距的地方：漏一段就少一条 fact |
| D | 2 条 | 两个阶段各一条 |
| E | 1 条 | 单段即可 |

**关键：多段题的两条 fact 必须分别落在两段证据上。** 如果两条 fact 都来自同一段，
那这题实际上还是单段题，MMR 又白测了。

## 自检清单（每题过一遍）

- [ ] 每条 fact 都能在 `supported_by` 指的那段里找到依据
- [ ] 不同 fact 覆盖不同 evidence
- [ ] 没有一条 fact 需要原文之外的推理
- [ ] 答题者只写出一条 fact 就应被判为"部分正确"，不是"全对"

---

# 三、怎么定 `required_evidence_ids` / `optional_evidence_ids`

`candidate_pool` 已经给好了候选（3–6 个真实 `passage_id`），用 `passage_index.json` 查
每个 ID 是什么：

```bash
py -c "
import json
idx = json.load(open('data/annotations/probe-v1/passage_index.json', encoding='utf-8'))['passages']
for pid in ['cwe-passage:...']:
    p = idx[pid]
    print(p['field_name'], '|', p['source_locator'], '|', p['words'], 'w')
    print('   ', p['preview'][:160])
"
```

- `required_evidence_ids`：**答对这道题必须具备**的段，**2–3 个**。少一个就应当扣分。
- `optional_evidence_ids`：能补充但不必须的段，**0–2 个**。
- 两者都只能从 `scaffold.candidate_pool` 里挑，不要手写新 ID。
- 挑完后把 `scaffold` 整个字段删掉（它是脚手架，不属于正式 schema）。

## E 模板额外要填

```json
"answer_span": {
  "quote": "Automated Static Analysis - Source Code",
  "start_char": 0,
  "end_char": 40
}
"answer_variants": ["static analysis of source code", "automated source code analysis"]
```

- `quote` 必须是该段 `preview` 里的**连续子串**，一个字都不能改
- `start_char`/`end_char` 是该子串在这段 `text` 里的字符区间（左闭右开），可用
  `text.find(quote)` 得到
- `answer_variants` 是**人类可接受的等价说法**，用于人工判分参考，不做字符串匹配

---

# 四、三条铁律

| 铁律 | 违反的后果 |
| --- | --- |
| **标注时不要看模型输出** | 会不自觉地出"模型刚好能答的题"，探针失去意义。先标完 40 题、提交冻结，再跑模型 |
| **只用 ≤120 词的段** | 更长的段会被预处理器切块（`chunk_index > 0`），`passage_id` 就不是这里给的值 |
| **多段题的两条必选证据语义不能太像** | 太像时 MMR 会主动去重掉第二段，你会得到"MMR 更差"的假结论。挑完比对两段 preview |

## 关于 `passage_id` 的可信度

本目录的 ID 是按 [contracts.py](../../../src/cyber_qa/data/contracts.py#L168-L172) 的冻结公式
在 `chunk_index = 0` 假设下算出的，已用 `baseline_smoke.v1.json` 的 12 条标注做过
**12/12 逐字节核对**。

**首次预处理完成后必须再核对一次**（因为 `chunk_index` 假设依赖真实分词器）：

```bash
py scripts/verify_probe_ids.py --passages data/processed/cwe-v1/passages.jsonl
```

校验不通过的 ID 用 `passages.jsonl` 里的真实值替换，并在 `manifest.json` 记录修正次数。

---

# 五、标完之后

1. 把 40 题的 `status` 从 `skeleton` 改成 `reviewed`（未请他人复核则写 `source_text_checked`，
   不要虚构独立复核）。
2. `annotator` 填真实姓名；`reviewer` 未复核就保持 `null`。
3. 冻结文件哈希，写进 `manifest.json`。
4. 跑门禁三指标（需环境就绪）：

| 指标 | 判读 |
| --- | --- |
| **Evidence Recall@5**：MMR vs Top-K，配对比较 | MMR 显著更高 → 继续扩到正式 120 题 |
| **池内平均两两余弦** | < 0.3 → 池里没冗余，MMR 惩罚项无感，需重新设计 |
| **两策略 selected_order 差异题数** | 0 题不同 → MMR 完全没生效，先查实现 |

判读规则见 `experiments/README.md`。**差异 < 5% 且不显著时停下来重新想方向，不要继续堆题量。**
