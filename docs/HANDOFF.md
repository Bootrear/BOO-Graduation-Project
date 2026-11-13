# 跨会话交接

恢复顺序：AGENTS.md → BASELINE_SPEC.md → IMPLEMENTATION_PLAN.md → PROGRESS.md → 本文件；再检查 git status/branch/log。不得重新设计冻结方案。

## 当前分支和提交

- 分支 `baseline/cwe-dpr-reader-mmr`，远端 origin=`https://github.com/Bootrear/BOO-Graduation-Project.git`。
- 写入时最新 HEAD：`8496cf309b7fd768233f23d15f242c15b9e6285f`（P01），已 push 且 ls-remote 一致。
- P00 主提交 `0766ce4bd693138b0523d371d64cd8f520287a09` 与文档收尾 `b857f41c8a1628ec31c27772d674abe749b5f319` 均已核验。
- P02 已提交推送并经 ls-remote 核验：`05b0b9e52fbfc1b64dcbe99db0c39617a4d9dceb`。P03 已完成数据验证，待提交推送。本文档自身最新提交哈希以 `git rev-parse HEAD` 为准，以上是写入时准确审计锚点。

## 本阶段目标

P03：用真实且固定 revision 的 tokenizer 确定预算、实现确定性分段、写入并重载真实快照。已完成阶段验证，整体基线仍未验收。

## 已修改文件

- pyproject.toml、requirements-tokenization.txt：tokenization extra 与实测版本。
- configs/dpr-models.v1.json：三模型不可变 revision。
- scripts/fetch_dpr_resources.py：有界重试、每文件哈希收据、可继续的本地资源获取（默认只取 tokenizer）。
- src/cyber_qa/resources.py：校验资源、按角色显式加载 tokenizer，共享词表与位置上限核查。
- src/cyber_qa/data/chunking.py：189-token 预算与连续文本切分。
- src/cyber_qa/data/preprocess.py、scripts/preprocess_cwe.py：原子快照写入、清单与重载校验。
- tests/test_preprocess.py：预算/真实输入布局/真实 tokenizer 切分/快照重载与损坏拒绝测试。
- docs/CWE_CONTRACT.md、docs/RUNTIME.md、docs/PROGRESS.md、docs/HANDOFF.md：实际决策和验证。
- 忽略本地目录：models/dpr、data/raw/cwe、data/processed/cwe-v1、outputs/cwe-v1-repeat、.venv。install.sh 保持未跟踪且不修改。

## 已运行命令及结果

- `.venv/bin/python -m pip install 'transformers==4.57.1'`：成功，随后导出 requirements-tokenization.txt。
- `.venv/bin/python -m pip install -e '.[dev,tokenization]' -c requirements-tokenization.txt`：成功；pip check 无冲突。
- 访问三个 Hugging Face model API：首次 TLS EOF；子进程加载已有统一代理后重试成功，revision 已保存，无机器网络配置修改。
- `.venv/bin/python scripts/fetch_dpr_resources.py`：三角色各 4 个 tokenizer/config 文件完整取得并校验。
- 实测 tokenizer：30522 个相同词表，显式 Reader 类三段输入/Context 两段输入均为 3 个特殊 token；位置上限 512、隐藏维 768；最长真实 title 22 token。
- `.venv/bin/python -m pytest -q`：**52 passed in 1.96s**，无 skip。
- `scripts/preprocess_cwe.py --raw data/raw/cwe/cwec_v4.20.xml.zip --receipt data/raw/cwe/download_receipt.json --output data/processed/cwe-v1`：成功，5748 段，约 5.53 秒。
- 同命令改为 `--output outputs/cwe-v1-repeat`：成功，约 5.60 秒；两次快照 ID/JSONL 字节/记录完全一致。
- 独立 Python 遍历 5748 段：实际 Context 输入≤256、Reader（问题64 tokens）≤512、正文≤189；拼接各来源所有块无非空白文本丢失，全部通过。
- 快照 ID：`cwe:88e4eab3cc54f16611040a0e528d7a128253426e90ee5054327fd28449fee393`；JSONL SHA-256：`a20e52c87054121dcfe3dfbf78f5399df3deb2d5c638e747f145facc82c71525`。
- P02 `05b0b9e52fbfc1b64dcbe99db0c39617a4d9dceb` 已推送并经 ls-remote 核验；P03 提交前 diff --check 通过。

## 当前失败或阻塞

- P03 无未解决验证失败。上游三个 tokenizer metadata 都写 QuestionEncoder，AutoTokenizer 会选错；已按角色显式加载并测试真实布局，警告原因已记录。
- 仍无模型权重、独立 .venv torch、向量索引；真实 DPR/Reader/端到端未验证。
- 超长问题策略已冻结为拒绝、标题输入截断为64 token并保留原文；查询执行/日志由 P06/P08 实现，不能标记其查询行为已验收。
- 原始数据获取时间保持 null/unknown；registered_at 单独保存。

## 下一步应执行的唯一具体动作

完成本阶段提交推送核验后，在 `src/cyber_qa/selection/mmr.py` 实现 P04 的完整候选池 min-max 归一化函数（epsilon=1e-12、单候选/同分为0、非有限值使查询失败），然后按计划补齐 Top-K/MMR 及回归。

## 提交与恢复命令

仅暂存上方列出的 P03 代码、配置、测试和文档，不能暂存原始数据/权重/install.sh。

```bash
git diff --check
git diff --cached --check
git diff --cached
git -c user.name=Codex -c user.email=codex@localhost commit -m "feat(data): add deterministic token-aware CWE snapshots"
git push origin baseline/cwe-dpr-reader-mmr
git fetch origin baseline/cwe-dpr-reader-mmr
git rev-parse HEAD
git rev-parse origin/baseline/cwe-dpr-reader-mmr
```

若推送失败保留本地提交，登记真实哈希/原因与未推送状态，创建 checkpoint 文档提交；恢复 push 前 fetch 检查差异，禁止强推。若本轮阶段不能完成，停止扩展并保存可运行 checkpoint。

更新时间：2026-11-13T14:57:20+08:00。
