# xhs-saas K8s Deployment & Operations

Production-grade Kubernetes deployment for xhs-saas (Xiaohongshu SaaS) with AI Agent platform.

## Architecture

```
                          ┌──────────────────────┐
                          │   Ingress (nginx)    │
                          │  xhs.example.com     │
                          └──────────┬───────────┘
                                     │
                          ┌──────────┴───────────┐
                          │                      │
                  ┌───────▼────────┐   ┌────────▼────────┐
                  │  xhs-frontend  │   │  xhs-backend    │
                  │  (nginx + SPA) │   │  (FastAPI)      │
                  │  replicas: 2-6 │   │  replicas: 2-10 │
                  │  HPA enabled   │   │  HPA enabled    │
                  └────────────────┘   └────────┬────────┘
                                                  │
                          ┌───────────────────────┼─────────────────────┐
                          │                       │                     │
                  ┌───────▼────────┐   ┌──────────▼────────┐  ┌────────▼─────────┐
                  │  xhs-worker    │   │ xhs-celery-worker │  │  xhs-celery-beat │
                  │  (APScheduler) │   │  (Celery worker)  │  │  (Celery beat)   │
                  │  replicas: 1   │   │  replicas: 2-6    │  │  replicas: 1     │
                  └────────────────┘   └───────────────────┘  └──────────────────┘

                  ┌──────────────────┐  ┌──────────────────┐
                  │ xhs-postgres     │  │ xhs-redis        │
                  │ (StatefulSet)    │  │ (StatefulSet)    │
                  │ 20Gi storage     │  │ 5Gi storage      │
                  └──────────────────┘  └──────────────────┘

                  ┌──────────────────────────────────────────────┐
                  │              CronJobs                        │
                  │  - xhs-cookie-refresh  (every 6h)            │
                  │  - xhs-content-publish (every 15min)         │
                  │  - xhs-cleanup-stale   (daily 3am)           │
                  │  - xhs-metrics-rollup  (hourly)              │
                  │  - xhs-db-backup       (daily 2am)           │
                  └──────────────────────────────────────────────┘
```

## Directory Structure

```
k8s/
├── base/                          # Base manifests (Kustomize)
│   ├── 00-namespace.yaml
│   ├── 01-rbac.yaml
│   ├── 02-configmap.yaml
│   ├── 03-secrets.yaml
│   ├── 04-pvc.yaml
│   ├── 10-backend-deployment.yaml
│   ├── 11-frontend-deployment.yaml
│   ├── 12-worker-deployment.yaml
│   ├── 20-services.yaml
│   ├── 30-ingress.yaml
│   ├── 40-hpa.yaml
│   ├── 50-pdb.yaml
│   ├── 60-redis.yaml
│   ├── 61-postgres.yaml
│   ├── 70-networkpolicy.yaml
│   └── kustomization.yaml
├── overlays/
│   ├── dev/
│   └── prod/
├── jobs/
│   └── cronjobs.yaml
└── scripts/
```

## Quick Start

### 1. Deploy to Dev

```bash
# Linux/macOS
./scripts/deploy.sh dev latest

# Windows PowerShell
.\scripts\deploy.ps1 dev latest
```

### 2. Deploy to Production

```bash
./scripts/deploy.sh prod v0.6.3
```

## Operations

### Build

```bash
./scripts/build.sh v0.6.3
docker push ghcr.io/your-org/xhs-saas-backend:v0.6.3
docker push ghcr.io/your-org/xhs-saas-frontend:v0.6.3
```

### Status

```bash
./scripts/status.sh
```

### Logs

```bash
./scripts/logs.sh backend 200
./scripts/logs.sh frontend 200
```

### Rollback

```bash
./scripts/rollback.sh
./scripts/rollback.sh backend
```

### Continuous Reconciliation

Deploy `reconcile.sh` as a Kubernetes Deployment for auto-healing:
- Restart pods in CrashLoopBackOff
- Clean up failed CronJob pods
- Monitor API health

## Security

All pods run with:
- `runAsNonRoot: true`
- `readOnlyRootFilesystem: true`
- `allowPrivilegeEscalation: false`
- `capabilities.drop: [ALL]`
- `seccompProfile: RuntimeDefault`

## CronJobs

| CronJob | Schedule | Purpose |
| --- | --- | --- |
| xhs-cookie-refresh | `0 */6 * * *` | Refresh XHS publisher cookies every 6h |
| xhs-content-publish | `*/15 * * * *` | Run scheduled posts every 15 min |
| xhs-cleanup-stale | `0 3 * * *` | Daily cleanup at 3 AM |
| xhs-metrics-rollup | `0 */1 * * *` | Hourly metrics aggregation |
| xhs-db-backup | `0 2 * * *` | Daily database backup at 2 AM |

## License

MIT