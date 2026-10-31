from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"
DASHBOARD = ROOT / "dashboard.html"
RUNS = ROOT / "runs"

DATA_FILES = ["documents.csv", "test_queries.csv"]
RESULTS_FILES = [
    "full_experiment_raw.csv",
    "full_experiment_tool_calls.csv",
    "full_experiment_labelled.csv",
    "metrics_summary.csv",
    "metrics_by_attack_family.csv",
]
FIGURE_FILES = [
    "attack_success_by_configuration.png",
    "tool_misuse_by_configuration.png",
    "answer_utility_by_configuration.png",
]


# --------------------------------------------------------------------------
# Small helpers to prompt the user in the terminal
# --------------------------------------------------------------------------

def ask(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    while True:
        val = input(f"{prompt}{suffix}: ").strip()
        if not val and default is not None:
            return default
        if val:
            return val
        print("  -> a value is required.")


def ask_choice(prompt: str, choices: list[str], default: str | None = None) -> str:
    choices_str = "/".join(choices)
    while True:
        val = ask(f"{prompt} ({choices_str})", default)
        if val in choices:
            return val
        print(f"  -> invalid value, choose one of: {choices_str}")


def ask_int(prompt: str, default: int | None = None, minimum: int = 1) -> int:
    default_str = str(default) if default is not None else None
    while True:
        val = ask(prompt, default_str)
        try:
            n = int(val)
            if n < minimum:
                raise ValueError
            return n
        except ValueError:
            print(f"  -> enter an integer >= {minimum}.")


# --------------------------------------------------------------------------
# Collect configurations from the user
# --------------------------------------------------------------------------

def collect_configs() -> tuple[list[dict], bool]:
    print("=== Test configuration ===")
    n = ask_int("How many test configurations do you want to run?", default=1)

    configs = []
    for i in range(1, n + 1):
        print(f"\n--- Configuration {i}/{n} ---")
        model = ask("Ollama model to use", default="llama3.1:8b")
        query = ask_choice("User query language", ["en", "sp"], default="sp")
        malicious = ask_choice("Malicious document language", ["en", "sp"], default="sp")
        backend = ask("Backend", default="ollama")
        repeats = ask_int(f"How many repetitions for configuration {i}?", default=1)
        configs.append({
            "model": model, "query": query, "malicious": malicious,
            "backend": backend, "repeats": repeats,
        })

    print()
    build_dashboard = ask_choice("Build dashboard.html on every run?", ["y", "n"], default="y") == "y"

    return configs, build_dashboard


# --------------------------------------------------------------------------
# Pipeline execution + archiving
# --------------------------------------------------------------------------

def sh(cmd: list[str]) -> None:
    print(f"\n$ {' '.join(cmd)}")
    subprocess.run(cmd, check=True, cwd=ROOT)


def safe_name(s: str) -> str:
    return s.replace(":", "-").replace("/", "-").replace(" ", "_")


def archive(model: str, query: str, malicious: str, rep: int | None = None, total_reps: int | None = None) -> Path:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    rep_tag = f"_rep{rep}of{total_reps}" if total_reps and total_reps > 1 else ""
    dest = RUNS / f"{safe_name(model)}_q-{query}_m-{malicious}"
    (dest / "data").mkdir(parents=True, exist_ok=True)
    (dest / "results").mkdir(parents=True, exist_ok=True)
    (dest / "figures").mkdir(parents=True, exist_ok=True)

    for name in DATA_FILES:
        src = DATA / name
        if src.exists():
            shutil.move(str(src), str(dest / "data" / name))

    for name in RESULTS_FILES:
        src = RESULTS / name
        if src.exists():
            shutil.move(str(src), str(dest / "results" / name))

    for name in FIGURE_FILES:
        src = FIGURES / name
        if src.exists():
            shutil.move(str(src), str(dest / "figures" / name))

    if DASHBOARD.exists():
        shutil.move(str(DASHBOARD), str(dest / "dashboard.html"))

    print(f"-> results archived in {dest}")
    return dest


def run_once(cfg: dict, build_dashboard: bool, rep: int | None = None, total_reps: int | None = None) -> None:
    sh([sys.executable, "data/build_dataset.py",
        "--query-language", cfg["query"],
        "--malicious_doc-language", cfg["malicious"]])

    sh([sys.executable, "src/run_experiment.py",
        "--backend", cfg["backend"], "--model", cfg["model"],
        "--query-language", cfg["query"],
        "--malicious-doc-language", cfg["malicious"]])

    sh([sys.executable, "src/evaluator.py"])

    if build_dashboard:
        sh([sys.executable, "tools/build_dashboard.py"])

    archive(cfg["model"], cfg["query"], cfg["malicious"], rep, total_reps)


def main() -> None:
    configs, build_dashboard = collect_configs()

    total_runs = sum(c["repeats"] for c in configs)
    print(f"\n{len(configs)} configuration(s), {total_runs} run(s) in total.")
    if ask_choice("Start now?", ["y", "n"], default="y") == "n":
        print("Cancelled.")
        return

    run_count = 0
    failures = []
    for ci, cfg in enumerate(configs, 1):
        for rep in range(1, cfg["repeats"] + 1):
            run_count += 1
            print(f"\n{'=' * 70}")
            print(f"[{run_count}/{total_runs}] config {ci}/{len(configs)} - "
                  f"model={cfg['model']} query={cfg['query']} malicious={cfg['malicious']} "
                  f"(repetition {rep}/{cfg['repeats']})")
            print("=" * 70)
            try:
                run_once(cfg, build_dashboard, rep, cfg["repeats"])
            except subprocess.CalledProcessError as e:
                print(f"!! run failed ({e}), moving on to the next one.", file=sys.stderr)
                failures.append((cfg, rep))

    print(f"\n{run_count - len(failures)}/{run_count} run(s) succeeded.")
    if failures:
        print(f"{len(failures)} failure(s):")
        for cfg, rep in failures:
            print(f"  - model={cfg['model']} query={cfg['query']} malicious={cfg['malicious']} rep={rep}")
        sys.exit(1)


if __name__ == "__main__":
    main()