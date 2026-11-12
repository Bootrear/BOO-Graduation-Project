# 数据源、体积与下载说明

## 1. 结论

本项目所说的“数据库”主要是公开安全知识数据，而不是必须部署的 MySQL、PostgreSQL 或 Neo4j。当前阶段采用：

- 原始层：官方 JSON、XML、STIX 文件；
- 处理层：统一 evidence schema 的 JSONL；
- 检索层：计划使用 DPR 段落向量与索引，安全 ID 用于来源追溯；
- 标注层：人工核验的问题、gold facts 与 gold evidence。

MVP 不需要独立数据库服务。条目元数据较少时可以继续使用 JSONL，后续若需要复杂过滤再加入 SQLite；向量检索实现确定后再生成 FAISS 或 HNSW 索引。

2026-10-20 的起始快照记录包含 10 个文件，共 **149,914,316 bytes（142.97 MiB）**。这些是本地已有文件，不随 Git 上传，也不代表正式实验数据已经冻结。

依据当前[开题报告](../docs/开题报告_整理版.md)，**CWE 是主线必需来源**，NVD、ATT&CK、CAPEC 与 KEV 均为可选扩展。下表保留起始快照的版本和校验记录；动态官方入口今后下载的文件可能与历史哈希不同，应另建快照并记录，不能冒充原始版本。

## 2. 已下载数据

| 优先级 | 数据源 | 项目用途 | 本地快照 | 下载体积 | 校验结果 |
| --- | --- | --- | --- | ---: | --- |
| 可选扩展 | NVD/CVE JSON 2.0 | 漏洞描述、CVSS、受影响配置、CWE 和参考链接 | 2024、2025、2026 年度包 | 23.89 + 23.82 + 35.24 MiB | 官方 metadata 中的压缩大小、解压大小和解压后 SHA-256 均一致 |
| 必需 | CWE | 弱点定义、层级和关联关系 | 4.20 | 1.93 MiB | ZIP 完整，XML 可解析，969 个 Weakness 条目 |
| 可选扩展 | MITRE ATT&CK Enterprise | 战术、技术、子技术、缓解措施和关系 | 20.0 | 52.71 MiB | STIX bundle 可解析，26,690 个 STIX objects |
| 可选增强 | CAPEC | 攻击模式以及与 CWE/ATT&CK 的映射 | 3.9 | 3.67 MiB | XML 可解析，按官方口径统计 559 个 Attack Patterns |
| 可选增强 | CISA KEV | 已知在野利用标签，可用于问题筛选和重要性标注 | 2026-10-20 本地快照 | 1.71 MiB | JSON 可解析，1,748 个漏洞 |

NVD 三个压缩包解压后合计约 **986.85 MiB**，因此建议 ETL 时直接流式读取 `.json.gz`，不要为了解压再额外占用约 1 GiB 磁盘。

## 3. 本地路径与官方来源

| 本地文件 | 官方来源 |
| --- | --- |
| `raw/nvd/nvdcve-2.0-2024.json.gz` | [NVD 2024 JSON 2.0 feed](https://nvd.nist.gov/feeds/json/cve/2.0/nvdcve-2.0-2024.json.gz) |
| `raw/nvd/nvdcve-2.0-2025.json.gz` | [NVD 2025 JSON 2.0 feed](https://nvd.nist.gov/feeds/json/cve/2.0/nvdcve-2.0-2025.json.gz) |
| `raw/nvd/nvdcve-2.0-2026.json.gz` | [NVD 2026 JSON 2.0 feed](https://nvd.nist.gov/feeds/json/cve/2.0/nvdcve-2.0-2026.json.gz) |
| `raw/nvd/nvdcve-2.0-2024.meta` | [NVD 2024 metadata](https://nvd.nist.gov/feeds/json/cve/2.0/nvdcve-2.0-2024.meta) |
| `raw/nvd/nvdcve-2.0-2025.meta` | [NVD 2025 metadata](https://nvd.nist.gov/feeds/json/cve/2.0/nvdcve-2.0-2025.meta) |
| `raw/nvd/nvdcve-2.0-2026.meta` | [NVD 2026 metadata](https://nvd.nist.gov/feeds/json/cve/2.0/nvdcve-2.0-2026.meta) |
| `raw/cwe/cwec_v4.20.xml.zip` | [CWE Downloads](https://cwe.mitre.org/data/downloads) |
| `raw/attack/enterprise-attack-20.0.json` | [MITRE ATT&CK Enterprise 20.0 STIX](https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master/enterprise-attack/enterprise-attack-20.0.json) |
| `raw/capec/capec_v3.9.xml` | [CAPEC 3.9 XML](https://capec.mitre.org/data/xml/capec_v3.9.xml) |
| `raw/cisa_kev/known_exploited_vulnerabilities_2026-10-20.json` | [CISA KEV JSON feed](https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json) |

原始数据由 `.gitignore` 排除，不会随 Git 仓库提交。固定快照的文件哈希保存在 [`starter_snapshot_2026-10-20.sha256`](starter_snapshot_2026-10-20.sha256)。

## 4. 暂未下载的大数据或非当前必需数据

| 数据 | 体积判断 | 暂不下载原因 | 手动下载入口 |
| --- | --- | --- | --- |
| NVD 全历史年度包（2002 至今） | 累计为数百 MiB 压缩数据，解压后为数 GiB，且会持续变化 | 当前主线优先 CWE；NVD 的范围与题量应在扩展时另行确定 | [NVD Data Feeds](https://nvd.nist.gov/vuln/data-feeds) |
| NVD CPE Match 2.0 | 官方页面当前约 806 MiB 压缩 | 主要用于完整 CPE 匹配；MVP 可先使用 CVE 条目内的 configurations 字段 | [NVD Data Feeds](https://nvd.nist.gov/vuln/data-feeds) |
| NVD CPE Dictionary | 约 80 MiB 压缩 | 文件不算特别大，但当前不是必需数据；只有在做产品名称标准化、完整 CPE 查询时再下载 | [NVD Data Feeds](https://nvd.nist.gov/vuln/data-feeds) |
| NQ、HotpotQA、SecQA、CyberMetric、CTIBench | 各数据集规模和许可不同 | 它们是基线或评测数据，不是本项目主知识库；应在基线实验确定后按许可证单独获取 | 参见开题报告参考文献与数据集章节 |

## 5. 后续会在本地生成的数据

以下内容不是外部数据库，无需现在下载：

1. `processed/*.jsonl`：统一 schema 后的 evidence；
2. ID 映射：优先建立 CWE 条目及知识段的来源对应关系；
3. 向量索引：体积由切分数量和向量维度决定，例如 10 万条、768 维、`float32` 的裸向量约 293 MiB，尚不含索引结构和元数据；
4. `annotations/`：至少 120 题人工核验标注，按来源条目划分开发集 80 题与冻结测试集 40 题。

## 6. 校验方法

在仓库根目录运行：

```powershell
.\.venv\Scripts\python.exe scripts/validate_raw_data.py
```

脚本只使用 Python 标准库，校验 NVD 官方哈希、ZIP 完整性、XML 结构、STIX bundle 和 KEV JSON，并输出各本地文件的 SHA-256。需先按主 README 建立环境，并准备表中完整起始快照（含三个 `.meta` 文件）；只有 CWE 时不能直接运行该全量校验脚本。它不会自动下载数据，也不会自动比对起始快照清单，历史快照一致性还需逐项核对清单 SHA-256。
