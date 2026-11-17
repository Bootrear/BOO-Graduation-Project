# P06 Reader 对齐与原文跨度

入口：`cyber_qa.reader.dpr.DPRReaderScorer(runtime).score(question, candidates, batch_size=8)`。
返回不可变 ReaderResult；候选保留 passage、原始检索向量、排名和 retrieval_score，另存 reader_relevance_logit、reader_start_logits、reader_end_logits、answer_span/span_score。两策略共用 `prepare_pool(result.candidates)`；归一化只在完整池准备时执行，Reader 本身不归一化、不重复为策略推理。

## 输入与答案规则

沿用 P03 InputBudget：问题最多 64 token，超长拒绝、不截断；标题前 64 token，保留完整原始标题并记录原始/使用数量和 title_truncated；正文最多 189 token，不截断。Reader 总上限 512。真实 tokenizer 的布局为 `[CLS] question [SEP] title [SEP] body`，无尾部 SEP。分别调用同一 Reader tokenizer 得到正文 offset_mapping，手动组装相同布局。每条输入保存 ID、token IDs、正文字符偏移、各部分长度；padding 只进入批次张量，不进入候选保存的 logits。

只允许正文中非特殊 token 的连续跨度；问题、标题、分隔标记、正文中的特殊 token（含 UNK/PAD）和 padding 不得进入答案，也不得跨越这些位置。字符起点包含、终点不包含，token 起止都包含。答案直接切片 passage.text，不通过 decode 重新拼写；Unicode、大小写与标点保留原文。source_text、source_locator 和快照仍随 passage 保留。

P06 根据已安装 transformers 4.57.1 的 DPR tokenizer `_get_best_spans`/`decode_best_spans` 核查：span_score 为 start_logit + end_logit，默认最大跨度 64 token。本项目在 `ReaderConfig` 冻结这些规则，同分按 start_token、end_token 升序。span_score、relevance_logit、retrieval_score 互不混合，均不是正确概率。没有合法正文 token 时返回空跨度及 `no_valid_passage_tokens`；语义充分性和普通回答回退由 P07 单独处理。

## 对齐与异常

每批严格检查 relevance `(batch,)`、start/end `(batch, padded_width)`；不使用 squeeze；全部输出含 padding 必须有限。单候选保持一维 relevance。按当前输入行把分数、跨度与完整候选绑定，再任意重排完整记录。相同 ID 的完全相同候选只计算一次，冲突重复、混合快照、非法排名/检索分数、零/非有限向量、超预算及异常输出均记录错误并使查询失败，不返回部分正常结果。

模型延迟加载、eval/inference_mode、权重/revision 校验复用 P05 DPRRuntime。ReaderResult 分开记录模型加载增量时间和 tokenization/forward/后处理时间；后者不代表稳定性能基准。

## 实测验收（2026-11-17，北京时间）

```bash
.venv/bin/python -m pytest -q
.venv/bin/python scripts/check_dpr_reader.py --device cuda --output outputs/p06-reader.json
```

- 全套 **119 passed in 4.54s**，无 skip；新增 20 项 Reader 回归。测试 fixture 首轮形状预期及 Passage 构造错误已修复，未放宽生产契约。
- 固定 CWE 4.20 / 5748 段索引、固定 single-nq 权重、RTX 4090。最初两候选探针：relevance `(2,)`、start/end `(2,48)`。
- SQL injection 查询真实 20 候选：批次 `(8,187)/(8,127)/(4,78)`。全部候选单条推理、反序跨批推理与正常批次的 relevance/start/end 对齐（rtol=1e-4，atol=2e-4）；跨度位置与原文字节字符串相同，span_score atol=4e-4。
- 全部 20 条跨度切片/有效位置/长度验证通过，两策略共用完整池，真实分数 MMR 与参考实现相等，原始向量未改变。
- 本次 Reader 处理 0.0641s，Reader 加载 0.8378s，仅一次样本；验收脚本额外 forward 是对齐比较，不是线上每策略重复评分。
- 首位 Reader 记录来自 CWE-564 potential_mitigations，跨度 `non-SQL style database`，字符 `[35,57)`，token `[20,24]`，span_score 2.794670820236206。它不是 SQL injection 的定义；此验收证明对齐与追溯，不证明语义正确或校准。P07/P09 必须如实保留该质量限制。
- pip check、compileall、脚本 help、旧 DSES 示例及原始输入哈希通过。完整日志/产物在忽略路径 outputs/p06-reader.*，不上传权重/数据/索引。

P06 真实 Reader 推理已通过；后续普通回答/完整 CLI/P09 验收见 ANSWERING.md、CLI.md、ACCEPTANCE.md。
