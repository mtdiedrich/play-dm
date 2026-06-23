"""FastAPI application — DnD 5e DM tool with LLM players."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Any

log = logging.getLogger("play_dm")

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from play_dm.character import (
    apply_damage,
    apply_healing,
    consume_spell_slot,
    skill_bonus,
    saving_throw_bonus,
)
from play_dm.combat import (
    add_condition,
    advance_turn,
    apply_combatant_damage,
    current_combatant,
    remove_condition,
    roll_initiative_order,
)
from play_dm.dice import roll, roll_with_modifier, ability_modifier
from play_dm.game_state import add_log_entry, load_state, save_state
from play_dm.llm_player import generate_character, get_player_response
from play_dm.models import GameState

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
SAVES_DIR = BASE_DIR / "saves"
SAVES_DIR.mkdir(exist_ok=True)

app = FastAPI(title="play-dm")


@app.on_event("startup")
async def _setup_logging() -> None:
    """Configure play_dm logging after uvicorn has fully set up its own handlers."""
    logger = logging.getLogger("play_dm")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    # Replace any stale handlers (handles hot-reload)
    for h in list(logger.handlers):
        logger.removeHandler(h)
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S"
    ))
    logger.addHandler(handler)
    logger.info("play_dm logger ready")


if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/saves")
async def list_saves() -> JSONResponse:
    files = [p.stem for p in SAVES_DIR.glob("*.json")]
    return JSONResponse({"saves": sorted(files)})


# ---------------------------------------------------------------------------
# WebSocket handler
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    log.info("WebSocket connected")

    # Each connection gets its own game state and Anthropic client
    state = GameState()
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    # max_retries=4 so transient Anthropic 500s are retried automatically
    client = anthropic.Anthropic(api_key=api_key, max_retries=4) if api_key else None
    # Tracks the most recent speech from each player so siblings get party context
    party_context: dict[str, str] = {}

    async def send(msg: dict[str, Any]) -> None:
        await ws.send_text(json.dumps(msg))

    async def send_log(entry_type: str, content: str, player_id: str | None = None, metadata: dict | None = None) -> None:
        nonlocal state
        state = add_log_entry(state, entry_type, content, player_id=player_id, metadata=metadata or {})
        await send({"type": "log_entry", "entry": state.log[-1].model_dump(mode="json")})

    async def send_state() -> None:
        await send({"type": "state_update", "state": state.model_dump(mode="json")})

    async def handle_player_response(char: Any, player_id: str, dm_message: str) -> None:
        """Call LLM for one player, log their response, auto-roll dice. Updates party_context."""
        nonlocal state
        # Prepend recent actions from all other players so this LLM knows what its allies did
        others = [(pid, v) for pid, v in party_context.items() if pid != player_id]
        augmented = dm_message
        if others:
            lines = " | ".join(v for _, v in others)
            augmented = f"[Party context — your allies just did: {lines}]\n\n{dm_message}"

        history = state.player_conversation_histories.get(player_id, [])
        parsed, new_history = get_player_response(client, char, history, augmented)
        state.player_conversation_histories[player_id] = new_history
        log.info("%s responded (action_type=%s)", char.name, parsed.get("action_type"))

        if parsed.get("speech"):
            party_context[player_id] = f'{char.name}: "{parsed["speech"]}"'

        if parsed.get("speech"):
            await send_log("player_speech", f'**{char.name}**: "{parsed["speech"]}"', player_id=player_id)

        if parsed.get("action_description"):
            await send_log(
                "player_action",
                f"{char.name} {parsed['action_description']}",
                player_id=player_id,
                metadata={"action_type": parsed.get("action_type", "none")},
            )

        action_type = parsed.get("action_type", "none")
        details = parsed.get("action_details", {})

        if action_type == "attack":
            weapon = details.get("weapon_or_spell") or "weapon"
            atk_mod = ability_modifier(char.ability_scores.strength)
            total, rolls, mod = roll_with_modifier("1d20", atk_mod + char.proficiency_bonus)
            await send({"type": "dice_roll", "dice": "1d20", "rolls": rolls,
                        "modifier": atk_mod + char.proficiency_bonus, "total": total,
                        "context": f"{char.name} attacks with {weapon}",
                        "character_name": char.name, "player_id": player_id})
            await send_log("dice_roll",
                           f"{char.name} rolls to attack with {weapon}: {total} (d20={rolls[0]}, mod={mod:+})",
                           player_id=player_id,
                           metadata={"dice": "1d20", "total": total, "rolls": rolls, "modifier": mod})

        elif action_type == "skill_check":
            skill = details.get("skill") or "Perception"
            try:
                bonus = skill_bonus(char, skill)
            except ValueError:
                bonus = 0
            total, rolls, mod = roll_with_modifier("1d20", bonus)
            await send({"type": "dice_roll", "dice": "1d20", "rolls": rolls, "modifier": bonus,
                        "total": total, "context": f"{char.name} {skill} check",
                        "character_name": char.name, "player_id": player_id})
            await send_log("dice_roll",
                           f"{char.name} rolls {skill} check: {total} (d20={rolls[0]}, mod={bonus:+})",
                           player_id=player_id,
                           metadata={"dice": "1d20", "total": total, "skill": skill})

        elif action_type == "saving_throw":
            ability = details.get("ability") or "Dexterity"
            try:
                bonus = saving_throw_bonus(char, ability)
            except ValueError:
                bonus = 0
            total, rolls, mod = roll_with_modifier("1d20", bonus)
            await send({"type": "dice_roll", "dice": "1d20", "rolls": rolls, "modifier": bonus,
                        "total": total, "context": f"{char.name} {ability} saving throw",
                        "character_name": char.name, "player_id": player_id})
            await send_log("dice_roll",
                           f"{char.name} rolls {ability} saving throw: {total} (d20={rolls[0]}, mod={bonus:+})",
                           player_id=player_id,
                           metadata={"dice": "1d20", "total": total, "ability": ability})

        elif action_type == "spell":
            spell_name = details.get("weapon_or_spell") or "spell"
            slot_level = int(details.get("spell_slot_level") or 0)
            if slot_level > 0:
                try:
                    state.characters[player_id] = consume_spell_slot(char, slot_level)
                    await send_log("system",
                                   f"{char.name} expends a level-{slot_level} spell slot for {spell_name}.",
                                   player_id=player_id)
                except ValueError as exc:
                    await send_log("system", f"{char.name}: {exc}", player_id=player_id)

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await send({"type": "error", "message": "Invalid JSON."})
                continue

            cmd = msg.get("type", "")
            log.info("WS cmd: %s", cmd)

            # ------------------------------------------------------------------
            if cmd == "new_session":
                if not client:
                    await send({"type": "error", "message": "ANTHROPIC_API_KEY not set."})
                    continue

                player_count = max(2, min(4, int(msg.get("player_count", 3))))
                theme = str(msg.get("theme", ""))
                state = GameState(
                    session_name=msg.get("session_name", "New Campaign"),
                    session_theme=theme,
                )

                await send_log("system", f"Starting new session with {player_count} LLM players…")

                for i in range(1, player_count + 1):
                    if i > 1:
                        await asyncio.sleep(1)  # brief pause between calls to avoid rate limits
                    await send_log("system", f"Generating character for Player {i}…")
                    existing_names = [c.name for c in state.characters.values()]
                    try:
                        char = generate_character(client, i, theme, existing_names=existing_names)
                        state.characters[char.id] = char
                        state.player_conversation_histories[char.id] = []
                        log.info("Generated character: %s the %s %s", char.name, char.race, char.character_class)
                        await send_log(
                            "system",
                            f"Player {i}: {char.name} the {char.race} {char.character_class} (HP {char.max_hp}, AC {char.armor_class})",
                        )
                        await send_state()  # Show column immediately — don't wait for all chars
                    except Exception as exc:
                        log.error("Character gen failed for player %d: %s", i, exc)
                        await send({"type": "error", "message": f"Character gen failed for player {i}: {exc}"})

                # Final state_update in case any character failed and partial state needs sync
                await send_state()

            # ------------------------------------------------------------------
            elif cmd == "dm_narrate":
                if not client:
                    await send({"type": "error", "message": "ANTHROPIC_API_KEY not set."})
                    continue

                text = str(msg.get("text", "")).strip()
                if not text:
                    continue

                await send_log("dm_narration", text)

                for player_id, char in state.characters.items():
                    try:
                        await handle_player_response(char, player_id, text)
                    except Exception as exc:
                        log.error("LLM error for %s: %s", char.name, exc)
                        await send({"type": "error", "message": f"LLM error for {char.name}: {exc}"})

                await send_state()

            # ------------------------------------------------------------------
            elif cmd == "dm_reply":
                if not client:
                    await send({"type": "error", "message": "ANTHROPIC_API_KEY not set."})
                    continue

                player_id = str(msg.get("player_id", ""))
                text = str(msg.get("text", "")).strip()
                if not text or player_id not in state.characters:
                    continue

                char = state.characters[player_id]
                await send_log("dm_reply", text, player_id=player_id)

                try:
                    await handle_player_response(char, player_id, text)
                except Exception as exc:
                    log.error("LLM error for %s: %s", char.name, exc)
                    await send({"type": "error", "message": f"LLM error for {char.name}: {exc}"})

                await send_state()

            # ------------------------------------------------------------------
            elif cmd == "dm_reroll":
                if not client:
                    await send({"type": "error", "message": "ANTHROPIC_API_KEY not set."})
                    continue

                player_id = str(msg.get("player_id", ""))
                if player_id not in state.characters:
                    continue

                try:
                    player_num = int(player_id.replace("player-", ""))
                except ValueError:
                    player_num = 1

                existing_names = [c.name for pid, c in state.characters.items() if pid != player_id]
                theme = state.session_theme

                await send_log("system", f"Rerolling character for Player {player_num}…")
                # Signal frontend to clear this player's column messages
                await send({"type": "player_reset", "player_id": player_id})
                try:
                    char = generate_character(client, player_num, theme, existing_names=existing_names)
                    state.characters[player_id] = char
                    state.player_conversation_histories[player_id] = []
                    party_context.pop(player_id, None)
                    log.info("Rerolled: %s the %s %s", char.name, char.race, char.character_class)
                    await send_log("system", f"Rerolled Player {player_num}: {char.name} the {char.race} {char.character_class}")
                    await send_state()
                except Exception as exc:
                    log.error("Reroll failed for %s: %s", player_id, exc)
                    await send({"type": "error", "message": f"Reroll failed: {exc}"})

            # ------------------------------------------------------------------
            elif cmd == "start_combat":
                enemies_raw: list[dict] = msg.get("enemies", [])
                # Expand count > 1 into multiple enemies
                enemies: list[dict] = []
                for e in enemies_raw:
                    count = int(e.get("count", 1))
                    for i in range(count):
                        suffix = f" {i + 1}" if count > 1 else ""
                        enemies.append({
                            "id": str(uuid.uuid4()),
                            "name": e["name"] + suffix,
                            "hp": int(e["hp"]),
                            "ac": int(e["ac"]),
                            "dex": int(e.get("dex", 10)),
                        })

                chars = list(state.characters.values())
                state.combat = roll_initiative_order(chars, enemies)
                order_str = ", ".join(
                    f"{c.name} ({c.initiative})" for c in state.combat.initiative_order
                )
                await send_log("combat", f"⚔ Combat begins! Initiative order: {order_str}")
                first = current_combatant(state.combat)
                await send_log("combat", f"Round {state.combat.round} — {first.name}'s turn.")
                await send_state()

            # ------------------------------------------------------------------
            elif cmd == "next_turn":
                if not state.combat.active:
                    await send({"type": "error", "message": "No combat active."})
                    continue
                state.combat = advance_turn(state.combat)
                combatant = current_combatant(state.combat)
                await send_log("combat", f"Round {state.combat.round} — {combatant.name}'s turn.")

                # If it's an LLM player's turn and DM didn't narrate, prompt player automatically
                if combatant.is_player and client:
                    char = state.characters.get(combatant.id)
                    if char and combatant.current_hp > 0:
                        history = state.player_conversation_histories.get(combatant.id, [])
                        prompt = f"It's your turn in combat (Round {state.combat.round}). What do you do?"
                        try:
                            parsed, new_history = get_player_response(client, char, history, prompt)
                            state.player_conversation_histories[combatant.id] = new_history
                            if parsed.get("speech"):
                                await send_log("player_speech", f'**{char.name}**: "{parsed["speech"]}"', player_id=char.id)
                            if parsed.get("action_description"):
                                await send_log("player_action", f"{char.name} {parsed['action_description']}", player_id=char.id)
                        except Exception as exc:
                            await send({"type": "error", "message": f"LLM error for {char.name}: {exc}"})

                await send_state()

            # ------------------------------------------------------------------
            elif cmd == "apply_damage":
                target_id = str(msg.get("target_id", ""))
                damage = int(msg.get("damage", 0))
                if state.combat.active:
                    state.combat = apply_combatant_damage(state.combat, target_id, damage)
                if target_id in state.characters:
                    state.characters[target_id] = apply_damage(state.characters[target_id], damage)
                target_name = (
                    state.characters[target_id].name if target_id in state.characters
                    else next((c.name for c in state.combat.initiative_order if c.id == target_id), target_id)
                )
                await send_log("combat", f"💥 {target_name} takes {damage} damage.")
                await send_state()

            # ------------------------------------------------------------------
            elif cmd == "apply_healing":
                target_id = str(msg.get("target_id", ""))
                healing = int(msg.get("healing", 0))
                if target_id in state.characters:
                    state.characters[target_id] = apply_healing(state.characters[target_id], healing)
                if state.combat.active:
                    for c in state.combat.initiative_order:
                        if c.id == target_id:
                            c.current_hp = min(c.max_hp, c.current_hp + healing)
                target_name = state.characters[target_id].name if target_id in state.characters else target_id
                await send_log("combat", f"💚 {target_name} is healed for {healing} HP.")
                await send_state()

            # ------------------------------------------------------------------
            elif cmd == "end_combat":
                from play_dm.models import CombatState
                state.combat = CombatState()
                await send_log("combat", "⚔ Combat has ended.")
                await send_state()

            # ------------------------------------------------------------------
            elif cmd == "roll_dice":
                expr = str(msg.get("dice", "1d20"))
                modifier = int(msg.get("modifier", 0))
                context = str(msg.get("context", ""))
                total, rolls, mod = roll_with_modifier(expr, modifier)
                await send({
                    "type": "dice_roll",
                    "dice": expr,
                    "rolls": rolls,
                    "modifier": modifier,
                    "total": total,
                    "context": context,
                    "character_name": "DM",
                })
                await send_log(
                    "dice_roll",
                    f"DM rolls {expr}{f'+{mod}' if mod > 0 else (str(mod) if mod < 0 else '')}: {total}" +
                    (f" ({context})" if context else ""),
                    metadata={"dice": expr, "total": total, "rolls": rolls},
                )

            # ------------------------------------------------------------------
            elif cmd == "save_game":
                filename = str(msg.get("filename", "autosave")).strip() or "autosave"
                # Sanitize filename
                filename = "".join(c for c in filename if c.isalnum() or c in "._- ")
                path = str(SAVES_DIR / f"{filename}.json")
                try:
                    save_state(state, path)
                    await send_log("system", f"💾 Game saved as '{filename}'.")
                    await send({"type": "save_ok", "filename": filename})
                except Exception as exc:
                    await send({"type": "error", "message": f"Save failed: {exc}"})

            # ------------------------------------------------------------------
            elif cmd == "load_game":
                filename = str(msg.get("filename", "")).strip()
                filename = "".join(c for c in filename if c.isalnum() or c in "._- ")
                path = str(SAVES_DIR / f"{filename}.json")
                try:
                    state = load_state(path)
                    await send_log("system", f"📂 Loaded save '{filename}'.")
                    await send_state()
                except FileNotFoundError:
                    await send({"type": "error", "message": f"Save '{filename}' not found."})
                except Exception as exc:
                    await send({"type": "error", "message": f"Load failed: {exc}"})

            # ------------------------------------------------------------------
            else:
                await send({"type": "error", "message": f"Unknown command: {cmd!r}"})

    except WebSocketDisconnect:
        log.info("WebSocket disconnected")
