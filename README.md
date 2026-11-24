# BOO-Graduation-Project

本科毕业设计：基于检索增强与证据筛选的网络安全问答系统设计与实现。

第一阶段普通问答基线已实现：**固定 CWE → 分段 → DPR 召回 → Reader → Reader Top-K / 逐轮 MMR → 抽取答案或原文回退**。真实模型、12 题全流程及新进程重载通过；**答案质量仍不足，不能视为已校准的安全问答产品**。本次指定支持段落召回 4/12、两策略选中均 3/12；详见[验收及质量限制](docs/ACCEPTANCE.md)。

跨会话继续任务，先按 [AGENTS.md](AGENTS.md) 读取规格、计划、[进度](docs/PROGRESS.md)和[交接](docs/HANDOFF.md)。当前实现依据是 [BASELINE_SPEC](docs/BASELINE_SPEC.md)，不是早期 README 的规划。

## 部署与运行

本次验证环境：Linux x86_64、Python 3.12.11、torch 2.9.1+cu128、RTX 4090。Git 不含模型、数据或索引。完整准备、校验和失败恢复见[部署指南](docs/DEPLOYMENT.md)。在仓库根目录运行：

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements-inference.txt
.venv/bin/python -m pip install -e . --no-deps
.venv/bin/python scripts/fetch_dpr_resources.py --weights
```

准备已校验的 CWE 4.20 文件后（下载命令见部署指南）：

```bash
.venv/bin/python -m cyber_qa preprocess --raw data/raw/cwe/cwec_v4.20.xml.zip --output data/processed/cwe-v1
.venv/bin/python -m cyber_qa build-index --snapshot data/processed/cwe-v1 --output data/processed/dpr-index-v1 --device cuda --batch-size 32
.venv/bin/python -m cyber_qa query --question 'What are examples of hard-coded credentials?' --strategy both --device cuda --output outputs/query.json
```

快照和索引输出目录必须不存在；已有产物直接 query。`--strategy` 可取 reader_topk、mmr、both，默认 mmr。实际示例两策略均抽取 `password`，来源 CWE-798；这是原文中的一个例子，遗漏 cryptographic key，不能当作完整回答。JSON 含答案、证据、来源/快照、原始分数、MMR 日志和分阶段时间。

```bash
.venv/bin/python -m pytest -q
.venv/bin/python scripts/check_baseline_smoke.py --device cuda --output outputs/smoke
```

## 固定规则与模块

检索改进的独立对照入口（保留现有基线；默认 N=20/50/100，按顺序跑四种方案）：

```bash
.venv/bin/python scripts/compare_retrieval.py --device cuda
```

输出到新的 `outputs/retrieval-comparison-<UTC>/`，先查看 `comparison.md`，另有 CSV 和逐题 JSON。
方法定义、参数和指标边界见[检索四方案实验](docs/RETRIEVAL_EXPERIMENTS.md)。

| 模块 | 实现与说明 |
| --- | --- |
| 数据 | 仅 CWE 4.20 Weakness，5 类字段，5748 段；稳定 SHA-256 ID、真实时间依据和来源定位；[契约](docs/CWE_CONTRACT.md) |
| DPR | 匹配 single-nq question/context，768 维原始内积，索引保存/重载严格校验；[检索](docs/RETRIEVAL.md) |
| Reader | 分批形状/ID 对齐，排除非正文 token，原文字符映射，64-token 跨度上限；[Reader](docs/READER.md) |
| 选择 | N=20、K=5、λ=.5 **未调优**；完整候选池一次 min-max，epsilon=1e-12；冗余 max(0,clip(cos,-1,1))，逐轮更新；[选择](docs/SELECTION.md) |
| 回答 | 只用已选 Reader 结果，分数不混合；抽取/相关原文/信息不足或处理失败；[回退](docs/ANSWERING.md) |
| CLI | `src/cyber_qa/__main__.py`，共享 `pipeline/ordinary.py`；一次 Reader 供两策略复用；[运行记录](docs/CLI.md) |

问题最多 64 token，超长明确拒绝；标题输入保留前 64 token并记录，原始标题不变；正文预算 189 token。非有限模型输出、零范数向量或索引不兼容使查询失败。Reader 分数不是概率，有跨度也不代表证据充分。

当前没有 Web/API 服务。增强模式、自动更新、正式 120 题（开发 80/测试 40）、开发集调优、独立人工质量复核和正式实验属于后续范围。

[文档导航](docs/README.md) · [部署](docs/DEPLOYMENT.md) · [验收](docs/ACCEPTANCE.md) · [进度与时间线](docs/PROGRESS.md) · [开题报告](docs/开题报告_整理版.md) · [贡献边界](CONTRIBUTIONS.md)
