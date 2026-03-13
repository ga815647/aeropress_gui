(() => {
  const form = document.getElementById("optimize-form");
  if (!form) return;

  const presetSelect = document.getElementById("preset");
  const ghInput = document.getElementById("gh");
  const khInput = document.getElementById("kh");
  const mgInput = document.getElementById("mg_frac");
  const submitButton = document.getElementById("submit-button");
  const summary = document.getElementById("summary");
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
      body: "焙度會改變理想風味向量與苦甜平衡，直接影響排序結果。",
      meta: "若不知道怎麼選，通常可先從中焙 M 開始測試。",
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
    const entry = fieldHelp[key];
    if (!entry) return;
    tooltipTitle.textContent = entry.title;
    tooltipBody.textContent = entry.body;
    tooltipMeta.textContent = entry.meta;
  }

  function syncControlsPanelState() {
    if (!controlsPanel || !controlsBody || !controlsToggle) return;

    const hiddenOnMobile = mobileControlsQuery.matches && mobileControlsHidden;
    controlsPanel.hidden = hiddenOnMobile;
    controlsPanel.classList.remove("is-collapsed");
    controlsBody.hidden = false;
  }

  function setMobileControlsHidden(nextValue, { scrollToResults = false } = {}) {
    if (!mobileControlsQuery.matches) return;
    mobileControlsHidden = nextValue;
    syncControlsPanelState();

    if (nextValue && scrollToResults) {
      requestAnimationFrame(() => {
        summary.scrollIntoView({ behavior: "smooth", block: "start" });
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

  function renderInlineTimer(result, index) {
    return `
      <div class="inline-timer-wrap" style="margin-top: 1.5rem; border-top: 1px solid #e4d7cb; padding-top: 1.5rem; text-align: center;">
        <div id="timer-display-${index}" style="font-size: 3.5rem; font-weight: bold; font-variant-numeric: tabular-nums; color: #bb5f2a; line-height: 1;">00:00</div>
        <div id="timer-current-action-${index}" style="font-size: 1.2rem; color: #4e6b5b; margin-top: 0.5rem; margin-bottom: 1.5rem; min-height: 1.8rem;">準備注水</div>
        <div style="display: flex; gap: 12px; justify-content: center;">
          <button class="btn btn-primary primary-button" type="button" data-inline-timer-toggle="${index}" style="min-width: 120px;">▶️ 開始</button>
          <button class="btn btn-outline-secondary default-button" type="button" data-inline-timer-reset="${index}" style="min-width: 100px;">🔄 重置</button>
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
          action: "旋轉與靜置：輕柔搖晃 5 秒後靜置", 
          rowId: `timeline-row-${index}-2` 
        },
        { 
          time: result.steep_sec + 5 + result.swirl_wait_sec, 
          action: "開始下壓：穩定平均地向下壓", 
          rowId: `timeline-row-${index}-3` 
        },
        { 
          time: result.steep_sec + 5 + result.swirl_wait_sec + result.press_sec, 
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
      toggleBtn.textContent = "▶️ 繼續";
    } else {
      if (timer.elapsedMs >= timer.totalTimeSec * 1000) {
        timer.elapsedMs = 0;
      }
      timer.isRunning = true;
      timer.lastTickMs = Date.now();
      toggleBtn.textContent = "⏸️ 暫停";
      
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
    if (toggleBtn) toggleBtn.textContent = "▶️ 開始";
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
          if (toggleBtn) toggleBtn.textContent = "🔄 重新開始";
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
    
    const elapsedSec = timer.elapsedMs / 1000;
    let currentMilestone = timer.milestones[0];
    let nextMilestoneIdx = 1;

    for (let i = timer.milestones.length - 1; i >= 0; i--) {
      if (elapsedSec >= timer.milestones[i].time) {
        currentMilestone = timer.milestones[i];
        nextMilestoneIdx = Math.min(i + 1, timer.milestones.length - 1);
        break;
      }
    }

    if (elapsedSec >= timer.totalTimeSec) {
      actionText.textContent = "萃取完成！請享用咖啡。";
    } else {
      actionText.textContent = currentMilestone.action;
    }

    // Highlight row
    for (let i = 1; i < timer.milestones.length; i++) {
        const rowId = timer.milestones[i].rowId;
        const row = document.getElementById(rowId);
        if (row) {
             if (timer.milestones[i] === currentMilestone && elapsedSec < timer.totalTimeSec) {
                 row.style.backgroundColor = "#fff9e6";
             } else {
                 row.style.backgroundColor = "";
             }
        }
    }
  }

  function metricCard(label, value) {
    return `<div class="chip"><strong>${label}</strong><div>${value}</div></div>`;
  }

  function compoundCard(key, value) {
    const help = compoundHelp[key];
    return `
      <div class="compound" title="${help.label}">
        <strong>${key}</strong>
        <div>${value.toFixed(4)}</div>
        <div class="compound-note">${help.label}: ${help.body}</div>
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
    const cards = results.map((r, index) => {
      const isSelected = index === currentDetailIndex;
      const borderStyle = isSelected ? "border: 2px solid #bb5f2a;" : "border: 1px solid #e4d7cb;";
      const cursorStyle = isSelected ? "cursor: default;" : "cursor: pointer;";
      const currentIndicator = isSelected ? `<span style="font-size: 0.8em; color: #bb5f2a; font-weight: bold; background: #fdf3ed; padding: 2px 6px; border-radius: 4px; border: 1px solid #bb5f2a;">📍 目前顯示</span>` : ``;

      return `
      <div class="recipe-card" data-select-recipe="${index}" style="min-width: 280px; scroll-snap-align: start; flex-shrink: 0; border-radius: 12px; padding: 1.2rem; background: #fff; ${borderStyle} ${cursorStyle} transition: border-color 0.2s, background-color 0.2s;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem;">
          <div>
            <div class="muted" style="font-size: 0.85em; font-weight: bold;">Rank ${index + 1}</div>
            <h3 style="margin: 0; font-size: 1.1em; color: #4e6b5b;">Score ${r.score.toFixed(1)}</h3>
          </div>
          ${currentIndicator}
        </div>
        <div style="font-size: 0.9em; color: #6d6358; line-height: 1.4;">
          <strong>Temp ${r.temp}C / Dial ${r.dial} / Dose ${r.dose}g</strong><br>
          Contact: ${formatTime(r.total_contact_sec)}<br>
          TDS ${r.tds.toFixed(2)}% | EY ${r.ey.toFixed(1)}%
        </div>
      </div>
      `;
    }).join("");

    return `
      <div class="scroll-container" style="display: flex; overflow-x: auto; scroll-snap-type: x mandatory; gap: 16px; padding: 0 24px 16px 24px; margin-top: 1rem;">
        ${cards}
      </div>
    `;
  }

  function renderSingleDetail(result, meta, index) {
    if (!result) return "";
    let currentSec = 0;
      const v_drip = result.v_drip || result.pre_seal_drip_ml || 0;
      
      const timelineHtml = `
        <div class="timeline-wrap" style="margin-top: 1.5rem; border-top: 1px solid #e4d7cb; padding-top: 1rem;">
          <h4 style="margin: 0 0 0.75rem 0; font-size: 1.05rem; color: #4e6b5b;">實戰沖煮指南 (Timeline)</h4>
          <div style="display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 1rem;">
            <span class="badge" style="background-color: #6d6358; font-size: 0.85em; padding: 0.4em 0.6em; font-weight: normal;">🔥 焙度: ${meta.roast_name}</span>
            <span class="badge" style="background-color: #6d6358; font-size: 0.85em; padding: 0.4em 0.6em; font-weight: normal;">🌡️ 水溫: ${result.temp}°C</span>
            <span class="badge" style="background-color: #6d6358; font-size: 0.85em; padding: 0.4em 0.6em; font-weight: normal;">⚙️ 刻度: Dial ${result.dial}</span>
            <span class="badge" style="background-color: #6d6358; font-size: 0.85em; padding: 0.4em 0.6em; font-weight: normal;">⚖️ 粉量: ${result.dose}g</span>
            <span class="badge" style="background-color: #6d6358; font-size: 0.85em; padding: 0.4em 0.6em; font-weight: normal;">💧 水量: ${result.water_ml}ml</span>
            <span class="badge" style="background-color: #6d6358; font-size: 0.85em; padding: 0.4em 0.6em; font-weight: normal;">💧 水質: GH ${meta.water_gh} / KH ${meta.water_kh}</span>
            <span class="badge" style="background-color: #6d6358; font-size: 0.85em; padding: 0.4em 0.6em; font-weight: normal;">🧪 Mg 比例: ${meta.water_mg_frac}</span>
          </div>
          <table class="table table-sm table-hover timeline-table" style="width: 100%; text-align: left; font-size: 0.95em; border-collapse: collapse; table-layout: fixed; word-wrap: break-word;">
            <tbody>
              <tr id="timeline-row-${index}-1" style="border-bottom: 1px solid #f1ece6; transition: background-color 0.3s;">
                <td style="padding: 0.5rem 0.25rem; font-weight: bold; width: 60px; vertical-align: top;">${formatTime(currentSec)}</td>
                <td style="padding: 0.5rem 0.25rem;">
                  <strong>注水與封閉</strong><br>
                  <span style="color: #6d6358;">注水至 ${result.water_ml} ml (水溫 ${result.temp}°C)，隨後塞入活塞建立負壓 (預估初期漏水約 ${v_drip.toFixed(1)} ml)。</span>
                </td>
              </tr>
              ${(() => {
                currentSec = result.steep_sec;
                return `
              <tr id="timeline-row-${index}-2" style="border-bottom: 1px solid #f1ece6; transition: background-color 0.3s;">
                <td style="padding: 0.5rem 0.25rem; font-weight: bold; vertical-align: top;">${formatTime(currentSec)}</td>
                <td style="padding: 0.5rem 0.25rem;">
                  <strong>旋轉與靜置</strong><br>
                  <span style="color: #6d6358;">帶著活塞輕柔搖晃杯身 5 秒，隨後放著靜置 ${result.swirl_wait_sec} 秒以建立粉床。</span>
                </td>
              </tr>
                `;
              })()}
              ${(() => {
                currentSec += (5 + result.swirl_wait_sec);
                const pressWarning = (result.press_sec_internal && result.press_sec_internal > 60) || result.press_sec > 60 
                  ? ' <span class="badge bg-danger" style="background-color: #bb5f2a; color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.8em; margin-left: 4px;">阻力崩潰折算</span>' 
                  : '';
                return `
              <tr id="timeline-row-${index}-3" style="border-bottom: 1px solid #f1ece6; transition: background-color 0.3s;">
                <td style="padding: 0.5rem 0.25rem; font-weight: bold; vertical-align: top;">${formatTime(currentSec)}</td>
                <td style="padding: 0.5rem 0.25rem;">
                  <strong>開始下壓</strong><br>
                  <span style="color: #6d6358;">穩定下壓，預計耗時 ${result.press_sec} 秒。${pressWarning}</span>
                </td>
              </tr>
                `;
              })()}
              ${(() => {
                currentSec += result.press_sec;
                return `
              <tr id="timeline-row-${index}-4" style="transition: background-color 0.3s;">
                <td style="padding: 0.5rem 0.25rem; font-weight: bold; vertical-align: top;">${formatTime(currentSec)}</td>
                <td style="padding: 0.5rem 0.25rem;">
                  <strong>萃取完成</strong><br>
                  <span style="color: #6d6358;">總接觸時間完成！享受咖啡。</span>
                </td>
              </tr>
                `;
              })()}
            </tbody>
          </table>
          ${renderInlineTimer(result, index)}
        </div>
      `;

      return `
      <article class="result-card" id="recipe-card-${index}" style="min-width: 0; overflow-x: hidden;">
        <div class="result-head">
          <div>
            <div class="muted">Rank ${index + 1}</div>
            <h2 style="margin:4px 0 0">Temp ${result.temp}C / Dial ${result.dial} / Dose ${result.dose}g</h2>
          </div>
          <div class="score">${result.score.toFixed(1)}</div>
        </div>
        
        <div class="metrics" style="margin-top: 1rem;">
          <div class="metric"><strong>TDS</strong><div>${result.tds.toFixed(4)}%</div></div>
          <div class="metric"><strong>EY</strong><div>${result.ey.toFixed(3)}%</div></div>
          <div class="ratio"><strong>SW / AC</strong><div>${result.ratios.ac_sw_actual} (Ideal ${result.ratios.ac_sw_ideal})</div></div>
          <div class="ratio"><strong>PS / Bitter</strong><div>${result.ratios.ps_bitter_actual} (Ideal ${result.ratios.ps_bitter_ideal})</div></div>
        </div>

        ${timelineHtml}

        <div class="compound-grid" style="margin-top: 1.5rem; min-width: 0;">
          ${keys.map((key) => compoundCard(key, result.compounds_abs[key])).join("")}
        </div>
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

    if (!results.length) {
      setMobileControlsHidden(false);
      resultsNode.innerHTML = `<div class="empty">沒有可用結果。</div>`;
      updateRadarTrigger([]);
      return;
    }

    currentDetailIndex = 0;
    renderResultContent(results, meta);
    updateRadarTrigger(results);
  }

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

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (document.activeElement instanceof HTMLElement) {
      document.activeElement.blur();
    }
    setMobileControlsHidden(true, { scrollToResults: true });
    submitButton.disabled = true;
    submitButton.textContent = "計算中...";

    const payload = Object.fromEntries(new FormData(form).entries());
    ["gh", "kh", "mg_frac", "top", "t_env", "altitude"].forEach((key) => {
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
})();
