# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 路由

| 想看什麼 | 去哪 |
|---------|------|
| 待辦任務 / phase 歷史 / 評分鑑別度改革紀錄 | [`TASKS.md`](TASKS.md) |
| 泡法時間軸 / 各時間參數定義 / 三錨點時間圖 | [`BREW_PROTOCOL.md`](BREW_PROTOCOL.md) |
| Data flow / Grid search / 化合物模型 / 評分公式細節 / 感知前處理 / Key files / Water 參數 / 修改方向表 | [`ARCHITECTURE.md`](ARCHITECTURE.md) |

**僅剩待辦：**
- UI — Chip 標籤重寫（Phase 5 full IDEAL 對齊文獻後可進行）
- `light` 槽真淺焙錨點待補（找到 Nordic-style AeroPress 食譜後校準）
- scoring 殘留 issue：90s vs 120s 在 standard brewer 同 dose 鑑別力不足（`build_ideal_abs` 隨 actual TDS 內插 bracket 吸收絕對差距）— 詳見 TASKS.md
- 化合物層 brewer geometry 建模（未來 phase）— XL 深床效應未進化合物層，現用 `dial_offset` 兜底

**目前狀態（Phase 7 完成）：** 6 錨點全 PASS（Hoffman 89.6 / April 75.0 / Champion 61.6 / Under 0 / Over 34.1 / Hedrick **85.7**，從 68.1 大幅修正），11 pytest PASS。`compounds.py` 已純 Arrhenius × first-order；Phase 7 把 `grind_kinetics` 也套到 `k_mel_eff` 上（與 CGA 同結構），讓粗磨真實壓低 MEL 累積 — 文獻機制 Gagné「fines × time = astringency」的最小連續代理。**化合物層在 dial/steep/temp 全域掃描下處處連續單調或單峰，無島（驗證原則 #4）**。Hoffman vs Hedrick 的雙峰地形完全來自 scoring 層 IDEAL 校準，合法。

## Commands

```bash
# Run optimizer (CLI)
python main.py --roast light --brewer xl
python main.py --roast light --brewer xl --preset volvic_pure --top 5
python main.py --roast medium --gh 50 --kh 30 --output json --radar

# Run anchor validation (mandatory after any constants.py change)
python diagnose_anchor.py

# Run tests
python -m pytest tests/

# Start web app
python webapp.py
```

**CLI key flags:** `--roast` (required), `--brewer` (standard/xl), `--preset` (water preset name), `--gh`/`--kh`/`--mg-frac` (manual water), `--top N`, `--output` (terminal/json/csv), `--radar`, `--t-env`, `--altitude`.

---

## 口感矯正工作流程（強制）

每當使用者提供口感矯正指示（例如「太苦」「酸不足」「澀感高」「甜感弱」等），
必須在修改 `constants.py` 後**立即執行**：

```bash
python diagnose_anchor.py
```

若輸出顯示 `[ FAIL ]`，**必須修正常數直到全部通過**，才能回報完成。

修改方向參考表見 [`ARCHITECTURE.md`](ARCHITECTURE.md) §「常數修改方向參考」。

### 錨點基準（勿偏離）

**注意：Hoffmann/April/Championship 三錨點掛在 `medium_light` 槽**（El Tambo 實際 Agtron 65-75 = 中淺焙）。`light` 槽留給 Nordic 真淺焙，與 Hoffmann 校準無關。

| 參數 | Hoffman 實測值 | 模型目標 |
|------|--------------|---------|
| TDS | 1.23%（稍粗）→ 原版 ~1.27% | `TDS_PREFER["medium_light"] = 1.27` |
| EY | 20–22% | `EY_PREFER["medium_light"] = 21.0` |
| 研磨 | 450–600µm EK43 → ZP6 dial ≈ 4.3 | `dial_prefer["medium_light"] = 4.3` |
| 水溫 | 97.8°C（208°F） | 錨點檢查固定 98–99°C |
| 浸泡 | 2:00 → swirl → press | 錨點 `fixed_steep=120s` |

---

## 三錨點食譜（原始資料）

來源：2022 年文章《Brewing for Balance, Acidity, or Sweetness》，使用哥倫比亞 El Tambo 水洗豆（Agtron 65-75，Square Mile filter style，**對應本系統 `medium_light` 焙度槽**——早期版本誤標 `light` 已修正）。

> 三錨點完整時間軸（含每個時間參數對應到哪段動作）見 [`BREW_PROTOCOL.md`](BREW_PROTOCOL.md) §3。

| 錨點 | 劑量 | 水量 | 水溫 | 研磨 | 浸泡 | TDS | 目標風味 |
|------|------|------|------|------|------|-----|---------|
| Hoffman 平衡 | 11g | 200ml | 208°F (97.8°C) | 4 EK / 450-600µm（細）| 120s swirl → 150s press | 1.23% | 平衡（Heath bar + 檸檬點心）|
| April 酸質 | 13g | 200ml | 185°F (85°C) | 6.75 EK / 810µm（粗）| 90s total，含半密封 25s | 1.17% | 酸質為主（清爽、爽口、多汁）|
| Championship 甜感醇厚 | 17g | 200ml | 176°F (80°C) | 6.75 EK / 810µm（粗）| 100s 倒置，20s 壓 | 1.56% | 甜感+醇厚（奶油、牛軋糖、濃稠感）|

---

## 模型設計原則（紅線，禁止偏離）

**好喝不好喝跟泡法無關。評分只看杯中物：化合物比例 + TDS。**

- EY、水溫、浸泡時間是過程變數，不是杯中物品質指標，**不得作為主要扣分依據**
- TDS 是杯中物品質的合法指標（太淡/太濃影響口感）
- 化合物向量（AC/SW/PS/CA/CGA/MEL 比例）是最核心的口感品質指標

### 四條不可違反的架構原則

1. **禁止 min/max/if-else 硬斷點** — 物理世界是連續的。所有閾值、天花板、地板必須用平滑連續函數：
   - `max(x - threshold, 0)` → softplus 或 sigmoid gate
   - `min(x, cap)` → sigmoid saturation
   - `if x > threshold` → sigmoid transition
   - 例外：純離散邏輯（`inverted=True/False`）不在此限

2. **所有錨點用同一個評分公式** — April 和 Championship 必須通過 `flavor_score()` 得到高分，不允許用獨立的 `_anchor_cosine_score()`。如果一個評分系統無法同時獎勵 Hoffman 的均衡、April 的酸質、Championship 的甜醇，那是評分系統的問題，不是用特例繞過的理由。

3. **化合物模型必須自我鑑別** — 好喝的配方（Hoffman/April/Championship）的化合物 profile 進入評分公式後自然高分。難喝的配方（欠萃/過萃）的化合物 profile 自然低分。不需要靠 TDS floor 或 EY floor 來區分好壞 — 化合物信號本身就應該承載這個資訊。

4. **化合物層純連續物理；感官層允許閾值（嚴格二層分工）** — 物理化學是連續的，人類感知有閾值。兩者必須分層、不互相污染：
   - **化合物層 (`compounds.py`)**: **純連續物理動力學** — Arrhenius 速率 × 一階反應，從 t=0 連續到 t=∞、從 0K 到任何溫度全域可微。**禁止**：onset 時間（如 `CGA_TIME_ONSET=150`）、time floor（如 `SW_TIME_FLOOR=0.30`）、tent function（如 `1 - abs(temp - optimal)`）、softplus 溫度閾值（如 `softplus(temp - 92)`）— 即使數學上平滑，這些都是「閾值化偽裝」，不符合分子萃取物理。
   - **感官層 (`scoring.py`)**: **sigmoid / softplus / Gaussian 可用** — 人類感知本來就有閾值（Weber-Fechner law）。合法的閾值化感知層成員：`SW_AROMA_THRESH`、`SCORCH_PARAMS`、`TDS_FLOOR_MID`、`KH_FLOOR`。
   - **違反此原則的代價：** 化合物模型失去自我鑑別力（→ 違反原則 #3）→ 評分只能靠 process-variable 後置 gate 補救（如 `acid_trap = sigmoid(temp - 96) × sigmoid(120 - steep)`）→ 補丁是症狀治療，根因仍在 compounds.py 內部的非物理 gate。

### 原則 #1 vs #4 的關係（層次補強）

| 角度 | #1（全域）| #4（分層）|
|------|---------|---------|
| 規定 | **怎麼寫**閾值（要平滑）| **哪裡可以有**閾值（只感官層）|
| 化合物層 | 不能用硬斷點 | 連平滑閾值都禁止，只能用 `exp()` 結構（Arrhenius / 一階）|
| 感官層 | 用 sigmoid / softplus / Gaussian | 允許（人類感知本有閾值）|

**關鍵：`exp()` vs `sigmoid/softplus` 結構不同：**
- `exp(-Ea/RT)`、`1 - exp(-k·t)`：**全域 monotone、無拐點、無 threshold 參數** → 純物理曲線
- `sigmoid(k·(x - threshold))`、`softplus(x - threshold)`：**顯式 threshold 參數、有 inflection 點** → 閾值化（即使平滑）

化合物層 `softplus(temp - 92)` 滿足 #1（平滑）但違反 #4（藏 threshold）；改成 `exp(Ea/R × (1/T_ref - 1/T))` 才同時滿足兩者。

**判斷流程：**
```
寫一行新公式時，問自己：
├─ 這是化學物理？→ exp() / Arrhenius / 一階，禁所有閾值
└─ 這是人類感知？→ sigmoid / softplus（必須平滑）
```

### 三錨點各自「分數不低」的物理原因

| 錨點 | 為何分數不低 | 關鍵信號 |
|------|------------|---------|
| Hoffman | 化合物 log-ratio 偏差小，TDS≈1.27 接近 `TDS_PREFER` | compound_reward 接近 1.0；tds_factor 接近 1.0 |
| April | AC > CGA 且 AC > MEL（純淨酸質）；TDS=1.17% 在 SCA 範圍 | ratio bonus 補償；tds_factor 對 1.17 寬鬆 |
| Championship | SW+PS > 0.35；SW > MEL/CGA（甜感主導）；TDS=1.56% 高濃縮 | ratio bonus 補償；TDS Super-Gaussian 高側 sigma=0.65 寬腰 |

April / Champion 在 `diagnose_anchor.py` 也檢查 `compounds["AC"] > compounds["CGA"]` 等 profile-specific 條件作為輔助斷言，但**評分本身用統一的 `flavor_score()`**（原則 #2）。

---

**禁止為了讓某錨點通過而削弱某項懲罰** → 必須找出物理根本原因。
