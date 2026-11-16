# P05 DPR 编码、索引与恢复

状态：实现与合成回归已完成；真实模型/完整索引验收进行中，最终状态见 PROGRESS/HANDOFF。此文件不是完整问答部署说明，Reader 与普通回答将在后续阶段接入。

## 固定接口与实现

- `src/cyber_qa/models.py`：本地加载 `configs/dpr-models.v1.json` 中匹配的 single-nq question/context/reader 资源。模型延迟加载、eval/inference_mode；tokenizer 与 snapshot provenance、输入预算须完全一致。权重须有下载器取得的上游 LFS 大小/SHA-256 记录，并在加载前重新校验。
- `src/cyber_qa/retrieval/dpr.py`：`build_index`、`load_index`、`DPRIndex.search` 共用实现。精确 NumPy float32 原始内积，768 维，不归一化；目前只有 5748 个段落，无需近似索引/FAISS。分数同分以 passage_id 字典序排序，排名从 1 开始，最多 N=20。空库返回空元组；N 必须为正整数。重复 ID 的索引拒绝加载，正常候选天然唯一。
- 保存 `vectors.npy`、有序 `passage_ids.json`、`index_manifest.json`。写入临时目录、重载检查后才启用；已有输出目录拒绝覆盖。
- 索引清单保存模型/tokenizer/revision/文件哈希、输入预算、context 权重哈希、语料哈希、快照、维度、dtype、metric、向量/映射哈希、依赖版本、设备、批次和时间。加载时校验清单、快照/配置兼容性、映射顺序、文件哈希、向量形状/dtype/有限性/非零范数。传 runtime 时还核对 context 权重哈希。
- 返回完整 `RetrievedPassage`（passage、retrieval_rank、retrieval_score、原始 vector）；MMR 独立计算余弦，不改写 DPR 向量。尚无 Reader 分数或答案。

## 输入与耗时

沿用 P03 的冻结预算：context 256、question 64、title 64、passage 189、Reader 512。context 输入为 `[CLS] title [SEP] text [SEP]`，segment 全零（与 DPR 原始编码路径一致）；question 为 `[CLS] question [SEP]`。超长问题明确拒绝，标题仅在模型输入截断，来源 title 不变。完整保留原文，不对 passage 静默截断。现有三角色共享词表的校验仍然执行。

模型输出须为 context `(batch,768)`、question `(1,768)`；非有限值或零向量使操作失败。`model_load_seconds` 单独记录加载时间；`offline_build_seconds` 不含模型加载，query 检查脚本的 query_seconds 在预加载 question 后计时。建库前已有 tokenizer 加载不计入离线编码时间。

segment 约定同时核对了 [DPR 原始段落编码实现](https://github.com/facebookresearch/DPR/blob/main/generate_dense_embeddings.py) 的 zeros_like segment 张量。

接口依据：[Transformers 4.57.1 DPR 文档](https://huggingface.co/docs/transformers/v4.57.1/en/model_doc/dpr) 与本地同版本实现。固定模型 revision 见配置，不自动切换 latest。

## 下载与中断恢复

```bash
.venv/bin/python -m pip install -e '.[inference]' -c requirements-tokenization.txt
.venv/bin/python scripts/fetch_dpr_resources.py --weights
```

下载器通过固定 revision 的 Hugging Face API `?blobs=true` 读取权重 LFS 大小/SHA-256；仅本地自记哈希不能证明下载完整。完整权重验证后才从 `.part` 晋升为正式文件；不完整旧缓存隔离为 `.bin.invalid`。HTTP 长度不符、上游大小或哈希不符均失败；服务支持 Range 时续传 `.part`，忽略 Range 时重新下载；最终完整文件必须通过上游哈希。断开后重复同一命令即可。失败重试最多三次，未验证权重绝不成为可加载资源。

2026-11-16 恢复检查发现 question 旧缓存 10,922,208 字节，上游要求 437,986,065 字节（SHA-256 `7fd8074bf164ea506267e1894b4b7579d25c56858d4890d707272557b7c7cc00`）；此次修复针对该实际完整性缺陷。tokenizer 文件与 P03 快照配置未改变。原下载器输出的 verified 不代表真实权重可用。

如果 shell 继承了冲突代理，按已有环境加载 `/root/.config/codex/network-env.sh`，不修改网络配置，不上传网络日志、权重与缓存。

## 建库与真实召回验收命令

以下入口已实现，实际执行结果以 PROGRESS/HANDOFF 为准；运行依赖权重与独立 torch 安装成功。

```bash
.venv/bin/python scripts/build_dpr_index.py --snapshot data/processed/cwe-v1 --output data/processed/dpr-index-v1 --device cuda --batch-size 32
.venv/bin/python scripts/check_dpr_retrieval.py --device cuda --output outputs/p05-retrieval-first.json
.venv/bin/python scripts/check_dpr_retrieval.py --device cuda --output outputs/p05-retrieval-reload.json --compare outputs/p05-retrieval-first.json
```

检查脚本使用真实 context/question 模型，核对单候选/批量 context 编码、已保存向量、只读索引、余弦处理不改变原始向量、重载和跨进程的候选及分数一致。批量与单条浮点编码比较使用 rtol=1e-4、atol=2e-4，保存重载召回要求结果完全一致。默认查询 `What is SQL injection?`，输出含原文/来源和时间，但不是 Reader/MMR/普通回答端到端验收。

## 单元验证

```bash
.venv/bin/python -m pytest -q tests/test_resource_downloads.py tests/test_retrieval.py
.venv/bin/python -m pytest -q
```

前一命令 24 passed；全套 97 passed（此次在 torch 安装前执行）。下载使用模拟 HTTP、索引使用合成向量，不能代替真实推理。覆盖旧自记哈希错误缓存、截断响应、续传/服务器忽略 Range、错误 Range、revision 错配、索引保存重载、同分、空库、最多 N、原始内积、来源映射、配置/快照/权重错配、损坏向量与无效输入。
