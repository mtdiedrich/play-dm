# Spec: DnD 5e DM Tool with LLM Players

## Goal
Build a browser-based application where a human DM runs a DnD 5e session and 2–4 players are driven by Anthropic `claude-3-5-haiku-20241022` LLMs.

---

## Current Behavior
N/A — new project.

---

## Target Behavior

### Session Lifecycle
1. DM opens the web UI and starts a new session (choosing 2–4 players and an optional campaign theme).
2. The backend calls Anthropic to generate unique characters for each LLM player (name, race, class, background, stats, inventory, spells).
3. Character sheets are displayed in the left sidebar.
4. DM types narration in the bottom input bar and presses Send.
5. The backend forwards the narration to each LLM player in turn; each player responds with a JSON payload describing their speech and action.
6. If the player's action requires a dice roll, the backend auto-rolls the appropriate dice and applies modifiers; the result is appended to the log.
7. All events stream back to the browser via WebSocket and appear in the scrollable game log in real time.
8. The DM can start combat at any time by entering enemy info. The backend rolls initiative for all combatants, sets turn order, and advances turns on demand.
9. The DM can save the session to a JSON file and reload it later.

### UI Layout
- **Header**: session name, Save / Load / New Game buttons.
- **Left sidebar**: compact character cards (name, race/class, HP bar, AC, conditions, expandable full sheet).
- **Center**: scrollable game log with typed entries (DM narration, player speech, player actions, dice rolls, system messages).
- **Right sidebar**: combat tracker (initiative order list with HP bars, visible only during combat).
- **Bottom bar**: DM text input + Send button; separate "Start Combat" button.

### DnD 5e Systems Supported
| System | Detail |
|---|---|
| Ability scores & modifiers | STR/DEX/CON/INT/WIS/CHA, standard modifier formula |
| Skill checks | All 18 skills; proficiency bonus applied when proficient |
| Saving throws | All 6 ability saves; proficiency applied when indicated |
| Combat | Initiative (d20+DEX mod), attack rolls (d20+prof+STR/DEX), damage by weapon |
| HP tracking | Damage, healing, death saves (three strikes), unconscious state |
| Spell slots | Tracked per level; depleted on cast; restored on long rest |
| Inventory | Item list with quantities |
| Conditions | Poisoned, frightened, prone, restrained, blinded, unconscious, etc. |

---

## Files to Create

| File | Purpose |
|---|---|
| `pyproject.toml` | Project metadata, dependencies (fastapi, uvicorn, anthropic, pydantic, python-dotenv, websockets) |
| `src/play_dm/__init__.py` | Package marker |
| `src/play_dm/models.py` | Pydantic models: `AbilityScores`, `InventoryItem`, `Character`, `Combatant`, `CombatState`, `LogEntry`, `GameState` |
| `src/play_dm/dice.py` | `roll(expr)`, `roll_with_modifier(expr, mod)`, `advantage_roll()`, `disadvantage_roll()`, `ability_modifier(score)` |
| `src/play_dm/character.py` | `skill_bonus(char, skill)`, `saving_throw_bonus(char, ability)`, `passive_perception(char)`, `apply_damage(char, amt)`, `apply_healing(char, amt)`, `consume_spell_slot(char, level)`, `long_rest(char)` |
| `src/play_dm/combat.py` | `roll_initiative_order(characters, enemies)`, `current_combatant(state)`, `advance_turn(state)`, `apply_combatant_damage(state, id, amt)`, `add_condition(state, id, cond)`, `remove_condition(state, id, cond)` |
| `src/play_dm/game_state.py` | `save_state(state, path)`, `load_state(path)`, `add_log_entry(state, …)` |
| `src/play_dm/llm_player.py` | `generate_character(client, player_num, theme)`, `get_player_response(client, char, history, message)` |
| `src/play_dm/main.py` | FastAPI app: `GET /`, `GET /saves`, WebSocket `/ws` — handles all game events |
| `frontend/index.html` | Single-page shell with sidebar structure |
| `frontend/styles.css` | Dark DnD theme (CSS variables, sidebar layout, log styling, combat tracker) |
| `frontend/app.js` | WebSocket client; renders log entries, character cards, combat tracker |
| `tests/test_dice.py` | Unit tests for all dice functions |
| `tests/test_character.py` | Unit tests for character utility functions |
| `tests/test_combat.py` | Unit tests for combat state machine |
| `tests/test_game_state.py` | Unit tests for save/load and log helpers |
| `.env.example` | `ANTHROPIC_API_KEY=your_key_here` |
| `saves/.gitkeep` | Empty placeholder so saves/ is tracked |
| `README.md` | Setup and usage instructions |

---

## Step-by-Step Implementation Instructions

### 1. pyproject.toml
Create with `[project]` metadata. Dependencies:
- `fastapi>=0.111`
- `uvicorn[standard]>=0.30`
- `anthropic>=0.30`
- `pydantic>=2.7`
- `python-dotenv>=1.0`
- `websockets>=12.0`

Dev dependencies: `pytest>=8`, `pytest-asyncio>=0.23`.

### 2. models.py
Define `AbilityScores`, `InventoryItem`, `Character`, `Enemy`, `Combatant`, `CombatState`, `LogEntry`, `GameState` as Pydantic v2 `BaseModel`s. Use `Field(default_factory=...)` for mutable defaults.

### 3. dice.py
- Parse `XdY` or `dY` strings with regex.
- `roll(expr)` → `(total, [individual_rolls])`.
- `roll_with_modifier(expr, mod)` → `(total, rolls, mod)`.
- `advantage_roll()` → `(result, roll1, roll2)` taking the max.
- `disadvantage_roll()` → `(result, roll1, roll2)` taking the min.
- `ability_modifier(score)` → `(score - 10) // 2`.

### 4. character.py
- `skill_bonus`: look up the skill's governing ability, compute mod, add proficiency if proficient.
- `saving_throw_bonus`: compute ability mod, add proficiency if in `saving_throw_proficiencies`.
- `apply_damage`: reduce `current_hp`; clamp at 0; set `unconscious` condition if <= 0.
- `apply_healing`: increase `current_hp`; clamp at `max_hp`; clear `unconscious` condition if was 0.
- `consume_spell_slot(char, level)`: decrement `spell_slots[str(level)]`; raise `ValueError` if none remain.
- `long_rest`: restore HP to max, restore all spell slots, clear most conditions.

### 5. combat.py
- `roll_initiative_order`: for each character and enemy, roll `d20 + DEX mod`; sort descending; return `CombatState` with `active=True`.
- `current_combatant`: return the combatant at `state.turn_index`.
- `advance_turn`: increment `turn_index`; wrap around; increment `round` when wrapping.
- `apply_combatant_damage`, `add_condition`, `remove_condition`: mutate combatant in `initiative_order`.

### 6. game_state.py
- `save_state(state, path)`: write `state.model_dump_json()` to file.
- `load_state(path)`: read file, return `GameState.model_validate_json(data)`.
- `add_log_entry`: append `LogEntry` to `state.log` and update `state.updated_at`.

### 7. llm_player.py
**`generate_character(client, player_num, theme)`**:
- Send a single Anthropic message asking for a DnD 5e character as JSON.
- Parse the JSON response into a `Character` model.
- System prompt instructs the LLM to return valid JSON only.

**`get_player_response(client, char, history, dm_message)`**:
- Append the DM message to conversation history.
- Send the conversation to Anthropic with a character-specific system prompt.
- Expect a JSON response with keys: `speech`, `action_description`, `action_type` (enum), `action_details`.
- Parse and return the dict + updated history.

**Player system prompt** includes the character sheet and rules for JSON-only responses.

**Action types**: `attack`, `spell`, `skill_check`, `saving_throw`, `move`, `item_use`, `free_action`, `none`.

### 8. main.py (FastAPI)
- Mount `frontend/` as static files at `/static`. Serve `frontend/index.html` at `GET /`.
- `GET /saves` → list JSON files in `saves/`.
- `WebSocket /ws` → single connection; receive JSON commands, dispatch to handlers, stream responses back.

**WebSocket commands (client → server)**:

| type | payload | action |
|---|---|---|
| `new_session` | `player_count`, `theme` | Generate characters, update state |
| `dm_narrate` | `text` | Send to all LLM players sequentially, roll dice as needed |
| `start_combat` | `enemies: [{name, hp, ac, count}]` | Roll initiative, update state |
| `next_turn` | — | Advance combat turn |
| `apply_damage` | `target_id`, `damage` | Apply damage to combatant |
| `apply_healing` | `target_id`, `healing` | Heal target |
| `end_combat` | — | Clear combat state |
| `save_game` | `filename` | Save state to file |
| `load_game` | `filename` | Load state from file |

**WebSocket events (server → client)**:

| type | payload |
|---|---|
| `log_entry` | `LogEntry` dict |
| `state_update` | full `GameState` dict (characters, combat, etc.) |
| `dice_roll` | dice expr, rolls, total, modifier, context, character_name |
| `error` | message string |

### 9. Frontend (index.html / styles.css / app.js)
- **index.html**: three-column layout (left sidebar, center log, right combat panel), bottom input bar.
- **styles.css**: dark theme (`#1a1a2e` background, `#c9a84c` gold accent); log entry types styled differently; HP bars as `<progress>` elements; responsive for wide screens.
- **app.js**: open WebSocket on load; send commands on form submit; render incoming events by type; auto-scroll log; update character cards and combat tracker on `state_update`.

---

## Test Plan

### test_dice.py
| Test | Expected |
|---|---|
| `roll("1d6")` total is 1–6 | Pass |
| `roll("2d6")` total is 2–12 | Pass |
| `roll("d20")` total is 1–20 | Pass |
| `ability_modifier(10)` = 0 | Pass |
| `ability_modifier(16)` = 3 | Pass |
| `ability_modifier(8)` = −1 | Pass |
| `advantage_roll()` result equals max of the two rolls | Pass |
| `disadvantage_roll()` result equals min of the two rolls | Pass |
| `roll("1d20")` called 100x, all in [1,20] | Pass |

### test_character.py
| Test | Expected |
|---|---|
| `skill_bonus` for proficient skill adds proficiency_bonus | Correct total |
| `skill_bonus` for non-proficient skill returns only ability mod | Correct total |
| `apply_damage` reduces current_hp | HP decremented |
| `apply_damage` beyond 0 clamps and sets unconscious | HP == 0, "unconscious" in conditions |
| `apply_healing` restores HP; clears unconscious | HP increased, condition cleared |
| `apply_healing` beyond max_hp clamps | HP == max_hp |
| `consume_spell_slot` decrements slot count | Slot count decremented |
| `consume_spell_slot` with no slots raises ValueError | ValueError raised |
| `long_rest` restores HP and spell slots | Full restore |

### test_combat.py
| Test | Expected |
|---|---|
| `roll_initiative_order` returns active `CombatState` | `active == True` |
| Initiative order is sorted descending | Correct order |
| `advance_turn` increments `turn_index` | +1 |
| `advance_turn` wraps at end of list | index back to 0, round incremented |
| `apply_combatant_damage` reduces HP | HP decremented |
| `add_condition` adds condition to combatant | Condition present |
| `remove_condition` removes it | Condition absent |

### test_game_state.py
| Test | Expected |
|---|---|
| `save_state` + `load_state` round-trip preserves data | Loaded == original |
| `add_log_entry` appends entry to log | len(log) increases |
| `load_state` on missing file raises `FileNotFoundError` | Error raised |

---

## Out of Scope
- Multi-DM or multi-user sessions (single DM, single WebSocket connection)
- Full spell database / spell effect automation
- Miniature battle maps or grid systems
- Player-vs-player damage (DM applies damage manually to any target)
- Voice input/output
- Character leveling up mid-session
- Multiple simultaneous save slots shown in the UI (files are listed but management is manual)
