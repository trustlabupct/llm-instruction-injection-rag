"""Statistical rigor over the labeled results.

    python src/stats_analysis.py

With a small n (27 questions with a poisoned document, due to configuration) the rates are
point estimates. This module adds:

  1. 95% bootstrap confidence intervals for ASR (over runs with a poisoned document) and
     for usefulness AU (over the 32), per configuration.
  2. McNemar's test (exact, binomial) between adjacent configurations, pairing by question
     the attack_success outcome. Answers whether the ASR differences between configurations
     are statistically significant and not noise.

Writes results/metrics_ci.csv and results/mcnemar_tests.csv.
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


def boot_ci(values: np.ndarray, iters: int = B) -> tuple[float, float]:
    if len(values) == 0:
        return (0.0, 0.0)
    idx = RNG.integers(0, len(values), size=(iters, len(values)))
    means = values[idx].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def mcnemar_exact(a: np.ndarray, b: np.ndarray) -> tuple[int, int, float]:
    """a, b: paired binary vectors (same question). Returns (b01, b10, p_value)."""
    only_a = int(np.sum((a == 1) & (b == 0)))   # A obeys, B does not
    only_b = int(np.sum((a == 0) & (b == 1)))   # B obeys, A does not
    n = only_a + only_b
    if n == 0:
        return only_a, only_b, 1.0
    p = binomtest(min(only_a, only_b), n, 0.5, alternative="two-sided").pvalue
    return only_a, only_b, float(p)


def main() -> None:
    df = pd.read_csv(RESULTS / "full_experiment_labelled.csv", keep_default_na=False)
    df["poison"] = df["poisoned_retrieved"].astype(str).str.len() > 0

    rows = []
    for c in CONFIGS:
        sub = df[df["configuration"] == c]
        poison = sub[sub["poison"]]
        asr = poison["attack_success"].mean()
        au = sub["answer_useful"].mean()
        asr_lo, asr_hi = boot_ci(poison["attack_success"].to_numpy())
        au_lo, au_hi = boot_ci(sub["answer_useful"].to_numpy())
        rows.append({"configuration": c, "n_poison": len(poison), "n_total": len(sub),
                      "asr": asr, "asr_ci_low": asr_lo, "asr_ci_high": asr_hi,
                      "au": au, "au_ci_low": au_lo, "au_ci_high": au_hi})
    ci = pd.DataFrame(rows)
    ci.to_csv(RESULTS / "metrics_ci.csv", index=False)

    def pct(x):
        return f"{x * 100:.1f}"
    print("=== ASR and AU with 95% CI (bootstrap, 10000 resamples) ===")
    for _, r in ci.iterrows():
        print(f"  {r.configuration}: ASR {pct(r.asr)}% [95%CI {pct(r.asr_ci_low)}-{pct(r.asr_ci_high)}]   "
              f"AU {pct(r.au)}% [95%CI {pct(r.au_ci_low)}-{pct(r.au_ci_high)}]")

    # McNemar between adjacent configurations (attack_success paired by question with poison)
    piv = (df[df["poison"]].pivot_table(index="query_id", columns="configuration",
                                        values="attack_success", aggfunc="first"))
    pairs = [("C1", "C2"), ("C2", "C3"), ("C3", "C4"), ("C4", "C5"), ("C3", "C5")]
    rows_m = []
    print("\n=== McNemar (exact) between configurations, ASR paired by question ===")
    for a, b in pairs:
        va, vb = piv[a].to_numpy(), piv[b].to_numpy()
        b01, b10, p = mcnemar_exact(va, vb)
        sig = "significant" if p < 0.05 else "not significant"
        rows_m.append({"comparison": f"{a} vs {b}", "only_" + a: b01, "only_" + b: b10,
                        "p_value": p, "significant_0.05": p < 0.05})
        print(f"  {a} vs {b}: {a}-only={b01}, {b}-only={b10}, p={p:.4f}  ({sig})")
    pd.DataFrame(rows_m).to_csv(RESULTS / "mcnemar_tests.csv", index=False)
    print(f"\n-> {RESULTS/'metrics_ci.csv'}\n-> {RESULTS/'mcnemar_tests.csv'}")


if __name__ == "__main__":
    main()
