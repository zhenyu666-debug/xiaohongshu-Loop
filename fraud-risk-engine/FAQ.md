# Frequently-Asked Questions

### Q: I ran `docker pull tigergraph/tigergraph:latest` and it hung — why?

Your Docker daemon is configured with a registry-mirror at
`https://docker.1ms.run` that points at `127.0.0.1:7890`. If the local
proxy is not running the connection is refused.

Fix options:

1. Start your local proxy (Clash / similar) and retry.
2. Edit Docker Desktop → Settings → Docker Engine and remove the
   `registry-mirrors` entries; restart Docker Desktop.

Until the image is present, the API still works — the in-memory
detector kicks in transparently.

### Q: Can I use real customer data?

Not without writing a separate ingestion path. This project ships with a
synthetic generator only — no `data/seed/*.csv` should ever contain
real PII.

### Q: Where is the TigerGraph password?

In `TG_PASSWORD` env var; defaults to `tigergraph`. Override before
deploying.

### Q: Why vanilla JS / no React?

The frontend is a single HTML file + ~300 lines of vanilla JS. It works
air-gapped and avoids a Node build pipeline. If you outgrow it, the
data model in `/api/detector/run` is the contract.

### Q: How do I add a new detection rule?

1. Add a new GSQL query in `app/queries/fraud_queries.py`.
2. Add a post-processor in `app/detection/models.py`.
3. Add a matching in-memory algorithm in
   `app/detection/local_detector.py`.
4. Wire both into `run_local_detector` and `TigerGraphDetector.run`.
5. Add tests in `tests/test_detection.py`.

### Q: Why two memory layers?

Static memory is curated and checked in. Dynamic memory is regenerated
on every detection run — it's a "what just happened" snapshot rather
than tribal knowledge.
