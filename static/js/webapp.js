(() => {
  const form = document.getElementById("optimize-form");
  if (!form) return;

  const submitButton = document.getElementById("submit-button");
  const resultsNode = document.getElementById("results");
  const tooltipTitle = document.getElementById("tooltip-title");
  const tooltipBody = document.getElementById("tooltip-body");
  const tooltipMeta = document.getElementById("tooltip-meta");
  const roastSelect = document.getElementById("roast");
  const tempInput = document.getElementById("temp");
  const brewerSelect = document.getElementById("brewer");
  const doseMinInput = document.getElementById("dose_min");
  const doseMaxInput = document.getElementById("dose_max");

  const ATTRIBUTES = window.APP_ATTRIBUTES || [];
  const AXIS_VIEW = window.APP_AXIS_VIEW || {};
  const DEADBAND = window.APP_ORDINAL_DEADBAND || 0.01;
  const mobileControlsQuery = window.matchMedia("(max-width: 640px)");
  const mobileLayoutQuery = window.matchMedia("(max-width: 880px)");

  let currentDetailIndex = 0;
  let latestPayload = null;
  let steepTimer = null;        // { index, elapsedMs, running, lastTick, target }
  let steepInterval = null;
  // fb form state, keyed by slot — prefill + comparison context
  const fbState = {};

  // ── attribute / group display labels ────────────────────────────────
  const ATTR_ZH = {
    "Sour": "酸", "Citrus": "柑橘", "Tea.floral": "花茶香", "Sweet": "甜",
    "Cereal": "穀物", "Thick.viscous": "醇厚", "Bitter": "苦",
    "Astringent": "澀", "Burnt": "焦香", "Dark.chocolate": "黑巧克力",
  };
  const GROUP_ZH = {
    "acidity": "酸質", "sweetness": "甜感", "body": "醇厚度",
    "bitterness": "苦味", "astringency": "澀感", "roast": "焙烤調",
    "character": "個性香氣",
  };
  const ROAST_COLOR = {
    "light": "#b45309", "medium_light": "#1d4ed8",
    "medium": "#3f6b3a", "moderately_dark": "#5b3a2e",
  };

  const fieldHelp = {
    brewer: {
      title: "器材尺寸",
      body: "AeroPress 標準版（200ml）或 XL（400ml）。Layer 1 只看水量與粉量比例 —— 同沖煮比例下兩者 TDS/EY 相同。",
      meta: "XL 豆量步進 1g、標準版 0.5g。",
    },
    roast: {
      title: "焙度",
      body: "每個焙度有一份 per-roast 的 10 屬性感官 IDEAL（data/ideal.json）。系統會搜尋最接近該 IDEAL 的配方。",
      meta: "medium_light = 使用者 ⭐5 校準；其餘焙度多為佔位，待 feedback 校準。",
    },
    temp: {
      title: "沖煮水溫",
      body: "水溫是最佳化的『輸入』，不是被搜尋的維度 —— 它只透過 Layer 1 的 EY/TDS 影響風味。切換焙度時會自動帶入該焙度的慣例預設。",
      meta: "預設僅為慣例（淺焙熱、深焙涼）+ 安全，非推導最佳值；可依口味自行調整。",
    },
    top: {
      title: "Top N",
      body: "回傳幾組最接近 IDEAL 的配方，依距離由近到遠排序。",
      meta: "比較前幾名通常 3 就夠。",
    },
    dose_range: {
      title: "豆量區間",
      body: "手動限制搜尋的豆量範圍（克）。留空則用該焙度的預設區間。只填一端也可以。",
      meta: "例如手上只剩 18g，填 max=18 就不會超量。",
    },
  };

  function showHelp(key) {
    if (key === "roast") {
      const opt = (window.APP_ROAST_OPTIONS || []).find(o => o.code === roastSelect.value);
      if (opt) {
        tooltipTitle.textContent = "焙度";
        tooltipBody.textContent = opt.note;
        tooltipMeta.textContent = fieldHelp.roast.meta;
        return;
      }
    }
    const entry = fieldHelp[key];
    if (!entry) return;
    tooltipTitle.textContent = entry.title;
    tooltipBody.textContent = entry.body;
    tooltipMeta.textContent = entry.meta;
  }

  function escapeHtml(text) {
    return String(text == null ? "" : text).replace(/[&<>"']/g, (ch) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[ch]);
  }

  function formatTime(seconds) {
    const total = Math.round(seconds || 0);
    return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
  }

  // ── sensory-group arithmetic (model prefill of the questionnaire) ────
  function groupValue(attrs, group) {
    const members = AXIS_VIEW[group] || [];
    if (!attrs || !members.length) return null;
    let sum = 0, n = 0;
    for (const a of members) {
      if (typeof attrs[a] === "number") { sum += attrs[a]; n += 1; }
    }
    return n ? sum / n : null;
  }

  // per-attribute: ">" / "<" direction, or "?" = within dead-band (no signal)
  function ordinalSign(delta) {
    if (delta > DEADBAND) return ">";
    if (delta < -DEADBAND) return "<";
    return "?";
  }

  // model's predicted >/=/< per questionnaire group, comparing two attr sets
  function computePrefill(thisAttrs, comparedAttrs) {
    if (!thisAttrs || !comparedAttrs) return null;
    const out = {};
    for (const group of Object.keys(AXIS_VIEW)) {
      const a = groupValue(thisAttrs, group);
      const b = groupValue(comparedAttrs, group);
      if (a == null || b == null) continue;
      out[group] = ordinalSign(a - b);
    }
    return Object.keys(out).length ? out : null;
  }

  // ════════════════ LOGBOOK / history modal ════════════════
  let historyCache = { entries: [], fetchedAt: 0 };
  let historyFilters = { roast: "__all__", minStars: 0 };
  let editingTimestamp = null;
  const HISTORY_EDIT_WINDOW_HOURS = 1;

  function historyEditRemainingHours(entry) {
    if (!entry.timestamp) return null;
    const created = new Date(entry.timestamp).getTime();
    if (isNaN(created)) return null;
    const remain = HISTORY_EDIT_WINDOW_HOURS - (Date.now() - created) / 3_600_000;
    return remain > 0 ? remain : null;
  }

  function formatHistoryTime(iso) {
    if (!iso) return "—";
    const then = new Date(iso);
    if (isNaN(then.getTime())) return iso.slice(0, 10);
    const ymd = iso.slice(0, 10);
    const diffDays = Math.floor((new Date() - then) / 86400000);
    if (diffDays < 0) return ymd;
    if (diffDays === 0) return `今天 · ${ymd}`;
    if (diffDays === 1) return `昨天 · ${ymd}`;
    if (diffDays < 7) return `${diffDays} 天前 · ${ymd}`;
    return ymd;
  }

  function ordinalGlyph(sign) {
    if (sign === ">") return "▲";
    if (sign === "<") return "▼";
    if (sign === "?") return "?";
    return "=";
  }

  function applyHistoryFilters(entries) {
    return entries.filter((e) => {
      if (historyFilters.roast !== "__all__" && e.roast !== historyFilters.roast) return false;
      if (historyFilters.minStars > 0 && (!e.stars || e.stars < historyFilters.minStars)) return false;
      return true;
    });
  }

  // best = highest stars; tie-break by smallest recomputed distance
  function findBestTimestamp(entries) {
    let best = null;
    for (const e of entries) {
      if (!e.stars) continue;
      if (!best) { best = e; continue; }
      const d = (e.recipe && e.recipe.distance != null) ? e.recipe.distance : Infinity;
      const bd = (best.recipe && best.recipe.distance != null) ? best.recipe.distance : Infinity;
      if (e.stars > best.stars || (e.stars === best.stars && d < bd)) best = e;
    }
    return best ? best.timestamp : null;
  }

  function timestampShort(iso) {
    if (!iso) return "—";
    return iso.slice(5, 16).replace("T", " ");
  }

  function renderComparisonSummary(entry) {
    if (!entry.overall && !entry.attributes_vs) return "";
    const ref = entry.compared_to
      ? `對照 ${timestampShort(entry.compared_to)}`
      : "對照上一杯";
    const overall = entry.overall
      ? `<span class="hist-cmp-overall hist-cmp-${entry.overall === ">" ? "up" : entry.overall === "<" ? "down" : "eq"}">整體 ${ordinalGlyph(entry.overall)}</span>`
      : "";
    let attrs = "";
    if (entry.attributes_vs) {
      attrs = Object.entries(entry.attributes_vs).map(([g, s]) => {
        const model = entry.model_attributes_vs && entry.model_attributes_vs[g];
        // a flag only when model & user claim OPPOSITE directions; "?" = no signal
        const conflict = ((model === ">" && s === "<") || (model === "<" && s === ">"))
          ? " hist-cmp-conflict" : "";
        return `<span class="hist-cmp-attr${conflict}">${escapeHtml(GROUP_ZH[g] || g)} ${ordinalGlyph(s)}</span>`;
      }).join("");
    }
    return `
      <div class="hist-cmp">
        <span class="hist-cmp-ref">${escapeHtml(ref)}</span>
        ${overall}${attrs}
      </div>`;
  }

  function renderHistoryEntry(entry, isBest) {
    const accent = ROAST_COLOR[entry.roast] || "#5b6770";
    const time = formatHistoryTime(entry.timestamp);
    const starsHtml = entry.stars
      ? `<span class="history-entry-stars"><span class="history-entry-stars-on">${"★".repeat(entry.stars)}</span><span class="history-entry-stars-off">${"★".repeat(5 - entry.stars)}</span></span>`
      : `<span class="history-entry-stars-empty">— 未評星 —</span>`;

    const r = entry.recipe;
    const recipeLine = r
      ? `${r.temp}°C · dial ${r.dial} · ${r.dose}g · steep ${formatTime(r.steep_sec)}`
      : `<span class="history-entry-recipe-missing">舊紀錄無 brew 快照</span>`;
    const metricsLine = r && r.distance != null
      ? `距 IDEAL ${Number(r.distance).toFixed(4)}${r.tds != null ? ` · TDS ${Number(r.tds).toFixed(2)}% · EY ${Number(r.ey).toFixed(1)}%` : ""}`
      : "";

    const absoluteHtml = entry.absolute
      ? `<span class="hist-absolute hist-absolute-${entry.absolute}">單獨喝：${entry.absolute === "good" ? "好喝" : entry.absolute === "ok" ? "普通" : "不行"}</span>`
      : "";
    const tagsHtml = (entry.tags || []).length
      ? `<div class="history-entry-tags">${entry.tags.map(t => `<span>${escapeHtml(t)}</span>`).join('<span class="history-entry-tag-sep">·</span>')}</div>`
      : "";
    const commentHtml = entry.comment
      ? `<div class="history-entry-comment">${escapeHtml(entry.comment)}</div>`
      : `<div class="history-entry-comment-empty">（無感想文字）</div>`;
    const bestRibbon = isBest ? `<div class="history-entry-best">✦ 目前最佳沖煮</div>` : "";

    const isEditing = editingTimestamp === entry.timestamp;
    const remainH = historyEditRemainingHours(entry);
    const remainLabel = remainH !== null
      ? (remainH >= 1 ? `${Math.floor(remainH)}h` : `${Math.max(1, Math.ceil(remainH * 60))}m`)
      : "";
    const editTriggerHtml = (!isEditing && remainH !== null)
      ? `<div class="history-entry-edit-trigger"><button type="button" class="history-edit-open" data-edit-open="${entry.timestamp}">✎ 編輯 <span class="history-edit-remain">· 剩 ${remainLabel}</span></button></div>`
      : "";
    const editFormHtml = isEditing ? renderHistoryEditFields(entry) : "";

    return `
      <article class="history-entry" data-roast="${escapeHtml(entry.roast || "")}" data-stars="${entry.stars || 0}" style="--accent:${accent};">
        <div aria-hidden="true" class="history-entry-bar"></div>
        <div class="history-entry-body">
          <header class="history-entry-head">
            <div class="history-entry-meta">
              <span class="history-entry-time">${time}</span>
              <span class="history-entry-divider">·</span>
              ${starsHtml}
            </div>
            <div class="history-entry-id">
              <span aria-hidden="true" class="history-entry-id-dot"></span>
              <span class="history-entry-label-text">${escapeHtml(entry.roast || "")}</span>
              <span class="history-entry-divider">·</span>
              <span>${escapeHtml(entry.brewer || "")}</span>
            </div>
          </header>
          ${renderComparisonSummary(entry)}
          ${commentHtml}
          <div class="history-entry-recipe">${recipeLine}${metricsLine ? `<span class="history-entry-metrics">${metricsLine}</span>` : ""}</div>
          ${absoluteHtml}
          ${tagsHtml}
          ${bestRibbon}
          ${editTriggerHtml}
          ${editFormHtml}
        </div>
      </article>`;
  }

  function renderHistoryEditFields(entry) {
    const stars = entry.stars || 0;
    const starButtons = [1, 2, 3, 4, 5].map((n) =>
      `<button type="button" class="history-edit-star history-edit-star-btn" data-edit-star="${n}" aria-pressed="${stars >= n}">★</button>`
    ).join("");
    const absVal = entry.absolute || "";
    const absButtons = [["good", "好喝"], ["ok", "普通"], ["bad", "不行"]].map(([v, l]) =>
      `<button type="button" class="history-edit-abs" data-edit-abs="${v}" data-edit-active="${absVal === v ? "1" : "0"}">${l}</button>`
    ).join("");
    return `
      <div class="history-edit-form" data-edit-ts="${entry.timestamp}">
        <div class="history-edit-row">
          <span class="history-edit-key">星等</span>
          <div class="history-edit-stars">${starButtons}</div>
        </div>
        <div class="history-edit-row">
          <span class="history-edit-key">單獨喝</span>
          <div class="history-edit-abs-group">${absButtons}</div>
        </div>
        <div class="history-edit-block">
          <div class="history-edit-key">感想</div>
          <textarea class="history-edit-comment history-edit-comment-input" rows="3">${escapeHtml(entry.comment || "")}</textarea>
        </div>
        <div class="history-edit-actions">
          <button type="button" class="history-edit-save" data-edit-save>儲存 · SAVE</button>
          <button type="button" class="history-edit-cancel" data-edit-cancel>取消</button>
          <span class="history-edit-msg"></span>
        </div>
      </div>`;
  }

  function renderHistoryModal(entries) {
    const filtered = applyHistoryFilters(entries);
    const bestTs = findBestTimestamp(entries);
    const roastsSeen = Array.from(new Set(entries.map(e => e.roast).filter(Boolean)));

    const roastBtn = (name) => {
      const active = historyFilters.roast === name;
      const accent = ROAST_COLOR[name];
      const swatch = accent ? `<span aria-hidden="true" class="history-filter-swatch" style="color:${accent};"></span>` : "";
      return `<button type="button" class="history-filter-btn${active ? " is-active" : ""}" data-history-roast="${name}">${swatch}${name === "__all__" ? "全部" : escapeHtml(name)}</button>`;
    };
    const starBtn = (n) => {
      const active = historyFilters.minStars === n;
      return `<button type="button" class="history-filter-btn${active ? " is-active" : ""}" data-history-stars="${n}">${n === 0 ? "全部" : `★ ${n}+`}</button>`;
    };
    const dot = `<span class="history-filter-dot">·</span>`;
    const roastFilter = [roastBtn("__all__")].concat(roastsSeen.map(roastBtn)).join(dot);
    const starFilter = [0, 1, 2, 3, 4, 5].map(starBtn).join(dot);

    const body = filtered.length
      ? filtered.slice().sort((a, b) => (b.timestamp || "").localeCompare(a.timestamp || ""))
          .map(e => renderHistoryEntry(e, bestTs && e.timestamp === bestTs)).join("")
      : `<div class="history-empty"><div class="history-empty-mark" aria-hidden="true">⌬</div><div class="history-empty-text">${entries.length ? "此條件下無紀錄。" : "尚無紀錄。下一杯就是第一筆。"}</div></div>`;

    return `
      <div id="history-modal" class="history-modal">
        <div class="history-modal-panel" role="dialog" aria-modal="true" aria-labelledby="history-modal-title">
          <div class="history-modal-head">
            <div>
              <span class="history-eyebrow">§ LOGBOOK · 沖煮歷史</span>
              <h2 id="history-modal-title" class="history-title">Brewing Lab Logbook</h2>
              <p class="history-subtitle">共 ${entries.length} 筆紀錄${filtered.length !== entries.length ? `（過濾後 ${filtered.length} 筆）` : ""}</p>
            </div>
            <button id="history-modal-close" class="history-close" type="button" aria-label="關閉">×</button>
          </div>
          <div class="history-filter-strip">
            <div class="history-filter-row"><span class="history-filter-key">焙度</span><div class="history-filter-options">${roastFilter}</div></div>
            <div class="history-filter-row"><span class="history-filter-key">星等</span><div class="history-filter-options">${starFilter}</div></div>
          </div>
          <div id="history-modal-body" class="history-modal-body">${body}</div>
        </div>
      </div>`;
  }

  function attachHistoryHandlers() {
    const modal = document.getElementById("history-modal");
    if (!modal) return;
    modal.querySelector("#history-modal-close")?.addEventListener("click", closeHistoryModal);
    modal.addEventListener("click", (e) => { if (e.target === modal) closeHistoryModal(); });

    modal.querySelectorAll("[data-history-roast]").forEach((btn) => {
      btn.addEventListener("click", () => { historyFilters.roast = btn.dataset.historyRoast; rerenderHistoryModal(); });
    });
    modal.querySelectorAll("[data-history-stars]").forEach((btn) => {
      btn.addEventListener("click", () => { historyFilters.minStars = Number(btn.dataset.historyStars); rerenderHistoryModal(); });
    });
    modal.querySelectorAll("[data-edit-open]").forEach((btn) => {
      btn.addEventListener("click", () => {
        editingTimestamp = btn.dataset.editOpen;
        rerenderHistoryModal();
        document.querySelector(`.history-edit-form[data-edit-ts="${editingTimestamp}"] .history-edit-comment`)?.focus();
      });
    });
    modal.querySelectorAll("[data-edit-cancel]").forEach((btn) => {
      btn.addEventListener("click", () => { editingTimestamp = null; rerenderHistoryModal(); });
    });
    modal.querySelectorAll(".history-edit-star").forEach((btn) => {
      btn.addEventListener("click", () => {
        const f = btn.closest(".history-edit-form");
        if (!f) return;
        const current = Number(btn.dataset.editStar);
        const allOn = f.querySelectorAll('.history-edit-star[aria-pressed="true"]');
        const target = (allOn.length === current && btn.getAttribute("aria-pressed") === "true") ? 0 : current;
        f.querySelectorAll(".history-edit-star").forEach((b) => {
          b.setAttribute("aria-pressed", Number(b.dataset.editStar) <= target ? "true" : "false");
        });
      });
    });
    modal.querySelectorAll(".history-edit-abs").forEach((btn) => {
      btn.addEventListener("click", () => {
        const on = btn.dataset.editActive === "1";
        btn.closest(".history-edit-abs-group").querySelectorAll(".history-edit-abs")
          .forEach((b) => { b.dataset.editActive = "0"; });
        btn.dataset.editActive = on ? "0" : "1";
      });
    });
    modal.querySelectorAll("[data-edit-save]").forEach((btn) => {
      btn.addEventListener("click", () => submitHistoryEdit(btn));
    });
  }

  async function submitHistoryEdit(btn) {
    const f = btn.closest(".history-edit-form");
    if (!f) return;
    const ts = f.dataset.editTs;
    const msg = f.querySelector(".history-edit-msg");
    const starCount = f.querySelectorAll('.history-edit-star[aria-pressed="true"]').length;
    const stars = starCount > 0 ? starCount : null;
    const absBtn = f.querySelector('.history-edit-abs[data-edit-active="1"]');
    const absolute = absBtn ? absBtn.dataset.editAbs : null;
    const comment = (f.querySelector(".history-edit-comment").value || "").trim();

    if (!comment && stars === null && !absolute) {
      msg.textContent = "至少填一項（星等 / 單獨喝 / 感想）";
      msg.style.color = "var(--amber)";
      return;
    }
    btn.disabled = true;
    msg.textContent = "儲存中…";
    msg.style.color = "var(--ink-mute)";
    try {
      const resp = await fetch("/api/feedback/update", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ timestamp: ts, stars, absolute, comment }),
      });
      const data = await resp.json();
      if (!resp.ok || !data.ok) throw new Error(data.error || "save failed");
      const idx = historyCache.entries.findIndex((e) => e.timestamp === ts);
      if (idx >= 0) historyCache.entries[idx] = data.entry;
      editingTimestamp = null;
      rerenderHistoryModal();
    } catch (err) {
      msg.textContent = `失敗：${err.message || err}`;
      msg.style.color = "var(--amber)";
      btn.disabled = false;
    }
  }

  function rerenderHistoryModal() {
    const existing = document.getElementById("history-modal");
    if (!existing) return;
    const scrollTop = existing.querySelector("#history-modal-body")?.scrollTop || 0;
    const wrap = document.createElement("div");
    wrap.innerHTML = renderHistoryModal(historyCache.entries);
    existing.replaceWith(wrap.firstElementChild);
    attachHistoryHandlers();
    const b = document.querySelector("#history-modal-body");
    if (b) b.scrollTop = scrollTop;
  }

  async function fetchHistory() {
    try {
      const r = await fetch("/api/feedback");
      const d = await r.json();
      historyCache = { entries: d.entries || [], fetchedAt: Date.now() };
    } catch (e) {
      historyCache = { entries: historyCache.entries, fetchedAt: Date.now() };
    }
    updateHistoryButtonCount();
    return historyCache.entries;
  }

  function updateHistoryButtonCount() {
    const counter = document.querySelector("#history-trigger .history-count");
    if (counter) counter.textContent = `(${historyCache.entries.length})`;
  }

  async function openHistoryModal() {
    await fetchHistory();
    document.getElementById("history-modal")?.remove();
    const wrap = document.createElement("div");
    wrap.innerHTML = renderHistoryModal(historyCache.entries);
    document.body.appendChild(wrap.firstElementChild);
    document.body.style.overflow = "hidden";
    attachHistoryHandlers();
    document.getElementById("history-modal-close")?.focus();
  }

  function closeHistoryModal() {
    document.getElementById("history-modal")?.remove();
    document.body.style.overflow = "";
    editingTimestamp = null;
  }

  function mountHistoryTrigger() {
    const btn = document.getElementById("history-trigger");
    if (!btn || btn.dataset.bound === "1") return;
    btn.dataset.bound = "1";
    btn.addEventListener("click", (e) => { e.stopPropagation(); openHistoryModal(); });
  }

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && document.getElementById("history-modal")) closeHistoryModal();
  });

  // ════════════════ STEEP TIMER ════════════════
  function renderSteepTimer(result, index) {
    return `
      <div class="specimen-section">
        <span class="specimen-section-title">STEEP TIMER · 浸泡計時</span>
        <span class="specimen-section-aside">目標浸泡 ${formatTime(result.steep_sec)}</span>
      </div>
      <div class="timer">
        <div class="timer-display" id="timer-display-${index}">0:00</div>
        <div class="timer-status" id="timer-status-${index}">注水 → 插活塞 1cm → 按下開始</div>
        <div class="timer-controls">
          <button class="timer-btn timer-btn-primary" type="button" data-timer-toggle="${index}">▶ 開始</button>
          <button class="timer-btn" type="button" data-timer-reset="${index}">↻ 重置</button>
        </div>
      </div>`;
  }

  function syncSteepTimerUI() {
    if (!steepTimer) return;
    const { index, target } = steepTimer;
    const display = document.getElementById(`timer-display-${index}`);
    const status = document.getElementById(`timer-status-${index}`);
    if (!display || !status) return;
    const elapsedSec = steepTimer.elapsedMs / 1000;
    display.textContent = formatTime(elapsedSec);
    status.classList.toggle("is-running", steepTimer.running);
    if (elapsedSec >= target) {
      display.textContent = formatTime(target);
      status.textContent = "浸泡完成 — 旋轉後穩定下壓";
      status.classList.add("is-done");
    } else {
      status.classList.remove("is-done");
      const left = Math.ceil(target - elapsedSec);
      status.textContent = steepTimer.running ? `浸泡中 · 剩餘 ${left}s` : `已暫停 · 剩餘 ${left}s`;
    }
  }

  function tickSteep() {
    if (!steepTimer || !steepTimer.running) return;
    const now = Date.now();
    steepTimer.elapsedMs += now - steepTimer.lastTick;
    steepTimer.lastTick = now;
    if (steepTimer.elapsedMs >= steepTimer.target * 1000) {
      steepTimer.elapsedMs = steepTimer.target * 1000;
      steepTimer.running = false;
      const btn = document.querySelector(`[data-timer-toggle="${steepTimer.index}"]`);
      if (btn) btn.textContent = "↻ 重新開始";
      clearInterval(steepInterval);
      steepInterval = null;
    }
    syncSteepTimerUI();
  }

  function toggleSteepTimer(index, result) {
    if (!steepTimer || steepTimer.index !== index) {
      steepTimer = { index, elapsedMs: 0, running: false, lastTick: 0, target: result.steep_sec };
    }
    const btn = document.querySelector(`[data-timer-toggle="${index}"]`);
    if (steepTimer.running) {
      steepTimer.running = false;
      if (btn) btn.textContent = "▶ 繼續";
      clearInterval(steepInterval);
      steepInterval = null;
    } else {
      if (steepTimer.elapsedMs >= steepTimer.target * 1000) steepTimer.elapsedMs = 0;
      steepTimer.running = true;
      steepTimer.lastTick = Date.now();
      if (btn) btn.textContent = "‖ 暫停";
      steepInterval = setInterval(tickSteep, 100);
    }
    syncSteepTimerUI();
  }

  function resetSteepTimer(index, result) {
    clearInterval(steepInterval);
    steepInterval = null;
    steepTimer = { index, elapsedMs: 0, running: false, lastTick: 0, target: result.steep_sec };
    const btn = document.querySelector(`[data-timer-toggle="${index}"]`);
    if (btn) btn.textContent = "▶ 開始";
    syncSteepTimerUI();
  }

  // ════════════════ RESULT CARDS ════════════════
  function renderMasterCards(results) {
    if (!results || results.length <= 1) return "";
    const cards = results.map((r, i) => {
      const sel = i === currentDetailIndex ? " is-selected" : "";
      const tag = i === currentDetailIndex ? " · 顯示中" : "";
      return `
        <div class="master-card${sel}" data-select-recipe="${i}">
          <div class="master-card-rank">Rank ${i + 1}${tag}</div>
          <div class="master-card-score">${r.distance.toFixed(4)}</div>
          <div class="master-card-scorelabel">距 IDEAL</div>
          <div class="master-card-meta">${r.temp}°C · dial ${r.dial} · ${r.dose}g<br>steep ${formatTime(r.steep_sec)}</div>
        </div>`;
    }).join("");
    return `<div class="master-strip">${cards}</div>`;
  }

  function attributeRows(result) {
    const attrs = result.attributes, ideal = result.ideal;
    let scaleMax = 0.1;
    for (const a of ATTRIBUTES) scaleMax = Math.max(scaleMax, attrs[a], ideal[a]);
    scaleMax = Math.ceil(scaleMax * 20) / 20;  // round up to 0.05

    return ATTRIBUTES.map((a) => {
      const pred = attrs[a], idl = ideal[a], delta = result.deltas[a];
      const predPct = Math.max(0, Math.min(100, (pred / scaleMax) * 100));
      const idealPct = Math.max(0, Math.min(100, (idl / scaleMax) * 100));
      const offClass = Math.abs(delta) >= 0.03 ? " attr-row-off" : "";
      const sign = delta > 0 ? "+" : "";
      return `
        <div class="attr-row${offClass}">
          <span class="attr-name">${escapeHtml(ATTR_ZH[a] || a)}<span class="attr-name-en">${escapeHtml(a)}</span></span>
          <span class="attr-bar-track">
            <span class="attr-bar-fill" style="width:${predPct}%;"></span>
            <span class="attr-bar-ideal" style="left:${idealPct}%;" title="IDEAL ${idl.toFixed(3)}"></span>
          </span>
          <span class="attr-pred">${pred.toFixed(3)}</span>
          <span class="attr-delta">${sign}${delta.toFixed(3)}</span>
        </div>`;
    }).join("");
  }

  function renderSingleDetail(result, meta, index) {
    if (!result) return "";
    const accent = ROAST_COLOR[result.roast] || "#1d4ed8";
    return `
      <article class="sample" id="recipe-card-${index}" style="--accent:${accent};">
        <header class="sample-head">
          <div class="sample-no"><span>SAMPLE</span><span class="sample-no-num">№ ${String(index + 1).padStart(2, "0")}</span></div>
          <div class="sample-label">${escapeHtml(meta.roast_name || result.roast)} · ${escapeHtml(result.brewer || "")}</div>
        </header>

        <div class="score-block">
          <div class="score-display">${result.distance.toFixed(4)}</div>
          <div class="score-meta">
            <div class="score-label">距該焙度感官 IDEAL · DISTANCE</div>
            <div class="score-hint">10 屬性與目標的 RMS 距離 — 越小越接近你的理想杯。非 0–100 評分。</div>
          </div>
        </div>

        <div class="vector-grid">
          <div class="vector-cell"><span class="vector-label">TEMP · 水溫</span><span class="vector-value">${result.temp}<span class="vector-unit">°C</span></span></div>
          <div class="vector-cell"><span class="vector-label">DIAL · 研磨</span><span class="vector-value">${result.dial}</span></div>
          <div class="vector-cell"><span class="vector-label">DOSE · 粉量</span><span class="vector-value">${result.dose}<span class="vector-unit">g</span></span></div>
          <div class="vector-cell"><span class="vector-label">STEEP · 浸泡</span><span class="vector-value">${formatTime(result.steep_sec)}</span></div>
        </div>

        <div class="brew-meta">
          注水 ${result.water_ml}ml · 插活塞 1cm → 浸泡 ${formatTime(result.steep_sec)} → 旋轉 → 穩定下壓
          <span class="brew-meta-latent">內部估值 TDS ${result.tds.toFixed(2)}% · EY ${result.ey.toFixed(1)}%（粗估，非評分依據）</span>
        </div>

        ${renderSteepTimer(result, index)}

        <div class="specimen-section">
          <span class="specimen-section-title">SENSORY PROFILE · 10 感官屬性</span>
          <span class="specimen-section-aside">實線=預測 · ◆=IDEAL</span>
        </div>
        <div class="attr-list">${attributeRows(result)}</div>

        ${renderFeedbackForm(result, `detail-${index}`)}
      </article>`;
  }

  function renderResultContent(results, meta) {
    resultsNode.innerHTML = `
      <div id="master-view">${renderMasterCards(results)}</div>
      <div id="detail-view">${results[currentDetailIndex] ? renderSingleDetail(results[currentDetailIndex], meta, currentDetailIndex) : ""}</div>`;
    if (results[currentDetailIndex]) {
      resetSteepTimer(currentDetailIndex, results[currentDetailIndex]);
    }
    attachFeedbackHandlers();
  }

  function renderResults(payload) {
    latestPayload = payload;
    clearInterval(steepInterval);
    steepInterval = null;
    steepTimer = null;
    const { meta, results } = payload || {};
    if (payload && payload.error) {
      resultsNode.innerHTML = `<div class="empty-state"><div class="empty-title">計算失敗</div><p class="empty-instructions">${escapeHtml(payload.error)}</p></div>`;
      return;
    }
    if (!results || !results.length) {
      resultsNode.innerHTML = `<div class="empty-state"><div class="empty-title">沒有可用結果</div></div>`;
      return;
    }
    currentDetailIndex = 0;
    renderResultContent(results, meta);
  }

  // ════════════════ §4 FEEDBACK QUESTIONNAIRE ════════════════
  function comparedToOptions(currentRecipeId) {
    const entries = (historyCache.entries || [])
      .slice()
      .sort((a, b) => (b.timestamp || "").localeCompare(a.timestamp || ""))
      .slice(0, 12);
    const opts = entries.map((e) => {
      const r = e.recipe;
      const desc = r ? `${r.temp}°C/dial ${r.dial}/${r.dose}g/${formatTime(r.steep_sec)}` : "無快照";
      return `<option value="${escapeHtml(e.timestamp)}">${timestampShort(e.timestamp)} · ${escapeHtml(e.roast || "")} · ${escapeHtml(desc)}</option>`;
    }).join("");
    return `<option value="">（無 — 第一杯 / 不比較）</option>${opts}`;
  }

  function choiceGroup(slot, key, choices, selected) {
    return `<div class="q-choices" data-q-slot="${slot}" data-q-key="${key}">` +
      choices.map(([v, l]) => `<button type="button" class="q-choice${v === selected ? " is-on" : ""}" data-q-value="${v}">${l}</button>`).join("") +
      `</div>`;
  }

  function attrGroupRows(slot) {
    return Object.keys(AXIS_VIEW).map((g) => `
      <div class="q-attr-row" data-q-group="${g}">
        <span class="q-attr-name">${escapeHtml(GROUP_ZH[g] || g)}
          <span class="q-attr-model" data-q-model="${g}"></span></span>
        ${choiceGroup(slot, `attr-${g}`, [[">", "更多"], ["?", "沒注意到"], ["<", "更少"]], null)}
      </div>`).join("");
  }

  function renderFeedbackForm(result, slot) {
    const rid = result.recipe_id;
    if (!rid) return "";
    return `
      <details class="feedback fb-section" data-fb-slot="${slot}" data-fb-recipe="${rid}">
        <summary class="feedback-summary">TASTING · 我泡過了 — 對照問卷</summary>
        <div class="feedback-form">
          <div class="q-row">
            <span class="q-row-label">對照哪一杯 · COMPARED TO</span>
            <select class="q-compared" data-q-slot="${slot}">${comparedToOptions(rid)}</select>
            <p class="q-hint">挑你『上一杯』的紀錄；逐屬性會由模型先預填，你只改不準的。</p>
          </div>

          <div class="q-pairwise" data-q-slot="${slot}" hidden>
            <div class="q-row">
              <span class="q-row-label">整體偏好 · 這杯 vs 上一杯</span>
              ${choiceGroup(slot, "overall", [[">", "較好 ▲"], ["=", "差不多"], ["<", "較差 ▼"]], null)}
            </div>
            <div class="q-row">
              <span class="q-row-label">逐屬性 · 這杯比上一杯…（模型已預填）</span>
              <div class="q-attrs">${attrGroupRows(slot)}</div>
              <p class="q-hint">「沒注意到」= 沒把握，不計入後續模型矯正；只有明確的更多 / 更少才算訊號。</p>
            </div>
          </div>

          <div class="q-row">
            <span class="q-row-label">單獨喝這杯如何 · ABSOLUTE（偶爾填）</span>
            ${choiceGroup(slot, "absolute", [["good", "好喝"], ["ok", "普通"], ["bad", "不行"]], null)}
          </div>
          <div class="q-row">
            <span class="q-row-label">感想 · COMMENT（主要 input）</span>
            <textarea class="q-comment" data-q-slot="${slot}" rows="3" placeholder="例：「body 比上一杯扎實，但花香被壓掉」、「尾韻乾」、「下次想試 dial 高一點」…"></textarea>
          </div>
          <div class="q-row q-row-inline">
            <span class="q-row-label">星等 · STARS（選填、非搜尋訊號）</span>
            <div class="q-stars" data-q-slot="${slot}">
              ${[1, 2, 3, 4, 5].map(n => `<button type="button" class="q-star" data-q-star="${n}">★</button>`).join("")}
            </div>
          </div>
          <div class="q-actions">
            <button type="button" class="q-save" data-q-slot="${slot}">儲存 · SAVE</button>
            <span class="q-msg" data-q-slot="${slot}"></span>
          </div>
          <div class="q-history" data-q-slot="${slot}">${renderFeedbackList(result.feedback)}</div>
        </div>
      </details>`;
  }

  function renderFeedbackList(feedback) {
    if (!feedback || !feedback.length) return "";
    return feedback.slice().reverse().map((f) => {
      const date = (f.timestamp || "").slice(0, 10);
      const stars = f.stars ? ` · ${"★".repeat(f.stars)}` : "";
      const overall = f.overall ? ` · 整體 ${ordinalGlyph(f.overall)}` : "";
      const absolute = f.absolute ? ` · ${f.absolute}` : "";
      const comment = f.comment ? `<div class="fb-comment">「${escapeHtml(f.comment)}」</div>` : "";
      return `<div class="fb-entry"><div class="fb-meta">${date}${stars}${overall}${absolute}</div>${comment}</div>`;
    }).join("");
  }

  // recompute the model prefill for a slot from the chosen compared cup
  function refreshPrefill(slot) {
    const section = document.querySelector(`.fb-section[data-fb-slot="${slot}"]`);
    if (!section) return;
    const recipeId = section.dataset.fbRecipe;
    const result = findResultByRecipeId(recipeId);
    const select = section.querySelector(`.q-compared[data-q-slot="${slot}"]`);
    const pairwise = section.querySelector(`.q-pairwise[data-q-slot="${slot}"]`);
    const comparedTs = select ? select.value : "";

    fbState[slot] = fbState[slot] || {};
    fbState[slot].comparedTo = comparedTs || null;

    if (!comparedTs) {
      fbState[slot].prefill = null;
      if (pairwise) pairwise.hidden = true;
      return;
    }
    if (pairwise) pairwise.hidden = false;

    const comparedEntry = (historyCache.entries || []).find(e => e.timestamp === comparedTs);
    const comparedAttrs = comparedEntry && comparedEntry.recipe ? comparedEntry.recipe.attributes : null;
    const prefill = (result && comparedAttrs) ? computePrefill(result.attributes, comparedAttrs) : null;
    fbState[slot].prefill = prefill;

    // apply prefill to the per-group choice buttons + the "model said" tag
    Object.keys(AXIS_VIEW).forEach((g) => {
      const sign = prefill ? prefill[g] : null;
      const groupBox = section.querySelector(`.q-choices[data-q-key="attr-${g}"]`);
      if (groupBox) {
        groupBox.querySelectorAll(".q-choice").forEach((b) => {
          b.classList.toggle("is-on", sign != null && b.dataset.qValue === sign);
        });
      }
      const modelTag = section.querySelector(`[data-q-model="${g}"]`);
      if (modelTag) modelTag.textContent = sign ? `模型：${ordinalGlyph(sign)}` : (comparedAttrs ? "" : "無快照");
    });
  }

  function attachFeedbackHandlers() {
    document.querySelectorAll(".q-compared").forEach((sel) => {
      if (sel.dataset.bound === "1") return;
      sel.dataset.bound = "1";
      sel.addEventListener("change", () => refreshPrefill(sel.dataset.qSlot));
    });
    document.querySelectorAll(".q-choice").forEach((btn) => {
      if (btn.dataset.bound === "1") return;
      btn.dataset.bound = "1";
      btn.addEventListener("click", () => {
        const box = btn.closest(".q-choices");
        const wasOn = btn.classList.contains("is-on");
        box.querySelectorAll(".q-choice").forEach((b) => b.classList.remove("is-on"));
        if (!wasOn) btn.classList.add("is-on");
      });
    });
    document.querySelectorAll(".q-star").forEach((btn) => {
      if (btn.dataset.bound === "1") return;
      btn.dataset.bound = "1";
      btn.addEventListener("click", () => {
        const box = btn.closest(".q-stars");
        const n = Number(btn.dataset.qStar);
        const currentOn = box.querySelectorAll(".q-star.is-on").length;
        const target = (currentOn === n) ? 0 : n;
        box.querySelectorAll(".q-star").forEach((b) => {
          b.classList.toggle("is-on", Number(b.dataset.qStar) <= target);
        });
      });
    });
    document.querySelectorAll(".q-save").forEach((btn) => {
      if (btn.dataset.bound === "1") return;
      btn.dataset.bound = "1";
      btn.addEventListener("click", () => submitFeedback(btn.dataset.qSlot, btn));
    });
    // initialise prefill / pairwise visibility for every freshly-rendered form
    document.querySelectorAll(".fb-section").forEach((s) => refreshPrefill(s.dataset.fbSlot));
  }

  function readChoice(slot, key) {
    const box = document.querySelector(`.q-choices[data-q-slot="${slot}"][data-q-key="${key}"]`);
    if (!box) return null;
    const on = box.querySelector(".q-choice.is-on");
    return on ? on.dataset.qValue : null;
  }

  async function submitFeedback(slot, btn) {
    const section = document.querySelector(`.fb-section[data-fb-slot="${slot}"]`);
    if (!section) return;
    const msg = document.querySelector(`.q-msg[data-q-slot="${slot}"]`);
    const recipeId = section.dataset.fbRecipe;
    const result = findResultByRecipeId(recipeId);
    if (!result) { msg.textContent = "找不到配方"; msg.style.color = "var(--amber)"; return; }

    const comparedTo = (fbState[slot] && fbState[slot].comparedTo) || null;
    const overall = comparedTo ? readChoice(slot, "overall") : null;
    const absolute = readChoice(slot, "absolute");
    const comment = (section.querySelector(`.q-comment[data-q-slot="${slot}"]`).value || "").trim();
    const starsOn = section.querySelectorAll(`.q-stars[data-q-slot="${slot}"] .q-star.is-on`).length;
    const stars = starsOn > 0 ? starsOn : null;

    let attributesVs = null;
    if (comparedTo) {
      attributesVs = {};
      Object.keys(AXIS_VIEW).forEach((g) => {
        const v = readChoice(slot, `attr-${g}`);
        if (v) attributesVs[g] = v;
      });
      if (!Object.keys(attributesVs).length) attributesVs = null;
    }
    const modelAttributesVs = comparedTo ? (fbState[slot] && fbState[slot].prefill) || null : null;

    if (!comment && !overall && !attributesVs && !absolute && !stars) {
      msg.textContent = "請至少填一項（整體 / 逐屬性 / 單獨喝 / 感想 / 星等）";
      msg.style.color = "var(--amber)";
      return;
    }
    btn.disabled = true;
    msg.textContent = "儲存中…";
    msg.style.color = "var(--ink-mute)";

    const body = {
      recipe_id: recipeId,
      roast: result.roast,
      brewer: result.brewer_size,
      recipe: {
        temp: result.temp, dial: result.dial, dose: result.dose,
        steep_sec: result.steep_sec, tds: result.tds, ey: result.ey,
        distance: result.distance,
      },
      compared_to: comparedTo,
      overall, attributes_vs: attributesVs, model_attributes_vs: modelAttributesVs,
      absolute, comment, stars,
    };
    try {
      const resp = await fetch("/api/feedback", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await resp.json();
      if (!resp.ok || !data.ok) throw new Error(data.error || "save failed");
      const mount = section.querySelector(`.q-history[data-q-slot="${slot}"]`);
      if (mount) mount.insertAdjacentHTML("afterbegin", renderFeedbackList([data.entry]));
      section.querySelector(`.q-comment[data-q-slot="${slot}"]`).value = "";
      section.querySelectorAll(`.q-choice.is-on, .q-star.is-on`).forEach((b) => b.classList.remove("is-on"));
      msg.textContent = "✓ 已儲存";
      msg.style.color = "var(--lichen)";
      await fetchHistory();
      // refresh the compared-to dropdowns now that a new entry exists
      document.querySelectorAll(".q-compared").forEach((sel) => {
        const keep = sel.value;
        const owner = sel.dataset.qSlot;
        const ownerSection = document.querySelector(`.fb-section[data-fb-slot="${owner}"]`);
        sel.innerHTML = comparedToOptions(ownerSection ? ownerSection.dataset.fbRecipe : "");
        sel.value = keep;
      });
    } catch (err) {
      msg.textContent = `失敗：${err.message || err}`;
      msg.style.color = "var(--amber)";
    } finally {
      btn.disabled = false;
    }
  }

  function findResultByRecipeId(recipeId) {
    if (!latestPayload || !latestPayload.results) return null;
    return latestPayload.results.find((r) => r.recipe_id === recipeId) || null;
  }

  // ════════════════ WIRING ════════════════
  function syncRoastDefaults() {
    const temps = window.APP_DEFAULT_TEMPS || {};
    const def = temps[roastSelect.value];
    if (def != null && tempInput) {
      tempInput.value = def;
      const note = document.getElementById("temp-note");
      if (note) note.textContent = `已帶入 ${roastSelect.value} 慣例預設 ${def}°C — 可自行微調。`;
    }
  }

  function syncDoseStep() {
    const stepG = brewerSelect.value === "xl" ? "1" : "0.5";
    if (doseMinInput) doseMinInput.step = stepG;
    if (doseMaxInput) doseMaxInput.step = stepG;
  }

  roastSelect.addEventListener("change", () => { syncRoastDefaults(); showHelp("roast"); });
  brewerSelect.addEventListener("change", syncDoseStep);
  syncDoseStep();
  syncRoastDefaults();

  document.querySelectorAll("[data-help-key] input, [data-help-key] select").forEach((el) => {
    const key = el.closest("[data-help-key]").dataset.helpKey;
    el.addEventListener("focus", () => showHelp(key));
  });
  document.querySelectorAll("[data-help-target]").forEach((b) => {
    b.addEventListener("click", () => showHelp(b.dataset.helpTarget));
  });

  resultsNode.addEventListener("click", (event) => {
    const sel = event.target.closest("[data-select-recipe]");
    if (sel) {
      const idx = Number(sel.dataset.selectRecipe);
      if (idx !== currentDetailIndex && latestPayload && latestPayload.results) {
        currentDetailIndex = idx;
        renderResultContent(latestPayload.results, latestPayload.meta);
        const dv = document.getElementById("detail-view");
        if (dv) window.scrollTo({ top: dv.getBoundingClientRect().top + window.scrollY - 20, behavior: "smooth" });
      }
      return;
    }
    const toggle = event.target.closest("[data-timer-toggle]");
    if (toggle) {
      const idx = Number(toggle.dataset.timerToggle);
      const r = latestPayload && latestPayload.results ? latestPayload.results[idx] : null;
      if (r) toggleSteepTimer(idx, r);
      return;
    }
    const reset = event.target.closest("[data-timer-reset]");
    if (reset) {
      const idx = Number(reset.dataset.timerReset);
      const r = latestPayload && latestPayload.results ? latestPayload.results[idx] : null;
      if (r) resetSteepTimer(idx, r);
    }
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (document.activeElement instanceof HTMLElement) document.activeElement.blur();
    if (mobileControlsQuery.matches) {
      requestAnimationFrame(() => resultsNode.scrollIntoView({ behavior: "smooth", block: "start" }));
    }
    submitButton.disabled = true;
    const labelEl = submitButton.querySelector(".submit-label");
    const arrowEl = submitButton.querySelector(".submit-arrow");
    const origLabel = labelEl ? labelEl.textContent : "";
    const origArrow = arrowEl ? arrowEl.textContent : "";
    if (labelEl) labelEl.textContent = "COMPUTING · 計算中";
    if (arrowEl) arrowEl.textContent = "…";

    const payload = Object.fromEntries(new FormData(form).entries());
    ["top", "temp", "dose_min", "dose_max"].forEach((k) => {
      payload[k] = payload[k] === "" || payload[k] == null ? null : Number(payload[k]);
    });
    try {
      await fetchHistory();  // so the compared-to dropdowns are fresh
      const resp = await fetch("/api/optimize", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await resp.json();
      renderResults(data);
    } catch (error) {
      resultsNode.innerHTML = `<div class="empty-state"><div class="empty-title">計算失敗</div><p class="empty-instructions">${escapeHtml(String(error))}</p></div>`;
    } finally {
      submitButton.disabled = false;
      if (labelEl) labelEl.textContent = origLabel;
      if (arrowEl) arrowEl.textContent = origArrow;
    }
  });

  showHelp("brewer");
  mountHistoryTrigger();
  fetchHistory();
})();
