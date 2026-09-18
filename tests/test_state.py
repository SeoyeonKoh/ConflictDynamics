import pytest

from conflict_sim.agent.state import AgentState, Relationship
from conflict_sim.models import AgentSpec, Config, Outcome, Received


def config(**overrides):
    return Config(
        n_agents=3, agents=[AgentSpec(name=n, persona="Works.") for n in "ABC"], **overrides
    )


def outcome(**fields):
    return Outcome(session_id="talk:1", public=False, **fields)


def test_received_valence_moves_relation_by_its_mean_times_w_valence():
    state = AgentState()
    received = [
        Received(speaker="B", valence=-0.5, arousal=0),
        Received(speaker="B", valence=-1, arousal=0),
    ]
    deltas = state.apply_outcome(outcome(received=received), config(), tick=4)
    assert deltas == {"B": pytest.approx(0.2 * -0.75)}
    assert state.relations["B"].relation == pytest.approx(-0.15)
    assert state.relations["B"].last_interaction_tick == 4


def test_public_sessions_multiply_the_relation_change():
    state = AgentState()
    state.apply_outcome(
        Outcome(
            session_id="talk:1",
            public=True,
            received=[Received(speaker="B", valence=-1, arousal=0)],
        ),
        config(),
        tick=1,
    )
    assert state.relations["B"].relation == pytest.approx(-0.2 * 1.5)


def test_refusal_costs_w_structural_in_relation_and_stress():
    state = AgentState()
    state.apply_outcome(outcome(refused=["B"]), config(), tick=1)
    assert state.relations["B"].relation == pytest.approx(-0.15)
    assert state.stress == pytest.approx(0.15)


def test_arousal_received_raises_stress_by_w_arousal():
    state = AgentState()
    state.apply_outcome(
        outcome(received=[Received(speaker="B", valence=0, arousal=0.8)]), config(), tick=1
    )
    assert state.stress == pytest.approx(0.08)
    assert state.relations["B"].relation == 0


def test_relation_and_stress_stay_in_range():
    state = AgentState(stress=0.99, relations={"B": Relationship(relation=-0.95)})
    state.apply_outcome(
        Outcome(
            session_id="s",
            public=True,
            received=[Received(speaker="B", valence=-1, arousal=1)],
            refused=["B"],
        ),
        config(),
        tick=1,
    )
    assert state.relations["B"].relation == -1
    assert state.stress == 1


def test_end_tick_decays_stress_and_sets_mood_from_recent_valence():
    state = AgentState(stress=0.5, mood=0.9)
    state.end_tick([-0.4, 0.2], config())
    assert (state.stress, state.mood) == (pytest.approx(0.48), pytest.approx(-0.1))
    state.end_tick([], config())
    assert (state.stress, state.mood) == (pytest.approx(0.46), 0)


def test_snapshot_is_plain_data():
    state = AgentState(relations={"B": Relationship(relation=-0.2, grievances=["A:3"])})
    assert state.snapshot() == {
        "stress": 0.0,
        "mood": 0.0,
        "expression": "neutral",
        "relations": {"B": {"relation": -0.2, "grievances": ["A:3"], "summary": None}},
    }
