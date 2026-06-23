import json
import pytest
import tempfile
import os
from datetime import datetime
from play_dm.models import GameState, Character, AbilityScores, LogEntry
from play_dm.game_state import save_state, load_state, add_log_entry


def make_empty_state() -> GameState:
    return GameState(session_name="Test Campaign")


class TestSaveLoad:
    def test_round_trip_preserves_session_name(self, tmp_path):
        state = make_empty_state()
        path = tmp_path / "test_save.json"
        save_state(state, str(path))
        loaded = load_state(str(path))
        assert loaded.session_name == state.session_name

    def test_round_trip_preserves_session_id(self, tmp_path):
        state = make_empty_state()
        path = tmp_path / "test_save.json"
        save_state(state, str(path))
        loaded = load_state(str(path))
        assert loaded.session_id == state.session_id

    def test_round_trip_with_log_entries(self, tmp_path):
        state = make_empty_state()
        state = add_log_entry(state, "dm_narration", "You enter a dark cave.")
        path = tmp_path / "test_save.json"
        save_state(state, str(path))
        loaded = load_state(str(path))
        assert len(loaded.log) == 1
        assert loaded.log[0].content == "You enter a dark cave."

    def test_save_creates_file(self, tmp_path):
        state = make_empty_state()
        path = tmp_path / "test_save.json"
        save_state(state, str(path))
        assert path.exists()

    def test_load_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_state(str(tmp_path / "nonexistent.json"))

    def test_saved_file_is_valid_json(self, tmp_path):
        state = make_empty_state()
        path = tmp_path / "test_save.json"
        save_state(state, str(path))
        with open(path) as f:
            data = json.load(f)
        assert "session_id" in data
        assert "session_name" in data


class TestAddLogEntry:
    def test_appends_entry(self):
        state = make_empty_state()
        state = add_log_entry(state, "dm_narration", "Welcome to the dungeon.")
        assert len(state.log) == 1

    def test_entry_has_correct_type(self):
        state = make_empty_state()
        state = add_log_entry(state, "player_speech", "I attack the goblin!")
        assert state.log[0].entry_type == "player_speech"

    def test_entry_has_correct_content(self):
        state = make_empty_state()
        state = add_log_entry(state, "system", "Combat started.")
        assert state.log[0].content == "Combat started."

    def test_multiple_entries_ordered(self):
        state = make_empty_state()
        state = add_log_entry(state, "dm_narration", "First message.")
        state = add_log_entry(state, "dm_narration", "Second message.")
        assert state.log[0].content == "First message."
        assert state.log[1].content == "Second message."

    def test_entry_with_player_id(self):
        state = make_empty_state()
        state = add_log_entry(state, "player_speech", "Hello!", player_id="p1")
        assert state.log[0].player_id == "p1"

    def test_entry_with_metadata(self):
        state = make_empty_state()
        state = add_log_entry(state, "dice_roll", "Rolled 15", metadata={"dice": "1d20", "result": 15})
        assert state.log[0].metadata["dice"] == "1d20"
