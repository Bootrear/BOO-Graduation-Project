"""A single retrieval/Reader/preparation pass feeds either or both strategies."""

from datetime import datetime, timezone
from importlib.metadata import version
import platform
import time

from cyber_qa.answering.ordinary import assemble_answer, failed_answer
from cyber_qa.config import AnswerConfig, BaselineConfig, ReaderConfig
from cyber_qa.data.contracts import stable_hash
from cyber_qa.models import DPRRuntime
from cyber_qa.reader.dpr import DPRReaderScorer
from cyber_qa.retrieval.dpr import load_index
from cyber_qa.selection.mmr import prepare_pool, reader_topk, select_mmr


class QAPipeline:
    def __init__(self, runtime, index, config=None, *, startup=None):
        self.runtime, self.index = runtime, index
        self.config = config or BaselineConfig()
        self.scorer = DPRReaderScorer(runtime)
        self.startup = startup or {}

    @classmethod
    def load(cls, index_path, snapshot_path, *, config=None, **runtime_args):
        started = time.perf_counter()
        runtime = DPRRuntime(**runtime_args)
        runtime_seconds = time.perf_counter() - started
        started = time.perf_counter()
        index = load_index(index_path, snapshot_path, runtime)
        return cls(runtime, index, config, startup={"runtime_initialization_seconds": runtime_seconds,
            "index_load_seconds": time.perf_counter() - started})

    def query(self, question, *, strategy="mmr", batch_size=8):
        started = time.perf_counter()
        stage = "validation"
        runtime = self.runtime
        before_load = runtime.model_load_seconds
        record = {"schema_version": "ordinary-run-v1", "question": question,
            "recorded_at": datetime.now(timezone.utc).isoformat(), "status": "running",
            "configuration": {"baseline": self.config.to_dict(), "reader": ReaderConfig().to_dict(),
                              "answer": AnswerConfig().to_dict(), "input_budget": runtime.budget.to_dict()},
            "index": self.index.metadata, "startup_timings": self.startup,
            "environment": {"python": platform.python_version(), **{name: version(name) for name in
                            ("torch", "transformers", "tokenizers", "numpy")}},
            "device": runtime.device, "timings": {}, "results": {}}
        record["configuration_sha256"] = stable_hash(record["configuration"])
        try:
            if strategy not in ("mmr", "reader_topk", "both"):
                raise ValueError("strategy must be mmr, reader_topk or both")
            if type(batch_size) is not int or batch_size < 1:
                raise ValueError("batch_size must be a positive integer")
            ids = runtime.question_ids(question)
            record["question_input"] = {"question_tokens": len(ids), "truncated": False,
                                        "policy": runtime.budget.long_question_policy}
            stage = "question_model_loading"
            runtime.load_model("question")
            stage = "question_encoding"
            tick = time.perf_counter()
            vector = runtime.encode_question(question)
            record["timings"]["question_encoding_seconds"] = time.perf_counter() - tick
            stage = "retrieval"
            tick = time.perf_counter()
            candidates = self.index.search(vector, n=self.config.candidate_count)
            record["timings"]["retrieval_seconds"] = time.perf_counter() - tick
            record["candidate_count"] = len(candidates)
            stage = "reader"
            reader = self.scorer.score(question, candidates, batch_size=batch_size)
            record["reader"] = reader.to_dict()
            record["timings"]["reader_seconds"] = reader.reader_seconds
            stage = "pool_preparation"
            tick = time.perf_counter()
            pool = prepare_pool(reader.candidates, self.config)
            record["timings"]["pool_preparation_seconds"] = time.perf_counter() - tick
            record["candidates"] = [c.to_dict() for c in pool.candidates]
            strategies = ("reader_topk", "mmr") if strategy == "both" else (strategy,)
            for name in strategies:
                stage = "selection_" + name
                tick = time.perf_counter()
                selected = (reader_topk if name == "reader_topk" else select_mmr)(pool, self.config)
                record["timings"][stage + "_seconds"] = time.perf_counter() - tick
                stage = "answer_" + name
                tick = time.perf_counter()
                answer = assemble_answer(selected, len(pool.candidates), self.config)
                record["timings"][stage + "_seconds"] = time.perf_counter() - tick
                record["results"][name] = {"selection": selected.to_dict(), "answer": answer.to_dict()}
            record["status"] = "success"
        except Exception as exc:
            record["status"] = "failed"
            record["error"] = {"stage": stage, "type": type(exc).__name__, "message": str(exc)}
            record["results"] = {}  # never expose a partly completed query as normal results
            record["failure_answer"] = failed_answer(f"{stage}: {type(exc).__name__}: {exc}").to_dict()
        record["model_provenance"] = runtime.provenance
        record["weight_sha256"] = dict(runtime.weight_hashes)
        record["model_loading_info"] = dict(runtime.loading_info)
        record["timings"]["model_load_seconds"] = runtime.model_load_seconds - before_load
        record["timings"]["query_total_seconds"] = time.perf_counter() - started
        return record
