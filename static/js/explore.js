/* explore.js — calibration-bracket mode (standalone module).
 *
 * Deliberately kept separate from webapp.js: it only attaches a click handler
 * to #explore-button and renders into #results. webapp.js is untouched, so this
 * feature does not entangle with the in-progress UI rewrite living there.
 *
 * Backend: POST /api/explore -> { meta, bracket: [...] }. The bracket is the
 * label's optimum plus single-axis temp/dose offsets — brew & rate the spread
 * to give accumulated feedback a usable gradient.
 */
(() => {
  "use strict";

  const form = document.getElementById("optimize-form");
  const button = document.getElementById("explore-button");
  const resultsNode = document.getElementById("results");
  if (!form || !button || !resultsNode) return;

  // env / water fields are numeric; "" -> null (backend supplies defaults)
  const NUM_KEYS = ["gh", "kh", "mg_frac", "t_env", "altitude"];

  function buildPayload() {
    const payload = Object.fromEntries(new FormData(form).entries());
    NUM_KEYS.forEach((k) => {
      payload[k] = (payload[k] === "" || payload[k] === undefined)
        ? null : Number(payload[k]);
    });
    return payload;
  }

  function fmtTime(sec) {
    const t = Math.round(Number(sec) || 0);
    return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, "0")}`;
  }

  function esc(s) {
    return String(s).replace(/[&<>"]/g, (c) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]
    ));
  }

  function emptyState(title, tw) {
    resultsNode.innerHTML =
      `<div class="empty-state"><div class="empty-title">${esc(title)}</div>` +
      `<div class="empty-tw">${esc(tw)}</div></div>`;
  }

  function render(data) {
    const meta = data.meta || {};
    const rows = data.bracket || [];
    if (!rows.length) {
      emptyState("NO BRACKET", "無可用結果");
      return;
    }
    const body = rows.map((r) => {
      const optimum = r.bracket === "optimum";
      return `<tr class="bracket-row${optimum ? " is-optimum" : ""}">` +
        `<td class="bx-tag">${esc(r.bracket)}</td>` +
        `<td>${esc(r.temp)}°C</td>` +
        `<td>${Number(r.dial).toFixed(1)}</td>` +
        `<td>${Number(r.dose).toFixed(1)}g</td>` +
        `<td>${fmtTime(r.steep_sec)}</td>` +
        `<td>${Number(r.tds).toFixed(3)}</td>` +
        `<td>${Number(r.ey).toFixed(1)}</td>` +
        `<td class="bx-score">${Number(r.score).toFixed(1)}</td></tr>`;
    }).join("");
    resultsNode.innerHTML =
      `<div class="bracket-report">` +
        `<div class="bracket-head">` +
          `<span class="eyebrow">§ CALIBRATION BRACKET · 校準探索</span>` +
          `<h2>label「${esc(meta.label || "")}」 · ${esc(meta.roast_name || "")}</h2>` +
          `<p class="bracket-intro">這幾杯都泡來、各自評分 — 每杯只偏移一個軸，` +
          `你的評分高低差就是能拿來校準 data/labels.json 的梯度。</p>` +
        `</div>` +
        `<table class="bracket-table"><thead><tr>` +
          `<th>BRACKET</th><th>水溫</th><th>刻度</th><th>豆量</th><th>浸泡</th>` +
          `<th>TDS</th><th>EY</th><th>模型分</th>` +
        `</tr></thead><tbody>${body}</tbody></table>` +
        `<p class="bracket-note">⚠ 模型分高 ≠ 你會喜歡 — 重點是「你的評分」` +
        `在這幾杯之間的高低差。</p>` +
      `</div>`;
  }

  button.addEventListener("click", async () => {
    button.disabled = true;
    const labelEl = button.querySelector(".submit-label");
    const original = labelEl ? labelEl.textContent : "";
    if (labelEl) labelEl.textContent = "COMPUTING · 計算中";
    try {
      const resp = await fetch("/api/explore", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildPayload()),
      });
      render(await resp.json());
      resultsNode.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) {
      emptyState("ERROR", `探索失敗：${err}`);
    } finally {
      button.disabled = false;
      if (labelEl) labelEl.textContent = original;
    }
  });
})();
