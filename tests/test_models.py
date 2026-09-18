import pytest

from conflict_sim.models import Decision, Thread, Utterance


def test_tree_preserves_order_and_exposes_posts_after_a_tick():
    thread = Thread([Utterance(id="root", speaker="A", text="First", reply_to=None, timestamp=0)])
    thread.add(Utterance(id="reply", speaker="B", text="Second", reply_to="root", timestamp=1))
    assert [u.id for u in thread.after(0)] == ["reply"]


@pytest.mark.parametrize(
    "fields",
    [
        {"id": "root"},
        {"reply_to": "missing"},
        {"reply_to": None},
        {"timestamp": -1},
        {"text": " "},
    ],
)
def test_invalid_posts_do_not_mutate_the_thread(fields):
    thread = Thread([Utterance(id="root", speaker="A", text="First", reply_to=None, timestamp=0)])
    with pytest.raises(ValueError):
        data = dict(id="new", speaker="B", text="Reply", reply_to="root", timestamp=1)
        thread.add(Utterance(**(data | fields)))
    assert len(thread.utterances) == 1


@pytest.mark.parametrize(
    "fields",
    [
        {"timestamp": True},
        {"timestamp": "0"},
        {"timestamp": -1},
        {"text": "\t\n"},
        {"speaker": 42},
        {"id": ""},
        {"unexpected": "value"},
    ],
)
def test_utterance_rejects_bad_input_at_construction(fields):
    data = dict(id="root", speaker="A", text="First", reply_to=None, timestamp=0)
    with pytest.raises(ValueError):
        Utterance(**(data | fields))


def test_decision_parses_json_without_coercing_string_numbers():
    decision = Decision.model_validate_json(
        '{"urge": 1, "reply_to": null, "reflection": "I need a source."}'
    )
    assert decision.model_dump() == {
        "urge": 1.0,
        "reply_to": None,
        "reflection": "I need a source.",
        "expression": "neutral",
        "importance": 3.0,
        "valence": 0.0,
        "arousal": 0.0,
    }
    with pytest.raises(ValueError):
        Decision.model_validate_json(
            '{"urge": "0.5", "reply_to": null, "reflection": "I need a source."}'
        )


@pytest.mark.parametrize("reflection", [None, "", " \n", 12])
def test_reflection_must_be_nonempty_text(reflection):
    with pytest.raises(ValueError):
        Decision(urge=0, reply_to=None, reflection=reflection)


# --- company simulation schemas (phase A) ---


def test_expression_table_covers_every_label_with_its_valence():
    from conflict_sim.models import EXPRESSION_VALENCE

    assert EXPRESSION_VALENCE == {
        "neutral": 0.0,
        "pleased": 0.5,
        "amused": 0.8,
        "surprised": 0.0,
        "tired": -0.3,
        "anxious": -0.5,
        "annoyed": -0.6,
        "angry": -0.9,
    }


def test_decision_carries_expression_and_record_axes():
    decision = Decision.model_validate_json(
        '{"urge": 0.4, "reply_to": null, "reflection": "Fine.", "expression": "annoyed",'
        ' "importance": 6, "valence": -0.5, "arousal": 0.7}'
    )
    assert (decision.expression, decision.importance, decision.valence, decision.arousal) == (
        "annoyed",
        6.0,
        -0.5,
        0.7,
    )


def test_decision_without_new_fields_defaults_to_a_neutral_face():
    decision = Decision(urge=0, reply_to=None, reflection="Fine.")
    assert (decision.expression, decision.valence, decision.arousal) == ("neutral", 0.0, 0.0)


@pytest.mark.parametrize(
    "fields",
    [
        {"expression": "furious"},
        {"importance": 0},
        {"importance": 11},
        {"valence": -1.5},
        {"arousal": 2},
        {"arousal": "0.5"},
    ],
)
def test_decision_rejects_out_of_range_axes(fields):
    data = dict(urge=0, reply_to=None, reflection="Fine.")
    with pytest.raises(ValueError):
        Decision(**(data | fields))


def action_data(**overrides):
    return {
        "kind": "work",
        "task": "spec",
        "expression": "neutral",
        "reflection": "Back to the spec.",
        "importance": 3,
        "valence": 0,
        "arousal": 0.1,
    } | overrides


def test_action_parses_llm_json_for_each_kind():
    from conflict_sim.models import Action

    Action.model_validate(action_data(kind="move", task=None, place="pantry"))
    Action.model_validate(action_data(kind="message", task=None, target="Blake", text="Status?"))
    Action.model_validate(action_data(kind="assign", target="Casey"))
    Action.model_validate(action_data(kind="talk", task=None, text="Got a minute?"))
    Action.model_validate(action_data(kind="rest", task=None))


@pytest.mark.parametrize(
    "overrides",
    [
        {"kind": "move"},  # no place
        {"kind": "work", "task": None},
        {"kind": "message", "task": None, "target": "Blake"},  # no text
        {"kind": "message", "task": None, "text": "Status?"},  # no target
        {"kind": "chat", "task": None},
        {"kind": "assign"},  # no target
        {"kind": "approve", "task": None},
        {"kind": "report", "task": None, "target": "Drew"},  # no text
        {"kind": "gossip", "task": None},
        {"kind": "rest", "task": None, "unexpected": 1},
    ],
)
def test_action_requires_the_arguments_its_kind_needs(overrides):
    from conflict_sim.models import Action

    with pytest.raises(ValueError):
        Action.model_validate(action_data(**overrides))


def test_agent_spec_company_fields_are_optional_for_wiki_presets():
    from conflict_sim.models import AgentSpec

    wiki = AgentSpec(name="Alex", persona="Insists.")
    assert (wiki.disc, wiki.department, wiki.title, wiki.role, wiki.reports_to) == (None,) * 5
    company = AgentSpec(
        name="Alex",
        persona="Insists.",
        disc="D",
        department="product",
        title="manager",
        role="Product lead",
        reports_to="Erin",
        skills=["planning"],
    )
    assert company.disc == "D"
    with pytest.raises(ValueError):
        AgentSpec(name="Alex", persona="Insists.", disc="X")


def test_task_spec_validates_effort_and_deadline():
    from conflict_sim.models import TaskSpec

    task = TaskSpec(id="spec", description="Write the spec", effort_ticks=8, due=28)
    assert (task.difficulty, task.owner, task.depends_on, task.skills) == (3, None, [], [])
    for bad in [{"effort_ticks": 0}, {"due": -1}, {"difficulty": 6}]:
        with pytest.raises(ValueError):
            TaskSpec(**({"id": "spec", "description": "x", "effort_ticks": 8, "due": 28} | bad))


def test_memory_record_is_immutable_and_bounded():
    from conflict_sim.models import MemoryRecord

    record = MemoryRecord(
        id="r1",
        agent_id="Alex",
        type="observation",
        description="Blake looks angry after the meeting.",
        created_tick=12,
        importance=3,
        valence=-0.9,
        arousal=0.9,
        self_relevance=0.0,
        subjects=["Blake"],
        session_id=None,
    )
    with pytest.raises(ValueError):
        record.importance = 5
    for bad in [{"type": "hearsay"}, {"importance": 0.5}, {"self_relevance": 1.5}]:
        with pytest.raises(ValueError):
            MemoryRecord(**(record.model_dump() | bad))


def test_view_is_assembled_from_environment_and_agent_parts():
    from conflict_sim.models import BlockedTask, Message, Rejected, TaskView, View

    view = View(
        agent="Blake",
        day=0,
        tick=9,
        phase="morning",
        place="dev-office",
        present={"Casey": "annoyed"},
        tasks=[TaskView(id="api", description="Ship API", owner="Blake", progress=0.25, due=28)],
        blocked=[BlockedTask(task="api", waiting_on="spec", owner="Alex", since_tick=7, due=28)],
        resources={"meeting-room": 1},
        inbox=[Message(sender="Alex", text="Any update?", tick=8, session_id="dm:Alex:Blake:0")],
        unanswered=[],
        rejected=Rejected(
            action=action_data(kind="move", task=None, place="meeting-room"),
            reason="meeting-room is full",
        ),
        stress=0.3,
        mood=-0.2,
    )
    assert view.present["Casey"] == "annoyed"
    assert view.rejected.action.place == "meeting-room"
    with pytest.raises(ValueError):
        view.stress = 0.9


def test_outcome_and_event_are_plain_facts():
    from conflict_sim.models import Event, Outcome, Received

    outcome = Outcome(
        session_id="talk:3:12",
        public=True,
        received=[Received(speaker="Blake", valence=-0.6, arousal=0.8)],
        refused=["Blake"],
        ignored=[],
        rebutted=["Blake"],
        opposed=["Casey"],
    )
    assert outcome.received[0].speaker == "Blake"
    event = Event(tick=12, day=0, kind="outcome", actor="Alex", target="Blake", payload={"d": -0.2})
    assert (event.location, event.session) == (None, None)
    with pytest.raises(ValueError):
        Event(tick=12, day=0, kind="gossip", actor="Alex", payload={})
