"""Rebuild replay.js, the recorded day the intro page plays behind its slides.

    uv run python viz/public/intro/build.py runs/<run>/<scenario>/replicate-1

It keeps what the page draws: the office map from hello, every agent's place, action, face and
speech per tick, and the relation changes. Names and roles come from the persona file, because
older journals carry only ids. A script rather than JSON, so the page also opens from file://.
"""

import json
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).parent
ROOT = HERE.parents[2]
PERSONAS = ROOT / "conf/personas/korean_enterprise_10_ko.yaml"


def props(o):
    return {p["name"]: p["value"] for p in o.get("properties", [])}


def box(o):
    return [o["x"], o["y"], o["width"], o["height"]]


def main(run_dir: Path):
    messages = [json.loads(line) for line in (run_dir / "frames.jsonl").open(encoding="utf-8")]
    hello = messages[0]
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    people = {a["id"]: a for a in yaml.safe_load(PERSONAS.read_text(encoding="utf-8"))["agents"]}
    ids = [a["id"] for a in hello["agents"]]
    capacity = {r["id"]: r["capacity"] for r in hello["resources"]}

    layers = {layer["name"]: layer["objects"] for layer in hello["map_data"]["layers"]}
    places = [
        [props(o)["place_id"], o["name"], *box(o), props(o).get("floor", "oak"),
         capacity.get(props(o)["place_id"])]
        for o in layers["places"]
    ]  # fmt: skip
    place_index = {p[0]: i for i, p in enumerate(places)}

    def talkers(session):
        return [ids.index(p) for p in session["participants"]]

    frames = []
    for m in messages:
        if m["type"] != "frame":
            continue
        agents = []
        for a in m["agents"]:
            row = [round(a["x"]), round(a["y"]), a["action"], a["expression"],
                   place_index[a["place"]]]  # fmt: skip
            if a.get("bubble") or a.get("target"):
                row.append(a.get("bubble") or 0)
            if a.get("target") in ids:
                row.append(ids.index(a["target"]))
            agents.append(row)
        sessions = [
            [s["kind"], place_index.get(s.get("place"), -1), talkers(s)] for s in m["sessions"]
        ]
        frames.append([m["phase"], agents, sessions])

    outcomes, rejected = [], []
    for m in messages:
        if m["type"] != "event":
            continue
        payload = m.get("payload") or {}
        if m["kind"] == "outcome" and payload.get("relation_delta"):
            why = next((k for k in ("ignored", "refused") if payload.get(k)), "")
            outcomes.append([m["tick"], ids.index(payload["a"]), ids.index(payload["b"]),
                             round(payload["relation_delta"], 4), why])  # fmt: skip
        elif m["kind"] == "rejected" and m["actors"] and m["actors"][0] in ids:
            rejected.append([m["tick"], ids.index(m["actors"][0]), payload.get("reason", "")])

    tile = hello["map_data"]["tilewidth"]
    data = {
        "run": run_dir.parts[-3],
        "scenario": manifest["scenario"],
        "model": manifest["model_id"],
        "ticksPerDay": hello["config"]["ticks_per_day"],
        "tickMinutes": hello["tick_minutes"],
        "size": [hello["map_data"]["width"] * tile, hello["map_data"]["height"] * tile],
        "places": places,
        "zones": [[o["name"], *box(o)] for o in layers["zones"]],
        "corridors": [box(o) for o in layers["walkways"] if props(o)["walkway"] == "corridor"],
        "doors": [
            [o["name"], *box(o)] for o in layers["walkways"] if props(o)["walkway"] == "door"
        ],
        "furniture": [[props(o)["frame"], *box(o)] for o in layers["furniture"]],
        "agents": [
            [
                a["id"],
                people[a["id"]]["name"],
                people[a["id"]]["role"],
                a["dept"],
                people[a["id"]]["disc"],
                int(a["sprite"].split("-")[1]),
            ]
            for a in hello["agents"]
        ],  # fmt: skip
        "frames": frames,
        "outcomes": outcomes,
        "rejected": rejected,
    }
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    (HERE / "replay.js").write_text(f"window.CD_REPLAY = {text};\n", encoding="utf-8")
    print(f"replay.js: {len(frames)} ticks, {len(ids)} agents, {len(text) // 1024} KB")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
