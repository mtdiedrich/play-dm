// app.js — play-dm frontend
'use strict';

// ─── WebSocket ───────────────────────────────────────────────────────────────
const WS_URL = `ws://${location.host}/ws`;
let ws = null;
let gameState = null;

function connectWS() {
  ws = new WebSocket(WS_URL);

  ws.addEventListener('open', () => {
    setIndicator(true);
  });

  ws.addEventListener('close', () => {
    setIndicator(false);
    setTimeout(connectWS, 2000); // reconnect
  });

  ws.addEventListener('message', (ev) => {
    const msg = JSON.parse(ev.data);
    handleMessage(msg);
  });
}

function send(obj) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(obj));
  }
}

function setIndicator(connected) {
  const el = document.getElementById('wsIndicator');
  el.classList.toggle('connected', connected);
  el.title = connected ? 'Connected' : 'Disconnected — reconnecting…';
}

// ─── Message Handler ─────────────────────────────────────────────────────────
function handleMessage(msg) {
  switch (msg.type) {
    case 'log_entry':
      appendLogEntry(msg.entry);
      break;
    case 'state_update':
      gameState = msg.state;
      renderState(gameState);
      break;
    case 'dice_roll':
      appendDiceRoll(msg);
      break;
    case 'error':
      appendLogEntry({ entry_type: 'error', content: '⚠ ' + msg.message, metadata: {} });
      break;
    case 'save_ok':
      appendLogEntry({ entry_type: 'system', content: `Game saved as "${msg.filename}".`, metadata: {} });
      break;
    default:
      break;
  }
}

// ─── Log ─────────────────────────────────────────────────────────────────────
function appendLogEntry(entry) {
  const log = document.getElementById('gameLog');
  const div = document.createElement('div');
  div.className = `log-entry log-${entry.entry_type}`;

  const inner = document.createElement('span');
  inner.className = 'log-content';
  inner.innerHTML = markdownLite(entry.content || '');
  div.appendChild(inner);

  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}

function appendDiceRoll(msg) {
  const log = document.getElementById('gameLog');
  const div = document.createElement('div');
  div.className = 'log-entry log-dice_roll';

  const context = msg.context ? `<em>${msg.context}</em> — ` : '';
  const rollsStr = msg.rolls ? `[${msg.rolls.join(', ')}]` : '';
  const modStr = msg.modifier !== 0 ? ` ${msg.modifier >= 0 ? '+' : ''}${msg.modifier}` : '';
  div.innerHTML =
    `<span class="log-content">${context}${msg.dice}${modStr} → ` +
    `<span class="dice-result">${msg.total}</span>` +
    `<span class="dice-detail">${rollsStr}${modStr}</span></span>`;

  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}

// Very light markdown: bold, italic, line breaks
function markdownLite(text) {
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/\n/g, '<br>');
}

// ─── State Rendering ─────────────────────────────────────────────────────────
function renderState(state) {
  document.getElementById('sessionName').textContent = state.session_name || 'Session';
  renderCharacters(state.characters || {});
  renderCombat(state.combat);
}

function renderCharacters(characters) {
  const container = document.getElementById('characterCards');
  container.innerHTML = '';

  const entries = Object.values(characters);
  if (entries.length === 0) {
    container.innerHTML = '<p class="empty-hint">No characters yet.</p>';
    return;
  }

  entries.forEach((char) => {
    const card = buildCharCard(char);
    container.appendChild(card);
  });
}

function buildCharCard(char) {
  const hpPct = Math.max(0, Math.min(100, (char.current_hp / char.max_hp) * 100));
  const hpColor = hpPct > 50 ? 'var(--green)' : hpPct > 25 ? 'var(--orange)' : 'var(--red)';

  const card = document.createElement('div');
  card.className = 'char-card';
  card.dataset.charId = char.id;

  const conditionTags = (char.conditions || [])
    .map((c) => `<span class="condition-tag">${c}</span>`)
    .join('');

  const spellInfo = char.spell_slots && Object.keys(char.spell_slots).length > 0
    ? '<div class="char-details-section"><strong>Spell Slots:</strong> ' +
      Object.entries(char.spell_slots)
        .map(([lvl, n]) => `L${lvl}:${n}`)
        .join(' / ') + '</div>'
    : '';

  const spellsKnown = [...(char.cantrips || []), ...(char.spells_known || [])];
  const spellsInfo = spellsKnown.length > 0
    ? `<div class="char-details-section"><strong>Spells:</strong> ${spellsKnown.join(', ')}</div>`
    : '';

  const inventoryInfo = (char.inventory || []).length > 0
    ? `<div class="char-details-section"><strong>Inventory:</strong> ${
        char.inventory.map((i) => `${i.name}${i.quantity > 1 ? ` ×${i.quantity}` : ''}`).join(', ')
      }</div>`
    : '';

  const scores = char.ability_scores || {};
  const abilityRows = [
    ['STR', scores.strength], ['DEX', scores.dexterity], ['CON', scores.constitution],
    ['INT', scores.intelligence], ['WIS', scores.wisdom], ['CHA', scores.charisma],
  ].map(([label, val]) => {
    const mod = val !== undefined ? Math.floor((val - 10) / 2) : 0;
    const modStr = mod >= 0 ? `+${mod}` : `${mod}`;
    return `<div class="char-stat"><div class="char-stat-label">${label}</div><div class="char-stat-value">${val ?? '—'}<small style="color:var(--text-dim)">(${modStr})</small></div></div>`;
  }).join('');

  card.innerHTML = `
    <div class="char-header" onclick="toggleCharDetails('${char.id}')">
      <div>
        <div class="char-name">${char.name}</div>
        <div class="char-subtitle">${char.race} ${char.character_class} · Lvl ${char.level}</div>
      </div>
      <span style="color:var(--text-dim);font-size:0.7rem">▼</span>
    </div>
    <div class="char-hp-bar-wrap">
      <div class="char-hp-label"><span>HP</span><span>${char.current_hp} / ${char.max_hp}</span></div>
      <div class="char-hp-bar"><div class="char-hp-fill" style="width:${hpPct}%;background:${hpColor}"></div></div>
    </div>
    <div class="char-stats">
      <div class="char-stat"><div class="char-stat-label">AC</div><div class="char-stat-value">${char.armor_class}</div></div>
      <div class="char-stat"><div class="char-stat-label">SPEED</div><div class="char-stat-value">${char.speed}ft</div></div>
      <div class="char-stat"><div class="char-stat-label">PROF</div><div class="char-stat-value">+${char.proficiency_bonus}</div></div>
    </div>
    ${conditionTags ? `<div class="char-conditions">${conditionTags}</div>` : ''}
    <div class="char-details" id="charDetails_${char.id}">
      <div class="char-stats" style="margin-top:0.5rem">${abilityRows}</div>
      ${spellInfo}
      ${spellsInfo}
      ${inventoryInfo}
      <div class="char-details-section" style="margin-top:0.5rem;font-style:italic;">${char.personality_traits || ''}</div>
    </div>
  `;
  return card;
}

function toggleCharDetails(charId) {
  const el = document.getElementById(`charDetails_${charId}`);
  if (el) el.classList.toggle('open');
}
window.toggleCharDetails = toggleCharDetails;

function renderCombat(combat) {
  const tracker = document.getElementById('combatTracker');
  const toolbar = document.getElementById('combatToolbar');
  const startBtn = document.getElementById('btnStartCombat');

  if (!combat || !combat.active) {
    tracker.innerHTML = '<p class="empty-hint">No active combat.</p>';
    toolbar.classList.add('hidden');
    startBtn.textContent = '⚔ Start Combat';
    return;
  }

  startBtn.textContent = '⚔ Combat Active';
  toolbar.classList.remove('hidden');

  tracker.innerHTML = `<p style="font-size:0.72rem;color:var(--gold);margin-bottom:0.5rem">Round ${combat.round}</p>`;

  (combat.initiative_order || []).forEach((c, idx) => {
    const isActive = idx === combat.turn_index;
    const hpPct = Math.max(0, Math.min(100, (c.current_hp / c.max_hp) * 100));
    const hpColor = hpPct > 50 ? 'var(--green)' : hpPct > 25 ? 'var(--orange)' : 'var(--red)';

    const row = document.createElement('div');
    row.className = `combatant-row${isActive ? ' active-turn' : ''}${c.current_hp === 0 ? ' dead' : ''}`;

    const conds = (c.conditions || []).map((cd) => `<span class="condition-tag" style="font-size:0.6rem">${cd}</span>`).join('');

    row.innerHTML = `
      <div>
        <span class="combatant-name">${isActive ? '▶ ' : ''}${c.name}</span>
        ${c.is_player ? '<span style="color:var(--blue);font-size:0.65rem"> (PC)</span>' : '<span style="color:var(--red);font-size:0.65rem"> (Enemy)</span>'}
        ${conds}
      </div>
      <div>
        <span class="combatant-initiative" title="Initiative">Init ${c.initiative}</span>
      </div>
      <div class="combatant-hp-bar"><div class="combatant-hp-fill" style="width:${hpPct}%;background:${hpColor}"></div></div>
      <div style="grid-column:1/-1;display:flex;justify-content:space-between;align-items:center;margin-top:2px">
        <span class="combatant-hp ${hpPct <= 25 ? 'critical' : hpPct <= 50 ? 'low' : ''}">${c.current_hp}/${c.max_hp} HP</span>
        <span style="font-size:0.7rem;color:var(--text-muted)">AC ${c.armor_class}</span>
      </div>
      <div class="combatant-actions">
        <button class="btn btn-ghost btn-sm" onclick="dmgDialog('${c.id}','${c.name}')">Dmg</button>
        <button class="btn btn-ghost btn-sm" onclick="healDialog('${c.id}','${c.name}')">Heal</button>
      </div>
    `;
    tracker.appendChild(row);
  });
}

// Expose for inline onclick handlers
window.dmgDialog = function(id, name) {
  const dmg = parseInt(prompt(`Damage to ${name}:`, '0'), 10);
  if (!isNaN(dmg) && dmg > 0) send({ type: 'apply_damage', target_id: id, damage: dmg });
};
window.healDialog = function(id, name) {
  const hp = parseInt(prompt(`Heal ${name} by:`, '0'), 10);
  if (!isNaN(hp) && hp > 0) send({ type: 'apply_healing', target_id: id, healing: hp });
};

// ─── New Session ──────────────────────────────────────────────────────────────
document.getElementById('btnNewSession').addEventListener('click', () => {
  openModal('modalNewSession');
});

document.getElementById('btnConfirmNewSession').addEventListener('click', () => {
  const sessionName = document.getElementById('inSessionName').value.trim() || 'New Campaign';
  const playerCount = parseInt(document.getElementById('inPlayerCount').value, 10);
  const theme = document.getElementById('inTheme').value.trim();
  send({ type: 'new_session', player_count: playerCount, theme, session_name: sessionName });
  closeAllModals();
});

// ─── DM Narrate ──────────────────────────────────────────────────────────────
document.getElementById('dmForm').addEventListener('submit', (ev) => {
  ev.preventDefault();
  const textarea = document.getElementById('dmInput');
  const text = textarea.value.trim();
  if (!text) return;
  send({ type: 'dm_narrate', text });
  textarea.value = '';
});

// Ctrl+Enter to submit
document.getElementById('dmInput').addEventListener('keydown', (ev) => {
  if (ev.key === 'Enter' && (ev.ctrlKey || ev.metaKey)) {
    ev.preventDefault();
    document.getElementById('dmForm').dispatchEvent(new Event('submit'));
  }
});

// ─── Start Combat ─────────────────────────────────────────────────────────────
document.getElementById('btnStartCombat').addEventListener('click', () => {
  openModal('modalStartCombat');
});

document.getElementById('btnAddEnemy').addEventListener('click', () => {
  addEnemyRow();
});

document.getElementById('enemyList').addEventListener('click', (ev) => {
  if (ev.target.classList.contains('remove-enemy')) {
    ev.target.closest('.enemy-row').remove();
  }
});

document.getElementById('btnConfirmStartCombat').addEventListener('click', () => {
  const rows = document.querySelectorAll('.enemy-row');
  const enemies = [];
  rows.forEach((row) => {
    const name = row.querySelector('.enemy-name').value.trim();
    const hp = parseInt(row.querySelector('.enemy-hp').value, 10);
    const ac = parseInt(row.querySelector('.enemy-ac').value, 10);
    const dex = parseInt(row.querySelector('.enemy-dex').value, 10);
    const count = parseInt(row.querySelector('.enemy-count').value, 10) || 1;
    if (name && hp > 0) enemies.push({ name, hp, ac, dex, count });
  });
  if (enemies.length === 0) { alert('Add at least one enemy.'); return; }
  send({ type: 'start_combat', enemies });
  closeAllModals();
});

// ─── Combat Toolbar ───────────────────────────────────────────────────────────
document.getElementById('btnNextTurn').addEventListener('click', () => {
  send({ type: 'next_turn' });
});

document.getElementById('btnEndCombat').addEventListener('click', () => {
  if (confirm('End combat?')) send({ type: 'end_combat' });
});

// ─── Roll Dice ────────────────────────────────────────────────────────────────
document.getElementById('btnRollDice').addEventListener('click', () => {
  openModal('modalRollDice');
});

document.getElementById('btnConfirmRollDice').addEventListener('click', () => {
  const dice = document.getElementById('inDiceExpr').value.trim() || '1d20';
  const modifier = parseInt(document.getElementById('inDiceModifier').value, 10) || 0;
  const context = document.getElementById('inDiceContext').value.trim();
  send({ type: 'roll_dice', dice, modifier, context });
  closeAllModals();
});

// ─── Save / Load ──────────────────────────────────────────────────────────────
document.getElementById('btnSave').addEventListener('click', () => {
  if (gameState) {
    document.getElementById('inSaveFilename').value =
      (gameState.session_name || 'save').toLowerCase().replace(/\s+/g, '_');
  }
  openModal('modalSave');
});

document.getElementById('btnConfirmSave').addEventListener('click', () => {
  const filename = document.getElementById('inSaveFilename').value.trim() || 'autosave';
  send({ type: 'save_game', filename });
  closeAllModals();
});

document.getElementById('btnLoad').addEventListener('click', async () => {
  const res = await fetch('/saves');
  const data = await res.json();
  const listEl = document.getElementById('savesList');
  if (data.saves.length === 0) {
    listEl.innerHTML = '<p class="empty-hint">No saves found.</p>';
  } else {
    listEl.innerHTML = '';
    data.saves.forEach((name) => {
      const row = document.createElement('div');
      row.className = 'save-item';
      row.innerHTML = `<span class="save-item-name">${name}</span>
        <button class="btn btn-ghost btn-sm" onclick="loadSave('${name}')">Load</button>`;
      listEl.appendChild(row);
    });
  }
  openModal('modalLoad');
});

window.loadSave = function(name) {
  send({ type: 'load_game', filename: name });
  closeAllModals();
};

// ─── Modal Helpers ────────────────────────────────────────────────────────────
function openModal(id) {
  document.getElementById(id).classList.remove('hidden');
}

function closeAllModals() {
  document.querySelectorAll('.modal-overlay').forEach((m) => m.classList.add('hidden'));
}

document.querySelectorAll('.modal-cancel').forEach((btn) => {
  btn.addEventListener('click', closeAllModals);
});

document.querySelectorAll('.modal-overlay').forEach((overlay) => {
  overlay.addEventListener('click', (ev) => {
    if (ev.target === overlay) closeAllModals();
  });
});

// ─── Enemy Row Helper ─────────────────────────────────────────────────────────
function addEnemyRow() {
  const row = document.createElement('div');
  row.className = 'enemy-row';
  row.innerHTML = `
    <input type="text" placeholder="Name" class="enemy-name" />
    <input type="number" placeholder="HP" class="enemy-hp" value="10" min="1" />
    <input type="number" placeholder="AC" class="enemy-ac" value="12" min="1" />
    <input type="number" placeholder="DEX" class="enemy-dex" value="10" min="1" max="30" />
    <input type="number" placeholder="Count" class="enemy-count" value="1" min="1" max="10" />
    <button class="btn btn-ghost btn-sm remove-enemy">✕</button>
  `;
  document.getElementById('enemyList').appendChild(row);
}

// ─── Init ─────────────────────────────────────────────────────────────────────
connectWS();
