"""Version 1 viewer messages. Coordinates belong to Tiled, never to the world model."""

import json
from pathlib import Path


class Frames:
    def __init__(self, cfg, run_id: str):
        path = (
            Path(cfg.stream_map) if cfg.stream_map else Path(__file__).parent / "maps/office.json"
        )
        self.map = json.loads(path.read_text())
        self._seat_new_departments(cfg)
        self.places, self.seats, self.seat_dept = {}, {}, {}
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
                    if "dept" in props:  # a department's own desks, behind its partition
                        self.seat_dept[(obj["x"], obj["y"])] = props["dept"]
        missing = {p.id for p in cfg.environment.office.places} - self.places.keys()
        if missing:
            raise ValueError(f"Tiled map is missing places: {sorted(missing)}")
        self.cfg, self.run_id = cfg, run_id
        self.dept = {agent.name: agent.department for agent in cfg.agents}
        self.people = {a.name: (a.display_name or a.name, a.role or a.title) for a in cfg.agents}
        self.previous_tasks = self.previous_resources = None
        self.previous_plans = {}
        self.retrieved = {}

    def _seat_new_departments(self, cfg):
        """Company departments missing from the map take its unused department areas."""
        objects = [o for layer in self.map["layers"] for o in layer.get("objects", [])]

        def prop(obj, name):
            return next((p for p in obj.get("properties", []) if p["name"] == name), None)

        desks = {p["value"] for o in objects if (p := prop(o, "dept")) and prop(o, "seat")}
        zones = [(o, prop(o, "zone")) for o in objects]
        areas = [z for _, z in zones if z and z["value"] in desks]  # department areas only
        wanted = {a.department: a.team for a in cfg.agents}
        new = [d for d in wanted if d not in {a["value"] for a in areas}]
        free = [a["value"] for a in areas if a["value"] not in wanted]
        if not new:
            return
        moved = dict(zip(free, new, strict=False))
        for obj in objects:
            dept = prop(obj, "dept")
            if dept and dept["value"] in moved:
                dept["value"] = moved[dept["value"]]
        for obj, zone in zones:
            if zone and zone["value"] in moved:
                zone["value"] = wanted[moved[zone["value"]]] or moved[zone["value"]]
            elif zone and zone["value"] in free:
                obj["properties"].remove(zone)  # no one sits here: drop its label

    def hello(self, snapshot):
        return {
            "type": "hello",
            "version": 1,
            "run_id": self.run_id,
            "map": "office.json",
            "map_data": self.map,
            "tick_minutes": 15,
            "agents": [
                {"id": a["id"], "name": a["id"], "sprite": f"agent-{i % 20}", "dept": a["dept"],
                 "display_name": self.people.get(a["id"], (a["id"], None))[0],
                 "title": self.people.get(a["id"], (a["id"], None))[1]}
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
                    # Sent when it changes; the viewer keeps the last one it saw.
                    **({"plan": a["plan"]}
                       if "plan" in a and a["plan"] != self.previous_plans.get(a["id"])
                       else {}),  # fmt: skip
                }
            )
            if "plan" in a:
                self.previous_plans[a["id"]] = a["plan"]
        tasks, resources = snapshot["tasks"], snapshot["resources"]
        frame = {
            "type": "frame",
            "tick": snapshot["tick"],
            "day": snapshot["day"],
            "phase": snapshot["phase"],
            "agents": agents,
            "sessions": sessions,
            **({"lines": _with_thoughts(snapshot["lines"], events)}
               if snapshot.get("lines") else {}),  # fmt: skip
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
        put while others come and go; a seat marked with a department goes to its own people
        first. Anyone left over stands in a grid over the place."""
        seats, placed, standing = self.seats.get(place, []), {}, []
        for name in occupants:
            free = [i for i in range(len(seats)) if seats[i] not in placed.values()]
            if not free:
                standing.append(name)
                continue
            own = [i for i in free if self.seat_dept.get(seats[i]) == self.dept.get(name)]
            free = own or free
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


def _with_thoughts(lines, events):
    """Each line with what its speaker thought before saying it: a reply's judgement, or the
    action that opened the conversation. Meetings record none; a thought that only repeats the
    line (a planned talk) is left out."""
    replied = {
        e.payload.get("utterance_id"): e.payload.get("reflection")
        for e in events
        if e.kind == "decision" and e.payload.get("posted")
    }
    opened = {
        e.actor: e.payload.get("reflection")
        for e in events
        if e.kind == "action" and e.payload.get("kind") in ("talk", "message")
    }
    spoke, out = set(), []  # one action a tick: a speaker's first other line this tick is it
    for line in lines:
        thought = replied.get(line["id"])
        if thought is None and not line["session"].startswith("meeting:"):
            if line["speaker"] not in spoke:
                thought = opened.get(line["speaker"])
            spoke.add(line["speaker"])
        thought = (thought or "").strip()
        out.append(line | ({"thought": thought} if thought and thought != line["text"].strip()
                           else {}))  # fmt: skip
    return out
