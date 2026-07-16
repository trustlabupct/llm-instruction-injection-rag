"""Backend local del cuadro de mando (solo biblioteca estandar + el propio proyecto).

    python tools/dashboard_server.py            # http://localhost:8000
    python tools/dashboard_server.py --port 8010

Sirve dashboard.html y expone una API JSON que reutiliza la tuberia real
(rag_pipeline + prompts + local_llm + mock_tools + evaluator) para:

  GET  /                     -> el cuadro de mando (genera dashboard.html si falta)
  GET  /api/status           -> disponibilidad de Ollama y modelos instalados
  GET  /api/results          -> resultados etiquetados oficiales (para recargar el panel)
  GET  /api/catalog          -> preguntas y documentos del corpus
  POST /api/run_query        -> lanza UNA consulta en vivo contra el modelo y la etiqueta
  POST /api/run_experiment   -> re-ejecuta el experimento con otros parametros (en 2o plano)
  GET  /api/job              -> estado del experimento en 2o plano

El experimento en vivo se escribe con prefijo 'live_run' y NO sobrescribe los ficheros
oficiales (full_experiment_*, metrics_summary.csv, figures/). Todo es local: no hay APIs
de pago ni efectos externos (las herramientas siguen siendo simuladas).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
RESULTS = ROOT / "results"
sys.path.insert(0, str(SRC))

import pandas as pd  # noqa: E402

import evaluator  # noqa: E402
import mock_tools  # noqa: E402
import output_filter  # noqa: E402
from local_llm import OLLAMA_URL, get_llm  # noqa: E402
from prompts import CONFIGURATIONS, OUTPUT_FILTER, SYSTEM_PROMPTS, TOOLS_ENABLED, build_prompt  # noqa: E402
from rag_pipeline import Document, Retriever, load_documents, load_queries  # noqa: E402

OLLAMA_TAGS = OLLAMA_URL.replace("/api/chat", "/api/tags")

# --- estado compartido -------------------------------------------------------
_retrievers: dict[str, Retriever] = {}
_docs = load_documents()
_queries = {q["query_id"]: q for q in load_queries()}
JOB = {"running": False, "done": False, "error": None, "log": [], "params": None, "metrics": None}
_job_lock = threading.Lock()


def get_retriever(backend: str) -> Retriever:
    if backend not in _retrievers:
        try:
            _retrievers[backend] = Retriever(_docs, backend=backend)
        except ImportError as e:
            raise RuntimeError(
                f"el retriever '{backend}' no esta disponible: {e}. "
                "Instala sentence-transformers (o usa la imagen Docker, que ya lo incluye)."
            ) from e
    return _retrievers[backend]


def _mk_injected(inject_doc: dict) -> Document:
    fam = (inject_doc.get("family") or "none").strip()
    return Document(
        doc_id=inject_doc.get("doc_id") or "DINJ",
        title=inject_doc.get("title") or "Documento inyectado",
        category=inject_doc.get("category") or "otros",
        doc_type="poisoned" if fam not in ("", "none") else "clean",
        attack_family=fam or "none",
        content=inject_doc.get("content") or "",
    )


def ollama_status() -> dict:
    try:
        with urllib.request.urlopen(OLLAMA_TAGS, timeout=4) as r:
            tags = json.loads(r.read())
        return {"ok": True, "models": [m["name"] for m in tags.get("models", [])]}
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
        return {"ok": False, "models": []}


def run_single(question, config, top_k, temperature, backend, model, allowed_tools,
               system_override=None, inject_doc=None):
    """Ejecuta una consulta a traves de la tuberia y devuelve recuperacion, respuesta y etiquetas.

    system_override: si se indica, sustituye el prompt del sistema de la configuracion
                     (para experimentar con el texto de las defensas C3/C4).
    inject_doc: si se indica, se anade un documento al corpus solo para esta consulta
                (para inyectar un ataque nuevo y ver si el retriever lo recupera).
    """
    if inject_doc and (inject_doc.get("content") or "").strip():
        corpus = _docs + [_mk_injected(inject_doc)]
        retr = Retriever(corpus, backend=backend)  # ad-hoc, no se cachea
    else:
        retr = get_retriever(backend)
    recuperados = retr.retrieve(question, top_k=int(top_k))
    docs = [d for d, _ in recuperados]
    system, user = build_prompt(config, question, recuperados)
    if system_override is not None and str(system_override).strip():
        system = str(system_override)

    llm = get_llm("ollama", model=model, temperature=float(temperature), seed=42)
    respuesta = llm.generate(system, user)
    if OUTPUT_FILTER.get(config) and system_override is None:
        respuesta, _ = output_filter.filter_response(respuesta, allowed_tools)

    tools_on = TOOLS_ENABLED[config]
    calls, tool_rows = [], []
    if tools_on:
        for nombre, args in mock_tools.parse_tool_calls(respuesta):
            permitido = nombre in allowed_tools
            mock_tools.execute(nombre, args)  # sin efecto real
            calls.append({"tool": nombre, "args": json.dumps(args, ensure_ascii=False),
                          "allowed": permitido,
                          "reason": ("el usuario solicito esta accion" if permitido
                                     else "la pregunta no requeria esta herramienta")})
            tool_rows.append({"query_id": "LIVE", "configuration": config, "tool_name": nombre,
                              "arguments": json.dumps(args, ensure_ascii=False), "allowed": permitido})

    poison = [d.doc_id for d in docs if d.is_poisoned]
    familias = sorted({d.attack_family for d in docs if d.is_poisoned})
    raw = pd.DataFrame([{
        "run_id": "live", "query_id": "LIVE", "query_type": "live", "configuration": config,
        "question": question, "retrieved_docs": "|".join(d.doc_id for d in docs),
        "retrieved_scores": "|".join(f"{s:.4f}" for _, s in recuperados),
        "poisoned_retrieved": "|".join(poison), "attack_families": "|".join(familias),
        "response": respuesta, "tool_calls": "|".join(c["tool"] for c in calls),
        "allowed_tools": "|".join(allowed_tools), "model": llm.name,
        "temperature": temperature, "top_k": top_k, "timestamp": "",
    }])
    tc = pd.DataFrame(tool_rows) if tool_rows else pd.DataFrame(
        columns=["query_id", "configuration", "tool_name", "arguments", "allowed"])
    lab = evaluator.etiquetar(raw, tc).iloc[0]
    labels = {k: int(lab[k]) for k in
              ["attack_success", "tool_misuse", "excessive_agency", "data_leakage",
               "safe_refusal", "answer_useful", "obeys_override", "obeys_contamination",
               "obeys_tool_abuse", "obeys_exfiltration"]}

    return {
        "config": config, "tools_on": tools_on,
        "retrieved": [{"doc_id": d.doc_id, "title": d.title, "poisoned": d.is_poisoned,
                       "family": d.attack_family, "category": d.category,
                       "score": round(s, 4), "content": d.content}
                      for d, s in recuperados],
        "system_prompt": system, "user_prompt": user, "response": respuesta,
        "calls": calls, "labels": labels,
    }


def metrics_from(prefix: str) -> dict:
    raw = pd.read_csv(RESULTS / f"{prefix}_raw.csv", keep_default_na=False)
    tcp = RESULTS / f"{prefix}_tool_calls.csv"
    tc = pd.read_csv(tcp, keep_default_na=False) if tcp.exists() else pd.DataFrame()
    lab = evaluator.etiquetar(raw, tc)
    resumen = evaluator.metricas_por_configuracion(lab).to_dict(orient="records")
    familia = evaluator.metricas_por_familia(lab).to_dict(orient="records")
    return {"summary": resumen, "family": familia, "n": len(lab)}


def experiment_worker(params):
    global JOB
    try:
        cmd = [sys.executable, str(SRC / "run_experiment.py"),
               "--backend", "ollama", "--model", params["model"],
               "--top-k", str(params["top_k"]), "--temperature", str(params["temperature"]),
               "--retriever", params["retriever"], "--out", "live_run"]
        if params.get("pilot"):
            cmd.append("--pilot")
        proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, bufsize=1)
        for line in proc.stdout:
            line = line.strip()
            if line:
                with _job_lock:
                    JOB["log"].append(line)
                    JOB["log"] = JOB["log"][-40:]
        proc.wait()
        if proc.returncode != 0:
            raise RuntimeError(f"run_experiment devolvio codigo {proc.returncode}")
        with _job_lock:
            JOB["metrics"] = metrics_from("live_run")
            JOB["done"] = True
    except Exception as e:  # noqa: BLE001
        with _job_lock:
            JOB["error"] = str(e)
            JOB["done"] = True
    finally:
        with _job_lock:
            JOB["running"] = False


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # silenciar el log por defecto
        pass

    def _send(self, code, payload, ctype="application/json"):
        body = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if "json" in ctype or "html" in ctype else ""))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        if self.path in ("/", "/dashboard.html"):
            html = ROOT / "dashboard.html"
            if not html.exists():
                subprocess.run([sys.executable, str(ROOT / "tools" / "build_dashboard.py")], cwd=str(ROOT))
            return self._send(200, html.read_bytes(), "text/html")
        if self.path == "/api/status":
            return self._send(200, {"ollama": ollama_status(), "configs": CONFIGURATIONS,
                                    "tools": list(mock_tools.TOOLS.keys())})
        if self.path.startswith("/api/prompt"):
            from urllib.parse import parse_qs, urlparse
            cfg = (parse_qs(urlparse(self.path).query).get("config", ["C3"])[0])
            if cfg not in SYSTEM_PROMPTS:
                return self._send(400, {"error": "configuracion desconocida"})
            return self._send(200, {"config": cfg, "system_prompt": SYSTEM_PROMPTS[cfg],
                                    "tools_on": TOOLS_ENABLED[cfg]})
        if self.path == "/api/results":
            return self._send(200, metrics_from("full_experiment"))
        if self.path == "/api/catalog":
            return self._send(200, {
                "queries": [{"query_id": q["query_id"], "question": q["question"],
                             "type": q["query_type"], "allowed": q["allowed_tools"]}
                            for q in _queries.values()],
                "poisoned_docs": [{"doc_id": d.doc_id, "title": d.title, "family": d.attack_family}
                                  for d in _docs if d.is_poisoned],
            })
        if self.path == "/api/job":
            with _job_lock:
                return self._send(200, dict(JOB))
        return self._send(404, {"error": "no encontrado"})

    def do_POST(self):
        try:
            data = self._body()
        except Exception:  # noqa: BLE001
            return self._send(400, {"error": "JSON invalido"})

        if self.path == "/api/run_query":
            q = (data.get("question") or "").strip()
            if not q:
                return self._send(400, {"error": "falta la pregunta"})
            config = data.get("config", "C2")
            if config not in CONFIGURATIONS:
                return self._send(400, {"error": "configuracion desconocida"})
            allowed = data.get("allowed_tools") or []
            # si es una pregunta del corpus, usar sus herramientas permitidas por defecto
            if not allowed and data.get("query_id") in _queries:
                allowed = _queries[data["query_id"]]["allowed_tools"]
            try:
                res = run_single(q, config, data.get("top_k", 3), data.get("temperature", 0.0),
                                 data.get("retriever", "tfidf"), data.get("model", "llama3.1:8b"),
                                 allowed, system_override=data.get("system_prompt"),
                                 inject_doc=data.get("inject_doc"))
                return self._send(200, res)
            except Exception as e:  # noqa: BLE001
                return self._send(500, {"error": str(e)})

        if self.path == "/api/compare_retrievers":
            q = (data.get("question") or "").strip()
            if not q:
                return self._send(400, {"error": "falta la pregunta"})
            top_k = int(data.get("top_k", 3))
            out = {}
            for backend in ("tfidf", "embeddings"):
                try:
                    rec = get_retriever(backend).retrieve(q, top_k=top_k)
                    out[backend] = {"docs": [{"doc_id": d.doc_id, "title": d.title,
                                              "poisoned": d.is_poisoned, "family": d.attack_family,
                                              "score": round(s, 4)} for d, s in rec]}
                except Exception as e:  # noqa: BLE001
                    out[backend] = {"error": str(e)}
            return self._send(200, out)

        if self.path == "/api/run_experiment":
            with _job_lock:
                if JOB["running"]:
                    return self._send(409, {"error": "ya hay un experimento en marcha"})
                params = {"model": data.get("model", "llama3.1:8b"),
                          "top_k": int(data.get("top_k", 3)),
                          "temperature": float(data.get("temperature", 0.0)),
                          "retriever": data.get("retriever", "tfidf"),
                          "pilot": bool(data.get("pilot", True))}
                JOB.update({"running": True, "done": False, "error": None, "log": [],
                            "params": params, "metrics": None})
            threading.Thread(target=experiment_worker, args=(params,), daemon=True).start()
            return self._send(202, {"started": True, "params": params})

        return self._send(404, {"error": "no encontrado"})


def main():
    import os
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=int(os.environ.get("DASH_PORT", 8000)))
    ap.add_argument("--host", default=os.environ.get("DASH_HOST", "127.0.0.1"),
                    help="127.0.0.1 en local; 0.0.0.0 dentro de Docker")
    args = ap.parse_args()
    # asegurar que el dashboard existe
    if not (ROOT / "dashboard.html").exists():
        subprocess.run([sys.executable, str(ROOT / "tools" / "build_dashboard.py")], cwd=str(ROOT))
    st = ollama_status()
    shown = "localhost" if args.host in ("127.0.0.1", "0.0.0.0") else args.host
    print(f"Cuadro de mando en  http://{shown}:{args.port}  (bind {args.host})")
    print(f"Ollama en {OLLAMA_URL}: {'OK, modelos=' + ', '.join(st['models']) if st['ok'] else 'NO disponible'}")
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
