#!/usr/bin/env bash
# Show xhs-saas deployment status

set -euo pipefail

NAMESPACE=${NAMESPACE:-"xhs-saas"}

echo "==> Namespace: $NAMESPACE"
echo ""

echo "==> Pods"
kubectl -n $NAMESPACE get pods -o wide
echo ""

echo "==> Services"
kubectl -n $NAMESPACE get svc
echo ""

echo "==> Ingress"
kubectl -n $NAMESPACE get ing
echo ""

echo "==> HPA"
kubectl -n $NAMESPACE get hpa
echo ""

echo "==> PDB"
kubectl -n $NAMESPACE get pdb
echo ""

echo "==> PVC"
kubectl -n $NAMESPACE get pvc
echo ""

echo "==> CronJobs (next 5 schedules)"
kubectl -n $NAMESPACE get cronjobs
echo ""

echo "==> Recent events (last 20)"
kubectl -n $NAMESPACE get events --sort-by='.lastTimestamp' | tail -20
