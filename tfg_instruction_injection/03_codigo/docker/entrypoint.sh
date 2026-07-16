#!/usr/bin/env bash
# Arranca el cuadro de mando de inmediato y descarga el modelo en segundo plano,
# de modo que el panel es accesible al instante (las vistas estáticas funcionan sin
# modelo; el modo en vivo se activa en cuanto termina la descarga).
set -e

OLLAMA_URL="${OLLAMA_URL:-http://ollama:11434/api/chat}"
BASE="${OLLAMA_URL%/api/chat}"
MODEL="${OLLAMA_MODEL:-llama3.1:8b}"

prepare_model() {
  echo "[entrypoint] esperando a Ollama en ${BASE} ..."
  for i in $(seq 1 90); do
    curl -sf "${BASE}/api/tags" >/dev/null 2>&1 && break
    sleep 2
  done
  if curl -sf "${BASE}/api/tags" 2>/dev/null | grep -q "\"${MODEL}\""; then
    echo "[entrypoint] modelo ${MODEL} ya presente."
  else
    echo "[entrypoint] descargando modelo ${MODEL} en segundo plano (~5 GB la primera vez)..."
    curl -s "${BASE}/api/pull" -d "{\"name\":\"${MODEL}\"}" >/dev/null \
      && echo "[entrypoint] modelo ${MODEL} listo." \
      || echo "[entrypoint] AVISO: no se pudo descargar el modelo; el modo en vivo no estará disponible."
  fi
}

# preparar el modelo sin bloquear el arranque del panel
prepare_model &

echo "[entrypoint] arrancando el cuadro de mando en :${DASH_PORT:-8000}"
exec python tools/dashboard_server.py --host "${DASH_HOST:-0.0.0.0}" --port "${DASH_PORT:-8000}"
