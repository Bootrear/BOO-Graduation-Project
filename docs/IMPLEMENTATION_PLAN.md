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

### R01：用户追加的检索四方案独立实验

- 输入：既有 DPR 基线、CWE 快照/向量索引、40 题探针与 N20/50/100 历史结果。
- 产物：独立实验模块，原始 DPR / BM25+DPR / 子问题 DPR / CWE 条目检索；顺序运行脚本；
  同 N 的检索与 Top-K/MMR 对照、逐题记录、JSON/CSV/Markdown、历史归档和 provenance。
- 验收：原实现/配置/历史结果字节不变；无 gold 信息进入检索；去重与候选预算；
  一次 Reader 共用筛选；失败不从分母消失；合成单元验证及真实 40×4×3 流程分开记账。
- 停止边界：不叠加三个实验，不调参，不改冻结公式，不做语义答案评分或声称正式有效性；
  机器标注待人工复核。详细算法与参数见 RETRIEVAL_EXPERIMENTS.md。

大模型增强模式、自动数据更新、正式 120 题（开发 80/冻结测试 40）核验集、仅开发集 λ 调优、正式实验；变更归一化/相似度必须升级配置并重评 λ。

## STEP2：跨语言免翻译路线（新分支 `step2/crosslingual-rag`）

依据：[STEP2 完整规格](BASELINE_SPEC_V2.md) 与 [工作单](theprompt_2.md)。下列阶段各自只交付一个可以独立验证并提交的小边界；不得修改冻结的 baseline-v1/R01 资产。每阶段结束按本文件顶部闭环更新进度、交接和提交日志。

### STEP2-DOC：恢复机制与规格冻结

- 目标：使后续会话只靠仓库文档能恢复 STEP2 约束、门禁和下一步。
- 依赖：分支 `step2/crosslingual-rag` 已创建并推送；已完整读取 STEP2 输入。
- 产物：`BASELINE_SPEC_V2.md`、v1 顶部导航、此 STEP2 阶段计划、五类进度、六项交接、提交记录与文档导航。
- 验收命令与预期：`git diff --check` 成功；规格覆盖公式/字段/边界/门禁；链接目标存在；原始 `docs/theprompt.md` 与 STEP1/R01 历史不变；仅相关文档入提交。
- 提交建议：`docs(step2): establish cross-session recovery baseline`。
- 停止边界：不下载模型、不改配置/代码、不运行新功能。

### STEP2-P0A：真实资源与模型来源核查

- 目标：核实运行环境、上游不可变 revision/权重元数据、资源容量和服务访问方式。
- 依赖：STEP2-DOC 已推送；可访问模型上游及可用于真实推理的硬件/服务。
- 产物：新增 STEP2 专属模型/资源清单和获取校验代码；记录上游声明长度/SHA-256、实测摘要、revision、软件环境。不得修改 `requirements-inference.txt`。
- 验收命令与预期：专属资源检查脚本对完整下载报告上游哈希匹配；截断/错误摘要拒绝；模型标识与 tokenizer revision 固定；`pytest` 对资源边界通过。若环境不支持，记录精确阻塞并停在此阶段。
- 提交建议：`feat(step2): verify pinned crosslingual model resources`。
- 停止边界：未通过真实上游权重验证不得编码或建库，不接受本地自记哈希。

### STEP2-P0B：跨语言索引构建与加载契约

- 目标：对固定 CWE 5748 段以 Qwen3-Embedding-0.6B 建立可校验向量索引。
- 依赖：P0A 资源完整且模型可以真实加载；已有固定 CWE 快照可复现。
- 产物：独立索引模块/CLI/manifest、原向量与 passage_id 映射、保存重载检查。
- 验收命令与预期：真实编码 5748 段；检查维度、有限/非零向量、快照兼容和所有哈希；新进程加载成功且检索次序/分数稳定；索引不入库。
- 提交建议：`feat(step2): build and validate multilingual embedding index`。
- 停止边界：真实索引未保存重载通过，不开始 P1 指标或 MMR 适配。

### STEP2-P1A：中文平行题集生成

- 目标：从冻结的英文 probe-v1 逐题生成中文 question 平行稿，评测元数据原样保留。
- 依赖：P0A/P0B 完成；取得翻译方案的模型/工具与可复现运行信息。机器翻译只用于离线题集派生，禁止进入在线查询链路。
- 产物：新版本中文 JSONL、独立生成器和字段不变性验证；标记 `machine_translated_needs_human_review`、`reviewer=null`、源问题 SHA-256。
- 验收命令与预期：针对性 pytest；记录数/唯一题 ID 与英文集一致；`gold_facts`、证据 ID、source snapshot 及全部非 question 字段逐值相同；中文 question 非空，原文件字节不变。
- 提交建议：`feat(step2): create unreviewed Chinese probe parallel set`。
- 停止边界：无明确模型/工具来源时不伪称“已翻译”；不运行检索门禁，不人工复核题集。

### STEP2-P1：双语检索门禁

- 目标：同题同快照对比跨语言检索和英文 DPR 历史基线。
- 依赖：P0B 和 P1A 通过。
- 产物：独立评测入口及逐题输出，按语言/N 记录 Recall@N、池内平均余弦与中英等价性。
- 验收命令与预期：新旧脚本 `--help` 通过；真实中英各 40 题或按工作单实际完整题集运行；英文各 N 不低于历史的 90%；等价性目标 ≥0.85。低于 0.60 明确停止 P2/P3；0.60–0.85 暂停并提交差距分析。
- 提交建议：`test(step2): evaluate bilingual retrieval gate`。
- 停止边界：P1 门禁不满足时不运行 P2/P3；探针只作探索性诊断。

### STEP2-P1B：跨语言召回门禁实测

- 目标：在 40 个相同 question ID 上分别运行原英文题和 P1A 中文译题，计算 N=20/50/100 的必选证据 Recall@N、中英等价性及池内平均两两余弦。
- 依赖：P0A/P0B、P1A 均通过；只读 probe-v1 历史 DPR 对照与题集。
- 产物：新评测脚本、逐题运行记录和 `outputs/` 汇总；原 `eval_probe.py` 与历史输出保持不变。
- 验收命令与预期：中文和英文均直接由 Qwen3 编码；真实 40×2 检索完成；英文各 N 达到历史 DPR 对照 90% 门槛；报告中英等价性和与 0.857 对比的两两余弦；按 `<0.60`/`0.60–0.85`/`≥0.85` 规则决定是否停止/暂停/通过。
- 提交建议：`test(step2): measure bilingual retrieval gate`。
- 停止边界：若等价性 `<0.60`，不开始 P2/P3；若在 `[0.60,0.85)`，提交差距分析并暂停后续门禁；40 题仍仅作探索性诊断。

### STEP2-P2A：检索分数适配的 MMR

- 目标：显式将 Qwen 检索分数与同空间段落向量传入既有 MMR 逐轮逻辑。
- 依赖：P1 通过；证明可在不修改冻结 MMR 文件前提下复用 `select_mmr()`。
- 产物：新适配器、新配置版本、检索 Top-K/MMR 逐轮记录。
- 验收命令与预期：边界与回归测试覆盖空池、K=0、不足 K、单候选、全同分、NaN/Inf、零向量、lambda 两端；lambda=1 与检索 Top-K 完全一致；增量与参考逐轮顺序/分数一致；两冗余尺度均可计算。
- 提交建议：`feat(step2): adapt retrieval relevance to shared MMR selector`。
- 停止边界：若既有接口无法满足显式分数契约，停止并提交接口适配提案，不改冻结文件。

### STEP2-P2B：双语筛选比较与尺度扫描

- 目标：同候选池比较中英文 Top-K/MMR，并对 lambda 和两种冗余尺度留档。
- 依赖：P2A 单元验证通过且 P1 门禁通过。
- 产物：指标脚本和忽略的逐题/汇总产物，含 Recall@5、全覆盖、Hit、胜负、冗余、分歧及配对 bootstrap 95% CI。
- 验收命令与预期：真实中文/英文评测均完成；lambda 从 0 到 1；lambda=1 选择完全一致；未显著时报告无显著差异；不得把 40 题结果写成论文结论。
- 提交建议：`test(step2): compare bilingual MMR and retrieval top-k`。
- 停止边界：仅开发语义可用于参数选择；若 P1 门禁失败不进入本阶段。

### STEP2-P3：中文生成与引用校验

- 目标：完成至少 10 个中文问题的真实生成链路及确定性引用检查。
- 依赖：P2B 输出齐全；固定 Qwen2.5-7B-Instruct revision 与服务端模型核验可用。
- 产物：专属 LLM 客户端、固定 prompt/config、句子切分/引用校验器、新查询 CLI、结构化结果。
- 验收命令与预期：中文原问直接检索，无翻译调用；temperature=0/top_p=1/max_tokens 固定；逐句编号存在且范围合法；报告有效引用、无引用陈述与词面弱支持；至少 10 条人工抽查记录；响应标识和 token/延迟/prompt 哈希可查。
- 提交建议：`feat(step2): answer Chinese queries with validated citations`。
- 停止边界：引用校验确定性失败时不得静默修答案或称链路通过；资源失败记录为阻塞。

### STEP2-P4：文档、旧路径回归与交付审计

- 目标：整理复现命令、四门禁结果、限制和跨会话状态，确认英文路径未破坏。
- 依赖：P0–P3 的实际状态均已记账（失败阶段也可保留为未完成，不得改判通过）。
- 产物：路线文档、PROGRESS/HANDOFF、README 与 scripts/data 导航更新。
- 验收命令与预期：`.venv/bin/python -m pytest -q`、`.venv/bin/python -m compileall -q src scripts`、`git diff --check` 成功；新旧 CLI help、索引/模型加载核查及旧评测脚本检查有结果；推送及远端三值哈希一致。
- 提交建议：`docs(step2): record verified route and acceptance status`。
- 停止边界：真实链路未通过不得标整体验收；环境/门禁阻塞保留唯一具体恢复动作。

## 中断、推送失败与恢复

- 一个阶段的验证来不及完成：先保存可运行状态，运行可完成的最小检查；更新 HANDOFF 的唯一下一步，例如一条具体失败测试命令；提交 `checkpoint(Pxx): incomplete - ...`。
- 推送失败：把失败的提交哈希、时间、原始错误的非敏感摘要、远端/分支写入 HANDOFF，文档更新再本地提交；最终回复报告实际 HEAD 和未同步状态。
- 恢复推送：`git fetch origin` → 检查 `git log --oneline --left-right HEAD...origin/baseline/cwe-dpr-reader-mmr`（远端分支存在时）→ 保留双方历史解决差异 → `git push -u origin baseline/cwe-dpr-reader-mmr` → 核对 `git ls-remote --heads origin baseline/cwe-dpr-reader-mmr`。
- 同步核验若远端领先，使用 `git merge-base --is-ancestor <阶段提交> origin/baseline/cwe-dpr-reader-mmr` 确认包含关系；不得静默将远端覆盖。
