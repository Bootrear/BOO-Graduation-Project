# 跨会话交接

恢复顺序：AGENTS.md → BASELINE_SPEC.md → IMPLEMENTATION_PLAN.md → PROGRESS.md → 本文件；再核查 git status、branch、log。

## 当前分支和提交

- 分支 `baseline/cwe-dpr-reader-mmr`；origin=`https://github.com/Bootrear/BOO-Graduation-Project.git`。
- 写入时最新 HEAD：`2acbff7e3874638d04d7e7e69767d3402b4cced1`（P03），已推送且 ls-remote 与本地完全一致。
- 已核验阶段链：P00 0766ce4 / 收尾 b857f41 → P01 8496cf3 → P02 05b0b9e → P03 2acbff7。
- P04 已验证，当前改动待提交推送。本文档自身最新提交/HEAD 运行 `git rev-parse HEAD` 获取，上述为写入时审计锚点，不自引用。

## 本阶段目标

P04：实现完整候选池一次归一化、非负余弦、Reader Top-K、逐轮 MMR/参考等价性和选择日志。数学验证通过；真实 DPR/Reader/端到端仍未验收。

## 已修改文件

- src/cyber_qa/data/candidates.py：携带 passage、vector、retrieval/Reader 分数、跨度的完整记录。
- src/cyber_qa/selection/mmr.py：共享尺度、PreparedPool、Top-K、增量 MMR、直接参考实现、日志。
- tests/test_mmr.py：21 项回归及 80 组固定种子随机参考等价性。
- docs/SELECTION.md、docs/PROGRESS.md、docs/HANDOFF.md：算法细则与阶段记录。
- install.sh 仍为进入任务前的未跟踪用户文件，不纳入提交。

## 已运行命令及结果

- `.venv/bin/python -m pytest -q tests/test_mmr.py`：**21 passed in 0.08s**。
- `.venv/bin/python -m pytest -q`：**73 passed in 2.04s**，含当前本地真实 tokenizer 测试，无 skip。
- 指定 A/B/C：Top-K=[A,B]，MMR=[A,C]，第二轮 C 分数 −0.05、冗余0.1；负分仍选择，归一化保持0，不按剩余池重算。
- 80 组随机候选：增量与直接遍历参考的完整结果/日志一致；所有选择无重复；λ=1 顺序与 Top-K 一致。
- `git diff --check`：通过；`git ls-remote --heads origin baseline/cwe-dpr-reader-mmr`：P03 `2acbff7e3874638d04d7e7e69767d3402b4cced1` 已核验。
- 之前 P03：真实 5748 段、重复构建字节一致，快照/输入预算/原文覆盖全部通过，命令与哈希见 CWE_CONTRACT.md。

## 当前失败或阻塞

- P04 无未解决测试失败。
- DPR/Reader 模型权重与独立 .venv 的 torch 尚未取得；尚无向量索引或真实模型推理结论。
- 当前已有 .venv、data/raw/cwe、models/dpr 的分词资源、data/processed/cwe-v1；均已忽略，不上传大文件。
- 超长问题拒绝和标题输入截断的查询日志尚待 P06/P08 实现；不可标成已验收。

## 下一步应执行的唯一具体动作

P04 提交推送并核验后，执行 `.venv/bin/python scripts/fetch_dpr_resources.py --weights`，开始 P05 的固定 revision 权重获取。子进程若继承冲突代理，可先加载已有 `/root/.config/codex/network-env.sh`；不要更改机器网络配置。

## 提交与恢复

```bash
git add src/cyber_qa/data/candidates.py src/cyber_qa/selection/mmr.py tests/test_mmr.py docs/SELECTION.md docs/PROGRESS.md docs/HANDOFF.md
git diff --cached --check
git diff --cached
git -c user.name=Codex -c user.email=codex@localhost commit -m "feat(selection): implement deterministic reader top-k and iterative MMR"
git push origin baseline/cwe-dpr-reader-mmr
git fetch origin baseline/cwe-dpr-reader-mmr
git rev-parse HEAD
git rev-parse origin/baseline/cwe-dpr-reader-mmr
```

推送失败保留本地提交，登记哈希/原因与恢复命令，再创建 checkpoint 文档提交；恢复 push 前先 fetch 检查分叉，不强推。不能完成阶段则停止新功能、做最小验证并保存标明 incomplete 的 checkpoint。

更新时间：2026-11-13T15:03:10+08:00。
