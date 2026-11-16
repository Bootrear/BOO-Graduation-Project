# 跨会话交接

恢复顺序：AGENTS.md → BASELINE_SPEC.md → IMPLEMENTATION_PLAN.md → PROGRESS.md → 本文件；再核查 git status、branch、log。

## 当前分支和提交

- 分支 `baseline/cwe-dpr-reader-mmr`；origin=`https://github.com/Bootrear/BOO-Graduation-Project.git`。
- 写入时 HEAD / 最近远端核验提交：`0f9875a5eb2dc598d72f28526bbb5bc1a9875fb7`（P05 中途检查点），fetch/ls-remote 与本地一致。
- 已核验阶段链：P00 0766ce4 / 收尾 b857f41 → P01 8496cf3 → P02 05b0b9e → P03 2acbff7 → P04 cd5c629 → P05 检查点 0f9875a。
- P05 真实验收现在已完成；当前收尾改动待提交推送。包含本文档的最新提交使用 `git rev-parse HEAD` 获取，以上是写入时审计锚点，不是自引用。

## 本阶段目标与结论

P05：匹配 DPR 双编码器、原始内积索引、映射、兼容性及持久化召回。代码、单元测试、真实双编码器推理、5748 段全量建库、跨进程重载召回均通过。P06 Reader / P07 普通回答 / P09 真实完整端到端仍未验收，整体基线保持未完成。

## 已修改文件

- `src/cyber_qa/models.py`：恢复已有草稿，固定本地角色/预算/哈希，严格加载完整权重，记录已核查的旧 pooler 差异，执行 eval/inference_mode 与输出形状/有限性检查。
- `src/cyber_qa/retrieval/dpr.py`：原始 float32 内积、稳定排名、完整来源记录、原子持久化、快照/配置/权重/映射/向量完整性校验、独立加载和建库计时。
- `scripts/fetch_dpr_resources.py`：固定 revision 上游 LFS 大小/哈希、HTTP 长度、Range 续传、坏缓存隔离；解决旧 question 11 MB 缓存误验问题。
- `scripts/build_dpr_index.py`、`scripts/check_dpr_retrieval.py`：真实建库、单条/批量对齐、持久化和跨进程重载验收入口。
- `tests/test_resource_downloads.py`、`tests/test_retrieval.py`：26 项资源/索引/严格加载回归。
- `pyproject.toml`、`requirements-inference.txt`：inference extra 与当前 Linux x86_64/Python 3.12 独立环境精确包锁。
- `docs/RETRIEVAL.md`、`docs/RUNTIME.md`、`docs/README.md`、`docs/PROGRESS.md`、`docs/HANDOFF.md`：规则、命令、哈希、失败修复、实测状态、时间线及下一步。
- `install.sh` 未跟踪、不改动、不提交。原始数据、权重、索引、虚拟环境与本地日志均忽略；`docs/theprompt.md` 原始字节哈希未变。

## 已运行命令及结果

1. `.venv/bin/python scripts/fetch_dpr_resources.py --weights`：退出 0；question/context/reader 三权重均通过上游 LFS 校验，精确大小/哈希见 RETRIEVAL。
2. `.venv/bin/python -m pip install -e '.[inference]' -c requirements-tokenization.txt`：成功；独立 torch 2.9.1+cu128，CUDA 12.8，RTX 4090。`pip check` 无冲突；独立 CUDA 张量求和得到 2.0。
3. `.venv/bin/python scripts/build_dpr_index.py --snapshot data/processed/cwe-v1 --output data/processed/dpr-index-v1 --device cuda --batch-size 32`：成功；5748×768 原始 float32 向量。模型加载 3.149s，离线编码/写入 8.972s。
4. `.venv/bin/python scripts/check_dpr_retrieval.py --device cuda --output outputs/p05-retrieval-first.json`：成功；真实问题 `What is SQL injection?`，20 个候选，首段 CWE-564 description，原始内积 82.84361267089844。
5. `.venv/bin/python scripts/check_dpr_retrieval.py --device cuda --output outputs/p05-retrieval-reload.json --compare outputs/p05-retrieval-first.json`：新进程成功；候选/顺序/分数完全一致。单条与批量 context、保存向量对齐和余弦不改写原始向量也通过。
6. `.venv/bin/python -m pytest -q`：**99 passed in 4.34s**，无 skip；其中资源/索引回归 26 项。合成回归与以上真实验收分开记账。
7. `python -m compileall -q src scripts tests`、两脚本 `--help`、旧 DSES smoke_demo、原始 theprompt SHA-256 与 `git diff --check` 均通过。

完整产物/本地日志位于忽略路径：data/processed/dpr-index-v1、outputs/p05-*.json / outputs/p05-*.log。向量 SHA-256 `47c54ab91545b52b630e6b1dd6f244c41b872ad4f108bf8259e3fcac9b3257c5`；详细其余哈希见 RETRIEVAL。

## 当前失败或阻塞

- P05 无未解决测试/资源阻塞。中途服务器重启已恢复，缺失依赖/不完整权重问题已解除。
- 首次建库因旧 pooler 多余参数被严格校验拒绝，已核对三个 state_dict 与同版本 DPREncoder（add_pooling_layer=False、原始 CLS）。仅允许角色对应的旧 pooler weight/bias 与 position_ids；缺失/错配/其他多余参数仍失败，记录在 index_manifest 的 context_loading_info。
- 两次真实 query_seconds 分别 24.847436s、0.022957s；尚未归因/做稳定性能基准，不能承诺稳定延迟。
- Reader 权重已取得但尚未推理；超长问题/标题截断的完整查询日志、答案跨度和普通回答待 P06–P08。P05 不代替 P09 端到端。
- 完整新环境部署重放待 P10，不将当前环境安装成功冒充全部部署验收。

## 下一步应执行的唯一具体动作

P05 收尾提交推送核验后，执行下列真实 Reader 输出形状核查，开始 P06（尚未执行，不代表 Reader 验收已通过）：

```bash
.venv/bin/python - <<'PY'
from cyber_qa.models import DPRRuntime
from cyber_qa.retrieval.dpr import load_index
runtime = DPRRuntime(device="cuda")
index = load_index("data/processed/dpr-index-v1", "data/processed/cwe-v1", runtime)
question = "What is SQL injection?"
candidates = index.search(runtime.encode_question(question), n=2)
batch = runtime.tokenizers["reader"](
    question,
    [c.passage.title for c in candidates],
    [c.passage.text for c in candidates],
    padding=True, return_tensors="pt",
).to(runtime.device)
model = runtime.load_model("reader")
with runtime.torch.inference_mode():
    result = model(**batch)
print([c.passage_id for c in candidates])
print(result.relevance_logits.shape, result.start_logits.shape, result.end_logits.shape)
PY
```

随后在 P06 范围实现单候选/跨批/重排对齐与有效原文跨度，保留分数分离与 Reader 只计算一次；不修改冻结的尺度/公式/输入预算。

## 提交与恢复

```bash
git push origin baseline/cwe-dpr-reader-mmr
git fetch origin baseline/cwe-dpr-reader-mmr
git rev-parse HEAD
git rev-parse origin/baseline/cwe-dpr-reader-mmr
git ls-remote --heads origin baseline/cwe-dpr-reader-mmr
```

仅提交本任务路径。推送失败保留本地提交，记录准确哈希/失败原因/恢复命令；远端变化先检查分叉，不强推。无法完成后续阶段则停止扩展，做最小验证并推送明确 incomplete 的 checkpoint。

更新时间：2026-11-16T10:59:22+08:00。
