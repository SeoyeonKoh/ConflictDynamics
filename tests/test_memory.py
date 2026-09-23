import json

import numpy as np
import pytest

from conflict_sim.agent.memory import MemoryStore
from conflict_sim.models import Insights, MemoryConfig, MemoryRecord, Questions


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def complete(self, **request):
        self.requests.append(request)
        return self.responses.pop(0)

    def embed(self, texts):
        return [[1.0, 0.0] if "spec" in t else [0.0, 1.0] for t in texts]


def store(llm=None, **config):
    return MemoryStore("Alex", MemoryConfig(**config), llm or FakeLLM([]), "demo")


def record(store, description, tick, *, type="observation", importance=3, valence=0.0, **fields):
    return store.append(
        description=description,
        tick=tick,
        type=type,
        importance=importance,
        valence=valence,
        arousal=fields.pop("arousal", abs(valence)),
        subjects=fields.pop("subjects", []),
        **fields,
    )


def test_append_assigns_ids_and_queues_the_record_for_the_loop():
    s = store()
    first = record(s, "Blake looks annoyed.", 3, subjects=["Blake"], valence=-0.6)
    second = record(s, "Worked on spec.", 4, type="action")
    assert (first.id, second.id) == ("Alex:0", "Alex:1")
    assert first.self_relevance == 0 and second.self_relevance == 0
    assert [r.id for r in s.pending_writes] == ["Alex:0", "Alex:1"]
    assert s.pending_texts() == [("Alex:0", "Blake looks annoyed."), ("Alex:1", "Worked on spec.")]


def test_self_relevance_is_one_when_i_am_a_subject_or_my_task_is_involved():
    s = store()
    assert (
        record(s, "Blake asked me for the spec.", 1, subjects=["Blake", "Alex"]).self_relevance == 1
    )
    assert record(s, "The spec slipped.", 1, about_my_task=True).self_relevance == 1


def test_embeddings_arrive_later_and_drain_hands_everything_to_the_loop():
    s = store()
    record(s, "spec is late", 1)
    record(s, "lunch", 1)
    s.set_embeddings({"Alex:0": [1.0, 0.0]})
    assert s.pending_texts() == [("Alex:1", "lunch")]
    rows, log = s.drain()
    assert [(r.id, None if v is None else v.tolist()) for r, v in rows] == [
        ("Alex:0", [1.0, 0.0]),
        ("Alex:1", None),
    ]
    assert log == [] and s.pending_writes == []


def test_reflection_modes_map_to_k_over_reflection_records():
    s = store()
    record(s, "an observation", 1)
    record(s, "first insight", 2, type="reflection")
    record(s, "second insight", 3, type="reflection")
    assert s.reflections(0) == []
    assert s.reflections(1) == ["second insight"]
    assert s.reflections(None) == ["first insight", "second insight"]


def test_retrieve_prefers_relevant_then_recent_and_logs_the_query():
    s = store()
    record(s, "spec is late", 1)
    record(s, "lunch was fine", 1)
    record(s, "old spec talk", 0)
    s.set_embeddings({"Alex:0": [1.0, 0.0], "Alex:1": [0.0, 1.0], "Alex:2": [1.0, 0.0]})
    hits = s.retrieve("what about the spec", [1.0, 0.0], tick=5, mood=0, k=2)
    assert [r.id for r in hits] == ["Alex:0", "Alex:2"]
    assert s.last_access["Alex:0"] == 5 and s.last_access["Alex:1"] == 1
    assert s.retrieval_log == [
        {"tick": 5, "query": "what about the spec", "ids": ["Alex:0", "Alex:2"]}
    ]


def test_vectors_are_arrays_and_a_query_may_be_one_too():
    s = store()
    record(s, "spec is late", 1)
    record(s, "lunch was fine", 1)
    s.set_embeddings({"Alex:0": [1.0, 0.0], "Alex:1": [0.0, 1.0]})
    assert all(isinstance(v, np.ndarray) for v in s.vectors.values())
    hits = s.retrieve("spec", np.array([0.6, 0.8]), tick=2, mood=0, k=2)
    assert [r.id for r in hits] == ["Alex:1", "Alex:0"]  # cosine 0.8 beats 0.6, recency equal


def test_mood_congruent_records_win_only_when_alpha_mood_is_on():
    def make(alpha):
        s = store(alpha_mood=alpha)
        record(s, "Blake snapped at me", 1, valence=-0.8)
        record(s, "Casey thanked me", 1, valence=0.8)
        return s

    assert make(0).retrieve("q", None, tick=3, mood=-0.5, k=1)[0].id == "Alex:1"
    assert make(1).retrieve("q", None, tick=3, mood=-0.5, k=1)[0].id == "Alex:0"


def test_retrieve_with_k_zero_is_free():
    s = store()
    record(s, "x", 1)
    assert s.retrieve("q", None, tick=2, mood=0, k=0) == [] and s.retrieval_log == []


def test_reflection_triggers_on_cumulative_importance_and_on_subject_valence():
    s = store(reflect_threshold=10, relation_reflect_threshold=-1)
    record(s, "a", 1, importance=6)
    assert not s.due_reflection() and s.due_relation_reflections() == []
    record(s, "b", 2, importance=5, valence=-0.6, subjects=["Blake"])
    record(s, "c", 3, importance=1, valence=-0.5, subjects=["Blake"])
    record(s, "d", 3, importance=1, valence=-1, subjects=["Alex"])  # never about myself
    assert s.due_reflection() and s.due_relation_reflections() == ["Blake"]
    fresh = store(reflect_threshold=10)
    record(fresh, "insight", 1, type="reflection", importance=10)  # reflections are not events
    assert not fresh.due_reflection()


def test_reflect_asks_questions_then_insights_and_stores_a_reflection_tree():
    llm = FakeLLM(
        [
            json.dumps({"questions": ["Why is the spec late?", "Do I trust Blake?"]}),
            json.dumps(
                {
                    "insights": [
                        {
                            "text": "Alex is waiting on Blake.",
                            "evidence": ["Alex:0", "Alex:9"],
                            "importance": 6,
                            "valence": -0.4,
                            "arousal": 0.3,
                            "subjects": ["Blake"],
                        }
                    ]
                }
            ),
            json.dumps(
                {
                    "insights": [
                        {
                            "text": "Blake means well.",
                            "evidence": [],
                            "importance": 4,
                            "valence": 0.2,
                            "arousal": 0.1,
                            "subjects": ["Blake"],
                        }
                    ]
                }
            ),
        ]
    )
    s = store(llm, reflect_threshold=5, reflect_questions=2)
    record(s, "spec is late", 1, importance=5, subjects=["Blake"])
    new = s.reflect(tick=4, mood=0)
    assert [r.type for r in new] == ["reflection", "reflection"]
    assert new[0].evidence == ["Alex:0"]  # unknown ids are dropped
    assert new[0].self_relevance == 1 and new[0].created_tick == 4
    assert not s.due_reflection()
    assert len(llm.requests) == 3 and all(r["json_mode"] for r in llm.requests)
    assert [r["schema"] for r in llm.requests] == [Questions, Insights, Insights]
    assert json.loads(llm.requests[1]["prompt"])["question"] == "Why is the spec late?"


def test_relation_reflection_asks_one_fixed_question_about_the_subject():
    llm = FakeLLM(
        [
            json.dumps(
                {
                    "insights": [
                        {
                            "text": "Blake deflects.",
                            "evidence": ["Alex:0"],
                            "importance": 7,
                            "valence": -0.7,
                            "arousal": 0.5,
                            "subjects": ["Blake"],
                        }
                    ]
                }
            )
        ]
    )
    s = store(llm, relation_reflect_threshold=-0.5)
    record(s, "Blake refused.", 1, valence=-0.6, subjects=["Blake"])
    assert s.due_relation_reflections() == ["Blake"]
    new = s.reflect(tick=2, mood=-0.3, about="Blake")
    assert (
        new[0].description == "Blake deflects."
        and "Blake" in json.loads(llm.requests[0]["prompt"])["question"]
    )
    assert s.due_relation_reflections() == []


def test_records_are_immutable_memory_records():
    s = store()
    assert isinstance(record(s, "x", 1), MemoryRecord)
    with pytest.raises(ValueError):
        s.records[0].importance = 9


def test_the_day_review_looks_back_on_today_against_the_plan_in_one_call():
    """Leaving work: one call over the plan, task status and today's weightiest records."""
    insight = {"text": "I never got to the api.", "evidence": ["Alex:3", "gone"], "importance": 7,
               "valence": -0.6, "arousal": 0.5, "subjects": ["Blake"]}  # fmt: skip
    llm = FakeLLM([json.dumps({"insights": [insight]})])
    s = store(llm)
    record(s, "yesterday", 0, importance=9)
    record(s, "Today's plan: work on api.", 32, type="plan", importance=9)
    for i in range(45):
        record(s, f"today {i}", 33 + i // 2, importance=1 + i % 10)
    new = s.review_day(63, mood=-0.2, since=32, plan=["Work on api."], tasks=[{"id": "api"}])
    assert len(llm.requests) == 1
    payload = json.loads(llm.requests[0]["prompt"])
    assert payload["plan"] == ["Work on api."] and payload["task_status"] == [{"id": "api"}]
    rows = payload["records"]
    assert len(rows) == 40 and {r["type"] for r in rows} == {"observation"}
    assert [r["tick"] for r in rows] == sorted(r["tick"] for r in rows)  # in the day's order
    assert "Alex:0" not in {r["id"] for r in rows}  # nothing from yesterday
    assert [(r.type, r.description, r.evidence) for r in new] == [
        ("reflection", "I never got to the api.", ["Alex:3"])
    ]
