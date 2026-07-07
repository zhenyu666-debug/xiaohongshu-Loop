# Rate-limit Probe Findings

**Date:** 2026-07-07 20:24 UTC+8
**Account:** acc_676072139 (卡匹迪恩)
**Template:** mgu_phd
**CSV:** `C:\Users\Hasee\.qclaw\workspace\get_jobs\xiaohongshu-saas\logs\rate_probe_20260707_201805.csv`

## Summary

- Total attempts: 2
- Success: 0
- Stopped early: False - 

## Per-Rung Results

| Rung | Interval | OK | Failed | Throttled | Verdict |
|------|----------|----|--------|-----------|--------|
| 1 | 1m | 0 | 2 | 0 | mixed |
## Observations

_Manually fill in after reviewing the CSV and XHS creator dashboard screenshots._

## Recommendations

_Manually fill in after observing at which rung 限流 fires._

## Next Steps

1. Set `interval_minutes` in the Task row based on the last safe rung.
2. If no 限流 observed, push the cadence higher.
3. Monitor the account stage in the DB after 24h - if it transitions to `cooling` or `banned`, pause all publishing.
