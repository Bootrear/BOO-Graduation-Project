# 第一阶段基线实施计划

依据：`BASELINE_SPEC.md`（完整规范）。本文件描述将要做的工作，不代表已实现。
阶段按依赖顺序执行；P04 不依赖模型下载，资源受阻时可在记录依赖后先推进。
本计划无承诺完成日期；实际时间仅写入 PROGRESS，使用 Asia/Shanghai。

## 每阶段固定交付流程

1. 读取恢复文件并核对本地/远端；将阶段目标与唯一下一步写入 HANDOFF。
2. 在该阶段边界内实现；使用共享核心逻辑，保留旧接口与用户改动。
3. 运行该阶段验收及受影响的已有测试；记录完整命令、退出结果、环境和未验证项。
4. 更新 PROGRESS 五类状态、文件用途与实际时间线，更新 HANDOFF。
5. 检查 `git diff --check`、`git diff`、`git diff --cached`；仅暂存明确相关路径。
6. `git commit` 后 `git push -u origin baseline/cwe-dpr-reader-mmr`。
7. `git fetch origin baseline/cwe-dpr-reader-mmr` 后比较 `git rev-parse HEAD` 与 `git rev-parse origin/baseline/cwe-dpr-reader-mmr`；如远端前进，检查祖先关系与差异，不覆盖历史。
8. 记录已核验提交。后续仅文档修订也须提交、推送并再次核验。

## P00：恢复机制与规格冻结

- 输入：原始提示词、当前仓库与用户追加要求。
- 产物：AGENTS、完整规格、计划、进度、交接、文档导航，以及原始提示词版本化。
- 验收：规格原文保留区与输入逐字一致（允许 CRLF→LF）；检查五类状态和恢复顺序；确认工作区保护项；运行现有可执行冒烟示例并如实记录测试依赖缺失；文档链接/差异检查；首次提交推送并核验。
- 提交建议：`docs(baseline): freeze requirements and establish resumable workflow`。
- 停止边界：不在此阶段实现 DPR、Reader、数据解析或 MMR。

## P01：环境、资源与可执行配置骨架

- 依赖：P00 已推送且核验。
- 产物：独立环境与最小依赖声明/版本记录；环境与资源核查记录；正式 baseline 配置骨架（不得把未确认 revision 标成已固定）。
- 首个动作：`python -m venv .venv`。随后 `.venv/bin/python -m pip install -e '.[dev]'`，运行 `.venv/bin/python -m pytest -q`。
- 验收：已有测试实际执行；GPU/内存/磁盘与版本证据登记；N=20、K=5、λ=0.5/未调优、epsilon 与尺度在配置中集中表达并验证；列出数据/模型获取与兼容性检查方案。
- 提交建议：`chore(baseline): establish reproducible runtime and configuration`。
- 资源缺失只阻塞真实验收，不阻塞可独立的契约或数学单元测试。

## P02：真实 CWE 样本核查与数据契约

- 依赖：P01；取得实际 CWE 文件，登记来源、SHA-256、版本、namespace、结构、时间依据。若历史版本不可得，用明确的新快照，不能冒充 4.20。
- 产物：manifest 与 passage 类型/验证器；显式 CWE 路径映射；来源定位、嵌套配对、清洗规则；正常/缺失/空/重复来源单元统计；小型来源合法的测试 fixture。
- 验收：规格三的全部字段；时间带时区；未知 acquired_at 为 null/unknown 并另记登记时间；仅 Weakness；五类语义字段；嵌套含义与 source_text 保留；不同来源同文独立溯源；真实文件解析证据。
- 提交建议：`feat(data): define traceable CWE records and semantic parsing`。
- 停止边界：未有真实 tokenizer 时不得声称分段预算已验证。

## P03：确定性分段与快照产物

- 依赖：P02、已选择并实测的 tokenizer。
- 产物：处理配置哈希、稳定 snapshot_id/passage_id 规则、JSONL/manifest 写入；source_text 与 text 区分；token 预算、标题/问题/特殊 token 预留、长问题和截断规则。
- 验收：同输入同配置重复运行文本/ID/UTF-8 content_sha256 一致；运行时间不进入 ID；超长文本真实分词器预算；缺失/重复/跨来源统计；完整来源回查。
- 提交建议：`feat(data): add deterministic token-aware CWE snapshots`。

## P04：统一尺度、Reader Top-K 与逐轮 MMR

- 依赖：P01 配置和 P02 契约；数学验证无需下载模型，禁止把 fixture 测试记作真实推理。
- 产物：集中 min-max/非负余弦；Top-K；MMR 参考实现与增量实现；逐轮日志及完整证据返回。
- 验收：规格六、七、九全部尺度和边界；NaN/Inf/零向量失败；完整池只归一化一次；原始 logit 保留；确定性同分；空池/K=0/不足K/λ=0/λ=1；随机有效输入下参考与增量顺序/分数一致。
- 必做：A=10、B=9、C=8 和规格给定三向量，λ=0.5/K=2，Top-K=[A,B]、MMR=[A,C]；不能只算一次分数。
- 提交建议：`feat(selection): implement deterministic reader top-k and iterative MMR`。

## P05：DPR 双编码器、索引持久化与召回

- 依赖：P03；真实匹配 question/context 模型及 tokenizer revision 可用。
- 产物：离线段落编码、原始向量与 passage_id 映射、索引保存/加载、线上问题编码和召回；模型/维度/长度/度量/索引元数据与一致性校验。
- 验收：真实模型输出形状及有限性；检索度量符合模型；MMR 归一化副本不改变检索向量；去重与确定性排名；返回最多 N；快照/维度/配置错配拒绝加载；保存重载结果一致。
- 提交建议：`feat(retrieval): persist compatible DPR indexes and retrieve candidates`。
- 若真实资源失败，只能交付 checkpoint 或明确已实现未真实验证，不通过此阶段真实验收。

## P06：Reader 对齐与可回查答案跨度

- 依赖：P05；真实匹配 Reader/tokenizer。
- 产物：分批 Reader；形状检查；retrieval_score/relevance_logit/start/end/span_score 分离；候选记录；原文位置映射和异常策略。
- 验收：多候选/单候选/跨批对齐；重排时 ID、文本、向量、分数、跨度一起移动；排除问题/标题等非 passage 区域、特殊 token、padding；起止与跨度限制；真实抽取回到 text；同一问题只计算一次供两策略复用。
- 提交建议：`feat(reader): align passage scores and trace answer spans`。

## P07：普通模式回答与明确回退

- 依赖：P04、P06。
- 产物：只使用最终证据的抽取/相关原文/信息不足或失败输出；冻结答案排序、span_score 和回退规则及实现位置，标记未校准。
- 验收：答案、证据 ID、上下文、来源完整；未选证据不可进入答案；无候选/不足 K/证据不足独立处理；数量不当充分性；不混合未定义尺度，不称 logit 为概率；逐条记录回退原因。
- 提交建议：`feat(answering): assemble ordinary answers with explicit fallbacks`。

## P08：端到端 CLI 与运行产物

- 依赖：P03–P07。
- 产物：处理、建索引、加载索引、查询、策略选择、结构化保存的完整 CLI；共享 pipeline；阶段耗时与加载/离线耗时分开。
- 验收：帮助与参数错误、空结果/失败记录、文件写入；两策略使用相同 pool 与 Reader 缓存；配置/模型/快照/筛选日志可回查。无现有 API，先 CLI，不扩建 Web 服务。
- 提交建议：`feat(cli): expose the reproducible ordinary QA pipeline`。

## P09：真实数据与模型冒烟验收

- 依赖：P08，完整真实数据、模型和索引可用。
- 产物：10–20 道来自实际 CWE 的英文问题与支持证据、实际查询及两策略输出、验证摘要与资源/耗时记录（不上传大产物）。
- 验收：至少一条查询实际经过 DPR→Reader→MMR→普通回答；同题两策略共享候选与 Reader；索引保存后从新进程加载并重复文档命令；结果追溯到固定原文；人工检查支持证据。不得用模拟模型验收。
- 提交建议：`test(baseline): verify real CWE and DPR end-to-end queries`。
- 有任何真实流程缺失：整体基线保持未验收。

## P10：部署复现与最终审计

- 依赖：P09。
- 产物：README/部署指南、准确可运行的处理/建库/查询命令、依赖与模型 revision、配置说明、失败恢复说明、完整验收映射及最新进度。
- 验收：在干净进程重放文档命令；全部相关测试通过；核对规格每条验收；代码/真实推理/端到端状态分开；最后文档也提交推送且远端核验。
- 提交建议：`docs(baseline): document deployment and verified acceptance`。

## 后续范围（不阻塞本阶段、不得混称本轮完成）

大模型增强模式、自动数据更新、正式 120 题（开发 80/冻结测试 40）核验集、仅开发集 λ 调优、正式实验；变更归一化/相似度必须升级配置并重评 λ。

## 中断、推送失败与恢复

- 一个阶段的验证来不及完成：先保存可运行状态，运行可完成的最小检查；更新 HANDOFF 的唯一下一步，例如一条具体失败测试命令；提交 `checkpoint(Pxx): incomplete - ...`。
- 推送失败：把失败的提交哈希、时间、原始错误的非敏感摘要、远端/分支写入 HANDOFF，文档更新再本地提交；最终回复报告实际 HEAD 和未同步状态。
- 恢复推送：`git fetch origin` → 检查 `git log --oneline --left-right HEAD...origin/baseline/cwe-dpr-reader-mmr`（远端分支存在时）→ 保留双方历史解决差异 → `git push -u origin baseline/cwe-dpr-reader-mmr` → 核对 `git ls-remote --heads origin baseline/cwe-dpr-reader-mmr`。
- 同步核验若远端领先，使用 `git merge-base --is-ancestor <阶段提交> origin/baseline/cwe-dpr-reader-mmr` 确认包含关系；不得静默将远端覆盖。
