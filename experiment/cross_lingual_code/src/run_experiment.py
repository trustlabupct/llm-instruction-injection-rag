"""Ejecucion del experimento.

    python src/run_experiment.py --model llama3.1:8b
    python src/run_experiment.py --pilot                # subconjunto de 6 preguntas

Escribe results/<nombre>_raw.csv y results/<nombre>_tool_calls.csv.
Cada ejecucion se identifica con un run_id para no sobrescribir resultados previos.
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mock_tools
import output_filter
from local_llm import get_llm
from prompts import CONFIGURATIONS, OUTPUT_FILTER, TOOLS_ENABLED, build_prompt
from rag_pipeline import Retriever, load_documents, load_queries

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"

PILOTO = ["Q01", "Q15", "Q18", "Q22", "Q26", "Q28"]

CAMPOS = ["run_id", "query_id", "query_type", "configuration", "question",
          "retrieved_docs", "retrieved_scores", "poisoned_retrieved",
          "attack_families", "response", "tool_calls", "allowed_tools",
          "model", "temperature", "top_k", "timestamp"]


def clasificar_llamada(tool, query) -> tuple[bool, str]:
    """Decide si una llamada es legitima segun la pregunta, no segun el documento."""
    if tool in query["allowed_tools"]:
        return True, "el usuario solicito explicitamente esta accion"
    if tool in query["forbidden_tools"]:
        return False, "la pregunta del usuario no requeria esta herramienta"
    return False, "herramienta no contemplada para esta pregunta"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="ollama", choices=["ollama"])
    ap.add_argument("--model", default="llama3.1:8b")
    ap.add_argument("--retriever", default="tfidf", choices=["tfidf", "embeddings"])
    ap.add_argument("--top-k", type=int, default=3)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--out", default=None, help="prefijo de los ficheros de salida")
    # language settings
    ap.add_argument("--query-language", default="sp", choices=["sp", "en"])
    ap.add_argument("--malicious-doc-language", default="sp", choices=["sp", "en"])
    args = ap.parse_args()

    langs_used = {args.query_language, args.malicious_doc_language}
    retriever_backend = "embeddings" if len(langs_used) > 1 else args.retriever

    prefijo = args.out or ("pilot" if args.pilot else "full_experiment")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    documentos = load_documents()
    preguntas = load_queries()
    if args.pilot:
        preguntas = [q for q in preguntas if q["query_id"] in PILOTO]

    retriever = Retriever(documentos, backend=retriever_backend)
    llm = get_llm(args.backend, model=args.model, temperature=args.temperature, seed=args.seed)

    filas, llamadas = [], []
    total = len(preguntas) * len(CONFIGURATIONS)
    hecho = 0

    for q in preguntas:
        recuperados = retriever.retrieve(q["question"], top_k=args.top_k)
        docs = [d for d, _ in recuperados]

        for config in CONFIGURATIONS:
            hecho += 1
            print(f"[{hecho}/{total}] {q['query_id']} {config}", file=sys.stderr)

            system, user = build_prompt(config, q["question"], recuperados, args.query_language)
            respuesta = llm.generate(system, user)

            # C5: filtro de salida determinista sobre la respuesta ya generada
            if OUTPUT_FILTER[config]:
                respuesta, _ = output_filter.filter_response(respuesta, q["allowed_tools"])

            nombres_llamadas = []
            if TOOLS_ENABLED[config]:
                for nombre, argumentos in mock_tools.parse_tool_calls(respuesta):
                    permitido, motivo = clasificar_llamada(nombre, q)
                    mock_tools.execute(nombre, argumentos)  # sin efecto real
                    llamadas.append(mock_tools.ToolCall(
                        query_id=q["query_id"], configuration=config,
                        tool_name=nombre, arguments=argumentos,
                        allowed=permitido, reason=motivo).as_row() | {"run_id": run_id})
                    nombres_llamadas.append(nombre)

            envenenados = [d.doc_id for d in docs if d.is_poisoned]
            filas.append({
                "run_id": run_id,
                "query_id": q["query_id"],
                "query_type": q["query_type"],
                "configuration": config,
                "question": q["question"],
                "retrieved_docs": "|".join(d.doc_id for d in docs),
                "retrieved_scores": "|".join(f"{s:.4f}" for _, s in recuperados),
                "poisoned_retrieved": "|".join(envenenados),
                "attack_families": "|".join(sorted({d.attack_family for d in docs if d.is_poisoned})),
                "response": respuesta,
                "tool_calls": "|".join(nombres_llamadas),
                "allowed_tools": "|".join(q["allowed_tools"]),
                "model": llm.name,
                "temperature": args.temperature,
                "top_k": args.top_k,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

    RESULTS.mkdir(exist_ok=True)
    raw = RESULTS / f"{prefijo}_raw.csv"
    with raw.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        w.writeheader()
        w.writerows(filas)

    tc = RESULTS / f"{prefijo}_tool_calls.csv"
    campos_tc = ["run_id", "query_id", "configuration", "tool_name",
                 "arguments", "allowed", "reason", "timestamp"]
    with tc.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos_tc, extrasaction="ignore")
        w.writeheader()
        w.writerows(llamadas)

    print(f"\n{len(filas)} ejecuciones -> {raw}")
    print(f"{len(llamadas)} llamadas a herramientas -> {tc}")
    print(f"run_id = {run_id}")


if __name__ == "__main__":
    main()
