"""Extract paired two-comment seeds from a local CGA-WIKI corpus."""

import argparse
import json
from collections import defaultdict
from pathlib import Path

from .models import Utterance
from .storage import write_json


def extract_seeds(corpus: Path, output: Path, split: str = "train") -> dict:
    """Keep original comment links; exclude an entire pair if either seed is unsuitable."""
    if split not in {"train", "val", "test"}:
        raise ValueError(f"Unknown CGA split: {split}")
    if output.exists():
        raise FileExistsError(f"Output already exists: {output}")
    records = json.loads((corpus / "conversations.json").read_text(encoding="utf-8"))
    conversations = {cid: row.get("meta", row) for cid, row in records.items()}
    comments = defaultdict(list)
    with (corpus / "utterances.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            # CGA uses NaN for some missing root parents; emit standard JSON null.
            row = json.loads(line, parse_constant=lambda _: None)
            if not row["meta"]["is_section_header"]:
                comments[row["conversation_id"]].append(
                    {key: row[key] for key in ("id", "speaker", "text", "reply-to", "timestamp")}
                )

    report = {"source": str(corpus.resolve()), "split": split, "pairs": [], "excluded": []}
    seeds = {}
    visited = set()
    for cid, meta in sorted(conversations.items()):
        if meta["split"] != split or cid in visited:
            continue
        pair = sorted({cid, meta["pair_id"]})
        visited.update(pair)
        reasons = []
        if len(pair) != 2 or any(partner not in conversations for partner in pair):
            reasons.append("missing_or_self_pair")
        else:
            left, right = (conversations[partner] for partner in pair)
            if left["pair_id"] != pair[1] or right["pair_id"] != pair[0]:
                reasons.append("non_reciprocal_pair")
            if left["split"] != right["split"]:
                reasons.append("split_mismatch")
            if (
                left["conversation_has_personal_attack"]
                == right["conversation_has_personal_attack"]
            ):
                reasons.append("same_outcome")
        first_two = {}
        for partner in pair:
            rows = sorted(comments[partner], key=lambda row: row["timestamp"])[:2]
            first_two[partner] = rows
            if len(rows) < 2:
                reasons.append(f"{partner}: fewer_than_two_comments")
            elif rows[1]["reply-to"] != rows[0]["id"]:
                reasons.append(f"{partner}: second_not_reply_to_first")
            elif any(not row["text"].strip() for row in rows):
                reasons.append(f"{partner}: empty_comment")
        if reasons:
            report["excluded"].append({"conversation_ids": pair, "reasons": reasons})
            continue

        files = []
        for side, partner in enumerate(pair):
            rows = first_two[partner]
            filename = f"pair-{len(report['pairs']):04d}-{side}.json"
            seeds[filename] = {
                "source": "cga-wiki",
                "conversation_id": partner,
                "cga": conversations[partner],
                "original_seed": [
                    {key: row[key] for key in ("id", "reply-to", "timestamp")} for row in rows
                ],
                "utterances": [
                    Utterance(
                        id=row["id"],
                        speaker=row["speaker"],
                        text=row["text"],
                        reply_to=None if index == 0 else row["reply-to"],
                        timestamp=0,
                    ).model_dump()
                    for index, row in enumerate(rows)
                ],
            }
            files.append(filename)
        report["pairs"].append({"conversation_ids": pair, "seed_files": files})

    output.mkdir(parents=True)
    for filename, data in seeds.items():
        write_json(output / filename, data)
    write_json(output / "manifest.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path, help="local CGA-WIKI corpus directory")
    parser.add_argument("output", type=Path, help="new directory for seeds and manifest.json")
    parser.add_argument("--split", choices=["train", "val", "test"], default="train")
    args = parser.parse_args()
    try:
        report = extract_seeds(args.corpus, args.output, args.split)
    except (OSError, ValueError, KeyError) as exc:
        raise SystemExit(f"error: {exc}") from exc
    print(
        f"Saved {len(report['pairs'])} pairs; excluded {len(report['excluded'])}. See {args.output}"
    )
    if not report["pairs"]:
        raise SystemExit("No eligible pairs; see manifest.json for exclusions.")


if __name__ == "__main__":
    main()
