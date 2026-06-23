# play-dm

A browser-based Dungeons & Dragons 5e DM console where **you** are the Dungeon Master and **Anthropic LLMs** play the characters.

- 2–4 LLM players powered by `claude-3-5-haiku-20241022`
- Characters generated at session start (name, race, class, stats, spells, inventory)
- Full DnD 5e combat: initiative, attack rolls, HP tracking, spell slots, conditions
- Skill checks and saving throws rolled automatically from player actions
- Save / load sessions to JSON files
- Dark fantasy web UI with live game log, character sheets, and combat tracker

---

## Setup

### Prerequisites
- Python ≥ 3.11
- An [Anthropic API key](https://console.anthropic.com/)

### Install

```bash
# Clone or open the project folder
cd play-dm

# Copy the env template and add your key
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY=sk-ant-...

# Install dependencies
pip install -e ".[dev]"
```

> **Using conda / miniconda?** Run `pip install -e ".[dev]"` inside your active environment.

### Run

```bash
uvicorn play_dm.main:app --reload --port 8000
```

Then open [http://localhost:8000](http://localhost:8000) in your browser.

---

## Usage

### Starting a Session
1. Click **New Session** in the header.
2. Choose session name, number of players (2–4), and an optional campaign theme.
3. Click **Generate Characters** — each LLM player receives a unique DnD 5e character.
4. Characters appear in the left sidebar with HP bars, stats, and (expandable) full sheets.

### Narrating
- Type in the bottom text area and press **Send** (or Ctrl+Enter).
- Every LLM player receives your narration and responds with speech + action.
- Dice rolls for attacks, skill checks, and saving throws happen automatically.

### Combat
1. Click **⚔ Start Combat** and add enemies (name, HP, AC, DEX, count).
2. Click **Roll Initiative** — the initiative order appears in the right sidebar.
3. Use **Next Turn ▶** to advance turns. LLM players act automatically on their turn.
4. Use **Dmg / Heal** buttons next to each combatant to apply damage or healing.
5. Click **End Combat** when finished.

### Dice
- Click **🎲 Roll Dice** for a freeform DM roll (any XdY expression + modifier).

### Save / Load
- Click **Save** → enter a filename → game state is written to `saves/<name>.json`.
- Click **Load** → select a save file → session is fully restored.

---

## Running Tests

```bash
pytest
```

All 68 tests cover dice rolling, character utilities (skill checks, HP, spell slots), combat state machine, and save/load round-trips.

---

## Project Structure

```
play-dm/
├── src/play_dm/
│   ├── models.py          # Pydantic data models
│   ├── dice.py            # Dice rolling utilities
│   ├── character.py       # HP, skills, saving throws, spell slots
│   ├── combat.py          # Initiative, turn order, conditions
│   ├── game_state.py      # Save / load / log helpers
│   ├── llm_player.py      # Anthropic character generation + player responses
│   └── main.py            # FastAPI app + WebSocket handler
├── frontend/
│   ├── index.html         # UI shell
│   ├── styles.css         # Dark DnD theme
│   └── app.js             # WebSocket client + UI rendering
├── tests/                 # pytest test suite
├── saves/                 # JSON save files (auto-created)
├── .env.example           # Environment variable template
└── pyproject.toml         # Project metadata + dependencies
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Your Anthropic API key |

---

## Notes

- **Model**: `claude-3-5-haiku-20241022` is used for both character generation and player turns (fast and cost-effective for interactive play).
- **Costs**: Each DM narration sends one API call per player. A 3-player session with 20 narrations ≈ 60 API calls.
- **Out of scope**: automated spell effects, battle maps, levelling up mid-session, multi-user/multi-DM play.
