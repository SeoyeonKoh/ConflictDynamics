"""CRAFT scoring for finished runs. Reads a corpus, never the engine.

The simulation does not know how conflictual it is: generation and measurement stay
separate so the scorer can be replaced without re-running any simulation.

    uv run --extra score conflict-score runs/llm-rr6
"""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

SCHEMA_VERSION = 1
DEFAULT_WEIGHTS = "craft-wiki-finetuned"


def derive_metrics(series: list[dict], threshold: float) -> dict:
    """Summarise a p(t) series the way section 6.1 of the design defines it.

    `series` holds one row per utterance in conversation order, each with an `id`,
    a `timestamp` tick and a CRAFT probability `p`.
    """
    if not series:
        raise ValueError("Cannot summarise an empty forecast series")
    probs = [row["p"] for row in series]
    peak = max(range(len(probs)), key=probs.__getitem__)

    rises = [(probs[i] - probs[i - 1], i) for i in range(1, len(probs))]
    steepest_rise, steepest_at = max(rises, default=(0.0, peak))

    crossings = [index for index, value in enumerate(probs) if value >= threshold]
    horizon = crossings[0] if crossings else None

    return {
        "n_utterances": len(series),
        "decision_threshold": threshold,
        "max_p": probs[peak],
        "max_p_at": {"index": peak, "id": series[peak]["id"], "tick": series[peak]["timestamp"]},
        # dp/dt over the utterance sequence, not wall-clock: the largest single step up.
        "max_dp": steepest_rise,
        "max_dp_at": {
            "index": steepest_at,
            "id": series[steepest_at]["id"],
            "tick": series[steepest_at]["timestamp"],
        },
        "escalated": horizon is not None,
        # The turn where escalation is first forecast, or None when it never is.
        "forecast_horizon": (
            None
            if horizon is None
            else {
                "index": horizon,
                "id": series[horizon]["id"],
                "tick": series[horizon]["timestamp"],
            }
        ),
        "final_p": probs[-1],
    }


def order_series(series: list[dict], ordered_ids: list[str]) -> list[dict]:
    """Restore corpus order. Sorting by id is wrong: "sim:10" precedes "sim:2" lexically."""
    rank = {utterance_id: index for index, utterance_id in enumerate(ordered_ids)}
    return sorted(series, key=lambda row: rank.get(row["id"], len(rank)))


def read_utterance_order(corpus_dir: Path) -> list[str]:
    lines = (corpus_dir / "utterances.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line)["id"] for line in lines if line.strip()]


def forecast_corpus(corpus_dir: Path, weights: str = DEFAULT_WEIGHTS, device: str = "cpu") -> dict:
    """Run CRAFT over one corpus and return its p(t) series plus provenance."""
    import importlib.metadata as metadata

    import torch  # noqa: F401  CRAFT is only exported once torch is imported.
    from convokit import Corpus, Forecaster
    from convokit.forecaster.CRAFTModel import CRAFTModel

    corpus = Corpus(filename=str(corpus_dir))
    model = CRAFTModel(initial_weights=weights, torch_device=device)
    # The labeler is only read when fitting; scoring uses the published weights as they are.
    scored = Forecaster(forecaster_model=model, labeler=lambda _convo: 0).transform(corpus)

    series = [
        {
            "id": utterance.id,
            "speaker": utterance.speaker.id,
            "timestamp": utterance.timestamp,
            "p": utterance.meta.get("forecast_prob"),
            "forecast": utterance.meta.get("forecast"),
        }
        for utterance in scored.iter_utterances()
    ]
    series = order_series(
        [row for row in series if row["p"] is not None], read_utterance_order(corpus_dir)
    )
    return {
        "series": series,
        "model": {
            "forecaster": "CRAFT",
            "weights": weights,
            "device": device,
            "convokit_version": metadata.version("convokit"),
        },
        "threshold": model._decision_threshold,
    }


def score_run(run_dir: Path, weights: str = DEFAULT_WEIGHTS, device: str = "cpu") -> dict:
    """Score one run directory and write scores.json beside its corpus."""
    corpus_dir = run_dir / "corpus"
    if not (corpus_dir / "utterances.jsonl").is_file():
        raise ValueError(f"No corpus to score in {run_dir}")
    forecast = forecast_corpus(corpus_dir, weights=weights, device=device)
    report = {
        "schema_version": SCHEMA_VERSION,
        "scored_at": datetime.now(UTC).isoformat(),
        "run": str(run_dir),
        "model": forecast["model"],
        "metrics": derive_metrics(forecast["series"], forecast["threshold"]),
        "series": forecast["series"],
    }
    (run_dir / "scores.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return report


def find_runs(root: Path) -> list[Path]:
    """Run directories, not the corpus directories inside them."""
    return sorted(path.parent.parent for path in root.rglob("corpus/utterances.jsonl"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Score finished runs with the CRAFT forecaster.")
    parser.add_argument("runs", nargs="*", type=Path, help="run directories holding a corpus/")
    parser.add_argument("--all", type=Path, metavar="ROOT", help="score every run under ROOT")
    parser.add_argument("--weights", default=DEFAULT_WEIGHTS)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    targets = list(args.runs) + (find_runs(args.all) if args.all else [])
    if not targets:
        raise SystemExit("error: name at least one run directory, or pass --all runs")

    for run_dir in targets:
        try:
            report = score_run(run_dir, weights=args.weights, device=args.device)
        except (OSError, ValueError) as exc:
            print(f"skipped {run_dir}: {exc}")
            continue
        metrics = report["metrics"]
        horizon = metrics["forecast_horizon"]
        reached = "none" if horizon is None else "tick {}".format(horizon["tick"])
        print(
            f"{run_dir}: max p={metrics['max_p']:.4f} at tick {metrics['max_p_at']['tick']}, "
            f"max dp={metrics['max_dp']:+.4f}, horizon={reached} "
            f"(threshold {metrics['decision_threshold']})"
        )


if __name__ == "__main__":
    main()
