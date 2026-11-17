# DPR Reader

`dpr.py` 已实现分批相关性评分、正文答案跨度与原文位置回查；输入完整 RetrievedPassage，输出 ReaderResult。详细规则、真实验证和限制见 [READER.md](../../../docs/READER.md)。

调用一次 `DPRReaderScorer(runtime).score(question, candidates)`，再以 `prepare_pool(result.candidates)` 准备完整池并供 `reader_topk` / `select_mmr` 共用。普通回答应复用已选候选上的 answer_span，不再次运行 Reader。
