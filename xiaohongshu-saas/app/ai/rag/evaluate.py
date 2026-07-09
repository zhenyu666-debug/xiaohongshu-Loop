"""Offline RAG evaluation: hit-rate@k and MRR."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class EvalExample:
    question: str
    expected_sources: List[str]
    expected_answer_keywords: List[str] = field(default_factory=list)


@dataclass
class EvalResult:
    question: str
    hit_at_k: int
    reciprocal_rank: float
    answer_keyword_hits: int
    retrieved_sources: List[str]


@dataclass
class EvalReport:
    examples: List[EvalResult]
    hit_rate_at_k: float
    mrr: float
    avg_keyword_hit_rate: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "examples": [
                {
                    "question": e.question,
                    "hit_at_k": e.hit_at_k,
                    "reciprocal_rank": e.reciprocal_rank,
                    "answer_keyword_hits": e.answer_keyword_hits,
                    "retrieved_sources": e.retrieved_sources,
                }
                for e in self.examples
            ],
            "hit_rate_at_k": self.hit_rate_at_k,
            "mrr": self.mrr,
            "avg_keyword_hit_rate": self.avg_keyword_hit_rate,
        }


async def evaluate_retrieval(
    pipeline: Any,
    examples: List[EvalExample],
    top_k: int = 5,
    answer_check: Optional[Callable[[str, EvalExample], bool]] = None,
) -> EvalReport:
    """Run retrieval evaluation. Uses retriever.retrieve only (no generation needed)."""
    results: List[EvalResult] = []
    for ex in examples:
        retrieved = pipeline.retriever.retrieve(ex.question, top_k=top_k)
        retrieved_sources = [
            r.entry.metadata.get("source", "") for r in retrieved
        ]
        expected_set = set(ex.expected_sources)
        hit_at_k = 1 if any(s in expected_set for s in retrieved_sources) else 0
        rr = 0.0
        for i, src in enumerate(retrieved_sources, 1):
            if src in expected_set:
                rr = 1.0 / i
                break
        kw_hits = 0
        if answer_check is not None:
            generated = await pipeline.generator.generate(ex.question, retrieved)
            if answer_check(generated.answer, ex):
                kw_hits = 1
        else:
            if ex.expected_answer_keywords:
                kw_hits = sum(
                    1 for kw in ex.expected_answer_keywords
                    if any(kw.lower() in r.entry.metadata.get("text", "").lower() for r in retrieved)
                )
        results.append(EvalResult(
            question=ex.question,
            hit_at_k=hit_at_k,
            reciprocal_rank=rr,
            answer_keyword_hits=kw_hits,
            retrieved_sources=retrieved_sources,
        ))

    n = max(len(results), 1)
    hit_rate = sum(r.hit_at_k for r in results) / n
    mrr = sum(r.reciprocal_rank for r in results) / n
    if answer_check is not None:
        kw_rate = sum(r.answer_keyword_hits for r in results) / n
    else:
        total_kw = sum(len(ex.expected_answer_keywords) for ex in examples) or 1
        kw_rate = sum(r.answer_keyword_hits for r in results) / total_kw
    return EvalReport(examples=results, hit_rate_at_k=hit_rate, mrr=mrr, avg_keyword_hit_rate=kw_rate)