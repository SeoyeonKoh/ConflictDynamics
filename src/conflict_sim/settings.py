"""Edit and save complete Hydra settings together with their public seed."""

import json
import re
from copy import deepcopy
from difflib import unified_diff
from pathlib import Path
from tempfile import TemporaryDirectory

import streamlit as st
import yaml
from hydra import compose, initialize_config_dir
from hydra.errors import HydraException
from omegaconf import OmegaConf
from omegaconf.errors import OmegaConfBaseException

from .models import Config
from .storage import load_seed, parse_seed, write_json

PROJECT_DIR = Path(__file__).resolve().parents[2]


def validate_settings(config: dict, seed: dict) -> Config:
    cfg = Config.model_validate(config)
    thread = parse_seed(seed)
    missing = {u.speaker for u in thread.utterances} - {a.name for a in cfg.agents}
    if missing:
        raise ValueError(f"초기 대화 작성자에 해당하는 에이전트가 없습니다: {sorted(missing)}")
    return cfg


def load_settings(path: Path, overrides: list[str] | None = None) -> tuple[dict, dict]:
    """A run uses its archived seed, never the original seed_file path."""
    if path.name == "run.json":
        config = json.loads(path.read_text(encoding="utf-8"))["config"]
        seed_path = path.parent / "seed.json"
    else:
        try:
            with initialize_config_dir(version_base="1.3", config_dir=str(path.parent.resolve())):
                raw = compose(config_name=path.stem, overrides=overrides or [])
            config = OmegaConf.to_container(raw, resolve=True, throw_on_missing=True)
        except (HydraException, OmegaConfBaseException, yaml.YAMLError) as exc:
            raise ValueError(str(exc)) from exc
        seed_path = (
            path.parent / "seed.json"
            if (path.parent / "seed.json").is_file()
            else PROJECT_DIR / (config.get("seed_file") or "conf/seeds/example.json")
        )
    _, seed = load_seed(seed_path)
    return validate_settings(config, seed).model_dump(), seed


def _literal_strings(value):
    """Escape interpolation in editor text before Hydra reads the saved YAML."""
    if isinstance(value, dict):
        return {key: _literal_strings(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_literal_strings(item) for item in value]
    if isinstance(value, str):
        return re.sub(r"(\\*)\$\{", lambda m: "\\" * (2 * len(m[1]) + 1) + "${", value)
    return value


def save_settings(root: Path, name: str, config: dict, seed: dict) -> Path:
    """Publish YAML and seed as one new folder; existing settings are immutable."""
    if not re.fullmatch(r"[\w-]{1,80}", name):
        raise ValueError("설정 이름은 1~80자의 한글·영문·숫자·밑줄·하이픈으로 작성하세요.")
    data = validate_settings(config, seed).model_dump()
    destination = root.resolve() / name
    if destination.exists():
        raise FileExistsError("같은 이름의 설정이 있습니다. 새 이름으로 저장하세요.")
    seed_path = destination / "seed.json"
    data["seed_file"] = str(
        seed_path.relative_to(PROJECT_DIR) if seed_path.is_relative_to(PROJECT_DIR) else seed_path
    )
    data["live"] = False
    root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".settings-", dir=root) as temporary:
        staging = Path(temporary)
        write_json(staging / "seed.json", seed)
        (staging / "config.yaml").write_text(
            yaml.safe_dump(_literal_strings(data), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        restored, _ = load_settings(staging / "config.yaml")
        if restored != data:
            raise ValueError("Hydra가 저장한 설정을 원문 그대로 읽지 못했습니다.")
        staging.rename(destination)
    return destination / "config.yaml"


def set_editor(config: dict, seed: dict, label: str) -> None:
    # Reset widgets before they are rendered, including those on a previously hidden tab.
    for key in list(st.session_state):
        if key.startswith("edit_"):
            del st.session_state[key]
    values = {
        f"edit_{key}": value
        for key, value in config.items()
        if key not in {"agents", "seed_file", "live"}
    }
    values.update(
        edit_max_utterances=config["max_utterances"] or 0,
        edit_model_decide=config["model_decide"] or "",
        edit_model_speak=config["model_speak"] or "",
        edit_save_name="",
    )
    for i, agent in enumerate(config["agents"]):
        for field, value in agent.items():
            values[f"edit_agent_{i}_{field}"] = "" if value is None else value
    for i, utterance in enumerate(seed["utterances"]):
        for field in ("speaker", "text"):
            values[f"edit_seed_{i}_{field}"] = utterance[field]
    # Explicit assignments also reset the browser when the widget's default is
    # unchanged. Deleting keys alone can leave stale text visible in Streamlit.
    st.session_state.update(values)
    st.session_state.settings_config = config
    st.session_state.settings_seed = seed
    st.session_state.settings_label = label
    st.session_state.settings_draft_config = deepcopy(config)
    st.session_state.settings_draft_seed = deepcopy(seed)
    st.session_state.pop("settings_widget_values", None)


def edit_settings(*, disabled: bool, rule_help: dict, tick_help: str) -> tuple[dict, dict]:
    if st.session_state.get("settings_disabled") != disabled:
        for key, value in st.session_state.get("settings_widget_values", {}).items():
            st.session_state[key] = value
    st.session_state.settings_disabled = disabled
    # Widget identity can change when disabled or when its options change. Keep the
    # latest draft as the default, separate from the original used in the diff.
    config = deepcopy(st.session_state.settings_draft_config)
    seed = deepcopy(st.session_state.settings_draft_seed)
    st.caption(f"불러온 설정: {st.session_state.settings_label}")
    basic, participants, conversation, advanced = st.tabs(
        ["실행 조건", "에이전트", "초기 대화", "모델·예산"]
    )
    with basic:
        columns = st.columns(3)
        for column, field, label, options in (
            (0, "backend", "Backend", ["demo", "openai"]),
            (1, "rule", "Order rule", list(rule_help)),
            (2, "memory_mode", "Memory", ["none", "summary", "full"]),
        ):
            config[field] = columns[column].selectbox(
                label,
                options,
                index=options.index(config[field]),
                key=f"edit_{field}",
                disabled=disabled,
            )
        config["max_ticks"] = columns[0].number_input(
            "Max ticks",
            min_value=1,
            value=config["max_ticks"],
            key="edit_max_ticks",
            disabled=disabled,
            help=tick_help,
        )
        config["random_seed"] = columns[1].number_input(
            "Random seed",
            value=config["random_seed"],
            step=1,
            key="edit_random_seed",
            disabled=disabled,
        )
        config["max_utterances"] = (
            columns[2].number_input(
                "최대 생성 발화 수 (0: 제한 없음)",
                min_value=0,
                value=config["max_utterances"] or 0,
                key="edit_max_utterances",
                disabled=disabled,
                help="초기 대화 2개를 제외합니다. 조건 비교 시 같은 발화 수를 지정할 수 있습니다.",
            )
            or None
        )
        config["silence_limit"] = columns[0].number_input(
            "연속 무발화 종료 틱",
            min_value=1,
            value=config["silence_limit"],
            key="edit_silence_limit",
            disabled=disabled,
        )
        st.caption(rule_help[config["rule"]])
        st.caption("demo: 고정 예시 응답 · openai: .env의 키로 유료 API 호출")
    with participants:
        count = st.number_input(
            "에이전트 수",
            min_value=3,
            max_value=6,
            value=config["n_agents"],
            key="edit_n_agents",
            disabled=disabled,
        )
        st.caption(
            "입장은 화면 표시용입니다. 실제 행동은 성향에 입장과 반응 방식을 적어 조정하세요."
        )
        agents = config["agents"]
        for i in range(count):
            if i >= len(agents):
                agents.append(
                    {"name": f"Agent{i + 1}", "stance": None, "persona": "", "availability": 0.9}
                )
            agent = agents[i]
            with st.expander(
                f"{i + 1}. {agent['name']} · {agent['stance'] or '입장 미입력'}", expanded=i == 0
            ):
                columns = st.columns([1, 2, 1])
                agent["name"] = columns[0].text_input(
                    "이름",
                    agent["name"],
                    key=f"edit_agent_{i}_name",
                    disabled=disabled,
                )
                agent["stance"] = (
                    columns[1].text_input(
                        "입장 (화면 표시용)",
                        agent["stance"] or "",
                        key=f"edit_agent_{i}_stance",
                        disabled=disabled,
                    )
                    or None
                )
                agent["availability"] = columns[2].number_input(
                    "참여 가능성",
                    min_value=0.0,
                    max_value=1.0,
                    step=0.1,
                    value=float(agent["availability"]),
                    key=f"edit_agent_{i}_availability",
                    disabled=disabled,
                )
                agent["persona"] = st.text_area(
                    "성향 (LLM에 전달)",
                    agent["persona"],
                    height=140,
                    key=f"edit_agent_{i}_persona",
                    disabled=disabled,
                )
        config.update(agents=agents[:count], n_agents=count)
    with conversation:
        st.caption(
            "첫 발화에 두 번째 발화가 답하는 초기 대화입니다. 이후 발화는 실행 중 생성됩니다."
        )
        names = list(dict.fromkeys(a["name"] for a in config["agents"] if a["name"].strip()))
        for i, utterance in enumerate(seed["utterances"]):
            utterance["speaker"] = st.selectbox(
                f"{i + 1}번째 발화 작성자",
                names,
                index=names.index(utterance["speaker"]) if utterance["speaker"] in names else None,
                key=f"edit_seed_{i}_speaker",
                disabled=disabled,
            )
            utterance["text"] = st.text_area(
                f"{i + 1}번째 발화 내용",
                utterance["text"],
                height=120,
                key=f"edit_seed_{i}_text",
                disabled=disabled,
            )
        if seed["utterances"] != st.session_state.settings_seed["utterances"]:
            seed["edited"] = True
    with advanced:
        columns = st.columns(2)
        for column, field, label in (
            (0, "model_decide", "판단 모델"),
            (1, "model_speak", "발언 모델"),
            (0, "language", "대화 언어"),
        ):
            config[field] = (
                columns[column].text_input(
                    label,
                    config[field] or "",
                    key=f"edit_{field}",
                    disabled=disabled,
                )
                or None
            )
        efforts = [None, "none", "low", "medium", "high", "xhigh", "max"]
        config["reasoning_effort"] = columns[1].selectbox(
            "추론 수준",
            efforts,
            index=efforts.index(config["reasoning_effort"]),
            format_func=lambda value: "모델 기본값" if value is None else value,
            key="edit_reasoning_effort",
            disabled=disabled,
        )
        config["temperature"] = columns[0].number_input(
            "Temperature",
            min_value=0.0,
            max_value=2.0,
            step=0.1,
            value=float(config["temperature"]),
            key="edit_temperature",
            disabled=disabled,
        )
        for column, field, label in (
            (1, "context_size", "최근 대화 문맥 수"),
            (0, "max_tokens_decide", "판단 응답 토큰 상한"),
            (1, "max_tokens_speak", "발언 응답 토큰 상한"),
            (0, "max_total_tokens", "실행 전체 토큰 예산"),
            (1, "max_input_chars", "호출당 입력 문자 상한"),
        ):
            config[field] = columns[column].number_input(
                label,
                min_value=1,
                value=config[field],
                key=f"edit_{field}",
                disabled=disabled,
            )
        st.caption("토큰 예산은 다음 호출 전에 검사하므로 한 응답만큼 초과할 수 있습니다.")
    st.session_state.settings_draft_config = config
    st.session_state.settings_draft_seed = seed
    st.session_state.settings_widget_values = {
        key: st.session_state[key] for key in st.session_state if key.startswith("edit_")
    }
    return config, seed


def settings_actions(config: dict, seed: dict, root: Path, *, disabled: bool) -> bool:
    """Show the edited diff and save a named copy. Return whether it can run."""
    before = {"config": st.session_state.settings_config, "seed": st.session_state.settings_seed}
    after = {"config": config, "seed": seed}
    with st.expander("불러온 설정과 비교"):
        diff = "\n".join(
            unified_diff(
                yaml.safe_dump(before, allow_unicode=True, sort_keys=False).splitlines(),
                yaml.safe_dump(after, allow_unicode=True, sort_keys=False).splitlines(),
                fromfile="불러온 설정",
                tofile="현재 편집",
                lineterm="",
            )
        )
        if diff:
            st.code(diff, language="diff")
        else:
            st.caption("변경한 항목이 없습니다.")
    valid = True
    try:
        validate_settings(config, seed)
    except ValueError as exc:
        valid = False
        st.error(f"설정을 확인해 주세요: {exc}")
    columns = st.columns([3, 1], vertical_alignment="bottom")
    name = columns[0].text_input(
        "새 설정 이름",
        key="edit_save_name",
        disabled=disabled,
        placeholder="예: 방어적-Alex-v1",
        help="한글·영문·숫자·밑줄·하이픈, 최대 80자",
    )
    if columns[1].button("다른 이름으로 저장", disabled=disabled or not valid or not name):
        try:
            path = save_settings(root, name, config, seed)
        except (OSError, ValueError) as exc:
            st.error(str(exc))
        else:
            st.session_state.settings_notice = f"저장했습니다: {path.parent.name}"
            st.rerun()
    return valid
