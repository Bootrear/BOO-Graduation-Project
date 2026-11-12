# 核心模块职责

当前包只包含基础数据结构、早期 ID 解析／DSES 与证据指标。下表的“计划”不代表已经具备相应接口；主线见[开题报告](../../docs/开题报告_整理版.md)。

| 目录 | 已有能力 | 计划职责 |
| --- | --- | --- |
| `data/` | `Evidence` 最小数据类 | CWE 解析、语义字段分段、来源和版本记录、内容变化检测与快照更新 |
| `retrieval/` | CVE／CWE／CAPEC／ATT&CK ID 解析 | DPR 段落编码、索引与问题编码，初始召回 N=20 |
| [reader/](reader/README.md) | 仅职责说明 | Reader 相关性评分、答案位置及候选对应关系 |
| `selection/` | 早期 `dses.py`，包级导出仍为 DSES | MMR 至多 5 段与 Reader Top-5 对照；尚无 MMR 实现 |
| [answering/](answering/README.md) | 仅职责说明 | 普通抽取／原文回退、增强生成与证据编号检查 |
| [pipeline/](pipeline/README.md) | 仅职责说明 | 串联各阶段，供界面和实验共用，保存追溯记录 |
| `evaluation/` | evidence precision／recall、早期字段覆盖 | 检索、筛选、事实、引用与开销的完整评价 |

早期 DSES 的实体、字段覆盖和长度成本评分不属于本轮 MMR 定义，不应将其包级 `select_evidence` 当作 MMR 调用。保留现有路径、导出和测试，以便追溯历史探索。

前期接口接入时应核对模型输入、分数含义与尺度、知识段顺序、token／原文位置映射及返回格式，并记录原始代码提交和验证结果。现阶段不引入模型下载或额外依赖。
