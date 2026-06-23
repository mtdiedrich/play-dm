"""LLM player integration — character generation and response parsing via Anthropic."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import anthropic

from play_dm.dice import roll as _roll_dice
from play_dm.models import AbilityScores, Character, InventoryItem

log = logging.getLogger("play_dm.llm")
MODEL = "claude-haiku-4-5"

# ── Big Five personality trait helpers ───────────────────────────────────────

_BIG_FIVE_TRAITS = ["openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism"]

_BIG_FIVE_LOW = {
    "openness":          "conventional, prefers routine, skeptical of new ideas",
    "conscientiousness": "impulsive and spontaneous, acts without planning, disorganised",
    "extraversion":      "introverted and reserved, quiet, uncomfortable in the spotlight",
    "agreeableness":     "competitive and blunt, self-interested, suspicious of others",
    "neuroticism":       "emotionally stable and calm, rarely rattled",
}
_BIG_FIVE_HIGH = {
    "openness":          "curious and imaginative, loves new ideas and experiences",
    "conscientiousness": "disciplined and reliable, plans carefully, follows through",
    "extraversion":      "outgoing and energetic, talkative, seeks excitement and company",
    "agreeableness":     "cooperative and empathetic, trusting, eager to help",
    "neuroticism":       "anxious and emotionally reactive, worries easily, moody",
}


def _roll_big_five() -> dict[str, int]:
    """Roll 5 × d100 and return a Big Five score dict."""
    return {trait: _roll_dice("1d100")[0] for trait in _BIG_FIVE_TRAITS}


def _big_five_descriptor(score: int) -> str:
    if score <= 20:   return "very low"
    elif score <= 40: return "low"
    elif score <= 60: return "moderate"
    elif score <= 80: return "high"
    else:             return "very high"


def _big_five_text(score: int, trait: str) -> str:
    level = _big_five_descriptor(score)
    if score <= 50:
        desc = _BIG_FIVE_LOW[trait]
    else:
        desc = _BIG_FIVE_HIGH[trait]
    return f"{score:3d}/100 ({level}) — {desc}"


def _format_big_five_block(big_five: dict[str, int]) -> str:
    lines = []
    for trait in _BIG_FIVE_TRAITS:
        score = big_five.get(trait, 50)
        lines.append(f"  {trait.capitalize():<18} {_big_five_text(score, trait)}")
    return "\n".join(lines)

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
    client: anthropic.Anthropic,
    player_num: int,
    theme: str = "",
    existing_names: list[str] | None = None,
) -> Character:
    """Ask an LLM to create a unique DnD 5e character and return a Character model."""
    big_five = _roll_big_five()
    theme_clause = f" The campaign theme is: {theme}." if theme else ""
    avoid_clause = (
        f" The character's name must be completely different from these already-used names: {', '.join(existing_names)}."
        if existing_names
        else ""
    )
    big_five_clause = (
        f"\n\nThis character's Big Five personality scores (d100 rolls) are:\n{_format_big_five_block(big_five)}\n"
        "Write the personality_traits field to authentically reflect these scores in 1-2 sentences."
    )
    prompt = (
        f"Create a unique level-1 Dungeons & Dragons 5th Edition character for player {player_num}.{theme_clause}{avoid_clause} "
        f"Include appropriate starting equipment and class features. "
        f"For spellcasters, include spell slots, spells_known, and cantrips.{big_five_clause}\n"
        f"Respond ONLY with this exact JSON schema (no extra fields):\n{_CHAR_SCHEMA}"
    )

    log.info("generate_character: calling %s for player %d", MODEL, player_num)
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=_CHAR_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    log.info("generate_character: received response (%d chars)", len(response.content[0].text))
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
        big_five=big_five,
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
    big_five_section = (
        f"\nPERSONALITY (Big Five d100):\n{_format_big_five_block(char.big_five)}"
        if char.big_five
        else ""
    )

    return f"""You are playing {char.name}, a {char.race} {char.character_class} (Level {char.level}) in a Dungeons & Dragons 5th Edition campaign.

CHARACTER SHEET
Name: {char.name} | Race: {char.race} | Class: {char.character_class} (Level {char.level})
Background: {char.background}
Personality: {char.personality_traits}{big_five_section}

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
  "speech": "<REQUIRED. One plain sentence: what do you DO? See rules below.>",
  "action_description": "<one short clause, third-person, e.g. 'asks the bartender about work'>",
  "action_type": "<one of: attack, spell, skill_check, saving_throw, move, item_use, free_action, none>",
  "action_details": {{
    "target": "<name of target, or null>",
    "weapon_or_spell": "<weapon or spell name, or null>",
    "skill": "<skill name for skill_check, e.g. Perception, or null>",
    "ability": "<ability name for saving_throw, e.g. Dexterity, or null>",
    "spell_slot_level": <int level 0-9, 0 if not casting>
  }}
}}

RULES FOR SPEECH:
- Write like a player at a table telling the DM what they do: plain, direct, first-person.
- NO asterisks. NO theatrical dialogue. NO dramatic flair. Just state the action.
  BAD: "I nod to the bartender and take a sip, glancing over at my companions."
  GOOD: "I ask the bartender if he knows of any work or trouble in town."
  BAD: "I scan the room casually while finishing my drink."
  GOOD: "I want to look around the tavern for anyone who seems suspicious — can I roll Perception?"

RULES FOR WHAT TO DO — BE AN ACTIVE PLAYER:
- You are playing a game. Every response must ADVANCE the scene.
- Passive ambient actions (sipping a drink, nodding, glancing around) are NOT valid responses unless you have nothing else to do and you explicitly say so.
- Ask the DM for information: "I ask the innkeeper if there are any rumors about the old mine."
- Investigate things: "I want to get a closer look at that cloaked figure in the corner."
- Talk to NPCs or party members with purpose: "I ask the guard what happened here."
- Use your skills and abilities: "I try to use Insight on the merchant to see if he's lying."
- Make decisions that move things forward: "I suggest we head to the market to find supplies."
- If you don't know what to do, pick the most interesting option available and do it.
- Think: what does {char.name} WANT right now? Do that. Don't wait.

PERSONALITY RULES — your Big Five scores above are binding:
- They shape WHAT you do and HOW you engage, not just how you phrase it.
- Low Extraversion → you hold back and observe before acting; you don't volunteer first.
- High Extraversion → you're the first to speak or act; you seek attention.
- Low Agreeableness → you're skeptical, blunt, put your own goals first.
- High Agreeableness → you help, cooperate, check on others before yourself.
- Low Conscientiousness → you act on impulse; you don't plan ahead.
- High Conscientiousness → you think before acting; you ask clarifying questions first.
- Low Neuroticism → you're calm and steady even in tense situations.
- High Neuroticism → you're on edge; you react to threats or uncertainty quickly.
- Low Openness → you stick to what you know; you're skeptical of unusual ideas.
- High Openness → you're drawn to mysteries, strange things, and new possibilities."""


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

    log.info("get_player_response: calling %s for %s", MODEL, char.name)
    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=_build_system_prompt(char),
        messages=updated_history,
    )
    reply_text = response.content[0].text.strip()
    log.info("get_player_response: %s replied (%d chars, action_type pending parse)", char.name, len(reply_text))

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

    # Ensure speech is never blank — fall back to action_description
    if not parsed.get("speech") and parsed.get("action_description"):
        parsed["speech"] = parsed["action_description"]

    updated_history = updated_history + [{"role": "assistant", "content": reply_text}]
    return parsed, updated_history
