# Phase 10 — Step 4：薄 Layer 1（knob → TDS/EY）

> **狀態：完成（2026-05-22）。** Phase 10 §11 執行步驟表的 Step 4 交付物。
> 程式：[`../models/layer1.py`](../models/layer1.py)。
> 上游：[`PHASE10_SENSORY_REFOUNDING.md`](PHASE10_SENSORY_REFOUNDING.md)（藍圖 §6 薄 Layer 1 規格）、[`PHASE10_STEP3_LABELS.md`](PHASE10_STEP3_LABELS.md) §9.1（light IDEAL 待 Step 4 重推）。

---

## 1. 交付物摘要

- `models/layer1.py` —— `brew(roast, temp, dial, steep_sec, dose, water_ml, brewer) → {ey, tds}`。取代 `ey_model.py` + `tds_model.py` + `compounds.py` 全套。
- 模型 = **單一一階逼近平衡上限**（equilibrium-desorption 粗形）：`EY = E_MAX·(1−exp(−t_eff/τ))·f_ratio`。純 `exp()` 結構、全域單調、飽和、無閾值（CLAUDE.md 原則 #1）。
- **5 個參數，只校準 1 個錨點：** `E_MAX` 由 Hoffman（唯一的素浸泡錨點）解出;`TAU_REF`/`ALPHA`/`GAMMA`/`K_RATIO` 4 個是物理先驗。**April/Champion 因「技法 confound」剔除**（§3.1）—— 此為對藍圖 §6（原訂 Hoffman/April/Champion/Hedrick 多錨點校準）的**刻意修正**，使用者裁決 2026-05-22。
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

## 3. 校準（單一 Hoffman 錨點）

### 3.1 為什麼只用 Hoffman —— April/Champion 是「不同黑箱」

薄 Layer 1 建模的是**素浸泡**：旋鈕只有 溫度/研磨/dose/水量/時間/容器，**沒有技法旋鈕**。

3 個有實測 TDS 的文獻錨點裡，**只有 Hoffman 是素浸泡**（直立、單次旋轉、無花招）。另兩個是技法沖煮：

| 錨點 | 技法 | 與薄 Layer 1 的關係 |
|---|---|---|
| **Hoffman** | 直立浸泡、swirl、壓 | ✅ 素浸泡 —— in-distribution，可校準 |
| April | 半密封 + 二段注水 | ❌ 技法沖煮 —— 不同流程 |
| Championship | 倒置 + 高劑量攪動 | ❌ 技法沖煮 —— 不同流程 |

April/Champion 在 80–85°C 仍萃出 TDS 1.17 / 1.56，靠的是**技法**。薄 Layer 1 看不到技法 → 若硬把它們當錨點，模型只能用手上的旋鈕去解釋「低溫卻萃得好」，結果把**技法的功勞錯誤折進一個過小的溫度係數**。Step 4 早先版本的 3-錨點擬合就證實了這點：`ALPHA` 被擠到 0.0194（Q10≈1.2，太溫和）—— 那是 April/Champion 技法污染出來的假象，不是物理。

> **原則：被污染的錨點比沒有錨點更糟。** April/Champion 與薄 Layer 1 是**不同的黑箱**（不同流程），混進校準只會讓參數失真。故剔除；只留 Hoffman。

### 3.2 參數（1 解出 + 4 物理先驗）

| 參數 | 值 | 角色 | 來源 |
|---|---|---|---|
| `E_MAX_REF` | 23.346 % | medium_light 平衡上限 | **由 Hoffman 解出**（唯一擬合數）|
| `TAU_REF` | 50.0 s | 速率常數（98°C / dial 4.3 / standard）| 物理先驗 —— 愛樂壓浸泡 120s 達平衡 ~93% |
| `ALPHA` | 0.026 /°C | 溫度 → 速率 | 物理先驗 —— Arrhenius Ea≈30 kJ/mol 線性化 |
| `GAMMA` | 0.32 /dial | 研磨 → 速率 | 物理先驗 |
| `K_RATIO` | 1.5 | 沖煮比容量係數 | 物理先驗 |

固定偏移：`T_REF=98`、`DIAL_REF=4.3`、`T_PRESS_OFFSET=10s`。

**解法：** `E_MAX` 解到讓模型重現 Hoffman 實測 TDS 1.23（→ EY 19.96%）。其餘 4 個參數是物理先驗 —— 家裡無折射儀 → 除 Hoffman 外產不出任何 (旋鈕→實測 TDS) 配對（藍圖 §6）。受「單調 + 飽和」結構約束，1 個素浸泡錨點 + 4 個物理先驗就釘出一條合理的粗估曲線（**結構替代缺的資料**）。

**`ALPHA` 是物理先驗,不是擬合值。** Arrhenius：萃取速率 ∝ exp(−Ea/RT)。取 Ea≈30 kJ/mol（擴散主導的萃取活化能量級），在 98°C 線性化 → `ALPHA = Ea/(R·T²) = 30000/(8.314·371.15²) = 0.0262/°C`，Q10≈1.3。這讓**溫度成為一個物理上站得住、適度的槓桿**（88→98°C 約動 1.4pp EY，§4.4）—— 取代早先被 April/Champion 污染擠出的 0.0194。

> Layer 2（`models/sensory.py`）的 `b_temp=0`：固定 TDS/EY 下溫度對 6 感官軸**無直接項**（Batali 2020）。所以溫度對風味的影響**完全經由 EY/TDS 傳遞** —— 溫度是萃取旋鈕、不是風味軸。Layer 1 的 `ALPHA` 是溫度唯一的入口，因此它的量級要誠實。

---

## 4. 驗證

### 4.1 Hoffman 錨點重現（精確）

| | predicted EY | predicted TDS | 實測 TDS |
|---|---|---|---|
| Hoffman（98°C / 4.3 / 120s / 11g / 200ml）| 19.96% | 1.2300% | 1.23 |

**April/Champion —— 不是錨點，只作「技法落差」示意：** 用技法盲的薄 Layer 1 跑它們的食譜 → April 預測 TDS 1.08（實測 1.17）、Champion 預測 TDS 1.42（實測 1.56）。預測低於實測的那段落差 ≈ **技法的貢獻**（半密封 / 倒置攪動補出的額外萃取）。模型誠實地少算 —— 因為它本來就沒有技法旋鈕。

### 4.2 單調性掃描（medium_light XL，base 95°C / 4.3 / 120s / 24g）

| 掃描 | 值 | EY |
|---|---|---|
| 溫度 | 82 / 88 / 94 / 100°C | 17.24 → 18.24 → 19.12 → 19.84 ↑ 飽和 |
| 研磨 | dial 3.0 / 4.3 / 5.5 / 7.0 | 20.75 → 19.25 → 16.92 → 13.26 ↓（越粗越少）|
| 浸泡 | 30 / 90 / 180 / 360s | 10.83 → 17.74 → 20.67 → 21.39 ↑ 飽和 |
| 劑量 | 16 / 22 / 28 / 34g | 19.80 → 19.38 → 18.99 → 18.61 ↓（溫和）|

全部單調、飽和、無斷點、無 blow-up。

### 4.3 Sanity 點（素浸泡，標準 200ml，無實測 TDS）

| 配方 | EY | TDS | 期望 |
|---|---|---|---|
| Hedrick（95°C / 6.0 / 240s / 14g）| 19.69% | 1.596% | 寬 sanity band ✓（素浸泡長浸泡）|
| Under-extract（93°C / 6.5 / 60s / 11g）| 9.83% | 0.609% | EY < 15、TDS < 0.85 ✓ |
| Over-extract（99°C / 3.5 / 240s / 11g）| 21.54% | 1.326% | EY > 21、TDS > 1.20 ✓ |

### 4.4 溫度槓桿（medium_light XL，4.3 / 120s / 24g）

| 溫度 | EY | TDS |
|---|---|---|
| 88°C | 18.24% | 1.241% |
| 90°C | 18.55% | 1.262% |
| 94°C | 19.12% | 1.300% |
| 98°C | 19.62% | 1.333% |

88→98°C ≈ +1.4pp EY / +0.09 TDS —— 在使用者實際範圍（93–100°C）內溫度是個**看得見、但溫和**的槓桿。極端（80°C）效應更大；技法沖煮（April/Champion）能在低溫補回的那段，本模型不涵蓋。

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

tim ⭐4 食譜（light，100°C / dial 3.7 / 60s / 25g / XL 400ml）→ **TDS 1.1868 / EY 16.75**（60s 是短浸泡 → 僅達平衡 ~75%）。

| 軸 | Step 3 (舊 Layer 1) | Step 4 (新 Layer 1) |
|---|---|---|
| acidity | 0.3770 | 0.3541 |
| sweetness | 0.1774 | 0.1960 |
| body | 0.0771 | 0.0418 |
| bitterness | 0.3096 | 0.2220 |
| astringency | 0.1613 | 0.1599 |
| roast | 0.2283 | 0.1811 |

tim n=3 bracket **仍正確排序**（感官距離 ⭐4 0.000 < ⭐3 0.033 < ⭐2 0.055）。`light` 仍是 **provisional**：tim 不是 Layer 1 校準錨點（Layer 1 只錨在 Hoffman 素浸泡），其 (TDS,EY) 帶著未校準的 `E_MAX_ROAST_FACTOR['light']` 先驗 → 仍是 feedback 第一精修對象。

---

## 6. 發現 / 開放項目（medium_light，交給 Step 5）

Step 4 **不動** `labels.json` 的 medium_light / medium / moderately_dark（Step 3 將 medium_light 定為 Tier A frozen）。但新 Layer 1 暴露兩個 medium_light 相關事實，需 Step 5 處理：

1. **Hoffman EY ≈ 19.96%，非 21。** `labels.json` 的 `medium_light.anchor_brew.ey = 21.0`。「21」是文章「EY 20–22%」區間的鬆散中點，與實測 TDS 1.23 + 真實 retention **不自洽**（EY 21 對應 TDS ≈ 1.29）。自洽值是 EY ≈ 20。`labels.json` 本身內部一致（`ideal = predict_axes(1.23, 21)` 仍成立），故未動；若 Step 5 要 anchor_brew 反映 Layer 1 實際輸出，應改 ey 21→19.96 並重推 medium_light IDEAL（影響：acidity 0.274→~0.288，其餘 < 0.01）。

2. **使用者 ⭐5 medium_light 杯落在 TDS ≈ 1.36，非 1.23。** 新 Layer 1 重算兩杯 ⭐5（24g/400ml XL）→ EY ≈ 19.9%、**TDS ≈ 1.36**。Step 3 §4 曾稱「⭐5 重算落 ~1.23/18、距 medium_light IDEAL 僅 dist 0.043」—— 那是**舊 Layer 1**。新 Layer 1 下 ⭐5（24g/400ml = 1:16.7，比 Hoffman 11g/200ml = 1:18.2 更濃）自然得較高 TDS。**這是濃度算術，非模型錯誤。** 後果：使用者實際偏好的杯比 Hoffman 錨點更濃 → medium_light IDEAL（錨在 Hoffman 1.23）可能需往使用者 ⭐5 偏好校準。屬 Step 5 + feedback-refine 議題（藍圖 §8 預期 feedback 驅動精修）。

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
5. **溫度是適度槓桿、且只經 EY/TDS 作用：** Layer 1 `ALPHA=0.026`（Arrhenius Ea≈30，Q10≈1.3）→ 溫度真實地推動 EY/TDS；Layer 2 `b_temp=0` → 溫度無直接感官項。所以溫度的風味效應**完全經 EY/TDS 中介**（Batali 2020：固定 TDS/EY 下溫度無感官效應）—— 這是正確架構（溫度是萃取旋鈕、非風味軸），不是「溫度無感」。Step 5 的 optimizer 對溫度會有真實（適度）梯度。
6. **April/Champion 不再是 Layer 1 錨點。** Step 7 重寫 `diagnose_anchor.py` 時，它們應改為「技法落差示意」或移除，不可當素浸泡物理錨點檢查。

---

## 9. 參考資料

- 藍圖 [`PHASE10_SENSORY_REFOUNDING.md`](PHASE10_SENSORY_REFOUNDING.md) §6（薄 Layer 1 規格）、§13。
- [`PHASE10_STEP3_LABELS.md`](PHASE10_STEP3_LABELS.md) §9.1（light IDEAL 重推交接）、§4（信心分層）。
- Sci Rep 2021 — *An equilibrium desorption model for the strength and extraction yield of full immersion brewed coffee*（PMC7994670）。
- Batali et al. 2020 — *Brew temperature, at fixed brew strength and extraction, has little impact on the sensory profile of drip brew coffee*（→ 溫度經 EY/TDS 中介、Layer 2 `b_temp=0`）。
- Hoffmann《Brewing for Balance, Acidity, or Sweetness》—— Hoffman 錨點實測 TDS 1.23（April/Champion 同文，但為技法沖煮 → 不作本 Layer 1 錨點）。
- 校準重現：`models/layer1.py` 內嵌 5 參數 + 先驗；§3.2 Hoffman 代入即重現 §4.1。
