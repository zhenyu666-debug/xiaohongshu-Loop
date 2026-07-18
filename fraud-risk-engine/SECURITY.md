# Security notes

- **No real PII.** The engine ships with a synthetic data generator. Do
  not load real customer records into this repository.
- **No secrets in repo.** All credentials live in environment variables
  (see `.env.example`). The default TigerGraph password is the upstream
  default (`tigergraph/tigergraph`) — override before any external
  deploy.
- **Docker mirror.** The host's Docker daemon is configured to use
  `https://docker.1ms.run` as a registry mirror. Until the proxy is
  running, `docker pull` will hang. Set
  `{"registry-mirrors": []}` in the Docker daemon config or run your
  preferred HTTP proxy.
- **Fallback behaviour.** When TigerGraph is unreachable the API serves
  the in-memory detector. This is **by design** for offline / air-gapped
  environments, but frontends should still respect the
  `/api/health.tigergraph.status` field and surface it in the UI.
