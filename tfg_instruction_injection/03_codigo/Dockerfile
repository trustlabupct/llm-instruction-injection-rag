# Imagen del cuadro de mando / banco de pruebas.
# El modelo LLM corre en un contenedor aparte (ollama/ollama); ver docker-compose.yml.
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.hfcache \
    DASH_HOST=0.0.0.0 \
    DASH_PORT=8000 \
    OLLAMA_URL=http://ollama:11434/api/chat \
    OLLAMA_MODEL=llama3.1:8b

# curl para el entrypoint (espera + pull); libgomp1 para torch (embeddings).
RUN apt-get update && apt-get install -y --no-install-recommends curl libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Dependencias del proyecto + retriever por embeddings (torch CPU, sin CUDA).
COPY requirements.txt .
RUN pip install -r requirements.txt \
    && pip install torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install "sentence-transformers>=2.7"

# Pre-descarga del modelo de embeddings para que el contenedor sea autónomo
# (no fatal: si no hay red en build, se descargará en el primer uso).
RUN python -c "from sentence_transformers import SentenceTransformer; \
SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')" \
    || echo "aviso: modelo de embeddings no precargado en build"

COPY . .
RUN chmod +x docker/entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["docker/entrypoint.sh"]
