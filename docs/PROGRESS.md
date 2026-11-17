# 第一阶段基线进度

总体状态：**P00–P10 代码与技术验收完成；答案质量不足、尚未校准。**
当前阶段：P10 部署重放/文档审计及阶段提交推送核验均完成；本轮P00–P10无未完成工程阶段。
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

- 无进行中的工程阶段。本次仅补记P10推送核验；该收尾文档提交自身哈希以git rev-parse HEAD获取，并再次推送核验。

## 待完成（后续范围，不冒称本轮完成）

- 12题的独立人工复核、正式120题（开发80/冻结测试40）构建、综合问题/答案质量评估。
- 仅开发集参数调优、回退校准、正式实验；变更尺度须升级配置并重评λ。
- 增强模式、自动数据更新、Web界面；本轮不自动扩展这些工作。

## 受阻

无未解决的本轮资源或技术验证阻塞；历史缺pytest/CWE/完整权重/独立torch问题均已解除。质量不足已公开记账，不以技术验收掩盖，也不私自调参。推送状态见HANDOFF。

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

install.sh未改动/未提交；theprompt.md原始SHA-256仍为80dff079148170ee5ae3c7c81886b0551caabc9fc2c61ac2b3093ad596533735。原始数据、模型、大索引、环境与日志全部忽略。早期P00–P05文件及用途见各阶段Git历史/文档。

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

- 2026-11-17T14:54:51+08:00：按用户要求清理与当前基线无关的早期选择器兼容层，删除实现、测试、配置、合成脚本和旧数据类导出，更新主线导出与文档引用；`.venv/bin/python -m pytest -q` 结果为 `135 passed in 130.10s`，compileall 与 `git diff --check` 通过。清理提交 `9a055b2` 已创建；首次推送因 `gnutls_handshake() failed: The TLS connection was non-properly terminated` 失败，待重试并核验远端。
