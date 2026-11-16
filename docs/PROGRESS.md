# 第一阶段基线进度

总体状态：**未实现完整基线，未通过真实端到端验收**。
当前阶段：P04 已提交推送并核验；正在恢复 P05 DPR 编码/索引草稿与真实资源。功能推进顺序见 IMPLEMENTATION_PLAN。
时间使用 Asia/Shanghai（UTC+08:00）；未记录的历史执行时间不补造。

## 已完成且验证通过

- 已完整读取 `docs/theprompt.md` 的全部要求，以及 README、配置、现有 schema/DSES/ID 路由/指标和 6 项测试代码。
- 工作区检查：任务分支为 `baseline/cwe-dpr-reader-mmr`，初始 HEAD 为 `e02886629f045b3de2eb9b0005e4117487faa1dc`；origin 为当前 GitHub 仓库；任务分支在初始检查时未存在于远端、没有 upstream。
- 旧示例：`PYTHONPATH=src python scripts/smoke_demo.py` 成功，选中 description/mitigation 两段，used_tokens=190。**仅合成 DSES 示例，不是 DPR/MMR 验收。**
- `python -m compileall -q src scripts tests` 成功；只证明语法可编译，不证明单元测试或模型正确性。
- 资源现场核查：Python 3.12.11；RTX 4090，24564 MiB 总显存、约 24109 MiB 空闲；约 48 GiB 磁盘可用；内存约 64 GiB。数值为本次采样，非长期保证。

- P00 文档一致性校验通过：规格完整原文区与源文件逐字一致（换行归一化）；原始字节 SHA-256 一致；本地文档链接存在；五类进度、六项交接字段及 P00–P10 计划齐全。

- P00 已完成：完整规格和恢复机制提交 `0766ce4bd693138b0523d371d64cd8f520287a09` 已推送，远端分支与本地哈希一致。

- P01：独立 .venv 安装成功；原有 6 项与新增 20 项配置测试共 **26 passed**；旧示例通过；pip check 无冲突；baseline.v1 配置读取校验通过。宿主 CUDA 张量运算通过，未做模型推理。

- P01 提交 `8496cf309b7fd768233f23d15f242c15b9e6285f` 已推送且经 ls-remote 核验。
- P02：真实 CWE 4.20 ZIP 哈希与历史清单一致；969 个 Weakness → 5454 个来源单元，Category/View 排除，嵌套语义配对保留；两次解析完全一致；契约与原有测试共 **43 passed**。详见 CWE_CONTRACT.md。

- P03：真实 tokenizer/固定 revision 与输入布局已核查，真实 CWE 生成 5748 段；两次构建字节一致；所有段落预算与来源内容覆盖检查通过；**52 passed**、pip check 无冲突。快照 `cwe:88e4eab3cc54f16611040a0e528d7a128253426e90ee5054327fd28449fee393`。

- P03 `2acbff7e3874638d04d7e7e69767d3402b4cced1` 已推送并核验。
- P04：完整池统一尺度、Reader Top-K、逐轮增量 MMR 与直接参考实现已通过 21 项针对性回归（包括指定 A/B/C 和 80 组随机等价性），全套 **73 passed**。详见 SELECTION.md。

## 已实现但尚未真实验证

- 原有 Evidence、DSES、指标、ID 提取现已通过原有单元测试；新基线模型与数据流程仍未实现。P00 的 pytest 缺失已在 P01 独立环境解决。
- 数据解析、真实 tokenizer 分段和正式 manifest/JSONL 已验证；P05 DPR 编码/索引已实现并通过合成回归，尚未真实推理；Reader 主流程尚未实现。MMR/Top-K 已单元验证，尚未接真实模型分数。

## 正在进行

- P05：恢复进入会话时已有的 models.py、retrieval/dpr.py、build_dpr_index.py 与 inference 依赖草稿；先核验真实权重完整性和独立运行依赖。

## 待完成

| 必须单列的主线工作 | 阶段 | 代码实现 | 单元验证 | 真实资源验证 |
| --- | --- | --- | --- | --- |
| CWE 字段契约与来源追溯 | P02–P03 | 已实现 | 通过 | 真实解析/分段/重载通过 |
| DPR 索引与召回 | P05 | 已实现，待真实核查 | 24 项资源/索引回归通过 | 权重已校验，待依赖/真实建库 |
| Reader 输出对齐 | P06 | 未开始 | 未开始 | 未开始 |
| 统一尺度处理 | P04 | 已实现 | 通过 | 后续接真实分数 |
| 逐轮 MMR | P04 | 已实现 | 通过 | 待 P09 |
| Reader Top-K | P04 | 已实现 | 通过 | 待 P09 |
| 普通回答 | P07 | 未开始 | 未开始 | 待 P09 |
| CLI 与共享运行记录 | P08 | 未开始 | 未开始 | 待 P09 |
| 真实端到端验证 | P09 | 未开始 | 不能替代真实验收 | 未开始 |
| 部署与复现说明 | P10 | 未开始 | 文档命令未重放 | 未开始 |

- P05：安装独立模型运行依赖、取得固定权重并实现 DPR 编码/索引/召回。
- 后续另列：增强模式、自动更新、正式 120 题核验集、开发集参数调优、正式实验。

## 受阻

| 条件 | 证据 | 影响 | 恢复动作 |
| --- | --- | --- | --- |
| pytest 缺失（已解除） | P01 的 `.venv/bin/python -m pytest -q` 26 passed | 已有测试现已执行 | 后续使用 .venv/bin/python |
| 真实 CWE 缺失（已解除） | P02 已取得并解析 4.20，原始 SHA-256 匹配 | 真实解析已验证 | 继续 P03，下载时间未知状态保留，不以登记时间替代 |
| 模型权重缺失（tokenizer 已解决） | P03 已固定并验证三个 tokenizer；尚无 pytorch_model.bin | DPR/Reader 推理未开始 | P05/P06 获取真实权重并验证 |
| 索引缺失 | data/processed 无真实索引 | 无法真实查询或重载验收 | P03/P05 生成并验证 |

P01 已在宿主环境执行 torch CUDA 张量求和（3.0），但未做 DPR/Reader 推理；faiss 未安装，是否使用及版本仍待索引阶段确定。上述是当前能力缺口，不等于已发生下载失败。网络推送状态单独见 HANDOFF。

## 本阶段文件变更记录

| 文件 | 用途 |
| --- | --- |
| AGENTS.md | 强制后续会话恢复顺序、阶段提交与状态真实性规则 |
| docs/theprompt.md | 原始任务输入纳入版本控制，保持原字节 |
| docs/BASELINE_SPEC.md | 完整保留技术要求、来源哈希、约束索引和恢复协议 |
| docs/IMPLEMENTATION_PLAN.md | P00–P10 小阶段依赖、产物、验证与提交边界 |
| docs/PROGRESS.md | 五类状态、证据、文件清单与实际时间线 |
| docs/HANDOFF.md | 分支/提交、命令结果、阻塞及唯一下一步 |
| docs/README.md | 增加恢复文档导航 |

P00 未修改工程代码；P01 增加 src/cyber_qa/config.py（校验配置）、configs/baseline.v1.json（冻结常量）、tests/test_config.py（配置回归）、requirements-dev.txt（测试工具版本）、docs/RUNTIME.md（环境与资源计划），并更新 configs/README.md。进入任务前的 install.sh 保持不动。

## 实际时间线

- 2026-11-13 14:13:27 +08:00：完成首轮环境、Git 与资源核查；发现 pytest、真实 CWE 与模型缺失。
- 2026-11-13（具体历史时刻未记录）：现有合成 smoke_demo 和语法编译检查成功；首次 pytest 尝试因未安装而失败。以上均为本次工作，未虚构历史测试结果。
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
