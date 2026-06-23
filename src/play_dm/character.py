"""Character utility functions."""
from __future__ import annotations

import copy

from play_dm.dice import ability_modifier
from play_dm.models import Character

# Maps each skill to its governing ability (title-cased)
_SKILL_ABILITY: dict[str, str] = {
    "Acrobatics": "Dexterity",
    "Animal Handling": "Wisdom",
    "Arcana": "Intelligence",
    "Athletics": "Strength",
    "Deception": "Charisma",
    "History": "Intelligence",
    "Insight": "Wisdom",
    "Intimidation": "Charisma",
    "Investigation": "Intelligence",
    "Medicine": "Wisdom",
    "Nature": "Intelligence",
    "Perception": "Wisdom",
    "Performance": "Charisma",
    "Persuasion": "Charisma",
    "Religion": "Intelligence",
    "Sleight of Hand": "Dexterity",
    "Stealth": "Dexterity",
    "Survival": "Wisdom",
}

_ABILITY_ATTR: dict[str, str] = {
    "Strength": "strength",
    "Dexterity": "dexterity",
    "Constitution": "constitution",
    "Intelligence": "intelligence",
    "Wisdom": "wisdom",
    "Charisma": "charisma",
}


def _get_ability_score(char: Character, ability: str) -> int:
    attr = _ABILITY_ATTR.get(ability)
    if attr is None:
        raise ValueError(f"Unknown ability: {ability!r}")
    return getattr(char.ability_scores, attr)


def skill_bonus(char: Character, skill: str) -> int:
    """Return total skill bonus (ability mod + proficiency if proficient)."""
    ability = _SKILL_ABILITY.get(skill)
    if ability is None:
        raise ValueError(f"Unknown skill: {skill!r}")
    score = _get_ability_score(char, ability)
    mod = ability_modifier(score)
    proficient = char.skills.get(skill, False)
    return mod + (char.proficiency_bonus if proficient else 0)


def saving_throw_bonus(char: Character, ability: str) -> int:
    """Return saving throw bonus (ability mod + proficiency if proficient)."""
    score = _get_ability_score(char, ability)
    mod = ability_modifier(score)
    proficient = ability in char.saving_throw_proficiencies
    return mod + (char.proficiency_bonus if proficient else 0)


def passive_perception(char: Character) -> int:
    """Return passive Perception score (10 + Perception bonus)."""
    return 10 + skill_bonus(char, "Perception")


def apply_damage(char: Character, amount: int) -> Character:
    """Apply damage to a character. Clamps to 0 and sets unconscious condition."""
    updated = char.model_copy(deep=True)
    updated.current_hp = max(0, updated.current_hp - amount)
    if updated.current_hp == 0 and "unconscious" not in updated.conditions:
        updated.conditions.append("unconscious")
    return updated


def apply_healing(char: Character, amount: int) -> Character:
    """Apply healing to a character. Clamps to max_hp and clears unconscious."""
    updated = char.model_copy(deep=True)
    updated.current_hp = min(updated.max_hp, updated.current_hp + amount)
    if "unconscious" in updated.conditions:
        updated.conditions.remove("unconscious")
    return updated


def consume_spell_slot(char: Character, level: int) -> Character:
    """Consume one spell slot at the given level. Raises ValueError if none remain."""
    slot_key = str(level)
    remaining = char.spell_slots.get(slot_key, 0)
    if remaining <= 0:
        raise ValueError(f"No spell slots remaining at level {level}.")
    updated = char.model_copy(deep=True)
    updated.spell_slots[slot_key] = remaining - 1
    return updated


def long_rest(char: Character) -> Character:
    """Restore HP, spell slots, and clear conditions after a long rest."""
    updated = char.model_copy(deep=True)
    updated.current_hp = updated.max_hp
    updated.spell_slots = copy.deepcopy(updated.max_spell_slots)
    updated.conditions = []
    updated.death_saves = {"successes": 0, "failures": 0}
    return updated
