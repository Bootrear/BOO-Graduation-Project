# 脚本入口

统一用户入口为 `python -m cyber_qa`，见 [部署指南](../docs/DEPLOYMENT.md)。脚本和 CLI 复用同一核心实现。

| 脚本 | 用途 |
| --- | --- |
| fetch_dpr_resources.py | 固定 revision tokenizer/权重下载、上游 LFS 校验、续传恢复 |
| preprocess_cwe.py | 固定 CWE 快照处理；同 CLI preprocess |
| build_dpr_index.py | DPR 原始向量索引；同 CLI build-index |
| check_dpr_retrieval.py | 真实双编码器、保存向量、重载召回校验 |
| check_dpr_reader.py | 单条/分批/反序对齐、原文跨度与真实选择校验 |
| check_baseline_smoke.py | 12 题真实普通问答、双策略、独立新进程重载 |
| validate_raw_data.py | 旧完整起始快照校验（含 NVD/CAPEC/ATT&CK/KEV），不属于本基线必需资源 |

真实验收脚本需要本地模型/数据/索引，缺失不能用合成结果代替。完整日志和 JSON 存 outputs/，不上传原始数据、权重或大索引。
