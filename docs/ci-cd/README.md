# K8s CI/CD Setup

The `k8s-deploy.yml` workflow file is stored in this directory rather than
`.github/workflows/` because the GitHub OAuth scope used for automated pushes
does not include the `workflow` scope, which is required to push workflow files.

## To enable CI/CD:

1. **Add the workflow file** to `.github/workflows/k8s-deploy.yml`:
   ```bash
   cp docs/ci-cd/k8s-deploy.yml .github/workflows/k8s-deploy.yml
   git add .github/workflows/k8s-deploy.yml
   git commit -m "ci: enable K8s deploy workflow"
   git push
   ```
   (Requires a push with `workflow` scope, e.g. from GitHub UI or with a
   personal access token that includes `workflow`.)

2. **Configure GitHub Secrets**:
   - `KUBE_CONFIG_DEV` - base64-encoded kubeconfig for dev cluster
   - `KUBE_CONFIG_PROD` - base64-encoded kubeconfig for prod cluster

3. **Build & push images**:
   - Images are auto-built on push to `main` and tags
   - Pushed to `ghcr.io/${{ github.repository }}/xhs-saas-backend` and `xhs-saas-frontend`

4. **Auto-deploy**:
   - Push to `main` → dev cluster (using `latest` tag)
   - Push tag `v*` → prod cluster (using version tag)

## Workflow Overview

The workflow has 4 jobs:
1. **test** - Run pytest on the backend
2. **build-backend** - Build and push backend Docker image
3. **build-frontend** - Build and push frontend Docker image
4. **deploy-dev** - Deploy to dev K8s cluster (main branch)
5. **deploy-prod** - Deploy to prod K8s cluster (v* tags, with environment approval)

See `k8s-deploy.yml` in this directory for the full configuration.
