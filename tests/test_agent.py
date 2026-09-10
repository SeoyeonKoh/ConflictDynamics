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


def test_decide_parses_valid_json_and_uses_only_the_decision_model():
    llm = FakeLLM('{"urge": 0.6, "reply_to": "root", "reflection": "I need a citation."}')
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
    llm = FakeLLM('{"urge": 0.5, "reply_to": "reply", "reflection": "I see a new source."}')
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
        llm.response = json.dumps({"urge": 0, "reply_to": None, "reflection": reflection})
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
