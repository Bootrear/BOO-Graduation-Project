# 跨会话交接

恢复顺序：AGENTS.md → BASELINE_SPEC.md → IMPLEMENTATION_PLAN.md → PROGRESS.md → 本文件；再检查 git status/branch/log。不得重新设计冻结方案。

## 当前分支和提交

- 分支 `baseline/cwe-dpr-reader-mmr`，远端 origin=`https://github.com/Bootrear/BOO-Graduation-Project.git`。
- 写入时最新 HEAD：`8496cf309b7fd768233f23d15f242c15b9e6285f`（P01），已 push 且 ls-remote 一致。
- P00 主提交 `0766ce4bd693138b0523d371d64cd8f520287a09` 与文档收尾 `b857f41c8a1628ec31c27772d674abe749b5f319` 均已核验。
- P02 当前已验证，待提交推送。本文档自身最新提交哈希以 `git rev-parse HEAD` 为准，以上是写入时准确审计锚点。

## 本阶段目标

P02：核查实际 CWE 4.20 结构、实现来源语义解析及 manifest/passage 契约。已完成本阶段验证；P03 tokenizer 分段、正式快照及 P04–P10 尚未完成，整体未验收。

## 已修改文件

- src/cyber_qa/data/contracts.py：规范化、完整字段、时间/哈希检查和稳定 ID 工厂。
- src/cyber_qa/data/cwe.py：4.20 XML/ZIP 语义单元、来源路径、重复和缺失统计。
- tests/test_cwe_contracts.py：17 项数据契约测试。
- docs/CWE_CONTRACT.md：实际格式、映射、ID、清洗规则、真实统计。
- docs/RUNTIME.md、docs/README.md、docs/PROGRESS.md、docs/HANDOFF.md：环境进展/导航/交接。
- 忽略的本地文件：data/raw/cwe/cwec_v4.20.xml.zip、download_receipt.json、outputs/cwe-p02-validation.json。
- install.sh 原有未跟踪文件保持不动；未提交数据/权重/索引或敏感日志。

## 已运行命令及结果

- P01：`.venv/bin/python -m pytest -q` 26 passed；旧 smoke_demo 成功；pip check 无冲突，见 RUNTIME。
- `git ls-remote --heads origin baseline/cwe-dpr-reader-mmr`：P01 `8496cf309b7fd768233f23d15f242c15b9e6285f` 与远端一致。
- `curl -fL --retry 2 --connect-timeout 15 --max-time 90 https://cwe.mitre.org/data/xml/cwec_v4.20.xml.zip -o data/raw/cwe/cwec_v4.20.xml.zip.part`：成功，校验后改名为 .zip。
- Python hashlib/zipfile/ElementTree 检查：SHA-256=`3976f599e5e5200219a3108bb896d06e2a88fbb293369e1883cb423a5e9d7d50`，ZIP CRC 正常，唯一 XML member，4.20/cwe-7。
- `.venv/bin/python -m pytest -q`：最终 **43 passed in 0.09s**。
- `.venv/bin/python` 调用 parse_cwe 两次：969 个 Weakness、5454 个来源单元；422 Category/59 View 排除；两次结果完全相同；摘要写到 outputs/cwe-p02-validation.json。
- `git diff --check`：通过。

## 当前失败或阻塞

- 无 P02 验证失败；数据缺失与 pytest 缺失已解决。
- 真实 tokenizer、DPR、Reader 权重尚未获取，独立 .venv 尚未安装模型依赖；预算和端到端未验证。
- 本次 curl 完成时间未精确记录，获取时间保持 null/unknown，registered_at 单独登记。不要用 mtime 或登记时间伪造下载时间。
- Git 身份使用命令级 `-c user.name=Codex -c user.email=codex@localhost`。

## 下一步应执行的唯一具体动作

执行 `git diff --check` 开始 P02 提交前检查；按下方列表提交、推送核验后，进入 P03 的真实 tokenizer 选择与预算检查。

## 提交与恢复命令

```bash
git add src/cyber_qa/data/contracts.py src/cyber_qa/data/cwe.py tests/test_cwe_contracts.py docs/CWE_CONTRACT.md docs/RUNTIME.md docs/README.md docs/PROGRESS.md docs/HANDOFF.md
git diff --cached --check
git diff --cached
git -c user.name=Codex -c user.email=codex@localhost commit -m "feat(data): define traceable CWE records and semantic parsing"
git push origin baseline/cwe-dpr-reader-mmr
git fetch origin baseline/cwe-dpr-reader-mmr
git rev-parse HEAD
git rev-parse origin/baseline/cwe-dpr-reader-mmr
```

若推送失败，保留本地 commit，记录哈希/错误，提交 checkpoint 文档；恢复 `git push origin baseline/cwe-dpr-reader-mmr` 前 fetch 检查分叉，禁止强推。工程阶段不能完成时停止扩展，最小验证后保存 checkpoint。

更新时间：2026-11-13T14:46:48+08:00。
