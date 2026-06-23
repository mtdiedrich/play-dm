"""Pydantic models for play-dm."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AbilityScores(BaseModel):
    strength: int
    dexterity: int
    constitution: int
    intelligence: int
    wisdom: int
    charisma: int


class InventoryItem(BaseModel):
    name: str
    quantity: int = 1
    weight: float = 0.0
    description: str = ""


class Character(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    race: str
    character_class: str
    level: int = 1
    background: str
    personality_traits: str = ""
    ability_scores: AbilityScores
    max_hp: int
    current_hp: int
    armor_class: int
    speed: int = 30
    proficiency_bonus: int = 2
    skills: dict[str, bool] = Field(default_factory=dict)
    saving_throw_proficiencies: list[str] = Field(default_factory=list)
    spell_slots: dict[str, int] = Field(default_factory=dict)
    max_spell_slots: dict[str, int] = Field(default_factory=dict)
    spells_known: list[str] = Field(default_factory=list)
    cantrips: list[str] = Field(default_factory=list)
    inventory: list[InventoryItem] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    death_saves: dict[str, int] = Field(default_factory=lambda: {"successes": 0, "failures": 0})
    # Big Five personality trait scores (0–100 each, rolled with d100)
    big_five: dict[str, int] = Field(default_factory=dict)


class Enemy(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    hp: int
    ac: int
    dex: int = 10


class Combatant(BaseModel):
    id: str
    name: str
    initiative: int
    initiative_roll: int
    current_hp: int
    max_hp: int
    armor_class: int
    is_player: bool = False
    conditions: list[str] = Field(default_factory=list)


class CombatState(BaseModel):
    active: bool = False
    round: int = 1
    turn_index: int = 0
    initiative_order: list[Combatant] = Field(default_factory=list)


class LogEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.now)
    entry_type: str
    content: str
    player_id: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


class GameState(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_name: str = "New Campaign"
    session_theme: str = ""
    characters: dict[str, Character] = Field(default_factory=dict)
    player_conversation_histories: dict[str, list[dict]] = Field(default_factory=dict)
    combat: CombatState = Field(default_factory=CombatState)
    log: list[LogEntry] = Field(default_factory=list)
    campaign_notes: str = ""
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
