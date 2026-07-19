"""Edge-feature operators from personalised-PageRank / NMF node embeddings.

Ported from the TigerLily library (Apache-2.0, Benedek Rozemberczki, 2022):
    https://github.com/benedekrozemberczki/tigerlily

The original TigerLily ``operator`` module exposes five edge-feature operators
(hadamard, difference, L1, L2, concatenation) that combine two node embeddings
into a single edge feature vector. They are commonly used to feed link-prediction
classifiers (LightGBM in TigerLily's drug-interaction pipeline).

Why a stdlib-only port?
------------------------
``fraud-risk-engine`` is intentionally stdlib-friendly at runtime (see
``pyproject.toml``). TigerLily uses ``numpy``, which we don't ship. This module
operates on plain Python lists of floats instead — slower for large vectors, but
keeps the runtime dep graph small and the code reviewable. Tests in
``tests/test_edge_features.py`` cross-check the math against hand-computed
expected values.

Use case in fraud-risk-engine
-----------------------------
Given a PPR / NMF embedding for an account and one for a device (or two
accounts), these operators produce a feature vector that downstream risk
detectors (or ML classifiers, if later added) can consume. Each operator is
pure and deterministic; pair it with :func:`app.eval.graph_robustness` to score
the resulting feature vectors across the funds-flow graph.
"""

from __future__ import annotations

from typing import List, Sequence

Vector = Sequence[float]


def _broadcastable(a: Vector, b: Vector) -> None:
    """Verify two embedding vectors have the same length.

    TigerLily operates on ``np.ndarray`` which broadcasts mismatched shapes;
    we raise eagerly instead so callers don't get a silent truncated result.
    """
    if len(a) != len(b):
        raise ValueError(
            f"embedding length mismatch: left={len(a)} right={len(b)}"
        )


def hadamard_operator(embedding_left: Vector, embedding_right: Vector) -> List[float]:
    """Element-wise product — equivalent to ``np.multiply``.

    Mirrors ``tigerlily.operator.hadamard_operator``.
    """
    _broadcastable(embedding_left, embedding_right)
    return [float(x) * float(y) for x, y in zip(embedding_left, embedding_right)]


def difference_operator(embedding_left: Vector, embedding_right: Vector) -> List[float]:
    """Element-wise subtraction — ``left - right``.

    Mirrors ``tigerlily.operator.difference_operator``.
    """
    _broadcastable(embedding_left, embedding_right)
    return [float(x) - float(y) for x, y in zip(embedding_left, embedding_right)]


def l1_norm_operator(embedding_left: Vector, embedding_right: Vector) -> List[float]:
    """Element-wise absolute difference.

    Mirrors ``tigerlily.operator.l1_norm_operator`` (which uses ``np.abs``).
    """
    _broadcastable(embedding_left, embedding_right)
    return [abs(float(x) - float(y)) for x, y in zip(embedding_left, embedding_right)]


def l2_norm_operator(embedding_left: Vector, embedding_right: Vector) -> List[float]:
    """Element-wise squared difference.

    Mirrors ``tigerlily.operator.l2_norm_operator`` (which uses ``np.square``).
    Sum across the vector yields squared Euclidean distance; the full norm is
    ``sqrt(sum(l2))``.
    """
    _broadcastable(embedding_left, embedding_right)
    diff = difference_operator(embedding_left, embedding_right)
    return [d * d for d in diff]


def concatenation_operator(
    embedding_left: Vector, embedding_right: Vector
) -> List[float]:
    """Concatenate two embeddings head-to-tail.

    Mirrors ``tigerlily.operator.concatenation_operator`` (which uses
    ``np.concatenate(..., axis=1)``). Output length is ``len(left) + len(right)``.
    """
    return [float(x) for x in embedding_left] + [float(y) for y in embedding_right]


# ---------------------------------------------------------------------------
# Operator registry (mirrors tigerlily.operators dict if/when added upstream)
# ---------------------------------------------------------------------------


OPERATORS = {
    "hadamard": hadamard_operator,
    "difference": difference_operator,
    "l1": l1_norm_operator,
    "l2": l2_norm_operator,
    "concat": concatenation_operator,
}


def apply_operator(name: str, left: Vector, right: Vector) -> List[float]:
    """Dispatch to the named operator.

    :param name: one of ``"hadamard" | "difference" | "l1" | "l2" | "concat"``
    :param left: left embedding vector
    :param right: right embedding vector
    :returns: the resulting edge-feature vector
    :raises KeyError: if ``name`` is not a registered operator
    """
    try:
        op = OPERATORS[name]
    except KeyError as exc:
        raise KeyError(
            f"unknown edge-feature operator {name!r}; "
            f"known: {sorted(OPERATORS)}"
        ) from exc
    return op(left, right)


def cosine_similarity(left: Vector, right: Vector) -> float:
    """Cosine similarity between two embedding vectors.

    Not part of the original TigerLily operator module but a natural complement
    to the existing :class:`AlertKind` "embedding_cosine_sim" branch in
    :mod:`app.detection.tg_detector`. Pure stdlib.
    """
    _broadcastable(left, right)
    dot = sum(float(x) * float(y) for x, y in zip(left, right))
    norm_l = sum(float(x) * float(x) for x in left) ** 0.5
    norm_r = sum(float(y) * float(y) for y in right) ** 0.5
    if norm_l == 0.0 or norm_r == 0.0:
        return 0.0
    return dot / (norm_l * norm_r)


__all__ = [
    "OPERATORS",
    "Vector",
    "apply_operator",
    "concatenation_operator",
    "cosine_similarity",
    "difference_operator",
    "hadamard_operator",
    "l1_norm_operator",
    "l2_norm_operator",
]
