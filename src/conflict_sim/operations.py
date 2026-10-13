"""Small opt-in calendar helpers. No LLM, scorer or mutable agent state here."""

from .models import Action, WeeklyOperations


def business_ticks(tick: int, normal_ticks: int, day_span: int, lunch: int) -> int:
    """Elapsed regular working ticks, excluding lunch, overnight and overtime."""
    day, within = divmod(tick, day_span)
    return (
        day * (normal_ticks - 4)
        + min(within, lunch)
        + max(0, min(within, normal_ticks) - lunch - 4)
    )


def elapsed_work(start: int, end: int, normal: int, span: int, lunch: int) -> int:
    return business_ticks(end, normal, span, lunch) - business_ticks(start, normal, span, lunch)


def preparation(action: Action) -> bool:
    return action.reflection.startswith("[preparation]")


def active_blocks(policy: WeeklyOperations, day: int, within: int):
    return [
        b for b in policy.blocks if b.day == day and b.tick <= within < b.tick + b.duration_ticks
    ]
