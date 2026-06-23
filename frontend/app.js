// app.js — play-dm frontend (column-per-character layout)
'use strict';

// ─── WebSocket ───────────────────────────────────────────────────────────────
const WS_URL = `ws://${location.host}/ws`;
let ws = null;
let gameState = null;

// Per-column message lists: player_id -> Array of rendered elements
const columnMsgLists = {};

function connectWS() {
  ws = new WebSocket(WS_URL);
  ws.addEventListener('open', () => setIndicator(true));
  ws.addEventListener('close', () => { setIndicator(false); setTimeout(connectWS, 2000); });
  ws.addEventListener('message', (ev) => handleMessage(JSON.parse(ev.data)));
}

function send(obj) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
}

function setIndicator(connected) {
  const el = document.getElementById('wsIndicator');
  el.classList.toggle('connected', connected);
  el.title = connected ? 'Connected' : 'Disconnected — reconnecting…';
}

// ─── Message routing ──────────────────────────────────────────────────────────
function handleMessage(msg) {
  switch (msg.type) {
    case 'log_entry':   routeLogEntry(msg.entry); break;
    case 'state_update': gameState = msg.state; renderState(gameState); break;
    case 'player_reset': {
      const msgEl = document.getElementById(`msgs_${msg.player_id}`);
      if (msgEl) msgEl.innerHTML = '';
      break;
    }
    case 'error':
      appendToStatusLog('⚠ ' + msg.message, 'error');
      appendToAllColumns(makeErrLine('⚠ ' + msg.message));
      break;
    case 'save_ok':
      appendToStatusLog(`💾 Saved as "${msg.filename}".`);
      appendToAllColumns(makeSysLine(`💾 Saved as "${msg.filename}".`));
      break;
    default: break;
  }
}

function routeLogEntry(entry) {
  const { entry_type, content, player_id } = entry;

  switch (entry_type) {
    case 'dm_narration':
      // DM spoke to everyone — show in all columns
      if (Object.keys(columnMsgLists).length > 0) {
        appendToAllColumns(makeDmBubble(content));
      } else {
        appendToStatusLog(content);
      }
      break;

    case 'dm_reply':
      // DM spoke to one player only
      appendToColumn(player_id, makeDmBubble(content));
      break;

    case 'player_speech':
      // Show full bubble in that player's column
      appendToColumn(player_id, makePlayerBubble(content));
      // Show a compact party note in every OTHER column
      appendToOtherColumns(player_id, makePartyLine(content));
      break;

    case 'player_action':
      // Suppressed — the speech already conveys the action
      break;

    case 'dice_roll':
      if (player_id) {
        appendToColumn(player_id, makeDiceLine(content));
      } else {
        appendToAllColumns(makeDiceLine(content));
      }
      break;

    case 'system':
      appendToStatusLog(content);
      // Only push to a column when the message targets a specific player
      // (e.g. spell-slot expend). Session-wide housekeeping stays in statusLog only.
      if (player_id) appendToColumn(player_id, makeSysLine(content));
      break;
    case 'combat':
      appendToStatusLog(content, 'combat');
      appendToAllColumns(makeSysLine(content));
      break;
    case 'error':
      appendToStatusLog(content, 'error');
      appendToAllColumns(makeErrLine(content));
      break;

    default:
      appendToAllColumns(makeSysLine(content));
      break;
  }
}

// ─── Status log (always-visible strip for system/combat/error events) ───────
function appendToStatusLog(text, kind = '') {
  const el = document.getElementById('statusLog');
  if (!el) return;
  const line = document.createElement('div');
  line.className = 'sl-line' + (kind ? ' sl-' + kind : '');
  line.textContent = text.replace(/\*\*/g, '').replace(/\*/g, '');
  el.appendChild(line);
  el.scrollTop = el.scrollHeight;
  // Keep last 30 lines
  while (el.children.length > 30) el.removeChild(el.firstChild);
}

// ─── Column append helpers ───────────────────────────────────────────────────
function appendToColumn(playerId, el) {
  const list = document.getElementById(`msgs_${playerId}`);
  if (!list) return;
  list.appendChild(el);
  list.scrollTop = list.scrollHeight;
}

function appendToAllColumns(el) {
  Object.keys(columnMsgLists).forEach((pid) => {
    appendToColumn(pid, el.cloneNode(true));
  });
}

function appendToOtherColumns(speakerPlayerId, el) {
  Object.keys(columnMsgLists).forEach((pid) => {
    if (pid !== speakerPlayerId) appendToColumn(pid, el.cloneNode(true));
  });
}

// ─── Message element builders ────────────────────────────────────────────────
function makeDmBubble(text) {
  const wrap = document.createElement('div');
  wrap.className = 'msg msg-dm';
  wrap.innerHTML = `<div class="msg-label">DM</div><div class="msg-bubble">${markdownLite(text)}</div>`;
  return wrap;
}

function makePlayerBubble(text) {
  const wrap = document.createElement('div');
  wrap.className = 'msg msg-player';
  // Strip leading **Name**: wrapper so we just show the speech
  const cleaned = text.replace(/^\*\*[^*]+\*\*:\s*"?/, '').replace(/"$/, '');
  const name = (text.match(/^\*\*([^*]+)\*\*/) || [])[1] || '';
  wrap.innerHTML = `<div class="msg-label">${name}</div><div class="msg-bubble">${markdownLite(cleaned)}</div>`;
  return wrap;
}

function makePartyLine(text) {
  const wrap = document.createElement('div');
  wrap.className = 'msg msg-party';
  // Compact: show "🗣 Name: «first 80 chars»"
  const nameMatch = text.match(/^\*\*([^*]+)\*\*:\s*"?(.+)/s);
  let preview = text;
  if (nameMatch) {
    const name = nameMatch[1];
    const body = nameMatch[2].replace(/"$/, '').trim().slice(0, 90);
    preview = `<strong>${name}:</strong> ${body}${nameMatch[2].length > 90 ? '…' : ''}`;
  }
  wrap.innerHTML = `<div class="msg-party-line">🗣 ${preview}</div>`;
  return wrap;
}

function makeDiceLine(text) {
  const wrap = document.createElement('div');
  wrap.className = 'msg msg-dice';
  // Highlight the number at the end e.g. "Thalia rolls Perception check: 15 (...)"
  const highlighted = text.replace(/:\s*(\d+)/, ': <span class="dice-num">$1</span>');
  wrap.innerHTML = `<div class="msg-dice-line">🎲 ${highlighted}</div>`;
  return wrap;
}

function makeSysLine(text) {
  const wrap = document.createElement('div');
  wrap.className = 'msg msg-system';
  wrap.innerHTML = `<div class="msg-sys-line">${markdownLite(text)}</div>`;
  return wrap;
}

function makeErrLine(text) {
  const wrap = document.createElement('div');
  wrap.className = 'msg msg-error';
  wrap.innerHTML = `<div class="msg-err-line">${text}</div>`;
  return wrap;
}

function markdownLite(text) {
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/\n/g, '<br>');
}

// ─── State rendering ──────────────────────────────────────────────────────────
function renderState(state) {
  document.getElementById('sessionName').textContent = state.session_name || 'Session';
  renderColumns(state.characters || {});
  renderCombat(state.combat);
}

function renderColumns(characters) {
  const area = document.getElementById('columnsArea');
  const entries = Object.values(characters);

  if (entries.length === 0) {
    // Only show the no-session hint if no columns have ever been built
    if (!document.querySelector('.char-column')) {
      area.innerHTML = '<div class="no-session-hint"><p>Click <strong>New Session</strong> to generate your party.</p></div>';
    }
    return;
  }

  // Remove the no-session hint if present
  const hint = area.querySelector('.no-session-hint');
  if (hint) hint.remove();

  // Build columns that don't exist yet; update headers for existing ones.
  // Always check the DOM directly — columnMsgLists can get stale.
  entries.forEach((char) => {
    const existingCol = document.getElementById(`col_${char.id}`);
    if (!existingCol) {
      columnMsgLists[char.id] = true;
      area.appendChild(buildColumn(char));
    } else {
      columnMsgLists[char.id] = true;
      updateColumnHeader(char);
    }
  });
}

function buildColumn(char) {
  const col = document.createElement('div');
  col.className = 'char-column';
  col.id = `col_${char.id}`;

  // Plain div — NOT a <form> — so Enter never causes a form submit / page navigation.
  col.innerHTML = `
    ${buildColHeader(char)}
    <div class="col-messages" id="msgs_${char.id}"></div>
    <div class="col-reply" id="replyArea_${char.id}">
      <input type="text" class="col-reply-input" id="replyInput_${char.id}"
             placeholder="Reply to ${char.name}…" autocomplete="off" />
      <button type="button" class="btn btn-primary btn-sm" id="replyBtn_${char.id}"
              title="Send to ${char.name}">↵</button>
    </div>
  `;

  function doReply() {
    const input = document.getElementById(`replyInput_${char.id}`);
    const text = input.value.trim();
    if (!text) return;
    send({ type: 'dm_reply', player_id: char.id, text });
    input.value = '';
  }

  col.querySelector(`#replyBtn_${char.id}`).addEventListener('click', doReply);
  col.querySelector(`#replyInput_${char.id}`).addEventListener('keydown', (ev) => {
    if (ev.key === 'Enter') { ev.preventDefault(); doReply(); }
  });

  return col;
}

function buildColHeader(char) {
  const hpPct = Math.max(0, Math.min(100, (char.current_hp / char.max_hp) * 100));
  const hpColor = hpPct > 50 ? 'var(--green)' : hpPct > 25 ? 'var(--orange)' : 'var(--red)';
  const conditions = (char.conditions || []).map((c) => `<span class="col-cond-tag">${c}</span>`).join('');
  const spellInfo = char.spell_slots && Object.keys(char.spell_slots).length > 0
    ? ' · ' + Object.entries(char.spell_slots).map(([l, n]) => `L${l}:${n}`).join('/')
    : '';

  return `
    <div class="col-header" id="colHeader_${char.id}">
      <div class="col-header-top">
        <div>
          <div class="col-char-name">${char.name}</div>
          <div class="col-char-sub">${char.race} ${char.character_class} · Lvl ${char.level}</div>
        </div>
        <button class="btn btn-ghost btn-sm col-reroll-btn" title="Reroll this character"
                onclick="rerollCharacter('${char.id}')">&#8635; Reroll</button>
      </div>
      <div class="col-hp-wrap">
        <div class="col-hp-label"><span>HP</span><span>${char.current_hp}/${char.max_hp}</span></div>
        <div class="col-hp-bar"><div class="col-hp-fill" id="hpFill_${char.id}"
             style="width:${hpPct}%;background:${hpColor}"></div></div>
      </div>
      <div class="col-stats-row">
        <span>AC ${char.armor_class}</span>
        <span>Spd ${char.speed}ft</span>
        <span>Prof +${char.proficiency_bonus}${spellInfo}</span>
      </div>
      ${conditions ? `<div class="col-conditions">${conditions}</div>` : ''}
    </div>`;
}

function updateColumnHeader(char) {
  const header = document.getElementById(`colHeader_${char.id}`);
  if (!header) return;
  const hpPct = Math.max(0, Math.min(100, (char.current_hp / char.max_hp) * 100));
  const hpColor = hpPct > 50 ? 'var(--green)' : hpPct > 25 ? 'var(--orange)' : 'var(--red)';
  const fill = document.getElementById(`hpFill_${char.id}`);
  if (fill) { fill.style.width = `${hpPct}%`; fill.style.background = hpColor; }
  // Update HP label text
  const label = header.querySelector('.col-hp-label');
  if (label) label.lastElementChild.textContent = `${char.current_hp}/${char.max_hp}`;
  // Update conditions
  const condWrap = header.querySelector('.col-conditions');
  const newConds = (char.conditions || []).map((c) => `<span class="col-cond-tag">${c}</span>`).join('');
  if (condWrap) condWrap.innerHTML = newConds;
}

function renderCombat(combat) {
  const panel = document.getElementById('combatPanel');
  const tracker = document.getElementById('combatTracker');
  const roundEl = document.getElementById('combatRound');

  if (!combat || !combat.active) {
    panel.classList.add('hidden');
    return;
  }

  panel.classList.remove('hidden');
  roundEl.textContent = `Round ${combat.round}`;
  tracker.innerHTML = '';

  (combat.initiative_order || []).forEach((c, idx) => {
    const isActive = idx === combat.turn_index;
    const hpPct = Math.max(0, Math.min(100, (c.current_hp / c.max_hp) * 100));
    const hpColor = hpPct > 50 ? 'var(--green)' : hpPct > 25 ? 'var(--orange)' : 'var(--red)';

    const row = document.createElement('div');
    row.className = `combatant-row${isActive ? ' active-turn' : ''}${c.current_hp === 0 ? ' dead' : ''}`;
    row.innerHTML = `
      <div class="combatant-top">
        <span class="combatant-name">${isActive ? '▶ ' : ''}${c.name}${c.is_player ? '' : ' <span style="color:var(--red);font-size:0.65rem">(E)</span>'}</span>
        <span class="combatant-init">ini ${c.initiative}</span>
      </div>
      <div class="combatant-hp-bar"><div class="combatant-hp-fill" style="width:${hpPct}%;background:${hpColor}"></div></div>
      <div class="combatant-bottom">
        <span style="color:${hpPct<=25?'var(--red)':hpPct<=50?'var(--orange)':'var(--green)'}">${c.current_hp}/${c.max_hp} HP</span>
        <span>AC ${c.armor_class}</span>
      </div>
      <div class="combatant-btns">
        <button class="btn btn-ghost btn-sm" onclick="dmgDialog('${c.id}','${c.name}')">Dmg</button>
        <button class="btn btn-ghost btn-sm" onclick="healDialog('${c.id}','${c.name}')">Heal</button>
      </div>`;
    tracker.appendChild(row);
  });
}

window.rerollCharacter = (playerId) => {
  if (confirm('Reroll this character? Their history will be cleared.')) {
    send({ type: 'dm_reroll', player_id: playerId });
  }
};

window.dmgDialog = (id, name) => {
  const v = parseInt(prompt(`Damage to ${name}:`, '0'), 10);
  if (!isNaN(v) && v > 0) send({ type: 'apply_damage', target_id: id, damage: v });
};
window.healDialog = (id, name) => {
  const v = parseInt(prompt(`Heal ${name} by:`, '0'), 10);
  if (!isNaN(v) && v > 0) send({ type: 'apply_healing', target_id: id, healing: v });
};

// ─── New Session ──────────────────────────────────────────────────────────────
document.getElementById('btnNewSession').addEventListener('click', () => openModal('modalNewSession'));

document.getElementById('btnConfirmNewSession').addEventListener('click', () => {
  const sessionName = document.getElementById('inSessionName').value.trim() || 'New Campaign';
  const playerCount = parseInt(document.getElementById('inPlayerCount').value, 10);
  const theme = document.getElementById('inTheme').value.trim();
  // Clear existing columns and status log
  document.getElementById('columnsArea').innerHTML = '';
  document.getElementById('statusLog').innerHTML = '';
  Object.keys(columnMsgLists).forEach((k) => delete columnMsgLists[k]);
  send({ type: 'new_session', player_count: playerCount, theme, session_name: sessionName });
  closeAllModals();
});

// ─── Narrate to All ───────────────────────────────────────────────────────────
document.getElementById('dmForm').addEventListener('submit', (ev) => {
  ev.preventDefault();
  const textarea = document.getElementById('dmInput');
  const text = textarea.value.trim();
  if (!text) return;
  send({ type: 'dm_narrate', text });
  textarea.value = '';
});

document.getElementById('dmInput').addEventListener('keydown', (ev) => {
  if (ev.key === 'Enter' && (ev.ctrlKey || ev.metaKey)) {
    ev.preventDefault();
    document.getElementById('dmForm').dispatchEvent(new Event('submit'));
  }
});

// ─── Combat ───────────────────────────────────────────────────────────────────
document.getElementById('btnStartCombat').addEventListener('click', () => openModal('modalStartCombat'));

document.getElementById('btnAddEnemy').addEventListener('click', () => {
  const row = document.createElement('div');
  row.className = 'enemy-row';
  row.innerHTML = `
    <input type="text" placeholder="Name" class="enemy-name" />
    <input type="number" placeholder="HP" class="enemy-hp" value="10" min="1" />
    <input type="number" placeholder="AC" class="enemy-ac" value="12" min="1" />
    <input type="number" placeholder="DEX" class="enemy-dex" value="10" min="1" max="30" />
    <input type="number" placeholder="Count" class="enemy-count" value="1" min="1" max="10" />
    <button class="btn btn-ghost btn-sm remove-enemy">✕</button>`;
  document.getElementById('enemyList').appendChild(row);
});

document.getElementById('enemyList').addEventListener('click', (ev) => {
  if (ev.target.classList.contains('remove-enemy')) ev.target.closest('.enemy-row').remove();
});

document.getElementById('btnConfirmStartCombat').addEventListener('click', () => {
  const enemies = [];
  document.querySelectorAll('.enemy-row').forEach((row) => {
    const name = row.querySelector('.enemy-name').value.trim();
    const hp = parseInt(row.querySelector('.enemy-hp').value, 10);
    const ac = parseInt(row.querySelector('.enemy-ac').value, 10);
    const dex = parseInt(row.querySelector('.enemy-dex').value, 10);
    const count = parseInt(row.querySelector('.enemy-count').value, 10) || 1;
    if (name && hp > 0) enemies.push({ name, hp, ac, dex, count });
  });
  if (!enemies.length) { alert('Add at least one enemy.'); return; }
  send({ type: 'start_combat', enemies });
  closeAllModals();
});

document.getElementById('btnNextTurn').addEventListener('click', () => send({ type: 'next_turn' }));
document.getElementById('btnEndCombat').addEventListener('click', () => {
  if (confirm('End combat?')) send({ type: 'end_combat' });
});

// ─── Dice ─────────────────────────────────────────────────────────────────────
document.getElementById('btnRollDice').addEventListener('click', () => openModal('modalRollDice'));
document.getElementById('btnConfirmRollDice').addEventListener('click', () => {
  const dice = document.getElementById('inDiceExpr').value.trim() || '1d20';
  const modifier = parseInt(document.getElementById('inDiceModifier').value, 10) || 0;
  const context = document.getElementById('inDiceContext').value.trim();
  send({ type: 'roll_dice', dice, modifier, context });
  closeAllModals();
});

// ─── Save / Load ──────────────────────────────────────────────────────────────
document.getElementById('btnSave').addEventListener('click', () => {
  if (gameState) document.getElementById('inSaveFilename').value =
    (gameState.session_name || 'save').toLowerCase().replace(/\s+/g, '_');
  openModal('modalSave');
});
document.getElementById('btnConfirmSave').addEventListener('click', () => {
  send({ type: 'save_game', filename: document.getElementById('inSaveFilename').value.trim() || 'autosave' });
  closeAllModals();
});
document.getElementById('btnLoad').addEventListener('click', async () => {
  const res = await fetch('/saves');
  const data = await res.json();
  const listEl = document.getElementById('savesList');
  if (!data.saves.length) {
    listEl.innerHTML = '<p class="empty-hint">No saves found.</p>';
  } else {
    listEl.innerHTML = '';
    data.saves.forEach((name) => {
      const row = document.createElement('div');
      row.className = 'save-item';
      row.innerHTML = `<span>${name}</span><button class="btn btn-ghost btn-sm" onclick="loadSave('${name}')">Load</button>`;
      listEl.appendChild(row);
    });
  }
  openModal('modalLoad');
});
window.loadSave = (name) => { send({ type: 'load_game', filename: name }); closeAllModals(); };

// ─── Modal helpers ─────────────────────────────────────────────────────────────
function openModal(id) { document.getElementById(id).classList.remove('hidden'); }
function closeAllModals() { document.querySelectorAll('.modal-overlay').forEach((m) => m.classList.add('hidden')); }
document.querySelectorAll('.modal-cancel').forEach((btn) => btn.addEventListener('click', closeAllModals));
document.querySelectorAll('.modal-overlay').forEach((o) => o.addEventListener('click', (ev) => { if (ev.target === o) closeAllModals(); }));

// ─── Init ─────────────────────────────────────────────────────────────────────
connectWS();
