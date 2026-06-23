import pytest
from play_dm.dice import roll, roll_with_modifier, advantage_roll, disadvantage_roll, ability_modifier


class TestRoll:
    def test_d6_range(self):
        total, rolls = roll("1d6")
        assert 1 <= total <= 6
        assert len(rolls) == 1

    def test_2d6_range(self):
        total, rolls = roll("2d6")
        assert 2 <= total <= 12
        assert len(rolls) == 2

    def test_d20_range(self):
        total, rolls = roll("d20")
        assert 1 <= total <= 20
        assert len(rolls) == 1

    def test_4d8_count(self):
        total, rolls = roll("4d8")
        assert len(rolls) == 4
        assert total == sum(rolls)

    def test_d20_100_samples(self):
        for _ in range(100):
            total, _ = roll("1d20")
            assert 1 <= total <= 20

    def test_invalid_dice_raises(self):
        with pytest.raises(ValueError):
            roll("not-a-dice")

    def test_zero_dice_raises(self):
        with pytest.raises(ValueError):
            roll("0d6")


class TestRollWithModifier:
    def test_adds_positive_modifier(self):
        total, rolls, mod = roll_with_modifier("1d20", 5)
        assert total == rolls[0] + 5
        assert mod == 5

    def test_adds_negative_modifier(self):
        total, rolls, mod = roll_with_modifier("1d20", -2)
        assert total == rolls[0] - 2
        assert mod == -2

    def test_zero_modifier(self):
        total, rolls, mod = roll_with_modifier("1d6", 0)
        assert total == rolls[0]


class TestAdvantageDisadvantage:
    def test_advantage_takes_max(self):
        result, roll1, roll2 = advantage_roll()
        assert result == max(roll1, roll2)
        assert 1 <= result <= 20

    def test_disadvantage_takes_min(self):
        result, roll1, roll2 = disadvantage_roll()
        assert result == min(roll1, roll2)
        assert 1 <= result <= 20

    def test_advantage_100_samples(self):
        for _ in range(100):
            result, r1, r2 = advantage_roll()
            assert result == max(r1, r2)

    def test_disadvantage_100_samples(self):
        for _ in range(100):
            result, r1, r2 = disadvantage_roll()
            assert result == min(r1, r2)


class TestAbilityModifier:
    def test_ten_is_zero(self):
        assert ability_modifier(10) == 0

    def test_eleven_is_zero(self):
        assert ability_modifier(11) == 0

    def test_twelve_is_one(self):
        assert ability_modifier(12) == 1

    def test_sixteen_is_three(self):
        assert ability_modifier(16) == 3

    def test_eight_is_minus_one(self):
        assert ability_modifier(8) == -1

    def test_six_is_minus_two(self):
        assert ability_modifier(6) == -2

    def test_twenty_is_five(self):
        assert ability_modifier(20) == 5

    def test_one_is_minus_five(self):
        assert ability_modifier(1) == -5
