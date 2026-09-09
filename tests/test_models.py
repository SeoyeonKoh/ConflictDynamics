import pytest

from conflict_sim.models import Decision, Thread, Utterance


def test_tree_preserves_order_and_exposes_recent_context():
    thread = Thread([Utterance(id="root", speaker="A", text="First", reply_to=None, timestamp=0)])
    thread.add(Utterance(id="reply", speaker="B", text="Second", reply_to="root", timestamp=1))
    assert [u.id for u in thread.after(0)] == ["reply"]
    assert "Second" in thread.context(1)
    assert "First" not in thread.context(1)


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
    decision = Decision.model_validate_json('{"urge": 1, "reply_to": null}')
    assert decision.model_dump() == {"urge": 1.0, "reply_to": None}
    with pytest.raises(ValueError):
        Decision.model_validate_json('{"urge": "0.5", "reply_to": null}')
