# 跨会话交接

恢复顺序：AGENTS.md → BASELINE_SPEC.md → IMPLEMENTATION_PLAN.md → PROGRESS.md → 本文件；再核查 git status、branch、log。

## 当前分支和提交

- 分支 `baseline/cwe-dpr-reader-mmr`；origin=`https://github.com/Bootrear/BOO-Graduation-Project.git`。
- 写入时 HEAD / 最近远端核验提交：`402abef6e87a50a775b17b9cb14d095b4b69f3c1`（P10），fetch/ls-remote一致。
- 本轮已核验：P06 `86e5ed400759bd198822c8cc2eb8e5339251a4ae`；P07 `7ec81b5250e71cb0f59a8e6e388857d820826b0b`；P08 `b28b783ac1686a9cbae4c2d7f849b99c84ae4786`；P09 `dff54ee097884a9112b9e2e40bfc6f6c219ea774`；P10如上。
- P10验收提交已推送核验；本次清理修改写入时 HEAD 为 `b78a9970f21c9b8479ef134caa3ea8d41096ce8d`。清理提交为 `9a055b2`（完整哈希以 `git rev-parse HEAD` 获取）；首次推送于清理提交后因 `gnutls_handshake() failed: The TLS connection was non-properly terminated` 失败，远端尚未核验包含该提交。

## 本阶段目标与结论

P00–P10普通问答基线代码、单元、真实模型、真实端到端和部署复现均已完成技术验收。随后已清理与当前基线无关的早期选择器兼容层；清理后的回归套件为135项，12题全流程、独立新进程重载、全量预处理/建库/查询结果保持不变。

**语义质量不足，不是已校准产品**：指定支持passage仅4/12召回、两策略均3/12选中；所有正常答案语义充分性为not_assessed。Codex逐条检查原文与实际输出，未声称独立人工复核。正式120题/调优/校准/增强模式/自动更新属于后续范围。

## 已修改文件

本次清理：删除早期选择器实现、测试、配置、合成脚本、旧数据类及其导出；更新 AGENTS.md、README.md、CONTRIBUTIONS.md、配置/脚本/模块说明、BASELINE_SPEC.md、IMPLEMENTATION_PLAN.md、READER.md、RUNTIME.md、SELECTION.md、研究范围、PROGRESS.md、HANDOFF.md，并将包级选择导出切换为 MMR。

install.sh保持未跟踪且未改动；docs/theprompt.md原始字节保留。data/raw、data/processed、models、outputs中的权重/原始数据/索引/日志/第二个虚拟环境均忽略，不提交。

## 已运行命令及结果

1. `.venv/bin/python -m cyber_qa preprocess --raw data/raw/cwe/cwec_v4.20.xml.zip --output data/processed/cwe-replay`：退出0，5748段，7.674s。
2. `.venv/bin/python -m cyber_qa build-index --snapshot data/processed/cwe-replay --output data/processed/dpr-index-replay --device cuda --batch-size 32`：退出0，5748×768；编码/写入8.882s，加载3.213s。
3. `.venv/bin/python -m cyber_qa query --snapshot data/processed/cwe-replay --index data/processed/dpr-index-replay --question 'What are examples of hard-coded credentials?' --strategy both --device cuda --output outputs/p10-query.json`：退出0；候选/分数/两策略答案与P09 smoke-12精确一致。
4. `python -m venv outputs/p10-venv` → 新环境 `pip install -r requirements-inference.txt` → `pip install -e . --no-deps` → `pip check`：全部成功，无冲突；复用pip缓存及已核验本地模型/原始数据，未继承site-packages。
5. `outputs/p10-venv/bin/python -m pytest -q`：历史 P10 验收为 137 passed；本次清理后 `.venv/bin/python -m pytest -q` 为 135 passed，无skip。
6. `outputs/p10-venv/bin/python scripts/check_baseline_smoke.py --snapshot data/processed/cwe-replay --index data/processed/dpr-index-replay --device cuda --output outputs/p10-fresh-smoke`：12题与独立子进程重载全部通过，质量统计不变。
7. 新环境依次运行CLI preprocess/build-index/query到 outputs/p10-clean-snapshot、p10-clean-index、p10-clean-query.json：全部退出0；JSONL/向量/映射哈希与原产物一致，查询结果精确一致。
8. compileall、pip check、修改文档本地链接、git diff --check、theprompt原始SHA-256/BASELINE_SPEC原文一致性均通过。各阶段单元/真实验证与失败修复见PROGRESS时间线。

## 当前失败或阻塞

无本轮技术/资源阻塞。未验证CPU/其他GPU/其他操作系统、无缓存全量外网下载、稳定性能或正式质量指标。已测Linux x86_64/Python3.12/RTX4090；第二环境安装共享pip缓存和本地资源。保护网络配置未改写。

## 下一步应执行的唯一具体动作

本次清理已完成本地验证。清理提交 `9a055b2` 尚未完成远端同步；恢复命令为 `git fetch origin` → 检查 `git log --oneline --left-right HEAD...origin/baseline/cwe-dpr-reader-mmr` → `git push -u origin baseline/cwe-dpr-reader-mmr` → 核对 `git ls-remote --heads origin baseline/cwe-dpr-reader-mmr`。没有未完成工程阶段需要继续。不自动扩展正式调参/增强模式/自动更新；阅读 ACCEPTANCE.md 的质量问题后，按用户新指定的后续范围行动。

## 提交与恢复

```bash
git push origin baseline/cwe-dpr-reader-mmr
git fetch origin baseline/cwe-dpr-reader-mmr
git rev-parse HEAD
git rev-parse origin/baseline/cwe-dpr-reader-mmr
git ls-remote --heads origin baseline/cwe-dpr-reader-mmr
```

首次P06提交因本机Git身份缺失失败，已沿用历史Codex/codex@localhost，以单次 `git -c user.name=Codex -c user.email=codex@localhost commit ...` 解决，未修改全局配置。推送失败保留本地提交并记录准确哈希/原因/恢复命令，不强推。

更新时间：2026-11-17T15:09:52+08:00。
