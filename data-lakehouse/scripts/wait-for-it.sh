#!/usr/bin/env bash
# wait-for-it.sh — 等待指定主机:端口就绪后执行命令
# 用法: ./wait-for-it.sh <host:port> <command> [args...]
# 示例: ./wait-for-it.sh localhost:5432 python app.py

set -e

HOST_PORT="$1"
shift
CMD=("$@")

IFS=':' read -r HOST PORT <<< "$HOST_PORT"
PORT="${PORT:-80}"

TIMEOUT="${WAIT_TIMEOUT:-60}"
ELAPSED=0

echo "等待 $HOST:$PORT 就绪 (超时 ${TIMEOUT}s)..."

while [ $ELAPSED -lt $TIMEOUT ]; do
    if nc -z "$HOST" "$PORT" 2>/dev/null; then
        echo "$HOST:$PORT 已就绪"
        break
    fi
    sleep 1
    ELAPSED=$((ELAPSED + 1))
    echo "  ${ELAPSED}s..."
done

if [ $ELAPSED -ge $TIMEOUT ]; then
    echo "ERROR: 等待 $HOST:$PORT 超时" >&2
    exit 1
fi

if [ ${#CMD[@]} -gt 0 ]; then
    exec "${CMD[@]}"
fi
