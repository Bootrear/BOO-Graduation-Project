# 实验运行手册（GPU 版）

本手册用于在**带 NVIDIA GPU 的 Linux 机器**上重跑 STEP1 探针集门禁实验：
判断 MMR 相对 Reader Top-K 是否带来增益，并定位瓶颈在检索、Reader 还是筛选。

- 代码分支：`step1/dataset-optimization`
- 数据：`data/annotations/probe-v1/qa.v1.jsonl`（40 题，机器起草，**复核后数字才可用于论文**）
- 环境基准：Linux x86_64、Python 3.12、torch 2.9.1+cu128、RTX 4090（见 `docs/DEPLOYMENT.md`）

> Windows 上用 CPU 跑过一次的结果：MMR 与 Top-K **40 题全平**（Recall@5 均 0.200），
> 检索天花板 0.275，必选证据检索中位排名 23。GPU 环境应复现同量级结果，并跑 N 扫描。

---

## 0. 取代码

```bash
git clone https://github.com/Bootrear/BOO-Graduation-Project.git
cd BOO-Graduation-Project
git switch step1/dataset-optimization
git log --oneline -3
```

已有工作副本则：

```bash
git fetch origin step1/dataset-optimization
git switch step1/dataset-optimization
git pull --ff-only
```

**不要**把 Windows 上的 `data/processed/` 或 `models/` 拷过来：CPU 与 GPU 的向量数值不同，
路径也不一致。在远端重新生成。

---

## 1. 环境

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -U pip
.venv/bin/python -m pip install -r requirements-inference.txt
.venv/bin/python -m pip install -e . --no-deps
.venv/bin/python -m pip check
.venv/bin/python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

期望最后一行是 `2.9.1+cu128 True NVIDIA GeForce RTX 4090`。若 `cuda.is_available()` 为 `False`，
先解决驱动/`nvidia-smi`，否则后续会静默跑在 CPU 上（慢 20 倍）。

如需代理，先导出再执行（不要改仓库里的网络配置）：

```bash
export HTTP_PROXY=http://<host>:<port>
export HTTPS_PROXY=$HTTP_PROXY
```

---

## 2. 下载并校验三个 DPR 模型

```bash
.venv/bin/python scripts/fetch_dpr_resources.py --weights
```

三行输出都应是 `verified 5 files at models/dpr/...`。总大小约 1.25 GB
（question / context / reader 各 417.7 MB，SHA-256 由上游 LFS 元数据校验）。

断网或失败直接重跑同一条命令即可续传；已校验的文件会跳过。

---

## 3. 预处理并核对快照

```bash
.venv/bin/python -m cyber_qa preprocess \
  --raw data/raw/cwe/cwec_v4.20.xml.zip \
  --output data/processed/cwe-v1
```

必须核对的三个值：

```bash
.venv/bin/python - <<'PY'
import json
m = json.load(open("data/processed/cwe-v1/manifest.json"))
s = json.load(open("data/processed/cwe-v1/statistics.json"))
print("snapshot_id     ", m["snapshot_id"])
print("passages_sha256 ", s["passages_sha256"])
print("final_passages  ", s["final_passages"])
PY
```

| 期望值 | |
| --- | --- |
| `snapshot_id` | `cwe:88e4eab3cc54f16611040a0e528d7a128253426e90ee5054327fd28449fee393` |
| `passages_sha256` | `a20e52c87054121dcfe3dfbf78f5399df3deb2d5c638e747f145facc82c71525` |
| `final_passages` | `5748` |

三者不一致就**停下**：说明数据或依赖版本不同，后续数字不可比。

再核对探针集的 200 个 `passage_id` 是否都能在真实快照里找到：

```bash
.venv/bin/python scripts/verify_probe_ids.py --passages data/processed/cwe-v1/passages.jsonl
```

期望 `一致 200，需修正 0，未找到 0`。有 `FIX` 行时按输出替换后再继续。

---

## 4. 建索引（只做一次）

```bash
.venv/bin/python -m cyber_qa build-index \
  --snapshot data/processed/cwe-v1 \
  --output data/processed/dpr-index-v1 \
  --device cuda --batch-size 32
```

记录输出里的 `vectors_sha256`、`offline_build_seconds`、`device`，写进实验笔记。
输出目录**不能已存在**；要重建先换目录名（如 `dpr-index-v1-gpu2`），不要删除旧目录。

索引与 N 无关：N=20/50/100 共用同一份索引，不用重建。

---

## 5. 先跑纯检索诊断（约 1 分钟）

在跑昂贵的 Reader 之前，先看清检索能给到多少：

```bash
.venv/bin/python scripts/eval_retrieval.py \
  --index data/processed/dpr-index-v1 \
  --snapshot data/processed/cwe-v1 \
  --device cuda \
  --out outputs/probe-retrieval.json
```

输出给出 `Recall@5/10/20/50/100/200` 曲线与必选证据的排名分布。

**判读：**

| 现象 | 含义 | 下一步 |
| --- | --- | --- |
| 曲线到 200 仍在涨 | 检索是硬瓶颈 | 扫到 N=100/200；或考虑换检索模型 |
| 中位排名远大于 20 | 现在 N=20 明显偏小 | 直接把 N 提到 50 或 100 |
| N=20 已接近饱和 | 瓶颈在 Reader 或筛选 | 重点看门禁里的 Reader 排名 |

---

## 6. 门禁主实验：N 扫描

```bash
for N in 20 50 100; do
  .venv/bin/python scripts/eval_probe.py \
    --index data/processed/dpr-index-v1 \
    --snapshot data/processed/cwe-v1 \
    --device cuda \
    --n $N \
    --out outputs/probe-eval-N$N.json
done
```

- `--n` 只覆盖 `candidate_count`，不改配置文件，也不写入仓库。
- GPU 上每轮 40 题通常在 1 分钟内完成（CPU 约 3 分钟）。
- Reader 的推理量随 N 线性增长；N=200 时注意显存与时间。

**看这几行输出：**

```
检索天花板            ← 必选证据进入 N 个候选的比例（= Recall@N）
Evidence Recall@5     Top-K … | MMR …
配对差值 (MMR-TopK)   …  95%CI […]  P(差值<=0)=…
逐题胜负              MMR 更好 a | 更差 b | 平 c
正确段 Reader 排名    mean … (median …) | 进前5的 x/y
仅看必选证据全部入池  n=… | Top-K … | MMR …
策略分歧              order …/40 | set …/40
池内平均两两余弦      …
```

---

## 7. 判读规则（事先定好，避免事后找解释）

在**必选证据全部入池**的题上比较，才是在评价筛选策略本身：

| 条件 | 结论 |
| --- | --- |
| 配对差值 95%CI 不含 0 且为正 | MMR 有增益，可继续扩到正式 120 题 |
| 差值 ≈ 0，且 `仅看必选证据全部入池` 一栏两者相同 | **筛选层无差异**：MMR 在本任务上无效，论文按此立论 |
| 差值 ≈ 0，但 `正确段 Reader 排名` 中位 ≤ 5 | Reader 已足够好，筛选没有改进空间 |
| `检索天花板` 明显低于 `Recall@5` 的可达上限 | 瓶颈在检索，先修检索再谈筛选 |

判定 MMR 前必须满足：`检索天花板` 足够高（约 ≥ 0.5），且 `正确段 Reader 排名` 有较大分散。
否则属于"测量仪器分辨率不足"，不能得出"MMR 无效"的结论。

---

## 8. λ 扫描（仅在选定 N 之后）

λ 是 MMR 唯一的自由参数，只能在开发集上定。探针集属于探索性使用：

```bash
for L in 0.0 0.25 0.5 0.75 1.0; do
  .venv/bin/python scripts/eval_probe.py \
    --index data/processed/dpr-index-v1 \
    --snapshot data/processed/cwe-v1 \
    --device cuda \
    --n 50 --lam $L \
    --out outputs/probe-eval-N50-lam$L.json
done
```

自检：`--lam 1.0` 时 MMR 的选择应与 Reader Top-K **完全一致**（`策略分歧 order 0/40`）。
若不是，说明实现或调用有问题，先查代码再继续。

---

## 9. 汇总成一张表

```bash
.venv/bin/python - <<'PY'
import glob, json
for path in sorted(glob.glob("outputs/probe-eval-*.json")):
    s = json.load(open(path))["summary"]
    d = s["evidence_recall_5"]["paired_diff"]
    print(f'{path:38s} N={s["config"]["candidate_count"]:<4d} lam={s["config"]["lambda_weight"]:<5} '
          f'ceil={s["retrieval_ceiling"]:.3f} topk={s["evidence_recall_5"]["reader_topk"]:.3f} '
          f'mmr={s["evidence_recall_5"]["mmr"]:.3f} diff={d["mean"]:+.3f} '
          f'CI=[{d["ci95"][0]:+.3f},{d["ci95"][1]:+.3f}] '
          f'win/lose/tie={s["per_question_outcome"]["mmr_better"]}/'
          f'{s["per_question_outcome"]["mmr_worse"]}/{s["per_question_outcome"]["tie"]}')
PY
```

---

## 10. 留档与提交

- 逐题结果在 `outputs/`（被 `.gitignore` 忽略，不上传）。
- 需要进论文的数字，另存到 `experiments/<YYYYMMDD-HHMM>_probe-gate_<snapshot>/`，
  按 `experiments/README.md` 的 `config.json / manifest.json / per_question.jsonl / summary.json / notes.md` 组织。
- 提交任何文件后，按用户要求**在 `docs/COMMIT_LOG.md` 表末追加一行**（时间、任务名称、主要内容）。

---

## 11. 常见失败

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `refusing to overwrite snapshot/index` | 输出目录已存在 | 换新目录名，不要删旧的 |
| `模型加载 … device=cpu` | CUDA 不可用 | 检查 `nvidia-smi`、torch 是否 cu 版本 |
| CUDA OOM（`build-index`） | batch 太大 | `--batch-size 16` 或 `8` |
| CUDA OOM（`eval_probe`） | N 太大或 batch 太大 | 降 `--batch-size`，或先跑 N=50 |
| 权重校验失败 | 下载被截断 | 重跑 `fetch_dpr_resources.py --weights` |
| `passages_sha256` 不一致 | 依赖或原始文件不同 | 停止，核对 `data/raw` 的 CWE 与依赖版本 |
| `verify_probe_ids` 有 FIX | 分词器分块不同 | 按输出替换 `passage_index.json` 与骨架中的 ID |

---

## 12. 时间预算（RTX 4090）

| 步骤 | 预计 |
| --- | --- |
| 依赖安装 + 模型下载 | 10–20 分钟（看网络） |
| 预处理 | 30–60 秒 |
| 建索引（5748 段） | 10–20 秒（含模型加载） |
| 纯检索诊断 | < 1 分钟 |
| 门禁一轮（N=20） | < 1 分钟 |
| N 扫描三档 + λ 扫描五档 | 约 10 分钟 |
