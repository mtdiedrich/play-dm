"""Game state management — save, load, and log helpers."""
from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from play_dm.models import GameState, LogEntry


def save_state(state: GameState, path: str) -> None:
    """Persist game state to a JSON file."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(state.model_dump_json(indent=2))


def load_state(path: str) -> GameState:
    """Load game state from a JSON file. Raises FileNotFoundError if missing."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Save file not found: {path!r}")
    with open(path, "r", encoding="utf-8") as f:
        return GameState.model_validate_json(f.read())


def add_log_entry(
    state: GameState,
    entry_type: str,
    content: str,
    player_id: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> GameState:
    """Append a log entry and update the session timestamp."""
    updated = state.model_copy(deep=True)
    entry = LogEntry(
        entry_type=entry_type,
        content=content,
        player_id=player_id,
        metadata=metadata or {},
    )
    updated.log.append(entry)
    updated.updated_at = datetime.now()
    return updated
