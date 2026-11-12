# 配置目录

- [baseline.example.json](baseline.example.json)：根据开题报告整理的配置草案，表达 CWE、DPR → Reader → MMR 与双模式的边界。**目前没有读取它的执行器，不能据此启动系统。**
- [dses.example.json](dses.example.json)：早期 DSES 探索配置，保留原有内容，不作为当前主线参数。

草案中 `null` 表示待开发阶段确定；尤其是模型 revision、Reader 分数处理、MMR λ、证据不足规则、生成参数与快照路径。不能把这些占位值当成正式实验配置。

主线初始候选数为 20，证据上限为 5。普通模式和增强模式共用同组 MMR 证据；Reader Top-5 只用于筛选对照。正式配置须在开发集确定后冻结，记录配置哈希与版本，不能在测试集调参。不要将 API 密钥写入配置。
