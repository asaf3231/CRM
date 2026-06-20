# ReactFirst GTM Engine — Backend (FastAPI) container
# Build context: Backend/   ·   Serves: uvicorn api_server:app
# On Railway: set the service Root Directory to "Backend" (Dockerfile auto-detected).
FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# build-essential covers any source-built wheels; libgomp1 is needed at runtime by
# torch / scikit-learn (pulled in by sentence-transformers / chromadb).
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libgomp1 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install deps first so this layer caches across code changes.
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# App code + the 3 runtime inputs (brands_catalog.csv, contacts.json, gtm_policies.txt)
# + angle_corpus.json. Secrets (.env) and generated dirs are excluded via .dockerignore.
COPY . .

# The host (Railway/Render) injects $PORT; default 8000 for local `docker run`.
ENV PORT=8000
EXPOSE 8000

# ChromaDB persists to ./.chroma at runtime — mount a persistent volume at /app/.chroma
# on the host so the vector store + embedding cache survive restarts.
CMD ["sh", "-c", "uvicorn api_server:app --host 0.0.0.0 --port ${PORT:-8000}"]
