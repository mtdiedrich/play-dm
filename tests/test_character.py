import pytest
from play_dm.models import AbilityScores, Character, InventoryItem
from play_dm.character import (
    skill_bonus,
    saving_throw_bonus,
    passive_perception,
    apply_damage,
    apply_healing,
    consume_spell_slot,
    long_rest,
)


def make_character(**overrides) -> Character:
    defaults = dict(
        id="test-player-1",
        name="Thalia",
        race="Elf",
        character_class="Wizard",
        level=3,
        background="Sage",
        personality_traits="Curious and methodical.",
        ability_scores=AbilityScores(
            strength=8,
            dexterity=14,
            constitution=12,
            intelligence=18,
            wisdom=14,
            charisma=10,
        ),
        max_hp=20,
        current_hp=20,
        armor_class=12,
        speed=30,
        proficiency_bonus=2,
        skills={
            "Arcana": True,
            "History": True,
            "Perception": False,
            "Athletics": False,
        },
        saving_throw_proficiencies=["Intelligence", "Wisdom"],
        spell_slots={"1": 4, "2": 2},
        max_spell_slots={"1": 4, "2": 2},
        spells_known=["Magic Missile", "Shield"],
        cantrips=["Mage Hand", "Fire Bolt"],
        inventory=[InventoryItem(name="Spellbook", quantity=1)],
        conditions=[],
    )
    defaults.update(overrides)
    return Character(**defaults)


class TestSkillBonus:
    def test_proficient_skill_adds_proficiency(self):
        char = make_character()
        # Arcana is INT-based (mod +4) + proficiency 2 = 6
        assert skill_bonus(char, "Arcana") == 6

    def test_non_proficient_skill_only_mod(self):
        char = make_character()
        # Perception is WIS-based (mod +2), not proficient
        assert skill_bonus(char, "Perception") == 2

    def test_athletics_strength_non_proficient(self):
        char = make_character()
        # Athletics is STR-based (mod -1), not proficient
        assert skill_bonus(char, "Athletics") == -1


class TestSavingThrowBonus:
    def test_proficient_save_adds_proficiency(self):
        char = make_character()
        # INT save: mod +4 + prof 2 = 6
        assert saving_throw_bonus(char, "Intelligence") == 6

    def test_non_proficient_save_only_mod(self):
        char = make_character()
        # STR save: mod -1, not proficient
        assert saving_throw_bonus(char, "Strength") == -1


class TestPassivePerception:
    def test_passive_perception(self):
        char = make_character()
        # 10 + WIS mod(+2) + 0 (not proficient in Perception) = 12
        assert passive_perception(char) == 12


class TestApplyDamage:
    def test_reduces_hp(self):
        char = make_character()
        result = apply_damage(char, 5)
        assert result.current_hp == 15

    def test_clamps_at_zero(self):
        char = make_character()
        result = apply_damage(char, 999)
        assert result.current_hp == 0

    def test_sets_unconscious_condition_at_zero(self):
        char = make_character()
        result = apply_damage(char, 999)
        assert "unconscious" in result.conditions

    def test_does_not_set_unconscious_if_hp_above_zero(self):
        char = make_character()
        result = apply_damage(char, 5)
        assert "unconscious" not in result.conditions


class TestApplyHealing:
    def test_restores_hp(self):
        char = make_character(current_hp=10)
        result = apply_healing(char, 5)
        assert result.current_hp == 15

    def test_clamps_at_max(self):
        char = make_character(current_hp=18)
        result = apply_healing(char, 50)
        assert result.current_hp == char.max_hp

    def test_clears_unconscious_condition(self):
        char = make_character(current_hp=0, conditions=["unconscious"])
        result = apply_healing(char, 1)
        assert "unconscious" not in result.conditions

    def test_does_not_add_hp_when_already_full(self):
        char = make_character()
        result = apply_healing(char, 10)
        assert result.current_hp == char.max_hp


class TestConsumeSpellSlot:
    def test_decrements_slot(self):
        char = make_character()
        result = consume_spell_slot(char, 1)
        assert result.spell_slots["1"] == 3

    def test_raises_when_no_slots(self):
        char = make_character(spell_slots={"1": 0, "2": 0})
        with pytest.raises(ValueError):
            consume_spell_slot(char, 1)


class TestLongRest:
    def test_restores_hp(self):
        char = make_character(current_hp=5)
        result = long_rest(char)
        assert result.current_hp == result.max_hp

    def test_restores_spell_slots(self):
        char = make_character(spell_slots={"1": 0, "2": 0})
        result = long_rest(char)
        assert result.spell_slots == result.max_spell_slots

    def test_clears_conditions(self):
        char = make_character(conditions=["poisoned", "frightened"])
        result = long_rest(char)
        assert result.conditions == []
