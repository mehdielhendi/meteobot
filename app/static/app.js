const messagesEl = document.getElementById("messages");
const form = document.getElementById("chat-form");
const input = document.getElementById("message");
const sendBtn = document.getElementById("send-btn");
const statusDot = document.getElementById("status-dot");
const statusText = document.getElementById("status-text");
const clockEl = document.getElementById("clock");
const chips = document.getElementById("chips");
const vigilanceMap = document.getElementById("vigilance-map");
const tickerInner = document.getElementById("ticker-inner");

const SESSION_KEY = "meteobot_session_id";

function getSessionId() {
  let id = localStorage.getItem(SESSION_KEY);
  if (!id) {
    id = `s_${Math.random().toString(36).slice(2)}_${Date.now()}`;
    localStorage.setItem(SESSION_KEY, id);
  }
  return id;
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function autosize() {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 136)}px`;
}

function vigilanceBadgeHtml(levelRaw) {
  const level = String(levelRaw || "vert")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
  let key = "vert";
  if (level.includes("rouge") || level === "red") key = "rouge";
  else if (level.includes("orange")) key = "orange";
  else if (level.includes("jaune") || level === "yellow") key = "jaune";
  else if (level.includes("vert") || level === "green") key = "vert";
  const label = key.toUpperCase();
  return `<span class="vig-badge vig-badge--${key}" title="Niveau de vigilance ${label}">${label}</span>`;
}

function formatReplyValue(label, value) {
  if (/^vigilance$/i.test(label.trim())) {
    return vigilanceBadgeHtml(value);
  }
  return escapeHtml(value);
}

function renderBotReply(text) {
  const lines = text.split("\n");
  if (!lines.length) return escapeHtml(text);

  const title = lines[0];
  const meta = [];
  const sections = [];
  let source = null;
  let current = null;
  const body = [];

  for (let i = 1; i < lines.length; i += 1) {
    const line = lines[i];
    if (!line.trim()) continue;
    if (line.startsWith("Source :")) {
      source = line.replace(/^Source\s*:\s*/, "");
      continue;
    }
    if (line.startsWith("• ")) {
      current = { header: line.slice(2), fields: [] };
      sections.push(current);
      continue;
    }
    if (current && (line.startsWith("  ") || line.startsWith("\t"))) {
      current.fields.push(line.trim());
      continue;
    }
    if (!current && line.includes(" : ")) {
      meta.push(line);
      continue;
    }
    body.push(line);
  }

  let html = `<div class="reply-title">${escapeHtml(title)}</div>`;
  if (meta.length) {
    html += `<div class="reply-meta">${meta
      .map((m) => `<div>${escapeHtml(m)}</div>`)
      .join("")}</div>`;
  }
  if (body.length) {
    html += `<div class="reply-body">${body
      .map((b) => `<div>${escapeHtml(b)}</div>`)
      .join("")}</div>`;
  }
  for (const section of sections) {
    html += `<div class="reply-section">`;
    html += `<div class="reply-section-title">${escapeHtml(section.header)}</div>`;
    if (section.fields.length) {
      html += `<div class="reply-fields">${section.fields
        .map((f) => {
          const parts = f.split(" : ");
          if (parts.length >= 2) {
            const label = parts.shift();
            const value = parts.join(" : ");
            return `<div class="reply-row"><span class="reply-label">${escapeHtml(
              label
            )}</span><span class="reply-value">${formatReplyValue(
              label,
              value
            )}</span></div>`;
          }
          return `<div class="reply-note">${escapeHtml(f)}</div>`;
        })
        .join("")}</div>`;
    }
    html += `</div>`;
  }
  if (source) {
    html += `<div class="reply-source">Source : ${escapeHtml(source)}</div>`;
  }
  return html;
}

function attachFollowups(bubbleEl, suggestions) {
  if (!suggestions || !suggestions.length) return;
  const wrap = document.createElement("div");
  wrap.className = "followups";
  for (const suggestion of suggestions.slice(0, 3)) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = suggestion;
    btn.addEventListener("click", () => ask(suggestion));
    wrap.appendChild(btn);
  }
  bubbleEl.appendChild(wrap);
}

function addBubble(text, role, options = {}) {
  const el = document.createElement("div");
  el.className = `bubble ${role}${options.typing ? " is-typing" : ""}`;
  if (options.typing) {
    el.innerHTML = `<span class="typing-wave" aria-hidden="true"><span></span><span></span><span></span></span><span>Analyse des bulletins…</span>`;
  } else if (role === "bot") {
    el.innerHTML = renderBotReply(text);
  } else {
    el.textContent = text;
  }
  messagesEl.appendChild(el);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return el;
}

function updateClock() {
  const now = new Date();
  clockEl.textContent = now.toLocaleTimeString("fr-FR", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function setLevelBadge(el, level) {
  const key = String(level || "vert").toLowerCase();
  el.className = `vig-badge vig-badge--lg vig-badge--${key}`;
  el.textContent = key.toUpperCase();
}

function applyPinLevels(places) {
  vigilanceMap.querySelectorAll(".map-pin").forEach((pin) => {
    const place = pin.dataset.place;
    const info = places[place] || { level: "vert" };
    const level = info.level || "vert";
    pin.classList.remove(
      "map-pin--vert",
      "map-pin--jaune",
      "map-pin--orange",
      "map-pin--rouge"
    );
    pin.classList.add(`map-pin--${level}`);
    const type = info.type ? ` · ${info.type}` : "";
    pin.title = `${place} — vigilance ${level.toUpperCase()}${type}`;
  });
}

function renderTicker(items) {
  if (!items || !items.length) return;
  const doubled = [...items, ...items];
  tickerInner.innerHTML = doubled
    .map((item) => `<span>${escapeHtml(item)}</span>`)
    .join("");
}

async function refreshDashboard() {
  try {
    const response = await fetch("/api/dashboard");
    if (!response.ok) throw new Error("dashboard");
    const data = await response.json();
    const metrics = data.metrics || {};

    const tempEl = document.getElementById("metric-temp");
    const tempMeta = document.getElementById("metric-temp-meta");
    if (metrics.avg_temp_c != null) {
      tempEl.textContent = `${metrics.avg_temp_c.toFixed(1)}°C`;
      tempMeta.textContent =
        metrics.obs_hour != null
          ? `OBS ${String(metrics.obs_hour).padStart(2, "0")}h · ${metrics.station_count} stations`
          : `${metrics.station_count} stations`;
    } else {
      tempEl.textContent = "—";
      tempMeta.textContent = "OBS indisponible";
    }

    document.getElementById("metric-alerts").textContent = String(
      metrics.active_alerts ?? 0
    );
    const alertPlaces = metrics.active_places || [];
    document.getElementById("metric-alerts-meta").textContent = alertPlaces.length
      ? alertPlaces.join(", ")
      : metrics.bulletin_nr
        ? `NR ${metrics.bulletin_nr}`
        : "Aucune province DRMNO";

    setLevelBadge(document.getElementById("metric-level"), metrics.top_level || "vert");
    document.getElementById("metric-level-meta").textContent = metrics.issue_date
      ? `BMS ${metrics.issue_date}`
      : "Bulletin BMS";

    const phenom = (metrics.phenomena || [])[0];
    document.getElementById("metric-phenom").textContent = phenom || "Calme";
    document.getElementById("metric-phenom-meta").textContent = phenom
      ? "Phénomène principal"
      : "Pas de phénomène signalé";

    applyPinLevels(data.places || {});
    renderTicker(data.ticker || []);
  } catch (error) {
    // keep defaults
  }
}

async function refreshHealth() {
  try {
    const response = await fetch("/api/health");
    if (!response.ok) throw new Error("down");
    const data = await response.json();
    statusDot.classList.add("is-online");
    statusText.textContent = `${data.app || "MétéoBot"} · en ligne`;
  } catch (error) {
    statusDot.classList.remove("is-online");
    statusText.textContent = "Hors ligne";
  }
}

async function ask(message) {
  addBubble(message, "user");
  input.value = "";
  autosize();
  sendBtn.disabled = true;
  const typing = addBubble("", "bot", { typing: true });

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        session_id: getSessionId(),
      }),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    typing.remove();
    const bubble = addBubble(data.reply, "bot");
    attachFollowups(bubble, data.suggestions || []);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  } catch (error) {
    typing.remove();
    addBubble(
      "Connexion impossible.\n\n• Astuce\n  Vérifiez que le serveur tourne sur le port 8000\nSource : interface",
      "bot"
    );
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
}

addBubble(
  "Console DRMNO opérationnelle.\nDate du service : vigilance colorée + bandeau OBS\n\n• Carte\n  Pins verts / orange / rouge selon le BMS courant\n• Essai\n  Cliquez Ouazzane ou demandez une alerte\nSource : console DRMNO",
  "bot"
);

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = input.value.trim();
  if (!message) return;
  await ask(message);
});

input.addEventListener("input", autosize);

input.addEventListener("keydown", async (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    const message = input.value.trim();
    if (!message || sendBtn.disabled) return;
    await ask(message);
  }
});

chips.addEventListener("click", async (event) => {
  const btn = event.target.closest("button[data-q]");
  if (!btn || sendBtn.disabled) return;
  await ask(btn.dataset.q);
});

vigilanceMap.addEventListener("click", async (event) => {
  const pin = event.target.closest(".map-pin");
  if (!pin || sendBtn.disabled) return;
  vigilanceMap.querySelectorAll(".map-pin").forEach((el) => el.classList.remove("is-active"));
  pin.classList.add("is-active");
  await ask(`Alerte à ${pin.dataset.place}`);
});

updateClock();
setInterval(updateClock, 30000);
refreshHealth();
refreshDashboard();
setInterval(refreshHealth, 30000);
setInterval(refreshDashboard, 60000);
autosize();
input.focus();
