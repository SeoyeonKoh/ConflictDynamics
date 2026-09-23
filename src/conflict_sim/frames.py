"""Version 1 viewer messages. Coordinates belong to Tiled, never to the world model."""

import json
from pathlib import Path


class Frames:
    def __init__(self, cfg, run_id: str):
        path = (
            Path(cfg.stream_map) if cfg.stream_map else Path(__file__).parent / "maps/office.json"
        )
        self.map = json.loads(path.read_text())
        self.places = {}
        for layer in self.map["layers"]:
            for obj in layer.get("objects", []):
                props = {p["name"]: p["value"] for p in obj.get("properties", [])}
                if "place_id" in props:
                    place = props["place_id"]
                    if place in self.places:
                        raise ValueError(f"Duplicate Tiled place_id: {place}")
                    self.places[place] = obj
        missing = {p.id for p in cfg.environment.office.places} - self.places.keys()
        if missing:
            raise ValueError(f"Tiled map is missing places: {sorted(missing)}")
        self.cfg, self.run_id = cfg, run_id
        self.previous_tasks = self.previous_resources = None
        self.retrieved = {}

    def hello(self, snapshot):
        return {
            "type": "hello",
            "version": 1,
            "run_id": self.run_id,
            "map": "office.json",
            "map_data": self.map,
            "tick_minutes": 15,
            "agents": [
                {"id": a["id"], "name": a["id"], "sprite": f"agent-{i % 20}", "dept": a["dept"]}
                for i, a in enumerate(snapshot["agents"])
            ],
            "config": {"ticks_per_day": self.cfg.ticks_per_day, "max_days": self.cfg.max_days},
            "tasks": snapshot["tasks"],
            "resources": snapshot["resources"],
        }

    def capture(self, snapshot, events, retrievals):
        for row in retrievals:
            self.retrieved[row["agent_id"]] = row["ids"]
        actions = {e.actor: e.payload.get("kind", "idle") for e in events if e.kind == "action"}
        agents = []
        for a in snapshot["agents"]:
            place = a["place"]
            obj = self.places[place]
            occupants = [b["id"] for b in snapshot["agents"] if b["place"] == place]
            index = occupants.index(a["id"])
            cols = max(1, int(obj.get("width", 96) // 32))
            rows = max(1, (len(occupants) + cols - 1) // cols)
            agents.append(
                {
                    "id": a["id"],
                    "place": place,
                    "x": obj["x"] + (index % cols + 0.5) * obj.get("width", 96) / cols,
                    "y": obj["y"] + (index // cols + 0.5) * obj.get("height", 96) / rows,
                    "action": actions.get(a["id"], "talk" if a["session"] else "idle"),
                    "expression": a["state"]["expression"],
                    "session": a["session"],
                    **({"bubble": a["bubble"]} if "bubble" in a else {}),
                }
            )
        tasks, resources = snapshot["tasks"], snapshot["resources"]
        frame = {
            "type": "frame",
            "tick": snapshot["tick"],
            "day": snapshot["day"],
            "phase": snapshot["phase"],
            "agents": agents,
            "sessions": snapshot["sessions"],
            "tasks": [
                t
                for t in tasks
                if self.previous_tasks is None or t != self.previous_tasks.get(t["id"])
            ],
            "resources": [
                r
                for r in resources
                if self.previous_resources is None or r != self.previous_resources.get(r["id"])
            ],
        }
        self.previous_tasks = {t["id"]: t for t in tasks}
        self.previous_resources = {r["id"]: r for r in resources}
        messages = [frame]
        for e in events:
            if e.kind in ("task", "rejected", "outcome", "shock", "session"):
                messages.append(
                    {
                        "type": "event",
                        "tick": e.tick,
                        "kind": e.kind,
                        "actors": [n for n in (e.actor, e.target) if n],
                        "text": json.dumps(e.payload, ensure_ascii=False),
                        "session": e.session,
                        "payload": e.payload,
                    }
                )
        return messages, self.inspect(snapshot)

    def inspect(self, snapshot):
        return {
            a["id"]: {
                "type": "inspect",
                "agent": a["id"],
                "tick": snapshot["tick"],
                "reflection": a["reflection"],
                "state": {"stress": a["state"]["stress"], "mood": a["state"]["mood"]},
                "relationships": [
                    {"to": name, "relation": r["relation"], "summary": r["summary"]}
                    for name, r in a["state"]["relations"].items()
                ],
                "retrieved": self.retrieved.get(a["id"], []),
            }
            for a in snapshot["agents"]
        }
