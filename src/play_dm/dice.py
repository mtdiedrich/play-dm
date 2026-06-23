"""Dice rolling utilities."""
from __future__ import annotations

import random
import re

_DICE_RE = re.compile(r"^(\d*)d(\d+)$", re.IGNORECASE)


def roll(expr: str) -> tuple[int, list[int]]:
    """Roll a dice expression like '2d6', '1d20', or 'd8'.

    Returns (total, individual_rolls).
    """
    m = _DICE_RE.match(expr.strip())
    if not m:
        raise ValueError(f"Invalid dice expression: {expr!r}. Expected format XdY or dY.")
    count = int(m.group(1)) if m.group(1) else 1
    sides = int(m.group(2))
    if count < 1:
        raise ValueError(f"Dice count must be at least 1, got {count}.")
    rolls = [random.randint(1, sides) for _ in range(count)]
    return sum(rolls), rolls


def roll_with_modifier(expr: str, modifier: int) -> tuple[int, list[int], int]:
    """Roll dice and add a modifier. Returns (total, individual_rolls, modifier)."""
    subtotal, rolls = roll(expr)
    return subtotal + modifier, rolls, modifier


def advantage_roll() -> tuple[int, int, int]:
    """Roll two d20 and take the higher. Returns (result, roll1, roll2)."""
    r1 = random.randint(1, 20)
    r2 = random.randint(1, 20)
    return max(r1, r2), r1, r2


def disadvantage_roll() -> tuple[int, int, int]:
    """Roll two d20 and take the lower. Returns (result, roll1, roll2)."""
    r1 = random.randint(1, 20)
    r2 = random.randint(1, 20)
    return min(r1, r2), r1, r2


def ability_modifier(score: int) -> int:
    """Return the DnD 5e ability modifier for the given score."""
    return (score - 10) // 2
