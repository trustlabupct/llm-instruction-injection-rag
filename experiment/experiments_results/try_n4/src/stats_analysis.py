"""Rigor estadistico sobre los resultados etiquetados.

    python src/stats_analysis.py

Con n pequeno (27 preguntas con documento contaminado por configuracion) las tasas son
estimaciones puntuales. Este modulo anade:

  1. Intervalos de confianza del 95 % por bootstrap para ASR (sobre las ejecuciones con
     documento contaminado) y para la utilidad AU (sobre las 32), por configuracion.
  2. Test de McNemar (exacto, binomial) entre configuraciones adyacentes, emparejando por
     pregunta el resultado de attack_success. Responde a si las diferencias de ASR entre
     configuraciones son estadisticamente significativas y no ruido.

Escribe results/metrics_ci.csv y results/mcnemar_tests.csv.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
CONFIGS = ["C1", "C2", "C3", "C4", "C5"]
RNG = np.random.default_rng(42)
B = 10000


def boot_ci(valores: np.ndarray, iters: int = B) -> tuple[float, float]:
    if len(valores) == 0:
        return (0.0, 0.0)
    idx = RNG.integers(0, len(valores), size=(iters, len(valores)))
    medias = valores[idx].mean(axis=1)
    return float(np.percentile(medias, 2.5)), float(np.percentile(medias, 97.5))


def mcnemar_exacto(a: np.ndarray, b: np.ndarray) -> tuple[int, int, float]:
    """a, b: vectores binarios emparejados (misma pregunta). Devuelve (b01, b10, p_valor)."""
    solo_a = int(np.sum((a == 1) & (b == 0)))   # A obedece, B no
    solo_b = int(np.sum((a == 0) & (b == 1)))   # B obedece, A no
    n = solo_a + solo_b
    if n == 0:
        return solo_a, solo_b, 1.0
    p = binomtest(min(solo_a, solo_b), n, 0.5, alternative="two-sided").pvalue
    return solo_a, solo_b, float(p)


def main() -> None:
    df = pd.read_csv(RESULTS / "full_experiment_labelled.csv", keep_default_na=False)
    df["poison"] = df["poisoned_retrieved"].astype(str).str.len() > 0

    filas = []
    for c in CONFIGS:
        sub = df[df["configuration"] == c]
        pois = sub[sub["poison"]]
        asr = pois["attack_success"].mean()
        au = sub["answer_useful"].mean()
        asr_lo, asr_hi = boot_ci(pois["attack_success"].to_numpy())
        au_lo, au_hi = boot_ci(sub["answer_useful"].to_numpy())
        filas.append({"configuration": c, "n_poison": len(pois), "n_total": len(sub),
                      "asr": asr, "asr_ci_low": asr_lo, "asr_ci_high": asr_hi,
                      "au": au, "au_ci_low": au_lo, "au_ci_high": au_hi})
    ci = pd.DataFrame(filas)
    ci.to_csv(RESULTS / "metrics_ci.csv", index=False)

    def pct(x):
        return f"{x * 100:.1f}".replace(".", ",")
    print("=== ASR y AU con IC 95 % (bootstrap, 10000 remuestreos) ===")
    for _, r in ci.iterrows():
        print(f"  {r.configuration}: ASR {pct(r.asr)} % [IC95 {pct(r.asr_ci_low)}–{pct(r.asr_ci_high)}]   "
              f"AU {pct(r.au)} % [IC95 {pct(r.au_ci_low)}–{pct(r.au_ci_high)}]")

    # McNemar entre configuraciones adyacentes (attack_success emparejado por pregunta con veneno)
    piv = (df[df["poison"]].pivot_table(index="query_id", columns="configuration",
                                        values="attack_success", aggfunc="first"))
    pares = [("C1", "C2"), ("C2", "C3"), ("C3", "C4"), ("C4", "C5"), ("C3", "C5")]
    filas_m = []
    print("\n=== McNemar (exacto) entre configuraciones, ASR emparejado por pregunta ===")
    for a, b in pares:
        va, vb = piv[a].to_numpy(), piv[b].to_numpy()
        b01, b10, p = mcnemar_exacto(va, vb)
        sig = "significativo" if p < 0.05 else "no significativo"
        filas_m.append({"comparacion": f"{a} vs {b}", "solo_" + a: b01, "solo_" + b: b10,
                        "p_value": p, "significativo_0.05": p < 0.05})
        print(f"  {a} vs {b}: {a}-solo={b01}, {b}-solo={b10}, p={p:.4f}  ({sig})")
    pd.DataFrame(filas_m).to_csv(RESULTS / "mcnemar_tests.csv", index=False)
    print(f"\n-> {RESULTS/'metrics_ci.csv'}\n-> {RESULTS/'mcnemar_tests.csv'}")


if __name__ == "__main__":
    main()
