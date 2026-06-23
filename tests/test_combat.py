import pytest
from play_dm.models import AbilityScores, Character, CombatState, Combatant
from play_dm.combat import (
    roll_initiative_order,
    current_combatant,
    advance_turn,
    apply_combatant_damage,
    add_condition,
    remove_condition,
)


def make_character(id: str, name: str, dex: int = 14, hp: int = 20, ac: int = 14) -> Character:
    return Character(
        id=id,
        name=name,
        race="Human",
        character_class="Fighter",
        level=1,
        background="Soldier",
        personality_traits="Brave.",
        ability_scores=AbilityScores(
            strength=16, dexterity=dex, constitution=14,
            intelligence=10, wisdom=12, charisma=8,
        ),
        max_hp=hp,
        current_hp=hp,
        armor_class=ac,
        speed=30,
        proficiency_bonus=2,
        skills={},
        saving_throw_proficiencies=[],
    )


def make_enemy(id: str, name: str, hp: int = 10, ac: int = 12, dex: int = 10) -> dict:
    return {"id": id, "name": name, "hp": hp, "ac": ac, "dex": dex}


class TestRollInitiativeOrder:
    def test_returns_active_state(self):
        chars = [make_character("p1", "Alice"), make_character("p2", "Bob")]
        enemies = [make_enemy("e1", "Goblin")]
        state = roll_initiative_order(chars, enemies)
        assert state.active is True

    def test_contains_all_combatants(self):
        chars = [make_character("p1", "Alice"), make_character("p2", "Bob")]
        enemies = [make_enemy("e1", "Goblin"), make_enemy("e2", "Goblin 2")]
        state = roll_initiative_order(chars, enemies)
        assert len(state.initiative_order) == 4

    def test_order_is_descending_by_initiative(self):
        chars = [make_character("p1", "Alice")]
        enemies = [make_enemy("e1", "Goblin")]
        state = roll_initiative_order(chars, enemies)
        initiatives = [c.initiative for c in state.initiative_order]
        assert initiatives == sorted(initiatives, reverse=True)

    def test_round_starts_at_one(self):
        chars = [make_character("p1", "Alice")]
        enemies = [make_enemy("e1", "Goblin")]
        state = roll_initiative_order(chars, enemies)
        assert state.round == 1

    def test_turn_index_starts_at_zero(self):
        chars = [make_character("p1", "Alice")]
        enemies = [make_enemy("e1", "Goblin")]
        state = roll_initiative_order(chars, enemies)
        assert state.turn_index == 0

    def test_players_marked_as_players(self):
        chars = [make_character("p1", "Alice")]
        enemies = [make_enemy("e1", "Goblin")]
        state = roll_initiative_order(chars, enemies)
        player_combatants = [c for c in state.initiative_order if c.is_player]
        assert len(player_combatants) == 1
        assert player_combatants[0].name == "Alice"


class TestCurrentCombatant:
    def test_returns_first_combatant(self):
        chars = [make_character("p1", "Alice")]
        enemies = [make_enemy("e1", "Goblin")]
        state = roll_initiative_order(chars, enemies)
        combatant = current_combatant(state)
        assert combatant is state.initiative_order[0]


class TestAdvanceTurn:
    def test_increments_turn_index(self):
        chars = [make_character("p1", "Alice"), make_character("p2", "Bob")]
        enemies = [make_enemy("e1", "Goblin")]
        state = roll_initiative_order(chars, enemies)
        state = advance_turn(state)
        assert state.turn_index == 1

    def test_wraps_turn_index(self):
        chars = [make_character("p1", "Alice")]
        enemies = [make_enemy("e1", "Goblin")]
        state = roll_initiative_order(chars, enemies)
        # 2 combatants; advance twice to wrap
        state = advance_turn(state)
        state = advance_turn(state)
        assert state.turn_index == 0

    def test_increments_round_on_wrap(self):
        chars = [make_character("p1", "Alice")]
        enemies = [make_enemy("e1", "Goblin")]
        state = roll_initiative_order(chars, enemies)
        # 2 combatants; advance twice to complete a round
        state = advance_turn(state)
        state = advance_turn(state)
        assert state.round == 2


class TestApplyCombatantDamage:
    def test_reduces_hp(self):
        chars = [make_character("p1", "Alice", hp=20)]
        enemies = []
        state = roll_initiative_order(chars, enemies)
        combatant_id = state.initiative_order[0].id
        state = apply_combatant_damage(state, combatant_id, 5)
        assert state.initiative_order[0].current_hp == 15

    def test_clamps_at_zero(self):
        chars = [make_character("p1", "Alice", hp=10)]
        enemies = []
        state = roll_initiative_order(chars, enemies)
        combatant_id = state.initiative_order[0].id
        state = apply_combatant_damage(state, combatant_id, 999)
        assert state.initiative_order[0].current_hp == 0


class TestConditions:
    def _get_state(self):
        chars = [make_character("p1", "Alice")]
        enemies = []
        return roll_initiative_order(chars, enemies)

    def test_add_condition(self):
        state = self._get_state()
        cid = state.initiative_order[0].id
        state = add_condition(state, cid, "poisoned")
        assert "poisoned" in state.initiative_order[0].conditions

    def test_remove_condition(self):
        state = self._get_state()
        cid = state.initiative_order[0].id
        state = add_condition(state, cid, "poisoned")
        state = remove_condition(state, cid, "poisoned")
        assert "poisoned" not in state.initiative_order[0].conditions

    def test_remove_nonexistent_condition_is_noop(self):
        state = self._get_state()
        cid = state.initiative_order[0].id
        state = remove_condition(state, cid, "blinded")  # was never added
        assert "blinded" not in state.initiative_order[0].conditions
