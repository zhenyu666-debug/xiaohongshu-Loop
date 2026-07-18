import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.loader.synth_generator import build_dataset
from app.detection.local_detector import run_local_detector
from app.eval.backtest import backtest_run, write_backtest_html, render_backtest_html
import tempfile, os

ds = build_dataset(accounts=120, devices=80, merchants=20, transactions=2000, fraud_rings=4, seed=20260716)
alerts = run_local_detector(ds, ring_min_len=3, shared_device_min=3, burst_min_count=10, top_k=20).alerts
result = backtest_run(alerts, ds, seed=20260716)

elapsed = result.metrics['elapsed_ms']
print(f'best_threshold = {result.best_threshold}')
print(f'best_f1        = {result.best_f1}')
print(f'rows           = {len(result.thresholds)}')
print(f'ground truth   = {result.ground_truth_size}')
print(f'planted rings  = {result.planted_ring_count}')
print(f'elapsed_ms     = {elapsed}')

with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
    html = render_backtest_html(result)
    f.write(html)
    path = f.name
    print(f'wrote {len(html)} bytes to {path}')
    has_best = "class='best'" in html
    print(f'has class best : {has_best}')
    print(f'has best row   : {"precision" in html}')
