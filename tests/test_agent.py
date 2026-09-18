import json

import pytest

from conflict_sim.agent import Agent
from conflict_sim.models import Thread, Utterance


class FakeLLM:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def complete(self, **request):
        self.requests.append(request)
        return self.response


def seed():
    return Thread(
        [
            Utterance(
                id="root", speaker="A", text="Please check this source.", reply_to=None, timestamp=0
            )
        ]
    )


def make_agent(llm):
    return Agent(
        "B", "Prefers independent sources. Writes concise replies.", 0.8, llm, "small", "large", 0.8
    )


def decision_json(**fields):
    return json.dumps(
        {
            "urge": 0,
            "reply_to": None,
            "reflection": "Nothing new.",
            "expression": "neutral",
            "importance": 3,
            "valence": 0,
            "arousal": 0,
        }
        | fields
    )


def test_decide_parses_valid_json_and_uses_only_the_decision_model():
    llm = FakeLLM(decision_json(urge=0.6, reply_to="root", reflection="I need a citation."))
    agent = make_agent(llm)
    decision = agent.decide(seed())
    assert (decision.urge, decision.reply_to) == (0.6, "root")
    assert agent.reflections == ["I need a citation."]
    assert len(llm.requests) == 1
    assert llm.requests[0]["model"] == "small"
    assert llm.requests[0]["json_mode"] is True
    payload = json.loads(llm.requests[0]["prompt"])
    assert payload["utterances"][0]["text"] == "Please check this source."


@pytest.mark.parametrize(
    "response",
    [
        "not json",
        "[]",
        "{}",
        '{"urge": true, "reply_to": null, "reflection": "Still unsure."}',
        '{"urge": -0.1, "reply_to": null, "reflection": "Still unsure."}',
        '{"urge": 1.1, "reply_to": null, "reflection": "Still unsure."}',
        '{"urge": NaN, "reply_to": null, "reflection": "Still unsure."}',
        '{"urge": "0.5", "reply_to": null, "reflection": "Still unsure."}',
        '{"urge": 0.5, "reply_to": 12, "reflection": "Still unsure."}',
        '{"urge": 0.5, "reply_to": "missing", "reflection": "Still unsure."}',
        '{"urge": 0.5, "reply_to": null}',
        '{"urge": 0.5, "reply_to": null, "reflection": " "}',
        '{"urge": 0.5, "reply_to": null, "reflection": "Still unsure."}',
        decision_json(expression="furious"),
        decision_json(importance=0),
    ],
)
def test_invalid_decisions_fail_instead_of_becoming_silence(response):
    agent = make_agent(FakeLLM(response))
    agent.reflections.append("An earlier concern.")
    with pytest.raises(ValueError):
        agent.decide(seed())
    assert agent.reflections == ["An earlier concern."]


def test_speak_includes_target_outside_recent_context_and_uses_generation_model():
    thread = seed()
    for index in range(12):
        thread.add(
            Utterance(id=str(index), speaker="A", text="Later text", reply_to="root", timestamp=1)
        )
    llm = FakeLLM("  Could you provide the original citation?  ")
    text = make_agent(llm).speak(thread, "root")
    assert text == "Could you provide the original citation?"
    assert llm.requests[0]["model"] == "large"
    payload = json.loads(llm.requests[0]["prompt"])
    assert payload["target"]["text"] == "Please check this source."


def test_empty_speech_is_an_error():
    with pytest.raises(ValueError):
        make_agent(FakeLLM(" ")).speak(seed(), "root")


def test_small_context_keeps_unread_text_until_it_has_been_seen():
    thread = seed()
    thread.add(
        Utterance(
            id="reply",
            speaker="C",
            text="An independent source is available.",
            reply_to="root",
            timestamp=0,
        )
    )
    llm = FakeLLM(decision_json(urge=0.5, reply_to="reply", reflection="I see a new source."))
    agent = make_agent(llm)
    agent.context_size = 1
    agent.decide(thread)
    payload = json.loads(llm.requests[-1]["prompt"])
    assert [u["id"] for u in payload["utterances"]] == ["root", "reply"]
    assert payload["utterances"][0]["text"] == "Please check this source."

    agent.last_seen = 2
    thread.add(
        Utterance(
            id="new", speaker="C", text="Here is the citation.", reply_to="reply", timestamp=1
        )
    )
    agent.decide(thread)
    payload = json.loads(llm.requests[-1]["prompt"])
    assert [u["id"] for u in payload["utterances"]] == ["new"]


@pytest.mark.parametrize("mode", ["summary", "full"])
def test_private_memory_is_updated_even_when_silent_and_passed_to_speech(mode):
    llm = FakeLLM("")
    agent = make_agent(llm)
    agent.memory_mode = mode
    reflections = [
        "I doubt the source.",
        "The source helps, but wording remains disputed.",
        "I accept the revised wording and have nothing to add.",
    ]
    for index, reflection in enumerate(reflections):
        llm.response = decision_json(reflection=reflection)
        agent.decide(seed())
        payload = json.loads(llm.requests[-1]["prompt"])
        previous = reflections[:index]
        assert payload["private_memory"] == (previous[-1:] if mode == "summary" else previous)
    assert agent.reflections == reflections

    llm.response = "The wording now matches the source."
    agent.speak(seed(), "root")
    payload = json.loads(llm.requests[-1]["prompt"])
    assert payload["private_memory"] == (reflections[-1:] if mode == "summary" else reflections)
    assert agent.reflections == reflections

    other = make_agent(llm)
    other.speak(seed(), "root")
    assert json.loads(llm.requests[-1]["prompt"])["private_memory"] == []
    assert len(llm.requests) == 5  # Three decisions, two speeches; no separate memory call.


def test_memory_mode_none_records_reflections_without_feeding_them_back():
    llm = FakeLLM("")
    agent = make_agent(llm)
    agent.memory_mode = "none"
    for reflection in ["I doubt the source.", "The wording still misreads it."]:
        llm.response = decision_json(reflection=reflection)
        agent.decide(seed())
        assert json.loads(llm.requests[-1]["prompt"])["private_memory"] == []
    llm.response = "Comment."
    agent.speak(seed(), "root")
    assert json.loads(llm.requests[-1]["prompt"])["private_memory"] == []
    # The log still gets every reflection, so the ablation keeps the same decision schema.
    assert agent.reflections == ["I doubt the source.", "The wording still misreads it."]


def test_persona_stays_in_the_payload_by_default():
    llm = FakeLLM(decision_json(urge=0.2))
    agent = make_agent(llm)
    agent.decide(seed())
    llm.response = "Comment."
    agent.speak(seed(), "root")
    for request in llm.requests:
        assert "Prefers independent sources" not in request["system"]
        assert json.loads(request["prompt"])["persona"] == agent.persona


def test_system_placement_moves_the_persona_out_of_the_payload():
    llm = FakeLLM(decision_json(urge=0.2))
    agent = make_agent(llm)
    agent.persona_placement = "system"
    agent.decide(seed())
    llm.response = "Comment."
    agent.speak(seed(), "root")
    assert len(llm.requests) == 2
    for request in llm.requests:
        assert request["system"].startswith("You are the editor B. Prefers independent sources.")
        payload = json.loads(request["prompt"])
        assert "persona" not in payload
        assert payload["editor"] == "B"
    assert "Return only a JSON object" in llm.requests[0]["system"]
    assert "Return only the comment text" in llm.requests[1]["system"]


def test_decide_prompt_asks_for_the_session_fields_and_keeps_impressions():
    from conflict_sim.agent import DECIDE_INSTRUCTIONS, PROMPT_VERSION

    assert PROMPT_VERSION == "3"
    for name in ["expression", "importance", "valence", "arousal"]:
        assert f'"{name}"' in DECIDE_INSTRUCTIONS
    assert "revise earlier impressions" not in DECIDE_INSTRUCTIONS
    assert "Prior impressions can be mistaken" not in DECIDE_INSTRUCTIONS
