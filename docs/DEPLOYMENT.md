# 普通问答基线部署与复现

范围：Linux x86_64 / Python 3.12 / 本地固定资源 / CLI。已测试 GPU 为 RTX 4090，torch 2.9.1+cu128；CUDA 驱动须兼容该运行库。CPU 入口可选 `--device cpu`，但本次未做 CPU 真实性能或全流程验收。没有 Web/API 服务或增强模式。

## 1. 独立环境

在仓库根目录执行。`requirements-inference.txt` 是本机完整锁定环境（包括 pytest），并非跨平台通用锁；Windows/macOS 不在本次验证范围。模型约 1.32 GB，CUDA 依赖另需数 GB，准备充足磁盘。

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements-inference.txt
.venv/bin/python -m pip install -e . --no-deps
.venv/bin/python -m pip check
```

## 2. 固定资源

```bash
mkdir -p data/raw/cwe
curl --fail --location https://cwe.mitre.org/data/xml/cwec_v4.20.xml.zip --output data/raw/cwe/cwec_v4.20.xml.zip
.venv/bin/python -c "import hashlib,pathlib; p=pathlib.Path('data/raw/cwe/cwec_v4.20.xml.zip'); assert hashlib.sha256(p.read_bytes()).hexdigest() == '3976f599e5e5200219a3108bb896d06e2a88fbb293369e1883cb423a5e9d7d50'"
.venv/bin/python scripts/fetch_dpr_resources.py --weights
```

无可靠下载完成收据时，preprocess 不传 --receipt，acquired_at=null、basis=unknown，并另记登记时间；不得用现在时间或 mtime 冒充原文件获取时间。有匹配可靠收据可显式传入。此次已有原始文件已在 P02 下载并核验，P10 复用这些字节。

模型/tokenizer 由 configs/dpr-models.v1.json 固定到下列 revision，不自动换 latest；下载器核对上游 LFS 大小/SHA-256，加载时再验证。三个旧 repo 的 tokenizer 类标签均为 question，程序明确按角色加载 Fast 类；仅允许已核查的未用 pooler/position_ids 多余参数，其他权重差异仍失败，详见 RETRIEVAL。

| 角色 | facebook 模型 | revision |
| --- | --- | --- |
| question | dpr-question_encoder-single-nq-base | d04a52f6d2f96c60117a925e8c24c4043a75f265 |
| context | dpr-ctx_encoder-single-nq-base | bb21a3c2b1656d60c6a8e920283bc40dabddadb8 |
| reader | dpr-reader-single-nq-base | 38f47a4986084c53447ba92ab0a83076b58d86a8 |

## 3. 处理、建库、加载与查询

全新部署用 cwe-v1/dpr-index-v1；本次为避免覆盖已有快照，实际重放用 cwe-replay/dpr-index-replay。输出目录必须尚不存在。

```bash
.venv/bin/python -m cyber_qa preprocess --raw data/raw/cwe/cwec_v4.20.xml.zip --output data/processed/cwe-replay
.venv/bin/python -m cyber_qa build-index --snapshot data/processed/cwe-replay --output data/processed/dpr-index-replay --device cuda --batch-size 32
.venv/bin/python -m cyber_qa query --snapshot data/processed/cwe-replay --index data/processed/dpr-index-replay --question 'What are examples of hard-coded credentials?' --strategy both --device cuda --output outputs/p10-query.json
```

query 独立加载已有索引，不重建；支持 reader_topk/mmr/both。`--config configs/baseline.v1.json` 集中指定 N/K/λ；默认20/5/.5、untuned。两策略共用同一候选池、Reader 结果及一次归一化。每个正常答案附 evidence_id/context/source，完整证据和字符跨度在 results 中，逐轮 MMR 记录选择前集合与冗余。正常 status=success 只代表处理成功，不代表语义正确。

输入和评分冻结：CWE text 的 UTF-8 SHA-256 与稳定来源 ID；question64/title64/context256/reader512/passage189；问题超限拒绝，标题只截断输入并记录。完整有效池 min-max（epsilon=1e-12，等分/单候选为0）；余弦先裁剪 [-1,1] 再 max(0,cos)；MMR 每轮最大冗余更新。Reader/span_score/检索分数分离，跨度≤64 token；普通回答按 Reader 原始相关性与固定同分规则选已选证据内的合法跨度。无合法跨度回退原文，无候选/已选为空/处理失败分别记录。

## 4. 验证与恢复

```bash
.venv/bin/python -m pytest -q
.venv/bin/python scripts/check_dpr_reader.py --device cuda --output outputs/reader-check.json
.venv/bin/python scripts/check_baseline_smoke.py --snapshot data/processed/cwe-replay --index data/processed/dpr-index-replay --device cuda --output outputs/replay-smoke
```

- 模型中断：重复 fetch_dpr_resources.py --weights；保留 .part 续传，坏缓存隔离，未核验权重不会启用。
- 索引不兼容：保留旧目录，用新输出目录从相同模型/预算/快照重建；不要编辑清单来绕过哈希检查。
- 长问题或模型异常：查看输出 JSON error.stage/type/message；处理失败退出1，参数错误退出2；无候选是成功处理后的 insufficient_information。不要把异常分数改成零继续回答。
- 输出文件写入失败：stderr 给出 output_write，不会把已失败保存说成成功。
- 数据、权重、索引、环境、运行日志均忽略；只提交代码、配置、题集和不敏感摘要。不得更改机器网络配置来“修复”基线。

## 5. 实测边界

P09：12 道真实题、全部来源/跨度检查、新进程重新加载索引/模型比较通过；指定支持段命中仅4/12、两策略选中3/12，答案质量不足，详见 ACCEPTANCE。没有正式测试集调优、模型校准或独立人工复核。

P10 复现结果与最终审计见本文件下方实测登记及 PROGRESS。单次计时仅记录事实，不承诺稳定吞吐或延迟。

## P10 实测登记（2026-11-17T10:16:03+08:00）

- 原独立环境按第3节命令逐个启动干净进程重建：预处理7.674s；建库编码/写入8.882s、模型加载3.213s；5748×768原始向量。数据 JSONL、向量和 ID 映射 SHA-256 均与 P03/P05 完全一致。
- 重放 hard-coded credentials 查询的完整候选/分数/选择/答案与 P09 smoke-12 完全相同；两策略输出 password/CWE-798，仍是部分答案。
- 新建第二个隔离环境 `outputs/p10-venv`，未继承 site-packages；按锁安装 requirements-inference.txt 和 editable 项目（--no-deps）成功，pip check 无冲突。历史 P10 新环境全套 **137 passed in 4.74s**、无 skip；清理旧兼容层后当前回归为 135 passed；12题真实冒烟与其启动的新进程 CLI 重载结果未改变。
- 新环境安装复用本机 pip 下载缓存、共享已校验的本地模型/原始数据；不是无缓存外网全量下载或跨机器/跨平台验证。未修改宿主包或网络配置。
- 详细产物与安装日志仅在忽略的 outputs/p10-*。原始提示词字节 SHA-256 和冻结规格原文一致；保护项 install.sh 未修改/未提交。

## 规格验收映射

| BASELINE_SPEC 要求 | 实现 / 验收证据 |
| --- | --- |
| 三：manifest、字段、语义映射、稳定ID/清洗/去重 | data/contracts.py、cwe.py、chunking.py、preprocess.py；test_cwe_contracts/test_preprocess；CWE_CONTRACT 与两次真实快照 |
| 四：匹配编码器、原始内积、索引持久化/兼容性 | models.py、retrieval/dpr.py；test_retrieval/test_resource_downloads；P05 与 P10 真实建库/重载 |
| 五：Reader 分数分离、单条/批次/重排、原文跨度、一次复用 | reader/dpr.py、data/candidates.py；test_reader；check_dpr_reader 与 P06 实测 |
| 六：固定池min-max/epsilon/非负余弦/异常 | selection/mmr.py；test_mmr；真实完整池与不改原向量检查 |
| 七：Top-K、逐轮MMR、同分/边界/参考等价/日志 | 同一mmr模块；21项选择回归含指定A/B/C和80组随机；P06真实参考等价 |
| 八：普通回答/回退/完整CLI/耗时 | answering/ordinary.py、pipeline/ordinary.py、__main__.py；test_answering/test_pipeline_cli；P08真实成功与失败JSON |
| 九：数据/对齐/尺度/MMR回归、10–20题与跨进程 | 137项测试无skip；12题真实流程、首题独立进程比较；ACCEPTANCE记录质量不足 |
| 十：配置/版本/预算/环境集中与共享核心 | BaselineConfig/InputBudget/ReaderConfig/AnswerConfig、固定revision与依赖锁、运行JSON；CLI/脚本复用核心 |
| 十一–十三：状态/文件/时间线/恢复/提交推送 | PROGRESS/HANDOFF和阶段Git提交；每阶段及最后文档提交均核验远端 |

本轮完成的是固定基线的实现、技术验收与复现材料；不把正式人工核验/开发集调优/模型校准/增强模式/自动更新等后续工作标为完成。

- 2026-11-17T10:18:10+08:00 补充核验：在第二个隔离环境中另建 outputs/p10-clean-snapshot 和 outputs/p10-clean-index，再执行 query；全部步骤退出0，JSONL/向量/映射哈希及完整查询候选/分数/答案与原产物完全一致。新环境的预处理、context/question/reader 三角色均已实际执行。
