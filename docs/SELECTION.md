# 统一尺度与逐轮证据筛选（P04）

核心实现：`src/cyber_qa/selection/mmr.py`。CLI、Reader 输出和实验后续均调用此实现，不能复制一套归一化或 MMR。

`data/candidates.py` 将 passage、原始 DPR 向量、retrieval_rank/score、Reader logit、答案字符/输入 token 位置及 span_score 放在同一不可变记录中。字符 end 为开区间、token end 为闭区间；答案文本必须等于 passage.text 对应片段。重排移动整个记录，避免文本/向量/跨度错位。

## 固定规则

- `prepare_pool` 对完整候选按 passage_id 去重。相同完整记录可重复输入但只保留一份；同 ID 内容/评分等不一致则显式失败。按 retrieval_rank、passage_id 形成确定性池顺序。
- `normalize_relevance` 用 Python 双精度浮点，对完整池计算一次 min-max。d>1e-12 时 (r−min)/d，否则全部为 0；包括单候选。原始分数始终保留。非有限值或差值溢出记录错误并失败。
- `similarity_matrix` 创建向量归一化副本，不改动 DPR 原始向量。余弦先裁剪到 [-1,1]，再 max(0,cos)。用 hypot 求范数、fsum 点积；维度不一致、NaN/Inf、零/非有限范数均记录并失败。
- `reader_topk` 按原始 Reader logit 降序，同分按 retrieval_rank 升序、passage_id 字典序。
- `select_mmr` 初始冗余 0；每轮以 λ×归一化相关性−(1−λ)×当前最大冗余选择一项，再对全部剩余候选更新最大值。即使得分为负，也选至 min(K,len(C))。
- MMR 同分按原始 Reader logit 降序、retrieval_rank 升序、passage_id 字典序。无额外“近似同分”容差。λ=0 首轮依此选首段；λ=1 与 Reader Top-K 一致。
- 每轮日志包含轮次、选择前 ID、所选 ID、原始/归一化相关性、最大冗余及对应已选 ID、MMR 分数。冗余并列时保留最早被选的对应段；首轮无对应段，记录 null。
- 两策略接收同一个 PreparedPool；筛选内部不重跑 Reader、不重新归一化。

这些分数不是答案正确概率，也不构成校准过的证据充分性判据。

## 验证证据

`tests/test_mmr.py` 共 21 项通过；整个仓库共 73 项通过（含真实 tokenizer 测试）。
指定 A/B/C 例子中归一化为 1、0.5、0，第一轮选 A；第二轮 B 得分 −0.245、C 得分 −0.05，因此 MMR 选 A/C，而 Top-K 选 A/B。

覆盖空池、K=0、不足K、λ端点、同分确定性、去重与冲突拒绝、负余弦、极小差值、非有限值、零向量，以及候选重排后完整记录对齐。固定种子随机生成 80 组候选，将增量实现与每轮直接遍历已选集合的 `select_mmr_reference` 比较，选择顺序、分数及日志完全相同。

```bash
.venv/bin/python -m pytest -q tests/test_mmr.py
.venv/bin/python -m pytest -q
```

本阶段为数学与候选契约验证；尚未把真实 DPR/Reader 输出接入，不能冒称真实模型或端到端验收。
