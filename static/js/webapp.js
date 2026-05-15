(() => {
  const form = document.getElementById("optimize-form");
  if (!form) return;

  const presetSelect = document.getElementById("preset");
  const ghInput = document.getElementById("gh");
  const khInput = document.getElementById("kh");
  const mgInput = document.getElementById("mg_frac");
  const submitButton = document.getElementById("submit-button");
  const resultsNode = document.getElementById("results");

  const radarModal = document.getElementById("radar-modal");
  const radarClose = document.getElementById("radar-close");
  const radarNode = document.getElementById("radar");
  const radarLegend = document.getElementById("radar-legend");
  const tooltipTitle = document.getElementById("tooltip-title");
  const tooltipBody = document.getElementById("tooltip-body");
  const tooltipMeta = document.getElementById("tooltip-meta");
  const controlsPanel = document.querySelector("[data-controls-panel]");
  const controlsBody = document.querySelector("[data-controls-body]");
  const controlsToggle = document.querySelector("[data-controls-toggle]");

  const presets = window.APP_PRESETS || {};
  const keys = ["AC", "SW", "PS", "CA", "CGA", "MEL"];
  const mobileControlsQuery = window.matchMedia("(max-width: 640px)");

  let currentDetailIndex = 0;
  let latestPayload = null;
  let latestRadarResults = [];
  let mobileControlsHidden = false;
  let brewTimerInterval = null;
  let activeTimers = {};

  const fieldHelp = {
    brewer: {
      title: "器材尺寸",
      body: "切換不同 AeroPress 容量，會影響搜尋範圍中的粉量與萃取條件。",
      meta: "一般版本與 XL 的配方尺度不同，建議先選對器材再開始比較。",
    },
    roast: {
      title: "焙度",
      body: "焙度依 SCA/SCAA 分類與 Agtron 色值對應，會改變理想風味向量與苦甜平衡。",
      meta: "可依豆袋上的 Agtron 或 SCA 等級選擇；無測量時可從 Medium (M) 開始。",
    },
    preset: {
      title: "水質預設",
      body: "選擇常見水配方後，會自動回填 GH、KH 與 Mg 比例。",
      meta: "若想微調，可先套用預設再手動修改數值。",
    },
    gh: {
      title: "GH",
      body: "總硬度代表鈣鎂離子含量，會影響萃取效率、甜感與結構。",
      meta: "常見起手值可先放在 40 到 100 ppm 附近。",
    },
    kh: {
      title: "KH",
      body: "碳酸鹽硬度代表緩衝能力，會影響酸感是否被壓掉或過度尖銳。",
      meta: "KH 過高常讓酸質變鈍，過低則可能讓杯感失去穩定性。",
    },
    mg_frac: {
      title: "Mg 比例",
      body: "用來描述 GH 中鎂占比，會牽動酸甜表現與口感輪廓。",
      meta: "常見可從 0.30 到 0.50 開始試。",
    },
    top: {
      title: "Top N",
      body: "控制回傳幾組最佳結果，方便你看多一點組合或只專注最前面的排序。",
      meta: "若主要是比較前三名，維持 3 就足夠。",
    },
    dose_range: {
      title: "豆量區間",
      body: "手動限制搜尋的豆量範圍（克）。留空則使用該焙度的預設區間。只填一端也可以：只填 min 表示下限，只填 max 表示上限。",
      meta: "例如手上只剩 18g 豆子，填 max=18 就能確保推薦不超量。",
    },
    t_env: {
      title: "環境溫度",
      body: "環境溫度會影響實際 slurry 溫度，進而影響模型中的萃取預估。",
      meta: "冬天與夏天差異明顯時，這個值值得調整。",
    },

    altitude: {
      title: "海拔",
      body: "海拔會影響沸點與實際水溫上限，因此會改變可行的沖煮溫度範圍。",
      meta: "平地可維持 0，高海拔地區再補入實際數值。",
    },
    label: {
      title: "口感方向",
      body: "Phase 8 感官 label 島：每個 label 是一份「想喝什麼」的目標（compound profile + TDS_PREFER），optimizer 會找出最接近該目標的配方。選擇「全部並列」會同時跑 4 個 label，每個 label 各印 Top 1，方便 cupping 對照。",
      meta: "balanced=Hoffman / acid-forward=April / sweet-body=Championship / coarse-modern=Hedrick。",
    },
  };

  const compoundHelp = {
    AC: {
      label: "明亮酸質",
      body: "代表杯中的活潑酸感與前段亮度，越高通常越有清晰、立體的果酸表現。",
    },
    SW: {
      label: "甜感厚度",
      body: "代表甜味與圓潤度，影響口感是否飽滿、滑順，能平衡過尖的酸質。",
    },
    PS: {
      label: "正向香氣",
      body: "代表花香、果香與乾淨香氣的強度，通常越高越能拉出愉悅的香氣層次。",
    },
    CA: {
      label: "木質苦感",
      body: "代表偏木質、乾感的苦味來源，過高時容易讓尾韻變硬、變澀。",
    },
    CGA: {
      label: "綠感刺激",
      body: "代表生澀、草本與尖銳刺激感，通常在萃取失衡時會更明顯。",
    },
    MEL: {
      label: "焙烤厚苦",
      body: "代表焙烤、焦糖化後的厚重苦甜感，適量能增加深度，過高則容易壓味。",
    },
  };

  function showHelp(key) {
    if (key === "preset") {
      const selected = presetSelect.value;
      const preset = presets[selected];
      if (selected && preset) {
        tooltipTitle.textContent = "水質預設";
        tooltipBody.textContent = preset.note || "自動填入 GH、KH 與 Mg 比例。";
        tooltipMeta.textContent = "已套用預設。若想微調，可手動修改下方數值。";
        return;
      }
    }
    if (key === "roast") {
      const selected = document.getElementById("roast").value;
      const roastOption = window.APP_ROAST_OPTIONS.find(opt => opt.code === selected);
      if (roastOption) {
        tooltipTitle.textContent = "焙度";
        tooltipBody.textContent = roastOption.note;
        tooltipMeta.textContent = "可依豆袋上的 Agtron 或 SCA 等級選擇；無測量時可從 Medium (M) 開始。";
        return;
      }
    }
    if (key === "label") {
      const selected = document.getElementById("label").value;
      if (selected === "") {
        tooltipTitle.textContent = "口感方向：全部並列 (cupping)";
        tooltipBody.textContent = "同時跑 4 個 label，每個 label 各回 Top 1 配方並列展示，方便 cupping 對照。";
        tooltipMeta.textContent = "選定單一 label 後切回單目標 Top N 模式。";
        return;
      }
      const labelOption = (window.APP_LABELS || []).find(l => l.name === selected);
      if (labelOption) {
        tooltipTitle.textContent = `口感方向：${labelOption.name}`;
        tooltipBody.textContent = labelOption.description;
        const anchor = labelOption.bullseye_anchor ? `源自 ${labelOption.bullseye_anchor} 食譜。` : "假想 label（無對應實測食譜）。";
        tooltipMeta.textContent = `${anchor} TDS 目標 ${labelOption.tds_prefer}%。`;
        return;
      }
    }
    const entry = fieldHelp[key];
    if (!entry) return;
    tooltipTitle.textContent = entry.title;
    tooltipBody.textContent = entry.body;
    tooltipMeta.textContent = entry.meta;
  }

  function syncControlsPanelState() {
    if (!controlsPanel || !controlsBody || !controlsToggle) return;

    const hiddenOnMobile = mobileControlsQuery.matches && mobileControlsHidden;
    if (hiddenOnMobile) {
      controlsPanel.classList.add("is-collapsed");
      controlsBody.hidden = true;
    } else {
      controlsPanel.classList.remove("is-collapsed");
      controlsBody.hidden = false;
    }
    controlsPanel.hidden = false; // Never hide the whole panel anymore
  }

  function setMobileControlsHidden(nextValue, { scrollToResults = false } = {}) {
    if (!mobileControlsQuery.matches) return;
    mobileControlsHidden = nextValue;
    syncControlsPanelState();

    if (nextValue && scrollToResults) {
      requestAnimationFrame(() => {
        if (resultsNode) {
          resultsNode.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      });
    }
  }

  function formatTime(seconds) {
    const total = Math.round(seconds);
    return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
  }

  // Helper to format remaining time
  function formatInlineClock(ms) {
    const totalSeconds = Math.ceil(Math.max(0, ms) / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }

  // ── 回饋區塊（Phase 10 — webapp 是唯一寫入 channel） ────────────────
  function escapeHtml(text) {
    return String(text || "").replace(/[&<>"']/g, (ch) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[ch]);
  }

  // ── 沖煮歷史 / Brewing Journal modal ─────────────────────────────
  // Design notes (5 lines):
  //   1) Editorial layout — comment is the visual hero (1.08em), metadata is engraved-small.
  //   2) Each entry sits on a 4px terracotta stripe; no card-on-card nesting.
  //   3) Label = colored dot (per-label), not a pill. Filters are text + active underline.
  //   4) Recent timestamps soften to "N 天前"; older entries show ISO date.
  //   5) Best 5-star entry by score earns a quiet "✦ 目前最佳沖煮" annotation.

  const HISTORY_LABEL_COLORS = {
    "balanced":      "#bb5f2a",
    "acid-forward":  "#d4a017",
    "sweet-body":    "#8f6a3d",
    "coarse-modern": "#6b4c32",
    "tim":           "#7d9173",
  };

  let historyCache = { entries: [], fetchedAt: 0 };
  let historyFilters = { label: "__all__", minStars: 0 };

  function formatHistoryTime(iso) {
    if (!iso) return "—";
    const then = new Date(iso);
    if (isNaN(then.getTime())) return iso.slice(0, 10);
    const ymd = iso.slice(0, 10);
    const diffDays = Math.floor((new Date() - then) / 86400000);
    if (diffDays < 0) return ymd;
    if (diffDays === 0) return `今天 · ${ymd}`;
    if (diffDays === 1) return `昨天 · ${ymd}`;
    if (diffDays < 7)   return `${diffDays} 天前 · ${ymd}`;
    return ymd;
  }

  function formatSteepShort(sec) {
    if (sec == null) return "—";
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m}:${String(s).padStart(2, "0")}`;
  }

  function applyHistoryFilters(entries) {
    return entries.filter((e) => {
      if (historyFilters.label !== "__all__" && e.label !== historyFilters.label) return false;
      if (historyFilters.minStars > 0 && (!e.stars || e.stars < historyFilters.minStars)) return false;
      return true;
    });
  }

  function findBestBrewTimestamp(entries) {
    let best = null;
    for (const e of entries) {
      if (e.stars !== 5) continue;
      const s = e.recipe && typeof e.recipe.score === "number" ? e.recipe.score : -Infinity;
      if (!best || s > (best.recipe?.score ?? -Infinity)) best = e;
    }
    return best ? best.timestamp : null;
  }

  function renderHistoryEntry(entry, isBest) {
    const accent = HISTORY_LABEL_COLORS[entry.label] || "#bb5f2a";
    const time = formatHistoryTime(entry.timestamp);

    const starsHtml = entry.stars
      ? `<span style="letter-spacing:2px;font-size:0.95em;">` +
        `<span style="color:#bb5f2a;">${"★".repeat(entry.stars)}</span>` +
        `<span style="color:#e4d7cb;">${"★".repeat(5 - entry.stars)}</span></span>`
      : `<span style="color:#c5b49e;font-size:0.85em;letter-spacing:0.05em;">— 未評星 —</span>`;

    const r = entry.recipe;
    const recipeLine = r
      ? `${r.temp}°C · dial ${r.dial} · ${r.dose}g · steep ${formatSteepShort(r.steep_sec)}`
      : `<span style="color:#a89c8a;font-style:italic;">舊紀錄無 brew 快照</span>`;
    const metricsLine = r && r.tds != null && r.ey != null && r.score != null
      ? `TDS ${r.tds.toFixed(2)}% · EY ${r.ey.toFixed(1)}% · score ${r.score.toFixed(1)}`
      : "";

    const tagsHtml = (entry.tags || []).length
      ? `<div style="margin-top:10px;font-size:0.82em;color:#7a6e5f;letter-spacing:0.02em;">
           ${entry.tags.map(t => `<span style="color:#6d6358;">${escapeHtml(t)}</span>`).join(
             '<span style="color:#d8c7b7;margin:0 6px;">·</span>'
           )}
         </div>`
      : "";

    const commentHtml = entry.comment
      ? `<div style="margin-top:14px;font-size:1.08em;line-height:1.7;color:#3a3a36;
                     font-weight:450;letter-spacing:0.005em;">
           <span style="color:#bb5f2a;margin-right:2px;">「</span>${escapeHtml(entry.comment)}<span style="color:#bb5f2a;margin-left:2px;">」</span>
         </div>`
      : `<div style="margin-top:14px;font-size:0.92em;color:#a89c8a;font-style:italic;">
           （無感想文字 — 只有快速評分）
         </div>`;

    const bestRibbon = isBest
      ? `<div style="margin-top:12px;font-size:0.72em;color:#bb5f2a;letter-spacing:0.18em;
                     text-transform:uppercase;font-weight:600;">✦ 目前最佳沖煮</div>`
      : "";

    return `
      <article class="history-entry" data-label="${entry.label}" data-stars="${entry.stars || 0}"
        style="display:flex;gap:18px;padding:24px 4px;border-bottom:1px solid #ece2d2;">
        <div aria-hidden="true" style="width:4px;background:${accent};border-radius:2px;
                                        flex-shrink:0;align-self:stretch;"></div>
        <div style="flex:1;min-width:0;">
          <header style="display:flex;justify-content:space-between;align-items:baseline;
                         flex-wrap:wrap;gap:8px 16px;font-size:0.85em;color:#6d6358;">
            <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
              <span style="font-variant-numeric:tabular-nums;">${time}</span>
              <span style="color:#d8c7b7;">·</span>
              ${starsHtml}
            </div>
            <div style="display:flex;align-items:center;gap:6px;font-size:0.85em;
                        color:#7a6e5f;letter-spacing:0.015em;">
              <span aria-hidden="true" style="display:inline-block;width:7px;height:7px;
                                              border-radius:50%;background:${accent};"></span>
              <span style="font-weight:600;color:#4e6b5b;">${escapeHtml(entry.label)}</span>
              <span style="color:#d8c7b7;">·</span>
              <span>${escapeHtml(entry.roast || "")}</span>
              <span style="color:#d8c7b7;">·</span>
              <span>${escapeHtml(entry.brewer || "")}</span>
            </div>
          </header>
          ${commentHtml}
          <div style="margin-top:14px;font-size:0.85em;color:#6d6358;
                      font-variant-numeric:tabular-nums;letter-spacing:0.01em;line-height:1.55;">
            ${recipeLine}${metricsLine ? `<br><span style="color:#9b9080;">${metricsLine}</span>` : ""}
          </div>
          ${tagsHtml}
          ${bestRibbon}
        </div>
      </article>
    `;
  }

  function renderHistoryModal(entries) {
    const filtered = applyHistoryFilters(entries);
    const bestTs = findBestBrewTimestamp(entries);

    const labelBtn = (name, accent) => {
      const active = historyFilters.label === name;
      return `<button type="button" data-history-label="${name}"
        style="background:none;border:none;cursor:pointer;padding:5px 2px;
               font-size:0.92em;color:${active ? '#bb5f2a' : '#6d6358'};
               font-weight:${active ? '600' : '400'};
               border-bottom:1px solid ${active ? '#bb5f2a' : 'transparent'};
               display:inline-flex;align-items:center;gap:6px;
               transition:color 0.12s, border-color 0.12s;">
        ${accent ? `<span aria-hidden="true" style="display:inline-block;width:6px;height:6px;border-radius:50%;background:${accent};"></span>` : ""}
        ${name === "__all__" ? "全部" : escapeHtml(name)}
      </button>`;
    };

    const starBtn = (n) => {
      const active = historyFilters.minStars === n;
      return `<button type="button" data-history-stars="${n}"
        style="background:none;border:none;cursor:pointer;padding:5px 2px;
               font-size:0.9em;color:${active ? '#bb5f2a' : '#6d6358'};
               font-weight:${active ? '600' : '400'};
               border-bottom:1px solid ${active ? '#bb5f2a' : 'transparent'};
               transition:color 0.12s, border-color 0.12s;">
        ${n === 0 ? "全部" : `⭐ ${n}+`}
      </button>`;
    };

    const dot = `<span style="color:#d8c7b7;margin:0 4px;">·</span>`;
    const labels = Object.keys(HISTORY_LABEL_COLORS);
    const labelFilter = [labelBtn("__all__", null)]
      .concat(labels.map(l => labelBtn(l, HISTORY_LABEL_COLORS[l])))
      .join(dot);
    const starFilter = [0, 1, 2, 3, 4, 5].map(starBtn).join(dot);

    const body = filtered.length
      ? filtered
          .slice()
          .sort((a, b) => (b.timestamp || "").localeCompare(a.timestamp || ""))
          .map(e => renderHistoryEntry(e, bestTs && e.timestamp === bestTs))
          .join("")
      : `<div style="padding:80px 24px;text-align:center;color:#a89c8a;">
           <div style="font-size:2.4em;margin-bottom:14px;opacity:0.35;letter-spacing:0.1em;">⌬</div>
           <div style="font-size:1.05em;letter-spacing:0.02em;">
             ${entries.length ? "此條件下無紀錄。" : "尚無紀錄。下一杯就是第一筆。"}
           </div>
         </div>`;

    const filterStrip = `
      <div style="position:sticky;top:0;background:#fdf7ef;padding:14px 28px 16px;
                  border-bottom:1px solid #ece2d2;z-index:1;">
        <div style="display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;">
          <span style="font-size:0.72em;color:#a89c8a;letter-spacing:0.18em;
                       text-transform:uppercase;min-width:42px;font-weight:600;">標籤</span>
          <div style="display:flex;flex-wrap:wrap;align-items:center;gap:0;">${labelFilter}</div>
        </div>
        <div style="display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;margin-top:8px;">
          <span style="font-size:0.72em;color:#a89c8a;letter-spacing:0.18em;
                       text-transform:uppercase;min-width:42px;font-weight:600;">星等</span>
          <div style="display:flex;flex-wrap:wrap;align-items:center;gap:0;">${starFilter}</div>
        </div>
      </div>
    `;

    return `
      <div id="history-modal" class="modal" style="display:flex;align-items:center;
           justify-content:center;position:fixed;inset:0;background:rgba(58,52,46,0.42);
           z-index:1000;backdrop-filter:blur(2px);">
        <div class="modal-panel" role="dialog" aria-modal="true" aria-labelledby="history-modal-title"
          style="max-width:760px;width:calc(100% - 32px);background:#fdf7ef;
                 border-radius:14px;display:flex;flex-direction:column;max-height:90vh;
                 box-shadow:0 24px 60px -20px rgba(58,52,46,0.25),
                            0 4px 12px -4px rgba(58,52,46,0.12);
                 overflow:hidden;">
          <div class="modal-head" style="display:flex;justify-content:space-between;
               align-items:flex-start;padding:24px 28px 18px;gap:16px;">
            <div>
              <span class="eyebrow" style="font-size:0.7em;color:#a89c8a;
                    letter-spacing:0.2em;text-transform:uppercase;font-weight:600;">Brewing Journal</span>
              <h2 id="history-modal-title" style="margin:6px 0 4px;color:#4e6b5b;
                  font-size:1.5em;font-weight:500;letter-spacing:-0.005em;">我的沖煮歷史</h2>
              <p style="margin:0;font-size:0.88em;color:#7a6e5f;">
                共 ${entries.length} 筆紀錄${filtered.length !== entries.length ? `（過濾後 ${filtered.length} 筆）` : ""}
              </p>
            </div>
            <button id="history-modal-close" class="modal-close" type="button" aria-label="關閉"
              style="background:none;border:none;font-size:1.6em;cursor:pointer;color:#a89c8a;
                     line-height:1;padding:4px 10px;border-radius:6px;
                     transition:background 0.15s, color 0.15s;">×</button>
          </div>
          ${filterStrip}
          <div id="history-modal-body"
               style="overflow-y:auto;padding:0 28px;flex:1;min-height:0;">
            ${body}
          </div>
        </div>
      </div>
    `;
  }

  function attachHistoryHandlers() {
    const modal = document.getElementById("history-modal");
    if (!modal) return;

    modal.querySelector("#history-modal-close")
      ?.addEventListener("click", closeHistoryModal);
    modal.addEventListener("click", (e) => {
      if (e.target === modal) closeHistoryModal();
    });

    const close = modal.querySelector("#history-modal-close");
    if (close) {
      close.addEventListener("mouseenter", () => {
        close.style.background = "#fdf3ed";
        close.style.color = "#bb5f2a";
      });
      close.addEventListener("mouseleave", () => {
        close.style.background = "none";
        close.style.color = "#a89c8a";
      });
    }

    modal.querySelectorAll("[data-history-label]").forEach((btn) => {
      btn.addEventListener("click", () => {
        historyFilters.label = btn.dataset.historyLabel;
        rerenderHistoryModal();
      });
    });
    modal.querySelectorAll("[data-history-stars]").forEach((btn) => {
      btn.addEventListener("click", () => {
        historyFilters.minStars = Number(btn.dataset.historyStars);
        rerenderHistoryModal();
      });
    });
  }

  function rerenderHistoryModal() {
    const existing = document.getElementById("history-modal");
    if (!existing) return;
    const scrollTop = existing.querySelector("#history-modal-body")?.scrollTop || 0;
    const wrap = document.createElement("div");
    wrap.innerHTML = renderHistoryModal(historyCache.entries);
    existing.replaceWith(wrap.firstElementChild);
    attachHistoryHandlers();
    const body = document.querySelector("#history-modal-body");
    if (body) body.scrollTop = scrollTop;
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
  }

  function mountHistoryTrigger() {
    // Phase-10 redesign: the button now lives in the masthead HTML —
    // we just attach the click handler to whatever's there.
    const btn = document.getElementById("history-trigger");
    if (!btn || btn.dataset.bound === "1") return;
    btn.dataset.bound = "1";
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      openHistoryModal();
    });
  }

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && document.getElementById("history-modal")) {
      closeHistoryModal();
    }
  });
  // ──────────────────────────────────────────────────────────────────


  function renderFeedbackList(feedback) {
    if (!feedback || !feedback.length) return "";
    const items = feedback.map((f) => {
      const stars = f.stars
        ? `<span style="letter-spacing:1px;color:var(--cinnabar);">${"★".repeat(f.stars)}<span style="color:var(--rule);">${"★".repeat(5 - f.stars)}</span></span>`
        : "—";
      const tags = (f.tags || []).map((t) => `<span class="fb-tag">${escapeHtml(t)}</span>`).join("");
      const date = (f.timestamp || "").slice(0, 10);
      const comment = f.comment ? `<div class="fb-comment">「${escapeHtml(f.comment)}」</div>` : "";
      return `
        <div class="fb-entry">
          <div class="fb-meta">${date} · ${stars}</div>
          ${comment}
          ${tags ? `<div style="margin-top: 6px;">${tags}</div>` : ""}
        </div>
      `;
    }).join("");
    return items;
  }

  function renderFeedbackForm(result, slot) {
    const rid = result.recipe_id;
    if (!rid) return "";
    const tagButtons = (window.APP_FEEDBACK_TAGS || []).map((t) =>
      `<button type="button" class="feedback-tag" data-fb-tag="${t}" data-fb-slot="${slot}">${t}</button>`
    ).join("");
    const starButtons = [1, 2, 3, 4, 5].map((n) =>
      `<button type="button" class="feedback-star" data-fb-star="${n}" data-fb-slot="${slot}">★</button>`
    ).join("");
    return `
      <details class="feedback fb-section" data-fb-slot="${slot}" data-fb-recipe="${rid}" data-fb-label="${result.label}">
        <summary class="feedback-summary">TASTING NOTES · 我泡過了</summary>
        <div class="feedback-form">
          <div class="feedback-row">
            <span class="feedback-row-label">STARS · 星等（選填）</span>
            <div class="feedback-stars" data-fb-slot="${slot}">${starButtons}</div>
            <input type="hidden" class="fb-stars-input" data-fb-slot="${slot}" value="">
          </div>
          <div class="feedback-row">
            <span class="feedback-row-label">TAGS · 標籤（多選）</span>
            <div class="feedback-tags" data-fb-slot="${slot}">${tagButtons}</div>
          </div>
          <div class="feedback-row">
            <span class="feedback-row-label">COMMENT · 感想（主要 input）</span>
            <textarea class="feedback-comment fb-comment-input" data-fb-slot="${slot}" rows="3"
              placeholder="例：「偏酸但喝得到甜尾」、「body 不夠」、「下次想試 dial 5.5」..."></textarea>
          </div>
          <div>
            <button type="button" class="feedback-save fb-save-btn" data-fb-slot="${slot}">儲存 · SAVE</button>
            <span class="feedback-msg fb-save-msg" data-fb-slot="${slot}"></span>
          </div>
          <div class="fb-history-mount" data-fb-slot="${slot}">${renderFeedbackList(result.feedback)}</div>
        </div>
      </details>
    `;
  }

  function attachFeedbackHandlers() {
    document.querySelectorAll(".feedback-star").forEach((btn) => {
      if (btn.dataset.fbBound === "1") return;
      btn.dataset.fbBound = "1";
      btn.addEventListener("click", () => {
        const slot = btn.dataset.fbSlot;
        const n = Number(btn.dataset.fbStar);
        const input = document.querySelector(`.fb-stars-input[data-fb-slot="${slot}"]`);
        if (input) input.value = String(n);
        document.querySelectorAll(`.feedback-stars[data-fb-slot="${slot}"] .feedback-star`).forEach((b) => {
          b.classList.toggle("is-on", Number(b.dataset.fbStar) <= n);
        });
      });
    });
    document.querySelectorAll(".feedback-tag").forEach((btn) => {
      if (btn.dataset.fbBound === "1") return;
      btn.dataset.fbBound = "1";
      btn.addEventListener("click", () => {
        const on = btn.dataset.fbActive === "1";
        btn.dataset.fbActive = on ? "0" : "1";
        btn.classList.toggle("is-on", !on);
      });
    });
    document.querySelectorAll(".fb-save-btn").forEach((btn) => {
      if (btn.dataset.fbBound === "1") return;
      btn.dataset.fbBound = "1";
      btn.addEventListener("click", () => submitFeedback(btn.dataset.fbSlot, btn));
    });
  }

  async function submitFeedback(slot, btn) {
    const section = document.querySelector(`.fb-section[data-fb-slot="${slot}"]`);
    if (!section) return;
    const msg = document.querySelector(`.fb-save-msg[data-fb-slot="${slot}"]`);
    const starsInput = document.querySelector(`.fb-stars-input[data-fb-slot="${slot}"]`);
    const commentInput = document.querySelector(`.fb-comment-input[data-fb-slot="${slot}"]`);
    const tags = Array.from(document.querySelectorAll(`.fb-tags[data-fb-slot="${slot}"] [data-fb-active="1"]`))
      .map((b) => b.dataset.fbTag);
    const stars = starsInput.value ? Number(starsInput.value) : null;
    const comment = (commentInput.value || "").trim();
    if (!comment && !stars && !tags.length) {
      msg.textContent = "請至少填一項";
      msg.style.color = "var(--cinnabar)";
      return;
    }
    btn.disabled = true;
    msg.textContent = "儲存中…";
    msg.style.color = "var(--ink-mute)";

    const meta = latestPayload?.meta || {};
    const result = findResultByRecipeId(section.dataset.fbRecipe);
    const body = {
      recipe_id: section.dataset.fbRecipe,
      label: section.dataset.fbLabel,
      stars,
      comment,
      tags,
      roast: meta.roast_code,
      brewer: getRecipeBrewer(section.dataset.fbRecipe),
      water: { gh: meta.water_gh, kh: meta.water_kh, mg_frac: meta.water_mg_frac },
      recipe: result ? {
        temp: result.temp,
        dial: result.dial,
        dose: result.dose,
        steep_sec: result.steep_sec,
        tds: result.tds,
        ey: result.ey,
        score: result.score,
      } : null,
    };
    try {
      const resp = await fetch("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await resp.json();
      if (!resp.ok || !data.ok) {
        throw new Error(data.error || "save failed");
      }
      // Prepend the new entry locally so the user sees it without refetching.
      const mount = document.querySelector(`.fb-history-mount[data-fb-slot="${slot}"]`);
      mount.insertAdjacentHTML("afterbegin", renderFeedbackList([data.entry]));
      commentInput.value = "";
      starsInput.value = "";
      document.querySelectorAll(`.feedback-stars[data-fb-slot="${slot}"] .feedback-star`).forEach((b) => {
        b.classList.remove("is-on");
      });
      document.querySelectorAll(`.feedback-tags[data-fb-slot="${slot}"] .feedback-tag`).forEach((b) => {
        b.dataset.fbActive = "0";
        b.classList.remove("is-on");
      });
      msg.textContent = "✓ 已儲存";
      msg.style.color = "var(--lichen)";
      fetchHistory();  // refresh history count + cache
    } catch (err) {
      msg.textContent = `失敗：${err}`;
      msg.style.color = "var(--cinnabar)";
    } finally {
      btn.disabled = false;
    }
  }

  function findResultByRecipeId(recipeId) {
    if (!latestPayload?.results) return null;
    const seq = Array.isArray(latestPayload.results)
      ? latestPayload.results
      : Object.values(latestPayload.results).flat();
    return seq.find((r) => r.recipe_id === recipeId) || null;
  }

  function getRecipeBrewer(recipeId) {
    const hit = findResultByRecipeId(recipeId);
    if (!hit) return "standard";
    return hit.brewer && hit.brewer.includes("XL") ? "xl" : "standard";
  }
  // ─────────────────────────────────────────────────────────────

  function renderInlineTimer(result, index) {
    return `
      <div class="specimen-section">
        <span class="specimen-section-title">BREW TIMER · 沖煮計時</span>
        <span class="specimen-section-aside">總長 ${formatTime(result.total_contact_sec)}</span>
      </div>
      <div class="timer">
        <div class="timer-display" id="timer-display-${index}">0:00</div>
        <div class="timer-status" id="timer-current-action-${index}">準備注水</div>
        <div class="timer-controls">
          <button class="timer-btn timer-btn-primary" type="button" data-inline-timer-toggle="${index}">▶ 開始</button>
          <button class="timer-btn" type="button" data-inline-timer-reset="${index}">↻ 重置</button>
        </div>
      </div>
    `;
  }

  function startOrPauseInlineTimer(index, result) {
    if (!activeTimers[index]) {
      const milestones = [
        { time: 0, 
          action: "準備注水", 
          rowId: `timeline-row-${index}-0` 
        },
        { 
          time: 0, 
          action: "注水與封閉：注水後塞入活塞建立負壓", 
          rowId: `timeline-row-${index}-1` 
        },
        { 
          time: result.steep_sec, 
          action: `旋轉與靜置：輕柔搖晃 ${result.swirl_sec} 秒後靜置`,
          rowId: `timeline-row-${index}-2` 
        },
        { 
          time: result.steep_sec + result.swirl_sec + result.swirl_wait_sec,
          action: "開始下壓：穩定平均地向下壓", 
          rowId: `timeline-row-${index}-3` 
        },
        { 
          time: result.steep_sec + result.swirl_sec + result.swirl_wait_sec + result.press_sec, 
          action: "萃取完成", 
          rowId: `timeline-row-${index}-4` 
        }
      ];

      activeTimers[index] = {
        isRunning: false,
        elapsedMs: 0,
        lastTickMs: 0,
        milestones: milestones,
        totalTimeSec: milestones[milestones.length - 1].time
      };
    }

    const timer = activeTimers[index];
    const toggleBtn = document.querySelector(`[data-inline-timer-toggle="${index}"]`);

    if (timer.isRunning) {
      timer.isRunning = false;
      toggleBtn.textContent = "▶ 繼續";
    } else {
      if (timer.elapsedMs >= timer.totalTimeSec * 1000) {
        timer.elapsedMs = 0;
      }
      timer.isRunning = true;
      timer.lastTickMs = Date.now();
      toggleBtn.textContent = "‖ 暫停";

      if (!brewTimerInterval) {
        brewTimerInterval = setInterval(tickAllTimers, 100);
      }
    }
    syncInlineTimerUI(index);
  }

  function resetInlineTimer(index) {
    if (activeTimers[index]) {
      activeTimers[index].isRunning = false;
      activeTimers[index].elapsedMs = 0;
    }
    const toggleBtn = document.querySelector(`[data-inline-timer-toggle="${index}"]`);
    if (toggleBtn) toggleBtn.textContent = "▶ 開始";
    syncInlineTimerUI(index);
  }

  function tickAllTimers() {
    const now = Date.now();
    let anyRunning = false;
    
    for (const [indexStr, timer] of Object.entries(activeTimers)) {
      if (timer.isRunning) {
        anyRunning = true;
        const delta = now - timer.lastTickMs;
        timer.elapsedMs += delta;
        timer.lastTickMs = now;
        
        if (timer.elapsedMs >= timer.totalTimeSec * 1000) {
          timer.elapsedMs = timer.totalTimeSec * 1000;
          timer.isRunning = false;
          const toggleBtn = document.querySelector(`[data-inline-timer-toggle="${indexStr}"]`);
          if (toggleBtn) toggleBtn.textContent = "↻ 重新開始";
        }
        
        syncInlineTimerUI(Number(indexStr));
      }
    }

    if (!anyRunning && brewTimerInterval) {
      clearInterval(brewTimerInterval);
      brewTimerInterval = null;
    }
  }

  function syncInlineTimerUI(index) {
    const timer = activeTimers[index];
    if (!timer) return;

    const display = document.getElementById(`timer-display-${index}`);
    const actionText = document.getElementById(`timer-current-action-${index}`);
    if (!display || !actionText) return;

    display.textContent = formatInlineClock(timer.elapsedMs);

    // Signature detail — Fraunces weight axis interpolates with progress.
    const progress = timer.totalTimeSec > 0
      ? Math.min(1, timer.elapsedMs / 1000 / timer.totalTimeSec)
      : 0;
    display.style.setProperty("--t-progress", progress.toFixed(3));

    const elapsedSec = timer.elapsedMs / 1000;
    let currentMilestone = timer.milestones[0];
    let nextMilestone = null;

    for (let i = timer.milestones.length - 1; i >= 0; i--) {
      if (elapsedSec >= timer.milestones[i].time) {
        currentMilestone = timer.milestones[i];
        nextMilestone = timer.milestones[i + 1] || null;
        break;
      }
    }

    actionText.classList.remove("is-running", "is-done");
    if (elapsedSec >= timer.totalTimeSec) {
      actionText.textContent = "EXTRACTION COMPLETE · 萃取完成";
      actionText.classList.add("is-done");
    } else if (nextMilestone && nextMilestone.time > elapsedSec) {
      const timeLeft = Math.ceil(nextMilestone.time - elapsedSec);
      actionText.textContent = `${currentMilestone.action} · 剩餘 ${timeLeft}s`;
      if (timer.isRunning) actionText.classList.add("is-running");
    } else {
      actionText.textContent = currentMilestone.action;
      if (timer.isRunning) actionText.classList.add("is-running");
    }

    // Highlight active timeline row
    for (let i = 1; i < timer.milestones.length; i++) {
      const rowId = timer.milestones[i].rowId;
      const row = document.getElementById(rowId);
      if (row) {
        row.classList.toggle(
          "is-active",
          timer.milestones[i] === currentMilestone && elapsedSec < timer.totalTimeSec
        );
      }
    }
  }

  function metricCard(label, value) {
    return `<div class="chip"><strong>${label}</strong><div>${value}</div></div>`;
  }

  function compoundCard(key, value, maxValue, idealAbs) {
    const help = compoundHelp[key];
    const maxVal = maxValue || 0.6;
    const fillPct = Math.min(100, (value / maxVal) * 100);
    const idealPct = idealAbs != null ? Math.min(100, (idealAbs / maxVal) * 100) : null;

    return `
      <div class="compound-col" title="${help.label}: ${help.body}">
        <div class="compound-code">${key}</div>
        <div class="compound-bar-track">
          <div class="compound-bar-fill" style="height: ${fillPct}%;"></div>
          ${idealPct != null ? `<div class="compound-bar-ideal" style="bottom: ${idealPct}%;"></div>` : ""}
        </div>
        <div class="compound-value">${value.toFixed(3)}</div>
        <div class="compound-name">${help.label}</div>
      </div>
    `;
  }

  function radarLegendCard(key) {
    const help = compoundHelp[key];
    return `
      <div class="legend-item">
        <strong>${key} - ${help.label}</strong>
        <div class="muted">${help.body}</div>
      </div>
    `;
  }

  function compareValueCell(result, primary, secondary = "", cellClass = "", valueClass = "") {
    const tdClass = cellClass ? ` class="${cellClass}"` : "";
    const rankClass = valueClass ? `compare-rank ${valueClass}` : "compare-rank";
    if (!result) {
      return `<td${tdClass}><span class="compare-rank">-</span></td>`;
    }
    return `
      <td${tdClass}>
        <span class="${rankClass}">${primary}</span>
        ${secondary ? `<span class="compare-sub">${secondary}</span>` : ""}
      </td>
    `;
  }

  function compareSection(title) {
    const radarLink = title === "六維向量"
      ? `<a href="#radar-modal" class="compare-section-link" data-open-radar>查看風味雷達圖</a>`
      : "";
    return `
      <tr class="compare-section-row">
        <td colspan="4">
          <div class="compare-section-cell">
            <span>${title}</span>
            ${radarLink}
          </div>
        </td>
      </tr>
    `;
  }

  function compareLabelCell(label, sublabel = "") {
    return `
      <span class="compare-label">${label}</span>
      ${sublabel ? `<span class="compare-label-sub">${sublabel}</span>` : ""}
    `;
  }

  function renderRankHeader(result, index) {
    const scoreLine = result ? `<span class="compare-sub">Score ${result.score.toFixed(1)}</span>` : "";
    return `
      <th>
        <div class="compare-rank-head">
          <span>Rank ${index + 1}</span>
          ${scoreLine}
          <div style="margin-top: 8px;">
             <button class="btn btn-sm btn-outline-primary" type="button" data-scroll-to-recipe="${index}">👉 選擇此配方</button>
          </div>
        </div>
      </th>
    `;
  }

  function buildRadarSvg(results) {
    if (!results.length) return "";

    const size = 420;
    const center = size / 2;
    const radius = 142;
    const rings = [0.25, 0.5, 0.75, 1.0];
    const maxByKey = Object.fromEntries(
      keys.map((key) => [key, Math.max(...results.map((item) => item.compounds_abs[key]), 1e-8)]),
    );

    const ringSvg = rings.map((ring) => {
      const points = keys.map((_, idx) => {
        const angle = (Math.PI * 2 * idx) / keys.length - Math.PI / 2;
        const x = center + Math.cos(angle) * radius * ring;
        const y = center + Math.sin(angle) * radius * ring;
        return `${x},${y}`;
      }).join(" ");
      return `<polygon points="${points}" fill="none" stroke="#e4d7cb"></polygon>`;
    }).join("");

    const spokes = keys.map((key, idx) => {
      const angle = (Math.PI * 2 * idx) / keys.length - Math.PI / 2;
      const x = center + Math.cos(angle) * radius;
      const y = center + Math.sin(angle) * radius;
      const lx = center + Math.cos(angle) * (radius + 28);
      const ly = center + Math.sin(angle) * (radius + 28);
      return `
        <line x1="${center}" y1="${center}" x2="${x}" y2="${y}" stroke="#d8c7b7"></line>
        <text x="${lx}" y="${ly}" text-anchor="middle" font-size="13" fill="#6d6358">${key}</text>
      `;
    }).join("");

    const series = results.slice(0, 3).map((result, index) => {
      const color = ["#bb5f2a", "#4e6b5b", "#8f4667"][index] || "#555";
      const points = keys.map((key, idx) => {
        const angle = (Math.PI * 2 * idx) / keys.length - Math.PI / 2;
        const normalized = result.compounds_abs[key] / maxByKey[key];
        const x = center + Math.cos(angle) * radius * normalized;
        const y = center + Math.sin(angle) * radius * normalized;
        return `${x},${y}`;
      }).join(" ");
      return `<polygon points="${points}" fill="${color}22" stroke="${color}" stroke-width="2"></polygon>`;
    }).join("");

    return `<svg viewBox="0 0 ${size} ${size}">${ringSvg}${spokes}${series}</svg>`;
  }

  function closeRadarModal() {
    radarModal.hidden = true;
    document.body.style.overflow = "";
  }

  function openRadarModal() {
    if (!latestRadarResults.length) return;
    radarNode.innerHTML = buildRadarSvg(latestRadarResults);
    radarLegend.innerHTML = keys.map((key) => radarLegendCard(key)).join("");
    radarModal.hidden = false;
    document.body.style.overflow = "hidden";
  }

  function updateRadarTrigger(results) {
    latestRadarResults = results.slice(0, 3);
    if (!latestRadarResults.length) {
      closeRadarModal();
      return;
    }
    if (!radarModal.hidden) {
      openRadarModal();
    }
  }

  function renderMasterCards(results) {
    if (!results || results.length <= 1) return "";
    const cards = results.map((r, index) => {
      const sel = index === currentDetailIndex ? " is-selected" : "";
      const indicator = index === currentDetailIndex ? " · 顯示中" : "";
      return `
        <div class="master-card${sel}" data-select-recipe="${index}">
          <div class="master-card-rank">Rank ${index + 1}${indicator}</div>
          <div class="master-card-score">${r.score.toFixed(1)}</div>
          <div class="master-card-meta">
            ${r.temp}°C · dial ${r.dial} · ${r.dose}g<br>
            steep ${formatTime(r.steep_sec)} · TDS ${r.tds.toFixed(2)}%
          </div>
        </div>
      `;
    }).join("");
    return `<div class="master-strip">${cards}</div>`;
  }

  function renderSingleDetail(result, meta, index) {
    if (!result) return "";
    const labelName = result.label || "balanced";
    const labelClass = `label-${labelName}`;
    const lbl = (window.APP_LABELS || []).find(l => l.name === labelName);
    const idealFor = (key) => (lbl && lbl.ideal && lbl.ideal[key] != null) ? lbl.ideal[key] * result.tds : null;
    const v_drip = result.v_drip || result.pre_seal_drip_ml || 0;

    // Timeline milestones — accumulating clock
    let t = 0;
    const rows = [];
    rows.push({
      n: 1, time: t,
      title: "注水與封閉 · POUR & SEAL",
      detail: `注水至 ${result.water_ml} ml（水溫 ${result.temp}°C），隨後塞入活塞建立負壓（預估初期漏水約 ${v_drip.toFixed(1)} ml）。`,
    });
    t = result.steep_sec;
    rows.push({
      n: 2, time: t,
      title: "旋轉與靜置 · SWIRL & SETTLE",
      detail: `輕柔搖晃杯身 ${result.swirl_sec} 秒，靜置 ${result.swirl_wait_sec} 秒建立粉床。`,
    });
    t += result.swirl_sec + result.swirl_wait_sec;
    const collapsed = (result.press_sec_internal && result.press_sec_internal > 60) || result.press_sec > 60;
    rows.push({
      n: 3, time: t,
      title: "開始下壓 · PRESS",
      detail: `穩定下壓，預計耗時 ${result.press_sec} 秒（水流通過時間，不含壓到底嗤聲）。${collapsed ? " 阻力崩潰折算。" : ""}`,
    });
    t += result.press_sec;
    rows.push({
      n: 4, time: t,
      title: "萃取完成 · COMPLETE",
      detail: "總接觸時間完成 — 享受咖啡。",
    });

    return `
      <article class="sample ${labelClass}" id="recipe-card-${index}">
        <header class="sample-head">
          <div class="sample-no">
            <span>SAMPLE</span>
            <span class="sample-no-num">№ ${String(index + 1).padStart(2, "0")}</span>
          </div>
          <div class="sample-label">${escapeHtml(labelName)} · ${escapeHtml(meta.roast_name || "")}</div>
        </header>

        <div class="score-block">
          <div class="score-display">${result.score.toFixed(1)}</div>
          <div class="score-meta">
            <div class="score-label">FLAVOR SCORE</div>
            <div class="score-scale">
              <span>0</span>
              <div class="score-scale-track">
                <div class="score-scale-tick" style="left: ${Math.max(0, Math.min(100, result.score))}%;"></div>
              </div>
              <span>100</span>
            </div>
          </div>
        </div>

        <div class="vector-grid">
          <div class="vector-cell">
            <span class="vector-label">TEMP · 水溫</span>
            <span class="vector-value">${result.temp}<span class="vector-unit">°C</span></span>
          </div>
          <div class="vector-cell">
            <span class="vector-label">DIAL · 研磨</span>
            <span class="vector-value">${result.dial}</span>
          </div>
          <div class="vector-cell">
            <span class="vector-label">DOSE · 粉量</span>
            <span class="vector-value">${result.dose}<span class="vector-unit">g</span></span>
          </div>
          <div class="vector-cell">
            <span class="vector-label">STEEP · 浸泡</span>
            <span class="vector-value">${formatTime(result.steep_sec)}</span>
          </div>
        </div>

        <div class="specimen-section">
          <span class="specimen-section-title">TIMELINE · Hoffman 沖煮指南</span>
          <span class="specimen-section-aside">總接觸 ${formatTime(result.total_contact_sec)} · TDS ${result.tds.toFixed(2)}% · EY ${result.ey.toFixed(1)}%</span>
        </div>
        <div class="timeline-callout">
          建議先「按馬錶」、隨即「注水」、完成後「塞塞子」 — 從水接觸咖啡的第一秒起計時。下壓秒數為水流通過時間；嗤聲後壓到底為空氣階段，不計入萃取。
        </div>
        <div class="timeline">
          ${rows.map(r => `
            <div class="timeline-row" id="timeline-row-${index}-${r.n}">
              <span class="timeline-time">${formatTime(r.time)}</span>
              <span class="timeline-action"><strong>${r.title}</strong><br>${r.detail}</span>
            </div>
          `).join("")}
        </div>

        ${renderInlineTimer(result, index)}

        <div class="specimen-section">
          <span class="specimen-section-title">COMPOUND VECTOR · 六向量化合物</span>
          <a href="#radar" class="specimen-section-link" data-open-radar>查看風味雷達圖 →</a>
        </div>
        <div class="compounds">
          ${keys.map(key => compoundCard(
            key,
            result.compounds_abs[key],
            meta.flavor_max ? meta.flavor_max[key] : 0.6,
            idealFor(key),
          )).join("")}
        </div>

        <div class="ratios">
          <div class="ratio-cell">
            <span class="ratio-label">AC / SW</span>
            <span>
              <span class="ratio-actual">${result.ratios.ac_sw_actual}</span>
              <span class="ratio-ideal"> · ideal ${result.ratios.ac_sw_ideal}</span>
            </span>
          </div>
          <div class="ratio-cell">
            <span class="ratio-label">PS / BITTER</span>
            <span>
              <span class="ratio-actual">${result.ratios.ps_bitter_actual}</span>
              <span class="ratio-ideal"> · ideal ${result.ratios.ps_bitter_ideal}</span>
            </span>
          </div>
        </div>

        ${renderFeedbackForm(result, `detail-${index}`)}
      </article>
    `;
  }

  function renderResultContent(results, meta) {
    resultsNode.innerHTML = `
      <div id="master-view" style="min-width: 0;">
        ${renderMasterCards(results)}
      </div>
      <div id="detail-view" style="margin-top: 2rem; min-width: 0; overflow-x: hidden;">
        ${results[currentDetailIndex] ? renderSingleDetail(results[currentDetailIndex], meta, currentDetailIndex) : ''}
      </div>
    `;

    syncInlineTimerUI(currentDetailIndex);
    attachFeedbackHandlers();
  }

  function renderChannelB(meta, byLabel) {
    // Flatten label → result list into one row per label (Top 1 each), side-by-side.
    const labels = Object.keys(byLabel);
    if (!labels.length) {
      resultsNode.innerHTML = `<div class="empty">沒有可用結果。</div>`;
      return;
    }
    const cards = labels.map((lbl, idx) => {
      const items = byLabel[lbl] || [];
      const labelClass = `label-${lbl}`;
      if (!items.length) {
        return `
          <div class="cup-card ${labelClass}">
            <div class="cup-card-head">
              <div class="cup-card-label">${escapeHtml(lbl)}</div>
            </div>
            <div class="cup-card-empty">（無候選配方）</div>
          </div>
        `;
      }
      const r = items[0];
      return `
        <div class="cup-card ${labelClass}">
          <div class="cup-card-head">
            <div class="cup-card-label">${escapeHtml(lbl)}</div>
            <div class="cup-card-score">${r.score.toFixed(1)}</div>
          </div>
          <div class="cup-card-params">
            ${r.temp}°C · dial ${r.dial} · ${r.dose}g · steep ${formatTime(r.steep_sec)}<br>
            TDS ${r.tds.toFixed(2)}% · EY ${r.ey.toFixed(1)}%
          </div>
          <div class="cup-card-id">recipe_id ${r.recipe_id || "—"}</div>
          ${renderFeedbackForm(r, `channelb-${idx}`)}
        </div>
      `;
    }).join("");

    resultsNode.innerHTML = `
      <div class="channel-b-intro">CHANNEL B · 各 label 各自最佳化 Top 1（cupping 比對）</div>
      <div class="channel-b-strip">${cards}</div>
      <div class="channel-b-hint">切回單一 label 可看完整 timeline / timer</div>
    `;
    updateRadarTrigger([]);
    attachFeedbackHandlers();
  }

  function renderResults(payload) {
    const { meta, results } = payload;
    latestPayload = payload;

    // reset all timers
    if (brewTimerInterval) {
      clearInterval(brewTimerInterval);
      brewTimerInterval = null;
    }
    activeTimers = {};

    // Channel B: results is dict[label] → list. Render parallel cards.
    if (results && !Array.isArray(results) && typeof results === "object") {
      setMobileControlsHidden(true, { scrollToResults: true });
      renderChannelB(meta, results);
      return;
    }

    if (!results || !results.length) {
      setMobileControlsHidden(false);
      resultsNode.innerHTML = `<div class="empty">沒有可用結果。</div>`;
      updateRadarTrigger([]);
      return;
    }

    currentDetailIndex = 0;
    renderResultContent(results, meta);
    updateRadarTrigger(results);
  }

  // ── 豆量步進依器材切換 ────────────────────────────────────────
  const doseMinInput = document.getElementById("dose_min");
  const doseMaxInput = document.getElementById("dose_max");
  const brewerSelect = document.getElementById("brewer");

  function syncDoseInputStep() {
    if (!brewerSelect) return;
    const stepG = brewerSelect.value === "xl" ? "1" : "0.5";
    if (doseMinInput) doseMinInput.step = stepG;
    if (doseMaxInput) doseMaxInput.step = stepG;
  }
  syncDoseInputStep();
  if (brewerSelect) brewerSelect.addEventListener("change", syncDoseInputStep);
  // ─────────────────────────────────────────────────────────────

  presetSelect.addEventListener("change", () => {
    const selected = presetSelect.value;
    if (selected && presets[selected]) {
      ghInput.value = presets[selected].gh;
      khInput.value = presets[selected].kh;
      mgInput.value = presets[selected].mg_frac;
    }
    showHelp("preset");
  });

  document.querySelectorAll("[data-help-key] input, [data-help-key] select").forEach((element) => {
    const key = element.closest("[data-help-key]").dataset.helpKey;
    element.addEventListener("focus", () => showHelp(key));
    element.addEventListener("change", () => showHelp(key));
    element.addEventListener("click", () => showHelp(key));
  });

  document.querySelectorAll("[data-help-target]").forEach((button) => {
    button.addEventListener("click", () => showHelp(button.dataset.helpTarget));
  });

  mobileControlsQuery.addEventListener("change", () => {
    if (!mobileControlsQuery.matches) {
      mobileControlsHidden = false;
    }
    syncControlsPanelState();
  });


  resultsNode.addEventListener("click", (event) => {
    const selectTrigger = event.target.closest("[data-select-recipe]");
    if (selectTrigger) {
      const newIndex = Number(selectTrigger.dataset.selectRecipe);
      if (newIndex !== currentDetailIndex) {
        // clear old timer if running
        if (activeTimers[currentDetailIndex] && activeTimers[currentDetailIndex].isRunning) {
          activeTimers[currentDetailIndex].isRunning = false;
        }
        // save scroll position before re-render
        const scrollContainer = resultsNode.querySelector(".scroll-container");
        const savedScrollLeft = scrollContainer ? scrollContainer.scrollLeft : 0;
        currentDetailIndex = newIndex;
        if (latestPayload?.results?.length) {
          renderResultContent(latestPayload.results, latestPayload.meta);
          // restore scroll position after re-render
          const newScrollContainer = resultsNode.querySelector(".scroll-container");
          if (newScrollContainer) newScrollContainer.scrollLeft = savedScrollLeft;
          setTimeout(() => {
            const detailView = document.getElementById("detail-view");
            if (detailView) {
                const yOffset = -20; 
                const y = detailView.getBoundingClientRect().top + window.scrollY + yOffset;
                window.scrollTo({top: y, behavior: 'smooth'});
            }
          }, 50);
        }
      }
      return;
    }

    const timerToggle = event.target.closest("[data-inline-timer-toggle]");
    if (timerToggle) {
        const index = Number(timerToggle.dataset.inlineTimerToggle);
        const result = latestPayload?.results?.[index];
        if (result) {
            startOrPauseInlineTimer(index, result);
        }
        return;
    }

    const timerReset = event.target.closest("[data-inline-timer-reset]");
    if (timerReset) {
        const index = Number(timerReset.dataset.inlineTimerReset);
        resetInlineTimer(index);
        return;
    }

    const trigger = event.target.closest("[data-open-radar]");
    if (!trigger) return;
    event.preventDefault();
    openRadarModal();
  });
  radarClose.addEventListener("click", closeRadarModal);
  radarModal.addEventListener("click", (event) => {
    if (event.target === radarModal) {
      closeRadarModal();
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    if (!radarModal.hidden) {
      closeRadarModal();
      return;
    }
  });
  
  controlsToggle.addEventListener("click", () => {
    if (!mobileControlsQuery.matches) return;
    setMobileControlsHidden(!mobileControlsHidden);
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (document.activeElement instanceof HTMLElement) {
      document.activeElement.blur();
    }
    setMobileControlsHidden(true, { scrollToResults: true });
    submitButton.disabled = true;
    submitButton.textContent = "計算中...";

    const payload = Object.fromEntries(new FormData(form).entries());
    ["gh", "kh", "mg_frac", "top", "t_env", "altitude", "dose_min", "dose_max"].forEach((key) => {
      payload[key] = payload[key] === "" ? null : Number(payload[key]);
    });

    try {
      const response = await fetch("/api/optimize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      renderResults(data);
    } catch (error) {
      setMobileControlsHidden(false);
      resultsNode.innerHTML = `<div class="empty">計算失敗：${error}</div>`;
      updateRadarTrigger([]);
    } finally {
      submitButton.disabled = false;
      submitButton.textContent = "開始最佳化";
    }
  });

  showHelp("brewer");
  syncControlsPanelState();
  mountHistoryTrigger();
  fetchHistory();
})();
