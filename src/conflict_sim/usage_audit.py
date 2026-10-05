"""Metadata-only call tracing; no prompts, counters or simulation state are modified."""

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
            audit_path = getattr(owner, "audit_path", None)
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
