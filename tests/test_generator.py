import copy
import json

import pytest

from conflict_sim.generator import MAX_FIXES, DraftBusy, Drafts, turn, view
from conflict_sim.llm import LLMError
from conflict_sim.scenario_draft import version_from_scenario


class FakeLLM:
    """Scripted JSON replies in order; records what it was sent; spends 10 tokens a call."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []
        self.usage = {"decide": {"total_tokens": 0}}

    def complete(self, *, system, prompt, model, temperature, json_mode, schema=None):
        self.calls.append({"system": system, "prompt": prompt})
        self.usage["decide"]["total_tokens"] += 10
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def router(next_step, reply="", settings=None):
    return json.dumps({"reply": reply, "next": next_step, "settings": settings or {}})


def ops(*items, reply="ok"):
    return json.dumps({"reply": reply, "ops": list(items)})


def _r10_as_scratch_json(edit=None):
    doc = version_from_scenario("r10_human").model_dump(mode="json")
    if edit:
        edit(doc)
    return json.dumps(doc["company"], ensure_ascii=False), json.dumps(doc["scenario"])


RUDE = {
    "op": "replace",
    "path": "/variant/company/people/2/communication_style",
    "value": "피드백할 때 깎아내리고 비꼬는 말을 쓴다.",
}


def test_a_vague_request_gets_a_question_and_no_version(tmp_path):
    d = Drafts(tmp_path).create("scratch", None)
    d = turn(d, "실험하고 싶어", [], FakeLLM([router("ask", reply="무엇을 비교할까요?")]), "m")
    assert d["messages"][0] == {"role": "user", "text": "실험하고 싶어", "tokens": 0}
    assert d["messages"][-1] == {"role": "ai", "text": "무엇을 비교할까요?", "tokens": 10}
    assert d["versions"]["baseline"] is None


def test_scratch_with_a_pair_builds_both_versions_that_pass(tmp_path):
    company, scenario = _r10_as_scratch_json()
    llm = FakeLLM(
        [
            router("generate", settings={"pair": True, "factor": "disposition"}),
            company,
            scenario,
            ops(RUDE),
        ]
    )
    d = turn(Drafts(tmp_path).create("scratch", None), "…", [], llm, "m")
    v = view(d)
    assert v["checks"] == {"baseline": [], "variant": []}
    assert {x["factor"] for x in v["diff"]} == {"disposition"} and v["outside"] == []
    assert set(v["files"]) == {"baseline", "variant"}
    assert "scenario/company_c15/gen_preview.yaml" in v["files"]["variant"]
    assert [m["role"] for m in d["messages"]] == ["user", "check", "check", "ai"]
    assert d["messages"][-1]["tokens"] == 40 and llm.replies == []
    json.dumps(v)  # the server sends it as is


def test_a_change_outside_the_chosen_factor_is_listed(tmp_path):
    d = Drafts(tmp_path).create("variant", "r10_human")
    llm = FakeLLM([router("generate", settings={"factor": "work"}), ops(RUDE)])
    v = view(turn(d, "업무량을 바꿔줘", [], llm, "m"))
    assert v["outside"] and {x["factor"] for x in v["outside"]} == {"disposition"}


def test_engine_errors_go_back_to_the_model_until_fixed(tmp_path):
    def nobody(doc):
        doc["company"]["tasks"][0]["owner"] = "NOBODY"

    company, scenario = _r10_as_scratch_json(nobody)
    owner = version_from_scenario("r10_human").company.tasks[0].owner
    fix = json.dumps({"ops": [{"op": "replace", "path": "/company/tasks/0/owner", "value": owner}]})
    llm = FakeLLM([router("generate"), company, scenario, fix])
    d = turn(Drafts(tmp_path).create("scratch", None), "만들어줘", [], llm, "m")
    assert "NOBODY" in llm.calls[3]["prompt"]
    checks = [m["text"] for m in d["messages"] if m["role"] == "check"]
    assert checks == ["형식 검사(baseline): 오류 1개 → 자동 수정 1번 → 통과"]
    assert view(d)["checks"] == {"baseline": [], "variant": None}


def test_a_version_that_never_passes_is_kept_and_reported(tmp_path):
    def nobody(doc):
        doc["company"]["tasks"][0]["owner"] = "NOBODY"

    company, scenario = _r10_as_scratch_json(nobody)
    bad_fix = json.dumps({"ops": [{"op": "replace", "path": "/company/nope/9", "value": 1}]})
    llm = FakeLLM([router("generate"), company, scenario, *[bad_fix] * MAX_FIXES])
    d = turn(Drafts(tmp_path).create("scratch", None), "만들어줘", [], llm, "m")
    assert llm.replies == []
    last_check = [m["text"] for m in d["messages"] if m["role"] == "check"][-1]
    assert "통과하지 못함" in last_check and "NOBODY" in last_check
    v = view(d)
    assert v["checks"]["baseline"] != [] and d["versions"]["baseline"] is not None
    assert v["files"] == {} and v["diff"] == []


def test_a_variant_may_not_touch_its_baseline(tmp_path):
    d = Drafts(tmp_path).create("variant", "r10_human")
    before = d["versions"]["baseline"]
    llm = FakeLLM(
        [
            router("edit"),
            ops(
                {"op": "replace", "path": "/baseline/company/organization", "value": "X"}, reply="x"
            ),
        ]
    )
    d = turn(d, "회사 이름 바꿔줘", [], llm, "m")
    assert d["versions"]["baseline"] == before and "baseline" in d["messages"][-1]["text"]


def test_a_patch_to_a_missing_path_changes_nothing(tmp_path):
    d = Drafts(tmp_path).create("variant", "r10_human")
    before = copy.deepcopy(d["versions"])
    llm = FakeLLM(
        [
            router("edit"),
            ops(
                {"op": "add", "path": "/variant", "value": before["baseline"]},
                {"op": "replace", "path": "/variant/company/nope/3", "value": "X"},
            ),
        ]
    )
    d = turn(d, "고쳐줘", [], llm, "m")
    assert d["versions"] == before and "/variant/company/nope/3" in d["messages"][-1]["text"]


def test_an_edit_changes_only_the_version_it_names(tmp_path):
    company, scenario = _r10_as_scratch_json()
    llm = FakeLLM(
        [
            router("generate", settings={"pair": True, "factor": "disposition"}),
            company,
            scenario,
            ops(),
            router("edit"),
            ops(RUDE, reply="바꿨습니다"),
        ]
    )
    drafts = Drafts(tmp_path)
    d = turn(drafts.create("scratch", None), "만들어줘", [], llm, "m")
    d = turn(d, "세 번째 사람을 무례하게", [], llm, "m")
    assert d["messages"][-2:] == [
        {"role": "check", "text": "형식 검사(variant): 오류 0개 → 통과", "tokens": 0},
        {"role": "ai", "text": "바꿨습니다", "tokens": 20},
    ]
    assert {x["factor"] for x in view(d)["diff"]} == {"disposition"}


def test_the_prompt_carries_the_writing_guide_and_the_materials(tmp_path):
    company, scenario = _r10_as_scratch_json()
    llm = FakeLLM([router("generate"), company, scenario])
    spec = {"name": "spec.md", "text": "# 결제 모듈\n연동 가구 42만"}
    d = turn(Drafts(tmp_path).create("scratch", None), "자료로 만들어줘", [spec], llm, "m")
    assert d["materials"] == [spec]
    system = llm.calls[0]["system"]
    assert "갈등은 구조에서 나오게 한다" in system and "meeting_room" in system and "P01" in system
    assert "spec.md" in llm.calls[1]["prompt"] and "연동 가구 42만" in llm.calls[1]["prompt"]
    assert "spec.md" in d["messages"][0]["text"]


def test_a_turn_leaves_its_input_alone_and_an_llm_failure_raises(tmp_path):
    d = Drafts(tmp_path).create("variant", "r10_human")
    before = copy.deepcopy(d)
    turn(d, "?", [], FakeLLM([router("ask", reply="무엇을?")]), "m")
    assert d == before
    with pytest.raises(LLMError):
        turn(d, "?", [], FakeLLM([LLMError("Run token budget reached")]), "m")
    assert d == before


def test_router_settings_join_the_draft(tmp_path):
    experiment = {
        "id": "rude-01",
        "factor": "disposition",
        "hypothesis": "상대의 스트레스가 오른다.",
        "measures": [{"metric": "stress", "subject": "partners_of:P03", "direction": "up"}],
        "behaviour_checks": ["P03이 비꼬는 말을 했는가"],
    }
    settings = {"title": "무례한 피드백", "pair": True, "factor": "disposition"}
    llm = FakeLLM([router("ask", settings={**settings, "experiment": experiment})])
    d = turn(Drafts(tmp_path).create("scratch", None), "…", [], llm, "m")
    assert {k: d[k] for k in settings} == settings and d["experiment"] == experiment


def test_drafts_are_stored_listed_and_loaded(tmp_path):
    drafts = Drafts(tmp_path)
    a = drafts.create("scratch", None)
    b = drafts.create("variant", "r10_human")
    assert a["id"].startswith("d-") and len(a["id"]) == len("d-20261110-1432-ab12")
    assert b["versions"]["baseline"] == version_from_scenario("r10_human").model_dump(mode="json")
    assert drafts.load(b["id"]) == b
    a["title"] = "첫 초안"
    drafts.write(a)
    assert drafts.load(a["id"])["title"] == "첫 초안"
    assert [x["id"] for x in drafts.listing()] == [a["id"], b["id"]]
    assert set(drafts.listing()[0]) == {"id", "title", "mode", "updated", "saved"}
    with pytest.raises(KeyError):
        drafts.load("d-20990101-0000-0000")
    with pytest.raises(KeyError):
        drafts.load("../secrets")


def test_a_held_draft_is_busy(tmp_path):
    drafts = Drafts(tmp_path)
    d = drafts.create("scratch", None)
    with drafts.busy(d["id"]):
        with pytest.raises(DraftBusy):
            with drafts.busy(d["id"]):
                pass
    with drafts.busy(d["id"]):
        pass
