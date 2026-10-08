"""The human prompt style: names and titles in, ids out, and only what a person could know."""

import json
import random
import re

import pytest

from conflict_sim.agent import Agent
from conflict_sim.agent import human as hm
from conflict_sim.company_runtime import apply_initial_relationships, build_company_config
from conflict_sim.environment import Environment
from conflict_sim.experiment import run_scenario
from conflict_sim.llm import DemoBackend
from conflict_sim.loop import Loop
from conflict_sim.models import PlanItem, Thread, Utterance

ENGINE_ID = re.compile(r"HDS-\d{3}|(?<![A-Za-z0-9])(T\d{2}|P\d{1,2}-[a-z]+)(?![A-Za-z0-9-])")


class Recorder:
    def write_tick(self, events, memory_rows, retrieval_rows):
        pass

    def write_checkpoint(self, day, data):
        pass


class Capture(DemoBackend):
    """The demo's answers, with every request kept."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.calls = []

    def complete(self, **request):
        self.calls.append(request)
        return super().complete(**request)


def world(ticks=8):
    cfg = build_company_config("r10_human")
    llm = Capture(
        blocked_nudge_ticks=cfg.blocked_nudge_ticks,
        blocked_report_ticks=cfg.blocked_report_ticks,
    )
    agents = [Agent(spec, cfg, llm) for spec in cfg.agents]
    apply_initial_relationships(agents)
    loop = Loop(cfg, agents, Environment(cfg.environment, cfg.agents), llm,
                random.Random(cfg.random_seed), Recorder())  # fmt: skip
    for tick in range(ticks):
        loop.tick(tick)
        loop.tick_now = tick + 1
    return cfg, loop, llm


def test_ids_become_names_and_titles_with_fitting_particles():
    d = hm.Directory(build_company_config("r10_human"))
    text = d.humanize("HDS-005 wrote to me: T06은 T03이 끝나야 해요. P1-arch를 먼저 봐 주세요.")
    assert text == (
        "정태우가 내게 보냄: 'API 계약'은 '요구사항 명세'가 끝나야 해요. "
        "'결제 서비스 - 결제 아키텍처 설계'를 먼저 봐 주세요."
    )
    assert (
        d.reason("T10 is blocked by T07")
        == "'통합 후보 빌드'은(는) '백엔드 구현'이(가) 끝나야 할 수 있다"
    )
    assert "이미 물어봤다" in d.reason(
        "already asked HDS-008 about the blocked work at tick 3; wait"
    )
    assert d.clock(34 + 6, 34) == "10:30" and d.tick_of("10:30", 34) == 40


def test_a_choice_in_names_and_titles_maps_back_to_ids():
    cfg, loop, _ = world(ticks=2)
    d, view = hm.Directory(cfg), loop._view(loop.agent("HDS-001"), 2, 0, "morning")
    reply = {
        "thought": "유진님한테 물어보자.",
        "kind": "message",
        "task": None,
        "person": "오유진",
        "people": [],
        "about": None,
        "place": None,
        "say": "유진님, 빌드 언제쯤 돼요?",
        "rating": None,
        "face": "neutral",
        "importance": 4,
        "valence": 0,
        "arousal": 0.2,
    }
    action = hm.to_action(d, reply, view)
    assert (action.kind, action.target, action.text) == (
        "message",
        "HDS-008",
        "유진님, 빌드 언제쯤 돼요?",
    )
    assign = hm.to_action(d, reply | {"kind": "assign", "task": "API 계약", "person": None,
                                      "people": ["윤지호", "오유진"]}, view)  # fmt: skip
    assert (assign.task, assign.target, assign.targets) == ("T06", "HDS-006", ["HDS-008"])
    prepare = hm.to_action(d, reply | {"kind": "prepare", "task": "API 계약", "person": None}, view)
    assert (prepare.kind, prepare.task) == ("rest", None) and "API 계약 준비" in prepare.reflection
    engine = {"kind": "rest", "expression": "neutral", "reflection": "-", "importance": 1,
              "valence": 0, "arousal": 0}  # fmt: skip
    assert hm.to_action(d, engine, view).kind == "rest"  # the demo's engine-shaped reply
    block = {
        "kind": "work",
        "task": "고객 리서치 - 고객 인터뷰 계획 수립",
        "person": None,
        "people": [],
        "about": None,
        "place": None,
        "until": "10:30",
        "text": "인터뷰 계획부터.",
    }
    plan = hm.to_plan(d, {"plan": [block]}, view, 2)
    assert (plan[0].task, plan[0].until) == ("P12-plan", 6)


def test_a_reply_label_is_the_utterance_id():
    thread = Thread([Utterance(id="dm:HDS-001:HDS-002:0", speaker="HDS-001", text="hi",
                               reply_to=None, timestamp=0)])  # fmt: skip
    _, loop, _ = world(ticks=1)
    d = hm.Directory(loop.cfg)
    _, labels = hm.thread_text(d, loop.agent("HDS-002"), thread, 0, "message", None, [])
    decision = hm.decision_from({"urge": 0.5, "reply_to": "#0", "reflection": "답하자.",
                                 "expression": "neutral", "importance": 3, "valence": 0,
                                 "arousal": 0}, labels)  # fmt: skip
    assert decision.reply_to == "dm:HDS-001:HDS-002:0"


def test_narrative_prompts_carry_no_engine_ids_and_no_one_elses_task_state():
    _, loop, llm = world(ticks=10)
    agent = loop.agent("HDS-006")
    view = loop._view(agent, 10, 0, "morning")
    agent._judge(None, agent._known(view), 10)  # an act call, judged now
    narrative = [c for c in llm.calls if not c["prompt"].lstrip().startswith("{")]
    # act, plan and speech so far (a decide needs a direct-message session, tested above)
    assert {c["schema"].__name__ if c["schema"] else None for c in narrative} >= {
        "HumanAction", "HumanPlan", None,
    }  # fmt: skip
    for call in narrative:
        assert not ENGINE_ID.search(call["system"]), call["system"][:200]
        # Demo-written memories and documents still say "Work on …" or "T06-1"; ids are gone.
        assert not re.search(r"HDS-\d{3}", call["prompt"]), call["prompt"][:400]
        # engine field names and state values (demo summaries say "ready for review" in English)
        assert not re.search(r"lifecycle|can_work|remaining_ticks|in_progress|\"ready\"",
                             call["prompt"])  # fmt: skip


@pytest.mark.parametrize("style", ["human"])
def test_the_human_scenario_runs_a_day_on_the_demo_backend(tmp_path, style):
    summary = run_scenario("r10_human", tmp_path / style)
    assert summary["run_status"] == "completed" and summary["agents"] == 10
    events = [json.loads(line) for line in (tmp_path / style / "events.jsonl").open()]
    assert sum(e["kind"] == "action" for e in events) > 200


def test_a_lunch_an_hour_off_is_moved_onto_lunch():
    plan = [
        PlanItem(kind="work", task="T01", until=12, text="a"),
        PlanItem(kind="eat", place="cafeteria", until=20, text="b"),  # 12-19, lunch is 16-19
        PlanItem(kind="work", task="T01", until=32, text="c"),
    ]
    fitted = hm.fit_lunch(plan, 0, 16)
    assert [(i.kind, i.until) for i in fitted] == [("work", 16), ("eat", 20), ("work", 32)]
    late = [PlanItem(kind="work", task="T01", until=20, text="a"),
            PlanItem(kind="eat", place="cafeteria", until=24, text="b"),  # 20-23
            PlanItem(kind="work", task="T01", until=32, text="c")]  # fmt: skip
    assert [(i.kind, i.until) for i in hm.fit_lunch(late, 0, 16)] == [
        ("work", 16), ("eat", 20), ("work", 32),
    ]  # fmt: skip


def test_what_i_asked_is_one_line_per_person_with_how_often_and_the_last_answer():
    _, loop, _ = world(ticks=1)
    agent, d = loop.agent("HDS-015"), hm.Directory(loop.cfg)
    agent._recent = []
    agent._asked = [
        {"to": "HDS-008", "about": ["T11"], "tick": 20, "said": "-", "reply": None},
        {"to": "HDS-014", "about": ["T11"], "tick": 22, "said": "-", "reply": "기다려요."},
        {"to": "HDS-008", "about": ["T10", "T11"], "tick": 23, "said": "-", "reply": None},
        {"to": "HDS-008", "about": ["T11"], "tick": 26, "said": "-", "reply": None},
    ]
    lines = [x for x in hm._what_i_did(d, agent, 30) if x.startswith("- ")]
    assert lines == [
        "- 14:30 서동현에게 '품질 검증' 관련해 물어봄 → 마지막 답: \"기다려요.\"",
        "- 14:00~15:30 오유진에게 '품질 검증', '통합 후보 빌드' 관련해 3번 물어봄 → 아직 답이 없다",
    ]
    assert d.span(20, 26, 40) == "어제 14:00~15:30"
    assert d.clock(20, 40 + 34) == "2일 전 14:00"


def test_evaluate_is_offered_only_in_an_evaluation_season():
    assert "- evaluate:" not in hm.act_head() and "- evaluate:" in hm.act_head(evaluation=True)
