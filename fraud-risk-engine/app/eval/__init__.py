"""Evaluation harness for the fraud-detection layer.

Submodules:
- :mod:`app.eval.backtest` — precision / recall / F1 sweeps over threshold grids
  using the synthetic dataset's planted rings as ground truth.

The package is intentionally stdlib-only — no scikit-learn dependency. All
metrics are simple enough to derive from a confusion-matrix dict.
"""
