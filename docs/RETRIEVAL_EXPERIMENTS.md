# 检索四方案独立对照（R01）

本实验比较原始 DPR 与三个独立检索改动。三个方案不叠加，不预设任何方案优于基线。
现有 `cyber_qa query`、`eval_probe.py`、`eval_retrieval.py`、DPR 索引和 baseline-v1 公式均保持原样。
新实现位于 `src/cyber_qa/experiments/`，只有新入口使用它。

## 一键运行

先按 [部署指南](DEPLOYMENT.md) 准备现有环境、模型、快照和索引。本机已有这些资源，直接在仓库根目录运行：

```bash
.venv/bin/python scripts/compare_retrieval.py --device cuda
```

默认依次在 N=20、50、100 下各跑 `dpr → hybrid → subquery → hierarchical`。
共 3×4×40=480 次问题流程，每次含一次 Reader 评分、两种筛选和普通回答。
CPU 用 `--device cpu`；默认 `auto` 自动选择设备。Windows 环境可用对应环境的
`python scripts/compare_retrieval.py --device cuda`，本轮没有验收 Windows。

只比较一个 N 或指定新的输出目录：

```bash
.venv/bin/python scripts/compare_retrieval.py --device cuda --n 20 --output outputs/retrieval-comparison-N20
.venv/bin/python scripts/compare_retrieval.py --device cuda --n 20 50 100 --output outputs/retrieval-comparison-new
```

输出目录必须不存在，已有目录会报错，重复运行默认生成新的 UTC 时间戳目录。
不需要下载额外模型、调用外部 API 或重新生成 DPR 向量；BM25 在内存中建表。
可用 `--qa`、`--snapshot`、`--index`、`--model-config`、`--model-root` 指向已有兼容资源。

## 四组方法及控制变量

| 名称 | 实际实现 | 检索输入 |
| --- | --- | --- |
| dpr | 原始 `DPRIndex.search`，未归一化内积与原同分规则 | 原问题 |
| hybrid | 原问题 DPR 与段落 BM25 各取前 L，等权 RRF 融合，去重取 N | 原问题；BM25 文本为标题＋正文 |
| subquery | 原问题 DPR＋规则拆分的两个子问题 DPR，等权 RRF 融合，去重取 N | 原问题与从其文本构造的子问题；不使用 BM25 |
| hierarchical | CWE 条目定位后从相关条目内取段落，并保留全库 DPR 名额 | 原问题；条目定位使用知识库编号、标题与 description |

所有组共用同一题集、快照、DPR 原始向量、Reader、K、λ、输入预算、尺度与排序规则。
默认 K=5、λ=0.5 未调优；允许 `--lam` 运行期统一覆盖，但不改写配置文件。
每个候选池只运行一次 Reader、一次完整池 min-max，供 Top-K 与 MMR 共用。
Reader 总是读取原问题，不读取子问题。普通回答复用原 `assemble_answer`。

**同 N 控制的是最终交给 Reader 的候选数，不是内部检索计算预算相同。**
不同方法需要的查询编码、BM25、条目定位时间实际计入检索耗时；模型一次加载，
各组不复用查询向量或 Reader 结果。固定顺序的单次耗时不能作为严格性能基准。

### 参数与确定性

新参数集中在 `RetrievalExperimentConfig`，随 manifest 保存，版本 `retrieval-ablation-v1`：

- 分支深度 `L=min(语料段数,max(N,branch_depth))`，`--branch-depth` 默认 100。
- RRF：`sum(1/(k+rank))`，rank 从 1 开始，`--rrf-k` 默认 60；不把 BM25 和 DPR 原始分数直接相加。
- BM25：k1=1.5、b=0.75、IDF=`log(1+(D-df+0.5)/(df+0.5))`，查询词只计一次。
  大小写统一，ASCII 字母/数字分词，连字符拆开，固定小型停用词表，不做 stemming。
  零分 BM25 文档不参与融合；完全无词匹配时回退到 DPR 排序。
- 融合分同分按 passage_id 字典序；原始 DPR 和筛选仍使用既有同分规则。
- `retrieval_score` 在所有组均保留**原问题 DPR 内积**；融合分另存 `ranking_scores`，
  `retrieval_rank` 是本方法最终候选顺序，不能将 RRF 分当 DPR 分或正确概率。

### 子问题规则的边界

仅在英文 `and + what/which/how/why/where/when/who` 处分成两部分，保留原问题。
第一部分成为子问题一；第二部分成为子问题二，并附第一部分作 Context，避免 `it` 丢失主题。
不拆 `architecture and design` 等名词并列，不使用评测 intent、模板、gold facts 或人工重写问题。
无法识别时严格回退到单次原始 DPR；生成查询超过 64 token 时跳过并记录原因，不截断原问题。
这是一种可复现、无需外部服务的初版子查询方案，不代表完整语义分解。

### 条目级检索的边界

1. 为每个 CWE 从实际知识库建立“编号＋标题＋description”文档，做 BM25 条目检索。
2. 原问题 DPR 对全库段落排序；按各条目最佳段落得分得到条目排名，避免按总分偏爱大条目。
3. 两个条目排名各截取至 L，等权 RRF；按分数及 CWE ID 确定前 M 个条目，`--entry-top-m` 默认 3。
4. 从预测条目的全部段落中按原问题 DPR 排序，最多占 `floor(min(N,语料段数)×0.75)` 个名额。
   余下名额从全库 DPR 补齐并去重；条目内不足也由全库补齐。比例用 `--focused-fraction` 设置。
5. 最终顺序先条目内候选、再全库补充；所有候选仍由同一个 Reader 重新评分。

**条目由问题和语料预测，不读取 QA 的 `record_ids`、`required_evidence_ids`、intent 或 gold facts。**
这些标注只在检索结束后用于计分。全库保底能减轻错误定位风险，但不能保证目标 CWE 被正确识别。

## 输出与判读

```text
outputs/retrieval-comparison-<UTC>/
├── manifest.json
├── archived-baseline/probe-eval-N*.json
├── dpr-N20.json / dpr-N20.jsonl
├── hybrid-N20.json / hybrid-N20.jsonl
├── subquery-N20.json / subquery-N20.jsonl
├── hierarchical-N20.json / hierarchical-N20.jsonl
├── ... N50、N100 ...
├── comparison.json
├── comparison.csv
└── comparison.md
```

- 先读 `comparison.md`：四组 Recall@N、全部必选证据入池率、两种筛选的 Recall@K/全覆盖率、耗时，
  以及相对同 N 基线的配对 bootstrap 差值与区间。
- `comparison.csv` 便于表格软件打开；`comparison.json` 包含单段/多段、intent 分组，
  微平均、Hit、标注 gold ID precision、事实支持段可用率、冗余、逐题胜负和 MMR 对 Top-K 的区间。
- 每方法 JSON 保存逐题候选、原文与来源、原始 DPR 分数、Reader 分数/跨度、完整 MMR 轮次、
  普通答案、子查询/跳过原因、条目预测及分阶段耗时。JSONL 每题落盘，异常退出仍保留已跑结果。
- manifest 保存 Git HEAD/工作区状态、Python 源码哈希、标注哈希与复核状态、索引元数据、
  模型 revision/权重哈希、环境/设备、实际参数、起止时间和已完成组别。完整输出不提交 Git。
- 原有 `outputs/probe-eval-N*.json` 只读并复制到归档目录，记录 SHA-256。默认 `--baseline-dir outputs`。
  新 DPR 结果与对应旧结果核对候选、gold ID、两种选择顺序和 Reader logit 差异。
  旧文件没有问题/模型哈希，数值一致不能补造历史运行来源。不存在旧文件时照常运行并记 not_available。
- 单题阶段失败会记录原因并继续剩余问题；可启动后，汇总将失败题按零计入完整分母，同时禁用该组配对区间。
  最终状态 `completed_with_failures`、退出码 1。模型/索引初始化失败会保留 manifest；命令行参数、配置或输出路径在初始化前出错则由 argparse/filesystem 直接报错。

**评测边界**：Recall 按指定段落 ID 计分；低 gold ID precision 不等同内容无关。
`annotated_fact_support` 仅表示每条 fact 至少一个标注支持段入池/入选，不评判答案是否表达了该事实。
普通回答仍是单跨度抽取，`answer_quality=not_assessed`。bootstrap 2000 次、固定 seed=20261123，
区间未做多重比较校正。探针集当前为机器草稿；不能据此宣称正式准确率或完成参数调优。

## 验证

```bash
.venv/bin/python -m pytest -q
.venv/bin/python scripts/compare_retrieval.py --device cuda --output outputs/retrieval-comparison-v1-final
```

真实运行：`.venv/bin/python scripts/compare_retrieval.py --device cuda --output outputs/retrieval-comparison-v1-final`；
产物位于忽略目录 `outputs/retrieval-comparison-v1-final/`，stdout/stderr 重定向至同级日志。
Python 3.12.11、CUDA RTX 4090、40 题机器草稿、每组 0 失败，四方案×N20/50/100 共 12 组；
全套 155 passed。新 DPR 三个 N 均与历史池/选择一致且 Reader logit 最大差异为 0。
准确指标、模型/权重/索引哈希和未人工复核限制见 [PROGRESS](PROGRESS.md)、[HANDOFF](HANDOFF.md)
以及该运行目录的 manifest/comparison 文件。
