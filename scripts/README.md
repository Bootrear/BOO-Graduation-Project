# 脚本入口

在仓库根目录的 Python >= 3.10 独立环境中执行，安装步骤见[主 README](../README.md)。

| 脚本 | 实际能力与前提 |
| --- | --- |
| [smoke_demo.py](smoke_demo.py) | 运行早期 DSES 合成数据示例；需先安装本项目，不下载模型、不执行真实问答 |
| [validate_raw_data.py](validate_raw_data.py) | 使用标准库校验本地完整起始快照：NVD metadata／哈希、CWE ZIP／XML、CAPEC XML、ATT&CK STIX、KEV JSON，并输出文件 SHA-256 |

数据校验脚本要求 [SOURCES.md](../data/SOURCES.md) 列出的所有原始文件存在，包括 NVD `.meta`；它不是下载器，也不校验知识段或向量索引。Git 克隆不含原始数据，缺文件时不能直接运行该脚本。

CWE ETL、索引构建、知识库更新、双模式问答及正式实验入口尚未实现，后续按实际交付补充，不提供占位启动命令。
