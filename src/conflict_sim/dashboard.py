"""Streamlit live demo and saved-run viewer. Runs the CLI, never imports the engine.

uv run --extra dashboard streamlit run src/conflict_sim/dashboard.py
"""

import html
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from time import monotonic
from uuid import uuid4

import pandas as pd
import streamlit as st

from conflict_sim.settings import (
    edit_settings,
    load_settings,
    save_settings,
    set_editor,
    settings_actions,
)

CONF_DIR = Path(__file__).resolve().parents[2] / "conf"
PRESETS = {
    "": "현재 설정 · config.yaml",
    "wording": "조사 결과의 해석과 표현",
    "editing": "문서 재구성과 편집 절차",
}
TICK_HELP = "tick: 시뮬레이션 진행 단위입니다. 한 틱에 발화가 없거나 여러 개일 수 있습니다."
URGE_HELP = "urge: 에이전트가 보고한 발언 의사(0~1)입니다. 실제 게시 여부와는 다릅니다."
RULE_HELP = {
    "round_robin": "고정된 순서로 참여자를 확인합니다.",
    "random": "매 틱 참여자 순서를 무작위로 정합니다.",
    "bidding": (
        "bidding: 발언 의사가 가장 높은 한 명을 뽑고 확률 조건을 적용합니다. "
        "틱당 최대 한 명이 발언합니다."
    ),
    "event_driven": "직접 답글·이름 언급 또는 대기 중인 발언 의사가 있는 참여자가 반응합니다.",
}

LIST_COLUMNS = [
    "run",
    "created_at",
    "rule",
    "agents",
    "seed",
    "backend",
    "model",
    "utterances",
    "ticks",
    "stop_reason",
]


def discover_runs(root: Path) -> tuple[list[dict], list[str]]:
    """Find every corpus under root, newest first, plus the names of unreadable ones."""
    rows: list[dict] = []
    broken: list[str] = []
    for meta_path in sorted(root.rglob("corpus/run.json")):
        directory = meta_path.parent.parent
        name = str(directory.relative_to(root))
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            broken.append(name)
            continue
        config = meta.get("config", {})
        rows.append(
            {
                "run": name,
                "created_at": meta.get("created_at", ""),
                "rule": config.get("rule"),
                "agents": config.get("n_agents"),
                "seed": config.get("random_seed"),
                "backend": config.get("backend"),
                "model": config.get("model_speak"),
                "utterances": meta.get("generated_utterances"),
                "ticks": meta.get("ticks"),
                "stop_reason": meta.get("stop_reason"),
                "corpus": str(meta_path.parent),
            }
        )
    rows.sort(key=lambda row: row["created_at"], reverse=True)
    return rows, broken


def _read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def load_run(corpus: Path) -> dict:
    return {
        "meta": json.loads((corpus / "run.json").read_text(encoding="utf-8")),
        "utterances": _read_jsonl(corpus / "utterances.jsonl"),
        "decisions": _read_jsonl(corpus / "decisions.jsonl"),
    }


def measurements(run: dict, report: dict | None, *, live: bool = False) -> None:
    """Show public-post counts and optional, separately computed CRAFT scores."""
    generated = pd.DataFrame([row for row in run["utterances"] if row["timestamp"] > 0])
    st.subheader("Speaking share")
    if generated.empty:
        st.info("No generated comments; seed comments are excluded from speaking share.")
    else:
        counts = generated.groupby("speaker").size().rename("Generated comments").to_frame()
        names = [agent["name"] for agent in run["meta"].get("config", {}).get("agents", [])]
        counts = counts.reindex(sorted(set(names) | set(counts.index)), fill_value=0)
        counts["Share"] = counts["Generated comments"] / len(generated)
        st.bar_chart(counts["Generated comments"])
        st.dataframe(counts, width="stretch")
    st.caption("Seed comments are excluded. Compare order rules at a common generated-post count.")
    st.subheader("CRAFT forecast")
    st.caption(
        "p(t) predicts derailment into a personal attack; it is not general conflict intensity."
    )
    if report is None:
        st.info("No scores.json yet. 실시간 채점을 켜면 자동으로 분석합니다.")
        return
    if report.get("schema_version") != 2:
        st.warning("Re-score this run to use the current metric definitions (schema version 2).")
        return
    rows = report["series"]
    expected = [row["id"] for row in run["utterances"]]
    if [row["id"] for row in rows] != (expected[: len(rows)] if live else expected):
        st.warning("scores.json does not match this corpus. Re-score the run.")
        return
    if live:
        st.caption(
            f"채점 완료: {len(rows)} / {len(expected)}개 발화 (시드 포함) · "
            "생성보다 늦게 갱신될 수 있습니다."
        )
    metrics = report["metrics"]
    threshold = metrics["decision_threshold"]
    frame = pd.DataFrame(rows).rename_axis("Utterance index (seed included)")
    frame["Decision threshold"] = threshold
    st.line_chart(frame[["p", "Decision threshold"]])
    crossing = metrics["first_threshold_crossing"]
    if crossing is None:
        st.write(f"No threshold crossing (p > {threshold}).")
    else:
        st.write(
            f"First threshold crossing: index {crossing['index']}, "
            f"tick {crossing['tick']}, utterance {crossing['id']} (p > {threshold})."
        )
    st.dataframe(frame, width="stretch", hide_index=False)


def reply_depth(utterances: list[dict]) -> dict[str, int]:
    """Depth of each utterance in the reply tree. Dangling and cyclic parents stop the walk."""
    parents = {u["id"]: u["reply-to"] for u in utterances}
    depths: dict[str, int] = {}
    for utterance_id in parents:
        depth = 0
        seen = {utterance_id}
        current = parents[utterance_id]
        while current is not None and current not in seen:
            depth += 1
            seen.add(current)
            if current not in parents:
                break
            current = parents[current]
        depths[utterance_id] = depth
    return depths


# Deep threads stop indenting here, the way {{outdent}} is used on a real talk page.
# A bare string here would be a module-level expression, which Streamlit magic renders.
MAX_INDENT = 6

TALK_PAGE_CSS = """
<style>
.talk {
  background: #ffffff;
  color: #202122;
  font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  font-size: 14px;
  line-height: 1.6;
  padding: 1.5em 1.75em 2em;
  border: 1px solid #a2a9b1;
  box-sizing: border-box;
  width: 100%;
}
.talk .ombox {
  border: 1px solid #a2a9b1;
  border-left: 10px solid #36c;
  background: #f8f9fa;
  padding: 0.6em 0.9em;
  margin-bottom: 1.6em;
  font-size: 13px;
  color: #54595d;
}
.talk h2 {
  font-family: "Linux Libertine", Georgia, "Times New Roman", serif;
  font-size: 1.5em;
  font-weight: normal;
  color: #000;
  border-bottom: 1px solid #a2a9b1;
  padding-bottom: 0.25em;
  margin: 0 0 0.35em;
}
.talk .pagemeta { color: #54595d; font-size: 13px; margin: 0 0 1.8em; }
.talk .comment { margin: 0 0 1.1em; padding-left: 0.9em; }
.talk .comment[data-depth="0"] { padding-left: 0; }
.talk .comment[data-depth]:not([data-depth="0"]) { border-left: 1px solid #eaecf0; }
.talk .comment p { margin: 0 0 0.6em; }
.talk .sig { color: #54595d; font-size: 13px; }
.talk .user { color: #3366cc; }
.talk .outdent { color: #72777d; }
.talk .tag {
  background: #eaecf0;
  color: #54595d;
  font-size: 11px;
  padding: 0 0.4em;
  margin-left: 0.3em;
}
</style>
"""


def agent_label(agent: dict) -> str:
    stance = agent.get("stance") or agent.get("persona", "").split(". ")[0]
    if len(stance) > 85:
        stance = stance[:82] + "…"
    return f"{agent['name']} · {stance}" if stance else agent["name"]


def talk_page_html(
    utterances: list[dict], title: str, subtitle: str, agents: list[dict] | None = None
) -> str:
    """Render the thread the way a MediaWiki talk page reads: colon indents and signatures."""
    depths = reply_depth(utterances)
    labels = {agent["name"]: agent_label(agent) for agent in agents or []}
    parts = [
        TALK_PAGE_CSS,
        '<div class="talk">',
        '<div class="ombox">Synthetic run generated by conflict-sim. '
        "Not Wikipedia content and not evidence about real editor behavior.</div>",
        f"<h2>{html.escape(title)}</h2>",
        f'<p class="pagemeta">{html.escape(subtitle)}</p>',
    ]
    for utterance in utterances:
        depth = depths.get(utterance["id"], 0)
        indent = min(depth, MAX_INDENT) * 1.6
        body = "".join(
            f"<p>{html.escape(block.strip())}</p>"
            for block in re.split(r"\n\s*\n", utterance["text"])
            if block.strip()
        )
        seed = utterance["timestamp"] == 0
        when = '<span class="tag">seed</span>' if seed else f"tick {utterance['timestamp']}"
        if depth > MAX_INDENT:
            when += f' · <span class="outdent">outdented from depth {depth}</span>'
        label = html.escape(labels.get(utterance["speaker"], utterance["speaker"]))
        parts.append(
            f'<div class="comment" data-depth="{depth}" '
            f'style="margin-left:{indent:g}em" title="{html.escape(utterance["id"])}">'
            f"{body}"
            f'<div class="sig">— <span class="user">{label}'
            f"</span> · {when}</div>"
            "</div>"
        )
    parts.append("</div>")
    return "\n".join(parts)


def show_reflections(agents: list[dict], decisions: list[dict]) -> None:
    st.subheader("Agent reflections")
    st.caption("Private self-reports · 다른 참여자에게 공유되지 않는 자기보고")
    st.caption(URGE_HELP)
    latest = {event["agent"]: event for event in decisions if event.get("reflection")}
    if not agents:
        agents = [{"name": name} for name in sorted({event["agent"] for event in decisions})]
    with st.container(height=500):
        for agent in agents:
            event = latest.get(agent["name"])
            with st.expander(agent_label(agent), expanded=True):
                if event is None:
                    st.caption("아직 기록된 성찰이 없습니다.")
                    continue
                st.caption(
                    f"Tick {event['tick']} · urge {event['urge']:.2f} · "
                    f"{'Posted' if event['posted'] else 'Not posted'}"
                )
                st.text(event["reflection"])
                if event.get("decision_source") == "retry":
                    st.caption(f"Reused from tick {event['decision_tick']}")


def replay_slice(run: dict, tick: int) -> dict:
    """A completed-tick snapshot; future posts and reflections must stay hidden."""
    return {
        "utterances": [row for row in run["utterances"] if row["timestamp"] <= tick],
        "decisions": [event for event in run["decisions"] if event["tick"] <= tick],
    }


def replay_view(run: dict, name: str) -> None:
    if st.session_state.get("replay_run") != name:
        st.session_state.update(replay_run=name, replay_tick=0, replay_playing=False)
    # Keep the position when a control reruns before the slider is rendered.
    st.session_state.replay_tick = st.session_state.get("replay_tick", 0)
    maximum = max(
        [
            run["meta"].get("ticks", 0),
            *(row["timestamp"] for row in run["utterances"]),
            *(event["tick"] for event in run["decisions"]),
        ]
    )
    speed = st.select_slider("재생 속도 (배속)", options=[0.5, 1.0, 2.0], value=1.0)
    if st.session_state.replay_playing and monotonic() >= st.session_state.replay_next_at:
        st.session_state.replay_tick = min(maximum, st.session_state.replay_tick + 1)
        st.session_state.replay_next_at = monotonic() + 1 / speed
        if st.session_state.replay_tick == maximum:
            st.session_state.replay_playing = False
            st.rerun()
    columns = st.columns(4)
    if columns[0].button("처음", key="replay_reset"):
        st.session_state.update(replay_tick=0, replay_playing=False)
        st.rerun()
    if columns[1].button("이전 tick", disabled=st.session_state.replay_tick == 0):
        st.session_state.replay_tick -= 1
        st.session_state.replay_playing = False
        st.rerun()
    if columns[2].button(
        "일시정지" if st.session_state.replay_playing else "재생", disabled=maximum == 0
    ):
        if st.session_state.replay_tick == maximum:
            st.session_state.replay_tick = 0
        st.session_state.replay_playing = not st.session_state.replay_playing
        st.session_state.replay_next_at = monotonic() + 1 / speed
        st.rerun()
    if columns[3].button("다음 tick", disabled=st.session_state.replay_tick == maximum):
        st.session_state.replay_tick += 1
        st.session_state.replay_playing = False
        st.rerun()
    if maximum:
        st.slider(
            "재생 위치 (tick)",
            0,
            maximum,
            key="replay_tick",
            help=TICK_HELP,
            on_change=lambda: st.session_state.update(replay_playing=False),
        )
    tick = st.session_state.replay_tick
    st.caption(f"기록 재생 · tick {tick} / {maximum} · API 호출 없음 · 상단 통계는 전체 실행 기준")
    st.caption("각 틱이 끝난 상태를 보여줍니다. 같은 틱의 발화와 성찰은 함께 표시됩니다.")
    snapshot = replay_slice(run, tick)
    agents = run["meta"].get("config", {}).get("agents", [])
    transcript, reflections = st.columns([3, 2])
    with transcript:
        st.subheader("Public conversation")
        st.html(talk_page_html(snapshot["utterances"], name, f"Replay · tick {tick}", agents))
    with reflections:
        show_reflections(agents, snapshot["decisions"])


def start_scoring(directory: Path, *, live: bool = False) -> subprocess.Popen:
    with (directory / "score.log").open("w", encoding="utf-8") as log:
        return subprocess.Popen(
            [
                sys.executable,
                "-m",
                "conflict_sim.score",
                *(["--live"] if live else []),
                str(directory.resolve()),
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )


def stop_scoring() -> None:
    process = st.session_state.get("score_process")
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
    st.session_state.score_busy = False
    for key in ("score_process", "score_attempt", "score_error"):
        st.session_state.pop(key, None)


def scoring_view(run: dict, directory: Path, *, live: bool = False) -> None:
    attempt = (str(directory.resolve()), live)
    if st.session_state.get("auto_scoring") and st.session_state.get("score_attempt") != attempt:
        stop_scoring()
        st.session_state.score_attempt = attempt
        try:
            st.session_state.score_process = start_scoring(directory, live=live)
            st.session_state.score_busy = True
        except OSError as exc:
            st.session_state.score_error = str(exc)
        st.rerun()
    process = (
        st.session_state.get("score_process")
        if st.session_state.get("score_attempt") == attempt
        else None
    )
    running = process is not None and process.poll() is None
    if process is not None and not running and st.session_state.get("score_busy"):
        st.session_state.score_busy = False
        st.rerun()
    score_path = directory / ("live-scores.json" if live else "scores.json")
    st.caption(
        "게시된 공개 발화만 분석합니다. OpenAI 호출은 없으며, "
        "첫 채점에는 모델 다운로드가 필요할 수 있습니다."
    )
    if running:
        st.info(
            "CRAFT 실시간 채점 · 새 발화를 기다리거나 분석하고 있습니다."
            if live
            else "CRAFT 채점 중…"
        )
    elif process is not None:
        if process.returncode == 0 and score_path.is_file():
            st.success("채점 완료 · 아래 측정 결과를 확인하세요.")
        else:
            st.error(
                "채점에 실패했습니다. 로그를 확인한 뒤 토글을 껐다 켜서 다시 시도하세요. "
                "기존 점수는 유지됩니다."
            )
            log = directory / "score.log"
            if log.is_file():
                with st.expander("채점 오류 로그", expanded=True):
                    st.code(log.read_text(encoding="utf-8", errors="replace")[-6000:])
    if st.session_state.get("score_attempt") == attempt and st.session_state.get("score_error"):
        st.error(f"채점을 시작하지 못했습니다: {st.session_state.score_error}")
    try:
        report = (
            json.loads(score_path.read_text(encoding="utf-8")) if score_path.is_file() else None
        )
        measurements(run, report, live=live)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        st.warning(f"Could not read scores.json: {exc}")


@st.cache_data(show_spinner=False)
def _cached_runs(root: str, stamp: tuple) -> tuple[list[dict], list[str]]:
    return discover_runs(Path(root))


@st.cache_data(show_spinner=False)
def _cached_run(corpus: str, stamp: tuple) -> dict:
    return load_run(Path(corpus))


def _stamp_of(paths) -> tuple:
    """Include child paths so nested additions, removals and edits invalidate the cache."""
    stamps = []
    for path in sorted(paths):
        try:
            info = path.stat()
        except FileNotFoundError:
            continue
        stamps.append((str(path), info.st_mtime_ns, info.st_ctime_ns, info.st_size))
    return tuple(stamps)


def start_live(root: Path, config: dict, seed: dict) -> tuple[subprocess.Popen, Path]:
    folder = root.resolve() / "live" / f"{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:8]}"
    # Freeze the edited inputs separately, before Hydra reserves the output directory.
    settings = save_settings(folder, "inputs", config, seed)
    directory = folder / "run"
    directory.mkdir()
    with (directory / "console.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "conflict_sim.cli",
                "--config-path",
                str(settings.parent),
                "--config-name",
                settings.stem,
                "live=true",
                f"seed_file={json.dumps(str(settings.parent / 'seed.json'))}",
                f"hydra.run.dir={json.dumps(str(directory))}",
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    return process, directory


def stop_live(process: subprocess.Popen, directory: Path) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)
    path = directory / "live.json"
    progress = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if progress.get("status") == "completed":
        return
    progress.update(status="stopped", message="Stopped by you · partial conversation retained")
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(progress, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def live_progress() -> None:
    process = st.session_state.get("live_process")
    if process is None:
        st.info("Choose a mode and press Start simulation.")
        return
    if process.poll() is not None and st.session_state.get("live_busy"):
        st.session_state.live_busy = False
        st.cache_data.clear()
        st.rerun()

    directory = st.session_state.live_directory
    path = directory / "live.json"
    progress = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    status = progress.get("status", "starting")
    message = progress.get("message", "Starting simulation…")
    if process.poll() is not None and status not in {"completed", "failed", "stopped"}:
        status, message = "failed", "The process exited before saving a result. See console.log."
        stop_scoring()
    if status == "failed":
        st.error(message)
    elif status == "stopped":
        st.warning(message)
    elif status == "completed":
        st.success(message)
    else:
        st.info(message)
    st.caption(f"Run: {directory}")
    config = progress.get("config", {})
    ticks = progress.get("ticks", 0)
    maximum = config.get("max_ticks", 1)
    utterances = progress.get("utterances", [])
    decisions = progress.get("decisions", [])
    columns = st.columns(3)
    columns[0].metric("Generated comments", max(0, len(utterances) - 2))
    columns[1].metric("Completed ticks", f"{ticks} / {maximum}", help=TICK_HELP)
    columns[2].metric("Status", status.capitalize())
    st.progress(min(ticks / maximum, 1.0))

    transcript, reflections = st.columns([3, 2])
    with transcript:
        st.subheader("Public conversation")
        if utterances:
            with st.container(height=500, autoscroll=True):
                st.html(
                    talk_page_html(
                        utterances,
                        "Article discussion",
                        config.get("rule", ""),
                        config.get("agents", []),
                    )
                )
    with reflections:
        show_reflections(config.get("agents", []), decisions)
    if decisions:
        with st.expander("Decision log"):
            st.dataframe(pd.DataFrame(decisions), width="stretch", hide_index=True)
    if utterances:
        st.subheader("실시간 측정")
        scoring_view({"meta": {"config": config}, "utterances": utterances}, directory, live=True)


def live_view(root: Path) -> None:
    process = st.session_state.get("live_process")
    running = process is not None and process.poll() is None
    source = st.selectbox(
        "설정 출처",
        ["시나리오", "저장한 설정", "실행 기록"],
        key="settings_source",
        disabled=running,
    )
    overrides = []
    path = None
    label = ""
    if source == "시나리오":
        preset = st.selectbox(
            "Scenario / 시나리오",
            list(PRESETS),
            format_func=PRESETS.get,
            key="live_preset",
            disabled=running,
        )
        path, label = CONF_DIR / "config.yaml", PRESETS[preset]
        overrides = [f"+scenario={preset}"] if preset else []
    elif source == "저장한 설정":
        paths = {
            p.parent.name: p
            for p in sorted((CONF_DIR / "experiments").glob("*/config.yaml"))
            if not p.parent.name.startswith(".")
        }
        selected = st.selectbox("저장한 설정", list(paths), key="settings_saved", disabled=running)
        if selected:
            path, label = paths[selected], selected
        else:
            st.info("아래에서 설정을 편집하고 새 이름으로 저장하면 여기에 나타납니다.")
    else:
        rows, _ = _cached_runs(str(root), _stamp_of(root.rglob("corpus/run.json")))
        paths = {row["run"]: Path(row["corpus"]) / "run.json" for row in rows}
        selected = st.selectbox("실행 기록", list(paths), key="settings_run", disabled=running)
        if selected:
            path, label = paths[selected], selected
        else:
            st.info("불러올 실행 기록이 없습니다.")
    load = st.button("불러오기", disabled=running or path is None)
    st.caption("불러오면 편집 중인 값을 선택한 설정으로 바꿉니다.")
    if load or "settings_config" not in st.session_state:
        try:
            config, seed = load_settings(path or CONF_DIR / "config.yaml", overrides)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            st.error(f"설정을 불러오지 못했습니다: {exc}")
        else:
            set_editor(config, seed, label or PRESETS[""])
    if "settings_config" not in st.session_state:
        return
    if notice := st.session_state.pop("settings_notice", None):
        st.success(notice)
    config, seed = edit_settings(disabled=running, rule_help=RULE_HELP, tick_help=TICK_HELP)
    valid = settings_actions(config, seed, CONF_DIR / "experiments", disabled=running)
    if valid:
        with st.expander("초기 대화와 참여자 입장"):
            rows = [dict(row, **{"reply-to": row["reply_to"]}) for row in seed["utterances"]]
            st.html(talk_page_html(rows, "초기 대화", config["language"], config["agents"]))
            for agent in config["agents"]:
                st.text(agent_label(agent))
    if st.button("Start simulation", type="primary", disabled=running or not valid):
        try:
            process, directory = start_live(root, config, seed)
        except (OSError, ValueError) as exc:
            st.error(f"Could not start the simulation: {exc}")
        else:
            st.session_state.update(live_process=process, live_directory=directory, live_busy=True)
            st.rerun()
    if st.button("Stop simulation", disabled=not running):
        stop_live(process, st.session_state.live_directory)
        st.session_state.live_busy = False
        st.rerun()
    st.fragment(run_every=0.5 if running or st.session_state.get("score_busy") else None)(
        live_progress
    )()


def main() -> None:
    st.set_page_config(page_title="ConflictDynamics", layout="wide")
    st.title("ConflictDynamics")

    busy = st.session_state.get("live_busy", False)
    page = st.sidebar.radio("View", ["Live simulation", "Saved runs"], disabled=busy)
    enabled = st.sidebar.toggle(
        "실시간 채점",
        key="auto_scoring",
        help=(
            "켜면 새 공개 발화를 백그라운드에서 분석합니다. 저장된 실행은 한 번 채점합니다. "
            "끄면 채점 작업만 중지됩니다."
        ),
    )
    if not enabled:
        stop_scoring()
    root_input = st.sidebar.text_input("runs directory", value="runs", disabled=busy)
    if st.sidebar.button("Reload"):
        st.cache_data.clear()
    root = Path(root_input).expanduser()

    if page == "Live simulation":
        live_view(root)
        return

    rows, broken = _cached_runs(str(root), _stamp_of(root.rglob("corpus/run.json")))
    if broken:
        st.warning(f"Skipped {len(broken)} run(s) with an unreadable run.json: {', '.join(broken)}")
    if not rows:
        st.info(f"No corpus found under {root.resolve()}. Run `uv run conflict-sim` first.")
        return

    st.dataframe(pd.DataFrame(rows)[LIST_COLUMNS], width="stretch", hide_index=True)

    names = [row["run"] for row in rows]
    selected = st.selectbox("Run", names)
    row = next(item for item in rows if item["run"] == selected)
    corpus = Path(row["corpus"])
    run = _cached_run(
        str(corpus),
        _stamp_of(corpus / name for name in ("run.json", "utterances.jsonl", "decisions.jsonl")),
    )

    decisions = run["decisions"]
    urges = [
        event["urge"]
        for event in decisions
        if "urge" in event and event.get("decision_source", "new") == "new"
    ]
    columns = st.columns(4)
    columns[0].metric("Generated", run["meta"].get("generated_utterances"))
    columns[1].metric("Ticks", run["meta"].get("ticks"), help=TICK_HELP)
    columns[2].metric("Stopped by", run["meta"].get("stop_reason"))
    columns[3].metric(
        "Mean urge", round(sum(urges) / len(urges), 3) if urges else "—", help=URGE_HELP
    )

    transcript_tab, decisions_tab, measurements_tab = st.tabs(
        ["Transcript", "Decisions", "Measurements"]
    )

    with transcript_tab:
        config = run["meta"].get("config", {})
        subtitle = " · ".join(
            str(part)
            for part in (
                config.get("rule"),
                f"{config.get('n_agents')} editors",
                f"seed {config.get('random_seed')}",
                config.get("model_speak") or config.get("backend"),
            )
            if part
        )
        st.caption(RULE_HELP.get(config.get("rule"), ""))
        if st.toggle("기록 재생", key="replay_mode"):
            st.fragment(run_every=0.25 if st.session_state.get("replay_playing") else None)(
                replay_view
            )(run, selected)
        else:
            st.session_state.replay_playing = False
            st.html(talk_page_html(run["utterances"], selected, subtitle, config.get("agents", [])))

    with decisions_tab:
        if decisions:
            st.dataframe(pd.DataFrame(decisions), width="stretch", hide_index=True)
            reflections = [event for event in decisions if event.get("reflection")]
            if reflections:
                labels = {
                    agent["name"]: agent_label(agent)
                    for agent in run["meta"].get("config", {}).get("agents", [])
                }
                editor = st.selectbox(
                    "Agent",
                    sorted({event["agent"] for event in reflections}),
                    format_func=lambda name: labels.get(name, name),
                )
                entries = [event for event in reflections if event["agent"] == editor]
                tick = st.selectbox("Reflection tick", [event["tick"] for event in entries])
                event = next(event for event in entries if event["tick"] == tick)
                origin = event.get("decision_tick", tick)
                status = "Reused" if event.get("decision_source") == "retry" else "New"
                st.caption(f"{status} reflection · originally recorded at tick {origin}")
                st.text(event["reflection"])
            else:
                st.info("This run recorded no reflections.")
        else:
            st.info("This run recorded no decisions.")

    with measurements_tab:
        st.fragment(run_every=0.5 if st.session_state.get("score_busy") else None)(scoring_view)(
            run, corpus.parent
        )


if __name__ == "__main__":
    main()
