"""An agent chooses whether and where to respond before generating text.

What kind of conversation this is (wiki talk page, office chat, direct message) is the session's
business: it supplies the instructions and how much of the thread this agent has already read.
"""

import json
from dataclasses import dataclass, field

from .llm import LanguageModel
from .models import Decision, Thread

PROMPT_VERSION = "3"


@dataclass
class Agent:
    name: str
    persona: str
    availability: float
    llm: LanguageModel
    model_decide: str
    model_speak: str
    temperature: float = 0.8
    context_size: int = 10
    language: str = "English"
    memory_mode: str = "summary"
    persona_placement: str = "payload"  # "system" puts the persona before the instructions.
    reflections: list[str] = field(default_factory=list)

    def _payload(self, thread: Thread, seen: int) -> dict:
        # Limit already-read history, but never discard unread comments.
        recent_start = max(0, len(thread.utterances) - self.context_size)
        context_start = min(recent_start, seen)
        payload = {
            "speaker": self.name,
            "persona": self.persona,
            "language": self.language,
            # "none" still records reflections but never feeds them back into a prompt.
            "private_memory": (
                []
                if self.memory_mode == "none"
                else self.reflections[-1:]
                if self.memory_mode == "summary"
                else self.reflections
            ),
            "utterances": [u.model_dump() for u in thread.utterances[context_start:]],
            "unread_ids": [u.id for u in thread.utterances[seen:]],
        }
        if self.persona_placement == "system":
            del payload["persona"]
        return payload

    def _system(self, instructions: str) -> str:
        if self.persona_placement == "system":
            return f"You are {self.name}. {self.persona}\n\n{instructions}"
        return instructions

    def decide(self, thread: Thread, instructions: str, *, seen: int) -> Decision:
        response = self.llm.complete(
            system=self._system(instructions),
            prompt=json.dumps(self._payload(thread, seen), ensure_ascii=False),
            model=self.model_decide,
            temperature=self.temperature,
            json_mode=True,
        )
        try:
            decision = Decision.model_validate_json(response)
            if decision.reply_to is not None:
                thread.get(decision.reply_to)
        except ValueError as exc:
            raise ValueError(f"Invalid decision from {self.name}: {exc}") from exc
        self.reflections.append(decision.reflection)
        return decision

    def speak(self, thread: Thread, target: str | None, instructions: str, *, seen: int) -> str:
        payload = self._payload(thread, seen)
        target_id = target if target is not None else thread.utterances[0].id
        payload["target"] = thread.get(target_id).model_dump()
        text = self.llm.complete(
            system=self._system(instructions),
            prompt=json.dumps(payload, ensure_ascii=False),
            model=self.model_speak,
            temperature=self.temperature,
            json_mode=False,
        ).strip()
        if not text:
            raise ValueError(f"Empty comment from {self.name}")
        return text
