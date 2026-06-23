"""LLM player integration — character generation and response parsing via Anthropic."""
from __future__ import annotations

import json
import re
from typing import Any

import anthropic

from play_dm.models import AbilityScores, Character, InventoryItem

MODEL = "claude-3-5-haiku-20241022"

_ACTION_TYPES = frozenset(
    {"attack", "spell", "skill_check", "saving_throw", "move", "item_use", "free_action", "none"}
)


def _modifier_str(score: int) -> str:
    mod = (score - 10) // 2
    return f"+{mod}" if mod >= 0 else str(mod)


# ---------------------------------------------------------------------------
# Character generation
# ---------------------------------------------------------------------------

_CHAR_SYSTEM = (
    "You are a Dungeons & Dragons 5th Edition expert. "
    "When asked to create a character, respond with ONLY a valid JSON object — "
    "no markdown, no explanation, no extra text."
)

_CHAR_SCHEMA = """
{
  "name": "<string>",
  "race": "<string>",
  "character_class": "<string, one of: Barbarian, Bard, Cleric, Druid, Fighter, Monk, Paladin, Ranger, Rogue, Sorcerer, Warlock, Wizard>",
  "background": "<string>",
  "personality_traits": "<1-2 sentences describing personality>",
  "ability_scores": {
    "strength": <int 8-18>,
    "dexterity": <int 8-18>,
    "constitution": <int 8-18>,
    "intelligence": <int 8-18>,
    "wisdom": <int 8-18>,
    "charisma": <int 8-18>
  },
  "max_hp": <int>,
  "armor_class": <int>,
  "saving_throw_proficiencies": ["<ability>", ...],
  "skills": {"<Skill Name>": true, ...},
  "spell_slots": {},
  "max_spell_slots": {},
  "spells_known": [],
  "cantrips": [],
  "inventory": [{"name": "<item>", "quantity": <int>}]
}
"""


def generate_character(
    client: anthropic.Anthropic, player_num: int, theme: str = ""
) -> Character:
    """Ask an LLM to create a unique DnD 5e character and return a Character model."""
    theme_clause = f" The campaign theme is: {theme}." if theme else ""
    prompt = (
        f"Create a unique level-1 Dungeons & Dragons 5th Edition character for player {player_num}.{theme_clause} "
        f"Include appropriate starting equipment and class features. "
        f"For spellcasters, include spell slots, spells_known, and cantrips. "
        f"Respond ONLY with this exact JSON schema (no extra fields):\n{_CHAR_SCHEMA}"
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=_CHAR_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()

    # Strip markdown code fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    data = json.loads(raw)

    # Build the character from the JSON data
    ability_scores = AbilityScores(**data["ability_scores"])
    inventory = [
        InventoryItem(name=item["name"], quantity=item.get("quantity", 1))
        for item in data.get("inventory", [])
    ]

    char = Character(
        id=f"player-{player_num}",
        name=data["name"],
        race=data["race"],
        character_class=data["character_class"],
        level=1,
        background=data["background"],
        personality_traits=data.get("personality_traits", ""),
        ability_scores=ability_scores,
        max_hp=data["max_hp"],
        current_hp=data["max_hp"],
        armor_class=data["armor_class"],
        speed=30,
        proficiency_bonus=2,
        skills=data.get("skills", {}),
        saving_throw_proficiencies=data.get("saving_throw_proficiencies", []),
        spell_slots=data.get("spell_slots", {}),
        max_spell_slots=data.get("max_spell_slots", {}),
        spells_known=data.get("spells_known", []),
        cantrips=data.get("cantrips", []),
        inventory=inventory,
    )
    return char


# ---------------------------------------------------------------------------
# Player response
# ---------------------------------------------------------------------------

def _build_system_prompt(char: Character) -> str:
    spells_section = ""
    if char.spells_known or char.cantrips:
        spells_section = (
            f"\nSPELLS KNOWN: {', '.join(char.spells_known) or 'None'}"
            f"\nCANTRIPS: {', '.join(char.cantrips) or 'None'}"
            f"\nSPELL SLOTS: {json.dumps(char.spell_slots) if char.spell_slots else 'N/A'}"
        )

    inventory_str = (
        ", ".join(f"{i.name} x{i.quantity}" for i in char.inventory)
        if char.inventory
        else "Nothing"
    )

    conditions_str = ", ".join(char.conditions) if char.conditions else "None"

    return f"""You are playing {char.name}, a {char.race} {char.character_class} (Level {char.level}) in a Dungeons & Dragons 5th Edition campaign.

CHARACTER SHEET
Name: {char.name} | Race: {char.race} | Class: {char.character_class} (Level {char.level})
Background: {char.background}
Personality: {char.personality_traits}

ABILITY SCORES
STR {char.ability_scores.strength} ({_modifier_str(char.ability_scores.strength)}) | \
DEX {char.ability_scores.dexterity} ({_modifier_str(char.ability_scores.dexterity)}) | \
CON {char.ability_scores.constitution} ({_modifier_str(char.ability_scores.constitution)}) | \
INT {char.ability_scores.intelligence} ({_modifier_str(char.ability_scores.intelligence)}) | \
WIS {char.ability_scores.wisdom} ({_modifier_str(char.ability_scores.wisdom)}) | \
CHA {char.ability_scores.charisma} ({_modifier_str(char.ability_scores.charisma)})

HP: {char.current_hp}/{char.max_hp} | AC: {char.armor_class} | Speed: {char.speed} ft
CONDITIONS: {conditions_str}
INVENTORY: {inventory_str}{spells_section}

RESPONSE FORMAT — you MUST reply with ONLY valid JSON, no extra text:
{{
  "speech": "<what your character says aloud, or empty string>",
  "action_description": "<narrative description of what your character attempts to do>",
  "action_type": "<one of: attack, spell, skill_check, saving_throw, move, item_use, free_action, none>",
  "action_details": {{
    "target": "<name of target, or null>",
    "weapon_or_spell": "<weapon or spell name, or null>",
    "skill": "<skill name for skill_check, e.g. Perception, or null>",
    "ability": "<ability name for saving_throw, e.g. Dexterity, or null>",
    "spell_slot_level": <int level 0-9, 0 if not casting>
  }}
}}

You are a PLAYER, not the DM. Describe only your character's intentions — not outcomes. Stay in character. \
Be creative but act consistently with your character's personality and abilities. \
If you are unconscious (0 HP), you can only roll death saving throws."""


def get_player_response(
    client: anthropic.Anthropic,
    char: Character,
    history: list[dict],
    dm_message: str,
) -> tuple[dict[str, Any], list[dict]]:
    """Send the DM's message to an LLM player and return their parsed response + updated history.

    Returns (parsed_response_dict, updated_history).
    """
    updated_history = list(history) + [{"role": "user", "content": dm_message}]

    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=_build_system_prompt(char),
        messages=updated_history,
    )
    reply_text = response.content[0].text.strip()

    # Strip markdown code fences if present
    reply_text = re.sub(r"^```(?:json)?\s*", "", reply_text)
    reply_text = re.sub(r"\s*```$", "", reply_text)

    try:
        parsed = json.loads(reply_text)
    except json.JSONDecodeError:
        # Graceful fallback: treat the whole reply as speech
        parsed = {
            "speech": reply_text,
            "action_description": "",
            "action_type": "none",
            "action_details": {
                "target": None,
                "weapon_or_spell": None,
                "skill": None,
                "ability": None,
                "spell_slot_level": 0,
            },
        }

    # Sanitize action_type
    if parsed.get("action_type") not in _ACTION_TYPES:
        parsed["action_type"] = "none"

    updated_history = updated_history + [{"role": "assistant", "content": reply_text}]
    return parsed, updated_history
