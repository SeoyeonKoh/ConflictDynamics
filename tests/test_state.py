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
    assert deltas == {"B": pytest.approx(0.1 * -0.75)}
    assert state.relations["B"].relation == pytest.approx(-0.075)
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
    assert state.relations["B"].relation == pytest.approx(-0.1 * 1.5)


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
    assert 0.99 < state.stress < 1  # it nears 1 but never bursts


def test_end_tick_decays_stress_and_sets_mood_from_recent_valence():
    state = AgentState(stress=0.5, mood=0.9)
    state.end_tick([-0.4, 0.2], config())
    assert (state.stress, state.mood) == (pytest.approx(0.48), pytest.approx(-0.1))
    state.end_tick([], config())
    assert (state.stress, state.mood) == (pytest.approx(0.46), 0)


def test_snapshot_is_plain_data_and_restores_the_same_state():
    state = AgentState(stress=0.3, relations={"B": Relationship(relation=-0.2, grievances=["A:3"])})
    snapshot = state.snapshot()
    assert snapshot == {
        "stress": 0.3,
        "mood": 0.0,
        "expression": "neutral",
        "relations": {
            "B": {
                "relation": -0.2,
                "grievances": ["A:3"],
                "summary": None,
                "last_interaction_tick": None,
            }
        },
    }
    other = AgentState()
    other.restore(snapshot)
    assert other == state


def test_outcome_deltas_come_in_name_order_so_events_are_reproducible():
    state = AgentState()
    deltas = state.apply_outcome(outcome(refused=["C", "A", "B"], ignored=["D"]), config(), tick=1)
    assert list(deltas) == ["A", "B", "C", "D"]


def test_stress_slows_work_but_never_stops_it():
    assert AgentState(stress=0).work_rate(config()) == 1
    assert AgentState(stress=1).work_rate(config()) == pytest.approx(0.5)
    assert AgentState(stress=1).work_rate(config(stress_work_penalty=0)) == 1


def test_a_low_rating_presses_more_than_a_high_one():
    low, high = AgentState(), AgentState()
    low.apply_evaluation(0.2, config())
    high.apply_evaluation(0.9, config())
    assert (low.stress, high.stress) == (pytest.approx(0.16), pytest.approx(0.02))


def test_an_evaluation_season_presses_every_tick_and_holds_off_recovery():
    state = AgentState(stress=0.5)
    state.end_tick([], config(), evaluation_season=True)
    assert state.stress == pytest.approx(0.5 + 0.005 * 0.5)


def test_stress_rises_less_the_higher_it_already_is():
    calm, tense = AgentState(stress=0.1), AgentState(stress=0.8)
    for state in (calm, tense):
        state.apply_evaluation(0, config())
    assert (calm.stress, tense.stress) == (pytest.approx(0.1 + 0.2 * 0.9), pytest.approx(0.84))


def test_a_tick_of_work_pressure_is_capped_however_many_tasks_press():
    state = AgentState()
    state.end_tick([], config(), pressure=0.2)
    assert state.stress == pytest.approx(config().p_max)
