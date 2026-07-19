"""Tests for the stdlib port of TigerLily edge-feature operators.

The values are verified against hand-computed expected outputs (no numpy, no
networkx). Mirrors ``tigerlily.operator`` from
https://github.com/benedekrozemberczki/tigerlily (Apache-2.0).
"""

from __future__ import annotations

import math

import pytest

from app.queries import edge_features
from app.queries.edge_features import (
    OPERATORS,
    apply_operator,
    concatenation_operator,
    cosine_similarity,
    difference_operator,
    hadamard_operator,
    l1_norm_operator,
    l2_norm_operator,
)


# Two simple 4-D embeddings — chosen so each operator's expected value is
# trivially hand-checkable.
LEFT = [1.0, 2.0, 3.0, 4.0]
RIGHT = [5.0, 6.0, 7.0, 8.0]


def test_hadamard_operator_matches_expected() -> None:
    """Element-wise product: [1*5, 2*6, 3*7, 4*8] = [5, 12, 21, 32]."""
    assert hadamard_operator(LEFT, RIGHT) == [5.0, 12.0, 21.0, 32.0]


def test_difference_operator_matches_expected() -> None:
    """left - right: [-4, -4, -4, -4]."""
    assert difference_operator(LEFT, RIGHT) == [-4.0, -4.0, -4.0, -4.0]


def test_l1_norm_operator_matches_expected() -> None:
    """Absolute differences: [4, 4, 4, 4]."""
    assert l1_norm_operator(LEFT, RIGHT) == [4.0, 4.0, 4.0, 4.0]


def test_l2_norm_operator_matches_expected() -> None:
    """Squared differences: [16, 16, 16, 16]. sqrt(sum) = 8 = euclidean."""
    out = l2_norm_operator(LEFT, RIGHT)
    assert out == [16.0, 16.0, 16.0, 16.0]
    assert math.isclose(math.sqrt(sum(out)), 8.0, rel_tol=1e-9)


def test_concatenation_operator_matches_expected() -> None:
    """Concatenation: [1, 2, 3, 4, 5, 6, 7, 8]."""
    assert concatenation_operator(LEFT, RIGHT) == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]


def test_apply_operator_dispatch() -> None:
    """apply_operator is a thin dispatcher over the OPERATORS registry."""
    for name in OPERATORS:
        out = apply_operator(name, LEFT, RIGHT)
        # Round-trip through the direct function must agree.
        assert out == OPERATORS[name](LEFT, RIGHT)


def test_apply_operator_unknown_raises() -> None:
    with pytest.raises(KeyError):
        apply_operator("not-a-real-operator", LEFT, RIGHT)


def test_mismatched_lengths_raise() -> None:
    """Mismatch is reported eagerly (numpy would broadcast silently)."""
    with pytest.raises(ValueError):
        hadamard_operator([1.0, 2.0], [1.0, 2.0, 3.0])
    with pytest.raises(ValueError):
        difference_operator([1.0], [1.0, 2.0])
    with pytest.raises(ValueError):
        cosine_similarity([1.0], [1.0, 2.0])


def test_cosine_similarity_orthogonal() -> None:
    """[1, 0] vs [0, 1] are orthogonal — similarity = 0."""
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_cosine_similarity_parallel() -> None:
    """[1, 2] vs [2, 4] are parallel — similarity = 1."""
    assert math.isclose(cosine_similarity([1.0, 2.0], [2.0, 4.0]), 1.0, rel_tol=1e-9)


def test_cosine_similarity_zero_vector_returns_zero() -> None:
    """A zero-norm input must not produce a NaN; we define this as 0."""
    assert cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0
    assert cosine_similarity([1.0, 2.0], [0.0, 0.0]) == 0.0


def test_operators_module_exports() -> None:
    """The package re-exports the operators so callers can ``from app.queries import edge_features``."""
    for name in (
        "hadamard_operator",
        "difference_operator",
        "l1_norm_operator",
        "l2_norm_operator",
        "concatenation_operator",
        "apply_operator",
        "cosine_similarity",
        "OPERATORS",
    ):
        assert hasattr(edge_features, name), f"missing export: {name}"


def test_operators_registry_keys() -> None:
    """The registry keys match the public names callers may pass to apply_operator."""
    assert set(OPERATORS) == {"hadamard", "difference", "l1", "l2", "concat"}
