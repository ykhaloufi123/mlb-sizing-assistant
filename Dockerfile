# Généré par Mistral Craft Table : image utilisée par `agents deploy`.
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY . .
RUN uv sync --no-dev
CMD ["uv", "run", "agents", "run-worker"]
