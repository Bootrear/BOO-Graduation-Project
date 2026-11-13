# 基线环境与资源记录

记录日期：2026-11-13，Asia/Shanghai。当前只完成 P01 开发环境与配置验证，未完成模型部署。

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

## 资源获取与接口核验计划（尚未执行）

1. CWE：先检查 [MITRE 官方下载页](https://cwe.mitre.org/data/downloads.html) 与 [历史发布](https://cwe.mitre.org/data/archive.html)，优先获取历史文档指向的 4.20；若实际文件不同，登记其真实版本和哈希，不能冒用旧 manifest。原始文件保留在忽略的 data/raw，记录下载完成时间与依据。
2. DPR：核查 [Transformers DPR 官方文档](https://huggingface.co/docs/transformers/model_doc/dpr)。候选资源是同一训练系列的 `facebook/dpr-question_encoder-single-nq-base`、`facebook/dpr-ctx_encoder-single-nq-base` 与 `facebook/dpr-reader-single-nq-base`；目前只是待核查候选，不是已安装或已冻结的模型。
3. 通过模型库的实际 revision 固定权重与 tokenizer，记录精确依赖版本、配置维度、最大长度；用实际输出检查 question/context 的 pooler_output 维度、Reader 的 relevance/start/end 形状与 passage 顺序。
4. Reader/span 映射及问题/标题/特殊 token 预算先在小样本检查，再冻结 P03/P06 参数。检索使用模型所需原始度量，MMR 使用独立余弦副本。
5. 若模型下载受阻，保留错误与恢复命令，先做独立契约与数学回归；不标记真实模型/端到端通过。

原始数据、权重、缓存和索引均不上传 Git。未来模型部署命令、索引和查询命令必须在真正实现后补充，不在此提供不存在的 CLI。
