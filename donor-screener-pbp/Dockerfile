FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

COPY pbp_api/ ./pbp_api/
COPY data/ ./data/

EXPOSE 8090

CMD ["uvicorn", "pbp_api.main:app", "--host", "0.0.0.0", "--port", "8090"]