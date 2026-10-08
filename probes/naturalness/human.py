# ruff: noqa: E501, E731, E741, UP045  (research harness: long Korean prompt text)
"""A human-knowable, narrative rendering of an agent's situation, and the act/speak calls on it.

Engine ids stay inside: the model sees names and task titles, chooses from enums of them, and the
choice is mapped back to ids. Only what the person has seen, been told or done is rendered.
"""

import json
import re
from functools import cache
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, create_model

from conflict_sim.agent.agent import _SPOKEN
from conflict_sim.models import Action

ROOT = Path(__file__).resolve().parents[2]
QUOTE_PAST = False  # quote my own past messages verbatim, or give their gist
OPEN_ONLY = False  # v2: only open tasks in the task enum, only people here for a talk
LIFE_ON = False  # today's private texture in the situation
PLACE_KO = {
    "lobby": "로비",
    "office": "사무실 내 자리",
    "meeting_room": "회의실",
    "focus_room": "집중 업무실",
    "pantry": "탕비실",
    "cafeteria": "구내식당",
}
FACE_KO = {
    "neutral": "평소 같음",
    "pleased": "기분 좋아 보임",
    "amused": "웃고 있음",
    "surprised": "놀란 표정",
    "tired": "피곤해 보임",
    "anxious": "불안해 보임",
    "annoyed": "짜증 나 보임",
    "angry": "화나 보임",
}
TENURE_KO = {
    "0_to_2_years": "입사 2년 이하",
    "3_to_6_years": "경력 3~6년",
    "7_to_10_years": "경력 7~10년",
    "10_plus_years": "경력 10년 이상",
}
POSITION_KO = {
    "team_manager": "팀 총괄 매니저",
    "functional_lead": "팀 리드",
    "senior_member": "선임",
    "member": "팀원",
}
# DISC as a communication tendency only (the persona policy forbids reading competence,
# aggression, honesty or conflict-proneness into it).
DISC_KO = {
    "D": "결론부터 짧고 단정적으로 말하고, 빨리 정하고 넘어가길 원한다. 돌려 말하지 않는다.",
    "i": "친근하고 말이 많은 편이다. 분위기를 띄우고 잡담도 잘하며, 감정을 숨기지 않고 말에 드러낸다.",
    "S": "부드럽고 공손하게 말한다. 상대 사정을 먼저 묻고 맞춰 주는 편이라, 직접 재촉하거나 거절하는 말은 망설인다.",
    "C": "정확하게 말하려 한다. 근거와 숫자를 챙기고, 단정하기보다 조심스럽게 표현하며 문장이 반듯하다.",
}
KIND_KO = {
    "work": "내 일을 한다 (필요한 게 다 갖춰진 일만 진척이 난다; 자리나 집중 업무실에서)",
    "rest": "쉬거나 자리에서 자잘한 일을 한다 (일 진척 없음; 탕비실·구내식당·로비에서 쉬면 피로가 풀린다)",
    "move": "다른 곳으로 간다",
    "eat": "밥을 먹는다 (구내식당)",
    "talk": "지금 같은 곳에 있는 사람과 직접 대화를 시작한다",
    "message": "메신저로 누군가에게 메시지를 보낸다 (상대는 다음 15분 안에 읽는다)",
    "chat": "오늘 메시지를 주고받은 사람과 메신저로 실시간 대화를 이어간다",
    "gossip": "누군가에 대한 얘기를 다른 사람에게 사적으로 전한다",
    "report": "상사에게 내 상황을 보고한다",
    "request": "내 일의 마감을 미뤄 달라고 요청한다",
    "approve": "검토를 기다리는 일을 승인한다 (권한 있는 경우)",
    "reject": "검토를 기다리는 일을 돌려보낸다 (권한 있는 경우; 무엇이 부족한지 말한다)",
    "assign": "담당자 없는 일을 누군가에게 맡긴다 (매니저만)",
    "help": "도움을 구하는 남의 일에 합류한다",
    "ask_help": "내 일에 도움을 구한다",
    "leave": "오늘은 퇴근한다",
}

# Today's private texture per person: nothing to do with work, seeded per day in a real design.
LIFE = {
    "HDS-001": "어젯밤 달리기를 못 해서 몸이 좀 무겁다. 오후에 임원 보고가 잡혀 있어 신경이 쓰인다.",
    "HDS-002": "점심에 친구 결혼식 축의금 보낼 걸 잊지 말아야 한다.",
    "HDS-003": "오늘 저녁 러닝 크루 모임이 있어서 칼퇴하고 싶다.",
    "HDS-005": "어제 늦게까지 코드 리뷰를 해서 눈이 뻑뻑하다.",
    "HDS-006": "어젯밤 늦게까지 게임을 해서 좀 졸리다. 커피가 땡긴다.",
    "HDS-008": "주말 공연 티켓팅에 성공해서 기분이 좋다.",
    "HDS-011": "집 이사 날짜가 다음 주라 틈틈이 이삿짐센터 연락을 해야 한다.",
    "HDS-013": "주말에 찍은 사진을 정리하고 싶은데 시간이 없다.",
    "HDS-014": "아이가 감기 기운이 있어 어린이집에서 연락 올까 봐 신경이 쓰인다.",
    "HDS-015": "점심에 동료들이랑 배드민턴 동호회 얘기를 하기로 했다.",
}

NORMS = """이것은 실제 회사 사람의 하루를 흉내 내는 시뮬레이션이다. 모범 직원이나 일 처리 프로그램처럼 굴지 말고,
이 사람이 지금 이 상황에서 실제로 할 법한 행동을 골라라. 늘 최선의 선택일 필요는 없다.
- 너는 네가 직접 보거나 듣거나 받은 것만 안다. 다른 사람 일이 얼마나 됐는지는 그 사람이 말해 주거나 끝났다는
  연락이 오기 전엔 모른다. 모르는 건 짐작하거나 물어봐야 알 수 있다.
- 사람은 같은 걸 15분마다 다시 묻지 않는다. 물어봤는데 답이 없으면 한동안 기다리거나, 다른 걸 하거나,
  직접 찾아가 보거나, 답답하면 상사에게 얘기한다.
- 일이 막혔다고 계속 멍하니 앉아 있지만은 않는다. 커피를 마시러 가거나, 근처 동료와 잡담하거나, 자잘한 일을
  하거나, 남을 돕기도 한다. 물론 그냥 쉬는 시간도 있다.
- 누가 말을 걸거나 메시지를 보내면 보통 답한다. 짧게라도.
- 기분, 피로, 사람에 대한 감정이 행동과 말투에 드러난다."""
CANDOR = """- 남의 말에 무조건 맞장구치거나 부탁을 다 들어주지 않는다. 동의하지 않으면 성격대로 말하고, 무리한 부탁은
  거절하거나 조건을 단다. 다만 예의는 지킨다."""

SPEECH = """말은 실제 회사에서 하듯 쓴다:
- 메신저나 자리에서 하는 말처럼 짧고 자연스럽게, 보통 한두 문장. 보고서나 공문처럼 쓰지 않는다.
- 동료는 이름으로 부른다(예: 태우님). 일은 그 이름으로 말한다(예: API 계약). 업무 코드나 사원 번호,
  시스템 용어(틱, 상태값 등)는 쓰지 않는다. 시간은 '11시쯤', '점심 전'처럼 말한다.
- 네 성격과 말투, 지금 기분이 드러나게 말한다."""


TASK_RX = re.compile(r"(?<![A-Za-z0-9])(?:P\d{1,2}-[a-z]+|T\d{2})(?![A-Za-z0-9-])")


def josa(word: str, pair: str) -> str:
    """word + the particle that fits its last syllable; pair like "이/가", "은/는", "을/를"."""
    a, b = pair.split("/")
    last = word.rstrip("'\" )")[-1:] or "a"
    if "가" <= last <= "힣":
        has = (ord(last) - 0xAC00) % 28 != 0
    else:
        has = last in "013678LMNlmn"
    return word + (a if has else b)


class World:
    """Names and titles for one loop, and the id ⇄ human-label maps."""

    def __init__(self, loop, scenario_preset: str):
        self.loop = loop
        self.name = {a.name: a.spec.display_name or a.name for a in loop.agents}
        self.spec = {a.name: a.spec for a in loop.agents}
        self.title = {}
        for t in loop.env.org.tasks.values():
            group = t.spec.group.split(" ", 1)[1] if t.spec.group else None
            self.title[t.id] = f"{group} - {t.spec.description}" if group else t.spec.description
        self.persona = {p["id"]: p for p in _personas(scenario_preset)}
        names = {v: k for k, v in self.name.items()}
        titles = {v: k for k, v in self.title.items()}
        self.by_name, self.by_title = names, titles
        self.departments = loop.cfg.environment.org.departments if loop.cfg.environment else []

    def humanize(self, text: str | None) -> str | None:
        """Ids in a text from the old engine (memories, a colleague's words) as names and titles."""
        if not text:
            return text
        nm = lambda pid: self.name.get(pid, pid)  # noqa: E731
        text = re.sub(r"I chose to (\w+) ?", lambda m: f"(내 선택: {m.group(1)}) ", text)
        text = re.sub(
            r"I said to (HDS-\d{3}):", lambda m: f"내가 {nm(m.group(1))}에게 한 말:", text
        )
        text = re.sub(r"I said:", "내가 한 말:", text)
        text = re.sub(
            r"(HDS-\d{3}) wrote to me:",
            lambda m: f"{josa(nm(m.group(1)), '이/가')} 내게 보냄:",
            text,
        )
        text = re.sub(r"(HDS-\d{3}) said:", lambda m: f"{nm(m.group(1))}의 말:", text)
        text = re.sub(
            r"(HDS-\d{3}) looks (\w+) in the (\w+)\.",
            lambda m: (
                f"{josa(self.name.get(m.group(1), m.group(1)), '이/가')} {PLACE_KO.get(m.group(3), m.group(3))}에서 "
                f"{FACE_KO.get(m.group(2), m.group(2))}."
            ),
            text,
        )
        text = re.sub(
            r"My (\w+) ?([\w-]*) was refused: (.*)",
            lambda m: f"내 {m.group(1)} {m.group(2)} 시도가 안 됨: {m.group(3)}",
            text,
        )
        text = re.sub(r"I worked on ([\w-]+)\.", r"\1 작업을 했다.", text)
        text = re.sub(r"HDS-\d{3}", lambda m: self.name.get(m.group(0), m.group(0)), text)
        pairs = {
            "은": "은/는",
            "는": "은/는",
            "이": "이/가",
            "가": "이/가",
            "을": "을/를",
            "를": "을/를",
            "과": "과/와",
            "와": "과/와",
        }

        def title(m):
            tid, particle = m.group(1), m.group(2) or ""
            if tid not in self.title:
                return m.group(0)
            label = f"'{self.title[tid]}'"
            return josa(label, pairs[particle]) if particle in pairs else label + particle

        text = re.sub(
            r"(?<![A-Za-z0-9])(P\d{1,2}-[a-z]+|T\d{2})(?![A-Za-z0-9-])(은|는|이|가|을|를|과|와)?",
            title,
            text,
        )
        text = re.sub(
            r"('[^']+'|\S+) is blocked by ('[^']+'|\S+)",
            lambda m: f"{josa(m.group(1), '은/는')} {josa(m.group(2), '이/가')} 끝나야 할 수 있다",
            text,
        )
        return text

    def clock(self, tick: int, now: int) -> str:
        span = self.loop.day_span
        hm = 9 * 60 + 15 * (tick % span)
        when = f"{hm // 60:02d}:{hm % 60:02d}"
        days = tick // span - now // span
        return when if days == 0 else ({-1: "어제 ", 1: "내일 "}.get(days, f"{days}일 뒤 ") + when)

    def person_line(self, pid: str) -> str:
        s = self.spec[pid]
        return (
            f"{self.name[pid]} ({self.dept_name(s.department)} {s.role}, "
            f"{POSITION_KO.get(s.position, s.position)}, {TENURE_KO.get(s.tenure_band, s.tenure_band)})"
        )

    def dept_name(self, dept: str | None) -> str:
        return _dept_names().get(dept, dept or "")


@cache
def _personas(preset: str) -> list[dict]:
    company = yaml.safe_load((ROOT / f"conf/company/{preset}.yaml").read_text())
    personas = next(
        d["/personas"] for d in company["defaults"] if isinstance(d, dict) and "/personas" in d
    )
    return yaml.safe_load((ROOT / f"conf/personas/{personas}.yaml").read_text())["agents"]


@cache
def _dept_names() -> dict:
    return yaml.safe_load(
        (ROOT / "conf/environment/org/large_korean_enterprise_ko.yaml").read_text()
    )["department_names"]


# Observable habits per DISC style: how the tendency shows in words and choices, never in
# competence, honesty or how much conflict someone starts.
HABITS = {
    "D": (
        "말버릇: 인사나 완충어 없이 본론부터, 짧은 문장. 질문보다 결정과 요청('~합시다', '~해 주세요'). "
        "행동: 기다리기보다 먼저 움직인다. 막히면 빨리 결정권자에게 가져간다. 잡담은 짧게 끊는다."
    ),
    "i": (
        "말버릇: 친근하게 이름을 부르고 감탄·웃음(ㅎㅎ, '오!')을 섞는다. 일 얘기 중에도 사적인 얘기가 끼어든다. "
        "행동: 혼자 있기보다 사람을 찾아가 얘기로 푼다. 분위기를 살피고 띄운다. 세부 확인은 가끔 놓친다."
    ),
    "S": (
        "말버릇: '혹시', '괜찮으시면', '죄송한데' 같은 완충어. 요청은 질문으로 돌려 말하고, 동의부터 한다. "
        "행동: 재촉을 미루고 좀 더 기다린다. 부탁을 잘 거절하지 못한다. 갈등이 보이면 한발 물러선다."
    ),
    "C": (
        "말버릇: 정중한 '~습니다'체, 숫자·조건·근거를 붙이고, '~로 이해했습니다'처럼 확인한다. 단정을 피한다. "
        "행동: 움직이기 전에 자료와 기준부터 본다. 모호한 요청엔 범위를 되묻는다. 감정은 잘 드러내지 않는다."
    ),
}
REGISTER = """말의 높낮이: 직급과 연차에 따라 다르게 한다. 상사나 선배에게는 존댓말을 깍듯이, 동료에게는 편한 존댓말(~요),
네가 리드나 매니저라면 팀원에게는 더 짧고 편하게 말한다. 연차가 낮으면 조심스럽게, 높으면 단정적으로 말하는 편이다."""


def persona_card(w: World, pid: str, rich: bool = True, voice: bool = False) -> str:
    s, p = w.spec[pid], w.persona.get(pid, {})
    boss = w.name.get(s.reports_to) if s.reports_to else None
    head = (
        f"너는 {w.name[pid]}이다. 한빛디지털시스템 {w.dept_name(s.department)} {s.role}"
        f" ({POSITION_KO.get(s.position, s.position)}, {TENURE_KO.get(s.tenure_band, s.tenure_band)})."
        + (f" 상사는 {boss}." if boss else " 이 프로젝트 전체의 총괄 매니저다.")
    )
    if not rich:
        return head + f" {s.persona}"
    lines = [
        head,
        f"말투: {p.get('communication_style', '')} {DISC_KO.get(s.disc, '')}",
        f"압박을 받으면: {p.get('pressure_response', '')}",
        f"갈등이 생기면: {p.get('conflict_engagement_style', '')}",
        f"일에서 중시하는 것: {p.get('personal_work_priority', '')}. 이 프로젝트에서 바라는 것: {p.get('project_goal', '')}",
        f"사람들과의 관계: {w.humanize(p.get('initial_relationship_notes', ''))}",
        f"취미: {', '.join(p.get('hobbies', []))}",
    ]
    if voice:
        lines += [HABITS.get(s.disc, ""), REGISTER]
    return "\n".join(lines)


def directory(w: World, me: str) -> str:
    rows = [f"- {w.person_line(pid)}" for pid in w.name if pid != me]
    return "같이 일하는 사람들:\n" + "\n".join(rows)


def _feel(w: World, agent, others) -> list[str]:
    out = []
    for pid, row in agent._relations(others).items():
        bits = []
        r = row.get("relation")
        if r is not None:
            bits.append(
                "호감이 있다"
                if r >= 0.3
                else "괜찮게 여긴다"
                if r > 0
                else "꽤 불편하다"
                if r <= -0.3
                else "조금 서운하다"
            )
        bits += [f"마음에 걸리는 일: {w.humanize(g)}" for g in row.get("grievances", [])]
        if row.get("summary"):
            bits.append(w.humanize(row["summary"]))
        out.append(f"- {w.name.get(pid, pid)}: " + "; ".join(bits))
    return out


def situation_text(w: World, agent, view, tick: int, memories: list[str]) -> str:
    me = agent.name
    L = []
    day_names = ["월", "화", "수", "목", "금"]
    L.append(
        f"지금은 {day_names[view.day % 5]}요일 {view.clock}. 너는 {PLACE_KO.get(view.place, view.place)}에 있다."
    )
    if view.present:
        L.append(
            "주변에 있는 사람: "
            + ", ".join(
                f"{w.name.get(p, p)}" + ("" if f == "neutral" else f"({FACE_KO[f]})")
                for p, f in view.present.items()
            )
        )
    if LIFE_ON and me in LIFE:
        L.append(f"오늘 네 개인적인 사정: {LIFE[me]}")
    stress = agent.state.stress
    if stress >= 0.7:
        L.append("너는 지금 많이 지쳐 있고 예민하다.")
    elif stress >= 0.4:
        L.append("너는 지금 좀 지치고 신경이 곤두서 있다.")
    if agent.state.mood <= -0.3:
        L.append("기분이 별로다.")
    # my own work
    known = agent._known(view)
    notes = {n["task"]: n for n in agent._task_notes(known)}
    asked = agent._asked
    mine = [
        t
        for t in view.tasks
        if t.role in ("owner", "contributor", "helper") and t.lifecycle != "done"
    ]
    if mine:
        L.append("\n네가 맡은 일:")
    for t in mine:
        role = (
            "담당"
            if t.role == "owner"
            else "함께 하는 일"
            if t.role == "contributor"
            else "돕는 일"
        )
        due = w.clock(t.due, tick)
        late = " (이미 마감이 지났다)" if t.due < tick else ""
        line = f"- '{w.title[t.id]}' ({role}, 마감 {due}{late})"
        if t.lifecycle == "review":
            line += ": 네 쪽 일은 끝내고 검토를 기다리는 중"
            L.append(line)
            continue
        left = t.remaining_ticks * 15
        line += (
            f": 남은 작업 약 {left // 60}시간 {left % 60}분"
            if left >= 60
            else f": 남은 작업 약 {left}분"
        )
        if t.progress > 0:
            line += f" (지금까지 {round(t.progress * 100)}% 했다)"
        n = notes.get(t.id)
        if n and n.get("can_work") == "no":
            for wt in n.get("waits_on", []):
                # who owns a task is common knowledge (the kickoff, the org chart); its progress is not
                pid = wt.get("owner") or getattr(
                    w.loop.env.org.tasks.get(wt["task"]), "owner", None
                )
                owner = "네" if pid == me else w.name.get(pid or "", "아직 담당자가 없는")
                how = {
                    "assigned": "맡을 때 들은 바로는",
                    "refused": f"{w.clock(n.get('noted_tick', tick), tick)}에 해 보려 했을 때",
                    "notice": "들은 바로는",
                    "worked": "",
                }.get(n.get("how"), "")
                pre = josa(f"'{w.title.get(wt['task'], wt['task'])}'", "이/가")
                if owner == "네":  # my own earlier task, still waiting for its sign-off
                    line += f"\n    · 네 {pre} 검토를 통과(승인)해야 시작할 수 있다. 아직 승인됐다는 소식은 없다."
                else:
                    line += f"\n    · {how} {owner}의 {pre} 끝나야 시작할 수 있다. 끝났다는 연락은 아직 못 받았다."
        elif t.depends_on:
            line += "\n    · 필요한 앞 단계는 끝났다는 연락을 받았다."
        if t.materials:
            line += f"\n    · 이 일에 대해 회사에 있는 자료: {t.materials}"
        for inp in t.inputs:
            if inp.get("lifecycle") == "done" and (inp.get("document") or inp.get("summary")):
                line += f"\n    · 받은 앞 단계 결과 '{w.title.get(inp['id'], inp['id'])}': {w.humanize(inp.get('document') or inp.get('summary'))}"
        if t.deliverable:
            line += f"\n    · 끝나면 낼 문서 형식: {t.deliverable}"
        L.append(line)
    reviews = [t for t in view.tasks if t.lifecycle == "review" and t.can_approve]
    if reviews:
        L.append("\n네 승인을 기다리는 일:")
        for t in reviews:
            who = w.name.get(t.owner or "", "누군가")
            line = f"- {josa(who, '이/가')} {josa(chr(39) + w.title[t.id] + chr(39), '을/를')} 끝내고 검토를 요청했다."
            if t.summary:
                line += f" 요약: {w.humanize(t.summary)}"
            if t.document:
                line += "\n    문서:\n    " + w.humanize(t.document).replace("\n", "\n    ")
            if t.criteria:
                line += f"\n    검토 기준: {t.criteria}"
            if t.rejections:
                line += f"\n    이미 {len(t.rejections)}번 돌려보낸 일이다." + (
                    " 더는 돌려보낼 수 없다." if len(t.rejections) >= 2 else ""
                )
            L.append(line)
    assignable = [t for t in view.tasks if t.role == "assigner"]
    if assignable:
        L.append(
            "\n아직 담당자가 없어 네가 맡길 수 있는 일: "
            + ", ".join(f"'{w.title[t.id]}'" for t in assignable)
        )
        if view.last_meeting:
            L.append(
                "지난 회의에서 나온 말:\n"
                + "\n".join(f"  {w.humanize(x)}" for x in view.last_meeting)
            )
    if view.help_wanted:
        L.append(
            "\n도움을 구하는 일: "
            + ", ".join(
                f"{w.name.get(h.owner, h.owner)}의 '{w.title.get(h.task, h.task)}'"
                for h in view.help_wanted
            )
        )
    # what happened to me
    if agent._recent:
        L.append("\n방금까지 네가 한 일:")
        for r in agent._recent[-5:]:
            t0 = r["tick"].split("-")
            when = w.clock(int(t0[0]), tick) + (
                f"~{w.clock(int(t0[1]), tick)}" if len(t0) > 1 else ""
            )
            what = {
                "work": "일함",
                "rest": "쉼/자잘한 일",
                "move": "이동",
                "eat": "식사",
                "message": "메시지 보냄",
                "talk": "대화",
                "approve": "승인",
                "reject": "반려",
                "assign": "배정",
                "report": "보고",
                "leave": "퇴근",
                "plan": "계획 세움",
            }.get(r["kind"], r["kind"])
            obj = r.get("task") or r.get("target") or r.get("place") or ""
            obj = w.title.get(obj) or w.name.get(obj) or PLACE_KO.get(obj, obj)
            s = f"- {when} {what} {obj}".rstrip()
            if r.get("said") and QUOTE_PAST:
                s += f': "{w.humanize(r["said"])}"'
            if r.get("refused"):
                s += f" (안 됐다: {w.humanize(r['refused'])})"
            L.append(s)
    if asked:
        L.append("\n최근 네가 물어본 것:")
        groups = []
        for a in asked[-8:]:
            if groups and groups[-1]["said"] == a["said"] and groups[-1]["tick"] == a["tick"]:
                groups[-1]["to"].append(a["to"])
                groups[-1]["replies"].append(a.get("reply"))
            else:
                groups.append(
                    {
                        "said": a["said"],
                        "tick": a["tick"],
                        "to": [a["to"]],
                        "replies": [a.get("reply")],
                    }
                )
        for g in groups:
            to = ", ".join(w.name.get(x, x) for x in g["to"])
            got = [r for r in g["replies"] if r]
            reply = f'답: "{w.humanize(got[0])}"' if got else "아직 답이 없다"
            if QUOTE_PAST:
                said = f': "{w.humanize(g["said"])}"'
            else:  # the gist, as one remembers it, not one's exact words
                about = sorted(
                    {x for a in asked if a["tick"] == g["tick"] for x in a.get("about", [])}
                )
                said = (
                    (" " + ", ".join(f"'{w.title.get(x, x)}'" for x in about) + " 관련해 물어봄")
                    if about
                    else " 물어봄"
                )
            L.append(f"- {w.clock(g['tick'], tick)} {to}에게{said} → {reply}")
    if view.unanswered:
        for u in view.unanswered:
            L.append(
                f"- {w.name.get(u.to, u.to)}에게 보낸 말에 {w.clock(u.since_tick, tick)}부터 답이 없다."
            )
    if view.rejected:
        r = view.rejected
        L.append(f"\n방금 하려던 것이 안 됐다: {w.humanize(r.reason)}")
    plan = [i for i in agent.plan if i.until > tick]
    if plan:
        L.append("\n오늘 아침에 생각해 둔 계획(지금은 달라졌을 수 있다):")
        L += [f"- {w.clock(i.until, tick)}까지: {w.humanize(i.text)}" for i in plan]
    if memories:
        L.append("\n떠오르는 기억:")
        L += [f"- {w.humanize(m)}" for m in memories]
    feel = _feel(w, agent, [*view.present, *(m.sender for m in view.inbox)])
    if feel:
        L.append("\n사람들에 대한 네 감정:")
        L += feel
    if view.inbox:
        L.append("\n새로 온 메시지:")
        for m in view.inbox:
            L.append(
                f'- {w.clock(m.tick, tick)} {w.name.get(m.sender, m.sender)}: "{w.humanize(m.text)}"'
            )
    return "\n".join(L)


def act_schema(w: World, agent, view):
    titles = sorted(
        {w.title[t.id] for t in view.tasks if t.lifecycle != "done" or not OPEN_ONLY}
        | {w.title.get(h.task, h.task) for h in view.help_wanted}
    )
    people = sorted(n for pid, n in w.name.items() if pid != agent.name)
    here = sorted(w.name[p] for p in view.present if p in w.name) or people
    places = sorted(PLACE_KO[p] for p in view.places)
    kinds = [k for k in KIND_KO]
    T = Literal[tuple(titles)] if titles else str
    fields = {
        "thought": (str, ...),
        "kind": (Literal[tuple(kinds)], ...),
        "task": (Optional[T], ...),
        "person": (Optional[Literal[tuple(people)]], ...),
        "people": (list[Literal[tuple(here if OPEN_ONLY else people)]], ...),
        "place": (Optional[Literal[tuple(places)]], ...),
        "say": (Optional[str], ...),
        "face": (
            Literal[
                "neutral", "pleased", "amused", "surprised", "tired", "anxious", "annoyed", "angry"
            ],
            ...,
        ),
        "importance": (int, ...),
        "valence": (float, ...),
        "arousal": (float, ...),
    }
    return create_model("HumanAction", **fields)


ACT_HEAD = """다음 15분 동안 무엇을 할지 이 사람으로서 정해라.
JSON으로만 답한다: "thought"(지금 이 사람의 속마음, 1~2문장, 혼잣말처럼), "kind"(할 일의 종류), 그에 필요한
"task"(일 이름), "person"(한 사람), "people"(직접 대화할 사람들), "place"(장소), "say"(talk·message·report·gossip일 때
실제로 하는 말; 아니면 null), "face"(남에게 보이는 표정), "importance"(1~10), "valence"(-1~1, 이게 너에게 좋은지),
"arousal"(0~1, 얼마나 감정이 올라왔는지).
할 수 있는 것:
""" + "\n".join(f"- {k}: {v}" for k, v in KIND_KO.items())


def act_system(w: World, pid: str, *, rich=True, norms=True, voice=False, candor=False) -> str:
    parts = [ACT_HEAD, SPEECH]
    if norms:
        parts.insert(0, NORMS + ("\n" + CANDOR if candor else ""))
    parts += [persona_card(w, pid, rich, voice), directory(w, pid)]
    return "\n\n".join(parts)


def to_action(w: World, reply: BaseModel) -> Action:
    place_id = {v: k for k, v in PLACE_KO.items()}
    task = w.by_title.get(reply.task) if reply.task else None
    target = w.by_name.get(reply.person) if reply.person else None
    targets = [w.by_name[n] for n in reply.people]
    kind = reply.kind
    if kind == "talk" and not targets and target:
        targets = [target]
    data = dict(
        kind=kind,
        task=task,
        target=target,
        targets=targets,
        place=place_id.get(reply.place) if reply.place else None,
        text=reply.say
        if kind in _SPOKEN | {"approve", "reject", "ask_help"} and reply.say
        else None,
        expression=reply.face,
        reflection=reply.thought or "-",
        importance=min(max(int(reply.importance), 1), 10),
        valence=min(max(reply.valence, -1), 1),
        arousal=min(max(reply.arousal, 0), 1),
    )
    if kind in ("approve", "reject") and not data["text"]:
        data["text"] = reply.thought
    try:
        return Action.model_validate(data)
    except ValueError:
        data.update(kind="rest", task=None, target=None, targets=[], text=None)
        return Action.model_validate(data)


def act_human(
    w: World,
    agent,
    view,
    tick: int,
    llm,
    *,
    rich=True,
    norms=True,
    k_mem=True,
    voice=False,
    candor=False,
):
    query = " ".join(
        [f"{view.phase} at {view.place}."] + [f"{m.sender} wrote: {m.text}" for m in view.inbox]
    )
    memories = agent._recall(query, tick) if k_mem else []
    system = act_system(w, agent.name, rich=rich, norms=norms, voice=voice, candor=candor)
    prompt = situation_text(w, agent, view, tick, memories)
    schema = act_schema(w, agent, view)
    raw = llm.complete(
        system=system,
        prompt=prompt,
        model=agent.config.model_decide,
        temperature=agent.config.temperature,
        json_mode=True,
        schema=schema,
    )
    reply = schema.model_validate_json(raw)
    return to_action(w, reply), {"system": system, "prompt": prompt, "raw": json.loads(raw)}
