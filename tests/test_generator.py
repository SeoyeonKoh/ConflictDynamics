import copy
import json

import pytest

from conflict_sim.company_runtime import build_company_config, load_c15_scenario
from conflict_sim.generator import MAX_FIXES, DraftBusy, Drafts, SaveRefused, save, turn, view
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
    "path": "/variant/company/people/HDS-003/communication_style",
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
    task = version_from_scenario("r10_human").company.tasks[0]
    fix = json.dumps(
        {"ops": [{"op": "replace", "path": f"/company/tasks/{task.id}/owner", "value": task.owner}]}
    )
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
    llm = FakeLLM([router("ask", settings={"experiment": {**experiment, "factor": "work"}})])
    assert turn(d, "…", [], llm, "m")["experiment"]["factor"] == "disposition"  # the draft's


def test_a_variant_answer_may_fill_the_experiment(tmp_path):
    """The router may leave the experiment out; the variant call then gives it in settings."""
    experiment = {
        "id": "rude_feedback",
        "hypothesis": "관계가 나빠진다.",
        "measures": [
            {"metric": "relation", "subject": "all", "toward": "all", "direction": "down"}
        ],
        "behaviour_checks": ["HDS-003이 깎아내리는 말을 했는가"],
    }
    answer = json.dumps({"reply": "ok", "ops": [RUDE], "settings": {"experiment": experiment}})
    llm = FakeLLM([router("generate", settings={"factor": "disposition"}), answer])
    d = turn(Drafts(tmp_path).create("variant", "r10_human"), "…", [], llm, "m")
    assert d["experiment"] == {**experiment, "factor": "disposition"}
    assert d["versions"]["variant"] is not None


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
    (tmp_path / "d-20990101-0000-abcd.json").write_text("{half a fi", "utf-8")
    assert len(drafts.listing()) == 2  # an unreadable file is skipped, not fatal


def _pair(tmp_path, name="r10_human", edit=None):
    """A scratch draft whose pair was generated from an existing scenario."""
    company, scenario = _r10_as_scratch_json(edit) if name == "r10_human" else _scratch(name, edit)
    llm = FakeLLM([router("generate", settings={"pair": True, "factor": "disposition"})])
    llm.replies += [company, scenario, ops()]
    return turn(Drafts(tmp_path).create("scratch", None), "만들어줘", [], llm, "m")


def _scratch(name, edit):
    doc = version_from_scenario(name).model_dump(mode="json")
    edit(doc)
    return json.dumps(doc["company"], ensure_ascii=False), json.dumps(doc["scenario"])


def test_a_baseline_only_edit_on_a_pair_is_pointed_out(tmp_path):
    d = _pair(tmp_path)
    variant = d["versions"]["variant"]
    rename = {"op": "replace", "path": "/baseline/company/organization", "value": "새 회사"}
    llm = FakeLLM([router("edit"), ops(rename, reply="바꿨어요")])
    d = turn(d, "회사 이름 바꿔줘", [], llm, "m")
    assert "두 버전 모두에 적용했어요" in llm.calls[1]["system"]  # the rule the model is given
    assert d["versions"]["baseline"]["company"]["organization"] == "새 회사"
    assert d["versions"]["variant"] == variant
    assert d["messages"][-1]["text"].endswith("baseline만 바뀌었어요 — 비교군과 다른 점에 나타나요")


def _long_materials(doc):
    doc["scenario"]["materials"] = {
        task["id"]: f"{task['id']} 자료 " + "가" * 50_000 for task in doc["company"]["tasks"]
    }


def test_a_big_attachment_keeps_every_prompt_under_the_server_limit(tmp_path):
    big = {"name": "big.md", "text": "x" * 1_000_000}
    company, scenario = _scratch("p0_documents_ko", _long_materials)
    llm = FakeLLM(
        [router("generate", settings={"pair": True, "factor": "disposition"})]
        + [company, scenario, ops(), router("edit"), ops()]
    )
    d = turn(Drafts(tmp_path).create("scratch", None), "x" * 50_000, [big], llm, "m")
    d = turn(d, "고쳐줘", [], llm, "m")
    assert llm.replies == [] and d["messages"][-1]["role"] == "ai"
    assert max(len(c["system"]) + len(c["prompt"]) for c in llm.calls) < 400_000
    assert "…(trimmed " in llm.calls[-1]["prompt"] and "가" * 1000 not in llm.calls[-1]["prompt"]
    assert d["materials"] == [big]  # trimmed only in what the model is sent


def test_ops_that_copy_a_shortened_text_are_refused(tmp_path):
    d = _pair(tmp_path, edit=_long_materials)
    before = copy.deepcopy(d["versions"])
    task = before["baseline"]["company"]["tasks"][0]["id"]
    copied = {
        "op": "replace",
        "path": f"/variant/scenario/materials/{task}",
        "value": "T01 자료 가가…(trimmed 49990 chars)",
    }
    d = turn(d, "자료 고쳐줘", [], FakeLLM([router("edit"), ops(copied)]), "m")
    assert d["versions"] == before and "trimmed" in d["messages"][-1]["text"]


def test_a_held_draft_is_busy(tmp_path):
    drafts = Drafts(tmp_path)
    d = drafts.create("scratch", None)
    with drafts.busy(d["id"]):
        with pytest.raises(DraftBusy):
            with drafts.busy(d["id"]):
                pass
    with drafts.busy(d["id"]):
        pass


@pytest.fixture
def tmp_conf(tmp_path, monkeypatch):
    """A copy of conf/ that saving may write into."""
    import shutil

    import conflict_sim.company as company
    import conflict_sim.company_runtime as runtime

    conf = tmp_path / "conf"
    shutil.copytree(company.CONF_DIR, conf)
    monkeypatch.setattr(company, "CONF_DIR", conf)
    monkeypatch.setattr(runtime, "CONF_DIR", conf)
    monkeypatch.setattr("conflict_sim.runs._CATALOG", {})
    return conf


EXPERIMENT = {"id": "rude", "factor": "disposition", "hypothesis": "h", "behaviour_checks": ["c"]}


def _passing_pair_draft(tmp_path, title="rude feedback"):
    d = _pair(tmp_path, edit=None)
    # the variant differs from the baseline in a disposition field
    d["versions"]["variant"]["company"]["people"][2]["communication_style"] = "깎아내리고 비꼰다."
    return {**d, "title": title, "factor": "disposition", "experiment": dict(EXPERIMENT)}


def _names(conf):
    return sorted(p.stem for p in (conf / "scenario" / "company_c15").glob("gen_*.yaml"))


def test_saving_writes_new_files_and_never_overwrites(tmp_path, tmp_conf):
    d = _passing_pair_draft(tmp_path)
    before = copy.deepcopy(d)
    d1 = save(d, tmp_conf, accept_outside=False)
    assert d == before  # the argument is not changed
    assert d1["saved"] == ["gen_rude_feedback_base", "gen_rude_feedback_var"]
    d2 = save(d1, tmp_conf, accept_outside=False)
    assert d2["saved"] == ["gen_rude_feedback_base_2", "gen_rude_feedback_var_2"]
    assert build_company_config("gen_rude_feedback_var").scenario
    assert load_c15_scenario("gen_rude_feedback_var").experiment.role == "variant"
    assert load_c15_scenario("gen_rude_feedback_base_2").experiment.id == "rude_2"
    assert (tmp_conf / "personas" / "gen_rude_feedback_base_2.yaml").is_file()


def test_a_scratch_pair_is_linked_by_id_and_baseline(tmp_path, tmp_conf):
    d = save(_passing_pair_draft(tmp_path), tmp_conf, accept_outside=False)
    base, var = (load_c15_scenario(n).experiment for n in d["saved"])
    assert (base.id, base.role, base.baseline) == ("rude", "baseline", "gen_rude_feedback_base")
    assert (var.id, var.role, var.baseline) == ("rude", "variant", "gen_rude_feedback_base")
    assert var.factor == "disposition" and var.hypothesis == "h" and var.behaviour_checks == ["c"]
    again = save(d, tmp_conf, accept_outside=False)
    base2, var2 = (load_c15_scenario(n).experiment for n in again["saved"])
    assert base2.id == var2.id == "rude_2"
    assert base2.baseline == var2.baseline == "gen_rude_feedback_base_2"


def test_a_variant_save_names_its_source_as_the_baseline(tmp_path, tmp_conf):
    d = Drafts(tmp_path).create("variant", "r10_human")
    variant = copy.deepcopy(d["versions"]["baseline"])
    variant["scenario"]["research_question"] = "다른 질문"
    d = {**d, "title": "q", "factor": "work", "experiment": {**EXPERIMENT, "factor": "work"},
         "versions": {"baseline": d["versions"]["baseline"], "variant": variant}}  # fmt: skip
    experiment = load_c15_scenario(save(d, tmp_conf, accept_outside=True)["saved"][0]).experiment
    assert (experiment.id, experiment.role, experiment.factor) == ("rude", "variant", "work")
    assert experiment.baseline == "r10_human"


def test_a_draft_without_an_experiment_still_writes_the_pair_link(tmp_path, tmp_conf):
    d = {**_passing_pair_draft(tmp_path), "experiment": None}
    d = save(d, tmp_conf, accept_outside=False)
    for name, role in zip(d["saved"], ("baseline", "variant")):
        experiment = load_c15_scenario(name).experiment
        assert (experiment.id, experiment.role, experiment.factor) == (
            "rude_feedback", role, "disposition")  # fmt: skip
        assert experiment.baseline == "gen_rude_feedback_base"


def test_a_korean_title_takes_its_name_from_the_experiment_id(tmp_path, tmp_conf):
    d = _passing_pair_draft(tmp_path, title="무례한 피드백")
    d["experiment"]["id"] = "rude-feedback"
    assert save(d, tmp_conf, accept_outside=False)["saved"] == [
        "gen_rude_feedback_base", "gen_rude_feedback_var"]  # fmt: skip
    long = _passing_pair_draft(tmp_path, title="a very long english title " * 5)
    name = save(long, tmp_conf, accept_outside=False)["saved"][0]
    slug = name.removeprefix("gen_").removesuffix("_base")
    assert 0 < len(slug) <= 40 and not slug.endswith("_")


def test_a_measure_must_name_a_person_of_the_company(tmp_path, tmp_conf):
    d = _passing_pair_draft(tmp_path)
    person = d["versions"]["baseline"]["company"]["people"][0]["id"]
    good = [
        {"metric": "stress", "subject": "all", "direction": "up"},
        {
            "metric": "relation",
            "subject": f"partners_of:{person}",
            "toward": person,
            "direction": "down",
        },  # fmt: skip
    ]
    for bad, value in (({"subject": "NOBODY"}, "NOBODY"),
                       ({"subject": "partners_of:GHOST"}, "partners_of:GHOST"),
                       ({"subject": person, "toward": "all"}, "all")):  # fmt: skip
        measure = {"metric": "relation", "direction": "up", "toward": None, **bad}
        d["experiment"]["measures"] = [*good, measure]
        with pytest.raises(SaveRefused, match=f"measure names an unknown person: {value}$"):
            save(d, tmp_conf, accept_outside=False)
    assert _names(tmp_conf) == []
    d["experiment"]["measures"] = good
    assert len(save(d, tmp_conf, accept_outside=False)["saved"]) == 2


def test_saved_files_that_do_not_load_are_removed(tmp_path, tmp_conf):
    d = _passing_pair_draft(tmp_path)
    for role in ("baseline", "variant"):
        d["versions"][role]["company"]["people"][0]["communication_style"] = "${oops}"
    assert view(d)["checks"] == {"baseline": [], "variant": []}  # the draft check cannot see it
    with pytest.raises(SaveRefused, match="the saved files do not load: "):
        save(d, tmp_conf, accept_outside=False)
    assert sorted(tmp_conf.rglob("gen_*")) == []


def test_an_invalid_draft_is_not_saved(tmp_path, tmp_conf):
    d = _passing_pair_draft(tmp_path)
    d["versions"]["variant"]["scenario"]["days"] = "x"
    with pytest.raises(SaveRefused, match="fix the errors first"):
        save(d, tmp_conf, accept_outside=False)
    assert _names(tmp_conf) == []


def test_a_variant_outside_its_factor_needs_consent(tmp_path, tmp_conf):
    d = _passing_pair_draft(tmp_path)
    d["factor"] = "structure"  # the disposition change is now outside the factor
    d["experiment"]["factor"] = "structure"
    with pytest.raises(SaveRefused, match="differs outside its factor"):
        save(d, tmp_conf, accept_outside=False)
    assert _names(tmp_conf) == []
    assert len(save(d, tmp_conf, accept_outside=True)["saved"]) == 2


def test_a_work_variant_reuses_the_source_company(tmp_path, tmp_conf):
    d = Drafts(tmp_path).create("variant", "r10_human")
    variant = copy.deepcopy(d["versions"]["baseline"])
    variant["scenario"]["research_question"] = "다른 질문"
    d = {**d, "title": "q", "factor": "work", "experiment": {**EXPERIMENT, "factor": "work"},
         "versions": {"baseline": d["versions"]["baseline"], "variant": variant}}  # fmt: skip
    d = save(d, tmp_conf, accept_outside=True)
    assert d["saved"] == ["gen_q_var"]
    assert _names(tmp_conf) == ["gen_q_var"]
    assert load_c15_scenario("gen_q_var").preset == "korean_enterprise_10_ko"
    assert not (tmp_conf / "personas" / "gen_q_var.yaml").exists()


def test_a_draft_with_nothing_to_write_is_refused(tmp_path, tmp_conf):
    drafts = Drafts(tmp_path)
    with pytest.raises(SaveRefused, match="nothing to save yet"):
        save(drafts.create("scratch", None), tmp_conf, accept_outside=False)
    with pytest.raises(SaveRefused, match="write the variant first"):
        save(drafts.create("variant", "r10_human"), tmp_conf, accept_outside=False)
    assert _names(tmp_conf) == []
