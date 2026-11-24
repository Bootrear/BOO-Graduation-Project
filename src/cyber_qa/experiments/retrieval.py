"""Independent retrieval ablations over an existing, unmodified DPR index.

Only question text enters retrieval. Gold IDs, intents and annotated CWE IDs
belong to evaluation and are deliberately absent from this interface.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
import math
import re

import numpy as np

from cyber_qa.data.candidates import RetrievedPassage
from cyber_qa.models import validate_vectors

METHODS = ("dpr", "hybrid", "subquery", "hierarchical")
STOPWORDS = frozenset("a an the is are was were be been being do does did can could "
                     "would should will may might what which who how why where when "
                     "and or of to in on at by for from with as it its this that these "
                     "those such have has had".split())


def lexical_tokens(text):
    # Split hyphens consistently in queries and documents, retain technical IDs.
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOPWORDS]


@dataclass(frozen=True)
class RetrievalExperimentConfig:
    version: str = "retrieval-ablation-v1"
    branch_depth: int = 100
    rrf_k: int = 60
    bm25_k1: float = 1.5
    bm25_b: float = 0.75
    entry_top_m: int = 3
    focused_fraction: float = 0.75

    def __post_init__(self):
        if self.version != "retrieval-ablation-v1":
            raise ValueError("unsupported retrieval experiment version")
        for name in ("branch_depth", "rrf_k", "entry_top_m"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 1:
                raise ValueError(f"{name} must be a positive integer")
        for name in ("bm25_k1", "bm25_b", "focused_fraction"):
            value = getattr(self, name)
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        if self.bm25_k1 <= 0 or not 0 <= self.bm25_b <= 1 or not 0 < self.focused_fraction < 1:
            raise ValueError("invalid BM25 or focused fraction parameters")

    def to_dict(self):
        return asdict(self)


class BM25:
    """Okapi BM25 with positive log(1 + odds) IDF; query terms counted once."""

    def __init__(self, documents, *, k1=1.5, b=0.75):
        self.k1, self.b = k1, b
        counts = [Counter(lexical_tokens(text)) for text in documents]
        self.lengths = np.array([sum(c.values()) for c in counts], dtype=np.float64)
        self.average_length = float(self.lengths.mean()) if len(counts) else 0.0
        postings = defaultdict(list)
        for i, count in enumerate(counts):
            for token, frequency in count.items():
                postings[token].append((i, frequency))
        self.postings = {}
        for token, entries in postings.items():
            indices, frequencies = zip(*entries)
            self.postings[token] = (np.array(indices), np.array(frequencies, dtype=np.float64),
                                   math.log1p((len(counts) - len(entries) + 0.5) / (len(entries) + 0.5)))

    def scores(self, query):
        scores = np.zeros(len(self.lengths), dtype=np.float64)
        for token in sorted(set(lexical_tokens(query))):
            if token not in self.postings:
                continue
            indices, tf, idf = self.postings[token]
            norm = 1 - self.b + self.b * self.lengths[indices] / self.average_length
            scores[indices] += idf * tf * (self.k1 + 1) / (tf + self.k1 * norm)
        return scores


def reciprocal_rank_fusion(rankings, k=60):
    scores = defaultdict(float)
    for ranking in rankings:
        # One vote per document per branch, even if a caller supplies duplicates.
        for rank, item in enumerate(dict.fromkeys(ranking), 1):
            scores[item] += 1.0 / (k + rank)
    return dict(scores)


def split_question(question):
    """Conservative English clause split, not an LLM or semantic parser.

    Split only 'and <question word>'; never split 'architecture and design'.
    Retain the original query and attach the first clause as context to the
    second. Unrecognized constructions fall back to the original DPR query.
    """
    original = question.strip()
    parts = re.split(r",?\s+and\s+(?=(?:what|which|how|why|where|when|who)\b)",
                     original.rstrip("?"), maxsplit=1, flags=re.IGNORECASE)
    if len(parts) != 2 or any(not part.strip() for part in parts):
        return [original]
    first, second = (p.strip() for p in parts)
    return list(dict.fromkeys([original, first + "?", second + "? Context: " + first + "."]))


@dataclass(frozen=True)
class RetrievalRun:
    candidates: tuple[RetrievedPassage, ...]
    trace: dict


class ExperimentRetriever:
    def __init__(self, runtime, index, config=None):
        self.runtime, self.index = runtime, index
        self.config = config or RetrievalExperimentConfig()
        self.ids = [p.passage_id for p in index.passages]
        self.positions = {pid: i for i, pid in enumerate(self.ids)}
        self.lexical = BM25([p.title + "\n" + p.text for p in index.passages],
                            k1=self.config.bm25_k1, b=self.config.bm25_b)
        groups = defaultdict(list)
        for i, passage in enumerate(index.passages):
            groups[passage.cwe_id].append(i)
        self.groups = dict(groups)
        self.entries = sorted(groups)
        entry_texts = []
        for cwe in self.entries:
            passages = [index.passages[i] for i in groups[cwe]]
            description = "\n".join(p.text for p in passages if p.field_name == "description")
            entry_texts.append(cwe + "\n" + passages[0].title + "\n" + description)
        self.entry_lexical = BM25(entry_texts, k1=self.config.bm25_k1, b=self.config.bm25_b)

    def _dense_scores(self, vector):
        vector = np.asarray(vector, dtype=np.float32)
        if vector.shape != (self.index.vectors.shape[1],):
            raise ValueError("question/index dimension mismatch")
        validate_vectors(vector.reshape(1, -1))
        scores = self.index.vectors @ vector
        if not np.isfinite(scores).all():
            raise ValueError("non-finite DPR scores")
        return scores

    def _order(self, scores, *, positive_only=False):
        return sorted((i for i in range(len(scores)) if not positive_only or scores[i] > 0),
                      key=lambda i: (-float(scores[i]), self.ids[i]))

    def retrieve(self, question: str, *, method: str, n: int) -> RetrievalRun:
        if method not in METHODS or type(n) is not int or n < 1:
            raise ValueError("invalid method or candidate count")
        vector = self.runtime.encode_question(question)
        trace = {"method": method, "queries": [question], "query_encoding_count": 1,
                 "retrieval_score_semantics": "original_question_raw_DPR_inner_product",
                 "retrieval_rank_semantics": "method_final_candidate_order"}
        if method == "dpr":
            # Call the original implementation unchanged, including ties.
            return RetrievalRun(self.index.search(vector, n=n), trace)
        scores = self._dense_scores(vector)
        dense_order = self._order(scores)
        depth = min(len(self.ids), max(n, self.config.branch_depth))
        ranking_scores = {}
        if method == "hybrid":
            lexical_scores = self.lexical.scores(question)
            lexical_order = self._order(lexical_scores, positive_only=True)[:depth]
            ranking_scores = reciprocal_rank_fusion(
                [[self.ids[i] for i in order] for order in (dense_order[:depth], lexical_order)],
                self.config.rrf_k)
            selected = sorted(ranking_scores, key=lambda pid: (-ranking_scores[pid], pid))[:n]
            trace.update(branch_depth=depth, branches={"dpr": [self.ids[i] for i in dense_order[:depth]],
                         "bm25": [self.ids[i] for i in lexical_order]},
                         ranking_score_semantics="equal_weight_RRF")
        elif method == "subquery":
            queries, skipped, orders = [question], [], [dense_order[:depth]]
            for query in split_question(question)[1:]:
                # Do not truncate or alter the frozen model input budget.
                try:
                    self.runtime.question_ids(query)
                except ValueError as exc:
                    skipped.append({"query": query, "reason": str(exc)})
                    continue
                orders.append(self._order(self._dense_scores(self.runtime.encode_question(query)))[:depth])
                queries.append(query)
            if len(queries) == 1:
                selected = [self.ids[i] for i in dense_order[:n]]
            else:
                ranking_scores = reciprocal_rank_fusion([[self.ids[i] for i in order] for order in orders],
                                                        self.config.rrf_k)
                selected = sorted(ranking_scores, key=lambda pid: (-ranking_scores[pid], pid))[:n]
            trace.update(queries=queries, query_encoding_count=len(queries), skipped_queries=skipped,
                         split_applied=len(queries) > 1, branch_depth=depth,
                         branches=[[self.ids[i] for i in order] for order in orders],
                         ranking_score_semantics="equal_weight_RRF" if len(queries) > 1 else "DPR")
        else:
            # Entry dense rank = rank by best-scoring member, not sum over a
            # variable number of passages (which would favor large entries).
            dense_entries = list(dict.fromkeys(self.index.passages[i].cwe_id for i in dense_order))
            lexical = self.entry_lexical.scores(question)
            lexical_entries = sorted((i for i, score in enumerate(lexical) if score > 0),
                                     key=lambda i: (-float(lexical[i]), self.entries[i]))
            entry_scores = reciprocal_rank_fusion(
                [dense_entries[:depth], [self.entries[i] for i in lexical_entries[:depth]]],
                self.config.rrf_k)
            ranked_entries = sorted(entry_scores, key=lambda cwe: (-entry_scores[cwe], cwe))
            chosen_entries = ranked_entries[:self.config.entry_top_m]
            target = min(n, len(self.ids))
            quota = math.floor(target * self.config.focused_fraction)
            focused = [i for i in dense_order if self.index.passages[i].cwe_id in chosen_entries][:quota]
            focused_set = set(focused)
            global_fill = [i for i in dense_order if i not in focused_set][:target - len(focused)]
            selected = [self.ids[i] for i in focused + global_fill]
            trace.update(entry_ranking=[{"cwe_id": cwe, "rrf_score": entry_scores[cwe]}
                                        for cwe in ranked_entries], chosen_entries=chosen_entries,
                         focused_quota=quota, focused_count=len(focused), global_count=len(global_fill),
                         ranking_score_semantics="entry_RRF_then_local_DPR_plus_global_DPR",
                         focused_ids=[self.ids[i] for i in focused])
        trace["ranking_scores"] = {pid: ranking_scores[pid] for pid in selected if pid in ranking_scores}
        candidates = tuple(RetrievedPassage(self.index.passages[self.positions[pid]], rank,
                            float(scores[self.positions[pid]]),
                            tuple(float(x) for x in self.index.vectors[self.positions[pid]]))
                           for rank, pid in enumerate(selected, 1))
        return RetrievalRun(candidates, trace)
