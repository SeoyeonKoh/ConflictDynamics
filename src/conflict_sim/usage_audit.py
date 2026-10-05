"""Metadata-only call tracing; no prompts, counters or simulation state are modified."""

import hashlib
import json
import logging
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from inspect import signature
from pathlib import Path

_WRITE_LOCK = threading.Lock()

_CONTEXT = ContextVar("llm_audit", default={})


@contextmanager
def audit_context(**fields):
    token = _CONTEXT.set(_CONTEXT.get() | fields)
    try:
        yield
    finally:
        _CONTEXT.reset(token)


def annotate(**fields):
    _CONTEXT.set(_CONTEXT.get() | fields)


def traced(call_type):
    def decorate(function):
        parameters = signature(function)

        @wraps(function)
        def wrapped(*args, **kwargs):
            bound = parameters.bind(*args, **kwargs).arguments
            owner = bound.get("self")
            fields = {"caller": f"{function.__module__}.{function.__qualname__}"}
            if function.__module__.endswith("llm") and _CONTEXT.get().get("caller"):
                fields.pop("caller")
            audit_path = getattr(owner, "audit_path", None) or getattr(
                getattr(owner, "llm", None), "audit_path", None
            )
            if audit_path is not None:
                fields["audit_path"] = audit_path
            if call_type and _CONTEXT.get().get("call_type"):
                fields["parent_call_type"] = _CONTEXT.get()["call_type"]
            if call_type:
                fields["call_type"] = call_type
            if call_type:
                fields["operation_caller"] = fields.get("caller", _CONTEXT.get().get("caller"))
            if "manager" in bound:
                fields["agent"] = bound["manager"].name
            if function.__name__ == "reflect":
                fields["reflection_scope"] = "relation" if bound.get("about") else "periodic"
            if "tick" in bound:
                fields["tick"] = bound["tick"]
            agent = getattr(owner, "name", None) or getattr(owner, "agent_id", None)
            if agent:
                fields["agent"] = agent
            if function.__name__ == "_ask" and "what" in bound:
                fields["call_type"] = {
                    "plan": "plan_day",
                    "action": "act",
                    "decision": "conversation_decision",
                }.get(bound["what"], bound["what"].replace(" ", "_"))
            if "schema" in bound:
                fields["schema"] = bound["schema"].__name__ if bound["schema"] else None
            if function.__module__.endswith("conversation"):
                fields["session_kind"] = owner.kind
                fields["session_id"] = owner.id
            with audit_context(**fields):
                return function(*args, **kwargs)

        return wrapped

    return decorate


def log_call(event, **fields):
    metadata = (
        {
            "tick": None,
            "agent": None,
            "call_type": "other",
            "caller": None,
            "action_retry": False,
            "validation_retry": False,
            "transport_retry": False,
        }
        | _CONTEXT.get()
        | fields
    )
    if event in ("embedding", "embedding_cache"):
        metadata["embedding_purpose"] = metadata.get("embedding_purpose", metadata["call_type"])
    metadata.pop("system_section_metrics", None)
    audit_path = metadata.pop("audit_path", None)
    metadata["retry"] = any(
        metadata[k] for k in ("action_retry", "validation_retry", "transport_retry")
    )
    logging.getLogger("conflict_sim.llm.audit").info(
        "LLM audit %s", json.dumps({"event": event} | metadata, ensure_ascii=False)
    )

    if audit_path is not None:
        try:
            with _WRITE_LOCK, Path(audit_path).open("a", encoding="utf-8") as output:
                output.write(json.dumps({"event": event} | metadata, ensure_ascii=False) + "\n")
        except OSError:
            logging.getLogger("conflict_sim.llm.audit").warning(
                "Could not write LLM audit metadata"
            )


def text_metric(text):
    """Exact text fingerprint and whitespace-only normalized fingerprint; never retain text."""
    normalized = " ".join(text.split())
    return {
        "chars": len(text),
        "sha256": hashlib.sha256(text.encode()).hexdigest(),
        "whitespace_sha256": hashlib.sha256(normalized.encode()).hexdigest(),
    }


def completion_metadata(system, prompt):
    """Non-overlapping section value sizes; JSON separators/keys remain envelope overhead."""
    sections = dict(_CONTEXT.get().get("system_section_metrics") or {"system": text_metric(system)})
    try:
        payload = json.loads(prompt)
    except (ValueError, TypeError):
        payload = None
    field_chars = None
    if isinstance(payload, dict):
        field_chars = {k: len(json.dumps(v, ensure_ascii=False)) for k, v in payload.items()}
        for key, value in payload.items():
            # View's tasks/blocked/help/places/transcript must be visible individually.
            if key == "view" and isinstance(value, dict):
                for subkey, subvalue in value.items():
                    sections[f"view.{subkey}"] = text_metric(
                        json.dumps(subvalue, ensure_ascii=False)
                    )
            else:
                sections[key] = text_metric(json.dumps(value, ensure_ascii=False))
    else:
        sections["prompt"] = text_metric(prompt)
    return {
        "system_chars": len(system),
        "prompt_chars": len(prompt),
        "payload_field_chars": field_chars,
        "section_metrics": sections,
    }


def embedding_metadata(texts):
    return {"text_count": len(texts), "text_metrics": [text_metric(t) for t in texts]}
