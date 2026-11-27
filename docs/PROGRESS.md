# 第一阶段基线进度

总体状态：**P00–P10 代码与技术验收完成；答案质量不足、尚未校准。**
当前阶段：原 P00–P10 完成。用户追加 R01 四方案检索对照，代码、单元验证、本地真实模型实验、提交推送与远端哈希核验均完成。
时间使用 Asia/Shanghai（UTC+08:00）；历史时间不补造。下方时间线中的“未实现/待验证”为该阶段当时状态。

## 已完成且验证通过

| 主线工作 | 阶段 | 代码实现 | 单元验证 | 真实资源验证 |
| --- | --- | --- | --- | --- |
| 恢复机制/冻结规格/环境 | P00–P01 | 已完成 | 文档/配置校验通过 | 原始输入字节保留，独立环境通过 |
| CWE 字段契约与来源追溯 | P02–P03 | 已实现 | 数据契约/分段通过 | 969条/5454来源单元/5748段；重建字节一致 |
| DPR 索引与召回 | P05 | 已实现 | 26项资源/索引回归通过 | 5748×768真实建库/新进程重载通过 |
| Reader 输出对齐 | P06 | 已实现 | 20项Reader回归通过 | 单条/分批/反序/跨度回查通过 |
| 统一尺度处理 | P04 | 已实现 | 冻结尺度边界通过 | P06完整真实池通过 |
| 逐轮 MMR | P04 | 已实现 | 指定A/B/C、80组随机参考等价等通过 | 真实分数参考等价和P09流程通过 |
| Reader Top-K | P04 | 已实现 | 确定性/边界通过 | P09与MMR共用Reader结果 |
| 普通回答 | P07 | 已实现 | 6项回答回归通过 | 真实答案/证据可回查，语义充分性未评估 |
| CLI 与共享运行记录 | P08 | 已实现 | 12项编排/CLI回归通过 | 真实成功/失败JSON；一次Reader供两策略 |
| 真实端到端验证 | P09 | 已实现 | 单元不能替代真实验收 | 12题全流程+新进程重载通过 |
| 部署与复现说明 | P10 | 已完成 | 清理后全套135 passed，无skip | 第二个独立环境安装/测试/真实12题通过；干净进程重建通过 |

- P10 数据JSONL、向量、ID映射哈希与P03/P05相同，重放查询候选/分数/答案完全一致。详见 DEPLOYMENT.md。
- P09 指定支持段落仅4/12被召回，两策略均3/12被选中；12题实际答案及问题详见 ACCEPTANCE.md。**技术成功不等于语义正确、已校准或达到可用准确率。**
- 早期选择器兼容层已清理；当前筛选主线统一使用 MMR。

## 已实现但尚未真实验证

- CPU/其他GPU/Windows/macOS部署与性能未验收；本次为Linux x86_64、Python3.12、RTX4090。
- 抽取/原文回退只检查结构有效性，不判断语义充分性；正常输出显式not_assessed。未建立正确概率、稳定性能基准或跨环境数值保证。

## 正在进行

- R01 检索四方案对照、两次完整真实运行均完成，最终输出源码哈希对应最终代码；主提交和文档提交已推送，远端核验一致。探针题仍为机器起草、40/40 未人工复核；结果是探索性诊断，不是质量验收或论文结论。

## 待完成（后续范围，不冒称本轮完成）

- 12题的独立人工复核、正式120题（开发80/冻结测试40）构建、综合问题/答案质量评估。
- 仅开发集参数调优、回退校准、正式实验；变更尺度须升级配置并重评λ。
- 增强模式、自动数据更新、Web界面；本轮不自动扩展这些工作。

## 受阻

无未解决的本轮资源或技术验证阻塞；历史缺pytest/CWE/完整权重/独立torch问题均已解除。质量不足已公开记账，不以技术验收掩盖，也不私自调参。R01 探针集标签尚未人工复核，所以不把 exact passage Recall 当作语义答案质量；40题也不足以代表总体。推送状态见HANDOFF。

## 本轮文件变更记录

| 文件 | 用途 |
| --- | --- |
| src/cyber_qa/reader/dpr.py、__init__.py、README.md | P06输入布局/批次对齐/正文跨度/异常 |
| src/cyber_qa/config.py、data/candidates.py | Reader/回答集中规则，保存起止logits和空跨度原因 |
| scripts/check_dpr_reader.py、tests/test_reader.py | 真实Reader验收与20项合成回归 |
| src/cyber_qa/answering/ordinary.py、__init__.py、README.md；tests/test_answering.py | P07已选证据内普通回答与6项回归 |
| src/cyber_qa/pipeline/ordinary.py、__init__.py、README.md；__main__.py；tests/test_pipeline_cli.py | P08共享编排/CLI/运行产物与12项回归 |
| data/annotations/baseline_smoke.v1.json、README.md；scripts/check_baseline_smoke.py | P09固定12题/支持原文/真实全流程与独立进程重载 |
| docs/READER.md、ANSWERING.md、CLI.md、ACCEPTANCE.md、DEPLOYMENT.md | 各阶段规则、实测证据、质量限制与部署 |
| README.md、src/cyber_qa/README.md、scripts/README.md、configs/README.md、docs/README.md | 最新入口和模块导航，替换过时规划状态 |
| docs/RETRIEVAL.md、RUNTIME.md、PROGRESS.md、HANDOFF.md | 区分历史状态与最终状态、北京时间时间线与恢复 |
| 早期选择器兼容层及关联说明 | 已删除实现、测试、配置、脚本和旧导出；主线仅保留 MMR |
| src/cyber_qa/experiments/retrieval.py、comparison.py、__init__.py；scripts/compare_retrieval.py | R01 独立 DPR/BM25 混合/子问题/CWE 条目检索；共用 Reader/Top-K/MMR/答案，逐题 JSONL、对照 JSON/CSV/Markdown、模型与产物 provenance |
| tests/test_retrieval_experiments.py | R01 BM25/RRF/查询隔离、候选预算、分数与向量保留、条目全局保底、汇总、失败处理、历史结果只读和 CLI 回归 |
| docs/RETRIEVAL_EXPERIMENTS.md；README.md、docs/README.md、scripts/README.md、experiments/README.md、IMPLEMENTATION_PLAN.md | 一键命令、固定项/算法/参数、输出契约、指标与标注限制 |

install.sh未改动/未提交；theprompt.md原始SHA-256仍为80dff079148170ee5ae3c7c81886b0551caabc9fc2c61ac2b3093ad596533735。原始数据、模型、大索引、环境与日志全部忽略。早期P00–P05文件及用途见各阶段Git历史/文档。

## R01：DPR 与三个独立检索实验

**实现和隔离**：保留既有 `DPRIndex.search`、向量索引、`eval_probe.py` 和 `probe-eval-N*.json`；新入口 `scripts/compare_retrieval.py` 依次比较 `dpr`、`hybrid`、`subquery`、`hierarchical`，默认 N=20/50/100。混合为段落 BM25 + DPR 等权 RRF；子问题为原问题+受限规则拆分的 DPR 查询+RRF；层级为问题/语料预测 CWE 条目、条目内 75% 候选配额+全局 DPR 保底。四组共用问题、真实 CWE 快照、同一原 DPR 向量、Reader、K=5、λ=.5、同一 Top-K/MMR 和答案装配；每题每方法只跑一遍 Reader。检索代码接口不读取 `record_ids`、intent 或 gold 字段。所有 N/算法参数均未调优。

**验证分账**：新增 20 项独立实验测试通过；全套 `.venv/bin/python -m pytest -q` 为 `155 passed in 5.18s`；`compileall`、脚本 `--help`、`git diff --check` 通过。最终真实运行 `.venv/bin/python scripts/compare_retrieval.py --device cuda --output outputs/retrieval-comparison-v1-final` 完成 40×4×3=480 题方法流程，12 组零失败；CUDA RTX 4090、Python 3.12.11、DPR/Reader 权重在本机。新运行 DPR 的候选池、Top-K/MMR 选择与旧 N20/50/100 逐题一致，Reader relevance logit 最大差异为 0；旧结果复制并以 SHA-256 归档。独立复验指标与前次运行完全相同（排除计时字段）。模型/索引/数据及 outputs 仍未提交。

| N | 方法 | 必选证据 Recall@N | 全必选证据入池题率 | Top-K Recall@5 | MMR Recall@5 | Top-K 全覆盖 | MMR 全覆盖 |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 20 | DPR | 27.50% | 12.50% | 20.00% | 20.00% | 7.50% | 7.50% |
| 20 | BM25 + DPR | 73.75% | 55.00% | 37.50% | 38.75% | 15.00% | 17.50% |
| 20 | 子问题 DPR | 30.00% | 12.50% | 21.25% | 20.00% | 7.50% | 5.00% |
| 20 | CWE 条目级 | 40.00% | 22.50% | 23.75% | 26.25% | 5.00% | 7.50% |
| 50 | DPR | 43.75% | 27.50% | 22.50% | 21.25% | 10.00% | 5.00% |
| 50 | BM25 + DPR | 85.00% | 72.50% | 32.50% | 33.75% | 15.00% | 12.50% |
| 50 | 子问题 DPR | 45.00% | 25.00% | 23.75% | 21.25% | 7.50% | 5.00% |
| 50 | CWE 条目级 | 60.00% | 55.00% | 22.50% | 22.50% | 7.50% | 7.50% |
| 100 | DPR | 50.00% | 32.50% | 20.00% | 21.25% | 2.50% | 5.00% |
| 100 | BM25 + DPR | 91.25% | 85.00% | 25.00% | 22.50% | 5.00% | 5.00% |
| 100 | 子问题 DPR | 52.50% | 40.00% | 21.25% | 25.00% | 5.00% | 10.00% |
| 100 | CWE 条目级 | 70.00% | 67.50% | 26.25% | 26.25% | 7.50% | 10.00% |

**有限观察**：混合方案在三个 N 上均提高精确 passage Recall@N，配对 question bootstrap 95%区间分别为 +46.25pp `[+32.50,+60.00]`、+41.25pp `[+28.75,+53.75]`、+41.25pp `[+28.75,+53.75]`；最终 MMR Recall 相对 DPR 分别为 +18.75pp `[+5.00,+33.75]`、+12.50pp `[0,+25.00]`、+1.25pp `[-11.25,+13.75]`。因此新增 gold 入池未稳定转化为最终证据收益。子问题方案整体改善小且区间跨零；CWE 层级在 N=100 入池有 +20pp `[+11.25,+28.75]`，筛选收益仍不确定。MMR vs Top-K 的差异小、各方法的配对区间大多跨零。本探针40题为 `auto_drafted_needs_human_review`，所有 gold/候选/问题未经人工核验；指标为标注 passage ID / gold fact support availability，不评判实际答案正确性。不得调参结论化或作为论文测试结果。

**实验产物（outputs 忽略且未提交）**：`outputs/retrieval-comparison-v1-final/manifest.json`、`comparison.md/.csv/.json`、12 个方法 JSON/JSONL 和原有三个基线文件的只读副本。目录内记录 40 题及最终源码哈希、索引/模型元数据、实际权重 SHA-256、环境、参数、分阶段时间和逐题候选/Reader/MMR/答案。完整判读见 `docs/RETRIEVAL_EXPERIMENTS.md`。校验断言：manifest completed、12 组×40 题均成功、三种 DPR replay matched/分数 delta 0；第二次真实运行汇总（不含耗时）与第一次逐项相同。

## STEP1：探针集数据集优化（probe-v1，尚未标注）

分支 `step1/dataset-optimization`（基于 `baseline/cwe-dpr-reader-mmr` 的 `ebd1f48`）。

**动机**：原 12 题冒烟集实测 12/12 为 `single_span`、12/12 只考 `description` 一个字段、
0 道多段题，因此 MMR 与 Top-K 选中的支持段同为 3/12、答案 12/12 相同。
在该题集上 MMR 在数学上无法体现价值，不能据此得出"MMR 无效"的结论。

**本次完成**：

| 项目 | 状态 | 证据 |
| --- | --- | --- |
| CWE 字段覆盖诊断 | 已完成 | 969 条目全部解析：Description 969、Common_Consequences 944、Potential_Mitigations 671、Extended_Description 579、Detection_Methods 499；含 Description + 至少 1 个其它字段的条目 946 个（97.6%） |
| `passage_id` 公式离线复算 | 已完成（12/12） | 按 `contracts.py` 冻结公式复算 `baseline_smoke.v1.json` 全部 12 条标注的 `passage_id` 与 `content_sha256`，逐字节一致 |
| 可出多段题的条目筛选 | 已完成 | 满足"≥3 字段 + 某字段 ≥4 兄弟段 + ≥2 段 ≤120 词"的条目 176 个；生成时按 ≤120 词放宽后可用 966 个 |
| 40 题骨架生成 | 已完成 | `data/annotations/probe-v1/`：skeleton.jsonl 40 条（40 个不同 CWE）、passage_index.json 200 段、manifest.json |
| 40 题问句与 gold_facts 起草 | 已完成（机器起草，待人工复核） | `draft.v1.json` → `qa.v1.jsonl`：40 条记录、72 条 gold fact、32 条多段题、8 条单段题；8 个 `answer_span` 与原文逐字符一致；40 条的 fact 均覆盖各自必选证据；`annotator=deepseek-auto-draft`、`status=auto_drafted_needs_human_review`、`reviewer=null` |

**尚未完成（不得冒称）**：40 题的 `question` 与 `gold_facts` **只有机器草稿，未经人工复核**；
未运行任何模型；无 Evidence Recall@5、无池内冗余度、无策略差异统计。
因此本轮**没有任何关于 MMR 有效性的结论**。

**下一步**：人工逐条复核 `draft.v1.json` 的问句、必选证据与 fact 依据（标准见
`data/annotations/probe-v1/README.md`），复核后重跑 `scripts/apply_probe_annotations.py`
并冻结哈希；随后跑门禁三指标。

## 实际时间线

- 2026-11-13 14:13:27 +08:00：完成首轮环境、Git 与资源核查；发现 pytest、真实 CWE 与模型缺失。
- 2026-11-13（具体历史时刻未记录）：语法编译检查成功；首次 pytest 尝试因未安装而失败。以上均为本次工作，未虚构历史测试结果。
- 2026-11-13T14:19:02+08:00：完整原文、来源哈希、链接、进度/交接字段及阶段列表校验通过；`git diff --check` 通过（新增文件另做暂存后检查）；提交推送待执行。

计划时间与实际时间分离：P01–P10 只有实施顺序，没有预先声称的完成时间。

- P00 暂存检查：默认 `git diff --cached --check` 将原始 theprompt.md 的 CRLF 报为行尾空白；为保留用户输入字节，使用 `git -c core.whitespace=trailing-space,space-before-tab,cr-at-eol diff --cached --check` 通过，未关闭真实尾随空格检查。

- 2026-11-13T14:36:06+08:00：P00 首次提交、推送、fetch 与远端哈希核验完成；记录核验结果并准备 P01。

- 2026-11-13T14:39:48+08:00：P01 开发环境、26 项测试、旧示例、pip check、配置读取及宿主 CUDA 张量检查通过；P00 收尾提交 `b857f41c8a1628ec31c27772d674abe749b5f319` 已经 ls-remote 核验。P01 等待提交推送。

- 2026-11-13T14:46:48+08:00：P02 真实归档下载、哈希核对、namespace/结构检查、两次真实解析及 43 项测试通过。新增 data/contracts.py（manifest/passage 校验与 ID）、data/cwe.py（语义解析）、tests/test_cwe_contracts.py（17 项契约回归）、docs/CWE_CONTRACT.md（规则与真实统计）；更新进度、交接、RUNTIME/文档导航。P02 待提交推送。

- 2026-11-13T14:50:37+08:00：P02 `05b0b9e52fbfc1b64dcbe99db0c39617a4d9dceb` 已推送且远端核验一致。P03 安装 transformers 4.57.1，首次模型 API 请求 TLS EOF 后按既有代理配置重试成功，已记录三模型 revision，正在下载 tokenizer 资源。

- 2026-11-13T14:57:20+08:00：P03 52 项测试通过；真实快照两次构建及全部 5748 段预算、来源覆盖检查通过。新增 chunking/preprocess/resources、资源获取与预处理脚本、模型 revision 配置、tokenization 依赖锁和测试；更新 pyproject 与文档。待本阶段提交推送。

- 2026-11-13T15:03:10+08:00：P04 新增 data/candidates.py（完整候选与跨度契约）、selection/mmr.py（统一尺度/两策略/参考实现）、tests/test_mmr.py、docs/SELECTION.md；21 项选择回归与全套 73 项测试通过，准备提交推送。

- 2026-11-16T10:40:15+08:00：恢复时 HEAD/远端均为 `cd5c629c2b0490070e2277812b195672f64d4b25`，P04 已同步；73 项测试再次通过（62.78s）。发现已有 question 权重只有 10,922,208 字节，上游固定 revision LFS 要求 437,986,065 字节，原下载器本地收据不足以证明完整性；P05 先修复上游校验。保留已有 P05 草稿与 install.sh。

- 2026-11-16T10:46:34+08:00：P05 下载完整性修复与索引契约 24 项回归通过；全套 97 passed in 2.05s，pip check 无冲突（torch 安装前）。question/context 权重已经上游完整性核验；独立 torch/CUDA 依赖及 Reader 下载进行中。新增/修改文件及用途见 HANDOFF、RETRIEVAL；未开始 P06。

- 2026-11-16T10:50:59+08:00：修复后下载命令退出 0，question/context/reader 三角色权重均通过上游 LFS 大小和 SHA-256；本地收据 outputs/p05-verified-weights.json 不上传，权重不上传。独立运行依赖仍在安装，未声称真实模型推理通过。

- 2026-11-16T10:53:45+08:00：P05 中途恢复检查点 `0f9875a5eb2dc598d72f28526bbb5bc1a9875fb7` 已提交推送，fetch/ls-remote 核验一致；依赖下载完成，正在本地安装，继续真实验收。

- 2026-11-16T10:58:24+08:00：独立 torch 2.9.1+cu128 安装与 pip check/CUDA 张量检查通过。首次建库因官方旧 pooler 多余参数被严格检查拒绝；核查源码/三个实际 state_dict 后限定允许未使用的 pooler/position_ids，补充回归后建库成功。5748×768 向量，离线编码/写入 8.972s，模型加载 3.149s。真实 SQL injection 查询 20 候选，两个新进程重载结果完全一致；全套 99 passed in 4.34s。新增 requirements-inference.txt；其余文件清单见 HANDOFF，未上传权重/数据/索引/日志，P06 未展开。

- 2026-11-16T11:00:24+08:00：P05 真实验收提交 `aa6f219e5c823653c58c632defcc459c2adf6adf` 已推送当前任务分支；fetch、远端跟踪分支与 ls-remote 均等于本地 HEAD。补记同步结果，最终文档提交仍需推送并核验；其自身哈希使用 git rev-parse HEAD 获取。

- 2026-11-17T09:57:35+08:00：P06 真实形状探针、20 候选单条/分批/反序对齐、跨度回查与两策略共用通过；全套 119 passed in 4.54s（新增 20 项）。新增 reader/dpr.py、reader/__init__.py、tests/test_reader.py、scripts/check_dpr_reader.py、docs/READER.md；更新 config.py（ReaderConfig）、data/candidates.py（起止 logits/空跨度原因）、Reader 说明与配置/文档导航及恢复文档。真实首位跨度不是定义，记录质量限制，不冒称语义正确或端到端通过。准备提交推送。

- 2026-11-17T10:00:05+08:00：P06 `86e5ed400759bd198822c8cc2eb8e5339251a4ae` 推送并 fetch 核验一致。首次 commit 缺身份失败，随后沿用历史 Codex/codex@localhost 以单次 -c 参数提交成功，未改全局 Git 配置。开始 P07。

- 2026-11-17T10:01:21+08:00：P07 新增 answering/ordinary.py、__init__.py、tests/test_answering.py、docs/ANSWERING.md；更新 AnswerConfig、回答说明/导航/恢复文档。全套 125 passed in 4.49s；复用 P06 真实评分装配通过，不声称完整端到端。规则明确结构合法不等同语义充分；准备提交推送。

- 2026-11-17T10:03:27+08:00：P07 `7ec81b5250e71cb0f59a8e6e388857d820826b0b` 已推送、fetch 核验一致；开始 P08。

- 2026-11-17T10:05:44+08:00：P08 新增 __main__.py、pipeline/ordinary.py、pipeline/__init__.py、tests/test_pipeline_cli.py、docs/CLI.md；更新 pipeline 说明及恢复文档/导航。全套 137 passed in 4.64s；真实 CLI 两策略单条查询退出 0，缺索引退出 1 且保存结构化失败。两策略一次 Reader/一次归一化计数回归通过。P09 冒烟/重载未完成，准备提交推送。

- 2026-11-17T10:07:50+08:00：P08 `b28b783ac1686a9cbae4c2d7f849b99c84ae4786` 已推送、fetch 核验一致；开始 P09，12 道题及支持原文由 Codex 逐条核对，未声称独立人工复核。

- 2026-11-17T10:09:39+08:00：P09 新增 data/annotations/baseline_smoke.v1.json、scripts/check_baseline_smoke.py、docs/ACCEPTANCE.md；更新标注说明/导航/恢复文档。12 题真实全流程与独立新进程重载均通过；支持段召回 4/12，两策略选中均为 3/12；明确记录语义质量不足、未独立人工复核、未调参。全套 137 项回归与 compileall 通过。准备提交推送。

- 2026-11-17T10:10:33+08:00：P09 提交已推送、fetch 核验一致；开始 P10 独立进程重放与文档审计，准确哈希见 HANDOFF。

- 2026-11-17T10:16:59+08:00：P10 原环境全量预处理/建库/查询重放通过，JSONL/向量/映射哈希完全一致；新建 outputs/p10-venv 按锁安装成功，pip check无冲突，137 passed in 4.74s，无skip；新环境12题真实全流程和独立子进程重载再次通过。重写README/核心/脚本导航，新增DEPLOYMENT与验收映射，历史文档显式标记阶段边界；准备最终提交推送。

- 2026-11-17T10:18:10+08:00：第二个隔离环境另行全量预处理/建库/查询完成，JSONL/向量/映射哈希和完整查询结果精确一致；文档本地链接、git diff --check、原始输入/冻结规格校验通过。所有P00–P10技术验收完成，待最后提交推送核验。

- 2026-11-17T10:19:47+08:00：P10 `402abef6e87a50a775b17b9cb14d095b4b69f3c1` 已推送，fetch/远端跟踪分支/ls-remote与本地完全一致。本次补记同步结果；包含本条记录的收尾文档提交自身哈希以git rev-parse HEAD获取，提交后再次推送并核验。工作区仅保留受保护install.sh。

- 2026-11-17T14:54:51+08:00：按用户要求清理与当前基线无关的早期选择器兼容层，删除实现、测试、配置、合成脚本和旧数据类导出，更新主线导出与文档引用；`.venv/bin/python -m pytest -q` 结果为 `135 passed in 130.10s`，compileall 与 `git diff --check` 通过。清理提交 `9a055b2` 已创建；首次推送因 `gnutls_handshake() failed: The TLS connection was non-properly terminated` 失败，随后重试成功，`e01a59375bcc125e88c5358cc089aac929a0dee2` 已完成远端核验。

- 2026-11-23T14:21:33+08:00：新增 STEP1 探针集数据集优化分支 `step1/dataset-optimization`（基于 `ebd1f48`）。本次为纯数据分析与标注脚手架，未下载权重、未建索引、未跑模型：完成 CWE 字段覆盖诊断（969 条目，946 个可用单段以上多字段条目）、`passage_id` 公式离线复算（对既有 12 条冒烟标注 12/12 逐字节一致）、多段题候选筛选（176 个条目满足竞争度条件），并生成 `data/annotations/probe-v1/` 的 40 题骨架（模板 A12/B8/C8/D4/E8，40 个不同 CWE，219 个候选段落索引）。`question` 与 `gold_facts` 留空待人工标注。同日修复工作区 Windows 权限缺陷（补当前用户完整控制权限，备份见工作区外 acl-recovery 目录），并通过本地代理 `127.0.0.1:7877` 完成远端 fetch 与基线分支落地。

- 2026-11-23T14:37:57+08:00：为 STEP1 的 40 题补齐 `question` 与 `gold_facts` 机器草稿。新增 `draft.v1.json` 与合并校验脚本 `apply_probe_annotations.py`，产出 `qa.v1.jsonl`：40 条记录、72 条 gold fact、32 条多段题、8 条单段题带 `answer_span`；脚本严格校验必选/补充证据均在候选池、fact 的 `supported_by` 合法、多段题 fact 覆盖全部必选证据、单段题 quote 与原文逐字符一致（含跨行匹配），全部通过。标注人记为 `deepseek-auto-draft`、状态 `auto_drafted_needs_human_review`、`reviewer=null`，**未经人工复核**。同时新增 `docs/COMMIT_LOG.md` 提交记录表（记录时间、任务名称、主要内容），并修正候选池按字段设限的缺陷（此前模板 C 的 8 道题候选池全为 `detection_methods`）。

- 2026-11-24T10:12:29+08:00：开始 R01 独立检索实验实现；Git HEAD=`16fc82aa57bd67684eaad182654bd9f9bfb5b3a3`，分支 `step1/dataset-optimization`，远端跟踪分支同步，工作区仅有受保护 `install.sh`。新增独立实验包/一键比较 CLI 和20项回归；首次测试 fixture 篡改不可变 Passage 导致 10 项 setup error，改用合法原对象后 `.venv/bin/python -m pytest -q tests/test_retrieval_experiments.py` 为 `20 passed`；全套 `155 passed in 5.18s`，help/compileall/diff-check 通过。CUDA RTX4090 两轮真实运行各完成 480 条流程，第二轮与第一轮非计时汇总一致；原 DPR 与历史 N20/50/100 选择、Reader 分数逐项匹配。结果见 R01 表、[检索四方案实验](RETRIEVAL_EXPERIMENTS.md)及 `outputs/retrieval-comparison-v1-final/`。主提交 `56208ff358d7196e8c7aa2698c3f1e0634adfc0c` 已创建，文档收尾提交/推送/远端核验待执行。
- 2026-11-24T10:26:16+08:00：R01 主提交 `56208ff358d7196e8c7aa2698c3f1e0634adfc0c` 与文档提交 `28277b2d1c2c4277ee32c5979a207d4930409c87` 已推送至 `origin/step1/dataset-optimization`；fetch 后本地 HEAD、origin 跟踪分支及 `ls-remote` 哈希一致。唯一未跟踪文件仍为受保护的 `install.sh`。

## STEP2：跨语言免翻译路线（`step2/crosslingual-rag`）

依据：[STEP2 完整规格](BASELINE_SPEC_V2.md) 和 [STEP2 工作单](theprompt_2.md)。本节只记录 STEP2，不改变 P00–P10/R01 历史状态；所有真实结果须与代码、单元测试、真实模型推理、真实端到端分别记账。

### 已完成且验证通过

| 项目 | 状态 | 证据 |
| --- | --- | --- |
| 阶段 0 恢复与自检 | 已完成 | 已读取指定文档；`docs/theprompt_2.md` 存在且由 `92b1543` 引入；本地/跟踪/远端 `step1/dataset-optimization` 哈希一致 |
| STEP2 分支 | 已完成 | `step2/crosslingual-rag` 已创建并推送；初始三值核验均为 `92b154328849fe8951d53ab7186521ef88a7e73a` |
| STEP2 恢复规格与阶段计划 | 已完成且验证通过 | `BASELINE_SPEC_V2.md`、STEP2 计划、进度、交接和导航提交 `f6d68e8`；`git diff --check`/staged check 通过，远端三值核验一致 |
| P0A 上游模型元数据核查 | 通过 | 两个固定 Hugging Face revision 返回身份匹配；Qwen3 与 Qwen2.5-7B 全部上游 LFS 文件逐项实测大小/SHA-256 匹配，7B 文件经 ModelScope 获取 |
| P0A 资源校验器回归 | 通过 | `.venv/bin/python -m pytest -q tests/test_crosslingual_resources.py`：`7 passed`；未覆盖真实模型推理 |
| P0A 两模型本地加载/推理探针 | 通过 | Qwen3 CUDA 产生 2×1024 有限归一化向量；Qwen2.5-7B-Instruct bfloat16 成功加载到 RTX 4090 并完成 80-token 贪心生成；单条探针不代表 P3 端到端验收 |
| P0B Qwen3 CWE 向量索引 | 通过 | 真实编码 5748 段、1024 维 float32、0 截断；索引哈希保存并从新进程重载；中文/英文 SQL injection 查询都召回 CWE-89 description |
| P1A 中文平行题集派生 | 通过（机器翻译，未人工复核） | 固定 Qwen2.5-7B 实际生成 40 道中文问题；验证 ID、source question SHA-256、所有非 question 字段逐值不变；源英文 JSONL SHA-256 保持不变 |

### 已实现但尚未真实验证

- P0A 模型资源已按上游 LFS 大小/SHA-256 核验；两模型本地 tokenizer/model 加载通过，Qwen3 与 7B 均完成真实模型推理探针。P0B 的索引代码、回归和真实 5748 段建库/重载也已完成。
- P1 双语检索门禁、P2 MMR 适配、P3 至少 10 题完整中文回答/引用校验仍未完成；真实短生成探针不等同于真实端到端验收。
- 规格定义了 Qwen3-Embedding-0.6B 检索、同空间余弦 MMR、Qwen2.5-7B-Instruct 中文回答、引用校验和字段契约；未实测的 revision、权重摘要、输入预算、服务端标识均未冻结为事实。
- P0A/P0B 模块和单元回归已实现；真实 Qwen3 编码、真实 7B 短生成、真实索引构建/重载均通过。仍未通过任何 P1 双语 Recall 门禁或完整中文 RAG 端到端验收。

### 正在进行

- STEP2-P1B：实现并运行 40 组英文/中文平行题 Qwen3 检索，核对 Recall@N 与中英等价性门禁。

### 待完成

- STEP2-P1：中文/英文检索 Recall@N、中英等价性、池内余弦和门禁判读。
- STEP2-P2：显式检索相关性适配既有 MMR、两种冗余尺度、lambda 扫描及配对 CI。
- STEP2-P3：至少 10 题中文生成、编号引用校验和人工事实抽查。
- STEP2-P4：路线文档、部署复现、英文 v1 回归和最终审计。

### 受阻

- 2026-11-26 的历史自检曾显示 CUDA 不可用、磁盘约 27G；该环境快照不代表当前环境。本次 2026-11-27 自检显示 RTX 4090、CUDA 可用、磁盘可用 25G，因此目前没有硬件阻塞。
- `models/crosslingual/Qwen--Qwen3-Embedding-0.6B/97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3/` 的 `model.safetensors`（1,191,586,416 字节，SHA-256 `0437e45c94563b09e13cb7a64478fc406947a93cb34a7e05870fc8dcd48e23fd`）与 `tokenizer.json`（11,423,705 字节，SHA-256 `def76fb086971c7867b829c23a26261e38d9d74e02139253b38aeb9df8b4b50a`）均匹配上游。
- Qwen2.5-7B Hugging Face 上游四分片核验通过；魔搭下载文件均与 pinned revision 的大小/SHA-256 匹配。Hugging Face 遗留 `.incomplete` 缓存不可作模型文件，保留在被忽略目录；当前磁盘剩余约 11G。
- 不存在当前 P0A/P0B 硬件或资源阻塞。GPU/transformers 结果只适用于当前 RTX 4090/Linux/Python 环境。
- 受保护未跟踪文件 `install.sh` 保留不动；模型、索引及运行产物均未提交。

### STEP2 文件变更记录（本阶段）

| 文件 | 用途 |
| --- | --- |
| `docs/BASELINE_SPEC_V2.md` | 完整 STEP2 公式、字段契约、边界、提示词、门禁、结论口径和资源阻塞 |
| `docs/BASELINE_SPEC.md` | 顶部仅增加 v2 规格链接，保留 v1 冻结内容 |
| `docs/IMPLEMENTATION_PLAN.md` | 追加 STEP2-DOC、P0A/P0B、P1、P2A/P2B、P3、P4 小阶段 |
| `docs/PROGRESS.md` | 本 STEP2 五类状态、文件清单、验证和时间线 |
| `docs/HANDOFF.md` | 本阶段分支、命令证据、阻塞和唯一下一步 |
| `docs/README.md` | 增加 STEP2 v2 规格导航 |
| `docs/COMMIT_LOG.md` | 追加本阶段提交记录，哈希按规则留待后续补填 |
| `configs/crosslingual-models.v2.json` | 两个模型的固定 revision 配置 |
| `scripts/check_crosslingual_resources.py` | 查询 Hugging Face revision/LFS 元数据、可选下载快照、实测本地文件 SHA-256 |
| `tests/test_crosslingual_resources.py` | 上游身份、LFS 元数据、本地哈希、固定 revision 下载参数回归 |
| `requirements-crosslingual.txt` | 单独固定资源获取依赖 `huggingface_hub==0.36.2` |
| `src/cyber_qa/crosslingual_resources.py`、`scripts/build_crosslingual_index.py`、`src/cyber_qa/retrieval/crosslingual.py` | P0B Qwen3 同模型编码、原始向量持久化、manifest 哈希/兼容检查和 cosine 召回 |
| `tests/test_crosslingual_index.py` | 索引维度/有限性/零向量、文件篡改、兼容性与余弦检索回归 |
| `src/cyber_qa/experiments/chinese_probe.py`、`scripts/make_chinese_probe.py`、`tests/test_chinese_probe.py`、`data/annotations/probe-v1-zh/` | 离线生成中文机器翻译平行题，校验题 ID/非 question 字段/source hash；产物明确未人工复核 |

### STEP2 实际时间线（Asia/Shanghai）

- 2026-11-26T15:37:33+08:00：远端提交 `92b1543` 引入 `docs/theprompt_2.md`，本地同步确认。
- 2026-11-26T16:02:42+08:00：阶段 0 环境自检记录完成；发现受保护 `install.sh`、CUDA 不可用和 STEP2 模型未下载。
- 2026-11-26T16:04:57+08:00：创建并推送 `step2/crosslingual-rag`，初始 HEAD 为 `92b154328849fe8951d53ab7186521ef88a7e73a`。
- 2026-11-26T16:19:25+08:00：完成 STEP2 v2 规格和小阶段计划；`git diff --check` 与 staged diff 检查通过，确认 v1/R01 冻结文件哈希保持不变；提交 `f6d68e8`。
- 2026-11-26T16:20:58+08:00：`f6d68e86286a53c6517e69a50815b1fd87977c84` 已推送；fetch 后本地 HEAD、`origin/step2/crosslingual-rag` 与 `git ls-remote` 三值一致。
- 2026-11-27T09:40:38+08:00：第二次会话恢复检查；切换到已有 STEP2 分支 `step2/crosslingual-rag`，其起始 HEAD/远端均为 `50c89def6dc7d80375f8803d4d0df37687618a95`。工作区有三个 P0A 相关未跟踪文件及受保护 `install.sh`。`nvidia-smi` 显示 RTX 4090 24GB，磁盘可用 25G，Torch `2.9.1+cu128` 且 CUDA 可用；Qwen 模型目录仍待核验。
- 2026-11-27T10:14:31+08:00：ModelScope 下载的 Qwen2.5-7B 四分片通过 pinned revision 上游大小/SHA-256 校验；两个模型 tokenizer 加载成功。
- 2026-11-27T10:14:31+08:00：Qwen3 实际 CUDA 推理返回中文查询/英文段落 1024 维归一化向量；同一时间点记录 tokenizer 和资源核验完成。
- 2026-11-27T10:21–10:26+08:00：Qwen2.5-7B bfloat16 加载 RTX 4090 并完成 80 token 贪心生成探针。探针输出有限且符合中文/编号 prompt 结构，未做语义质量验收。
- 2026-11-27T10:30:12+08:00：使用真实 Qwen3 对 CWE 4.20 的 5748 段构建最终原始向量索引：1024维、float32、cosine、0 段超长截断；向量 SHA-256=`734393d803ed2a31de8c39a17f09e69b61462191d34d27009e3337f39c8b9fa2`。新进程校验哈希/快照/revision 后，中英文 SQL injection 查询均召回 CWE-89 description。最终全套 `.venv/bin/python -m pytest -q`=`169 passed in 4.82s`；`compileall` 与 `git diff --check` 通过。P1 评测尚未运行。
- 2026-11-27T10:33:30+08:00：P0A/P0B 主提交 `758e5cf9cf15e2ceb5d33769f8cfda34ca4051ef` 已推送；fetch 后本地 HEAD、`origin/step2/crosslingual-rag` 与 `git ls-remote` 三值一致。
- 2026-11-27T10:38:00+08:00：P0A/P0B 远端核验文档提交 `eaafe9b1c199f13a58517834ec9688c3a6c535ac` 已推送并三值核验。
- 2026-11-27T10:38–10:39+08:00：固定 Qwen2.5-7B-Instruct 在 CUDA 上逐题翻译 probe-v1 40 道问题，生成 `data/annotations/probe-v1-zh/qa.v1.zh.jsonl`。9 项 P1A 单元测试通过；对 40 条做真实产物字段/hash 校验通过。源 `qa.v1.jsonl` SHA-256=`bdc2999481cf8680ecfa5cc2ba621947f41bade931e7e23057d54ec3ceca7ebf`，无文件差异；人工复核未做。P1A 文件和状态记录待提交推送。
