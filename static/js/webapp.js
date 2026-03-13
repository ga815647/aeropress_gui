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
  const viewModeBar = document.getElementById("view-mode-bar");
  const viewModeButtons = document.querySelectorAll("[data-view-mode]");
  const viewModeNote = document.getElementById("view-mode-note");
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

  let currentViewMode = "compare";
  let latestPayload = null;
  let latestRadarResults = [];
  let mobileControlsHidden = false;
  let brewTimer = {
    openRankIndex: null,
    steps: [],
    stepIndex: 0,
    remainingMs: 0,
    isRunning: false,
    endAtMs: 0,
    tickHandle: null,
  };

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
    tds_floor: {
      title: "TDS Floor",
      body: "限制過低 TDS 的組合，避免推薦雖然乾淨但過薄的結果。",
      meta: "若你想找更輕盈的配方，可試著微幅下修。",
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

  function clampTimerMs(value) {
    return Math.max(0, Math.round(value));
  }

  function formatTimerClock(ms) {
    const totalSeconds = Math.ceil(clampTimerMs(ms) / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }

  function buildBrewSteps(result) {
    if (!result) return [];
    return [
      {
        key: "steep",
        label: "浸泡",
        durationMs: clampTimerMs(result.steep_sec * 1000),
        action: "注完水還沒蓋蓋子（此時按下碼表），等待一段時間後塞入活塞建立負壓，讓咖啡粉持續浸泡。",
      },
      {
        key: "swirl",
        label: "旋轉",
        durationMs: clampTimerMs(result.swirl_sec * 1000),
        action: "穩定旋轉杯身，讓粉床重新均勻混合，提升萃取一致性。",
      },
      {
        key: "swirl_wait",
        label: "旋轉後等待",
        durationMs: clampTimerMs(result.swirl_wait_sec * 1000),
        action: "停止晃動，靜置讓粉床沉降，準備進入下壓階段。",
      },
      {
        key: "press",
        label: "下壓",
        durationMs: clampTimerMs(result.press_sec * 1000),
        action: "以穩定且平均的力道向下壓，直到這個配方流程完成。",
      },
    ];
  }

  function getTimerTotalRemainingMs() {
    if (!brewTimer.steps.length) return 0;
    const currentStepRemaining = brewTimer.isRunning
      ? clampTimerMs(brewTimer.endAtMs - Date.now())
      : brewTimer.remainingMs;
    const remainingAfterCurrent = brewTimer.steps
      .slice(brewTimer.stepIndex + 1)
      .reduce((total, step) => total + step.durationMs, 0);
    return currentStepRemaining + remainingAfterCurrent;
  }

  function clearBrewTimerTick() {
    if (brewTimer.tickHandle) {
      clearInterval(brewTimer.tickHandle);
      brewTimer.tickHandle = null;
    }
  }

  function resetBrewTimerState() {
    clearBrewTimerTick();
    brewTimer = {
      openRankIndex: null,
      steps: [],
      stepIndex: 0,
      remainingMs: 0,
      isRunning: false,
      endAtMs: 0,
      tickHandle: null,
    };
    syncBrewTimerViewportState();
  }

  function syncBrewTimerViewportState() {
    document.body.classList.toggle(
      "timer-open",
      brewTimer.openRankIndex !== null && currentViewMode === "compare",
    );
  }

  function syncBrewTimerPanel() {
    const panel = resultsNode.querySelector("[data-rank-timer-panel]");
    if (!panel || brewTimer.openRankIndex === null || !brewTimer.steps.length) return;

    const currentStep = brewTimer.steps[brewTimer.stepIndex];
    if (!currentStep) return;

    const currentRemaining = brewTimer.isRunning
      ? clampTimerMs(brewTimer.endAtMs - Date.now())
      : brewTimer.remainingMs;
    const nextStep = brewTimer.steps[brewTimer.stepIndex + 1];

    const statusNode = panel.querySelector("[data-rank-timer-status]");
    const clockNode = panel.querySelector("[data-rank-timer-clock]");
    const totalNode = panel.querySelector("[data-rank-timer-total]");
    const labelNode = panel.querySelector("[data-rank-timer-label]");
    const actionNode = panel.querySelector("[data-rank-timer-action-text]");
    const nextNode = panel.querySelector("[data-rank-timer-next]");
    const toggleNode = panel.querySelector("[data-rank-timer-toggle]");
    const progressNodes = panel.querySelectorAll("[data-rank-timer-step-chip]");

    statusNode.textContent = brewTimer.isRunning ? "進行中" : currentRemaining === 0 ? "已完成" : "準備開始";
    clockNode.textContent = formatTimerClock(currentRemaining);
    totalNode.textContent = `剩餘總時間 ${formatTimerClock(getTimerTotalRemainingMs())}`;
    labelNode.textContent = `步驟 ${brewTimer.stepIndex + 1}/${brewTimer.steps.length}：${currentStep.label}`;
    actionNode.textContent = currentStep.action;
    nextNode.textContent = nextStep
      ? `下一步：${nextStep.label}`
      : "下一步：完成整個沖煮流程。";
    toggleNode.textContent = brewTimer.isRunning ? "暫停" : currentRemaining === 0 ? "重新開始" : "開始";

    progressNodes.forEach((node, index) => {
      node.classList.toggle("is-active", index === brewTimer.stepIndex);
      node.classList.toggle("is-complete", index < brewTimer.stepIndex || (index === brewTimer.stepIndex && currentRemaining === 0));
    });
  }

  function advanceBrewTimerStep() {
    clearBrewTimerTick();

    if (brewTimer.stepIndex >= brewTimer.steps.length - 1) {
      brewTimer.isRunning = false;
      brewTimer.remainingMs = 0;
      brewTimer.endAtMs = 0;
      syncBrewTimerPanel();
      return;
    }

    brewTimer.stepIndex += 1;
    brewTimer.remainingMs = brewTimer.steps[brewTimer.stepIndex].durationMs;
    brewTimer.isRunning = true;
    brewTimer.endAtMs = Date.now() + brewTimer.remainingMs;
    brewTimer.tickHandle = setInterval(tickBrewTimer, 250);
    syncBrewTimerPanel();
  }

  function tickBrewTimer() {
    if (!brewTimer.isRunning) return;
    const remaining = clampTimerMs(brewTimer.endAtMs - Date.now());
    brewTimer.remainingMs = remaining;

    if (remaining === 0) {
      advanceBrewTimerStep();
      return;
    }

    syncBrewTimerPanel();
  }

  function openBrewTimer(index, result) {
    clearBrewTimerTick();
    const steps = buildBrewSteps(result);
    brewTimer = {
      openRankIndex: index,
      steps,
      stepIndex: 0,
      remainingMs: steps[0] ? steps[0].durationMs : 0,
      isRunning: false,
      endAtMs: 0,
      tickHandle: null,
    };
    syncBrewTimerViewportState();
  }

  function closeBrewTimer() {
    resetBrewTimerState();
    if (latestPayload?.results?.length && currentViewMode === "compare") {
      renderResultContent(latestPayload.results);
    }
  }

  function startOrPauseBrewTimer() {
    if (!brewTimer.steps.length) return;

    if (brewTimer.isRunning) {
      brewTimer.remainingMs = clampTimerMs(brewTimer.endAtMs - Date.now());
      brewTimer.isRunning = false;
      brewTimer.endAtMs = 0;
      clearBrewTimerTick();
      syncBrewTimerPanel();
      return;
    }

    if (brewTimer.remainingMs === 0) {
      brewTimer.stepIndex = 0;
      brewTimer.remainingMs = brewTimer.steps[0].durationMs;
    }

    brewTimer.isRunning = true;
    brewTimer.endAtMs = Date.now() + brewTimer.remainingMs;
    clearBrewTimerTick();
    brewTimer.tickHandle = setInterval(tickBrewTimer, 250);
    syncBrewTimerPanel();
  }

  function resetBrewTimer() {
    if (!brewTimer.steps.length) return;
    clearBrewTimerTick();
    brewTimer.stepIndex = 0;
    brewTimer.remainingMs = brewTimer.steps[0].durationMs;
    brewTimer.isRunning = false;
    brewTimer.endAtMs = 0;
    syncBrewTimerPanel();
  }

  function skipBrewTimerStep() {
    if (!brewTimer.steps.length) return;

    if (brewTimer.stepIndex >= brewTimer.steps.length - 1) {
      clearBrewTimerTick();
      brewTimer.remainingMs = 0;
      brewTimer.isRunning = false;
      brewTimer.endAtMs = 0;
      syncBrewTimerPanel();
      return;
    }

    clearBrewTimerTick();
    brewTimer.stepIndex += 1;
    brewTimer.remainingMs = brewTimer.steps[brewTimer.stepIndex].durationMs;
    brewTimer.isRunning = false;
    brewTimer.endAtMs = 0;
    syncBrewTimerPanel();
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

  function renderRankTimerPanel(result, index) {
    const steps = buildBrewSteps(result);
    const activeStep = steps[brewTimer.stepIndex] || steps[0];
    const totalMs = steps.reduce((sum, step) => sum + step.durationMs, 0);
    const currentMs = brewTimer.openRankIndex === index
      ? brewTimer.remainingMs
      : activeStep.durationMs;
    return `
      <div class="rank-timer-popover" data-rank-timer-panel="${index}">
        <div class="rank-timer-head">
          <div>
            <div class="rank-timer-rank">Rank ${index + 1} 沖煮碼表</div>
            <div class="rank-timer-score">Score ${result.score.toFixed(1)} · ${steps.length} steps</div>
          </div>
          <button class="rank-timer-close-button" type="button" data-rank-timer-action="close" aria-label="關閉碼表">×</button>
        </div>
        <div class="rank-timer-layout">
          <div class="rank-timer-clock-card">
            <div class="rank-timer-status" data-rank-timer-status>Ready</div>
            <div class="rank-timer-clock" data-rank-timer-clock>${formatTimerClock(currentMs)}</div>
            <div class="rank-timer-total" data-rank-timer-total>剩餘總時間 ${formatTimerClock(totalMs)}</div>
          </div>
          <div class="rank-timer-step-card">
            <div class="rank-timer-step-label" data-rank-timer-label>步驟 1/${steps.length}：${activeStep.label}</div>
            <div class="rank-timer-step-text" data-rank-timer-action-text>${activeStep.action}</div>
            <div class="rank-timer-step-next" data-rank-timer-next>下一步：${steps[1] ? steps[1].label : "完成整個沖煮流程。"}</div>
          </div>
        </div>
        <div class="rank-timer-progress">
          ${steps.map((step, stepIndex) => `
            <span
              class="rank-timer-step-chip ${stepIndex === 0 ? "is-active" : ""}"
              data-rank-timer-step-chip
            >${step.label}</span>
          `).join("")}
        </div>
        <div class="rank-timer-actions">
          <button class="rank-timer-action-button" type="button" data-rank-timer-action="toggle" data-rank-timer-toggle>開始</button>
          <button class="rank-timer-action-button is-secondary" type="button" data-rank-timer-action="next">下一步</button>
          <button class="rank-timer-action-button is-ghost" type="button" data-rank-timer-action="reset">重設</button>
        </div>
      </div>
    `;
  }

  function renderRankHeader(result, index) {
    const scoreLine = result ? `<span class="compare-sub">Score ${result.score.toFixed(1)}</span>` : "";
    const isOpen = brewTimer.openRankIndex === index && result;
    return `
      <th>
        <div class="compare-rank-head">
          <button
            class="rank-header-button ${isOpen ? "is-active" : ""}"
            type="button"
            data-rank-timer-trigger="${index}"
          >
            <span>Rank ${index + 1}</span>
            ${scoreLine}
          </button>
          ${isOpen ? renderRankTimerPanel(result, index) : ""}
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

  function renderCompareTable(results) {
    const topResults = results.slice(0, 3);
    const columns = [0, 1, 2].map((index) => renderRankHeader(topResults[index], index)).join("");

    const row = (label, formatter) => `
      <tr>
        <td>${label}</td>
        ${[0, 1, 2].map((index) => formatter(topResults[index])).join("")}
      </tr>
    `;

    const swirlRows = [
      row(compareLabelCell("碼表按下時機", "Timer Start"), (result) => compareValueCell(result, result ? "還沒蓋蓋子 (注完水)" : "-")),
      row(compareLabelCell("SWIRL 開始時間", "Swirl Start"), (result) => compareValueCell(result, result ? formatTime(result.steep_sec) : "-")),
      row(compareLabelCell("WAIT 開始時間", "Wait Start"), (result) => compareValueCell(result, result ? formatTime(result.steep_sec + result.swirl_sec) : "-")),
      row(compareLabelCell("Swirl", "操作時間"), (result) => compareValueCell(result, result ? `${result.swirl_sec}s` : "-")),
      row(compareLabelCell("Swirl Wait", "靜置沉降"), (result) => compareValueCell(result, result ? `${result.swirl_wait_sec}s` : "-")),
      row(compareLabelCell("Swirl Phase", "Swirl + Wait"), (result) => compareValueCell(result, result ? `${result.swirl_sec + result.swirl_wait_sec}s` : "-")),
    ].join("");

    const compoundRows = keys.map((key) => {
      const maxValue = Math.max(
        ...topResults
          .filter(Boolean)
          .map((result) => result.compounds_abs[key]),
      );

      return row(compareLabelCell(key, compoundHelp[key].label), (result) => {
        if (!result) {
          return compareValueCell(result, "-");
        }
        const isHighest = result.compounds_abs[key] === maxValue;
        return compareValueCell(
          result,
          result.compounds_abs[key].toFixed(4),
          "",
          isHighest ? "compare-cell-highlight" : "",
          isHighest ? "compare-rank-highlight" : "",
        );
      });
    }).join("");

    return `
      <section class="compare-card">
        <div class="compare-head">
          <h2>Top 3 核心比較</h2>
        </div>
        <div class="compare-table-wrap">
          <table class="compare-table">
            <thead>
              <tr>
                <th>比較項目</th>
                ${columns}
              </tr>
            </thead>
            <tbody>
              ${compareSection("配方")}
              ${row(compareLabelCell("沖煮", "溫度 / 刻度 / 粉量"), (result) => compareValueCell(result, result ? `${result.temp}C / Dial ${result.dial}` : "-", result ? `Dose ${result.dose}g` : ""))}
              ${row(compareLabelCell("時間", "浸泡 / 下壓 / 接觸"), (result) => compareValueCell(result, result ? `Steep ${formatTime(result.steep_sec)}` : "-", result ? `Press ${result.press_sec}s / Contact ${formatTime(result.total_contact_sec)}` : ""))}
              ${swirlRows}
              ${compareSection("萃取")}
              ${row(compareLabelCell("EY", "萃取率"), (result) => compareValueCell(result, result ? `${result.ey.toFixed(3)}%` : "-"))}
              ${row(compareLabelCell("TDS", "濃度"), (result) => compareValueCell(result, result ? `${result.tds.toFixed(4)}%` : "-"))}
              ${row(compareLabelCell("Slurry", "粉床溫度"), (result) => compareValueCell(result, result ? `${result.t_slurry.toFixed(1)}C` : "-"))}
              ${compareSection("比例")}
              ${row(compareLabelCell("AC/SW", "酸甜比"), (result) => compareValueCell(result, result ? result.ratios.ac_sw_actual : "-", result ? `ideal ${result.ratios.ac_sw_ideal}` : ""))}
              ${row(compareLabelCell("PS/Bitter", "香氣苦味比"), (result) => compareValueCell(result, result ? result.ratios.ps_bitter_actual : "-", result ? `ideal ${result.ratios.ps_bitter_ideal}` : ""))}
              ${compareSection("六維向量")}
              ${compoundRows}
            </tbody>
          </table>
        </div>
      </section>
    `;
  }

  function renderDetailCards(results) {
    return results.map((result, index) => {
      let currentSec = 0;
      const v_drip = result.v_drip || result.pre_seal_drip_ml || 0;
      
      const timelineHtml = `
        <div class="timeline-wrap" style="margin-top: 1.5rem; border-top: 1px solid #e4d7cb; padding-top: 1rem;">
          <h4 style="margin: 0 0 0.75rem 0; font-size: 1.05rem; color: #4e6b5b;">實戰沖煮指南 (Timeline)</h4>
          <table class="table table-sm table-hover timeline-table" style="width: 100%; text-align: left; font-size: 0.95em; border-collapse: collapse;">
            <tbody>
              <tr style="border-bottom: 1px solid #f1ece6;">
                <td style="padding: 0.5rem 0.25rem; font-weight: bold; width: 60px; vertical-align: top;">${formatTime(currentSec)}</td>
                <td style="padding: 0.5rem 0.25rem;">
                  <strong>注水與封閉</strong><br>
                  <span style="color: #6d6358;">注水至 ${result.water_ml} ml (水溫 ${result.temp}°C)，隨後塞入活塞建立負壓 (預估初期漏水約 ${v_drip.toFixed(1)} ml)。</span>
                </td>
              </tr>
              ${(() => {
                currentSec = result.steep_sec;
                return `
              <tr style="border-bottom: 1px solid #f1ece6;">
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
              <tr style="border-bottom: 1px solid #f1ece6;">
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
              <tr>
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
        </div>
      `;

      return `
      <article class="result-card">
        <div class="result-head">
          <div>
            <div class="muted">Rank ${index + 1}</div>
            <h2 style="margin:4px 0 0">Temp ${result.temp}C / Dial ${result.dial} / Dose ${result.dose}g</h2>
          </div>
          <div class="score">${result.score.toFixed(1)}</div>
        </div>
        <div class="metrics">
          <div class="metric"><strong>碼表按下</strong><div style="font-size: 0.85em; margin-top: 4px;">還沒蓋蓋子</div></div>
          <div class="metric"><strong>SWIRL 開始</strong><div>${formatTime(result.steep_sec)}</div></div>
          <div class="metric"><strong>WAIT 開始</strong><div>${formatTime(result.steep_sec + result.swirl_sec)}</div></div>
        </div>
        <div class="metrics">
          <div class="metric"><strong>Steep</strong><div>${formatTime(result.steep_sec)}</div></div>
          <div class="metric"><strong>Swirl</strong><div>${result.swirl_sec}s</div></div>
          <div class="ratio"><strong>Swirl Wait</strong><div>${result.swirl_wait_sec}s</div></div>
          <div class="ratio"><strong>Swirl Phase</strong><div>${result.swirl_sec + result.swirl_wait_sec}s</div></div>
          <div class="metric"><strong>Press</strong><div>${result.press_sec}s</div></div>
        </div>
        <div class="metrics">
          <div class="metric"><strong>Contact</strong><div>${formatTime(result.total_contact_sec)}</div></div>
          <div class="metric"><strong>EY</strong><div>${result.ey.toFixed(3)}%</div></div>
          <div class="metric"><strong>TDS</strong><div>${result.tds.toFixed(4)}%</div></div>
          <div class="metric"><strong>T_slurry</strong><div>${result.t_slurry.toFixed(1)}C</div></div>
        </div>
        <div class="metrics">
          <div class="ratio"><strong>AC/SW</strong><div>${result.ratios.ac_sw_actual} / ideal ${result.ratios.ac_sw_ideal}</div></div>
          <div class="ratio"><strong>PS/Bitter</strong><div>${result.ratios.ps_bitter_actual} / ideal ${result.ratios.ps_bitter_ideal}</div></div>

        </div>
        <div class="compound-grid">
          ${keys.map((key) => compoundCard(key, result.compounds_abs[key])).join("")}
        </div>
        ${timelineHtml}
      </article>
      `;
    }).join("");
  }

  function syncViewModeUI() {
    viewModeButtons.forEach((button) => {
      button.classList.toggle("is-active", button.dataset.viewMode === currentViewMode);
    });
    viewModeNote.textContent = currentViewMode === "compare"
      ? "聚焦前三名的核心數據差異。"
      : "逐項附上參數與風味說明，適合細讀。";
  }

  function renderResultContent(results) {
    resultsNode.innerHTML = currentViewMode === "compare"
      ? renderCompareTable(results)
      : renderDetailCards(results);
    syncBrewTimerViewportState();
    if (currentViewMode === "compare") {
      syncBrewTimerPanel();
    }
  }

  function renderResults(payload) {
    const { meta, results } = payload;
    latestPayload = payload;
    resetBrewTimerState();

    summary.innerHTML = [
      metricCard("焙度", `${meta.roast_name} (${meta.roast_code})`),
      metricCard("水質", `GH ${meta.water_gh} / KH ${meta.water_kh}`),
      metricCard("Mg 比例", meta.water_mg_frac),
      metricCard("TDS Floor", meta.tds_floor),
    ].join("");

    if (!results.length) {
      setMobileControlsHidden(false);
      viewModeBar.hidden = true;
      resultsNode.innerHTML = `<div class="empty">沒有可用結果。</div>`;
      updateRadarTrigger([]);
      return;
    }

    viewModeBar.hidden = false;
    syncViewModeUI();
    renderResultContent(results);
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


  viewModeButtons.forEach((button) => {
    button.addEventListener("click", () => {
      if (button.dataset.viewMode === currentViewMode) return;
      currentViewMode = button.dataset.viewMode;
      syncViewModeUI();
      if (latestPayload?.results?.length) {
        renderResultContent(latestPayload.results);
      }
    });
  });

  resultsNode.addEventListener("click", (event) => {
    const timerTrigger = event.target.closest("[data-rank-timer-trigger]");
    if (timerTrigger) {
      const index = Number(timerTrigger.dataset.rankTimerTrigger);
      const result = latestPayload?.results?.[index];
      if (!result) return;
      if (brewTimer.openRankIndex === index) {
        closeBrewTimer();
        return;
      }
      openBrewTimer(index, result);
      renderResultContent(latestPayload.results);
      syncBrewTimerPanel();
      return;
    }

    const timerAction = event.target.closest("[data-rank-timer-action]");
    if (timerAction) {
      const action = timerAction.dataset.rankTimerAction;
      if (action === "toggle") startOrPauseBrewTimer();
      if (action === "reset") resetBrewTimer();
      if (action === "next") skipBrewTimerStep();
      if (action === "close") closeBrewTimer();
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
    if (brewTimer.openRankIndex !== null) {
      closeBrewTimer();
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
    ["gh", "kh", "mg_frac", "top", "t_env", "tds_floor", "altitude"].forEach((key) => {
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
      viewModeBar.hidden = true;
      resultsNode.innerHTML = `<div class="empty">計算失敗：${error}</div>`;
      updateRadarTrigger([]);
    } finally {
      submitButton.disabled = false;
      submitButton.textContent = "開始最佳化";
    }
  });

  syncViewModeUI();
  showHelp("brewer");
  syncControlsPanelState();
})();
