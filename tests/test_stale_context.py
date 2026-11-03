"""What an agent is told must match how things stand when it acts, not when it planned
(r10_midweek v2, HDS-008: a planned "done" message, a return remembered without its reason, a
return that did not re-plan, a colleague's task credited to oneself)."""

import json

from test_agent import FakeLLM, make_agent, view

from conflict_sim.agent import human as hm
from conflict_sim.agent.agent import RETURNED_IMPORTANCE, _basis
from conflict_sim.company_runtime import build_company_config
from conflict_sim.models import Outcome, TaskView


def test_a_review_return_is_remembered_with_what_was_missing():
    agent = make_agent(FakeLLM("{}"))
    outcome = Outcome(session_id="action:28:R", public=False, refused=["R"])
    agent.apply_outcome(outcome, 28, ("api", "The cache rule is still an assumption."))
    record = agent.memory.records[-1]
    assert record.description == (
        "R returned api after review: The cache rule is still an assumption."
    )
    assert record.importance == RETURNED_IMPORTANCE

    agent.apply_outcome(Outcome(session_id="s", public=False, refused=["R"]), 29)
    assert agent.memory.records[-1].description == "R refused my request."  # a refused request


def test_a_return_reads_as_one_in_the_human_prompt():
    d = hm.Directory(build_company_config("r10_midweek"))
    why = "오프라인 캐시 기준이 가정으로 남아 있어요."
    text = d.humanize(f"HDS-005 returned T08 after review: {why}")
    assert text == f"정태우가 검토에서 '웹·모바일 구현'을 돌려보냈다: {why}"


def test_a_return_re_plans_at_once_even_after_a_round_trip_through_review():
    agent = make_agent(FakeLLM("{}"))
    once = [
        TaskView(
            id="api",
            description="Ship it",
            owner="B",
            progress=0.9,
            due=28,
            lifecycle="in_progress",
            rejections=[{"by": "R", "tick": 18, "note": "x"}],
        )
    ]
    agent._planned_tick, agent._basis = 20, _basis(agent._known(view(tick=20, tasks=once)))
    # Sent to review at 24 and back at 28: the same lifecycle as at the plan, one more return.
    twice = [once[0].model_copy(update={"rejections": once[0].rejections * 2})]
    now = view(tick=22, phase="morning", tasks=twice)  # inside the re-plan cooldown
    assert agent.replan_reason(now, 22) == "api came back from review"
    assert agent.replan_reason(now, 23) is None  # heard once


def test_the_day_review_says_who_did_finished_work():
    llm = FakeLLM(json.dumps({"insights": []}))
    agent = make_agent(llm)
    done = [
        TaskView(
            id="dark",
            description="Contrast fix",
            owner="B",
            progress=1.0,
            due=28,
            lifecycle="done",
            record={"worked_by": {"C": 2}},
        )
    ]
    agent.end_day(31, view(tick=31, tasks=done))
    status = json.loads(llm.requests[-1]["prompt"])["task_status"]
    assert status[0]["worked_by"] == {"C": 2}
