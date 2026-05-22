# Phase 10 — Step 4：薄 Layer 1（knob → TDS/EY）

> **狀態：完成（2026-05-22）。** Phase 10 §11 執行步驟表的 Step 4 交付物。
> 程式：[`../models/layer1.py`](../models/layer1.py)。
> 上游：[`PHASE10_SENSORY_REFOUNDING.md`](PHASE10_SENSORY_REFOUNDING.md)（藍圖 §6 薄 Layer 1 規格）、[`PHASE10_STEP3_LABELS.md`](PHASE10_STEP3_LABELS.md) §9.1（light IDEAL 待 Step 4 重推）。

---

## 1. 交付物摘要

- `models/layer1.py` —— `brew(roast, temp, dial, steep_sec, dose, water_ml, brewer) → {ey, tds}`。取代 `ey_model.py` + `tds_model.py` + `compounds.py` 全套。
- 模型 = **單一一階逼近平衡上限**（equilibrium-desorption 粗形）：`EY = E_MAX·(1−exp(−t_eff/τ))·f_ratio`。純 `exp()` 結構、全域單調、飽和、無閾值。
- **5 個自由參數**，校準到 3 個有實測 TDS 的 medium_light 錨點（Hoffman/April/Champion）：3 個用錨點解出（`E_MAX`/`TAU_REF`/`ALPHA`）、2 個物理先驗（`GAMMA`/`K_RATIO`）。3 錨點 TDS **重現誤差 ≤ 0.001%**。
- `data/labels.json` 的 `light` IDEAL 依 Step 3 §9.1 用新 Layer 1 重推（§5.4）。
- 舊三模組未刪除（`runtime.py`/`optimizer.py` 等仍 import 它們）—— Step 5 改接線後一併刪。本步驟為**純加法**：新增 `models/layer1.py`，不動既有檔（除 `labels.json` 的 light 重推）。

---

## 2. 模型形式

```
EY%  = E_MAX · (1 − exp(−t_eff / τ)) · f_ratio

  τ        = TAU_REF · brewer · exp(−ALPHA·(temp−T_REF)) · exp(−GAMMA·(DIAL_REF−dial))
  f_ratio  = water / (water + K_RATIO · dose)
  t_eff    = steep_sec + T_PRESS_OFFSET

TDS% = extracted / cup_mass · 100
  extracted = dose · EY/100
  cup_mass  = (water − dose·retention) + extracted
```

| 元件 | 意義 | 單調方向 |
|---|---|---|
| `E_MAX` | 平衡萃取上限（時間→∞、無限稀釋的 EY 天花板）| per-roast |
| `τ` | 速率常數（逼近 `E_MAX` 的 e-folding 時間）| 越熱 / 越細 → 越小（越快）；XL 深床 → 略大 |
| `f_time = 1−exp(−t_eff/τ)` | 一階萃取進度 | 越久 → 越接近 1（飽和）|
| `f_ratio` | 沖煮比飽和（咖啡:水越濃 → 漿液越早飽和 → EY 略低）| dose 越多 → 略低 |

**為什麼是這個形式（藍圖 §6）：** 平衡脫附全浸泡模型（Sci Rep 2021）的粗形 —— 萃取以一階速率逼近一個平衡上限。所有溫度/研磨/時間/比例都走 `exp()`：全域單調、飽和、無拐點、**無閾值參數** —— 滿足 CLAUDE.md 原則 #1（平滑連續）。**外觀即黑箱**：使用者只見「旋鈕進、TDS/EY 出」，內部是 5 參數的平衡脫附曲線。

`models/layer1.py` 為**純模組**（只 import `math`，無 `constants` 依賴）—— 與 `models/sensory.py` 同樣自含；`water_ml` 由呼叫端傳入，`brewer` 僅選 `BREWER_TAU_MULT`。

---

## 3. 校準

### 3.1 錨點（3 個有實測 TDS 的 medium_light 物理校準錨點）

來源：Hoffmann《Brewing for Balance, Acidity, or Sweetness》(El Tambo 水洗)。

| 錨點 | temp / dial / steep / dose / water | 實測 TDS |
|---|---|---|
| Hoffman | 98°C / 4.3 / 120s / 11g / 200ml | 1.23 |
| April | 85°C / 5.0 / 90s / 13g / 200ml | 1.17 |
| Championship | 80°C / 5.0 / 100s / 17g / 200ml | 1.56 |

> Hedrick 在 `diagnose_anchor.py` 標記 `measured_tds: None`（無實測 TDS）—— 藍圖 §6 誤以為 Hedrick 有「已知 TDS」。Hedrick 因此只當 sanity 點，不進校準。

實測量到的是 **TDS**；EY 由 `TDS = EY·dose÷出杯重` 反解（retention 2.15 g/g）：Hoffman ≈ 19.96%、April ≈ 15.67%、Champion ≈ 15.24%。

### 3.2 參數（5 個）

| 參數 | 值 | 角色 | 來源 |
|---|---|---|---|
| `E_MAX_REF` | 22.84 % | medium_light 平衡上限 | **錨點解出** |
| `TAU_REF` | 44.4 s | 速率常數（98°C / dial 4.3 / standard）| **錨點解出** |
| `ALPHA` | 0.0194 /°C | 溫度 → 速率 | **錨點解出** |
| `GAMMA` | 0.32 /dial | 研磨 → 速率 | 物理先驗 |
| `K_RATIO` | 1.5 | 沖煮比容量係數 | 物理先驗 |

固定偏移：`T_REF=98`、`DIAL_REF=4.3`、`T_PRESS_OFFSET=10s`。

**解法（結構替代缺的資料）：** 家裡無折射儀 → 除 3 個文獻錨點外產不出任何 (旋鈕→實測 TDS) 配對（藍圖 §6）。6 input × 自由黑箱必 overfit。故先以物理先驗釘住 `GAMMA`（研磨速率效應，中等）與 `K_RATIO`（沖煮比效應，溫和、~2% EY 跨度）；其餘 3 個 `E_MAX`/`TAU_REF`/`ALPHA` 由 3 錨點**精確解出**（3 方程 3 未知）。受「單調 + 飽和」約束，5 參數曲線被 3 錨點 + sanity 邊界釘死。

**溫度是溫和的槓桿（重要發現）：** `ALPHA` 解出 ≈ 0.019/°C —— τ 在 80–98°C 間只變化約 40%。這對上藍圖 §13「平衡脫附論文發現溫度對 TDS/EY 幾乎無感」。April/Champion 的低 EY 主要來自**較粗研磨 + 較高沖煮比 + 較短浸泡**，**不是**它們的低水溫。技法（April 半密封/二段注水、Champion 倒置）不進薄 Layer 1（藍圖 §6）—— 其效應被吸收進這組粗校準。

---

## 4. 驗證

### 4.1 錨點重現（誤差 ≤ 0.001% TDS）

| 錨點 | predicted EY | predicted TDS | 實測 TDS | 誤差 |
|---|---|---|---|---|
| Hoffman | 19.97% | 1.230% | 1.23 | +0.000 |
| April | 15.67% | 1.170% | 1.17 | +0.000 |
| Championship | 15.24% | 1.561% | 1.56 | +0.001 |

### 4.2 單調性掃描（medium_light XL，base 95°C / 4.3 / 120s / 24g）

| 掃描 | 值 | EY |
|---|---|---|
| 溫度 | 82 / 88 / 94 / 100°C | 18.24 → 18.85 → 19.37 → 19.80 ↑ 飽和 |
| 研磨 | dial 3.0 / 4.3 / 5.5 / 7.0 | 20.57 → 19.45 → 17.46 → 14.04 ↓（越粗越少）|
| 浸泡 | 30 / 90 / 180 / 360s | 11.63 → 18.18 → 20.51 → 20.94 ↑ 飽和 |
| 劑量 | 16 / 22 / 28 / 34g | 20.00 → 19.58 → 19.18 → 18.80 ↓（溫和）|

全部單調、飽和、無斷點、無 blow-up。

### 4.3 Sanity 點（非校準，標準 200ml）

| 配方 | EY | TDS | 期望 |
|---|---|---|---|
| Hedrick（95°C / 6.0 / 240s / 14g）| 19.72% | 1.599% | 無實測 → 寬 sanity band [1.30,1.65] ✓ |
| Under-extract（93°C / 6.5 / 60s / 11g）| 10.70% | 0.663% | EY < 15、TDS < 0.85 ✓ |
| Over-extract（99°C / 3.5 / 240s / 11g）| 21.09% | 1.298% | EY > 21、TDS > 1.20 ✓ |

> Hedrick TDS 1.60（舊化合物模型給 ~1.44）—— Hedrick 無實測，薄 Layer 1 對「粗磨 + 長浸泡（240s）」給較高萃取。屬粗估容忍範圍，非錨點。

---

## 5. 先驗與信心分層

### 5.1 per-roast `E_MAX`（只有 medium_light 被校準）

`E_MAX(roast) = E_MAX_REF · E_MAX_ROAST_FACTOR[roast]`。factor 是**文獻方向先驗**（深焙細胞結構更易溶 → 上限更高），未驗證：

```
very_light 0.92 · light 0.96 · medium_light 1.00 · medium 1.05
moderately_dark 1.09 · dark 1.12 · very_dark 1.14
```

### 5.2 `RETENTION`（per-roast 吸水率 g/g）

沿用文獻值 1.95–2.55（深焙更多孔、retention 較高）；只用於 TDS 的出杯重項。薄 Layer 1 **丟掉**舊 `tds_model.py` 的 dial-slope（±0.03 g/g，對 TDS 影響 < 0.02% —— 粗估不需要）。

### 5.3 `brewer` 幾何（XL）

`BREWER_TAU_MULT = {standard 1.0, xl 1.05}` —— XL 深床萃取略慢。**未校準先驗**（無 XL 折射儀資料），藍圖 §6「容器進一個小 offset 項」。XL 主效應（水量 400ml）走 `water_ml` 直接輸入。

### 5.4 `light` IDEAL 重推（Step 3 §9.1 交接項）

Step 3 的 `light` IDEAL 是用**舊 Layer 1** 重算 tim ⭐4 食譜得到（TDS 1.413 / EY 19.88）。Step 3 §9.1 明示「Layer 1 完成後須重推」。本步驟用新 Layer 1 重算：

tim ⭐4 食譜（light，100°C / dial 3.7 / 60s / 25g / XL 400ml）→ **TDS 1.2055 / EY 17.02**。

| 軸 | Step 3 (舊 Layer 1) | Step 4 (新 Layer 1) |
|---|---|---|
| acidity | 0.3770 | 0.3559 |
| sweetness | 0.1774 | 0.1929 |
| body | 0.0771 | 0.0444 |
| bitterness | 0.3096 | 0.2311 |
| astringency | 0.1613 | 0.1602 |
| roast | 0.2283 | 0.1869 |

新 Layer 1 把同一支 tim ⭐4 食譜讀得**較低 TDS**（1.21 vs 1.41）→ acidity/bitterness/roast 軸隨之下降。tim n=3 bracket **仍正確排序**（感官距離 ⭐4 0.000 < ⭐3 0.032 < ⭐2 0.060）。`light` 仍是 **provisional**：tim 不是 Layer 1 校準錨點，其 (TDS,EY) 帶著未校準的 `E_MAX_ROAST_FACTOR['light']` 先驗 → 仍是 feedback 第一精修對象。

---

## 6. 發現 / 開放項目（medium_light，交給 Step 5）

Step 4 **不動** `labels.json` 的 medium_light / medium / moderately_dark（Step 3 將 medium_light 定為 Tier A frozen）。但新 Layer 1 暴露兩個 medium_light 相關事實，需 Step 5 處理：

1. **Hoffman EY ≈ 19.97%，非 21。** `labels.json` 的 `medium_light.anchor_brew.ey = 21.0`。「21」是文章「EY 20–22%」區間的鬆散中點，與實測 TDS 1.23 + 真實 retention **不自洽**（EY 21 對應 TDS ≈ 1.29）。自洽值是 EY ≈ 20。`labels.json` 本身內部一致（`ideal = predict_axes(1.23, 21)` 仍成立），故未動；但若 Step 5 要 anchor_brew 反映 Layer 1 實際輸出，應改 ey 21→19.97 並重推 medium_light IDEAL（影響：acidity 0.274→~0.288，其餘 < 0.01）。

2. **使用者 ⭐5 medium_light 杯落在 TDS ≈ 1.36，非 1.23。** 新 Layer 1 重算兩杯 ⭐5（24g/400ml XL）→ EY ≈ 20.0%、**TDS ≈ 1.36**。Step 3 §4 曾稱「⭐5 重算落 ~1.23/18、距 medium_light IDEAL 僅 dist 0.043」—— 那是**舊 Layer 1**（舊 `brew_capacity` 把高劑量 EY 壓到 18）。新 Layer 1 溫度溫和、dose 效應溫和 → ⭐5（24g/400ml = 1:16.7，比 Hoffman 11g/200ml = 1:18.2 更濃）自然得較高 TDS。**這是濃度算術，非模型錯誤。** 後果：使用者實際偏好的杯比 Hoffman 錨點更濃 → medium_light IDEAL（錨在 Hoffman 1.23）可能需往使用者 ⭐5 偏好校準。屬 Step 5 + feedback-refine 議題（藍圖 §8 預期 feedback 驅動精修）。

---

## 7. 退役模組

| 模組 | 狀態 |
|---|---|
| `models/ey_model.py` | 退役 —— 被 `layer1.predict_ey` 取代。仍在 disk（`runtime.py`/`optimizer.py`/`diagnose_anchor.py` 仍 import）→ Step 5 改接線後刪除。|
| `models/tds_model.py` | 退役 —— `predict_tds` 取代 `calc_tds`/`calc_retention`；drip/channeling/press 相關函式整組退役（薄 Layer 1 不建模技法）。|
| `models/compounds.py` | 退役 —— 6 化合物動力學由 `models/sensory.py`（Layer 2，Step 2 已落地）取代。|

舊三模組完整保留於 git branch `compound-model-legacy`。Step 4 為純加法，未刪檔 → `main` 在 Step 4 後仍是 Step 3 之後的「既定過渡狀態」（舊評分鏈失效，待 Step 5/7）。

---

## 8. 給 Step 5 的交接

1. **接線：** Phase 10 管線 = `旋鈕 → layer1.brew() → {tds,ey} → sensory.predict_axes(tds,ey,roast,temp,dial) → 6 軸 → 評分`。Step 5 改寫 `runtime.evaluate_recipe` / `optimizer.py` 走此鏈，然後刪舊三模組。
2. **`brew()` 簽名：** `(roast, temp, dial, steep_sec, dose, water_ml, brewer="standard")`。`water_ml` 由呼叫端傳（`constants.BREWER_PRESETS[brewer]["water_ml"]`）。
3. **medium_light 兩個發現（§6）** —— Step 5 重寫評分時一併處理：anchor_brew.ey 21→20、以及 ⭐5 偏好 vs Hoffman IDEAL 的落差。
4. **評分移除 `tds_factor`**（藍圖 §7.2）：TDS 對風味的影響已完全經 6 軸表達。
5. **溫度是弱槓桿：** Layer 1 `ALPHA`≈0.019、Layer 2 `b_temp`=0 → Phase 10 整體對溫度近乎不敏感（藍圖 §13 的既定後果）。Step 5 的 optimizer 對溫度幾乎無梯度 —— UI/說明需同步（若要保留溫度建議，靠 `SCORCH` 類感官閾值或 feedback）。

---

## 9. 參考資料

- 藍圖 [`PHASE10_SENSORY_REFOUNDING.md`](PHASE10_SENSORY_REFOUNDING.md) §6（薄 Layer 1 規格）、§13（溫度/研磨對 TDS/EY 幾乎無感）。
- [`PHASE10_STEP3_LABELS.md`](PHASE10_STEP3_LABELS.md) §9.1（light IDEAL 重推交接）、§4（信心分層）。
- Sci Rep 2021 — *An equilibrium desorption model for the strength and extraction yield of full immersion brewed coffee*（PMC7994670）。
- Hoffmann《Brewing for Balance, Acidity, or Sweetness》—— 3 錨點實測 TDS。
- 校準重現：`models/layer1.py` 內嵌全部 5 參數 + 先驗；§3.1 錨點代入即重現 §4.1。
