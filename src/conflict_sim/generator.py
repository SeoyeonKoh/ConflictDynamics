"""The scenario generator's drafts and conversation: ask back, generate, edit, auto-fix."""

import copy
import json
import os
import re
import secrets
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Literal

import yaml
from pydantic import ValidationError

from . import company_runtime
from .company import CONF_DIR
from .company_runtime import C15Scenario, Experiment, load_c15_scenario
from .llm import LLMError
from .scenario_draft import (
    FACTORS,
    OFFICE,
    CompanyDraft,
    PatchError,
    Version,
    apply_ops,
    check,
    diff,
    files_of,
    version_from_scenario,
)

MAX_FIXES = 3
TEMPERATURE = 0.4
RECENT_MESSAGES = 20  # conversation lines each call sees
MATERIAL_PREVIEW = 1500  # characters of each material the router sees
# What one call may carry, so a prompt stays under the server's 400_000-character input limit
MATERIALS_BUDGET = 120_000  # attached materials, shared between the files
MESSAGE_CHARS = 2_000  # each conversation line
EXCERPT_CHARS = 400  # each scenario.materials text inside a version shown to the model
TRIM_MARK = "…(trimmed "
BASELINE_ALONE = "baseline만 바뀌었어요 — 비교군과 다른 점에 나타나요"

WRITING_GUIDE = (
    Path(__file__).resolve().parents[2] / "docs" / "scenario-writing-guide.md"
).read_text("utf-8")
with (CONF_DIR / "environment" / "office" / f"{OFFICE}.yaml").open(encoding="utf-8") as _handle:
    OFFICE_PLACES = [place["id"] for place in yaml.safe_load(_handle)["places"]]


def _scenario_schema() -> dict:
    schema = C15Scenario.model_json_schema()
    for key in ("id", "preset", "experiment"):  # the generator fills these when it saves
        schema["properties"].pop(key, None)
    schema["required"] = [k for k in schema.get("required", []) if k in schema["properties"]]
    return schema


COMPANY_SCHEMA = json.dumps(CompanyDraft.model_json_schema(), ensure_ascii=False)
SCENARIO_SCHEMA = json.dumps(_scenario_schema(), ensure_ascii=False)

SYSTEM_PROMPT = f"""You are the scenario writer of ConflictDynamics, an organization simulator.
HR staff and organization researchers describe an experiment in plain words; you turn it into a
company and a scenario the engine runs as they are. The user knows neither YAML nor the engine.
Write your "reply" to the user in Korean, briefly. Every text the simulated people read (names,
tasks, materials, agendas, persona fields) is Korean too.

## Company rules (a generated company)
- 3 to 20 people (the office has 20 seats).
- At most 6 departments. A department id is short English; its name is the Korean name the
  agents hear.
- Exactly one person at the top (reports_to null). Reporting lines have no cycle.
- From scratch, people ids are P01, P02, … and core task ids are C01, C02, ….
- A task's authority_scope names its sign-off; whoever signs it off holds an approve authority
  with that scope.
- The scenario uses language: Korean, prompt_style: human, schema_version: 1.
- The scenario's task_runtime lists exactly the company's task ids.
- A meeting's or shock's place is one of the office place ids: {", ".join(OFFICE_PLACES)}.

## Disposition rules
- Put an aggressive or irrational behaviour only into a person the user explicitly named. Never
  add one on your own.
- Write it as a description of behaviour, e.g. "피드백할 때 상대를 깎아내리고 비꼬는 말을 쓴다.
  잘못을 사람 탓으로 돌린다." Never write slurs or insults themselves into a persona.
- When the compared factor is disposition, such a behaviour in the variant IS the manipulation:
  do not warn about it.
- Only when the factor is something else (structure, work or event) and a draft still carries
  such a behaviour, including in both versions, warn in your reply that it departs from the
  writing guide and may blur the result. Do not refuse.

## Variant rules
- The variant changes one factor of the baseline: structure (reports_to, authorities,
  departments), work (effort, deadlines, added work), disposition (the narrative persona fields)
  or event (shocks, work arriving during the day). Variant ops never touch anything outside the
  chosen factor. Once a pair exists, a later change that is not the factor goes to both
  versions alike.

## Patch paths
- In a list whose items have ids (people, departments, tasks, conflict_events, task_runtime,
  projects, meetings), name an item by its id, never by its position:
  /variant/company/people/HDS-014/communication_style. A position there is refused. Append a new
  item with /-.
- Before you reply, check that each op's id is the person or task your reply names.

## Shortened texts
- To fit the request, long texts you are shown may end in "…(trimmed N chars)". Never copy such
  a text into an op: an op whose value carries that mark is refused. Leave those texts as they
  are, or write a whole new text.

## Experiment
- Fill experiment: id (a short English id that joins the pair), factor, hypothesis, measures,
  behaviour_checks. It is a draft setting, not part of a version: give it in "settings":
  {{"experiment": {{...}}}}, never in an op (/scenario/experiment does not exist).
- A measure's metric is one of stress, mood, relation, task_completion, rest_ratio; subject is a
  person id, all, or partners_of:<id>; toward is whom a relation points at; direction is up or
  down.
- Always give at least one behaviour check: a question whether the manipulation really happened
  (a language model may soften a rude role; without the check "no effect" and "did not act it"
  look the same).
- Fill the scenario's research_question, manipulated_variable, fixed_variables,
  observable_outputs and manipulation_check for the same experiment.

## Attached md materials
- Ground the work in the user's md materials: task names, content, deliverable format and review
  criteria, order.
- Also put the same content into the scenario's materials under the ids of the tasks it grounds,
  so the agents can read it while they work.
- Without materials, work from the experiment and the organization the user described.

## Output
- JSON only: no prose and no code fences.

## Scenario writing guide (verbatim)
{WRITING_GUIDE}"""

ROUTER_STEP = """## This call: choose the next step
From the conversation and the draft's state choose:
- ask: something needed is missing; ask for it. From scratch you need the experiment's intent,
  the organization, and whether to make a pair; for a variant, the factor to change. Ask only
  what is needed now.
- generate: make it new (from scratch: the whole company and scenario; a variant: the variant).
- edit: change the existing draft as the user says.
In settings put only what this message decided: title (a short Korean title), pair (from
scratch: also make a variant), factor (structure|work|disposition|event), experiment (without
role). When next is generate and settings.experiment in the draft is still null, fill experiment.
Output: {"reply": "...", "next": "ask|generate|edit", "settings": {...}}"""

COMPANY_STEP = f"""## This call: write the company
Write the company from the conversation and the materials, as one object of this JSON schema
(organization is the company's name, project the project's name):
{COMPANY_SCHEMA}"""

SCENARIO_STEP = f"""## This call: write the scenario
Write the scenario that runs on the given company. Work out the schedule as guide 2.6 says and
give every task its materials. One object of this JSON schema, without id, preset and experiment:
{SCENARIO_SCHEMA}"""

VARIANT_STEP = """## This call: make the variant
The variant starts as a copy of the baseline. Give JSON Patch ops (add, replace, remove) that
change the chosen factor only; paths start with /variant/company/ or /variant/scenario/.
When settings.experiment is null, also give the experiment in settings.
Output: {"reply": "what changed, in a sentence or two", "ops": [{"op": "replace", "path":
"/variant/...", "value": ...}], "settings": {"experiment": {...}} (only when it is null)}"""

EDIT_STEP = """## This call: edit the draft
Give JSON Patch ops (add, replace, remove) that make the user's change; paths start with
/baseline/ or /variant/.
- When locked is true the baseline is an existing scenario and may not change: every op goes to
  /variant/. A change outside the chosen factor will show as a difference outside the factor;
  say so in the reply.
- When locked is false and both versions are drafted (a pair), a change that IS the chosen
  factor goes to /variant/ only. Any other change is made with the same ops on both /baseline/
  and /variant/ (check that each path names the same item in both), and the reply says so,
  e.g. "두 버전 모두에 적용했어요 (비교 변수 아님)".
- A change to the experiment (hypothesis, measures, behaviour checks) goes in settings.
Output: {"reply": "what changed, in a sentence or two", "ops": [...], "settings": {"experiment":
{...}} (only when the experiment changes)}"""

FIX_STEP = """## This call: fix the format errors
The engine rejected this version (document) with these errors. Give only JSON Patch ops (add,
replace, remove) that remove the errors; paths are within the document (/company/...,
/scenario/...). Change nothing the errors do not need.
Output: {"ops": [...]}"""

_ID = re.compile(r"^d-\d{8}-\d{4}-[0-9a-f]{4}$")


class DraftBusy(RuntimeError):
    pass


def _now() -> str:
    return datetime.now().isoformat()


class Drafts:
    """One folder of <id>.json; a draft takes one message at a time."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self._locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()

    def _path(self, draft_id: str) -> Path:
        if not _ID.match(draft_id):
            raise KeyError(draft_id)
        return self.root / f"{draft_id}.json"

    def create(self, mode: Literal["scratch", "variant"], source: str | None) -> dict:
        if mode not in ("scratch", "variant") or (mode == "variant") != bool(source):
            raise ValueError("a variant needs a source scenario; a scratch draft takes none")
        baseline = version_from_scenario(source).model_dump(mode="json") if source else None
        while True:
            draft_id = f"d-{datetime.now():%Y%m%d-%H%M}-{secrets.token_hex(2)}"
            if not self._path(draft_id).exists():
                break
        draft = {
            "id": draft_id,
            "created": _now(),
            "updated": "",
            "mode": mode,
            "source": source,
            "title": "",
            "pair": False,
            "factor": None,
            "experiment": None,
            "materials": [],
            "versions": {"baseline": baseline, "variant": None},
            "messages": [],
            "saved": [],
        }
        self.write(draft)
        return draft

    def load(self, draft_id: str) -> dict:
        path = self._path(draft_id)
        if not path.is_file():
            raise KeyError(draft_id)
        return json.loads(path.read_text("utf-8"))

    def listing(self) -> list[dict]:
        rows = []
        for path in self.root.glob("d-*.json"):
            try:
                draft = json.loads(path.read_text("utf-8"))
                rows.append({k: draft[k] for k in ("id", "title", "mode", "updated", "saved")})
            except (OSError, ValueError, KeyError, TypeError):
                continue  # one broken file does not hide the other drafts
        return sorted(rows, key=lambda row: row["updated"], reverse=True)

    @contextmanager
    def busy(self, draft_id: str):
        with self._guard:
            lock = self._locks.setdefault(draft_id, threading.Lock())
        if not lock.acquire(blocking=False):
            raise DraftBusy(draft_id)
        try:
            yield
        finally:
            lock.release()

    def write(self, draft: dict) -> None:
        """Whole or not at all: a reader never sees half a file."""
        path = self._path(draft["id"])
        draft["updated"] = _now()
        self.root.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".json.tmp")
        temp.write_text(json.dumps(draft, ensure_ascii=False, indent=1), "utf-8")
        os.replace(temp, path)


def _check(doc) -> list[str]:
    """check() for a stored version, which may not even have the shape of one yet."""
    try:
        version = Version.model_validate(doc)
    except ValidationError as error:
        return [
            f"{'.'.join(map(str, e['loc']))}: {e['msg']}" if e["loc"] else e["msg"]
            for e in error.errors()
        ]
    return check(version)


def _experiment(draft: dict, role: str) -> Experiment | None:
    if not draft["experiment"]:
        return None
    try:
        return Experiment.model_validate({"id": "preview", **draft["experiment"], "role": role})
    except ValidationError:
        return None


def view(draft: dict) -> dict:
    """The draft as the screen shows it: engine checks, the pair's diff, the files it would save."""
    checks = {k: None if doc is None else _check(doc) for k, doc in draft["versions"].items()}
    passing = {
        k: Version.model_validate(doc) for k, doc in draft["versions"].items() if checks[k] == []
    }
    found = diff(passing["baseline"], passing["variant"]) if len(passing) == 2 else []
    files = {
        k: files_of(v, "preview", experiment=_experiment(draft, k), reuse_preset=None)
        for k, v in passing.items()
    }
    outside = [x for x in found if x["factor"] != draft["factor"]]
    return {**draft, "checks": checks, "diff": found, "outside": outside, "files": files}


class SaveRefused(ValueError):
    pass


SLUG_CHARS = 40


def _slug(draft: dict) -> str:
    """A file name part from the title, else the experiment id (titles are mostly Korean), else
    the draft id."""
    experiment = draft["experiment"] or {}
    for text in (draft["title"], experiment.get("id"), draft["id"]):
        slug = re.sub(r"[^a-z0-9]+", "_", str(text or "").lower()).strip("_")
        if slug := slug[:SLUG_CHARS].rstrip("_"):
            return slug
    raise AssertionError("a draft id always gives a slug")


def _check_measures(version: Version, experiment: Experiment) -> None:
    people = {p.id for p in version.company.people}
    for measure in experiment.measures:
        subject = measure.subject
        if subject != "all" and subject.removeprefix("partners_of:") not in people:
            raise SaveRefused(f"measure names an unknown person: {subject}")
        if measure.toward is not None and measure.toward not in people:
            raise SaveRefused(f"measure names an unknown person: {measure.toward}")


def _link(draft: dict, role: str, experiment_id: str, baseline: str) -> Experiment:
    """The experiment block a saved scenario carries, which links it to its pair (spec §6)."""
    try:
        return Experiment.model_validate({
            **(draft["experiment"] or {}),
            "id": experiment_id,
            "role": role,
            "factor": draft["factor"],
            "baseline": baseline,
        })  # fmt: skip
    except ValidationError as error:
        raise SaveRefused(f"the experiment is not valid: {error.errors()[0]['msg']}") from None


def _write_loadable(texts: dict[Path, str], names: list[str]) -> None:
    """Write the files, then load each scenario through the real loader; on any failure remove
    every file this call wrote."""
    written: list[Path] = []
    try:
        for path, text in texts.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("x", encoding="utf-8") as handle:
                written.append(path)
                handle.write(text)
        for name in names:
            company_runtime.build_company_config(name)
    except Exception as error:
        for path in written:
            path.unlink(missing_ok=True)
        if isinstance(error, OSError):
            raise
        raise SaveRefused(f"the saved files do not load: {error}") from error


def save(draft: dict, conf_dir: Path, *, accept_outside: bool) -> dict:
    """Write the draft's versions as new scenario files under conf_dir and return the draft with
    the names written. Nothing is overwritten, and nothing is left written when it refuses. The
    load check reads company_runtime.CONF_DIR, which is what the server passes as conf_dir."""
    versions = draft["versions"]
    if draft["mode"] == "variant" and versions["variant"] is None:
        raise SaveRefused("write the variant first")
    if versions["baseline"] is None and versions["variant"] is None:
        raise SaveRefused("nothing to save yet")
    shown = view(draft)
    if all(c is None for c in shown["checks"].values()) or any(shown["checks"].values()):
        raise SaveRefused("fix the errors first")
    if shown["outside"] and not accept_outside:
        raise SaveRefused("the variant differs outside its factor")
    slug, variant_mode = _slug(draft), draft["mode"] == "variant"
    roles = [r for r in ("baseline", "variant") if draft["versions"][r] is not None]
    reuse = None
    if variant_mode:
        roles = ["variant"]  # the baseline is the source scenario, which is not written
        company = version_from_scenario(draft["source"]).company
        if Version.model_validate(draft["versions"]["variant"]).company == company:
            reuse = load_c15_scenario(draft["source"]).preset
    experiment_id = (draft["experiment"] or {}).get("id") or slug
    suffix = 1
    while True:
        tail = "" if suffix == 1 else f"_{suffix}"
        names = {r: f"{slug}_{'base' if r == 'baseline' else 'var'}{tail}" for r in roles}
        baseline = draft["source"] if variant_mode else f"gen_{slug}_base{tail}"
        texts: dict[Path, str] = {}
        for role, name in names.items():
            version = Version.model_validate(draft["versions"][role])
            experiment = _link(draft, role, f"{experiment_id}{tail}", baseline)
            _check_measures(version, experiment)
            files = files_of(
                version,
                name,
                experiment=experiment,
                reuse_preset=reuse if role == "variant" else None,
            )
            texts.update({Path(conf_dir) / rel: text for rel, text in files.items()})
        if not any(path.exists() for path in texts):
            break
        suffix += 1
    saved = [f"gen_{name}" for name in names.values()]
    _write_loadable(texts, saved)
    return {**copy.deepcopy(draft), "saved": saved}


def _spent(llm) -> int:
    usage = getattr(llm, "usage", None)
    return sum(row.get("total_tokens", 0) for row in usage.values()) if usage else 0


def _call(llm, model: str, step: str, payload: dict) -> dict:
    text = llm.complete(
        system=f"{SYSTEM_PROMPT}\n\n{step}",
        prompt=json.dumps(payload, ensure_ascii=False, indent=1),
        model=model,
        temperature=TEMPERATURE,
        json_mode=True,
    )
    try:
        answer = json.loads(text)
    except ValueError:
        answer = None
    if not isinstance(answer, dict):
        raise LLMError("the generator's reply is not a JSON object")
    return answer


def _trim(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}{TRIM_MARK}{len(text) - limit} chars)"


def _context(draft: dict, *, preview: bool = False) -> dict:
    share = MATERIALS_BUDGET // max(len(draft["materials"]), 1)
    if preview:
        share = min(share, MATERIAL_PREVIEW)
    return {
        "mode": draft["mode"],
        "source": draft["source"],
        "settings": {k: draft[k] for k in ("title", "pair", "factor", "experiment")},
        "drafted": {k: v is not None for k, v in draft["versions"].items()},
        "materials": [
            {"name": m["name"], "text": _trim(m["text"], share)} for m in draft["materials"]
        ],
        "conversation": [
            {"role": m["role"], "text": _trim(m["text"], MESSAGE_CHARS)}
            for m in draft["messages"][-RECENT_MESSAGES:]
        ],
    }


def _shown(doc):
    """A version as the model is sent it: long scenario materials cut to an excerpt."""
    scenario = doc.get("scenario") if isinstance(doc, dict) else None
    materials = scenario.get("materials") if isinstance(scenario, dict) else None
    if not isinstance(materials, dict):
        return doc
    short = {k: _trim(v, EXCERPT_CHARS) if isinstance(v, str) else v for k, v in materials.items()}
    return {**doc, "scenario": {**scenario, "materials": short}}


def _take_settings(draft: dict, settings) -> list[str]:
    """Router, variant or edit settings into the draft; returns a note for what it could not
    take."""
    if not isinstance(settings, dict):
        return []
    if isinstance(settings.get("title"), str):
        draft["title"] = settings["title"]
    if isinstance(settings.get("pair"), bool) and draft["mode"] == "scratch":
        draft["pair"] = settings["pair"]
    if settings.get("factor") in FACTORS:
        draft["factor"] = settings["factor"]
    experiment = settings.get("experiment")
    if isinstance(experiment, dict):
        experiment = {k: v for k, v in experiment.items() if k != "role"}
        try:
            Experiment.model_validate({"id": "draft", **experiment, "role": "baseline"})
        except ValidationError as error:
            return [
                f"(실험 정보는 형식이 맞지 않아 반영하지 않았습니다: {error.errors()[0]['msg']})"
            ]
        draft["experiment"] = experiment
    if draft["experiment"] and draft["factor"]:  # one factor for the draft and its experiment
        draft["experiment"]["factor"] = draft["factor"]
    return []


def _fixed(name: str, doc, llm, model: str) -> tuple[dict, str]:
    """The version after up to MAX_FIXES rounds of handing the engine's errors back."""
    errors = _check(doc)
    found, rounds, patch_error = len(errors), 0, None
    while errors and rounds < MAX_FIXES:
        rounds += 1
        payload = {"document": _shown(doc), "errors": errors}
        if patch_error:
            payload["last_ops_refused"] = patch_error
        ops = _call(llm, model, FIX_STEP, payload).get("ops")
        try:  # a bad fix changes nothing; the next round says why
            doc, patch_error = apply_ops(doc, _well_formed(ops)), None
        except PatchError as error:
            patch_error = str(error)
        errors = _check(doc)
    line = f"형식 검사({name}): 오류 {found}개"
    if found:
        line += f" → 자동 수정 {rounds}번"
    line += " → 통과" if not errors else " → 통과하지 못함: " + "; ".join(errors[:3])
    return doc, line


def _well_formed(ops) -> list[dict]:
    if not isinstance(ops, list) or not all(
        isinstance(op, dict) and isinstance(op.get("path"), str) for op in ops
    ):
        raise PatchError("ops must be a list of objects, each with a path")
    for op in ops:
        if TRIM_MARK in json.dumps(op.get("value"), ensure_ascii=False):
            raise PatchError(f"an op copies a shortened text (…(trimmed N chars)): {op['path']}")
    return ops


def _patched(versions: dict, ops, allowed: tuple[str, ...]) -> tuple[dict | None, str | None]:
    """All the ops on {baseline, variant}, or none of them and the reason."""
    refused = "수정을 적용하지 않았습니다: "
    try:
        for op in _well_formed(ops):
            root = op["path"].split("/")[1] if op["path"].startswith("/") else ""
            if root == "baseline" and root not in allowed:
                return (
                    None,
                    refused + f"baseline(원본)은 잠겨 있어 고칠 수 없습니다 ({op['path']}).",
                )
            if root not in allowed:
                start = " 또는 ".join(f"/{name}/" for name in allowed)
                return None, refused + f"경로는 {start}로 시작해야 합니다 ({op['path']})."
        return apply_ops(versions, ops), None
    except PatchError as error:
        return None, refused + str(error)


def _settle_versions(draft, patched, llm, model, checks) -> None:
    for name in ("baseline", "variant"):
        doc = patched.get(name)
        if doc != draft["versions"][name]:
            if doc is not None:
                doc, line = _fixed(name, doc, llm, model)
                checks.append(line)
            draft["versions"][name] = doc


def _generate(draft: dict, llm, model: str, checks: list[str]) -> list[str]:
    versions, context = draft["versions"], _context(draft)
    replies = []
    if draft["mode"] == "scratch":
        company = _call(llm, model, COMPANY_STEP, context)
        scenario = _call(llm, model, SCENARIO_STEP, {**context, "company": company})
        scenario.setdefault("language", "Korean")
        scenario.setdefault("prompt_style", "human")
        doc = {"company": company, "scenario": scenario}
        versions["baseline"], line = _fixed("baseline", doc, llm, model)
        versions["variant"] = None
        checks.append(line)
    if draft["mode"] == "variant" or draft["pair"]:
        payload = {**context, "baseline": _shown(versions["baseline"])}
        answer = _call(llm, model, VARIANT_STEP, payload)
        replies += [str(answer.get("reply") or ""), *_take_settings(draft, answer.get("settings"))]
        start = {"baseline": versions["baseline"], "variant": copy.deepcopy(versions["baseline"])}
        patched, reason = _patched(start, answer.get("ops"), ("variant",))
        if reason:
            return [*replies, reason]
        versions["variant"] = None  # a new variant is checked even when it equals the old one
        _settle_versions(draft, patched, llm, model, checks)
    return replies


def _edit(draft: dict, llm, model: str, checks: list[str]) -> list[str]:
    versions, locked = draft["versions"], draft["mode"] == "variant"
    shown = {k: _shown(v) for k, v in versions.items()}
    answer = _call(llm, model, EDIT_STEP, {**_context(draft), "locked": locked, "versions": shown})
    noted = _take_settings(draft, answer.get("settings"))
    allowed = ("variant",) if locked else ("baseline", "variant")
    patched, reason = _patched(versions, answer.get("ops"), allowed)
    if reason:
        return [str(answer.get("reply") or ""), *noted, reason]
    # A pair's baseline changed alone: say so rather than guess whether the variant wanted it too
    alone = None not in versions.values() and patched["variant"] == versions["variant"]
    alone = alone and patched["baseline"] != versions["baseline"]
    _settle_versions(draft, patched, llm, model, checks)
    return [str(answer.get("reply") or ""), *noted, BASELINE_ALONE if alone else ""]


def _take_message(draft: dict, text: str, attachments: list[dict]) -> None:
    """The user's line and its attachments into the draft; a file sent again under the same name
    replaces the earlier one (a retry after a failure resends what it already stored)."""
    names = {a["name"] for a in attachments}
    draft["materials"] = [m for m in draft["materials"] if m["name"] not in names] + [
        {"name": a["name"], "text": a["text"]} for a in attachments
    ]
    if attachments:
        text += "\n\n첨부: " + ", ".join(a["name"] for a in attachments)
    draft["messages"].append({"role": "user", "text": text, "tokens": 0})


def failed(draft: dict, text: str, attachments: list[dict], error: Exception, llm) -> dict:
    """The draft after a turn the backend ended: the message and its attachments are kept (so a
    retry has them) with a failure line saying what the turn spent, when it is known."""
    draft = copy.deepcopy(draft)
    _take_message(draft, text, attachments)
    tokens = _spent(llm)  # the backend is fresh for each turn, so this is the turn's spending
    note = f" (토큰 {tokens})" if tokens else ""
    line = f"생성 실패{note}: {error}"
    draft["messages"].append({"role": "check", "text": line, "tokens": tokens})
    return draft


def turn(draft: dict, text: str, attachments: list[dict], llm, model: str) -> dict:
    """One user message through the generator; returns the new draft and leaves the given one
    alone. An LLM failure raises, so the caller keeps the draft as it was."""
    draft = copy.deepcopy(draft)
    start = _spent(llm)
    _take_message(draft, text, attachments)
    route = _call(llm, model, ROUTER_STEP, _context(draft, preview=True))
    replies = [str(route.get("reply") or ""), *_take_settings(draft, route.get("settings"))]
    checks: list[str] = []
    if route.get("next") == "generate":
        replies += _generate(draft, llm, model, checks)
    elif route.get("next") == "edit":
        replies += _edit(draft, llm, model, checks)
    draft["messages"] += [{"role": "check", "text": line, "tokens": 0} for line in checks]
    draft["messages"].append(
        {"role": "ai", "text": "\n\n".join(r for r in replies if r), "tokens": _spent(llm) - start}
    )
    return draft
