import random

import pytest

from conflict_sim.agent import Agent
from conflict_sim.company_runtime import (
    _validate_weekly_calendar,
    build_company_config,
    load_c15_scenario,
)
from conflict_sim.environment import Environment
from conflict_sim.llm import DemoBackend
from conflict_sim.loop import Loop, phase_of
from conflict_sim.models import Action
from conflict_sim.operations import business_ticks


class Recorder:
    def __init__(self):
        self.events = []

    def write_tick(self, events, memory_rows, retrieval_rows):
        self.events.extend(events)

    def write_checkpoint(self, day, data):
        pass


def runtime():
    cfg = build_company_config("r10_enterprise_weekly")
    backend = DemoBackend()
    agents = [Agent(a, cfg, backend) for a in cfg.agents]
    env = Environment(cfg.environment, cfg.agents)
    return Loop(cfg, agents, env, backend, random.Random(7), Recorder())


def action(kind, **kw):
    return Action(
        kind=kind,
        expression="neutral",
        reflection=kw.pop("reflection", "Test"),
        importance=3,
        valence=0,
        arousal=0,
        **kw,
    )


def test_six_workdays_explicit_lunch_and_single_minutes_owner():
    cfg = build_company_config("r10_enterprise_weekly")
    assert cfg.n_agents == 10 and cfg.max_days == 6 and cfg.ticks_per_day == 36
    assert [phase_of(t, 36, 2, 16) for t in range(16, 20)] == ["lunch"] * 4
    minutes = [t for t in cfg.environment.org.tasks if t.id.startswith("MIN-")]
    assert len(minutes) == 10 and len({t.id for t in minutes}) == 10
    assert all(t.owner and not t.contributors for t in minutes)
    assert not build_company_config("r10_midweek").weekly_operations


def test_break_cap_includes_leads_across_places_and_resets_each_tick():
    loop = runtime()
    env = loop.env
    env.advance(2)
    for name, place in zip(["HDS-001", "HDS-002", "HDS-005"], ["lobby", "pantry", "cafeteria"]):
        assert env.apply(name, action("rest", place=place), 2) is None
    assert env.apply("HDS-003", action("rest"), 2) is not None
    assert env.apply("HDS-003", action("rest", reflection="[preparation] research"), 2) is None
    env.advance(3)
    assert env.apply("HDS-003", action("rest"), 3) is None


def test_lunch_overnight_and_overtime_do_not_count_as_waiting():
    assert business_ticks(16, 36, 38, 16) == business_ticks(20, 36, 38, 16) == 16
    assert business_ticks(36, 36, 38, 16) == business_ticks(38, 36, 38, 16) == 32
    assert business_ticks(54, 36, 38, 16) == 48


def test_waiting_carries_next_day_and_reminds_once_then_escalates():
    loop = runtime()
    # PRICE design waits on PRICE requirements, owned by another team.
    loop.env.advance(24)
    query = action("message", target="HDS-003", text="요구사항 진행 상황을 알려 주세요.")
    assert loop._apply(loop.agent("HDS-013"), query, 24, 0) is None
    assert loop.env.apply("HDS-013", query, 30) is not None
    loop._request_followups(41, 1)  # 15 working ticks, not yet half a workday
    assert not loop.requests["HDS-013>HDS-003"]["reminded"]
    loop._request_followups(42, 1)
    assert loop.requests["HDS-013>HDS-003"]["reminded"]
    loop._request_followups(43, 1)
    assert loop.env.chase_counts["HDS-013>HDS-003"] == 2
    loop._request_followups(62, 1)  # a full working day after tick 24
    assert loop.requests["HDS-013>HDS-003"]["escalated"]
    assert len([e for e in loop._events if e.payload.get("kind") == "unanswered_escalation"]) == 1
    saved = loop.checkpoint()
    restored = runtime()
    restored.restore(saved, {})
    assert restored.requests == loop.requests
    assert restored.env.chase_counts == loop.env.chase_counts
    loop._send(loop.agent("HDS-003"), action("message", target="HDS-013", text="답변"), 67, 1)
    assert "HDS-013>HDS-003" not in loop.requests


def test_calendar_reserves_external_meeting_without_an_executive_agent():
    loop = runtime()
    reserved, worked = loop._calendar(9, 0)
    assert reserved == {"HDS-001"} and not worked
    assert len(loop.agents) == 10
    assert (
        loop.env.apply("HDS-002", action("talk", targets=["HDS-001"], text="질문"), 9) is not None
    )
    assert loop.env.apply("HDS-003", action("leave"), 9) is not None


def test_priority_revision_keeps_work_and_changes_only_explicit_tasks():
    loop = runtime()
    detailed = loop.env.org.tasks["DETAIL-analysis"]
    detailed.worked = 1.5
    original = loop.env.org.tasks["T07"].due
    loop._calendar(24, 0)
    assert detailed.worked == 1.5 and detailed.forced_block_until == 228
    assert loop.env.org.tasks["T07"].due == original
    saved = loop.env.snapshot()
    restored = runtime()
    restored.env.restore(saved)
    assert restored.env.org.tasks["DETAIL-analysis"].forced_block_until == 228


def test_cross_team_help_requires_matching_skill():
    loop = runtime()
    env = loop.env
    assert env.apply("HDS-006", action("help", task="DETAIL-analysis"), 2) is not None
    assert env.apply("HDS-002", action("help", task="DETAIL-analysis"), 2) is None


def test_calendar_rejects_overlap_before_a_run():
    scenario = load_c15_scenario("r10_enterprise_weekly")
    cfg = build_company_config("r10_enterprise_weekly")
    first = scenario.weekly_operations.blocks[0]
    policy = scenario.weekly_operations.model_copy(update={"blocks": [first, first]})
    scenario = scenario.model_copy(update={"weekly_operations": policy})
    with pytest.raises(ValueError, match="Overlapping"):
        _validate_weekly_calendar(scenario, cfg.agents, cfg.environment.org.tasks)


def test_standup_survives_arrival_phase_boundary():
    loop = runtime()
    loop.run_until(1)
    sid = "meeting:standup-0:0"
    assert loop.sessions[sid]["end"] == 1
    assert any(
        e.session == sid and e.payload.get("end") == "scheduled_end" for e in loop.writer.events
    )
