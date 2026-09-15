import json
import shutil
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

pytest.importorskip("streamlit")

from conflict_sim import settings  # noqa: E402

PROJECT = Path(__file__).resolve().parents[1]


@pytest.fixture
def inputs():
    return settings.load_settings(PROJECT / "conf/config.yaml")


def test_saved_settings_roundtrip_preserves_text_and_copies_the_seed(tmp_path, inputs):
    config, seed = inputs
    text = '한국어 "quoted", [list]:\nKeep ${literal} and \\${backslash} unchanged.'
    config["agents"][0]["persona"] = text
    seed["utterances"][0]["text"] = text
    path = settings.save_settings(tmp_path, "방어적-Alex-v1", config, seed)
    restored, copied_seed = settings.load_settings(path)
    assert restored["agents"] == config["agents"]
    assert restored == config | {"seed_file": str(path.parent / "seed.json"), "live": False}
    assert copied_seed == seed
    assert config["seed_file"] is None  # Saving never mutates the draft.


def test_existing_settings_are_never_overwritten(tmp_path, inputs):
    config, seed = inputs
    path = settings.save_settings(tmp_path, "one", config, seed)
    before = {p.name: p.read_bytes() for p in path.parent.iterdir()}
    config["agents"][0]["persona"] = "Changed."
    with pytest.raises(FileExistsError):
        settings.save_settings(tmp_path, "one", config, seed)
    assert before == {p.name: p.read_bytes() for p in path.parent.iterdir()}


@pytest.mark.parametrize("name", ["../outside", "/absolute", "", "has space", "a" * 81])
def test_invalid_names_cannot_create_files(tmp_path, inputs, name):
    with pytest.raises(ValueError):
        settings.save_settings(tmp_path / "settings", name, *inputs)
    assert not (tmp_path / "settings").exists()


@pytest.mark.parametrize(
    "invalid", ["empty_persona", "duplicate_name", "unknown_speaker", "bad_reply"]
)
def test_invalid_inputs_are_rejected_before_saving(tmp_path, inputs, invalid):
    config, seed = inputs
    if invalid == "empty_persona":
        config["agents"][0]["persona"] = " "
    elif invalid == "duplicate_name":
        config["agents"][1]["name"] = config["agents"][0]["name"]
    elif invalid == "unknown_speaker":
        seed["utterances"][0]["speaker"] = "Missing"
    else:
        seed["utterances"][1]["reply_to"] = "missing"
    with pytest.raises(ValueError):
        settings.save_settings(tmp_path, "invalid", config, seed)
    assert not list(tmp_path.iterdir())


def test_partial_save_is_not_published(tmp_path, inputs, monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(settings.yaml, "safe_dump", fail)
    with pytest.raises(OSError, match="disk full"):
        settings.save_settings(tmp_path, "partial", *inputs)
    assert not list(tmp_path.iterdir())


def test_hydra_missing_value_is_rejected_before_publishing(tmp_path, inputs):
    config, seed = inputs
    config["agents"][0]["persona"] = "???"  # Reserved by OmegaConf as a missing value.
    with pytest.raises(ValueError):
        settings.save_settings(tmp_path, "missing-value", config, seed)
    assert not list(tmp_path.iterdir())


def test_past_run_uses_archived_seed_even_when_original_is_gone(tmp_path, inputs):
    config, seed = inputs
    config["seed_file"] = "a/deleted/source.json"
    (tmp_path / "run.json").write_text(json.dumps({"config": config}))
    (tmp_path / "seed.json").write_text(json.dumps(seed))
    restored, archived = settings.load_settings(tmp_path / "run.json")
    assert restored == config
    assert archived == seed


def test_saved_settings_run_through_real_hydra_cli(tmp_path, inputs):
    config, seed = inputs
    config.update(max_ticks=1, memory_mode="none", rule="round_robin", max_utterances=1)
    config["agents"][0]["persona"] = "Changed persona with literal ${text}."
    seed["utterances"][0]["text"] = "Changed opening."
    path = settings.save_settings(tmp_path, "saved", config, seed)
    output = tmp_path / "result"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "conflict_sim.cli",
            "--config-path",
            str(path.parent),
            "--config-name",
            "config",
            f"hydra.run.dir={output}",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert completed.returncode == 0, completed.stderr
    metadata = json.loads((output / "corpus/run.json").read_text())
    assert metadata["config"] == settings.load_settings(path)[0]
    assert json.loads((output / "corpus/seed.json").read_text()) == seed
    assert metadata["generated_utterances"] == 1


@pytest.fixture
def editor_app(tmp_path, monkeypatch):
    from streamlit import cache_data
    from streamlit.testing.v1 import AppTest

    from conflict_sim import dashboard

    cache_data.clear()
    conf = tmp_path / "conf"
    shutil.copytree(PROJECT / "conf", conf, ignore=shutil.ignore_patterns("experiments"))
    monkeypatch.setattr(dashboard, "CONF_DIR", conf)
    monkeypatch.chdir(tmp_path)

    def view(root):
        from pathlib import Path

        from conflict_sim.dashboard import live_view

        live_view(Path(root))

    app = AppTest.from_function(view, args=(str(tmp_path / "runs"),)).run()
    assert not app.exception
    yield app, conf
    if "live_process" in app.session_state:
        process = app.session_state["live_process"]
        if process.poll() is None:
            process.terminate()
        process.wait(timeout=5)


def click(app, label):
    return next(b for b in app.button if b.label == label).click().run()


def test_editor_saves_loads_and_resets_all_fields(editor_app):
    app, conf = editor_app
    app.text_area(key="edit_agent_0_persona").set_value("My changed persona.").run()
    app.text_input(key="edit_agent_0_stance").set_value("새 입장").run()
    app.text_area(key="edit_seed_1_text").set_value("A sharper response.").run()
    app.number_input(key="edit_max_utterances").set_value(8).run()
    app.text_input(key="edit_model_speak").set_value("chosen-model").run()
    assert any("My changed persona." in code.value for code in app.code)
    assert any("A sharper response." in code.value for code in app.code)
    app.text_input(key="edit_save_name").set_value("custom-v1").run()
    click(app, "다른 이름으로 저장")
    assert not app.exception
    path = conf / "experiments/custom-v1/config.yaml"
    stored, seed = settings.load_settings(path)
    assert stored["agents"][0]["persona"] == "My changed persona."
    assert stored["agents"][0]["stance"] == "새 입장"
    assert stored["model_speak"] == "chosen-model"
    assert stored["max_utterances"] == 8
    assert seed["utterances"][1]["text"] == "A sharper response."
    assert seed["edited"] is True
    assert not list(conf.parent.rglob("console.log"))  # Saving never starts generation.

    app.selectbox(key="live_preset").set_value("wording").run()
    assert app.text_area(key="edit_agent_0_persona").value == "My changed persona."
    click(app, "불러오기")
    assert app.number_input(key="edit_n_agents").value == 4
    assert app.number_input(key="edit_max_utterances").value == 0
    assert app.text_input(key="edit_model_speak").value == "gpt-5.6-luna"
    app.selectbox(key="settings_source").set_value("저장한 설정").run()
    app.selectbox(key="settings_saved").set_value("custom-v1").run()
    click(app, "불러오기")
    assert not app.exception
    assert app.number_input(key="edit_n_agents").value == 6
    assert app.number_input(key="edit_max_utterances").value == 8
    assert app.text_area(key="edit_agent_0_persona").value == "My changed persona."
    assert app.text_area(key="edit_seed_1_text").value == "A sharper response."
    assert app.text_input(key="edit_model_speak").value == "chosen-model"
    app.number_input(key="edit_max_ticks").set_value(1).run()
    click(app, "Start simulation")
    assert not app.exception
    assert app.selectbox(key="settings_source").value == "저장한 설정"
    assert app.selectbox(key="settings_saved").value == "custom-v1"
    assert app.text_area(key="edit_agent_0_persona").value == "My changed persona."
    assert app.text_area(key="edit_seed_1_text").value == "A sharper response."


def test_invalid_edits_disable_save_and_start_without_losing_draft(editor_app):
    app, conf = editor_app
    app.text_input(key="edit_save_name").set_value("invalid").run()
    app.text_area(key="edit_agent_0_persona").set_value(" ").run()
    assert not app.exception
    assert app.error
    assert next(b for b in app.button if b.label == "다른 이름으로 저장").disabled
    assert next(b for b in app.button if b.label == "Start simulation").disabled
    app.text_area(key="edit_agent_0_persona").set_value("Repaired persona.").run()
    assert not app.error
    assert not next(b for b in app.button if b.label == "Start simulation").disabled
    assert not (conf / "experiments").exists()


def test_reloading_same_source_restores_every_edited_value(editor_app):
    app, _ = editor_app
    original = app.text_area(key="edit_agent_0_persona").value
    app.text_area(key="edit_agent_0_persona").set_value("Changed.").run()
    app.text_area(key="edit_seed_0_text").set_value("Changed opening.").run()
    app.number_input(key="edit_max_ticks").set_value(3).run()
    click(app, "불러오기")
    assert not app.exception
    assert app.text_area(key="edit_agent_0_persona").value == original
    assert app.text_area(key="edit_seed_0_text").value != "Changed opening."
    assert app.number_input(key="edit_max_ticks").value == 12
    assert any("변경한 항목이 없습니다" in caption.value for caption in app.caption)


def test_editor_loads_past_run_and_recovers_from_broken_settings(editor_app, inputs):
    app, conf = editor_app
    config, seed = inputs
    config.update(max_ticks=9, seed_file="missing/source.json")
    config["agents"][0]["persona"] = "Past run persona."
    seed["utterances"][0]["text"] = "Archived opening."
    corpus = conf.parent / "runs/past/corpus"
    corpus.mkdir(parents=True)
    (corpus / "run.json").write_text(json.dumps({"config": config}))
    (corpus / "seed.json").write_text(json.dumps(seed))
    app.selectbox(key="settings_source").set_value("실행 기록").run()
    app.selectbox(key="settings_run").set_value("past").run()
    click(app, "불러오기")
    assert not app.exception
    assert app.text_area(key="edit_agent_0_persona").value == "Past run persona."
    assert app.text_area(key="edit_seed_0_text").value == "Archived opening."
    assert app.number_input(key="edit_max_ticks").value == 9

    bad = conf / "experiments/broken"
    bad.mkdir(parents=True)
    (bad / "config.yaml").write_text("not: [valid")
    app.selectbox(key="settings_source").set_value("저장한 설정").run()
    app.selectbox(key="settings_saved").set_value("broken").run()
    click(app, "불러오기")
    assert not app.exception
    assert any("불러오지 못했습니다" in error.value for error in app.error)
    assert app.text_area(key="edit_agent_0_persona").value == "Past run persona."


def test_agent_rename_requires_a_valid_seed_speaker(editor_app):
    app, _ = editor_app
    app.text_input(key="edit_agent_0_name").set_value("Renamed").run()
    assert not app.exception
    assert next(b for b in app.button if b.label == "Start simulation").disabled
    app.selectbox(key="edit_seed_0_speaker").set_value("Renamed").run()
    assert not app.exception
    assert not app.error
    assert not next(b for b in app.button if b.label == "Start simulation").disabled
    app.number_input(key="edit_n_agents").set_value(3).run()
    assert len(app.session_state["settings_draft_config"]["agents"]) == 3
    app.number_input(key="edit_n_agents").set_value(4).run()
    assert next(b for b in app.button if b.label == "Start simulation").disabled
    app.text_area(key="edit_agent_3_persona").set_value("New participant.").run()
    assert not next(b for b in app.button if b.label == "Start simulation").disabled


def test_live_start_freezes_edited_inputs_before_launch(tmp_path, inputs):
    from conflict_sim.dashboard import start_live

    config, seed = inputs
    config.update(max_ticks=1, rule="round_robin", max_utterances=1, memory_mode="none")
    config["agents"][0]["persona"] = "Edited before starting."
    seed["utterances"][0]["text"] = "Edited initial post."
    expected = deepcopy(seed)
    process, directory = start_live(tmp_path / "runs, with spaces", config, seed)
    seed["utterances"][0]["text"] = "A later edit."
    try:
        assert process.wait(timeout=20) == 0, (directory / "console.log").read_text()
        archived = json.loads((directory / "corpus/run.json").read_text())
        assert archived["config"]["agents"] == config["agents"]
        assert archived["config"]["memory_mode"] == "none"
        assert archived["config"]["max_utterances"] == 1
        assert json.loads((directory / "corpus/seed.json").read_text()) == expected
        assert (directory.parent / "inputs/config.yaml").exists()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=3)
