# probe-v1-zh: machine-translated parallel questions

`qa.v1.zh.jsonl` is a machine-translated, **not human-reviewed** Chinese parallel
of `../probe-v1/qa.v1.jsonl`. Qwen2.5-7B-Instruct produced each `question` offline
from the original English question. The source labels, evidence IDs, gold facts,
snapshot, and all other source fields are preserved; the derived record adds
`translation_status=machine_translated_needs_human_review`,
`translated_language=zh`, `reviewer=null`, and `source_question_sha256`.

This is an exploratory probe only. It is not a reviewed dataset or a paper test
set. No translation component is part of the online retrieval/answering path.

Regenerate in a prepared environment with the pinned local model:

```bash
.venv/bin/python scripts/make_chinese_probe.py \
  --input data/annotations/probe-v1/qa.v1.jsonl \
  --output data/annotations/probe-v1-zh/qa.v1.zh.jsonl \
  --model-dir models/crosslingual/Qwen--Qwen2.5-7B-Instruct/a09a35458c702b33eeacc393d103063234e8bc28 \
  --device cuda --max-new-tokens 96
```
