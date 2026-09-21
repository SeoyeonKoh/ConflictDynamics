import json
import random
from pathlib import Path

import pytest
from hydra import compose, initialize_config_dir

from conflict_sim.agent import Agent
from conflict_sim.cli import parse_config
from conflict_sim.environment import Environment
from conflict_sim.llm import DemoBackend
from conflict_sim.loop import Loop, phase_of

CONF = Path(__file__).resolve().parents[1] / "conf"


class Recorder:
    """Stands in for storage: keeps what the loop hands over each tick."""

    def __init__(self):
        self.ticks = []

    def write_tick(self, events, memory_rows, retrieval_rows):
        rows = [(r, None if v is None else v.tolist()) for r, v in memory_rows]  # comparable
        self.ticks.append((list(events), rows, list(retrieval_rows)))

    def write_checkpoint(self, day, data):
        self.checkpoints = getattr(self, "checkpoints", []) + [(day, json.loads(json.dumps(data)))]

    @property
    def events(self):
        return [event for events, _, _ in self.ticks for event in events]

    def memory(self):
        """What `storage.read_memory` would hand back: records and vectors per agent."""
        out = {}
        for _, rows, _ in self.ticks:
            for record, vector in rows:
                records, vectors = out.setdefault(record.agent_id, ([], {}))
                records.append(record)
                vectors[record.id] = vector
        return out


class Spy:
    """Wraps the demo backend and keeps every prompt, so tests can read what an agent saw."""

    def __init__(self, backend):
        self.backend = backend
        self.prompts = []

    def complete(self, **request):
        self.prompts.append(json.loads(request["prompt"]))
        return self.backend.complete(**request)

    def embed(self, texts):
        return self.backend.embed(texts)


def company_config(**overrides):
    with initialize_config_dir(version_base="1.3", config_dir=str(CONF)):
        cfg = parse_config(
            compose(config_name="company", overrides=[f"{k}={v}" for k, v in overrides.items()])
        )
    return cfg


def make_loop(cfg=None, writer=None, llm=None):
    cfg = cfg or company_config()
    llm = llm or DemoBackend(
        blocked_nudge_ticks=cfg.blocked_nudge_ticks, blocked_report_ticks=cfg.blocked_report_ticks
    )
    agents = [Agent(spec, cfg, llm) for spec in cfg.agents]
    env = Environment(cfg.environment, cfg.agents)
    return Loop(cfg, agents, env, llm, random.Random(cfg.random_seed), writer=writer or Recorder())


@pytest.mark.parametrize(
    "tick,phase",
    [(0, "arrival"), (1, "morning"), (15, "morning"), (16, "lunch"), (19, "lunch"),
     (20, "afternoon"), (30, "afternoon"), (31, "closing"), (32, "arrival"), (48, "lunch")],
)  # fmt: skip
def test_phases_partition_a_day_of_32_ticks(tick, phase):
    assert phase_of(tick, 32) == phase


def test_one_demo_day_runs_end_to_end_and_moves_the_task_graph():
    loop = make_loop()
    result = loop.run()
    assert (result.days, result.ticks, result.stop_reason) == (1, 32, "max_days")
    tasks = loop.env.snapshot()["tasks"]
    assert tasks["spec"]["status"] == "done" and tasks["api"]["progress"] > 0
    kinds = {event.kind for event in loop.writer.events}
    assert {"action", "task", "decision", "outcome", "session"} <= kinds


def test_a_blocked_engineer_nudges_the_owner_then_reports_to_the_manager():
    loop = make_loop()
    loop.run()
    dm = loop.threads["dm:Alex:Blake:0"]
    assert dm.utterances[0].speaker == "Blake" and dm.utterances[0].timestamp == 2
    assert "spec" in dm.utterances[0].text
    report = loop.threads["dm:Blake:Erin:0"]
    assert report.utterances[0].speaker == "Blake" and report.utterances[0].timestamp == 4
    inbox_records = [
        r for r in loop.agent("Alex").memory.records if "Blake wrote to me" in r.description
    ]
    assert inbox_records and inbox_records[0].created_tick == 3


def test_messages_arrive_next_tick_whatever_the_acting_order():
    for reverse in (False, True):
        cfg = company_config()
        if reverse:  # senders now act before their receivers
            cfg = cfg.model_copy(update={"agents": list(reversed(cfg.agents))})
        loop = make_loop(cfg)
        loop.run_until(3)
        heard = [
            r for r in loop.agent("Alex").memory.records if "Blake wrote to me" in r.description
        ]
        assert [r.created_tick for r in heard] == [3], reverse  # sent at tick 2, read at tick 3
        assert loop.inbox["Alex"] == []


def test_an_unanswered_message_is_shown_once_after_no_reply_ticks():
    spy = Spy(DemoBackend())
    loop = make_loop(llm=spy)
    loop.run_until(7)
    seen = [(p["view"]["tick"], p["view"]["unanswered"]) for p in spy.prompts
            if "view" in p and p["speaker"] == "Blake"]  # fmt: skip
    shown = [(tick, u) for tick, us in seen for u in us]
    assert shown == [(5, {"to": "Alex", "since_tick": 2}), (7, {"to": "Erin", "since_tick": 4})]


def test_messages_to_an_agent_in_a_session_are_read_once_when_it_is_free_again():
    loop = make_loop()
    loop.run_until(17)
    busy = next(name for name in loop.busy)
    loop._send(loop.agent("Casey" if busy != "Casey" else "Drew"),
               __import__("conflict_sim.models", fromlist=["Action"]).Action(
                   kind="message", target=busy, text="Ping", expression="neutral",
                   reflection="Checking in.", importance=3, valence=0, arousal=0),
               tick=16, day=0)  # fmt: skip
    loop.run_until(22)
    pings = [
        r.created_tick
        for r in loop.agent(busy).memory.records
        if "wrote to me: Ping" in r.description
    ]
    assert len(pings) == 1 and pings[0] > 17


def test_lunch_makes_talk_sessions_and_their_outcomes_reach_the_agents():
    loop = make_loop()
    loop.run()
    talks = [m for m in loop.sessions.values() if m["kind"] == "talk"]
    assert talks and all(m["public"] and m["end"] is not None for m in talks)
    assert all(len(loop.threads[m["id"]].utterances) >= 1 for m in talks)
    assert any(agent.state.relations for agent in loop.agents)
    outcome_events = [e for e in loop.writer.events if e.kind == "outcome"]
    assert outcome_events and "relation_delta" in outcome_events[0].payload


def test_agents_in_a_live_session_do_not_act_and_sessions_close_at_phase_end():
    loop = make_loop()
    loop.run_until(17)
    busy = set(loop.busy)
    assert busy, "a lunch talk should be live after tick 17"
    loop.run_until(18)
    acted = {e.actor for e in loop.writer.events if e.kind == "action" and e.tick == 18}
    assert not busy & acted
    loop.run_until(20)
    assert all(m["end"] is not None for m in loop.sessions.values() if m["kind"] == "talk")


def test_every_tick_is_handed_to_storage_with_embedded_records():
    recorder = Recorder()
    loop = make_loop(writer=recorder)
    loop.run()
    assert len(recorder.ticks) == 32
    assert all(vector is not None for _, rows, _ in recorder.ticks for _, vector in rows)
    assert all(events for events, _, _ in recorder.ticks)  # a quiet tick may add no records
    assert all(not agent.memory.pending_writes for agent in loop.agents)
    assert all(r.id in agent.memory.vectors for agent in loop.agents for r in agent.memory.records)


def test_same_seed_same_events():
    runs = []
    for _ in range(2):
        loop = make_loop()
        loop.run()
        runs.append([e.model_dump() for e in loop.writer.events])
    assert runs[0] == runs[1]


def test_a_session_still_live_at_the_end_of_the_run_is_closed():
    class TalkAtClosing(Spy):
        def complete(self, **request):
            payload = json.loads(request["prompt"])
            if "view" in payload and payload["view"]["tick"] == 31 and payload["view"]["present"]:
                return json.dumps({"kind": "talk", "text": "One last thing before we go.",
                                   "expression": "neutral", "reflection": "Wrapping up.",
                                   "importance": 3, "valence": 0, "arousal": 0})  # fmt: skip
            return super().complete(**request)

    loop = make_loop(llm=TalkAtClosing(DemoBackend()))
    loop.run()
    assert loop.live == {} and loop.busy == {}
    talks = [m for m in loop.sessions.values() if m["kind"] == "talk"]
    assert any(m["start"] == 31 for m in talks) and all(
        m["end"] == 31 or m["end"] < 31 for m in talks
    )
    ends = [e for e in loop.writer.events if e.kind == "session" and "end" in e.payload]
    assert ends[-1].tick == 31 and ends[-1].payload["end"] == "day_end"
    assert len(loop.writer.ticks) == 32


def test_every_day_ends_with_its_sessions_closed_and_a_checkpoint():
    cfg = company_config().model_copy(update={"max_days": 2})
    loop = make_loop(cfg)
    loop.run()
    assert [day for day, _ in loop.writer.checkpoints] == [0, 1]
    data = loop.writer.checkpoints[0][1]
    assert data["tick"] == 32 and data["live"] == {} and data["busy"] == {}
    assert set(data["agents"]) == {a.name for a in loop.agents}
    assert data["env"]["tasks"]["spec"]["worked"] == 6


def test_a_restored_loop_replays_the_second_day_exactly():
    cfg = company_config().model_copy(update={"max_days": 2})
    straight = make_loop(cfg)
    straight.run()
    second_day = [e.model_dump() for e in straight.writer.events if e.day == 1]

    first = make_loop(cfg)
    first.run_until(31)
    day, data = first.writer.checkpoints[-1]
    resumed = make_loop(cfg)
    resumed.restore(data, first.writer.memory())
    assert resumed.tick_now == 32 and resumed.env.snapshot() == first.env.snapshot()
    assert all(len(a.memory.vectors) == len(a.memory.records) > 0 for a in resumed.agents)
    resumed.run()
    replayed = [e.model_dump() for e in resumed.writer.events]
    assert replayed == second_day
    assert [a.snapshot() for a in resumed.agents] == [a.snapshot() for a in straight.agents]
    day_one = [(rows, log) for _, rows, log in straight.writer.ticks[32:]]
    assert [(rows, log) for _, rows, log in resumed.writer.ticks] == day_one


def test_parallel_judgements_reproduce_the_sequential_run_and_use_several_threads():
    import threading

    class Threads(Spy):
        def complete(self, **request):
            self.threads = getattr(self, "threads", set()) | {threading.current_thread().name}
            return super().complete(**request)

    runs = {}
    for workers in (1, 4):
        cfg = company_config().model_copy(update={"workers": workers})
        loop = make_loop(cfg, llm=Threads(DemoBackend()))
        loop.run()
        runs[workers] = ([e.model_dump() for e in loop.writer.events], loop.llm.threads)
    assert runs[1][0] == runs[4][0]
    assert len(runs[1][1]) == 1 and len(runs[4][1]) > 1


def test_an_agent_pulled_into_a_session_this_tick_keeps_out_of_a_second_one():
    loop = make_loop()
    loop.run_until(17)  # every plan says `talk` at 17; one session must absorb the room
    talks = [m for m in loop.sessions.values() if m["kind"] == "talk" and m["start"] == 17]
    assert len(talks) == 1 and sorted(talks[0]["participants"]) == sorted(loop.by_name)
    assert set(loop.busy) == set(loop.by_name) and set(loop.busy.values()) == {talks[0]["id"]}
    rejected = [e for e in loop.writer.events if e.kind == "rejected" and e.tick == 17]
    assert rejected == []
