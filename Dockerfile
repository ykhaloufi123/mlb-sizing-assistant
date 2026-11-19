# Généré par Mistral Craft Table : image utilisée par `agents deploy`.
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY . .
RUN uv sync --no-dev
# Instance dédiée : un déploiement géré ne lit pas votre shell, l'adresse est donc fixée ici.
ENV MISTRAL_API_URL=https://api.7c746bb36ad3.dc.mistral.ai \
    AGENTS_SDK_DEPLOY_CONTROL_PLANE_URL=https://api.7c746bb36ad3.dc.mistral.ai/v2/agents
CMD ["uv", "run", "agents", "run-worker"]
