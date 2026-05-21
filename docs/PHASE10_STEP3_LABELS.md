# Phase 10 — Step 3：per-roast 感官 IDEAL（label 移除）

> **狀態：完成（2026-05-21）。** Phase 10 §11 執行步驟表的 Step 3 交付物。
> 程式：[`../data/labels.json`](../data/labels.json)（schema v5）。
> 上游：[`PHASE10_STEP2_LAYER2.md`](PHASE10_STEP2_LAYER2.md)（`predict_axes()`）、[`PHASE10_SENSORY_REFOUNDING.md`](PHASE10_SENSORY_REFOUNDING.md) **§0 修訂**（label 移除決策）。

---

## 1. 交付物摘要

- **label 概念移除**（藍圖等級變更，使用者裁決 2026-05-21；論證見藍圖 §0）。Layer 2 的風味目標從「5 個 label 島」改成「**每個焙度一個 6 感官軸 IDEAL**」。
- `data/labels.json` 升至 **schema v5**：頂層 key 從 label 名改成 **roast 名**（`light` / `medium_light` / `medium` / `moderately_dark`），各持一個 `ideal`（6 感官軸）+ `anchor_brew` + `seed` + `description`。
- 4 個 per-roast IDEAL 由 `predict_axes(**anchor_brew)` 機械推導；信心分三層（§4）。
- 此 Step 3 取代本檔早先的「5-label v4」版本（同次 session 內，使用者改方向後重做）。v4 的推導工沒白費 —— 6 軸 `predict_axes` 推導完全沿用，只是分組軸從 label 改成 roast。

---

## 2. 為什麼拿掉 label

完整論證在藍圖 §0。摘要：

- 一台 AeroPress + 一支豆子 + 一個焙度 = **一個固定設定**；固定設定下「好喝」是一個點，不是 5 個並列目標。
- 舊 5 個 label 掛在**異質的錨點**上 —— Hoffman/April/Champion 是同一支 El Tambo（那篇文章確實是「一支豆、三種沖煮目標」），但 Hedrick、tim 是別的豆。5 個 label 從來不是「同一支豆的 5 種風味」，它一半在描述「不同豆/焙度」。
- 使用者實際把 `label` 當「我在泡哪支豆」的代名詞用（`feedback.jsonl`：`balanced`/`coarse-modern` 全 medium_light、`tim` 全 light）—— label 在做 `roast` 該做的事。
- `sweet-body` 早已 UI 隱藏；使用者本就在往「更少 label」走。
- 早先 v4 文件 §4 記錄的彆扭（`sweet-body` 的 sweetness 軸根本不凸、`acid-forward` 的 acidity 軸絕對值第二低）**正是**硬從異質錨點擠 5 個並列 label 的產物 —— label 拿掉，彆扭自動消失。

**保留的東西：** 焙度仍重要（使用者另一個明示：「不同焙度偏好不同」）。所以不是收斂成一個全域 IDEAL，是 **per-roast**。使用者的兩個想法（拿掉 label + per-roast 偏好）在此匯合。

**失去的東西：** 「同支豆今天想喝酸一點」這種刻意調風味的能力（三錨點文章的前提）。使用者明示「好喝只會有一種」，為自己的單人系統砍掉這個一般性。optimizer 的 Top-N 仍會給鄰近變化版。

---

## 3. 4 個 per-roast IDEAL

`anchor_brew` 即推導輸入；`predict_axes(**anchor_brew)` 即重現 `ideal`（軸值四捨五入至 4 位）。

| roast | anchor_brew (tds/ey/roast/dial) | acidity | sweetness | body | bitterness | astringency | roast |
|---|---|---|---|---|---|---|---|
| light | 1.413 / 19.88 / light / 3.7 | 0.3770 | 0.1774 | 0.0771 | 0.3096 | 0.1613 | 0.2283 |
| medium_light | 1.23 / 21.0 / medium_light / 4.3 | 0.2743 | 0.1660 | 0.0583 | 0.2865 | 0.1638 | 0.2723 |
| medium | 1.23 / 21.0 / medium / 4.3 | 0.2393 | 0.1460 | 0.0683 | 0.3215 | 0.1738 | 0.3323 |
| moderately_dark | 1.23 / 21.0 / moderately_dark / 4.3 | 0.1893 | 0.1160 | 0.0883 | 0.3715 | 0.1888 | 0.4123 |

軸值是 CATA 偵測頻率，名目 [0,1]，**不 sum to 1**（各自獨立強度，非質量分率）。

---

## 4. 信心分層（誠實標注）

4 個 IDEAL 全是 `predict_axes` 預測，沒有任一焙度的杯被 DA panel 實測過。差別在錨點來源的可靠度：

| roast | 層級 | 來源與隱憂 |
|---|---|---|
| **medium_light** | **A — 文獻錨點** | Hoffman，**實測 TDS 1.23**。Hoffman 本身是 Layer 1 校準錨點 → 此 TDS 在 Step 4 改寫 Layer 1 後**仍穩定**。使用者 2 杯 ⭐5 回饋（XL 400ml）重算後落 ~1.23/18、距此 IDEAL 僅 **dist 0.043** → 獨立佐證「Hoffman 目標就是這位使用者的『好喝』」（使用者就是瞄準舊 `balanced`=Hoffman IDEAL 才泡出 ⭐5）|
| **light** | **B — 使用者 feedback（暫定）** | tim ⭐4 回饋食譜，用**現行 Layer 1**（XL 400ml）重算 → TDS 1.413 / EY 19.88。tim **不是** Layer 1 校準錨點 → 其「食譜→(TDS,EY)」映射會在 Step 4 換 Layer 1 後位移 → **Step 4 後須重新推導此 IDEAL**。n=3 tim bracket 距離排序正確（⭐4 0.000 < ⭐3 0.026 < ⭐2 0.037）|
| **medium** | **C — 確定性 placeholder** | 無錨點、無 feedback。= `predict_axes` 在 medium_light 的 brew 點（1.23/21/dial 4.3）套 `medium` roast offset。待該焙度有杯被記錄後校準 |
| **moderately_dark** | **C — 確定性 placeholder** | 同上，套 `moderately_dark` offset |

**4 個共通隱憂（沿襲自 Step 2）：**

- `predict_axes` 的 `_ROAST_OFFSET` 是**文獻方向先驗、非 fit**（Step 2 §4.4，cotter 單一焙度）。整個 roast 維度的量級未被驗證 —— 4 個 IDEAL 之間的相對差距是這個未驗證 offset 直接決定的。這正是使用者明示「不同焙度偏好不同、之後要調」要修的東西。
- `astringency` 軸 cotter R²=0.03 → 對 4 個焙度這條軸基本未訓練（4 者 astringency 擠在 0.16–0.19）。
- `predict_axes` 只看 `(TDS, EY, roast, dial)` —— 沖煮技法（低溫、倒置、半密封）不進模型（Layer 2 前提：杯中感官 ≈ f(TDS,EY)）。

---

## 5. 為何記錄『stale 的 feedback TDS/EY』

推導 light IDEAL 時發現：`feedback.jsonl` 裡 `recipe` 區塊存的 `tds`/`ey` 是**記錄當下的模型預測值**，現行模型已不一致 ——

| 杯 | feedback 存的 | 現行模型重算（XL 400ml）|
|---|---|---|
| ⭐5 #1 (medium_light) | TDS 1.414 / EY 20.80 | TDS 1.235 / EY 18.13 |
| ⭐5 #2 (medium_light) | TDS 1.426 / EY 20.98 | TDS 1.230 / EY 18.07 |
| tim ⭐4 (light) | TDS 1.451 / EY 20.43 | TDS 1.413 / EY 19.88 |

→ 推導 IDEAL 一律用**現行模型重算**的 `(TDS, EY)`，不用 feedback 存的值。`feedback.jsonl` 的訓練價值是**定性的**（stars / comment / tags，藍圖 §10）—— 它的 `recipe.tds/ey` 從來不是拿來做數值反推的。

---

## 6. schema v4 → v5 變更

| | v4（5-label，本檔早先版本）| v5（per-roast）|
|---|---|---|
| 頂層 key | label 名 ×5 | roast 名 ×4 |
| `ideal` | 6 感官軸（不變）| 6 感官軸（不變）|
| `ideal_by_roast` | label 內的 per-roast override | **移除** —— 頂層 key 已是 roast，巢狀 override 失去意義 |
| `tds_prefer` / `dial_prefer` | v4 已移除（吸收進 IDEAL）| 維持移除 |
| `anchor_brew` | 有 | 有 |
| `bullseye_anchor` | 有 | 改名 `seed`（含信心層級敘述）|

`tds_prefer` / `dial_prefer` 被 IDEAL 吸收的確認（藍圖 §7.2）不變：TDS 對風味的影響完全經 6 軸表達，能命中該 IDEAL 的 TDS 是 emergent，不需獨立評分欄位。

---

## 7. 已知後果：舊評分鏈暫時失效（Phase 10 過渡狀態）

Step 3 只改 `data/labels.json` 的結構與內容。仍按「label 島 / 化合物分率」假設運作的舊程式會壞：

| 檔案 | 狀態 | 修復步驟 |
|---|---|---|
| `models/labels.py` `ideal_abs()` | KeyError（化合物 key 不存在）| Step 5 |
| `models/scoring.py` `flavor_score()` | 依賴化合物 IDEAL + label 參數 | Step 5 |
| `optimizer.py` `optimize()` / `optimize_parallel()` | label 參數、Channel A/B | Step 5 |
| `diagnose_anchor.py`、`tests/` | label 島斷言 | Step 7 |
| `models/labels.py` `load_labels/label_names/get_label` | 機械上仍運作（回傳 `{roast: spec}`）；命名是 misnomer | Step 5 改名 |

這是藍圖「規模 ≈ Phase 8 × 2」的**既定過渡狀態**。整條鏈在 Step 5（評分）+ Step 7（diagnose/tests）才重新接通。

---

## 8. 開放項目

1. **不同焙度偏好不同 → per-roast IDEAL 校準。** `_ROAST_OFFSET`（`models/sensory.py` 文獻先驗）與 4 個 per-roast IDEAL 的相對差距，全靠這個未驗證 offset。需 per-roast feedback 才能校。`medium` / `moderately_dark` 目前是純 placeholder。
2. **light IDEAL 待 Step 4 後重推。** §4 —— tim 非 Layer 1 錨點，其 `(TDS,EY)` 映射會隨 Step 4 換 Layer 1 位移。
3. **tim / light 信心最低。** 模型尚無「淺焙明亮 vs 悶」訊號（Step 2 §7）—— feedback 第一精修對象。
4. **檔名 misnomer。** `data/labels.json` + `models/labels.py` 已無 label，名稱待 Step 5 改（→ `ideal.json` 等）。

---

## 9. 給 Step 4 / Step 5 的交接

1. **Step 4（薄 Layer 1）：** `medium_light.anchor_brew` 的 `(1.23, 21)` 來自 Hoffman 實測，是 Layer 1 應重現的目標之一。Layer 1 完成後，用新 Layer 1 重算 tim ⭐4 食譜 → 更新 `light.anchor_brew` 與 `light.ideal`。
2. **Step 5（評分重寫）：** IDEAL 已是 6 軸向量、與 `predict_axes` 同尺度 → 直接做 sensory-space 距離。評分流程改成 `roast → IDEAL(roast) → 距離`，**無 label 參數**。移除 `optimize_parallel` / Channel A/B；optimizer 對給定 roast 只找單一最佳。`models/labels.py:ideal_abs()` 在感官模型下無意義 → 移除。一併把 `labels.json` / `labels.py` 改名。
3. **Step 6（feedback / webapp）：** 移除 webapp label 下拉與 `--label` CLI flag；`feedback.jsonl` 的 `label` 欄位變 vestigial（既有紀錄保留為歷史）。

---

## 10. 參考資料

- 藍圖 [`PHASE10_SENSORY_REFOUNDING.md`](PHASE10_SENSORY_REFOUNDING.md) **§0**（label 移除決策）、§7.2（`tds_prefer` 吸收）。
- `models/sensory.py` —— `predict_axes()`、`SENSORY_AXES`、`_ROAST_OFFSET`。
- Step 2 §7（tim 限制）、§4.4（`_ROAST_OFFSET` 為先驗）。
- 推導重現：對任一 roast，`predict_axes(**anchor_brew)` 即得 `ideal`。
