# P07 普通回答规则

入口 `assemble_answer(selection, candidate_count, config)` 只接受最终 SelectionResult；不召回、不调用 Reader，也不读取未选候选。规则集中于 `config.AnswerConfig` 和 `answering/ordinary.py`。

1. 在已选证据内，按原始 Reader relevance_logit 降序、retrieval_rank 升序、passage_id 字典序选择有合法跨度的首段。span_score 仅用于 P06 同一段内选择跨度，不参与跨段混合评分。输出 `extractive_answer`、原文抽取、证据 ID、完整段落上下文及来源/快照。原始跨度位置留在对应证据记录。
2. 已选证据都没有有效跨度时，按同一顺序展示首段原文，类型 `related_text`，原因 `no_valid_answer_span`。
3. 无候选时返回 `insufficient_information/no_candidates`；有候选但无已选证据（如 K=0）返回 `insufficient_information/no_selected_evidence`。
4. 处理失败用 `failed_answer(reason)` 返回 `processing_failure` 与具体阶段/原因，不捏造答案或证据。

`candidate_shortfall` 单独表示候选数量小于 K，不触发“证据充分”的判断。有合法跨度仅代表结构合法，**不能证明它回答了问题**。正常抽取或原文输出始终标记 `evidence_sufficiency=not_assessed`、`uncalibrated_structural_rules_only`。不使用跨问题 logit 阈值或伪概率；语义充分性、综合题适用性和正式质量评估仍待后续核验/校准。失败记录的数量为 0 且不报告 shortfall，完整查询阶段状态由 P08 运行记录提供。

## 验证

`.venv/bin/python -m pytest -q`：**125 passed in 4.49s**，新增 6 项回答回归，覆盖未选 B 不得取代 MMR 已选 A/C、排序与 span_score 分离、同分规则、三类回退、候选不足与充分性分离、异常输入。

复用本地 P06 保存的真实评分/选择结果完成回答装配，两策略返回 `non-SQL style database` 且 evidence_id 属于各自选择集合，语义充分性为 not_assessed。此次仅是已有真实结果的装配检查（重建对象的向量占位未用于任何筛选/推理），不代替 P09 新进程真实全流程验收。SQL injection 示例的定义回答质量问题保留。

后续 P09 已完成新的真实全流程/跨进程验收，见 ACCEPTANCE.md；上述装配检查仅描述 P07 当时的验证边界。
