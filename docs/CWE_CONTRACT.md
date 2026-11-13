# CWE 4.20 解析与追溯契约（P02）

## 支持范围与真实来源

目前支持 UTF-8 的 CWE **4.20** 原始 XML，或仅含一份 XML 的 ZIP；根必须是 `{http://cwe.mitre.org/cwe-7}Weakness_Catalog`。未知版本/namespace、缺失容器、非法 ID/标题、DTD/entity 声明、超出 64 MiB 的原始或解压文件直接报错，不静默按其他结构解析。不将该实现声称为所有 CWE 版本通用解析器。

实际验证文件来自 [MITRE 4.20 归档](https://cwe.mitre.org/data/xml/cwec_v4.20.xml.zip)，下载入口见 [官方发布归档](https://cwe.mitre.org/data/archive.html)。原始 ZIP SHA-256：

```text
3976f599e5e5200219a3108bb896d06e2a88fbb293369e1883cb423a5e9d7d50
```

与仓库 `data/starter_snapshot_2026-10-20.sha256` 的对应条目一致；这只证明字节相同，不证明当前机器在历史日期下载了文件。XML member 为 `cwec_v4.20.xml`，根版本 4.20，Date=2026-04-30，namespace 为 cwe-7，schemaLocation 指向 v7.3。
本次 curl 下载未捕获精确完成时刻，保守登记 acquired_at=null、acquired_at_basis=unknown；registered_at 为实际登记时间，收据保存在忽略的 `data/raw/cwe/download_receipt.json`。不得用该登记时间、mtime 或历史文档日期冒充 acquired_at。

## 路径与语义单元

实现：`src/cyber_qa/data/cwe.py` 的 FIELD_PATHS；版本 `cwe-xml-4.20-v1`。

| 相对于 Weakness 的真实路径 | field_name | 来源单元 |
| --- | --- | --- |
| Description | description | 一份完整描述 |
| Extended_Description | extended_description | 一份完整扩展描述 |
| Common_Consequences/Consequence | common_consequences | 一组 Scope、Impact、Note 等 |
| Detection_Methods/Detection_Method | detection_methods | 一组 Method、Description、Effectiveness 等 |
| Potential_Mitigations/Mitigation | potential_mitigations | 一组 Phase、Strategy、Description 等 |

每个嵌套单元逐个保留子字段标签及文本，重复 Scope/Impact/Phase 不丢弃；保持配对，不把不同 Consequence/Method/Mitigation 混在一起。字段标签取自真实 XML，不生成安全事实。没有独立“成因”字段时不造新字段。
source_locator 例如 `/Weakness_Catalog/Weaknesses/Weakness[@ID='79']/Common_Consequences/Consequence[2]`；按本文件声明的 namespace 解读每层标签，序号从 1 起。XML member 单独由 ParsedCWE.xml_member 返回。

仅 Weakness 纳入语料；Category/View 分别计数排除。保留原始 Status（无则 null）。缺失字段按每个唯一条目统计，空来源文本单独统计且不生成单元。

## 文本规范与重复

- UTF-8 解码，NFC Unicode，CRLF/CR→LF；横向空白折叠为单空格，逐行 trim，移除空行但保留语义换行。
- XHTML 行内标签保留相邻文本，不插入破坏单词的空格；段落/块/列表边界换行，ul 的 li 带 `-`，ol 的 li 带序号。
- source_text 是上述解析结果，不是 XML 字节副本。原始 XML/ZIP 由原始哈希和快照保留回查。
- 同 ID 且相同 XML 内容（忽略元素外 tail）的重复条目只解析一份，计 duplicate_entries/duplicate_source_units；同 ID 不同内容直接失败，避免来源冲突。
- 跨条目/字段同文全部保留独立来源；统计 cross_source_identical_texts，不跨来源删除。
- P02 不分 token：超长 source_text 完整保留。**5454 个来源单元不是最终知识段数**；P03 才使用真实 tokenizer 与预算生成知识段。

## manifest 与 passage

实现 `src/cyber_qa/data/contracts.py`；完整必备字段见 BASELINE_SPEC 三。

manifest 的 acquisition/registration/processing 时间为带时区 ISO 8601；未知获取时间只能 null/unknown。额外字段 registered_at 用于未知下载时间时的登记。
稳定序列化采用 UTF-8 JSON，sort_keys=True、ensure_ascii=False、紧凑分隔符，拒绝 NaN/Inf；配置哈希为其 SHA-256。

```text
snapshot_id = "cwe:" + SHA256(canonical_json({
  dataset_name, dataset_version, raw_file_sha256,
  parser_version, chunker_version, preprocessing_config_sha256
}))

content_sha256 = SHA256(text.encode("utf-8"))

passage_id = "cwe-passage:" + SHA256(canonical_json({
  snapshot_id, cwe_id, source_locator, field_name, chunk_index, content_sha256
}))
```

获取/登记/处理时间不参与稳定 ID。chunk_index 从 0 起；text 必须是非空且已规范化的 source_text 连续片段；反序列化校验内容哈希和稳定 ID，不使用 Python hash、随机 UUID 或运行时间。不同来源同文 ID 不同，避免丢失溯源。
P02 已提供类型和 ID 工厂并通过合成契约测试；尚未生成完整真实分段 manifest/索引，不声称 P03 完成。

## 真实验证与统计

2026-11-13，Asia/Shanghai；实际运行：

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -c "from cyber_qa.data.cwe import parse_cwe; p=parse_cwe('data/raw/cwe/cwec_v4.20.xml.zip'); print(p.statistics)"
```

测试共 43 passed；真实文件连续解析两次，全部单元、统计及元数据一致。结果摘要保存在本地 `outputs/cwe-p02-validation.json`（忽略，不上传原始数据）。

| 统计 | 结果 |
| --- | ---: |
| 读取/纳入 Weakness | 969 / 969 |
| 来源单元 | 5454 |
| 排除 Category / View | 422 / 59 |
| 空文本 | 3 |
| 重复条目 / 同来源重复单元 | 0 / 0 |
| 跨来源同文重复出现次数（全部保留） | 1571 |
| 缺 description / extended_description | 0 / 387 |
| 缺 common_consequences / detection_methods / potential_mitigations | 25 / 470 / 298 |

P03 最终知识段数待实际分段后记录。没有模型推理或端到端验收结论。


## P03：真实 tokenizer 分段与可加载快照

P03 已在真实 CWE 与真实 DPR tokenizer 上完成处理和重载验证，最终为 **5748 段**；此前 P02 的“尚未分段”描述是该阶段历史边界。

- 实现：data/chunking.py、data/preprocess.py；入口 scripts/preprocess_cwe.py；资源检查 resources.py、获取脚本 scripts/fetch_dpr_resources.py。
- 三个 single-nq-base 模型/tokenizer 的 40 位不可变 revision 固定在 configs/dpr-models.v1.json；依赖锁在 requirements-tokenization.txt。不把 tokenizer 可用等同于模型权重推理通过。
- 三个词表均实测相同（30522 项），vocab.txt SHA-256 为 `07eced375cec144d27c900241f3e339478dec958f92fddbc551f295c992038a3`。
- 历史资源 metadata 都声明 QuestionEncoder tokenizer；AutoTokenizer 实测选错 Reader 类。现按角色显式使用 DPRQuestionEncoderTokenizerFast、DPRContextEncoderTokenizerFast、DPRReaderTokenizerFast，保留上游类型警告，并用真实序列测试确认布局。
- Context 输入是 `[CLS] title [SEP] text [SEP]`；Reader 输入是 `[CLS] question [SEP] title [SEP] text`；均为 3 个特殊 token，模型位置上限 512。
- 配置冻结 context=256、reader=512、question=64、title=64；知识段固定预算 min(256−64−3,512−64−64−3)=189。完整 title 保留在来源，推理标题超过 64 时仅截断输入 token ID 并记录；本快照最长标题 22 token，无标题需要截断。问题超过 64 token 的策略为明确拒绝并记录，不静默截断；实际查询入口将在 P06/P08 落地。
- 先保持来源单元；过长文本优先在 token 上限后半区的句号/问号/感叹号/换行边界切分，否则按 token offset 切分；每段重新编码复核预算。无重叠，保留文本连续片段；对全部实际源单元检查未丢失任何非空白字符。
- 输出 manifest.json、passages.jsonl、statistics.json；临时目录完整写入且校验后再改名，拒绝覆盖已有快照。重载检查文件 SHA-256、条数、知识段 ID/内容哈希/快照一致性。

实测命令（output 目录必须不存在）：

```bash
.venv/bin/python -m pip install -e '.[dev,tokenization]' -c requirements-tokenization.txt
.venv/bin/python scripts/fetch_dpr_resources.py
.venv/bin/python scripts/preprocess_cwe.py --raw data/raw/cwe/cwec_v4.20.xml.zip --receipt data/raw/cwe/download_receipt.json --output data/processed/cwe-v1
.venv/bin/python scripts/preprocess_cwe.py --raw data/raw/cwe/cwec_v4.20.xml.zip --receipt data/raw/cwe/download_receipt.json --output outputs/cwe-v1-repeat
.venv/bin/python -m pytest -q
```

如果重新取得原始文件但没有可靠 receipt，可不传 --receipt，获取时间仍为 null/unknown，另记处理时登记时间；不要复用不匹配哈希的收据。

结果：52 passed（包含实际 tokenizer 测试，缺分词依赖或本地资源时这些测试明确 skip，不代表通过）；完整真实处理两次约各 5.6 秒；两次 JSONL 字节、全部 passage 和 snapshot_id 相同。逐段检查 5748 段的实际 Context 输入≤256、64-token 问题下 Reader 输入≤512、正文≤189，全部通过。

快照 ID：`cwe:88e4eab3cc54f16611040a0e528d7a128253426e90ee5054327fd28449fee393`。
passages.jsonl SHA-256：`a20e52c87054121dcfe3dfbf78f5399df3deb2d5c638e747f145facc82c71525`。
以上为数据与 tokenizer 验证；未下载模型权重、未生成向量索引、未做真实 DPR/Reader 推理。
