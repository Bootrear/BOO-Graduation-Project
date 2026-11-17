# P09 真实 CWE / DPR 全流程冒烟验收

执行时间：2026-11-17T10:09:39+08:00。**技术端到端通过；语义质量不足、尚未校准。**

固定 CWE 4.20 / 5748 段 / single-nq 三模型 / N=20、K=5、λ=.5（未调优）。12 道英文题及对应描述字段原文、passage_id、字符位置、来源路径/URL/哈希保存在 `data/annotations/baseline_smoke.v1.json`。Codex 已逐条阅读并核对支持原文，未有独立人工复核；题集不是正式开发/测试集，未用于调参。

```bash
.venv/bin/python scripts/check_baseline_smoke.py --device cuda --output outputs/p09-smoke
```

命令退出 0。全部 12 题实际执行 DPR 问题编码→20 段召回→Reader→完整池归一化→Top-K/MMR→普通回答；同题只调用一次 Reader 并供两策略共用。每条候选/已选证据/答案均验证原文、快照、URL 和字符位置。首题通过 subprocess 启动新 Python CLI，重新加载已有索引/模型；候选、分数、跨度、两策略选择与回答一致（浮点 rtol=1e-4/atol=2e-4，ID/文本/位置严格相等）。两策略选择顺序可能不同，答案在本组 12 题均相同。

P09 历史验收全套 137 项测试通过，无 skip；清理旧兼容层后当前回归为 135 项，compileall 仍通过。完整逐题 JSON/重载结果/日志保存在忽略路径 outputs/p09-smoke/，Git 仅提交题集、验收脚本和本摘要。

## 质量观察（不能当作正式实验）

指定支持 passage 命中：召回 4/12，Reader Top-K 选中 3/12，MMR 选中 3/12；这只统计每题标出的一个具体支持段，不是完整相关性标注下的 Recall。与指定完整原文短语的字面完全匹配为 0/12，也不能直接当作正式 EM 或语义准确率。存在未召回、选错字段、抽取过短的问题。

| 题号 / 支持 CWE | 支持段召回 | 两策略选中支持段 | 实际普通答案（两策略相同） |
| --- | --- | --- | --- |
| smoke-01 / CWE-79 | False | False | user-controlled input that specifies a link to an external site, and uses that link in a redirect |
| smoke-02 / CWE-89 | False | False | SQL statement |
| smoke-03 / CWE-22 | False | False | lockout |
| smoke-04 / CWE-78 | True | False | library calls |
| smoke-05 / CWE-120 | False | False | Scope: Availability |
| smoke-06 / CWE-200 | False | False | the attacker |
| smoke-07 / CWE-287 | True | True | incorrect |
| smoke-08 / CWE-306 | False | False | it has insufficient privileges |
| smoke-09 / CWE-327 | False | False | SRP |
| smoke-10 / CWE-352 | True | True | a request |
| smoke-11 / CWE-434 | False | False | .php |
| smoke-12 / CWE-798 | True | True | password |

逐项原文审阅：smoke-01/03/04/05/07/08/09 的输出未回答题目所问；smoke-02 只给 SQL statement，未完整表达用户输入被当成 SQL 而非数据；smoke-06 只给 attacker，未表达未经授权；smoke-10 只给 a request，遗漏“是否由用户有意发出”的条件；smoke-11 的 .php 只是原文中的具体类型；smoke-12 的 password 只是两类例子之一。未依据这些失败修改公式、λ、预算或模型。

限制：所有正常输出 evidence_sufficiency=not_assessed，合法引用不等同语义支持。正式 120 题、独立人工复核、开发集调优、校准与综合问题评估仍属后续；不得声称 MMR 优于 Top-K 或已达到可用准确率。部署/复现收尾进入 P10。
