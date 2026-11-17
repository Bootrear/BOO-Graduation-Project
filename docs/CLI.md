# P08 统一 CLI 与查询记录

在仓库根目录、已安装 inference extra 且资源准备完毕的环境运行。获取资源/离线建库先看 RETRIEVAL.md。所有入口复用 data.preprocess、retrieval.dpr、reader.dpr、selection.mmr、answering.ordinary；无额外 API/Web 实现。

```bash
.venv/bin/python -m cyber_qa --help
.venv/bin/python -m cyber_qa preprocess --raw data/raw/cwe/cwec_v4.20.xml.zip --output data/processed/cwe-replay
.venv/bin/python -m cyber_qa build-index --snapshot data/processed/cwe-v1 --output data/processed/dpr-index-replay --device cuda --batch-size 32
.venv/bin/python -m cyber_qa query --question 'What is SQL injection?' --strategy both --device cuda --output outputs/query.json
```

原始文件位置应以实际下载目录为准；P10 将重放并统一完整部署命令。数据/索引产物目录必须不存在；查询 JSON 原子写入指定路径。策略可选 reader_topk/mmr/both；默认 mmr；配置默认 configs/baseline.v1.json，问题 token 超过 64 拒绝。--help/参数错误无需加载模型。

`QAPipeline.load(index, snapshot, ...)` 核验已有索引后，`query(question, strategy='both')` 在一次问题编码/召回/Reader 评分/完整池准备后调用两个筛选器。每种策略只装配自己选定证据的答案；不会重新推理或重新归一化。Reader 只按候选批次调用一次，测试用计数器覆盖此约束。默认 N=20/K=5/λ=.5 未调优；MMR 非负裁剪余弦及全部同分规则不变。

JSON 保存：问题、带时区运行时间、配置及稳定哈希、输入预算、实际问题长度/截断状态、完整 index_manifest（含快照/模型/revision/离线环境/建库耗时）、在线环境、权重哈希、Reader 原始起止 logits/输入字符偏移、完整候选/归一化分数、两策略顺序/证据/MMR 逐轮日志、普通答案及回退原因。

时间分开记录 runtime_initialization、index_load、model_load、question_encoding、retrieval、reader、pool_preparation、各策略 selection/answer 和 query_total。query_total 包含本次延迟模型加载；startup 不包含于 query_total；index 内离线耗时是建库历史，不加到查询延迟。单次样本不代表稳定性能。

正常查询（包括无候选/信息不足）退出 0；配置/资源初始化或阶段异常保存 failed JSON、error.stage/type/message 和 processing_failure，退出 1。失败时清空部分策略答案，保留已完成阶段诊断。输出文件写入失败以 stderr JSON 报告、退出 1；argparse 参数错误退出 2。

## P08 验证

- `.venv/bin/python -m pytest -q`：137 passed in 4.64s，无 skip；新增 12 项编排/CLI 回归。
- 上述 query 命令实际执行成功，20 候选、两策略各 5 段、结构化 outputs/p08-query.json；首位答案仍有 P06 已记录的语义质量限制。
- `query --index outputs/does-not-exist ...`：退出 1，outputs/p08-missing-index.json 保存 query_initialization / FileNotFoundError。
- CLI 实际单条全链路已运行；正式 10–20 题及跨进程重载的 P09 验收尚未完成，整体暂不标完成。
