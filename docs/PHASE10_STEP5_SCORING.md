# Phase 10 — Step 5：感官距離 + optimizer 重接線

> **狀態：完成（2026-05-22）。** Phase 10 §11 執行步驟表的 Step 5 交付物。
> 程式：[`../models/distance.py`](../models/distance.py)、[`../optimizer.py`](../optimizer.py)、[`../models/ideal.py`](../models/ideal.py)、[`../main.py`](../main.py)、[`../output/`](../output/)。
> 上游：[`PHASE10_SENSORY_REFOUNDING.md`](PHASE10_SENSORY_REFOUNDING.md)（藍圖 §0 label 移除、§7.2 評分）、[`PHASE10_STEP4_LAYER1.md`](PHASE10_STEP4_LAYER1.md) §8（給 Step 5 的交接）。
>
> **使用者裁決（2026-05-22，本步驟執行中）：** ① 取消 0–100 評分 —— 直接呈現「距目標多遠」的距離。② 水質（GH/KH/mg_frac）整個移除。下文已反映此二裁決。

---

## 1. 交付物摘要

- **評分 → 距離。** `models/scoring.py`（`flavor_score` / 6 化合物 / `tds_factor` / 感知 gate）退役 → 新 **`models/distance.py`**：`axis_distance(predicted, ideal)` = 預測 6 感官軸 vs 該焙度 6 軸 IDEAL 的**加權 RMS 距離**。**無 0–100 評分** —— optimizer 直接以距離排序、輸出距離。
- **`optimizer.py` 重接線** —— 走 Phase 10 管線 `旋鈕 → layer1.brew → {tds,ey} → sensory.predict_axes → 6 軸 → distance`。溫度為**輸入**、`dose×dial×steep` 為**搜尋維度**；候選以 `distance` 升冪排序。
- **`label` 概念的程式殘餘清除** —— `--label` CLI flag、`optimize_parallel()`、Channel A/B、`_score_against_label` 全移除（藍圖 §0）。
- **水質移除** —— `--gh/--kh/--mg-frac/--preset` CLI flag、`runtime.resolve_water_profile`、`data/water_presets.py` 刪除；`recipe_id` 不再含水質。Phase 10 的 Layer 1/2 本就不建模水質 → 移除等於刪掉一組從未驗證的死碼。
- **改名** —— `data/labels.json` → `data/ideal.json`；`models/labels.py` → `models/ideal.py`（`ideal_abs` 等化合物函式刪除，保留 per-roast IDEAL 查詢 + `recipe_id`）。
- **`output/` 三檔重寫** —— terminal / export / radar 改顯示 6 感官軸 vs IDEAL + 距離。
- **退役舊 Layer 1** —— `models/compounds.py` / `ey_model.py` / `tds_model.py` 刪除（Step 4 交接「Step 5 改接線後刪」；完整保留於 branch `compound-model-legacy`）。
- `constants.py` 新增 `DEFAULT_TEMP`（per-roast 慣例水溫預設）。

---

## 2. 距離模型（`models/distance.py`）

### 2.1 公式

```
distance = sqrt( Σ w_axis · (pred_axis − ideal_axis)²  /  Σ w_axis )
```

6 感官軸偏差的**加權 RMS**，單位 = CATA 偵測頻率（與軸值、與 terminal 逐軸差顯示的單位相同）。`distance = 0` 表示預測等於 IDEAL，越大越遠。全域平滑（CLAUDE.md 原則 #1）—— 無閾值、無 log、無 exp。**排序用的數字就是顯示的數字。**

| 參數 | 值 | 角色 |
|---|---|---|
| `AXIS_WEIGHT` | astringency 0.3、其餘五軸 1.0 | astringency 降權 —— cotter 回歸 R²=0.03（在訓練網格近乎平、未訓練,見 `models/sensory.py`）,預測值帶不了多少訊號 |

`AXIS_WEIGHT` 是本步驟**唯一的自由旋鈕**,誠實標為先驗、待 feedback 精修;Step 7 重新錨定時複查。

### 2.2 為什麼不要 0–100 評分（使用者裁決）

「評分」隱含一個客觀分數,但 cotter hedonic-liking 資料證實**沒有客觀『最好』的咖啡**（喜好曲面近乎平、消費者分兩群偏好相反 —— 見 `data/ideal.json` medium_light `seed`）。所以 optimizer 輸出**白話的東西：這杯離「你的」目標多遠**。同時這也消掉了原 Step 5 草案的校準負債 —— 原 `axis_distance_score` 用 `exp(−loss/σ)` 把距離壓成 0–1 再 ×100,那個 `AXIS_SIGMA` 是無資料支撐的猜測寬度。改成直接距離後,`AXIS_SIGMA` / `exp()` / log / `_AXIS_FLOOR` 全部不需要;模組從 ~50 行半推半猜的數學收斂成一條加權 RMS。

### 2.3 為什麼沒有獨立 TDS 項（藍圖 §7.2）

Phase 8 在化合物 reward 之上又乘一個繞 `tds_prefer` 的 Super-Gaussian `tds_factor`。Phase 10 整個拿掉:**TDS 對風味的影響已完全經 6 軸表達** —— Layer 2（`models/sensory.py`）把每一軸都對 TDS/EY 回歸,TDS 太高自然推高 `bitterness`/`roast`、壓低 `sweetness`,預測點自己就偏離 IDEAL。再放一個獨立 TDS 項 = 同一個物理事實計分兩次。同理**無 TDS floor / EY floor** —— 欠萃 / 過萃杯的 6 軸向量自然偏離 IDEAL → 距離大（§4.2）。原則 #3 落地（「感官模型自我鑑別」,藍圖 §9）。

### 2.4 焙度內 roast offset 自動抵銷

`predict_axes` 每一軸都含 `_ROAST_OFFSET[roast]`（文獻先驗、未驗證）。但在**同一焙度內**比距離時,預測 6 軸與 IDEAL 6 軸帶的是**同一個 offset** → `(pred − ideal)` 相減時 offset 抵銷。所以未驗證的 roast offset **不污染焙度內排序**;它只在跨焙度比較時起作用,而本系統不跨焙度比距離。焙度內,距離本質上是「`(tds,ey,dial)` 距 `anchor_brew` 多遠」的平滑重參數化。

---

## 3. optimizer 重接線（`optimizer.py`）

### 3.1 管線

```
evaluate_recipe(roast, brewer, temp, dial, steep, dose)
  → layer1.brew(roast,temp,dial,steep,dose,water_ml,brewer) → {tds, ey}
  → sensory.predict_axes(tds, ey, roast, temp, dial)        → 6 軸
  → distance.axis_distance(6 軸, ideal.roast_ideal(roast))  → distance
```

候選 dict 帶 `distance`;`optimize()` 以 `distance` **升冪**排序,回傳 Top-N（最接近在前）。

### 3.2 I/O 架構（藍圖交接 §8 #7）

- **輸入（使用者給）：** `roast`、`brewer`（→ `water_ml`）、`temperature`。
- **搜尋（optimizer 吐）：** `dose × dial × steep` —— 命中該焙度 6 軸 IDEAL 的組合。
- **溫度不進搜尋維度。** 溫度只經 Layer 1 的 EY/TDS 作用（Layer 2 `b_temp=0`）;對任一 `(tds,ey,dial)` 目標,換溫度只是換 steep 命中同一杯 → 優化溫度只吐 tie-break 噪音。
- grid：`dial` 3.0–7.5 步 0.1（46）× `steep` 30–420s 步 30（14）× `dose` 該焙度 `dose_per_100ml` ∩ brewer dose 範圍（XL 步 1.0g、standard 步 0.5g）。約 5–6 千候選,layer1 + predict_axes 皆廉價多項式 → 全域掃描 < 1s。

### 3.3 移除的東西

`optimize_parallel()` / Channel A/B / `_score_against_label` / `--label` flag —— 一個固定焙度只有**一個**感官 IDEAL（藍圖 §0）。`score_logged_recipe` 保留（feedback recompute 路徑）。

### 3.4 `DEFAULT_TEMP`（per-roast 慣例水溫）

`constants.DEFAULT_TEMP` —— `light` 98 / `medium_light` 95 / `medium` 92 / `moderately_dark` 89（°C）。溫度是中性變數、無「可推導最佳值」→ 此預設是**慣例 + 安全**（淺焙熱、深焙涼、離沸點留 headroom）,非研究結果;使用者用舌頭微調（藍圖交接 §8 (c)）。CLI `--temp` 省略時帶入。

### 3.5 水質移除

Phase 10 的 Layer 1（`layer1.py`）與 Layer 2（`sensory.py`）都不讀水質 → GH/KH/mg_frac 在 Phase 10 對 TDS/EY/軸/距離**完全無作用**。舊模型曾有的水質啟發式（`SOFT_WATER_BITTER_AMP`、KH→酸質衰減）本身就掛著「待實測後校正」、從未驗證。使用者裁決整組移除:CLI flag、`resolve_water_profile`、`data/water_presets.py` 刪除,`recipe_id` 不再含水質（→ 只差水質的兩杯收斂成同一 id,正確 —— 它們本就是同一杯）。`feedback.jsonl` 的 `water` 欄位變 vestigial(同 `label`)—— Step 6 清 schema。

---

## 4. 驗證

### 4.1 CLI 煙測（terminal / json / csv / radar 全通）

| roast / brewer / temp | Top 1 配方 | 預測 TDS / EY | 距離 |
|---|---|---|---|
| medium_light / XL / 95°C | dial 4.5 · 2:30 · 24g | 1.352 / 19.90 | **0.0006** |
| light / XL / 98°C | dial 3.5 · 1:00 · 25g | 1.192 / 16.83 | 0.0019 |
| medium / standard / 92°C | dial 4.4 · 2:00 · 12g | 1.360 / 19.88 | 0.0014 |
| moderately_dark / XL / 89°C | dial 4.7 · 3:00 · 22g | 1.347 / 21.62 | 0.0114 |

Top 1 全部落在該焙度 `anchor_brew` 鄰近 —— 管線自洽。

### 4.2 鑑別度（medium_light XL 95°C，純軸距離、無 floor）

| 杯 | 配方 | TDS / EY | 距離 |
|---|---|---|---|
| 好杯（近錨點）| 4.4 · 150s · 24g | 1.360 / 20.02 | **0.0013** |
| 過萃（極細 + 極長 + 高劑量）| 3.0 · 420s · 28g | 1.711 / 21.13 | 0.0591 |
| 欠萃（極粗 + 極短）| 7.4 · 30s · 16g | 0.221 / 5.07 | **0.6044** |

好杯 ≪ 過萃 ≪ 欠萃,單調。距離不經 exp() 壓縮 → 鑑別度比原評分版更直白（過萃離目標約 45×、欠萃約 460×）。

### 4.3 tim ⭐2/⭐4 bracket —— Phase 10 動機 bug

| tim 杯 | 配方 | TDS / EY | 距離 | 使用者評語 |
|---|---|---|---|---|
| ⭐4 | light · 100°C · 3.7 · 60s · 25g | 1.187 / 16.75 | **0.0000** | 淺焙酸 + 茶感、乾淨 |
| ⭐3 | light · 100°C · 3.7 · 60s · 24g | 1.137 / 16.81 | 0.0143 | 偏薄、香味淡 |
| ⭐2 | light · 98°C · 3.9 · 60s · 28g | 1.277 / 15.83 | 0.0240 | ROASTY、失去淺焙特色、太濃 |

排序正確、與星等單調 —— **原始 bug（模型把偏黑的 ⭐2 排在 tea-brown ⭐4 之上）已修。** 但須誠實記錄:⭐2 距離僅 0.024,與 ⭐4 差距不大。根因是 Layer 2（cotter）**結構上看不出 ⭐2 哪裡壞** —— cotter 無「高 TDS / 低 EY 欠發展」象限樣本（Step 2 §7 早已指出,Step 5 無法單獨修）。修法是 feedback 精修 light IDEAL,或日後第 7 軸 —— 不是距離公式的事。

### 4.4 roast→方法湧現（藍圖交接 §8 (f)）

「淺焙細/短、深焙粗/長」未手寫死,由 optimizer 命中各焙度 IDEAL 自然湧現:light → dial 3.5 / 60s（細、短）;medium_light → 4.5 / 150s;medium → 4.4 / 120s;moderately_dark → 4.7 / 180s（粗、長）。方向正確。

---

## 5. 發現 / 已知限制

1. **moderately_dark placeholder IDEAL 略不可達。** 它的 `anchor_brew` 是「medium_light 的 brew 點 `(1.3537, 19.92)` 套 moderately_dark roast offset」的確定性 placeholder（Step 3 §4）。但 `layer1.E_MAX_ROAST_FACTOR['moderately_dark']=1.09`（深焙上限更高）使得「TDS≈1.35 同時 EY≈19.92」搆不到 —— optimizer 最佳落在 EY≈21.6、`acidity` 軸差 −0.025,距離卡在 ~0.011。**這是 placeholder 的已知資料缺口**（medium,factor 1.05,仍可達 dist ~0.001）,非距離 bug;feedback 校準時連同 anchor_brew 修正。
2. **`AXIS_WEIGHT` 是先驗。** astringency 0.3 / 其餘 1.0 是合理起點、非 fit 值。Step 7 用 6 錨點重新錨定時複查。
3. **絕對距離,body 軸相對被輕看。** body 自然落在 0.04–0.11、bitterness 落在 0.22–0.41;加權 RMS 取絕對偏差 → body 的同等「百分比」偏離在距離裡權重較小（使用者裁定要絕對值,逐軸差表仍把 body 單列,可自行判讀）。

---

## 6. 過渡狀態（藍圖「規模 ≈ Phase 8×2」的既定中間態）

| 檔案 | 狀態 | 修復步驟 |
|---|---|---|
| `models/distance.py` `optimizer.py` `models/ideal.py` `main.py` `output/*` | ✅ Step 5 重寫完成、CLI 全通 | — |
| `webapp.py`、`models/feedback.py` | ⚠️ import 失敗（依賴已刪的 `models.scoring`/`models.labels`/`optimize_parallel`/`水質`;`feedback` 仍要求 `water` 欄位、`recompute_entry` 仍傳 `label=`）| **Step 6**（webapp label 下拉 + 水質 UI 移除、加溫度控制、feedback schema）|
| `diagnose_anchor.py`、`tests/` | ⚠️ import 失敗（依賴已刪的 `compounds`/`flavor_score`,仍是 label 島斷言）| **Step 7**（重寫成 Layer 1 物理 band / Layer 2 感官距離）|
| `.claude/hooks/anchor_check.py` | ⚠️ 仍呼叫 `diagnose_anchor.py`(已壞) | **Step 7**（與 diagnose 一起更新）|

舊 `compounds.py`/`ey_model.py`/`tds_model.py`/`scoring.py`/`labels.py`/`water_presets.py` 已刪,完整保留於 git branch `compound-model-legacy`。

---

## 7. 給 Step 6 / Step 7 的交接

**Step 6（feedback / webapp）：**
1. `webapp.py` 移除 label 下拉 + 水質 preset UI;`/api/optimize` 改呼叫單一 `optimize(roast, brewer, temp, top_n)`,加溫度控制（per-roast `DEFAULT_TEMP` 預設、使用者可調）。
2. `_serialize_result` / `_with_current_derived` 改用 6 軸 + IDEAL + `distance`,不再有 `compounds_abs` / `ratios` / `score`。
3. `models/feedback.py`:`append_feedback` 不再要求 `water` 欄位（schema 去水質);`recompute_entry` 去掉 `label=` 與水質參數（`score_logged_recipe` 已無)。`feedback.jsonl` 既有的 `label` / `water` 欄位變 vestigial（保留為歷史)。可考慮把 water 留作 feedback 的選填**文字註記**（未來若要建模水質的備料）,但不再是模型輸入。
4. result dict 新欄位:`distance`、`axes`、`ideal`、`brewer_size`、`roast`;舊 `score` / `compounds` / `t_slurry` / `press_sec` 等不再存在。

**Step 7（diagnose / tests）：**
1. `diagnose_anchor.py` 重寫:Layer 1 物理 band（`layer1.brew` 對 Hoffman 重現 TDS 1.23）+ Layer 2 感官距離（各焙度 anchor_brew 應 dist≈0、under/over 應 dist 大）。April/Champion 不再是 Layer 1 素浸泡錨點（Step 4 §8 #6）。
2. 用 under/over 錨點複查 `AXIS_WEIGHT`（§5.2）。
3. `tests/` 全部重寫（舊測試依賴已刪模組;`test_water_presets.py` 已隨 `water_presets.py` 刪除）。
4. `.claude/hooks/anchor_check.py` 的 `TRIGGER_SUFFIXES` 更新（移除 `compounds.py`/`ey_model.py`/`tds_model.py`/`scoring.py`,加 `layer1.py`/`sensory.py`/`distance.py`/`ideal.py`）。

---

## 8. 參考資料

- 藍圖 [`PHASE10_SENSORY_REFOUNDING.md`](PHASE10_SENSORY_REFOUNDING.md) §0（label 移除）、§7.2（評分、`tds_factor` 移除）、§9（原則改寫）。
- [`PHASE10_STEP4_LAYER1.md`](PHASE10_STEP4_LAYER1.md) §8（給 Step 5 的交接 —— 接線、I/O 架構、溫度為輸入）。
- [`PHASE10_STEP3_LABELS.md`](PHASE10_STEP3_LABELS.md)（`data/ideal.json` schema v5、信心分層）、[`PHASE10_STEP2_LAYER2.md`](PHASE10_STEP2_LAYER2.md)（`predict_axes`、astringency R²=0.03、§7 tim 限制）。
