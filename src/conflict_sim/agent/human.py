# ruff: noqa: E501  (prompt text: wide characters count double)
"""The human prompt style (`prompt_style: human`): what one person knows, told the way they would
tell it to themselves.

The engine runs on ids. This layer turns an agent's view into narrative with people's names and
task titles, lets the model choose from those names and titles, and maps the choice back to ids.
Only what the person has seen, been told or done is rendered: no one else's task state or
progress, no draft still in review. Probes against the engine's JSON prompts are in
`docs/agent-context-research.md` (2026-10-08).

The words are the company's language (`language` in the scenario): human_ko.py for Korean,
human_en.py for any other, which also asks for speech in that language. This module is the logic
only; both word modules have the same names.

A demo backend cannot read narrative, so every call also sets `ENGINE_PAYLOAD` to the engine's
payload and accepts a reply in the engine's own shape (ids, ticks).
"""

import re
from typing import Literal

from pydantic import BaseModel, create_model

from ..models import LUNCH_TICKS, Action, Config, Decision, PlanItem, Thread
from . import human_en, human_ko

_SPOKEN = {"talk", "message", "gossip", "report", "evaluate", "ask_help", "approve", "reject"}
FACES = ("neutral", "pleased", "amused", "surprised", "tired", "anxious", "annoyed", "angry")


def words(language: str):
    """The word module for a company's language."""
    return human_ko if language == "Korean" else human_en


def act_head(d: "Directory", evaluation: bool = False) -> str:
    """The act instructions; `evaluate` is a kind only in an evaluation season."""
    kinds = {k: v for k, v in d.w.KIND.items() if evaluation or k != "evaluate"}
    return d.w.ACT_HEAD + "\n".join(f"- {k}: {v}" for k, v in kinds.items())


def plan_head(d: "Directory") -> str:
    kinds = {k: v for k, v in d.w.KIND.items() if k not in ("evaluate", "chat")}
    return d.w.PLAN_HEAD + "\n".join(f"- {k}: {v}" for k, v in kinds.items())


def josa(word: str, pair: str) -> str:
    """word + the particle that fits its last syllable; pair like "이/가", "은/는", "을/를"."""
    with_coda, without = pair.split("/")
    last = word.rstrip("'\" )")[-1:] or "a"
    if "가" <= last <= "힣":
        coda = (ord(last) - 0xAC00) % 28 != 0
    else:
        coda = last in "013678LMNlmn"
    return word + (with_coda if coda else without)


_MARK = re.compile(r"⟨([^/⟩]+)/([^⟩]+)⟩")


def fill(template: str, **fields) -> str:
    """A word module's template filled in; a Korean particle mark such as ⟨이/가⟩ becomes the
    form that fits the word before it."""
    text = template.format(**fields)
    return _MARK.sub(lambda m: josa(m.string[: m.start()], f"{m[1]}/{m[2]}")[m.start() :], text)


_PARTICLES = {"은": "은/는", "는": "은/는", "이": "이/가", "가": "이/가", "을": "을/를", "를": "을/를",
              "과": "과/와", "와": "과/와"}  # fmt: skip
_TASK_ID = re.compile(
    r"(?<![A-Za-z0-9])(P\d{1,2}-[a-z]+|T\d{2})(?![A-Za-z0-9-])(은|는|이|가|을|를|과|와)?"
)


class Directory:
    """Who is who and what each task is called, from the config: the common knowledge of an
    office (names, roles, who was given which task), never anyone's progress. It carries the
    company's words (`w`)."""

    def __init__(self, config: Config):
        self.language = config.language
        self.w = words(config.language)
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
        return self.name.get(pid or "", pid or self.w.SOMEONE)

    def task(self, tid: str | None) -> str:
        return f"'{self.title.get(tid or '', tid or '')}'"

    def place(self, place: str | None, default: str = "") -> str:
        return self.w.PLACE.get(place or "", place or default)

    def clock(self, tick: int, now: int) -> str:
        minutes = 9 * 60 + 15 * (tick % self.day_span)
        hm = f"{minutes // 60:02d}:{minutes % 60:02d}"
        days = tick // self.day_span - now // self.day_span
        if days == 0:
            return hm
        named = {-1: self.w.YESTERDAY, 1: self.w.TOMORROW}.get(days)
        later = fill(self.w.DAYS_AGO, n=-days) if days < 0 else fill(self.w.DAYS_LATER, n=days)
        return (named or later) + hm

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
        s, w = self.spec[pid], self.w
        bits = [x for x in (s.team, s.role) if x]
        bits = [" ".join(bits)] + [w.POSITION.get(s.position or "", s.position or ""),
                                   w.TENURE.get(s.tenure_band or "", s.tenure_band or "")]  # fmt: skip
        return f"{self.name[pid]} ({', '.join(b for b in bits if b)})"

    def humanize(self, text: str | None) -> str:
        """Engine-written text (memory records, refusal reasons, older speech) with names and
        titles for ids."""
        if not text:
            return text or ""
        nm, w = self.who, self.w
        text = re.sub(r"I chose to (\w+) ?", lambda m: fill(w.H_CHOSE, kind=m[1]), text)
        text = re.sub(
            r"I said to (HDS-\d{3}|the room):",
            lambda m: fill(w.H_SAID_TO, who=nm(m[1]) if m[1] != "the room" else w.THE_ROOM),
            text,
        )
        text = text.replace("I said:", w.H_SAID)
        text = re.sub(r"(HDS-\d{3}) wrote to me:", lambda m: fill(w.H_WROTE, who=nm(m[1])), text)
        text = re.sub(r"(HDS-\d{3}) told me about (HDS-\d{3}):",
                      lambda m: fill(w.H_TOLD, who=nm(m[1]), about=nm(m[2])), text)  # fmt: skip
        text = re.sub(r"(HDS-\d{3}) said:", lambda m: fill(w.H_SAYS, who=nm(m[1])), text)
        text = re.sub(
            r"(HDS-\d{3}) looks (\w+) in the (\w+)\.",
            lambda m: fill(
                w.H_LOOKS, who=nm(m[1]), place=self.place(m[3]), face=w.FACE.get(m[2], m[2])
            ),  # fmt: skip
            text,
        )
        text = re.sub(r"(HDS-\d{3}) (refused my request|contradicted me)( in front of others)?\.",
                      lambda m: fill(w.H_REFUSED if m[2].startswith("refused") else w.H_CONTRADICTED,
                                     who=nm(m[1]), front=w.H_FRONT if m[3] else ""), text)  # fmt: skip
        text = re.sub(r"My (\w+) ?([\w-]*) was refused: (.*?)\.?$",
                      lambda m: fill(w.H_MY_REFUSED, kind=m[1], task=m[2], reason=self.reason(m[3])),
                      text, flags=re.M)  # fmt: skip
        text = re.sub(r"I worked on ([\w-]+)\.", lambda m: fill(w.H_WORKED, task=m[1]), text)
        text = text.replace("Today's plan:", w.H_PLAN).replace(
            "Re-planned the rest of today", w.H_REPLANNED
        )
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
        w = self.w

        def tasks(ids: str) -> str:
            return ", ".join(self.task(t.strip()) for t in ids.split(","))

        def people(ids: str) -> str:
            return ", ".join(self.who(p.strip()) for p in ids.split(","))

        rules = [
            (r"(\S+) is blocked by (.+)",
             lambda m: fill(w.R_BLOCKED, task=self.task(m[1]), pre=tasks(m[2]))),
            (r"(\S+) is awaiting review", lambda m: fill(w.R_REVIEW, task=self.task(m[1]))),
            (r"(\S+) is already done", lambda m: fill(w.R_DONE, task=self.task(m[1]))),
            (r"cannot work in (\S+)", lambda m: fill(w.R_PLACE, place=self.place(m[1]))),
            (r"(.+) (is|are) not here", lambda m: fill(w.R_NOT_HERE, who=people(m[1]))),
            (r"already asked (.+?) about the blocked work at tick (\d+)(?:; wait for an answer until tick (\d+))?",
             lambda m: fill(w.R_ASKED, who=people(m[1]))
             + (fill(w.R_WAIT, clock=self.clock(int(m[3]), int(m[3]))) if m[3] else "")),
            (r"(\S+) is (HDS-\d{3})'s own work; someone else signs it off",
             lambda m: fill(w.R_OWN, task=self.task(m[1]))),
            (r"(\S+) belongs to (\S+)",
             lambda m: fill(w.R_BELONGS, task=self.task(m[1]), who=self.who(m[2]))),
            (r"(\S+) does not work on (\S+)", lambda m: fill(w.R_NOT_MINE, task=self.task(m[2]))),
            (r"nothing to (\w+) on (\S+)", lambda m: fill(w.R_NOTHING, task=self.task(m[2]))),
            (r"name each person once", lambda m: w.R_ONCE),
            (r"(\S+) is full", lambda m: fill(w.R_FULL, place=self.place(m[1]))),
        ]  # fmt: skip
        for pattern, render in rules:
            if m := re.search(pattern, reason):
                return render(m)
        return self.humanize(reason)


def persona_card(d: Directory, pid: str) -> str:
    s, w = d.spec[pid], d.w
    where = " ".join(x for x in (s.team, s.role) if x)
    rank = ", ".join(
        x for x in (w.POSITION.get(s.position or ""), w.TENURE.get(s.tenure_band or "")) if x
    )
    boss = fill(w.P_BOSS, boss=d.who(s.reports_to)) if s.reports_to else w.P_TOP
    lines = [fill(w.P_ME, name=d.who(pid), where=where)
             + (fill(w.P_RANK, rank=rank) if rank else ".") + boss]  # fmt: skip
    style = " ".join(x for x in (s.communication_style, w.DISC.get(s.disc or "", "")) if x)
    if style:
        lines.append(fill(w.P_STYLE, x=style))
    if s.pressure_response:
        lines.append(fill(w.P_PRESSURE, x=s.pressure_response))
    if s.conflict_style:
        lines.append(fill(w.P_CONFLICT, x=s.conflict_style))
    if s.work_priority or s.project_goal:
        lines.append(
            fill(w.P_PRIORITY, priority=s.work_priority or "-", goal=s.project_goal or "-")
        )
    if s.relationship_notes:
        lines.append(fill(w.P_RELATIONS, x=d.humanize(s.relationship_notes)))
    if s.hobbies:
        lines.append(fill(w.P_HOBBIES, x=", ".join(s.hobbies)))
    if len(lines) == 1:  # a preset without the company fields
        lines.append(s.persona)
    return "\n".join(lines)


def _speech(d: Directory) -> str:
    """How people talk; in a language with no word module of its own, the language is named."""
    if d.language in ("Korean", "English"):
        return d.w.SPEECH
    return d.w.SPEECH + f"\n- Say and write everything in {d.language}."


def system(d: Directory, pid: str, head: str) -> str:
    """Fixed text first, so calls share a cacheable prefix; then who I am and who is who."""
    people = "\n".join(f"- {d.person_line(p)}" for p in d.name if p != pid)
    return "\n\n".join([d.w.NORMS, head, _speech(d), persona_card(d, pid), d.w.COWORKERS + people])


def _feelings(d: Directory, agent, others) -> list[str]:
    w, out = d.w, []
    for pid, row in agent._relations(others).items():
        bits = []
        if (r := row.get("relation")) is not None:
            bits.append(w.F_LIKE if r >= 0.3 else w.F_OK if r > 0
                        else w.F_UNEASY if r <= -0.3 else w.F_HURT)  # fmt: skip
        bits += [fill(w.F_GRIEVANCE, x=d.humanize(g)) for g in row.get("grievances", [])]
        if row.get("summary"):
            bits.append(d.humanize(row["summary"]))
        out.append(f"- {d.who(pid)}: " + "; ".join(bits))
    return out


def _strain(d: Directory, agent) -> list[str]:
    if agent.state.stress >= 0.7:
        return [d.w.S_VERY_TIRED]
    if agent.state.stress >= 0.4:
        return [d.w.S_TIRED]
    return []


def situation(d: Directory, agent, view, tick: int, memories: list[str]) -> str:
    """The view as this person knows it, in their own terms."""
    w, L = d.w, []
    L.append(fill(w.S_NOW, day=w.DAYS[view.day % 5], clock=view.clock or d.clock(tick, tick),
                  place=d.place(view.place)))  # fmt: skip
    if view.present:
        L.append(w.S_AROUND + ", ".join(
            d.who(p) + ("" if f == "neutral" else f"({w.FACE.get(f, f)})")
            for p, f in view.present.items()))  # fmt: skip
    else:
        L.append(w.S_ALONE)
    L += _strain(d, agent)
    if agent.state.mood <= -0.3:
        L.append(w.S_MOOD)
    if reflections := agent.memory.reflections(1):
        L.append(fill(w.S_THOUGHT, x=d.humanize(reflections[-1])))
    L += _to_assign(d, view)
    # Before my own work: the decisions others wait on (r10_human-v3: two reviews listed after a
    # long own-work section waited from 13:15 to the end of the day; probed 0 approvals in 5).
    L += _waiting_on_me(d, view)
    L += _my_work(d, agent, view, tick)
    if view.help_wanted:
        L.append(w.S_HELP + ", ".join(
            fill(w.S_HELP_ITEM, who=d.who(h.owner), task=d.task(h.task)) for h in view.help_wanted))  # fmt: skip
    L += _what_i_did(d, agent, tick)
    if talks := talked(d, agent, tick):
        L.append(w.S_TALKED)
        L += talks
    L += [fill(w.S_UNANSWERED, who=d.who(u.to), since=d.clock(u.since_tick, tick))
          for u in view.unanswered]  # fmt: skip
    if view.rejected:
        L.append(fill(w.S_REJECTED, reason=d.reason(view.rejected.reason)))
    plan = [i for i in agent.plan if i.until > tick]
    if plan:
        L.append(w.S_PLAN)
        L += [fill(w.S_PLAN_ITEM, until=d.clock(i.until, tick), text=d.humanize(i.text))
              for i in plan]  # fmt: skip
    if memories:
        L.append(w.S_MEMORIES)
        L += [f"- {d.humanize(m)}" for m in memories]
    if feel := _feelings(d, agent, [*view.present, *(m.sender for m in view.inbox)]):
        L.append(w.S_FEELINGS)
        L += feel
    if view.inbox:
        L.append(w.S_INBOX)
        for m in view.inbox:
            if m.provenance == "hearsay" and m.subject:
                L.append(fill(w.S_HEARSAY, who=d.who(m.sender), about=d.who(m.subject),
                              text=d.humanize(m.text)))  # fmt: skip
            else:
                L.append(f'- {d.clock(m.tick, tick)} {d.who(m.sender)}: "{d.humanize(m.text)}"')
    return "\n".join(L)


def _left(d: Directory, ticks: int) -> str:
    """Work still to do, in hours and minutes."""
    left = ticks * 15
    return fill(d.w.LEFT_H, h=left // 60, m=left % 60) if left >= 60 else fill(d.w.LEFT_M, m=left)


def _my_work(d: Directory, agent, view, tick: int) -> list[str]:
    me, w = agent.name, d.w
    notes = {n["task"]: n for n in agent._task_notes(agent._known(view))}
    mine = [
        t
        for t in view.tasks
        if t.role in ("owner", "contributor", "helper") and t.lifecycle != "done"
    ]
    if not mine:
        return ["\n" + w.W_NONE]
    out = [w.W_HEAD]
    for t in mine:
        role = w.W_ROLE.get(t.role, w.W_ROLE["helper"])
        late = w.W_LATE if t.due < tick else ""
        line = fill(w.W_LINE, task=d.task(t.id), role=role, due=d.clock(t.due, tick), late=late)
        if t.lifecycle == "review":
            out.append(line + w.W_IN_REVIEW)
            continue
        line += ": " + _left(d, t.remaining_ticks)
        if t.rejections:
            last = t.rejections[-1]
            why = last.get("note") or last.get("text") or ""
            line += w.W_RETURNED + (": " + d.humanize(why) if why else "")
        note = notes.get(t.id)
        if note and note.get("can_work") == "no":
            lifecycle = {x.id: x.lifecycle for x in view.tasks}
            for wait in note.get("waits_on", []):
                pid = (
                    wait.get("owner")
                    if wait.get("owner") not in (None, "nobody")
                    else d.owner.get(wait["task"])
                )
                task = d.task(wait["task"])
                if pid == me and lifecycle.get(wait["task"]) == "review":  # mine, awaiting sign-off
                    line += fill(w.W_MY_REVIEW, task=task)
                    continue
                if pid == me:
                    line += fill(w.W_MINE_FIRST, task=task)
                    continue
                how = w.W_HOW.get(note.get("how"), "")
                how = fill(how, clock=d.clock(note.get("noted_tick", tick), tick)) if how else ""
                whose = (
                    fill(w.W_WHOSE, who=d.who(pid), task=task)
                    if pid
                    else fill(w.W_UNOWNED, task=task)
                )
                line += fill(w.W_WAITS, how=how, whose=whose)
        elif t.depends_on:
            line += w.W_PREREQ_DONE
        if t.materials:
            line += fill(w.W_MATERIALS, x=_indent(d.humanize(t.materials), 6))
        for inp in t.inputs:  # what reached me: only finished work
            if inp.get("lifecycle") == "done" and (inp.get("document") or inp.get("summary")):
                got = d.humanize(inp.get("document") or inp.get("summary")).replace(
                    "\n", "\n      "
                )
                line += fill(w.W_INPUT, task=d.task(inp["id"]), x=got)
        if t.deliverable:
            line += fill(w.W_DELIVERABLE, x=_indent(d.humanize(t.deliverable), 6))
        out.append(line)
    return out


def _waiting_on_me(d: Directory, view) -> list[str]:
    w, out = d.w, []
    reviews = [t for t in view.tasks if t.lifecycle == "review" and t.can_approve]
    if reviews:
        out.append(w.A_HEAD)
    for t in reviews:
        line = fill(w.A_LINE, who=d.who(t.owner), task=d.task(t.id))
        if t.summary:
            line += fill(w.A_SUMMARY, x=d.humanize(t.summary))
        if t.document:
            line += w.A_DOC + d.humanize(t.document).replace("\n", "\n    ")
        if t.criteria:
            line += fill(w.A_CRITERIA, x=_indent(d.humanize(t.criteria), 6))
        for inp in t.inputs:
            if inp.get("document"):
                got = d.humanize(inp["document"]).replace("\n", "\n      ")
                line += fill(w.A_INPUT, task=d.task(inp["id"]), x=got)
        if t.rejections:
            line += fill(w.A_RETURNED, n=len(t.rejections))
            if not t.can_reject:
                line += w.A_NO_MORE
        out.append(line)
    return out


def _to_assign(d: Directory, view) -> list[str]:
    """Work nobody owns yet that I may hand out. A meeting's "I'll take it" is not an owner: until
    it is assigned, nobody can start it (r10_human 2026-10-08: the kickoff agreed every task, the
    manager took it as settled, assigned none, and the release path stopped)."""
    assignable = [t for t in view.tasks if t.role == "assigner"]
    if not assignable:
        return []
    out = [d.w.G_HEAD + ", ".join(d.task(t.id) for t in assignable), d.w.G_RULE]
    if view.last_meeting:
        out.append(d.w.G_MEETING + "\n".join(f"      {d.humanize(x)}" for x in view.last_meeting))
    return out


def _indent(text: str, spaces: int) -> str:
    """A text's later lines indented under the bullet it starts on."""
    return text.replace("\n", "\n" + " " * spaces)


def _what_i_did(d: Directory, agent, tick: int) -> list[str]:
    w, out = d.w, []
    if agent._recent:
        out.append(w.D_HEAD)
        for r in agent._recent[-5:]:
            span = r["tick"].split("-")
            when = d.clock(int(span[0]), tick) + (
                f"~{d.clock(int(span[1]), tick)}" if len(span) > 1 else ""
            )
            obj = r.get("task") or r.get("target") or r.get("place") or ""
            obj = d.title.get(obj) or d.name.get(obj) or d.place(obj)
            line = f"- {when} {w.DONE.get(r['kind'], r['kind'])} {obj}".rstrip()
            if r.get("refused"):
                line += fill(w.D_REFUSED, x=d.reason(r["refused"]))
            out.append(line)
    if agent._asked:  # the gist, as one remembers it: whom, how often, about what, any answer
        out.append(w.Q_HEAD)
        people: dict[str, list[dict]] = {}
        for a in agent._asked:
            people.setdefault(a["to"], []).append(a)
        for to, asks in sorted(people.items(), key=lambda kv: kv[1][-1]["tick"]):
            about = list(dict.fromkeys(x for a in asks for x in a["about"]))
            reply = next((a["reply"] for a in reversed(asks) if a.get("reply")), None)
            out.append(fill(
                w.Q_LINE,
                when=d.span(asks[0]["tick"], asks[-1]["tick"], tick),
                who=d.who(to),
                topics=", ".join(d.task(x) for x in about),
                times=fill(w.Q_TIMES, n=len(asks)) if len(asks) > 1 else "",
                answer=fill(w.Q_LAST, x=d.humanize(reply)) if reply else w.Q_NONE,
            ))  # fmt: skip
    return out


_SAID = re.compile(r"(?s)(?:I said(?: to (\S+))?|(\S+) said|(\S+) wrote to me): (.*)")


def talked(d: Directory, agent, tick: int, people=(), skip: str | None = None,
           most: int = 4) -> list[str]:  # fmt: skip
    """Today's conversations as one remembers them: with whom, and the last words said — what
    was settled is in them. Without this the same plan was agreed again and again (r10_human-v2:
    two colleagues agreed six times to go over the screens together). With `people`, only the
    conversations with any of them; `skip` is the one going on now."""
    me, day, w = agent.name, tick // d.day_span, d.w
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
        said = " → ".join(f'{w.ME if s == me else d.who(s)} "{_clip(d.humanize(t), 70)}"'
                          for _, s, _, t in lines[-2:])  # fmt: skip
        out.append(fill(w.T_LINE, when=d.span(lines[0][0], lines[-1][0], tick),
                        who=", ".join(d.who(o) for o in others),
                        how=w.HOW.get(sid.split(":")[0], ""), words=said))  # fmt: skip
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


def _enum(values, none: str):
    values = tuple(dict.fromkeys(values))
    return Literal[values] if values else Literal[none]


def act_schema(d: Directory, agent, view, evaluation: bool = False) -> type[BaseModel]:
    """Names and titles to choose from: open tasks only, and everyone but me. `people` is not
    narrowed to who is here: an assignment's team rarely is (r10_human-v3: the manager, alone with
    the owner, could only name the owner again, and eleven assignments were refused); a talk to
    someone absent becomes a message (`to_action`)."""
    titles = _choosable(d, view)
    people = [n for pid, n in d.name.items() if pid != agent.name]
    kinds = [k for k in d.w.KIND if evaluation or k != "evaluate"]
    places = [d.place(p) for p in view.places]
    T, P, W = (_enum(x, d.w.NONE) for x in (titles, people, places))
    return create_model(
        "HumanAction",
        thought=(str, ...),
        kind=(Literal[tuple(kinds)], ...),
        task=(T | None, ...),
        person=(P | None, ...),
        people=(list[P], ...),
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
    place_of = {d.place(p): p for p in view.places}
    kind = reply["kind"]
    if kind == "prepare":  # looking ahead at a waiting task: no progress, so a rest to the engine
        title = reply.get("task") or d.w.WAITING_TASK
        thought = (reply.get("thought") or "").strip()
        reply = reply | {"kind": "rest", "task": None,
                         "thought": fill(d.w.PREPARE, task=title, text=thought).strip()}  # fmt: skip
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
    if kind == "assign":
        target, targets = _team(target, targets)
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
        else None,
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


def _team(owner: str | None, people: list[str]) -> tuple[str | None, list[str]]:
    """An assignment's owner and team, each person once: an owner named again among the team is
    a slip of the form, not a second person."""
    if owner is None and people:
        owner, people = people[0], people[1:]
    return owner, [p for p in dict.fromkeys(people) if p != owner]


def remembered(d: Directory, action: Action) -> str:
    """What I did, as I would remember it: the deed in words, then my thought."""
    w = d.w
    who = d.who(action.target) if action.target else ", ".join(d.who(t) for t in action.targets)
    if action.kind == "talk":
        who = who or w.AROUND
    deed = w.DEED.get(action.kind)
    deed = action.kind if deed is None else fill(
        deed, task=d.task(action.task) if action.task else w.A_TASK, who=who,
        place=d.place(action.place, w.ELSEWHERE), about=d.who(action.subject))  # fmt: skip
    if action.text and action.kind in _SPOKEN:
        deed += f': "{action.text}"'
    return f"{deed}. {action.reflection}"


# --- plan ---


def plan_schema(d: Directory, agent, view, marks: list[str]) -> type[BaseModel]:
    titles = _choosable(d, view)
    people = [n for pid, n in d.name.items() if pid != agent.name]
    kinds = [k for k in d.w.KIND if k not in ("evaluate", "chat")]
    places = [d.place(p) for p in view.places]
    T, P, W = (_enum(x, d.w.NONE) for x in (titles, people, places))
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
    place_of = {d.place(p): p for p in view.places}
    for b in reply["plan"]:
        if isinstance(b.get("until"), int):  # the engine's shape (the demo backend)
            items.append(PlanItem.model_validate(b))
            continue
        kind = b["kind"]
        if kind == "prepare" and d.by_title.get(b.get("task") or ""):
            # A work block on the waiting task: while it waits the engine judges the block, so
            # my other open work comes first (r10_human-v2: a kept prepare-rest idled four ticks
            # beside an unfinished task), and once it is free the block works it.
            text = fill(d.w.PREPARE, task=b["task"], text=b.get("text") or "").strip()
            b, kind = b | {"kind": "work", "text": text}, "work"
        elif kind == "prepare":  # see to_action
            text = fill(d.w.PREPARE, task=b.get("task") or d.w.WAITING_TASK,
                        text=b.get("text") or "").strip()  # fmt: skip
            b, kind = b | {"kind": "rest", "task": None, "text": text}, "rest"
        target = d.by_name.get(b.get("person") or "")
        targets = [d.by_name[n] for n in b.get("people") or [] if n in d.by_name]
        if kind == "assign":
            target, targets = _team(target, targets)
        place = place_of.get(b.get("place") or "")
        if kind == "eat" and not place:
            place = next((p for p in view.places if p == "cafeteria"), None)
        data = {"kind": kind, "task": d.by_title.get(b.get("task") or ""), "target": target,
                "targets": targets, "place": place, "subject": d.by_name.get(b.get("about") or ""),
                "until": d.tick_of(b["until"], tick), "text": b.get("text") or "-"}  # fmt: skip
        items.append(PlanItem.model_validate(data))
    return items


# --- conversation ---


def my_work_brief(d: Directory, agent, view) -> str | None:
    """One line on what I am busy with, as I know it, for a conversation."""
    if view is None:
        return None
    w = d.w
    notes = {n["task"]: n for n in agent._task_notes(agent._known(view))}
    rows = []
    for t in view.tasks:
        if t.role not in ("owner", "contributor", "helper") or t.lifecycle == "done":
            continue
        row = d.task(t.id)
        if t.lifecycle == "review":
            row += w.B_REVIEW
        elif (n := notes.get(t.id)) and n.get("can_work") == "no":
            row += fill(
                w.B_WAITING, tasks=", ".join(d.task(x["task"]) for x in n.get("waits_on", []))
            )
        else:
            row += f" ({_left(d, t.remaining_ticks)})"
        rows.append(row)
    return w.B_HEAD + ", ".join(rows) if rows else w.W_NONE


def thread_text(d: Directory, agent, thread: Thread, seen: int, kind: str, place: str | None,
                memories: list[str], target: str | None = None) -> tuple[str, dict[str, str]]:  # fmt: skip
    """A conversation as lines "#n name: words", with labels for the reply choice; returns the
    text and label → utterance id."""
    me, w = agent.name, d.w
    people = sorted({u.speaker for u in thread.utterances} - {me})
    others = ", ".join(d.who(p) for p in people) or w.COLLEAGUE
    at = thread.utterances[-1].timestamp if thread.utterances else 0
    L = [fill(w.C_NOW, clock=d.clock(at, at)) + " " + fill(
        w.SETTING.get(kind, w.SETTING["talk"]), others=others,
        place=w.PLACE.get(place or "", w.OFFICE))]  # fmt: skip
    if brief := my_work_brief(d, agent, agent._view):
        L.append(brief)
    if agent._view is not None:  # what these people wait on me for: a sign-off asked of me
        L += [fill(w.C_REVIEW, who=d.who(t.owner), task=d.task(t.id)) for t in agent._view.tasks
              if t.lifecycle == "review" and t.can_approve and t.owner in people]  # fmt: skip
    L += _strain(d, agent)
    if feel := _feelings(d, agent, people):
        L.append(w.C_FEELINGS + "\n".join(feel))
    if reflections := agent.memory.reflections(1):
        L.append(fill(w.S_THOUGHT, x=d.humanize(reflections[-1])))
    if memories:
        L.append(w.C_MEMORIES + "\n".join(f"- {d.humanize(m)}" for m in memories[:6]))
    if people:  # the root utterance's id is the session's
        if earlier := talked(d, agent, at, people, thread.utterances[0].id, 3):
            L.append(w.C_EARLIER + "\n".join(earlier))
    start = min(max(0, len(thread.utterances) - agent.config.context_size), seen)
    labels: dict[str, str] = {}
    L.append(w.C_TALK)
    for i, u in enumerate(thread.utterances[start:], start=start):
        label = f"#{i}"
        labels[label] = u.id
        who = w.ME if u.speaker == me else d.who(u.speaker)
        new = w.C_NEW if i >= seen and u.speaker != me else ""
        L.append(f"{label} {who}: {d.humanize(u.text)}{new}")
    if target is not None:
        tu = thread.get(target)
        if tu is not None:
            L.append(fill(w.C_REPLY_TO, who=d.who(tu.speaker), text=d.humanize(tu.text)))
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
        [head, "- " + d.w.CANDOR, _speech(d), persona_card(d, pid), d.w.COWORKERS + people]
    )


def clean_speech(text: str, my_name: str) -> str:
    """One line of speech: no speaker label or quotes around it."""
    text = text.strip()
    labels = "|".join(re.escape(x) for x in (human_ko.ME, human_en.ME, my_name))
    text = re.sub(rf"^({labels})\s*[:：]\s*", "", text)
    if len(text) > 1 and text[0] in "\"'“" and text[-1] in "\"'”":
        text = text[1:-1].strip()
    return text


def replan_reason(d: Directory, reason: str) -> str:
    """The engine's re-plan reason ("T05 newly mine; T07 can be worked on now"), in words."""
    parts = []
    for part in reason.split("; "):
        if part == "the afternoon starts":
            parts.append(d.w.AFTERNOON)
            continue
        for suffix, why in d.w.REPLAN_WHY.items():
            if part.endswith(suffix):
                ids = [x.strip() for x in part[: -len(suffix)].split(",")]
                parts.append(", ".join(d.task(i) for i in ids) + f": {why}")
                break
        else:
            parts.append(d.humanize(part))
    return "; ".join(parts)


def lunch_error(d: Directory, start: int, until: int, lunch: int, tick: int) -> str:
    """Why a plan's eat block was refused, in clock times."""
    return fill(d.w.LUNCH_ERROR, start=d.clock(start, tick), until=d.clock(until, tick),
                lunch=d.clock(lunch, tick), end=d.clock(lunch + LUNCH_TICKS, tick))  # fmt: skip


def fit_lunch(plan: list[PlanItem], start: int, lunch: int,
              wait: str = human_en.WAIT_LUNCH) -> list[PlanItem]:  # fmt: skip
    """The plan's eat block moved onto lunch: lunch is cut out of whatever block covered it, and
    the time the eat block left goes to the block after. Real replies put lunch an hour early or
    late, and asking again did not fix it (2026-10-08 preflight). `wait` is the text of a wait
    for lunch when nothing comes before it."""
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
        out.insert(0, PlanItem(kind="rest", until=noon, text=wait))
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
