"""Tests for denominators: retry flags are not necessarily extra LLM calls."""

import runpy
from pathlib import Path

from conflict_sim.usage_audit import text_metric

FUNCTIONS = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "scripts/token_efficiency_analysis.py")
)


def completion(agent, tick, *, action=False, validation=False):
    return {
        "event": "completion",
        "agent": agent,
        "tick": tick,
        "call_type": "act",
        "schema": "Action",
        "action_retry": action,
        "validation_retry": validation,
        "system_chars": 10,
        "prompt_chars": 20,
        "section_metrics": {"fixed": text_metric("fixed")},
    }


def test_retry_only_group_does_not_count_as_within_tick_amplification():
    rows = [
        completion("A", 0),
        completion("A", 1, action=True),
        completion("B", 0),
        completion("B", 0, action=True, validation=True),
    ]
    data = FUNCTIONS["analyze"](rows, [])
    h2 = data["H2"]
    assert h2["act_action_retry_only"] == 1 and h2["act_both_retries"] == 1
    assert h2["act_retry_tagged_completions"] == 2
    assert h2["act_agent_tick_groups"] == 3
    assert h2["act_calls_above_one_per_agent_tick"] == 1
    assert h2["act_groups_with_only_retry_tagged_completions"] == 1
    assert h2["act_group_amplification_ratio"] == 4 / 3


def test_duplicates_use_model_text_key_and_agent_consecutive_denominators():
    rows = [
        {"agent": a, "tick": t, "model": m, "text_metrics": [text_metric(q)]}
        for a, t, m, q in [
            ("A", 0, "v1", "office  work"),
            ("A", 1, "v1", "office  work"),
            ("B", 0, "v1", "office work"),
            ("B", 1, "v2", "office work"),
        ]
    ]
    data = FUNCTIONS["duplicate_summary"](rows)
    assert data["total_queries"] == 4 and data["unique_exact_queries"] == 3
    assert data["unique_whitespace_normalized_queries"] == 2
    assert data["duplicate_within_agent"] == 1 and data["consecutive_equal"] == 1
    assert data["exact_duplicate_rate"] == 0.25


def test_section_repetition_is_per_agent_and_call_type():
    rows = [completion("A", 0), completion("B", 0), completion("A", 1)]
    rows.append(completion("A", 2) | {"call_type": "speech"})
    data = FUNCTIONS["section_summary"](rows)
    assert data["act/fixed"]["consecutive_pairs"] == 1
    assert data["act/fixed"]["consecutive_equal"] == 1
    assert data["speech/fixed"]["consecutive_pairs"] == 0
    assert data["act/fixed"]["share_of_system_plus_prompt_chars"] == 5 / 30


def test_20_agent_smoke_hash_matches_pre_extension_baseline(tmp_path, monkeypatch):
    import json

    output = tmp_path / "analysis"
    monkeypatch.setattr("sys.argv", ["analysis", "--output", str(output)])
    FUNCTIONS["main"]()
    result = json.loads((output / "hypothesis_analysis.json").read_text())
    assert result["method"]["behavior_sha256"] == (
        "0f29aef080152f847eea95eed0e2db0675505d61e28416146dc9b8fe7f46e4dd"
    )
    assert result["method"]["paid_api_calls"] == 0
