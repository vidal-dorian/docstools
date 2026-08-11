# Image de service pour l'API DocsTools (US-050).
# Voir docs/specification.md, section 8 : lecture seule sur index.sqlite,
# aucun volume en écriture requis.

FROM python:3.12-slim

WORKDIR /app

# Versions alignées sur pyproject.toml [project.dependencies].
RUN pip install --no-cache-dir "fastapi>=0.115" "uvicorn[standard]>=0.32"

COPY api/ ./api/

ENV DOCSTOOLS_DB_PATH=/data/index.sqlite

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
