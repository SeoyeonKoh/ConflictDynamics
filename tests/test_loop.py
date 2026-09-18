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
        self.ticks.append((list(events), list(memory_rows), list(retrieval_rows)))


def company_config(**overrides):
    with initialize_config_dir(version_base="1.3", config_dir=str(CONF)):
        cfg = parse_config(
            compose(config_name="company", overrides=[f"{k}={v}" for k, v in overrides.items()])
        )
    return cfg


def make_loop(cfg=None, writer=None):
    cfg = cfg or company_config()
    llm = DemoBackend(
        blocked_nudge_ticks=cfg.blocked_nudge_ticks, blocked_report_ticks=cfg.blocked_report_ticks
    )
    agents = [Agent(spec, cfg, llm) for spec in cfg.agents]
    env = Environment(cfg.environment, cfg.agents)
    return Loop(cfg, agents, env, llm, random.Random(cfg.random_seed), writer=writer)


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
    kinds = {event.kind for event in loop.events}
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


def test_messages_arrive_next_tick_and_unanswered_ones_surface_after_no_reply_ticks():
    loop = make_loop()
    loop.run_until(3)
    seen = loop.last_views["Alex"].inbox  # sent at tick 2, read at tick 3
    assert sorted((m.sender, m.tick) for m in seen) == [("Blake", 2), ("Casey", 2)]
    assert loop.inbox["Alex"] == [] and loop.last_views["Blake"].unanswered == []
    loop.run_until(6)
    unanswered = loop.last_views["Blake"].unanswered
    assert [(u.to, u.since_tick) for u in unanswered] == [("Alex", 2)]


def test_lunch_makes_talk_sessions_and_their_outcomes_reach_the_agents():
    loop = make_loop()
    loop.run()
    talks = [m for m in loop.sessions.values() if m["kind"] == "talk"]
    assert talks and all(m["public"] and m["end"] is not None for m in talks)
    assert all(len(loop.threads[m["id"]].utterances) >= 1 for m in talks)
    assert any(agent.state.relations for agent in loop.agents)
    outcome_events = [e for e in loop.events if e.kind == "outcome"]
    assert outcome_events and "relation_delta" in outcome_events[0].payload


def test_agents_in_a_live_session_do_not_act_and_sessions_close_at_phase_end():
    loop = make_loop()
    loop.run_until(17)
    busy = set(loop.busy)
    assert busy, "a lunch talk should be live after tick 17"
    loop.run_until(18)
    acted = {e.actor for e in loop.events if e.kind == "action" and e.tick == 18}
    assert not busy & acted
    loop.run_until(20)
    assert all(m["end"] is not None for m in loop.sessions.values() if m["kind"] == "talk")


def test_every_tick_is_handed_to_storage_with_embedded_records():
    recorder = Recorder()
    loop = make_loop(writer=recorder)
    loop.run()
    assert len(recorder.ticks) == 32
    assert all(vector is not None for _, rows, _ in recorder.ticks for _, vector in rows)
    assert all(events and rows for events, rows, _ in recorder.ticks)
    assert all(not agent.memory.pending_writes for agent in loop.agents)
    assert all(r.id in agent.memory.vectors for agent in loop.agents for r in agent.memory.records)


def test_same_seed_same_events():
    runs = []
    for _ in range(2):
        loop = make_loop()
        loop.run()
        runs.append([e.model_dump() for e in loop.events])
    assert runs[0] == runs[1]
