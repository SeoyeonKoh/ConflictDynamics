"""Version 1 viewer messages. Coordinates belong to Tiled, never to the world model."""

import json
from pathlib import Path


class Frames:
    def __init__(self, cfg, run_id: str):
        path = (
            Path(cfg.stream_map) if cfg.stream_map else Path(__file__).parent / "maps/office.json"
        )
        self.map = json.loads(path.read_text())
        self.places, self.seats = {}, {}
        for layer in self.map["layers"]:
            for obj in layer.get("objects", []):
                props = {p["name"]: p["value"] for p in obj.get("properties", [])}
                if "place_id" in props:
                    place = props["place_id"]
                    if place in self.places:
                        raise ValueError(f"Duplicate Tiled place_id: {place}")
                    self.places[place] = obj
                if "seat" in props:
                    self.seats.setdefault(props["seat"], []).append((obj["x"], obj["y"]))
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
        actions = {e.actor: e.payload for e in events if e.kind == "action"}
        # A talk may open and close inside one tick; the frame still shows it and its members.
        sessions = list(snapshot["sessions"])
        for e in events:
            if e.kind == "session" and e.payload.get("start"):
                if e.session not in {s["id"] for s in sessions}:
                    sessions.append(
                        {
                            "id": e.session,
                            "kind": e.payload["kind"],
                            "place": e.location,
                            "participants": e.payload["participants"],
                        }
                    )
        joined = {p: s["id"] for s in sessions for p in s["participants"]}
        order, occupants, spots = [a["id"] for a in snapshot["agents"]], {}, {}
        for a in snapshot["agents"]:
            occupants.setdefault(a["place"], []).append(a["id"])
        for place, names in occupants.items():
            spots |= self.spots(place, names, order)
        agents = []
        for a in snapshot["agents"]:
            x, y = spots[a["id"]]
            action = actions.get(a["id"], {})
            session = a["session"] or joined.get(a["id"])
            agents.append(
                {
                    "id": a["id"],
                    "place": a["place"],
                    "x": x,
                    "y": y,
                    "action": action.get("kind", "talk" if session else "idle"),
                    "expression": a["state"]["expression"],
                    "session": session,
                    **({"target": action["target"]} if action.get("target") else {}),
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
            "sessions": sessions,
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

    def spots(self, place, occupants, order):
        """Each occupant takes the first free seat from its own (index-keyed) one, so seats stay
        put while others come and go; anyone left over stands in a grid over the place."""
        seats, placed, standing = self.seats.get(place, []), {}, []
        for name in occupants:
            free = [i for i in range(len(seats)) if seats[i] not in placed.values()]
            if not free:
                standing.append(name)
                continue
            start = order.index(name) % len(seats)
            placed[name] = seats[min(free, key=lambda i: (i - start) % len(seats))]
        obj = self.places[place]
        cols = max(1, int(obj.get("width", 96) // 32))
        rows = max(1, (len(standing) + cols - 1) // cols)
        for index, name in enumerate(standing):
            placed[name] = (
                obj["x"] + (index % cols + 0.5) * obj.get("width", 96) / cols,
                obj["y"] + (index // cols + 0.5) * obj.get("height", 96) / rows,
            )
        return placed

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
