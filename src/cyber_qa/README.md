# 核心模块

当前第一阶段实现依据见 [BASELINE_SPEC](../../docs/BASELINE_SPEC.md)，真实状态及限制见 [PROGRESS](../../docs/PROGRESS.md)。

| 路径 | 已实现职责 |
| --- | --- |
| data/ | CWE 解析、完整来源契约、确定性分段/快照 |
| models.py、resources.py | 固定 revision 本地资源/权重校验与 DPR 加载 |
| retrieval/dpr.py | 原始内积索引、持久化与召回；id_router.py 保留旧接口 |
| reader/dpr.py | Reader 相关性/起止 logits、批次对齐、原文跨度 |
| selection/mmr.py | 完整池一次归一化、Top-K、逐轮 MMR 与参考实现 |
| answering/ordinary.py | 已选证据内抽取、原文/不足/失败回退 |
| pipeline/ordinary.py | 一次召回/Reader供两策略共享，运行记录 |
| __main__.py | preprocess/build-index/query CLI |
| evaluation/ | 早期证据指标，非本次正式实验结果 |

主线筛选实现位于 `selection.mmr`。增强模式、Web 界面、自动更新与正式评估未实现。所有正常回答的语义充分性仍为 not_assessed。
