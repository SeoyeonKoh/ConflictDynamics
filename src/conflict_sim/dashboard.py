"""Streamlit viewer for finished runs. Reads corpus files only, never the engine.

uv run --extra dashboard streamlit run src/conflict_sim/dashboard.py
"""

import json
from pathlib import Path

import pandas as pd
import streamlit as st

LIST_COLUMNS = [
    "run",
    "created_at",
    "rule",
    "agents",
    "seed",
    "backend",
    "model",
    "utterances",
    "ticks",
    "stop_reason",
]


def discover_runs(root: Path) -> tuple[list[dict], list[str]]:
    """Find every corpus under root, newest first, plus the names of unreadable ones."""
    rows: list[dict] = []
    broken: list[str] = []
    for meta_path in sorted(root.rglob("corpus/run.json")):
        directory = meta_path.parent.parent
        name = str(directory.relative_to(root))
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            broken.append(name)
            continue
        config = meta.get("config", {})
        rows.append(
            {
                "run": name,
                "created_at": meta.get("created_at", ""),
                "rule": config.get("rule"),
                "agents": config.get("n_agents"),
                "seed": config.get("random_seed"),
                "backend": config.get("backend"),
                "model": config.get("model_speak"),
                "utterances": meta.get("generated_utterances"),
                "ticks": meta.get("ticks"),
                "stop_reason": meta.get("stop_reason"),
                "corpus": str(meta_path.parent),
            }
        )
    rows.sort(key=lambda row: row["created_at"], reverse=True)
    return rows, broken


def _read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def load_run(corpus: Path) -> dict:
    return {
        "meta": json.loads((corpus / "run.json").read_text(encoding="utf-8")),
        "utterances": _read_jsonl(corpus / "utterances.jsonl"),
        "decisions": _read_jsonl(corpus / "decisions.jsonl"),
    }


def reply_depth(utterances: list[dict]) -> dict[str, int]:
    """Depth of each utterance in the reply tree. Dangling and cyclic parents stop the walk."""
    parents = {u["id"]: u["reply-to"] for u in utterances}
    depths: dict[str, int] = {}
    for utterance_id in parents:
        depth = 0
        seen = {utterance_id}
        current = parents[utterance_id]
        while current is not None and current not in seen:
            depth += 1
            seen.add(current)
            if current not in parents:
                break
            current = parents[current]
        depths[utterance_id] = depth
    return depths


@st.cache_data(show_spinner=False)
def _cached_runs(root: str, _stamp: float) -> tuple[list[dict], list[str]]:
    return discover_runs(Path(root))


@st.cache_data(show_spinner=False)
def _cached_run(corpus: str, _stamp: float) -> dict:
    return load_run(Path(corpus))


def _stamp_of(path: Path) -> float:
    return path.stat().st_mtime if path.exists() else 0.0


def main() -> None:
    st.set_page_config(page_title="ConflictDynamics runs", layout="wide")
    st.title("ConflictDynamics runs")

    root_input = st.sidebar.text_input("runs directory", value="runs")
    if st.sidebar.button("Reload"):
        st.cache_data.clear()
    root = Path(root_input).expanduser()

    rows, broken = _cached_runs(str(root), _stamp_of(root))
    if broken:
        st.warning(f"Skipped {len(broken)} run(s) with an unreadable run.json: {', '.join(broken)}")
    if not rows:
        st.info(f"No corpus found under {root.resolve()}. Run `uv run conflict-sim` first.")
        return

    st.dataframe(pd.DataFrame(rows)[LIST_COLUMNS], width="stretch", hide_index=True)

    names = [row["run"] for row in rows]
    selected = st.selectbox("Run", names)
    row = next(item for item in rows if item["run"] == selected)
    corpus = Path(row["corpus"])
    run = _cached_run(str(corpus), _stamp_of(corpus / "run.json"))

    decisions = run["decisions"]
    urges = [event["urge"] for event in decisions if "urge" in event]
    columns = st.columns(4)
    columns[0].metric("Generated", run["meta"].get("generated_utterances"))
    columns[1].metric("Ticks", run["meta"].get("ticks"))
    columns[2].metric("Stopped by", run["meta"].get("stop_reason"))
    columns[3].metric("Mean urge", round(sum(urges) / len(urges), 3) if urges else "—")

    transcript_tab, decisions_tab = st.tabs(["Transcript", "Decisions"])

    with transcript_tab:
        depths = reply_depth(run["utterances"])
        for utterance in run["utterances"]:
            seed = utterance["timestamp"] == 0
            label = "seed" if seed else f"t{utterance['timestamp']}"
            indent = "&nbsp;" * 4 * depths.get(utterance["id"], 0)
            st.markdown(
                f"{indent}**{utterance['speaker']}** · `{label}` · "
                f"reply-to `{utterance['reply-to']}` · {len(utterance['text'].split())} words",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"{indent}{'> ' if seed else ''}{utterance['text']}", unsafe_allow_html=True
            )
            st.divider()

    with decisions_tab:
        if decisions:
            st.dataframe(pd.DataFrame(decisions), width="stretch", hide_index=True)
        else:
            st.info("This run recorded no decisions.")


if __name__ == "__main__":
    main()
