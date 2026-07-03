FROM python:3.11-slim

WORKDIR /app

# System deps for Playwright (browser binaries are downloaded at runtime
# via `playwright install`; the slim image still needs the basics)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Install Python deps first for better layer caching
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

# Copy app code (and built console)
COPY app/ ./app/
COPY web/console/dist/ ./web/console/dist/
COPY scripts/ ./scripts/
COPY data/ ./data/

ENV APP_HOST=0.0.0.0 APP_PORT=8080
ENV PBP_API_URL=http://pbp-api:8090
ENV LAKEHOUSE_API_URL=http://lakehouse-api:8091

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8080/api/healthz || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]