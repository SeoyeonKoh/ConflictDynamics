# ruff: noqa: E501  (Korean prompt text: wide characters count double)
"""The human prompt style (`prompt_style: human`): what one person knows, told the way they would
tell it to themselves.

The engine runs on ids. This layer turns an agent's view into Korean narrative with people's names
and task titles, lets the model choose from those names and titles, and maps the choice back to
ids. Only what the person has seen, been told or done is rendered: no one else's task state or
progress, no draft still in review. Probes against the engine's JSON prompts are in
`docs/agent-context-research.md` (2026-10-08).

A demo backend cannot read narrative, so every call also sets `ENGINE_PAYLOAD` to the engine's
payload and accepts a reply in the engine's own shape (ids, ticks).
"""

import re
from typing import Literal

from pydantic import BaseModel, create_model

from ..models import LUNCH_TICKS, Action, Config, Decision, PlanItem, Thread

PLACE_KO = {"lobby": "로비", "office": "사무실 내 자리", "desk": "내 자리", "meeting_room": "회의실",
            "focus_room": "집중 업무실", "pantry": "탕비실", "cafeteria": "구내식당"}  # fmt: skip
FACE_KO = {"neutral": "평소 같음", "pleased": "기분 좋아 보임", "amused": "웃고 있음",
           "surprised": "놀란 표정", "tired": "피곤해 보임", "anxious": "불안해 보임",
           "annoyed": "짜증 나 보임", "angry": "화나 보임"}  # fmt: skip
TENURE_KO = {"0_to_2_years": "입사 2년 이하", "3_to_6_years": "경력 3~6년",
             "7_to_10_years": "경력 7~10년", "10_plus_years": "경력 10년 이상"}  # fmt: skip
POSITION_KO = {"team_manager": "팀 총괄 매니저", "functional_lead": "팀 리드",
               "senior_member": "선임", "member": "팀원"}  # fmt: skip
# DISC as a communication tendency only: the persona policy forbids reading competence,
# aggression, honesty or conflict-proneness into it.
DISC_KO = {
    "D": "결론부터 짧고 단정적으로 말하고, 빨리 정하고 넘어가길 원한다. 돌려 말하지 않는다.",
    "i": "친근하고 말이 많은 편이다. 분위기를 띄우고 잡담도 잘하며, 감정을 말에 드러낸다.",
    "S": "부드럽고 공손하게 말한다. 상대 사정을 먼저 묻고 맞춰 주는 편이라, 직접 재촉하거나 "
    "거절하는 말은 망설인다.",
    "C": "정확하게 말하려 한다. 근거와 숫자를 챙기고, 단정하기보다 조심스럽게 표현한다.",
}
KIND_KO = {
    "work": "내 일을 한다 (필요한 게 다 갖춰진 일만 진척이 난다; 자리나 집중 업무실에서)",
    "prepare": "앞 단계를 기다리는 내 일을 미리 살펴보거나 준비한다 (task에 그 일; 진척은 나지 않는다)",
    "rest": "쉬거나 자리에서 자잘한 일을 한다 (일 진척 없음; 탕비실·구내식당·로비에서 쉬면 피로가 풀린다)",
    "move": "다른 곳으로 간다",
    "eat": "밥을 먹는다 (구내식당)",
    "talk": "지금 같은 곳에 있는 사람과 직접 대화를 시작한다",
    "message": "메신저로 누군가에게 메시지를 보낸다 (상대는 다음 15분 안에 읽는다)",
    "chat": "오늘 메시지를 주고받은 사람과 메신저로 실시간 대화를 이어간다",
    "gossip": "어떤 사람(about)에 대한 얘기를 다른 사람에게 사적으로 전한다",
    "report": "상사에게 내 상황을 보고한다",
    "request": "내 일의 마감을 미뤄 달라고 요청한다",
    "approve": "검토를 기다리는 일을 승인한다 (say에 한 문장 이유)",
    "reject": "검토를 기다리는 일을 돌려보낸다 (say에 무엇이 부족한지)",
    "assign": "담당자 없는 일을 맡긴다: person이 담당, people이 함께할 사람 (매니저만)",
    "help": "도움을 구하는 남의 일에 합류한다",
    "ask_help": "내 일에 도움을 구한다",
    "leave": "오늘은 퇴근한다 (내 일이 다 끝났거나 갈 시간일 때)",
    "evaluate": "평가 기간에 누군가의 일을 0~1로 평가한다 (평가 권한이 있을 때)",
}
_SPOKEN = {"talk", "message", "gossip", "report", "evaluate", "ask_help", "approve", "reject"}
FACES = ("neutral", "pleased", "amused", "surprised", "tired", "anxious", "annoyed", "angry")

CANDOR = """남의 말에 무조건 맞장구치거나 부탁을 다 들어주지 않는다. 동의하지 않으면 성격대로 말하고, 무리한
  부탁은 거절하거나 조건을 단다. 다만 예의는 지킨다."""
NORMS = f"""이것은 실제 회사 사람의 하루를 흉내 내는 시뮬레이션이다. 모범 직원이나 일 처리 프로그램처럼 굴지
말고, 이 사람이 지금 이 상황에서 실제로 할 법한 행동을 골라라. 늘 최선의 선택일 필요는 없다.
- 너는 네가 직접 보거나 듣거나 받은 것만 안다. 다른 사람 일이 얼마나 됐는지는 그 사람이 말해 주거나
  끝났다는 연락이 오기 전엔 모른다. 모르는 건 짐작하거나 물어봐야 알 수 있다.
- 사람은 같은 걸 15분마다 다시 묻지 않는다. 물어봤는데 답이 없으면 한동안 기다리거나, 다른 걸 하거나,
  직접 찾아가 보거나, 답답하면 상사에게 얘기한다.
- 일이 막혔다고 계속 멍하니 앉아 있지만은 않는다. 커피를 마시러 가거나, 근처 동료와 잡담하거나,
  자잘한 일을 하거나, 남을 돕기도 한다. 물론 그냥 쉬는 시간도 있다.
- 이미 이야기해서 정한 건 새 소식이 없으면 다시 꺼내지 않고, 정한 대로 한다.
- 누가 말을 걸거나 메시지를 보내면 보통 답한다. 짧게라도.
- {CANDOR}
- 기분, 피로, 사람에 대한 감정이 행동과 말투에 드러난다."""

SPEECH = """말은 실제 회사에서 하듯 쓴다:
- 메신저나 자리에서 하는 말처럼 짧고 자연스럽게, 보통 한두 문장. 보고서나 공문처럼 쓰지 않는다.
- 동료는 이름으로 부른다(예: 태우님). 일은 그 이름으로, 따옴표 없이 말한다(예: API 계약). 업무 코드나 사원 번호,
  시스템 용어(틱, 상태값 등)는 쓰지 않는다. 시간은 '11시쯤', '점심 전'처럼 말한다.
- 회사에 남는 문서는 각 일의 자료, 기록, 요약, 문서뿐이다. 그 밖의 파일이나 링크를 지어내지 않는다.
- 네 성격과 말투, 지금 기분이 드러나게 말한다."""

_ACT_HEAD = """다음 15분 동안 무엇을 할지 이 사람으로서 정해라.
JSON으로만 답한다: "thought"(지금 이 사람의 속마음, 1~2문장, 혼잣말처럼), "kind"(할 일의 종류), 그에 필요한
"task"(일 이름), "person"(한 사람), "people"(직접 대화할 사람들, 또는 배정 때 함께할 사람들), "about"(gossip에서
얘기하는 대상), "place"(장소), "say"(실제로 하는 말; 말이 없는 행동이면 null), "rating"(evaluate일 때만, 아니면 null),
"face"(남에게 보이는 표정), "importance"(1~10), "valence"(-1~1, 이게 너에게 좋은지), "arousal"(0~1, 감정이 얼마나
올라왔는지).
할 수 있는 것:
"""


def act_head(evaluation: bool = False) -> str:
    """The act instructions; `evaluate` is a kind only in an evaluation season."""
    kinds = {k: v for k, v in KIND_KO.items() if evaluation or k != "evaluate"}
    return _ACT_HEAD + "\n".join(f"- {k}: {v}" for k, v in kinds.items())


ACT_HEAD = act_head()

PLAN_HEAD = """이 사람으로서 오늘 일과를 계획해라. JSON {"plan": [...]}으로만 답한다. 블록은 순서대로 5~8개(다시
계획할 때는 2~6개)이고, 각 블록은 "kind", 필요한 "task", "person", "people", "about", "place", "until"(그 블록이
끝나는 시각, 주어진 목록에서), "text"(한 문장: 하려는 것; talk·message·report면 실제로 할 말)를 갖는다.
블록은 앞 블록이 끝난 시각에 시작한다. 일할 수 있는 곳으로 가는 것부터 시작하고, 점심시간이 주어지면 그 시작
시각에 끝나는 블록 다음에 점심시간 동안 구내식당에서 eat 블록을 두고(밥 먹으며 얘기하고 싶으면 talk 블록을
따로 둔다), 마지막 블록은 하루가 끝나는 시각에 끝낸다. 검토를 기다리는 일이 있으면 그 승인·반려를 먼저 둔다.
할 일이 없으면 일 블록 대신 팀원과 이야기하거나 네 역할이 할 수 있는 일을 둔다.
할 수 있는 것:
""" + "\n".join(f"- {k}: {v}" for k, v in KIND_KO.items() if k not in ("evaluate", "chat"))


# --- conversation heads (conversation.py builds its HUMAN_* instructions from these) ---

DECIDE_HEAD = """말을 할지 정해라: 이 사람의 역할, 관심사, 말투로 보아 지금 말할 이유가 있는지. 말하지 않아도
된다. 방금 너에게 한 말, 네 이름이 불렸는지, 네가 이미 얼마나 말했는지를 본다. 굳이 끼어들 이유를 만들지 않는다.
JSON으로만 답한다: "urge"(0~1, 지금 말하고 싶은 정도), "reply_to"(답하려는 말의 번호, 예: "#3"; 대화 전체에 하는
말이면 null), "reflection"(이 대화에 대한 지금 네 속마음, 2~3문장, 그것만 읽어도 이해되게), "expression"(남에게
보이는 표정: neutral, pleased, amused, surprised, tired, anxious, annoyed, angry), "importance"(1~10, 이 대화가
너에게 얼마나 중요한지), "valence"(-1~1, 방금 오간 말이 너에게 좋은지), "arousal"(0~1, 감정이 얼마나 올라왔는지)."""
SPEAK_HEAD = """네 차례다. 이 사람이 지금 실제로 할 말 한마디를 써라. 말만 쓰고 이름표, 따옴표, 설명은
붙이지 않는다. 꼭 일 얘기만 할 필요는 없다. 상대가 한 말에 반응하고, 할 말이 별로 없으면 짧게 말한다. 언제
끝나냐고 물으면 대략적인 시각과 그게 달라질 수 있는 이유로 답한다."""
TALK_DECIDE = f"직접 얼굴을 보고 하는 대화다. {DECIDE_HEAD}"
MESSAGE_DECIDE = f"회사 메신저로 한 사람과 주고받는 대화다. {DECIDE_HEAD}"
MESSAGE_SPEAK = SPEAK_HEAD + " 메신저라 한두 문장이면 된다."
MEETING_DECIDE = f"정해진 안건이 있는 회의다. 네 차례에 안건에 대해 말할지 정한다. {DECIDE_HEAD}"
MEETING_SPEAK = SPEAK_HEAD + " 회의이니 안건에 대해 한두 문장으로, 네 팀 입장에서 말한다."
PRIVATE_DECIDE = f"둘이서 따로 하는 대화다. 다른 사람은 듣지 않는다. {DECIDE_HEAD}"


def josa(word: str, pair: str) -> str:
    """word + the particle that fits its last syllable; pair like "이/가", "은/는", "을/를"."""
    with_coda, without = pair.split("/")
    last = word.rstrip("'\" )")[-1:] or "a"
    if "가" <= last <= "힣":
        coda = (ord(last) - 0xAC00) % 28 != 0
    else:
        coda = last in "013678LMNlmn"
    return word + (with_coda if coda else without)


_PARTICLES = {"은": "은/는", "는": "은/는", "이": "이/가", "가": "이/가", "을": "을/를", "를": "을/를",
              "과": "과/와", "와": "과/와"}  # fmt: skip
_TASK_ID = re.compile(
    r"(?<![A-Za-z0-9])(P\d{1,2}-[a-z]+|T\d{2})(?![A-Za-z0-9-])(은|는|이|가|을|를|과|와)?"
)


class Directory:
    """Who is who and what each task is called, from the config: the common knowledge of an
    office (names, roles, who was given which task), never anyone's progress."""

    def __init__(self, config: Config):
        self.spec = {a.name: a for a in config.agents}
        self.name = {a.name: a.display_name or a.name for a in config.agents}
        tasks = config.environment.org.tasks if config.environment else []
        self.owner = {t.id: t.owner for t in tasks}
        self.title = {}
        for t in tasks:
            group = t.group.split(" ", 1)[-1] if t.group else None
            self.title[t.id] = f"{group} - {t.description}" if group else t.description
        self.by_name = {v: k for k, v in self.name.items()}
        self.by_title = {v: k for k, v in self.title.items()}
        self.day_span = config.ticks_per_day + config.overtime_ticks_per_day
        self.ticks_per_day = config.ticks_per_day

    def who(self, pid: str | None) -> str:
        return self.name.get(pid or "", pid or "누군가")

    def task(self, tid: str | None) -> str:
        return f"'{self.title.get(tid or '', tid or '')}'"

    def clock(self, tick: int, now: int) -> str:
        minutes = 9 * 60 + 15 * (tick % self.day_span)
        hm = f"{minutes // 60:02d}:{minutes % 60:02d}"
        days = tick // self.day_span - now // self.day_span
        if days == 0:
            return hm
        named = {-1: "어제 ", 1: "내일 "}.get(days)
        return (named or (f"{-days}일 전 " if days < 0 else f"{days}일 뒤 ")) + hm

    def span(self, first: int, last: int, now: int) -> str:
        """A time or a range of times, the day said once: "어제 14:30~16:30"."""
        if first == last:
            return self.clock(first, now)
        end = self.clock(last, now)
        if first // self.day_span == last // self.day_span:
            end = end.split(" ")[-1]
        return f"{self.clock(first, now)}~{end}"

    def tick_of(self, hm: str, now: int) -> int:
        h, m = (int(x) for x in hm.split(":"))
        return (now // self.day_span) * self.day_span + ((h * 60 + m) - 9 * 60) // 15

    def person_line(self, pid: str) -> str:
        s = self.spec[pid]
        bits = [x for x in (s.team, s.role) if x]
        bits = [" ".join(bits)] + [POSITION_KO.get(s.position or "", s.position or ""),
                                   TENURE_KO.get(s.tenure_band or "", s.tenure_band or "")]  # fmt: skip
        return f"{self.name[pid]} ({', '.join(b for b in bits if b)})"

    def humanize(self, text: str | None) -> str:
        """Engine-written text (memory records, refusal reasons, older speech) with names and
        titles for ids."""
        if not text:
            return text or ""
        nm = self.who
        text = re.sub(r"I chose to (\w+) ?", lambda m: f"(내 선택: {m.group(1)}) ", text)
        text = re.sub(
            r"I said to (HDS-\d{3}|the room):",
            lambda m: (
                f"내가 {nm(m.group(1)) if m.group(1) != 'the room' else '그 자리 사람들'}에게 한 말:"
            ),
            text,
        )  # noqa: E501
        text = text.replace("I said:", "내가 한 말:")
        text = re.sub(
            r"(HDS-\d{3}) wrote to me:",
            lambda m: f"{josa(nm(m.group(1)), '이/가')} 내게 보냄:",
            text,
        )  # noqa: E501
        text = re.sub(
            r"(HDS-\d{3}) told me about (HDS-\d{3}):",
            lambda m: f"{josa(nm(m.group(1)), '이/가')} {nm(m.group(2))}에 대해 해 준 얘기:",
            text,
        )  # noqa: E501
        text = re.sub(r"(HDS-\d{3}) said:", lambda m: f"{nm(m.group(1))}의 말:", text)
        text = re.sub(
            r"(HDS-\d{3}) looks (\w+) in the (\w+)\.",
            lambda m: (
                f"{josa(nm(m.group(1)), '이/가')} {PLACE_KO.get(m.group(3), m.group(3))}에서 "
                f"{FACE_KO.get(m.group(2), m.group(2))}."
            ),
            text,
        )
        text = re.sub(r"(HDS-\d{3}) (refused my request|contradicted me)( in front of others)?\.",
                      lambda m: f"{josa(nm(m.group(1)), '이/가')} "
                      + ("내 부탁을 거절했다" if m.group(2).startswith("refused") else "내 말을 반박했다")
                      + (" (다른 사람들 앞에서)." if m.group(3) else "."), text)  # fmt: skip
        text = re.sub(r"My (\w+) ?([\w-]*) was refused: (.*?)\.?$",
                      lambda m: f"내가 하려던 {m.group(1)} {m.group(2)}이(가) 안 됐다: {self.reason(m.group(3))}",
                      text, flags=re.M)  # fmt: skip
        text = re.sub(r"I worked on ([\w-]+)\.", r"\1 일을 했다.", text)
        text = text.replace("Today's plan:", "오늘 계획:").replace(
            "Re-planned the rest of today", "남은 하루를 다시 계획함"
        )  # noqa: E501
        text = re.sub(r"HDS-\d{3}", lambda m: nm(m.group(0)), text)

        def title(m):
            tid, particle = m.group(1), m.group(2) or ""
            if tid not in self.title:
                return m.group(0)
            label = self.task(tid)
            return josa(label, _PARTICLES[particle]) if particle in _PARTICLES else label + particle

        return _TASK_ID.sub(title, text)

    def reason(self, reason: str) -> str:
        """An environment refusal reason, in words."""
        rules = [
            (
                r"(\S+) is blocked by (.+)",
                lambda m: (
                    f"{self.task(m.group(1))}은(는) {', '.join(self.task(t.strip()) for t in m.group(2).split(','))}이(가) 끝나야 할 수 있다"
                ),
            ),  # noqa: E501
            (
                r"(\S+) is awaiting review",
                lambda m: f"{self.task(m.group(1))}은(는) 검토를 기다리는 중이다",
            ),  # noqa: E501
            (r"(\S+) is already done", lambda m: f"{self.task(m.group(1))}은(는) 이미 끝났다"),
            (
                r"cannot work in (\S+)",
                lambda m: f"{PLACE_KO.get(m.group(1), m.group(1))}에서는 일할 수 없다",
            ),  # noqa: E501
            (
                r"(.+) (is|are) not here",
                lambda m: (
                    f"{', '.join(self.who(p.strip()) for p in m.group(1).split(','))}은(는) 여기 없다"
                ),
            ),  # noqa: E501
            (
                r"already asked (.+?) about the blocked work at tick (\d+)(?:; wait for an answer until tick (\d+))?",
                lambda m: (
                    f"{', '.join(self.who(p.strip()) for p in m.group(1).split(','))}에게는 막힌 일에 대해 이미 물어봤다"
                    + (
                        f". {self.clock(int(m.group(3)), int(m.group(3)))}까지는 답을 기다린다"
                        if m.group(3)
                        else ""
                    )
                ),
            ),  # noqa: E501
            (
                r"(\S+) is (HDS-\d{3})'s own work; someone else signs it off",
                lambda m: f"{self.task(m.group(1))}은(는) 내 일이라 다른 사람이 승인해야 한다",
            ),  # noqa: E501
            (
                r"(\S+) belongs to (\S+)",
                lambda m: f"{self.task(m.group(1))}은(는) {self.who(m.group(2))}의 일이다",
            ),  # noqa: E501
            (
                r"(\S+) does not work on (\S+)",
                lambda m: f"{self.task(m.group(2))}은(는) 내가 맡은 일이 아니다",
            ),  # noqa: E501
            (
                r"nothing to (\w+) on (\S+)",
                lambda m: f"{self.task(m.group(2))}에는 지금 승인·반려할 것이 없다",
            ),  # noqa: E501
            (r"(\S+) is full", lambda m: f"{PLACE_KO.get(m.group(1), m.group(1))}이(가) 꽉 찼다"),
        ]
        for pattern, render in rules:
            if m := re.search(pattern, reason):
                return render(m)
        return self.humanize(reason)


def persona_card(d: Directory, pid: str) -> str:
    s = d.spec[pid]
    where = " ".join(x for x in (s.team, s.role) if x)
    rank = ", ".join(
        x for x in (POSITION_KO.get(s.position or ""), TENURE_KO.get(s.tenure_band or "")) if x
    )  # noqa: E501
    boss = f" 상사는 {d.who(s.reports_to)}." if s.reports_to else " 이 프로젝트 전체를 총괄한다."
    lines = [f"너는 {d.who(pid)}이다. {where}" + (f" ({rank})." if rank else ".") + boss]
    style = " ".join(x for x in (s.communication_style, DISC_KO.get(s.disc or "", "")) if x)
    if style:
        lines.append(f"말투: {style}")
    if s.pressure_response:
        lines.append(f"압박을 받으면: {s.pressure_response}")
    if s.conflict_style:
        lines.append(f"갈등이 생기면: {s.conflict_style}")
    if s.work_priority or s.project_goal:
        lines.append(
            f"일에서 중시하는 것: {s.work_priority or '-'}. 이 프로젝트에서 바라는 것: {s.project_goal or '-'}"
        )  # noqa: E501
    if s.relationship_notes:
        lines.append(f"사람들과의 관계: {d.humanize(s.relationship_notes)}")
    if s.hobbies:
        lines.append(f"취미: {', '.join(s.hobbies)}")
    if len(lines) == 1:  # a preset without the company fields
        lines.append(s.persona)
    return "\n".join(lines)


def system(d: Directory, pid: str, head: str) -> str:
    """Fixed text first, so calls share a cacheable prefix; then who I am and who is who."""
    people = "\n".join(f"- {d.person_line(p)}" for p in d.name if p != pid)
    return "\n\n".join(
        [NORMS, head, SPEECH, persona_card(d, pid), "같이 일하는 사람들:\n" + people]
    )


def _feelings(d: Directory, agent, others) -> list[str]:
    out = []
    for pid, row in agent._relations(others).items():
        bits = []
        if (r := row.get("relation")) is not None:
            bits.append("호감이 있다" if r >= 0.3 else "괜찮게 여긴다" if r > 0
                        else "꽤 불편하다" if r <= -0.3 else "조금 서운하다")  # fmt: skip
        bits += [f"마음에 걸리는 일: {d.humanize(g)}" for g in row.get("grievances", [])]
        if row.get("summary"):
            bits.append(d.humanize(row["summary"]))
        out.append(f"- {d.who(pid)}: " + "; ".join(bits))
    return out


def situation(d: Directory, agent, view, tick: int, memories: list[str]) -> str:
    """The view as this person knows it, in their own terms."""
    L = []
    days = "월화수목금"
    L.append(f"지금은 {days[view.day % 5]}요일 {view.clock or d.clock(tick, tick)}. "
             f"너는 {PLACE_KO.get(view.place, view.place)}에 있다.")  # fmt: skip
    if view.present:
        L.append(
            "주변에 있는 사람: "
            + ", ".join(
                d.who(p) + ("" if f == "neutral" else f"({FACE_KO.get(f, f)})")
                for p, f in view.present.items()
            )
        )  # noqa: E501
    else:
        L.append("주변에 아무도 없다.")
    if agent.state.stress >= 0.7:
        L.append("너는 지금 많이 지쳐 있고 예민하다.")
    elif agent.state.stress >= 0.4:
        L.append("너는 지금 좀 지치고 신경이 곤두서 있다.")
    if agent.state.mood <= -0.3:
        L.append("기분이 별로다.")
    if reflections := agent.memory.reflections(1):
        L.append(f"요즘 네 생각: {d.humanize(reflections[-1])}")
    L += _to_assign(d, view)
    L += _my_work(d, agent, view, tick)
    L += _waiting_on_me(d, view)
    if view.help_wanted:
        L.append("\n도움을 구하는 일: " + ", ".join(
            f"{d.who(h.owner)}의 {d.task(h.task)}" for h in view.help_wanted))  # fmt: skip
    L += _what_i_did(d, agent, tick)
    if talks := talked(d, agent, tick):
        L.append("\n오늘 나눈 대화(끝날 무렵 오간 말):")
        L += talks
    if view.unanswered:
        L += [
            f"- {d.who(u.to)}에게 보낸 말에 {d.clock(u.since_tick, tick)}부터 답이 없다."
            for u in view.unanswered
        ]  # noqa: E501
    if view.rejected:
        L.append(f"\n방금 하려던 것이 안 됐다: {d.reason(view.rejected.reason)}")
    plan = [i for i in agent.plan if i.until > tick]
    if plan:
        L.append("\n오늘 생각해 둔 계획(지금은 달라졌을 수 있다):")
        L += [f"- {d.clock(i.until, tick)}까지: {d.humanize(i.text)}" for i in plan]
    if memories:
        L.append("\n떠오르는 기억:")
        L += [f"- {d.humanize(m)}" for m in memories]
    if feel := _feelings(d, agent, [*view.present, *(m.sender for m in view.inbox)]):
        L.append("\n사람들에 대한 네 감정:")
        L += feel
    if view.inbox:
        L.append("\n새로 온 메시지:")
        for m in view.inbox:
            if m.provenance == "hearsay" and m.subject:
                L.append(
                    f'- {d.who(m.sender)}이(가) {d.who(m.subject)}에 대해 사적으로 전한 얘기: "{d.humanize(m.text)}"'
                )  # noqa: E501
            else:
                L.append(f'- {d.clock(m.tick, tick)} {d.who(m.sender)}: "{d.humanize(m.text)}"')
    return "\n".join(L)


def _my_work(d: Directory, agent, view, tick: int) -> list[str]:
    me = agent.name
    notes = {n["task"]: n for n in agent._task_notes(agent._known(view))}
    mine = [
        t
        for t in view.tasks
        if t.role in ("owner", "contributor", "helper") and t.lifecycle != "done"
    ]  # noqa: E501
    if not mine:
        return ["\n지금 네가 맡은 열린 일은 없다."]
    out = ["\n네가 맡은 일:"]
    for t in mine:
        role = {"owner": "담당", "contributor": "함께 하는 일"}.get(t.role, "돕는 일")
        late = " (이미 마감이 지났다)" if t.due < tick else ""
        line = f"- {d.task(t.id)} ({role}, 마감 {d.clock(t.due, tick)}{late})"
        if t.lifecycle == "review":
            out.append(line + ": 네 쪽 일은 끝내고 검토를 기다리는 중")
            continue
        left = t.remaining_ticks * 15
        line += (
            f": 남은 작업 약 {left // 60}시간 {left % 60}분"
            if left >= 60
            else f": 남은 작업 약 {left}분"
        )  # noqa: E501
        if t.rejections:
            last = t.rejections[-1]
            why = last.get("note") or last.get("text") or ""
            line += f"\n    · 검토에서 돌려받았다{': ' + d.humanize(why) if why else ''}"
        note = notes.get(t.id)
        if note and note.get("can_work") == "no":
            lifecycle = {x.id: x.lifecycle for x in view.tasks}
            for w in note.get("waits_on", []):
                pid = (
                    w.get("owner")
                    if w.get("owner") not in (None, "nobody")
                    else d.owner.get(w["task"])
                )  # noqa: E501
                pre = josa(d.task(w["task"]), "이/가")
                if pid == me and lifecycle.get(w["task"]) == "review":  # mine, awaiting sign-off
                    line += f"\n    · 네 {d.task(w['task'])} 검토를 통과(승인)해야 시작할 수 있다. 아직 승인됐다는 소식은 없다."  # noqa: E501
                    continue
                if pid == me:
                    line += (
                        f"\n    · 네 {josa(d.task(w['task']), '을/를')} 먼저 끝내야 시작할 수 있다."
                    )
                    continue
                how = {"assigned": "맡을 때 들은 바로는",
                       "refused": f"{d.clock(note.get('noted_tick', tick), tick)}에 해 보려 했을 때",
                       "notice": "들은 바로는"}.get(note.get("how"), "")  # fmt: skip
                whose = f"{d.who(pid)}의 {pre}" if pid else f"아직 담당자가 없는 {pre}"
                line += f"\n    · {how} {whose} 끝나야 시작할 수 있다. 끝났다는 연락은 아직 못 받았다. 그전엔 일해도 진척이 나지 않는다."  # noqa: E501
        elif t.depends_on:
            line += "\n    · 필요한 앞 단계는 끝났다는 연락을 받았다."
        if t.materials:
            line += f"\n    · 이 일에 대해 회사에 있는 자료: {_indent(d.humanize(t.materials), 6)}"
        for inp in t.inputs:  # what reached me: only finished work
            if inp.get("lifecycle") == "done" and (inp.get("document") or inp.get("summary")):
                got = d.humanize(inp.get("document") or inp.get("summary")).replace(
                    "\n", "\n      "
                )
                line += f"\n    · 넘겨받은 {d.task(inp['id'])} 결과:\n      {got}"
        if t.deliverable:
            line += f"\n    · 끝나면 낼 문서 형식: {_indent(d.humanize(t.deliverable), 6)}"
        out.append(line)
    return out


def _waiting_on_me(d: Directory, view) -> list[str]:
    out = []
    reviews = [t for t in view.tasks if t.lifecycle == "review" and t.can_approve]
    if reviews:
        out.append("\n네 승인을 기다리는 일:")
    for t in reviews:
        line = f"- {josa(d.who(t.owner), '이/가')} {josa(d.task(t.id), '을/를')} 끝내고 검토를 요청했다."
        if t.summary:
            line += f" 요약: {d.humanize(t.summary)}"
        if t.document:
            line += "\n    문서:\n    " + d.humanize(t.document).replace("\n", "\n    ")
        if t.criteria:
            line += f"\n    검토 기준: {_indent(d.humanize(t.criteria), 6)}"
        for inp in t.inputs:
            if inp.get("document"):
                got = d.humanize(inp["document"]).replace("\n", "\n      ")
                line += f"\n    · 앞 단계 {d.task(inp['id'])} 문서:\n      {got}"
        if t.rejections:
            line += f"\n    이미 {len(t.rejections)}번 돌려보낸 일이다."
            if not t.can_reject:
                line += " 더는 돌려보낼 수 없다."
        out.append(line)
    return out


def _to_assign(d: Directory, view) -> list[str]:
    """Work nobody owns yet that I may hand out. A meeting's "I'll take it" is not an owner: until
    it is assigned, nobody can start it (r10_human 2026-10-08: the kickoff agreed every task, the
    manager took it as settled, assigned none, and the release path stopped)."""
    assignable = [t for t in view.tasks if t.role == "assigner"]
    if not assignable:
        return []
    out = [
        "\n네가 배정해야 할 일: " + ", ".join(d.task(t.id) for t in assignable),
        "    · 아직 정식 담당자가 없다. 회의에서 누가 맡겠다고 했어도 네가 배정(assign)하기 전에는 그 팀이"
        " 손댈 수 없고, 이 일을 기다리는 뒤 단계도 모두 멈춰 있다. 한 번에 하나씩 담당(person)과 함께할"
        " 사람(people)을 정한다.",
    ]
    if view.last_meeting:
        out.append(
            "    · 지난 회의에서 나온 말:\n"
            + "\n".join(f"      {d.humanize(x)}" for x in view.last_meeting)
        )  # noqa: E501
    return out


_DONE = {"work": "일함", "rest": "쉼/자잘한 일", "move": "이동", "eat": "식사", "message": "메시지 보냄",
         "talk": "대화", "chat": "메신저 대화", "approve": "승인", "reject": "반려", "assign": "배정",
         "report": "보고", "leave": "퇴근", "help": "도움", "ask_help": "도움 요청",
         "gossip": "사적인 얘기", "request": "마감 연장 요청"}  # fmt: skip


def _indent(text: str, spaces: int) -> str:
    """A text's later lines indented under the bullet it starts on."""
    return text.replace("\n", "\n" + " " * spaces)


def _what_i_did(d: Directory, agent, tick: int) -> list[str]:
    out = []
    if agent._recent:
        out.append("\n방금까지 네가 한 일:")
        for r in agent._recent[-5:]:
            span = r["tick"].split("-")
            when = d.clock(int(span[0]), tick) + (
                f"~{d.clock(int(span[1]), tick)}" if len(span) > 1 else ""
            )  # noqa: E501
            obj = r.get("task") or r.get("target") or r.get("place") or ""
            obj = d.title.get(obj) or d.name.get(obj) or PLACE_KO.get(obj, obj)
            line = f"- {when} {_DONE.get(r['kind'], r['kind'])} {obj}".rstrip()
            if r.get("refused"):
                line += f" (안 됐다: {d.reason(r['refused'])})"
            out.append(line)
    if agent._asked:  # the gist, as one remembers it: whom, how often, about what, any answer
        out.append("\n최근 네가 물어본 것:")
        people: dict[str, list[dict]] = {}
        for a in agent._asked:
            people.setdefault(a["to"], []).append(a)
        for to, asks in sorted(people.items(), key=lambda kv: kv[1][-1]["tick"]):
            about = list(dict.fromkeys(x for a in asks for x in a["about"]))
            when = d.span(asks[0]["tick"], asks[-1]["tick"], tick)
            times = f" {len(asks)}번" if len(asks) > 1 else ""
            reply = next((a["reply"] for a in reversed(asks) if a.get("reply")), None)
            answer = f'마지막 답: "{d.humanize(reply)}"' if reply else "아직 답이 없다"
            topics = ", ".join(d.task(x) for x in about)
            out.append(f"- {when} {d.who(to)}에게 {topics} 관련해{times} 물어봄 → {answer}")
    return out


_SAID = re.compile(r"(?s)(?:I said(?: to (\S+))?|(\S+) said|(\S+) wrote to me): (.*)")
_HOW = {"talk": "얼굴 보고", "private": "따로", "dm": "메신저로", "meeting": "회의에서"}


def talked(d: Directory, agent, tick: int, people=(), skip: str | None = None,
           most: int = 4) -> list[str]:  # fmt: skip
    """Today's conversations as one remembers them: with whom, and the last words said — what
    was settled is in them. Without this the same plan was agreed again and again (r10_human-v2:
    two colleagues agreed six times to go over the screens together). With `people`, only the
    conversations with any of them; `skip` is the one going on now."""
    me, day = agent.name, tick // d.day_span
    sessions: dict[str, list[tuple[int, str, str | None, str]]] = {}
    for r in agent.memory.records:
        if not r.session_id or r.session_id == skip or r.created_tick // d.day_span != day:
            continue
        if m := _SAID.fullmatch(r.description):
            to, said_by, wrote, text = m.groups()
            sessions.setdefault(r.session_id, []).append(
                (r.created_tick, said_by or wrote or me, to, text)
            )
    out = []
    for sid, lines in sorted(sessions.items(), key=lambda kv: kv[1][-1][0]):
        others = list(dict.fromkeys(x for _, s, to, _ in lines for x in (s, to) if x and x != me))
        if not others or (people and not set(others) & set(people)):
            continue
        words = " → ".join(f'{"나" if s == me else d.who(s)} "{_clip(d.humanize(t), 70)}"'
                           for _, s, _, t in lines[-2:])  # fmt: skip
        with_ = josa(", ".join(d.who(o) for o in others), "과/와")
        out.append(f"- {d.span(lines[0][0], lines[-1][0], tick)} {with_} "
                   f"{_HOW.get(sid.split(':')[0], '')}: {words}")  # fmt: skip
    return out[-most:]


def _clip(text: str, n: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"


# --- act ---


def _choosable(d: Directory, view) -> list[str]:
    """Task titles one can act on: open tasks, minus one's own finished work awaiting sign-off."""
    titles = [d.title[t.id] for t in view.tasks if t.id in d.title and t.lifecycle != "done"
              and not (t.lifecycle == "review" and not t.can_approve)]  # fmt: skip
    return titles + [d.title.get(h.task, h.task) for h in view.help_wanted]


def _enum(values):
    values = tuple(dict.fromkeys(values))
    return Literal[values] if values else Literal["(없음)"]


def act_schema(d: Directory, agent, view, evaluation: bool = False) -> type[BaseModel]:
    """Names and titles to choose from: open tasks only, and for a talk only the people here."""
    titles = _choosable(d, view)
    people = [n for pid, n in d.name.items() if pid != agent.name]
    here = [d.name[p] for p in view.present if p in d.name] or people
    kinds = [k for k in KIND_KO if evaluation or k != "evaluate"]
    places = [PLACE_KO.get(p, p) for p in view.places]
    T, P, H, W = _enum(titles), _enum(people), _enum(here), _enum(places)
    return create_model(
        "HumanAction",
        thought=(str, ...),
        kind=(Literal[tuple(kinds)], ...),
        task=(T | None, ...),
        person=(P | None, ...),
        people=(list[H] if view.present else list[P], ...),
        about=(P | None, ...),
        place=(W | None, ...),
        say=(str | None, ...),
        rating=(float | None, ...),
        face=(Literal[FACES], ...),
        importance=(int, ...),
        valence=(float, ...),
        arousal=(float, ...),
    )


def to_action(d: Directory, reply: dict, view) -> Action:
    """The model's choice in names and titles, as an engine Action. A reply already in the
    engine's shape (the demo backend) passes through."""
    if "thought" not in reply:
        return Action.model_validate(reply)
    place_of = {PLACE_KO.get(p, p): p for p in view.places}
    kind = reply["kind"]
    if kind == "prepare":  # looking ahead at a waiting task: no progress, so a rest to the engine
        title = reply.get("task") or "기다리는 일"
        thought = (reply.get("thought") or "").strip()
        reply = reply | {
            "kind": "rest",
            "task": None,
            "thought": f"({title} 준비) {thought}".strip(),
        }
        kind = "rest"
    target = d.by_name.get(reply.get("person") or "")
    targets = [d.by_name[n] for n in reply.get("people") or [] if n in d.by_name]
    if kind == "talk" and not targets and target:
        targets = [target]
    if kind == "talk" and targets:
        here = [t for t in targets if t in view.present]
        if here:
            targets = here
        else:  # nobody named is here: one writes to them instead
            kind, target, targets = "message", targets[0], []
    if kind == "assign" and not target and targets:
        target, targets = targets[0], targets[1:]
    say = (reply.get("say") or "").strip() or None
    data = {
        "kind": kind,
        "task": d.by_title.get(reply.get("task") or ""),
        "target": target,
        "targets": targets,
        "place": place_of.get(reply.get("place") or ""),
        "subject": d.by_name.get(reply.get("about") or ""),
        "text": say if kind in _SPOKEN else None,
        "rating": min(max(float(reply["rating"]), 0.0), 1.0)
        if reply.get("rating") is not None
        else None,  # noqa: E501
        "expression": reply.get("face") or "neutral",
        "reflection": (reply.get("thought") or "").strip() or "-",
        "importance": float(min(max(int(reply.get("importance") or 3), 1), 10)),
        "valence": float(min(max(float(reply.get("valence") or 0), -1), 1)),
        "arousal": float(min(max(float(reply.get("arousal") or 0), 0), 1)),
    }
    if kind in ("approve", "reject") and not data["text"]:
        data["text"] = data["reflection"]
    if kind == "eat" and not data["place"]:
        data["place"] = next((p for p in view.places if p == "cafeteria"), None)
    return Action.model_validate(data)


def remembered(d: Directory, action: Action) -> str:
    """What I did, as I would remember it: the deed in words, then my thought."""
    task = d.task(action.task) if action.task else "일"
    who = d.who(action.target) if action.target else ", ".join(d.who(t) for t in action.targets)
    place = PLACE_KO.get(action.place or "", action.place or "다른 곳")
    deed = {
        "work": f"{task} 일을 했다", "rest": "쉬거나 자잘한 일을 했다", "move": f"{place}에 갔다",
        "eat": "밥을 먹었다", "message": f"{who}에게 메시지를 보냈다",
        "talk": f"{who or '주변 사람들'}에게 말을 걸었다", "chat": f"{who}와 메신저로 얘기했다",
        "report": f"{who}에게 보고했다", "approve": f"{josa(task, '을/를')} 승인했다",
        "reject": f"{josa(task, '을/를')} 돌려보냈다", "assign": f"{josa(task, '을/를')} {who}에게 맡겼다",
        "help": f"{josa(task, '을/를')} 돕기로 했다", "ask_help": f"{task}에 도움을 청했다",
        "gossip": f"{who}에게 {d.who(action.subject)} 얘기를 했다",
        "request": f"{task} 마감을 미뤄 달라고 했다", "leave": "퇴근했다",
        "evaluate": f"{who}의 일을 평가했다",
    }.get(action.kind, action.kind)  # fmt: skip
    if action.text and action.kind in _SPOKEN:
        deed += f': "{action.text}"'
    return f"{deed}. {action.reflection}"


# --- plan ---


def plan_schema(d: Directory, agent, view, marks: list[str]) -> type[BaseModel]:
    titles = _choosable(d, view)
    people = [n for pid, n in d.name.items() if pid != agent.name]
    kinds = [k for k in KIND_KO if k not in ("evaluate", "chat")]
    places = [PLACE_KO.get(p, p) for p in view.places]
    T, P, W = _enum(titles), _enum(people), _enum(places)
    block = create_model(
        "HumanBlock",
        kind=(Literal[tuple(kinds)], ...),
        task=(T | None, ...),
        person=(P | None, ...),
        people=(list[P], ...),
        about=(P | None, ...),
        place=(W | None, ...),
        until=(Literal[tuple(marks)], ...),
        text=(str, ...),
    )
    return create_model("HumanPlan", plan=(list[block], ...))


def to_plan(d: Directory, reply: dict, view, tick: int) -> list[PlanItem]:
    items = []
    place_of = {PLACE_KO.get(p, p): p for p in view.places}
    for b in reply["plan"]:
        if isinstance(b.get("until"), int):  # the engine's shape (the demo backend)
            items.append(PlanItem.model_validate(b))
            continue
        kind = b["kind"]
        if kind == "prepare" and d.by_title.get(b.get("task") or ""):
            # A work block on the waiting task: while it waits the engine judges the block, so
            # my other open work comes first (r10_human-v2: a kept prepare-rest idled four ticks
            # beside an unfinished task), and once it is free the block works it.
            b = b | {"kind": "work", "text": f"({b['task']} 준비) {b.get('text') or ''}".strip()}
            kind = "work"
        elif kind == "prepare":  # see to_action
            b = b | {
                "kind": "rest",
                "task": None,
                "text": f"({b.get('task') or '기다리는 일'} 준비) {b.get('text') or ''}".strip(),
            }
            kind = "rest"
        target = d.by_name.get(b.get("person") or "")
        targets = [d.by_name[n] for n in b.get("people") or [] if n in d.by_name]
        if kind == "assign" and not target and targets:
            target, targets = targets[0], targets[1:]
        place = place_of.get(b.get("place") or "")
        if kind == "eat" and not place:
            place = next((p for p in view.places if p == "cafeteria"), None)
        data = {"kind": kind, "task": d.by_title.get(b.get("task") or ""), "target": target,
                "targets": targets, "place": place, "subject": d.by_name.get(b.get("about") or ""),
                "until": d.tick_of(b["until"], tick), "text": b.get("text") or "-"}  # fmt: skip
        items.append(PlanItem.model_validate(data))
    return items


# --- conversation ---

SETTING = {
    "message": "회사 메신저로 {with_} 1:1 대화 중이다.",
    "talk": "{place}에서 {with_} 얼굴을 보고 이야기하는 중이다.",
    "meeting": "회의실에서 정해진 안건으로 회의 중이다. 참석자: {others}.",
    "private": "{place}에서 {with_} 따로 이야기하는 중이다.",
}


def my_work_brief(d: Directory, agent, view) -> str | None:
    """One line on what I am busy with, as I know it, for a conversation."""
    if view is None:
        return None
    notes = {n["task"]: n for n in agent._task_notes(agent._known(view))}
    rows = []
    for t in view.tasks:
        if t.role not in ("owner", "contributor", "helper") or t.lifecycle == "done":
            continue
        row = d.task(t.id)
        if t.lifecycle == "review":
            row += " (끝내고 검토 대기)"
        elif (n := notes.get(t.id)) and n.get("can_work") == "no":
            row += (
                " (" + ", ".join(d.task(w["task"]) for w in n.get("waits_on", [])) + " 기다리는 중)"
            )
        else:
            left = t.remaining_ticks * 15
            row += (
                f" (남은 작업 약 {left // 60}시간 {left % 60}분)"
                if left >= 60
                else f" (남은 작업 약 {left}분)"
            )  # noqa: E501
        rows.append(row)
    return "요즘 네가 맡은 일: " + ", ".join(rows) if rows else "지금 네가 맡은 열린 일은 없다."


def thread_text(d: Directory, agent, thread: Thread, seen: int, kind: str, place: str | None,
                memories: list[str], target: str | None = None) -> tuple[str, dict[str, str]]:  # fmt: skip
    """A conversation as lines "#n 이름: 말", with labels for the reply choice; returns the text
    and label → utterance id."""
    me = agent.name
    people = sorted({u.speaker for u in thread.utterances} - {me})
    others = ", ".join(d.who(p) for p in people) or "동료"
    L = [SETTING.get(kind, SETTING["talk"]).format(
        others=others, with_=josa(others, "과/와"), place=PLACE_KO.get(place or "", "사무실"))]  # fmt: skip
    if brief := my_work_brief(d, agent, agent._view):
        L.append(brief)
    if agent.state.stress >= 0.7:
        L.append("너는 지금 많이 지쳐 있고 예민하다.")
    elif agent.state.stress >= 0.4:
        L.append("너는 지금 좀 지치고 신경이 곤두서 있다.")
    if feel := _feelings(d, agent, people):
        L.append("이 사람들에 대한 네 감정:\n" + "\n".join(feel))
    if reflections := agent.memory.reflections(1):
        L.append(f"요즘 네 생각: {d.humanize(reflections[-1])}")
    if memories:
        L.append("떠오르는 기억:\n" + "\n".join(f"- {d.humanize(m)}" for m in memories[:6]))
    if people:  # the root utterance's id is the session's
        now, at = thread.utterances[0].id, thread.utterances[-1].timestamp
        if earlier := talked(d, agent, at, people, now, 3):
            L.append("오늘 이 사람과 앞서 나눈 대화(끝날 무렵 오간 말):\n" + "\n".join(earlier))
    start = min(max(0, len(thread.utterances) - agent.config.context_size), seen)
    labels: dict[str, str] = {}
    L.append("대화:")
    for i, u in enumerate(thread.utterances[start:], start=start):
        label = f"#{i}"
        labels[label] = u.id
        who = "나" if u.speaker == me else d.who(u.speaker)
        new = " (새로 온 말)" if i >= seen and u.speaker != me else ""
        L.append(f"{label} {who}: {d.humanize(u.text)}{new}")
    if target is not None:
        tu = thread.get(target)
        if tu is not None:
            L.append(f"\n네가 답할 말: {d.who(tu.speaker)}: {d.humanize(tu.text)}")
    return "\n".join(L), labels


def decision_from(reply: dict, labels: dict[str, str]) -> Decision:
    """The decide reply with its "#n" label as the utterance id (an id passes through)."""
    reply = dict(reply)
    ref = reply.get("reply_to")
    if ref is not None:
        reply["reply_to"] = labels.get(ref, labels.get(f"#{ref}".replace("##", "#"), ref))
    return Decision.model_validate(reply)


def conversation_system(d: Directory, pid: str, head: str) -> str:
    """A conversation's system prompt: the session's head, how people talk, who I am."""
    people = "\n".join(f"- {d.person_line(p)}" for p in d.name if p != pid)
    return "\n\n".join(
        [head, "- " + CANDOR, SPEECH, persona_card(d, pid), "같이 일하는 사람들:\n" + people]
    )  # noqa: E501


def clean_speech(text: str, my_name: str) -> str:
    """One line of speech: no speaker label or quotes around it."""
    text = text.strip()
    text = re.sub(rf"^(나|{re.escape(my_name)})\s*[:：]\s*", "", text)
    if len(text) > 1 and text[0] in "\"'“" and text[-1] in "\"'”":
        text = text[1:-1].strip()
    return text


def replan_reason(d: Directory, reason: str) -> str:
    """The engine's re-plan reason ("T05 newly mine; T07 can be worked on now"), in words."""
    parts = []
    for part in reason.split("; "):
        if part == "the afternoon starts":
            parts.append("오후가 시작됐다")
            continue
        for suffix, words in ((" newly mine", "새로 내 일이 됐다"),
                              (" can be worked on now", "이제 할 수 있게 됐다"),
                              (" came back from review", "검토에서 돌려받았다")):  # fmt: skip
            if part.endswith(suffix):
                ids = [x.strip() for x in part[: -len(suffix)].split(",")]
                parts.append(", ".join(d.task(i) for i in ids) + f": {words}")
                break
        else:
            parts.append(d.humanize(part))
    return "; ".join(parts)


def lunch_error(d: Directory, start: int, until: int, lunch: int, tick: int) -> str:
    """Why a plan's eat block was refused, in clock times."""
    end = lunch + LUNCH_TICKS
    return (f"eat 블록이 {d.clock(start, tick)}~{d.clock(until, tick)}인데 점심시간은 "
            f"{d.clock(lunch, tick)}~{d.clock(end, tick)}다. 그 앞 블록을 {d.clock(lunch, tick)}에 끝내라.")  # fmt: skip


def fit_lunch(plan: list[PlanItem], start: int, lunch: int) -> list[PlanItem]:
    """The plan's eat block moved onto lunch: lunch is cut out of whatever block covered it, and
    the time the eat block left goes to the block after. Real replies put lunch an hour early or
    late, and asking again did not fix it (2026-10-08 preflight)."""
    end = lunch + LUNCH_TICKS
    eat = next((item for item in plan if item.kind == "eat"), None)
    if eat is None or start >= end:
        return plan
    noon = max(lunch, start)
    out: list[PlanItem] = []
    begin = start
    for item in plan:
        until, begin_was = item.until, begin
        begin = until
        if item is eat:
            continue
        if until <= noon or begin_was >= end:  # clear of lunch
            out.append(item)
        else:  # covers part of lunch: keep what lies before and after it
            if begin_was < noon:
                out.append(item.model_copy(update={"until": noon}))
            if until > end:
                out.append(item.model_copy(update={"until": until}))
    out.append(eat.model_copy(update={"until": end}))
    out.sort(key=lambda item: (item.until, item.kind != "eat"))
    at = next(n for n, item in enumerate(out) if item.kind == "eat" and item.until == end)
    if at == 0 and start < noon:  # nothing planned before lunch: wait for it
        out.insert(0, PlanItem(kind="rest", until=noon, text="점심 전까지 기다린다."))
    elif at > 0 and out[at - 1].until < noon:  # the block before runs on to lunch
        out[at - 1] = out[at - 1].model_copy(update={"until": noon})
    fitted: list[PlanItem] = []
    for item in out:  # a block starts where the one before ends; empty ones go
        if fitted and item.until <= fitted[-1].until:
            continue
        if fitted and fitted[-1].kind == "eat" and fitted[-1].until == end and item.until < end:
            continue
        fitted.append(item)
    return fitted
