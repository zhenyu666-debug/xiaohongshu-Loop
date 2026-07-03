FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

COPY pbp_api/ ./pbp_api/
COPY data/ ./data/

ENV PBP_API_PORT=8090

EXPOSE 8090

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -fsS http://localhost:8090/healthz || exit 1

CMD ["uvicorn", "pbp_api.main:app", "--host", "0.0.0.0", "--port", "8090"]