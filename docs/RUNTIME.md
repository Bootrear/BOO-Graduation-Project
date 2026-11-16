# 基线环境与资源记录

记录日期：2026-11-13，Asia/Shanghai。P01 开发环境与配置已验证；P02 真实数据进展见 CWE_CONTRACT.md，未完成模型部署。

## 已验证的开发环境

- Linux x86_64，Python 3.12.11；项目核心只依赖标准库。
- 独立环境 `.venv` 由 `python -m venv .venv` 建立，没有继承宿主 site-packages。
- `.venv/bin/python -m pip install -e '.[dev]'` 安装成功；测试工具精确版本见根 `requirements-dev.txt`。
- `.venv/bin/python -m pytest -q`：P01 时共 26 passed（原有 6 项 + 配置 20 项）。
- `.venv/bin/python scripts/smoke_demo.py`：旧 DSES 合成示例通过；`.venv/bin/python -m pip check` 无依赖冲突。

重建同一开发工具环境：

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pip install -e .
.venv/bin/python -m pytest -q
.venv/bin/python scripts/smoke_demo.py
```

上述重建步骤组合未从第二个全新环境重放；各安装/测试命令已在当前环境执行。不要把本节当成完整问答部署说明。

## 硬件与宿主环境检查

RTX 4090、24564 MiB 总显存、检查时 24109 MiB 空闲；约 64 GiB 内存、48 GiB 磁盘可用。
宿主 Python 的 torch=2.13.0+cu132、numpy=2.3.5；`torch.cuda.is_available()` 为 True，CUDA 张量 `[1,2]` 求和得到 3.0。
**这些包不在独立 .venv 内**；P05 模型运行依赖需单独安装、验证和锁定，不应为复用宿主库破坏独立环境。

## 当前可加载的配置

`configs/baseline.v1.json` 通过 `cyber_qa.config.BaselineConfig.load` 读取：

```bash
.venv/bin/python -c "from cyber_qa.config import BaselineConfig; print(BaselineConfig.load('configs/baseline.v1.json').to_dict())"
```

N=20、K=5、λ=0.5；λ 标记 untuned。min-max 范围是完整有效候选池，epsilon=1e-12；相似度约定为 max(0, clipped cosine)。固定同分规则与失败策略有版本约束，非法数值/未知键/重复键拒绝加载。
K=0 和不足 K 允许；N 必须为正整数；λ∈[0,1]。此阶段只实现配置校验，评分算法将在 P04 实现。

## 资源获取与接口核验计划（P01 制定，进展另行登记）

1. CWE：先检查 [MITRE 官方下载页](https://cwe.mitre.org/data/downloads.html) 与 [历史发布](https://cwe.mitre.org/data/archive.html)，优先获取历史文档指向的 4.20；若实际文件不同，登记其真实版本和哈希，不能冒用旧 manifest。原始文件保留在忽略的 data/raw，记录下载完成时间与依据。
2. DPR：核查 [Transformers DPR 官方文档](https://huggingface.co/docs/transformers/model_doc/dpr)。候选资源是同一训练系列的 `facebook/dpr-question_encoder-single-nq-base`、`facebook/dpr-ctx_encoder-single-nq-base` 与 `facebook/dpr-reader-single-nq-base`；目前只是待核查候选，不是已安装或已冻结的模型。
3. 通过模型库的实际 revision 固定权重与 tokenizer，记录精确依赖版本、配置维度、最大长度；用实际输出检查 question/context 的 pooler_output 维度、Reader 的 relevance/start/end 形状与 passage 顺序。
4. Reader/span 映射及问题/标题/特殊 token 预算先在小样本检查，再冻结 P03/P06 参数。检索使用模型所需原始度量，MMR 使用独立余弦副本。
5. 若模型下载受阻，保留错误与恢复命令，先做独立契约与数学回归；不标记真实模型/端到端通过。

原始数据、权重、缓存和索引均不上传 Git。未来模型部署命令、索引和查询命令必须在真正实现后补充，不在此提供不存在的 CLI。

P02 更新：CWE 4.20 已下载并真实解析，原始哈希与历史清单一致；详见 [CWE 契约](CWE_CONTRACT.md)。模型/tokenizer 获取及推理仍未执行。

P03 更新：独立 .venv 已安装 transformers=4.57.1、tokenizers=0.22.2 等（完整版本见 requirements-tokenization.txt），通过带约束的 editable 安装与 pip check。三角色 tokenizer/固定 revision/输入布局、真实 CWE 分段与重载已验证，详见 CWE_CONTRACT.md 的 P03 节。模型权重与独立环境 torch 尚未安装。

## P05 实测更新（2026-11-16T10:58:24+08:00）

独立 `.venv` 已安装 torch=2.9.1+cu128、CUDA runtime=12.8；RTX 4090 真实 DPR 双编码器推理及完整建库通过。三模型权重均按固定 revision 的上游 LFS 大小/SHA-256 校验。NumPy float32 精确原始内积索引已选定，不需要 FAISS。锁定环境见根 `requirements-inference.txt`，详细命令、产物哈希、加载参数差异与验收见 [RETRIEVAL.md](RETRIEVAL.md)。

首次安装实际命令：`.venv/bin/python -m pip install -e '.[inference]' -c requirements-tokenization.txt`。`pip check` 无冲突，最终全套 99 passed。宿主环境未改写、未作为模型运行依赖复用；网络配置未修改。完整新环境重建仍待 P10，Reader 推理仍待 P06。
