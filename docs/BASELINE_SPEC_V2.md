# STEP2 跨语言免翻译基线规格

规格版本：`crosslingual-rag-v2`。依据：用户提供的 `docs/theprompt_2.md`，其路线、约束和门禁为本规格来源。本文新增 STEP2 契约，不改写 [v1 冻结规格](BASELINE_SPEC.md) 或 v1 历史结论。模型仓库的不可变 revision、真实 tokenizer 预算及资源哈希须在 P0 实测登记；不得以浮动版本或本地自记值替代。

## 1. 目标与固定路线

```text
中文或英文问题（不翻译）
  -> Qwen3-Embedding-0.6B 问题向量
  -> 与同模型编码的 5748 段英文 CWE 向量作余弦检索，取 N=20
  -> 复用 cyber_qa.selection.mmr.select_mmr，K=5，默认 lambda=0.5（未调优）
  -> Qwen2.5-7B-Instruct 阅读英文证据并以简体中文回答
  -> 确定性引用校验，输出中文答案、编号引用和英文来源原文
```

问题不经过翻译器、翻译 API 或翻译模型。模型选型固定，不允许以其它检索或生成模型替换。英文 baseline-v1 的 DPR Reader 抽取式路径继续可用，作为冻结对照；STEP2 的中文回答是新增路径。

不可修改的 v1/R01 资产包括：`configs/baseline.v1.json`、`src/cyber_qa/selection/mmr.py`、`src/cyber_qa/reader/`、`src/cyber_qa/retrieval/dpr.py`、`data/processed/dpr-index-v1/`、`scripts/eval_probe.py`、`scripts/eval_retrieval.py`、`scripts/compare_retrieval.py`、`data/annotations/probe-v1/qa.v1.jsonl`、R01 实验代码及已记录历史结论。新功能使用新模块、入口和配置版本；模型、数据、索引、运行日志与 `outputs/` 不入库。

## 2. 配置与向量检索契约

### 2.1 配置

新增配置版本为 `crosslingual-rag-v2`（不得使用 `baseline-v1`）。默认 `candidate_count=20`、`max_passages=5`、`lambda_weight=0.5` 且 `parameter_status=untuned`、`epsilon=1e-12`。允许评测 CLI 显式覆盖语言、N 和 lambda；每次运行记录实际值。`lambda_weight` 必须有限且处于 `[0,1]`。新依赖另建精确版本约束文件，不修改 `requirements-inference.txt`。

### 2.2 向量与检索度量

索引向量 `v_i` 与问题向量 `q` 均由同一固定 revision 的 `Qwen3-Embedding-0.6B` 编码，保留原始有限向量，并建立仅供余弦比较的归一化视图。向量内积/范数在足够精度下计算；检索分数定义为：

```text
score(q,i) = cos(q,v_i) = dot(q,v_i) / (norm(q) * norm(v_i))
```

按 `score` 降序、`passage_id` 字典序升序确定性排序，去重后返回至多 N 条。候选记录里的 `retrieval_score` 与 `retrieval_rank` 保存此结果。不得翻译查询，不得将 Reader 或生成模型分数作为检索相关性。

### 2.3 相关性归一化

对单次查询完整、去重且有效的候选池 `C`，设检索余弦分数为 `s_i`：

```text
d = max(s_i) - min(s_i)
若 d > epsilon: Rel(q,i) = (s_i - min(s)) / d
若 d <= epsilon: 对所有 i，Rel(q,i) = 0
epsilon = 1e-12
```

只在完整池上计算一次，所有 MMR 轮次使用固定结果。空池的归一化结果为空元组；单候选和全同分候选的相关性均为 0。原始余弦必须保留。输入含 NaN/Inf，差值或计算溢出，或向量维度不一致时，查询失败并记录阶段与原因；不得静默替换分数。

### 2.4 冗余尺度与候选池归一化变体

候选段落之间在相同 Qwen 向量空间计算：

```text
cos(i,j) = dot(v_i,v_j) / (norm(v_i) * norm(v_j))
cos_clipped(i,j) = min(1, max(-1, cos(i,j)))
Sim_raw(i,j) = max(0, cos_clipped(i,j))
```

初始默认采用池内 min-max 的冗余方案 (a)：只收集完整候选池所有无序非对角 pair 的 `Sim_raw`，对该组 pair 值做一次 min-max；若 range `<= epsilon`，所有非对角 `Sim_norm=0`。对角线不进入 min/max，MMR 自身集合定义也不会比较候选与自己。小于零的余弦先按 0 冗余，再参与池内 min-max。`Rel` 和 `Sim_norm` 因此都在 `[0,1]`，并在 MMR 全程固定。若候选不足两个，非对角冗余为空/为 0。

必须实现同一评测下的方案 (b) 诊断：保持 `Sim_raw`，扫描更高 lambda 的敏感性曲线；不能据此覆盖默认 (a)，也不能挑选测试表现后声称预先设定。记录两种尺度下实际 `Rel`、`Sim` 分布及选择结果。如果实测显示 `Sim` 尺度会压制相关性，应报告依据和曲线；任何改变默认策略都须先更新规格/配置版本，并暂停受影响门禁等待用户确认。非有限值或零范数向量使查询失败。

## 3. MMR 选择契约

不得复制 MMR。新增适配器将显式计算的检索 `Rel`、同源向量 `Sim` 与候选记录传给现有 `select_mmr()` 逐轮选择逻辑；不得从 Reader 字段隐式读取相关性。适配器/调用契约须让选择器使用检索分数作为相关性值及相关性同分依据（检索 rank、passage_id 用作后续确定性排序键），同时保持现有逐轮更新和 K 规则。若现有函数不能在不改被冻结文件的条件下表达该契约，先停止实现并提交提案，不得改写 `mmr.py`。

定义已选集合 `S`，候选最大冗余 `R(i,S)`：

```text
R(i,S) = 0                                      if S is empty
R(i,S) = max(Sim(i,j) for j in S)               otherwise
MMR(i) = lambda * Rel(q,i) - (1-lambda) * R(i,S)
i* = argmax over candidates not in S of MMR(i)
```

每次选出一段后加入 S 并重新为所有剩余候选更新最大冗余，直到选满 `min(K, |C|)`。可用最大值增量更新，但必须与逐轮直接遍历参考实现等价。选择同分按：检索相关性原始余弦降序、`retrieval_rank` 升序、`passage_id` 字典序升序。

- `lambda=1.0`：MMR 顺序必须与按检索余弦排序的 Top-K 完全一致。
- `lambda=0.0`：第一轮惩罚为 0；同分按上述规则确定，之后只按最大冗余惩罚选择。
- 空池、`K=0`：返回空选择及空日志。
- `0 < |C| < K`：返回所有候选，不重复选择。
- 单候选：选中该候选（若 K>0）；相关性归一化为 0。
- 全同分：相关性归一化为 0；选择仍确定。
- NaN/Inf、计算溢出、零向量：拒绝本查询并记录，不输出部分成功结果。

每轮日志至少包含 `round`、`selected_before`、`passage_id`、原始/归一化相关性、最大冗余及其对应已选段、MMR 分数。返回顺序与证据关联信息。

## 4. 字段契约

### 4.1 跨语言向量索引清单

索引清单至少包含：

| 字段 | 含义 |
| --- | --- |
| `schema_version`、`config_version` | 索引 schema 与 `crosslingual-rag-v2` 配置版本 |
| `dataset_name`、`dataset_version`、`snapshot_id`、`corpus_sha256` | CWE 快照身份、版本与实际 passage 文件校验值 |
| `model_id`、`model_revision`、`tokenizer_id`、`tokenizer_revision` | 固定模型与 tokenizer 标识及不可变 revision |
| `upstream_weight_files` | 每个上游权重文件的 URL/revision、上游声明字节数和 SHA-256、实测字节数和 SHA-256 |
| `embedding_dimension`、`dtype` | 索引向量维数与存储类型 |
| `metric`、`normalized` | `cosine` 度量及原始向量是否归一化；本契约要求保存原向量并记录为未归一化 |
| `count`、`passage_ids_sha256`、`vectors_sha256`、`index_sha256` | 数量、有序映射、向量文件与索引工件摘要 |
| `input_budget`、`truncation_policy`、`pooling`、`prefix_policy` | 实测 tokenizer 长度、长输入处理、池化及模型要求的 query/document 前缀 |
| `software`、`device`、`created_at` | 软件版本、构建设备与带时区的创建时间 |

加载时验证 snapshot、语料哈希、模型和 tokenizer 的 revision、上游权重校验、维度、度量、向量/ID 文件哈希、有限/非零向量及索引参数。模型/索引/快照不兼容必须拒绝加载。所有未从上游元数据验证的权重都不视为通过；严禁只相信本地自行生成的哈希。

### 4.2 候选记录

每条检索/筛选候选至少包含：

| 字段 | 含义 |
| --- | --- |
| `passage_id`、`cwe_id`、`title` | 稳定证据和 CWE 标识 |
| `text`、`source_url`、`source_locator`、`snapshot_id`、`dataset_version` | 英文原文与可回查来源 |
| `retrieval_rank`、`retrieval_score` | Qwen 跨语言余弦召回顺序及原始检索分数 |
| `relevance_normalized` | 完整池 min-max 得到的相关性；不可命名或解释成 Reader 分数 |
| `embedding` 或稳定向量引用 | 同一索引中的向量映射；输出大结果时允许以 ID 引用索引向量 |
| `redundancy_scale`、`mmr_steps` | 本次冗余方案标识及逐轮日志 |
| `selected_order`、`selected` | 筛选后顺序与成员标志 |

生成器的分数、证据可信度或 Reader 字段不得混进此 MMR 契约。

### 4.3 中文作答输出

结构化回答至少包含：

| 字段 | 含义 |
| --- | --- |
| `schema_version`、`status`、`question`、`question_language` | 输出版本、执行状态、原始问题及语言，不改写问题 |
| `answer_type`、`answer_text` | 中文生成答案或明确失败/信息不足类型 |
| `citations` | 答案中的 `[n]` 与 evidence ID 的映射 |
| `evidence` | 每项 `n`、`passage_id`、英文原文、CWE 标题/编号、URL、locator、snapshot |
| `citation_validation` | 每条句子的引用编号、越界/缺引检查、词面弱支持结果与总状态 |
| `generation` | 请求模型、真实服务端模型标识、固定解码参数、prompt SHA-256、输入/输出 token 数、延迟、原始响应 |
| `model_provenance` | 请求 revision、provider/endpoint 标识和响应关联信息 |
| `timings`、`failure_reason` | 可分阶段耗时及结构化失败原因；成功时失败原因为空 |

证据编号按最终 MMR 选中顺序从 `[1]` 开始连续编号。输出必须包含所引英文原文和完整来源。原始模型响应、prompt 哈希和 token/延迟数据可写入被忽略的运行记录；不得把凭据写入结果或版本库。

### 4.4 引用校验字段与规则

确定性校验器逐句输出：

```text
sentence_index, sentence_text, citation_numbers, citation_ids,
has_citation, citation_in_range, lexical_overlap_tokens,
weak_support_pass, validation_errors
```

确定性句子切分按 `。！？!?`、换行切分；ASCII `.` 只在其后为空白或文本末尾时作为句界，句末紧邻的 `[n]` 引用归属于该句。校验器抽取答案和被引英文证据的词元：小写 ASCII 字母数字串（长度至少 3，另识别完整 `CWE-数字`）及连续汉字串的重叠二字窗口；使用固定版本的通用停用词集合过滤。每个有引用句至少有一个相交的非停用词元时 `weak_support_pass=true`，否则为 false。该词面规则仅是弱检查，不能等同语义支持。`valid_citation_rate` = 范围内有效 citation occurrence / 答案中全部 citation occurrence；`uncited_claim_rate` = 无引用非空句数 / 全部非空句数；`weak_support_rate` = 通过弱支持的有引句数 / 有引句数（分母为 0 时分别返回 `null` 并记录原因）。总结果至少包含这些比率、`sentence_count`、`all_citations_in_range`、`valid`。越界引用、无编号陈述句、弱词面重合检查失败都必须明确记账；校验失败不得静默改写模型答案。

## 5. 提示词、模型请求与回答边界

固定生成模型 `Qwen2.5-7B-Instruct`。prompt 必须明确：

1. 只使用给定英文证据，不使用外部知识或猜测。
2. 使用简体中文回答。
3. 每个句子都标注与证据编号对应的 `[n]` 引用。
4. 证据不足时明确说“现有资料无法确认”。

CWE 编号和技术术语保留英文。请求参数固定为 `temperature=0`、`top_p=1`、`max_tokens=512`；512 是 STEP2 初始配置，不代表长度调优完成。实际模型 revision、参数、服务端返回的真实模型标识、原始响应、prompt 哈希、token 数、延迟均写入结构化记录。若服务端返回模型标识与请求不符，记录不匹配并判定模型校验失败。参数、revision 与权重来源未实测前不写成已固定事实。

明确区分：无候选、候选少于 K、无选中证据、证据不足、引用校验失败、模型/索引不兼容、推理/网络失败。候选数量不能作为证据充分性依据；引用词面检查通过不能证明语义正确。禁止 LLM 参与相关性打分、筛选或引用自评。保留英文抽取路径作为原文子串保证。

## 6. 平行题集契约

从 `data/annotations/probe-v1/qa.v1.jsonl` 逐题创建独立中文平行题集；不得覆盖源文件。只翻译 `question` 文本，以下字段必须与英文源记录逐值相同：`passage_id`（若源记录含该字段）、`gold_facts`、`required_evidence_ids`、`optional_evidence_ids`、`source_snapshot`。保留其它所有原始标注字段，并添加机器生成、未人工复核的状态，例如 `translation_status=machine_translated_needs_human_review`、`reviewer=null`、`source_question_sha256`。本任务不做中文题集人工复核；所有结果仅作探索性诊断。

生成器验证题数、唯一 ID、逐字段不变性、question 非空、翻译状态与源哈希。翻译组件仅用于题集派生，不允许进入在线查询调用链；在线 trace 必须证明中文原始问题直接编码，且不出现翻译 API/模型调用。

## 7. 验收门禁与结论口径

### P0 资源与索引

使用两个固定模型建好英文 CWE 5748 段向量索引；真实核验模型/tokenizer revision、上游权重大小及 SHA-256、维度、cosine 度量、索引摘要和保存/加载兼容性。完成前不开始真实 P1。

### P1 跨语言检索（决定性门禁）

同快照、同题、同 N 对比新旧检索器。英文 Recall@N 对照 DPR：N=20/50/100 基线分别为 27.5%/43.75%/50.00%，新检索器每档不得低于对应值的 90%。中英等价性：

```text
equivalence = mean over N in {20,50,100} and the same 40 question IDs of Recall@N(Chinese)
              / mean over N in {20,50,100} and the same 40 question IDs of Recall@N(English)
```

目标至少 0.85。报告各语言、各 N 和平均两两余弦，并与既有 0.857 对照。若等价性 `<0.60`，停止 P2/P3，分析并记录阻塞；若 `0.60 <= equivalence < 0.85`，不得宣称通过，暂停 P2/P3 并提交差距分析/恢复建议。英文退化不能用中文结果掩盖。

### P2 MMR 与筛选

在同一检索候选池分别比较检索 Top-K 与 MMR，中文和英文都运行。报告 Evidence Recall@5、全覆盖率、Hit@5、逐题胜负、候选池/选中集合冗余、策略分歧、配对 bootstrap 95% CI。扫描 `lambda=0.0..1.0`，两种冗余尺度分别报告；选择参数只可基于开发语义，40 题 probe 结果仅探索性。除非配对 bootstrap 95% CI 不含 0 且方向为正，不得声称 MMR 优于 Top-K。`lambda=1.0` 必须完全等于检索 Top-K。

### P3 中文生成端到端

至少 10 道问题走完“中文原问题 → 无翻译 Qwen 检索 → MMR → 固定 Qwen 中文回答 → 确定性引用校验”。报告有效引用率、无引用陈述率和弱支持率；人工抽查 10 条只记录逐条核查事实，不夸大。无翻译链路应由调用 trace/代码路径检查支持。

### 通用验证及完成定义

每个相关阶段运行其专属真实检查，并在最终阶段运行：

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q src scripts
git diff --check
```

还须检查新旧 CLI `--help`、真实索引/模型加载校验和旧脚本可运行。整体完成还要求：新分支远端哈希一致；中文真实端到端输出答案/引用/校验；中英文 MMR/Top-K 配对结果及 95% CI；等价性数字和门禁判读入文档；所有测试/编译/差异检查通过；文档更新完整；英文 v1 路径未破坏。probe-v1 未人工复核，不是论文测试集，不得写成论文结论。任何失败都如实列为未通过/阻塞，不能标记整体验收。

## 8. 阶段状态与变更记录

每阶段分开记账：代码已实现、单元测试通过、真实模型推理通过、真实端到端通过。`PROGRESS.md` 使用“已完成且验证通过 / 已实现但尚未真实验证 / 正在进行 / 待完成 / 受阻”五类。阶段记录修改文件、实际命令与退出结果、未验证事项、Asia/Shanghai 时间线、commit 和远端核验。每个 commit 都在 `COMMIT_LOG.md` 表末追加一行；时间必须与 `%cI` 一致，新行哈希标“见下”。分支为 `step2/crosslingual-rag`，只普通 push，不强推。不得提交模型、数据、索引、输出、日志、密钥或令牌。推送失败保留提交并记录哈希、原因与恢复命令。

### 已知阻塞（2026-11-26）

本机只读自检得到 torch `2.9.1+cu128`、`torch.cuda.is_available() == False`；`nvidia-smi` 未显示 GPU；物理内存约 4 GiB、磁盘可用约 27 GiB。`models/` 目前只有 DPR 目录，未发现 STEP2 两个模型目录。该环境不满足真实模型推理/索引的当前证据条件。先准备可用 CUDA/显存与模型上游访问，再执行 P0；不得用模拟模型替代。

### 复核状态（2026-11-27）

上述 2026-11-26 记录是当日环境快照，不代表后续会话环境。本次复核的 `nvidia-smi` 显示 NVIDIA GeForce RTX 4090、24GB 显存；`.venv/bin/python -c "import torch;print(torch.__version__, torch.cuda.is_available())"` 输出 `2.9.1+cu128 True`，`df -h .` 显示可用 25G。`models/dpr/` 存在；STEP2 Qwen 模型的实际文件、上游 LFS 核验与加载状态仍未确认。该机器状态解除此前的 GPU 不可用阻塞，但不代表模型资源或推理门禁通过。
