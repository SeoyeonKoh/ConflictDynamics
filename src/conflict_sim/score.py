"""CRAFT scoring for finished runs and live public snapshots, never the engine.

The simulation does not know how conflictual it is: generation and measurement stay
separate so the scorer can be replaced without re-running any simulation.

    uv run --extra score conflict-score runs/llm-rr6
"""

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from time import sleep

SCHEMA_VERSION = 2
DEFAULT_WEIGHTS = "craft-wiki-finetuned"
CORPUS_FILES = (
    "utterances.jsonl",
    "speakers.json",
    "conversations.json",
    "corpus.json",
    "index.json",
    "run.json",
)
# The wiki wrapper also keeps its seed and decision log beside the corpus (plan §1-11).
WIKI_CORPUS_FILES = CORPUS_FILES + ("decisions.jsonl", "seed.json")


def derive_metrics(series: list[dict], threshold: float) -> dict:
    """Summarise a p(t) series the way section 6.1 of the design defines it.

    `series` holds one row per utterance in conversation order, each with an `id`,
    a `timestamp` tick and a CRAFT probability `p`. Changes are signed differences
    between adjacent utterances, including those in the same tick. Threshold
    exceedance means `p > threshold`, matching CRAFT; it is not an observed attack.
    """
    if not series:
        raise ValueError("Cannot summarise an empty forecast series")
    probs = [row["p"] for row in series]
    peak = max(range(len(probs)), key=probs.__getitem__)

    changes = [(probs[i] - probs[i - 1], i) for i in range(1, len(probs))]
    max_change, change_at = max(changes, default=(0.0, peak))

    first_crossing = next((i for i, value in enumerate(probs) if value > threshold), None)

    return {
        "n_utterances": len(series),
        "decision_threshold": threshold,
        "max_p": probs[peak],
        "max_p_at": {"index": peak, "id": series[peak]["id"], "tick": series[peak]["timestamp"]},
        # A falling series has a negative maximum; a single utterance uses zero.
        "max_delta_p": max_change,
        "max_delta_p_at": {
            "index": change_at,
            "id": series[change_at]["id"],
            "tick": series[change_at]["timestamp"],
        },
        "threshold_exceeded": first_crossing is not None,
        # First observed exceedance, not lead time to a labeled future event.
        "first_threshold_crossing": (
            None
            if first_crossing is None
            else {
                "index": first_crossing,
                "id": series[first_crossing]["id"],
                "tick": series[first_crossing]["timestamp"],
            }
        ),
        "final_p": probs[-1],
    }


def order_series(series: list[dict], ordered_ids: list[str]) -> list[dict]:
    """Require exactly one valid forecast per utterance, then restore corpus order."""
    rank = {utterance_id: index for index, utterance_id in enumerate(ordered_ids)}
    ids = [row["id"] for row in series]
    if len(rank) != len(ordered_ids) or len(ids) != len(set(ids)) or set(ids) != set(rank):
        raise ValueError(
            "Forecast IDs must match the corpus exactly, without duplicates or omissions"
        )
    if any(
        not isinstance(row.get("p"), (int, float))
        or not math.isfinite(row["p"])
        or not 0 <= row["p"] <= 1
        for row in series
    ):
        raise ValueError("Every utterance needs a finite forecast probability in [0, 1]")
    return sorted(series, key=lambda row: rank[row["id"]])


def read_utterance_order(corpus_dir: Path) -> list[str]:
    return [row["id"] for row in _read_rows(corpus_dir)]


def read_sessions(corpus_dir: Path) -> dict[str, list[str]]:
    """Utterance ids per conversation, in corpus order. Rows without a conversation form one."""
    sessions: dict[str, list[str]] = {}
    rows = _read_rows(corpus_dir)
    for row in rows:
        sessions.setdefault(row.get("conversation_id", rows[0]["id"]), []).append(row["id"])
    return sessions


def _read_rows(corpus_dir: Path) -> list[dict]:
    lines = (corpus_dir / "utterances.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def load_forecaster(weights: str, device: str):
    import torch  # noqa: F401  CRAFT is only exported once torch is imported.
    from convokit import Forecaster
    from convokit.forecaster.CRAFTModel import CRAFTModel

    model = CRAFTModel(initial_weights=weights, torch_device=device)
    # The labeler is only read when fitting; scoring uses the published weights as they are.
    return Forecaster(forecaster_model=model, labeler=lambda _convo: 0)


def forecast(corpus, forecaster, weights: str, device: str) -> dict:
    import importlib.metadata as metadata

    ordered_ids = [utterance.id for utterance in corpus.iter_utterances()]
    scored = forecaster.transform(corpus)

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
    series = order_series(series, ordered_ids)
    return {
        "series": series,
        "model": {
            "forecaster": "CRAFT",
            "weights": weights,
            "device": device,
            "convokit_version": metadata.version("convokit"),
        },
        "threshold": forecaster.forecaster_model._decision_threshold,
    }


def forecast_corpus(corpus_dir: Path, weights: str = DEFAULT_WEIGHTS, device: str = "cpu") -> dict:
    """Run CRAFT over one corpus and return its p(t) series plus provenance."""
    forecaster = load_forecaster(weights, device)
    from convokit import Corpus

    return forecast(Corpus(filename=str(corpus_dir)), forecaster, weights, device)


def completed_corpus(run_dir: Path) -> Path:
    corpus_dir = run_dir / "corpus"
    if not all((corpus_dir / name).is_file() for name in CORPUS_FILES):
        raise ValueError(f"No complete corpus to score in {run_dir}")
    meta = json.loads((corpus_dir / "run.json").read_text(encoding="utf-8"))
    if meta.get("status", "completed") != "completed" or meta.get("stop_reason") not in {
        "max_ticks",
        "silence",
        "max_utterances",
        "max_days",
    }:
        raise ValueError(f"Run did not complete: {run_dir}")
    return corpus_dir


def session_metrics(series: list[dict], sessions: dict[str, list[str]], threshold: float) -> dict:
    """Per-session metrics (plan §3-2) plus a run summary; `series` is in corpus order."""
    by_id = {row["id"]: row for row in series}
    per_session = {
        sid: derive_metrics([by_id[i] for i in ids], threshold) for sid, ids in sessions.items()
    }
    exceeded = [
        (m["first_threshold_crossing"]["tick"], sid)
        for sid, m in per_session.items()
        if m["threshold_exceeded"]
    ]
    first = min(exceeded, default=None)
    return {
        "sessions": per_session,
        "summary": {
            "sessions": len(per_session),
            "exceeded": len(exceeded),
            "exceeded_fraction": len(exceeded) / len(per_session) if per_session else 0.0,
            "first_exceeded": None if first is None else {"session": first[1], "tick": first[0]},
        },
    }


def save_report(
    run_dir: Path,
    result: dict,
    filename: str = "scores.json",
    sessions: dict[str, list[str]] | None = None,
) -> dict:
    report = {
        "schema_version": SCHEMA_VERSION,
        "scored_at": datetime.now(UTC).isoformat(),
        "run": str(run_dir),
        "model": result["model"],
        "metrics": derive_metrics(result["series"], result["threshold"]),
        "series": result["series"],
    }
    if sessions is not None:
        report |= session_metrics(result["series"], sessions, result["threshold"])
    with TemporaryDirectory(prefix=".scores-", dir=run_dir) as temporary:
        path = Path(temporary) / "scores.json"
        path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        path.replace(run_dir / filename)
    return report


def score_run(run_dir: Path, weights: str = DEFAULT_WEIGHTS, device: str = "cpu") -> dict:
    """Score one run directory and write scores.json beside its corpus."""
    corpus_dir = completed_corpus(run_dir)
    result = forecast_corpus(corpus_dir, weights=weights, device=device)
    result["series"] = order_series(result["series"], read_utterance_order(corpus_dir))
    return save_report(run_dir, result, sessions=read_sessions(corpus_dir))


def forecast_public(rows: list[dict], forecaster, weights: str, device: str) -> dict:
    """Build an in-memory corpus from public fields only, never private reflections.

    The live wiki snapshot is one conversation whose root utterance carries its id.
    """
    from convokit import Corpus, Speaker, Utterance

    speakers = {row["speaker"]: Speaker(id=row["speaker"]) for row in rows}
    corpus = Corpus(
        utterances=[
            Utterance(
                id=row["id"],
                speaker=speakers[row["speaker"]],
                text=row["text"],
                conversation_id=rows[0]["id"],
                reply_to=row["reply-to"],
                timestamp=row["timestamp"],
            )
            for row in rows
        ]
    )
    return forecast(corpus, forecaster, weights, device)


def watch_run(run_dir: Path, weights: str = DEFAULT_WEIGHTS, device: str = "cpu") -> None:
    """Score the newest public prefix serially, keeping one model loaded per worker."""
    path = run_dir / "live.json"
    if not path.is_file():
        raise ValueError(f"No live.json to watch in {run_dir}")
    previous = []
    forecaster = None
    result = None
    while True:
        progress = json.loads(path.read_text(encoding="utf-8"))
        rows = progress.get("utterances", [])
        if rows and rows != previous:
            if forecaster is None:
                forecaster = load_forecaster(weights, device)
            result = forecast_public(rows, forecaster, weights, device)
            result["series"] = order_series(result["series"], [row["id"] for row in rows])
            save_report(run_dir, result, "live-scores.json")
            previous = rows
            print(f"Scored {len(rows)} public comments", flush=True)
        if progress.get("status") in {"completed", "failed", "stopped"}:
            if progress["status"] == "completed" and result is not None:
                corpus = completed_corpus(run_dir)
                saved = [
                    json.loads(line)
                    for line in (corpus / "utterances.jsonl")
                    .read_text(encoding="utf-8")
                    .splitlines()
                    if line.strip()
                ]
                if [
                    {key: row[key] for key in ("id", "speaker", "text", "reply-to", "timestamp")}
                    for row in saved
                ] != rows:
                    raise ValueError("Completed corpus does not match the scored live conversation")
                save_report(run_dir, result)
            return
        sleep(0.5)


def find_runs(root: Path) -> list[Path]:
    """Run directories, not the corpus directories inside them."""
    return sorted(
        path.parent.parent
        for path in root.rglob("corpus/run.json")
        if all((path.parent / name).is_file() for name in CORPUS_FILES)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Score finished runs with the CRAFT forecaster.")
    parser.add_argument("runs", nargs="*", type=Path, help="run directories holding a corpus/")
    parser.add_argument("--all", type=Path, metavar="ROOT", help="score every run under ROOT")
    parser.add_argument(
        "--live", type=Path, metavar="RUN", help="watch live.json until the run ends"
    )
    parser.add_argument("--weights", default=DEFAULT_WEIGHTS)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()
    if args.live is not None:
        if args.runs or args.all:
            parser.error("--live cannot be combined with completed run paths")
        try:
            watch_run(args.live.resolve(), args.weights, args.device)
        except Exception as exc:
            raise SystemExit(f"Live scoring failed: {exc}") from exc
        return

    targets = list(
        dict.fromkeys(
            path.resolve() for path in [*args.runs, *(find_runs(args.all) if args.all else [])]
        )
    )
    if not targets:
        raise SystemExit("error: name at least one run directory, or pass --all runs")

    failures = 0
    for run_dir in targets:
        try:
            report = score_run(run_dir, weights=args.weights, device=args.device)
        except Exception as exc:
            # A batch keeps processing other runs, including when a scoring dependency fails.
            failures += 1
            print(f"failed {run_dir}: {exc}", file=sys.stderr)
            continue
        metrics = report["metrics"]
        crossing = metrics["first_threshold_crossing"]
        reached = (
            "none" if crossing is None else f"index {crossing['index']} (tick {crossing['tick']})"
        )
        print(
            f"{run_dir}: max p={metrics['max_p']:.4f} at tick {metrics['max_p_at']['tick']}, "
            f"max delta p/utterance={metrics['max_delta_p']:+.4f}, "
            f"first threshold crossing={reached} (p > {metrics['decision_threshold']})"
        )
    print(f"Scored {len(targets) - failures} run(s); failed {failures}.")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
