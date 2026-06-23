"""Combat system."""
from __future__ import annotations

import random
import uuid

from play_dm.dice import ability_modifier
from play_dm.models import Character, Combatant, CombatState


def roll_initiative_order(
    characters: list[Character], enemies: list[dict]
) -> CombatState:
    """Roll initiative for all combatants and return an active CombatState."""
    combatants: list[Combatant] = []

    for char in characters:
        dex_mod = ability_modifier(char.ability_scores.dexterity)
        roll = random.randint(1, 20)
        initiative = roll + dex_mod
        combatants.append(
            Combatant(
                id=char.id,
                name=char.name,
                initiative=initiative,
                initiative_roll=roll,
                current_hp=char.current_hp,
                max_hp=char.max_hp,
                armor_class=char.armor_class,
                is_player=True,
                conditions=list(char.conditions),
            )
        )

    for enemy in enemies:
        dex_mod = ability_modifier(enemy.get("dex", 10))
        roll = random.randint(1, 20)
        initiative = roll + dex_mod
        combatants.append(
            Combatant(
                id=enemy.get("id", str(uuid.uuid4())),
                name=enemy["name"],
                initiative=initiative,
                initiative_roll=roll,
                current_hp=enemy["hp"],
                max_hp=enemy["hp"],
                armor_class=enemy["ac"],
                is_player=False,
            )
        )

    combatants.sort(key=lambda c: c.initiative, reverse=True)

    return CombatState(
        active=True,
        round=1,
        turn_index=0,
        initiative_order=combatants,
    )


def current_combatant(state: CombatState) -> Combatant:
    """Return the combatant whose turn it currently is."""
    return state.initiative_order[state.turn_index]


def advance_turn(state: CombatState) -> CombatState:
    """Advance to the next combatant's turn, wrapping to a new round when needed."""
    updated = state.model_copy(deep=True)
    next_index = updated.turn_index + 1
    if next_index >= len(updated.initiative_order):
        updated.turn_index = 0
        updated.round += 1
    else:
        updated.turn_index = next_index
    return updated


def apply_combatant_damage(
    state: CombatState, combatant_id: str, amount: int
) -> CombatState:
    """Apply damage to a combatant by id."""
    updated = state.model_copy(deep=True)
    for combatant in updated.initiative_order:
        if combatant.id == combatant_id:
            combatant.current_hp = max(0, combatant.current_hp - amount)
            break
    return updated


def add_condition(
    state: CombatState, combatant_id: str, condition: str
) -> CombatState:
    """Add a condition to a combatant."""
    updated = state.model_copy(deep=True)
    for combatant in updated.initiative_order:
        if combatant.id == combatant_id:
            if condition not in combatant.conditions:
                combatant.conditions.append(condition)
            break
    return updated


def remove_condition(
    state: CombatState, combatant_id: str, condition: str
) -> CombatState:
    """Remove a condition from a combatant (no-op if not present)."""
    updated = state.model_copy(deep=True)
    for combatant in updated.initiative_order:
        if combatant.id == combatant_id:
            if condition in combatant.conditions:
                combatant.conditions.remove(condition)
            break
    return updated
