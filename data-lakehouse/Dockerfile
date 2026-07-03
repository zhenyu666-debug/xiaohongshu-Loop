FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

COPY lakehouse_api/ ./lakehouse_api/

ENV TRINO_HOST=""
ENV TRINO_PORT=8080

EXPOSE 8091

CMD ["uvicorn", "lakehouse_api.main:app", "--host", "0.0.0.0", "--port", "8091"]


