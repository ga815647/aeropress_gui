# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 路由

| 想看什麼 | 去哪 |
|---------|------|
| 待辦任務 / phase 歷史 / 評分鑑別度改革紀錄 | [`TASKS.md`](TASKS.md) |
| 泡法時間軸 / 各時間參數定義 / 三錨點時間圖 | [`BREW_PROTOCOL.md`](BREW_PROTOCOL.md) |
| Data flow / Grid search / 化合物模型 / 評分公式細節 / 感知前處理 / Key files / Water 參數 / 修改方向表 | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| **進行中 — Phase 10 感官重構**（架構、訓練資料、8 步執行步驟）| [`docs/PHASE10_SENSORY_REFOUNDING.md`](docs/PHASE10_SENSORY_REFOUNDING.md) |
| **Phase 10 Step 1 — 6 感官軸定案**（屬性表、軸定義、湧現概念）| [`docs/PHASE10_STEP1_SENSORY_AXES.md`](docs/PHASE10_STEP1_SENSORY_AXES.md) |
| **Phase 10 Step 2 — Layer 2 風味模型**（cotter 回歸、係數、驗證）| [`docs/PHASE10_STEP2_LAYER2.md`](docs/PHASE10_STEP2_LAYER2.md) |
| **Phase 10 Step 3 — per-roast 感官 IDEAL（label 移除）**（per-roast IDEAL、schema v5、信心分層）| [`docs/PHASE10_STEP3_LABELS.md`](docs/PHASE10_STEP3_LABELS.md) |
| **Phase 10 Step 4 — 薄 Layer 1（knob→TDS/EY）**（平衡脫附式、5 參數校準、退役舊模組）| [`docs/PHASE10_STEP4_LAYER1.md`](docs/PHASE10_STEP4_LAYER1.md) |

> **🚧 進行中：Phase 10 — 感官重新奠基。** 模型從「6 化合物」改為「6 感官軸」。藍圖見 [`docs/PHASE10_SENSORY_REFOUNDING.md`](docs/PHASE10_SENSORY_REFOUNDING.md)（架構、訓練資料、8 步執行步驟）。舊化合物模型凍結於 git branch `compound-model-legacy`。**Step 1–4 完成（Step 4 於 2026-05-22）** — 6 感官軸定案（`acidity`/`sweetness`/`body`/`bitterness`/`astringency`/`roast`）+ Layer 2 風味模型 [`models/sensory.py`](models/sensory.py)（`predict_axes()`,cotter 27-cell 回歸）+ **`label` 概念移除**（藍圖 §0,裁決 2026-05-21）→ [`data/labels.json`](data/labels.json) schema v5（per-roast 6 軸 IDEAL,`light`/`medium_light`/`medium`/`moderately_dark`）+ **薄 Layer 1** [`models/layer1.py`](models/layer1.py)（平衡脫附式 `EY=E_MAX·(1−exp(−t/τ))·f_ratio`;`E_MAX` 由 Hoffman 單一**素浸泡**錨點解出、其餘 4 參數物理先驗;April/Champion 為技法沖煮、屬「不同黑箱」故剔除;`light` IDEAL 用新 Layer 1 重推）。**⚠️ 舊評分鏈（`models/scoring.py`/`models/labels.py:ideal_abs`/`optimizer.py`/`diagnose_anchor.py`/`tests/`）暫時失效,待 Step 5/7 重寫 —— 既定過渡狀態;舊 `ey_model`/`tds_model`/`compounds` 退役,Step 5 改接線後刪。下一步 §11 Step 5** — 重寫 `models/scoring.py`（sensory-space 距離,移除 `tds_factor`）。**Step 4 後續（2026-05-22）：medium_light IDEAL 已用使用者 ⭐5 杯重新校準（取代 Hoffman 文獻錨點 —— cotter hedonic 資料證實無「客觀最好」,單人系統以使用者實測 ⭐5 為準）;medium/moderately_dark placeholder 一併重算。****保留項：不同焙度偏好本身就不同,per-roast IDEAL 的 roast 維度靠 `models/sensory.py:_ROAST_OFFSET`（文獻先驗、未驗證）;`medium`/`moderately_dark` 目前是 placeholder,待 feedback 校準。** 下方「僅剩待辦 / 目前狀態」描述的是 Phase 10 之前的 Phase 8 狀態,Phase 10 落地後一併改寫。

**僅剩待辦：**
- **Phase 9 — Feedback UI（webapp 卡片內 comment + tags + stars，append `data/feedback.jsonl`）**；refine 由 Claude 對話讀 jsonl 做語意分析、提建議、編輯 `data/labels.json`，不寫 `refine_label.py`。Schema 規格見 [`docs/FEEDBACK_FORMAT.md`](docs/FEEDBACK_FORMAT.md)
- UI — Chip 標籤重寫（依 Phase 8 label 改 UI 風味描述）
- `light` 槽真淺焙錨點待補（找到 Nordic-style AeroPress 食譜後校準）
- 化合物層 brewer geometry 建模（未來 phase）— XL 深床效應未進化合物層，現用 `dial_offset` 兜底
- 非 medium_light 焙度的 label IDEAL 校準 — Phase 8 僅校準 medium_light 4 個錨點。2026-05-21 新增 `labels.json` v3 `ideal_by_roast` 機制 + `balanced.light` 粗略 override（淺焙搆不到 medium_light 的 CGA/MEL，light×balanced 從 ~56 分修到 ~95）；其餘焙度×label 仍無 roast-specific bullseye。`balanced.light` 是 model-derived 粗估、無實測錨點，待 light-roast balanced 食譜出現後精修

**目前狀態（Phase 8 完成）：** 6 錨點全 PASS（Hoffman 92.8 / April 90.6 / Champion 86.9 / Hedrick 92.5 / Under 0 / Over 44.6）、28 pytest PASS（含新增 Layer 1 `test_compound_calibration.py` × 8 + Layer 2 `test_label_scoring.py` × 8）。`data/labels.json` 持有 4 個 label 島（balanced / acid-forward / sweet-body / coarse-modern），每個自帶 IDEAL fractions + tds_prefer；scoring 層拿掉 `build_ideal_abs` TDS bracket 內插與 `ratio_bonus` 全套（純化為 log-ratio Gaussian × Super-Gaussian × 感知 gates）。optimizer 新增 `optimize_parallel()`（Channel B — 多 label 並列 Top）、每個結果帶 `recipe_id`（Phase 9 feedback 鉤子）；`diversify_top` 廢除。CLI `--label <name>` 單 label、無 flag = Channel B。

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
| TDS | 1.23%（稍粗）→ 原版 ~1.27% | `data/labels.json[balanced].tds_prefer = 1.27` |
| EY | 20–22% | `EY_PREFER["medium_light"] = 20.0` |
| 研磨 | 450–600µm EK43 → ZP6 dial ≈ 4.3 | `dial_prefer["medium_light"] = 4.3` |
| 水溫 | 97.8°C（208°F） | 錨點檢查固定 98°C |
| 浸泡 | 2:00 → swirl → press | 錨點 `fixed_steep=120s` |

**2026-05-21 TDS-anchor 校準：** `ey_model` 過去對 Hoffman 嚴重高估 TDS（predicted 1.39 vs measured 1.23），且誤差跟溫度走（April/Champion 80–85°C 幾乎準）。將三個有實測 TDS 的錨點設為 Layer 1 硬錨點後重校：`base_ey[medium_light]` 17.0→14.2（Hoffman ceiling-limited，定 EY 上限）、`K_LOW_TEMP_BOOST` 3.0→7.0（補償 April/Champion 低溫萃取，只對 <87°C 生效）、`EY_PREFER[medium_light]` 21.0→20.0（跟校準走）。三錨點 predicted TDS 現落在 measured ±0.05。`diagnose_anchor.py` / `test_compound_calibration.py` 的 TDS 檢查由「繞 predicted 自設 band」改為 assert `|predicted − measured| ≤ 0.05`。

**Phase 8 後：** 每個 label 自帶 `ideal` + `tds_prefer`（`data/labels.json`），不再有 per-roast `TDS_PREFER` 也不再有跨 TDS bracket 內插。改 label 屬性 = 改該 label 的口感目標，**零副作用其他 label**。

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

### 五條不可違反的架構原則

1. **禁止 min/max/if-else 硬斷點** — 物理世界是連續的。所有閾值、天花板、地板必須用平滑連續函數：
   - `max(x - threshold, 0)` → softplus 或 sigmoid gate
   - `min(x, cap)` → sigmoid saturation
   - `if x > threshold` → sigmoid transition
   - 例外：純離散邏輯（`inverted=True/False`）不在此限

2. **所有錨點在同一 label 內用同一個評分公式** — April 和 Championship 必須通過 `flavor_score()` 得到高分，不允許用獨立的 `_anchor_cosine_score()`。**Phase 8 後修訂**：每個 label 有自己的 IDEAL，但所有 label 共用同一個 `flavor_score()` 結構，只是 IDEAL 參數不同（見原則 #5）。禁止任何錨點走特例 scoring path。

3. **化合物模型必須自我鑑別** — 好喝的配方（Hoffman/April/Championship）的化合物 profile 進入評分公式後自然高分。難喝的配方（欠萃/過萃）的化合物 profile 自然低分。不需要靠 TDS floor 或 EY floor 來區分好壞 — 化合物信號本身就應該承載這個資訊。

4. **化合物層純連續物理；感官層允許閾值（嚴格二層分工）** — 物理化學是連續的，人類感知有閾值。兩者必須分層、不互相污染：
   - **化合物層 (`compounds.py`)**: **純連續物理動力學** — Arrhenius 速率 × 一階反應，從 t=0 連續到 t=∞、從 0K 到任何溫度全域可微。**禁止**：onset 時間（如 `CGA_TIME_ONSET=150`）、time floor（如 `SW_TIME_FLOOR=0.30`）、tent function（如 `1 - abs(temp - optimal)`）、softplus 溫度閾值（如 `softplus(temp - 92)`）— 即使數學上平滑，這些都是「閾值化偽裝」，不符合分子萃取物理。
   - **感官層 (`scoring.py`)**: **sigmoid / softplus / Gaussian 可用** — 人類感知本來就有閾值（Weber-Fechner law）。合法的閾值化感知層成員：`SW_AROMA_THRESH`、`SCORCH_PARAMS`、`TDS_FLOOR_MID`、`KH_FLOOR`。
   - **違反此原則的代價：** 化合物模型失去自我鑑別力（→ 違反原則 #3）→ 評分只能靠 process-variable 後置 gate 補救（如 `acid_trap = sigmoid(temp - 96) × sigmoid(120 - steep)`）→ 補丁是症狀治療，根因仍在 compounds.py 內部的非物理 gate。

5. **錨點分兩層：化合物校準錨點 vs 感官 label 島（嚴格角色分工）** — 每個「錨點」原本被綁定兩個彼此無關的角色，必須拆開。違反此原則導致新增錨點時必然動到另一個錨點的分數（Phase 4 加 Hedrick 時打亂 Hoffman/April 即此症狀）。

   > **⚠️ Phase 10 修訂中（2026-05-21）：`label` 概念已決定移除** —— Layer 2 從「感官 label 島」改成「per-roast 單一 IDEAL」（藍圖 [`docs/PHASE10_SENSORY_REFOUNDING.md`](docs/PHASE10_SENSORY_REFOUNDING.md) §0）。本原則的核心（Layer 1 物理校準錨點 vs Layer 2 感官目標,角色分離）**仍成立**；但下文「label 島」相關字眼待 Phase 10 landing 時連同原則 #3/#4 一併改寫。

   - **Layer 1：化合物校準錨點**（屬於物理層）
     - 用途：擬合 `compounds.py` / `ey_model.py` / `tds_model.py` 的 Ea、K、base profile 參數
     - 輸入：實測 brewing 配方（dial/steep/temp/dose/water）
     - 驗證：predicted TDS / EY / compound profile 接近 measured 值（容忍內）
     - **與「好不好喝」完全無關** — 它只回答「物理模型對不對」
     - 可以無限多（多了只是更多 fit 點，不會互相打架）
     - 包含 Under/Over-extract 邊界錨點（驗證低萃 / 過萃預測對）
     - 測試位置（規劃）：`tests/test_compound_calibration.py`

   - **Layer 2：感官 label 島**（屬於感官層）
     - 用途：定義「這個 label 喝起來該怎樣」
     - 每個 label 自帶 `IDEAL_FLAVOR[label]` + `TDS_PREFER[label]`
     - 評分：給定一個 compound profile，問「這個 profile 在 X label 下幾分」
     - 跨 label 比分數無意義（apples and oranges）
     - 可以無限多（balanced / acid-forward / sweet-body / coarse-modern / Nordic-floral / ...）
     - label 之間互不影響 — 新增 label 不會動到既有 label 的分數
     - **可以有「沒對應錨點的純假想 label」**（從文獻/SCA 風味輪推 IDEAL）
     - **可以有「沒對應 label 的純物理錨點」**（只進 Layer 1，不指派 sensory bullseye）
     - 測試位置（規劃）：`tests/test_label_scoring.py`

   - **典型映射（共用數字、不同角色）：**
     | 錨點 | Layer 1（物理目標）| Layer 2（感官 bullseye）|
     |------|-----------------|--------------------|
     | Hoffman | TDS 1.23% / EY 21% | `balanced` label IDEAL |
     | April | TDS 1.17% / EY ~18% | `acid-forward` label IDEAL |
     | Championship | TDS 1.56% / EY ~18% | `sweet-body` label IDEAL |
     | Hedrick | TDS 1.52% / EY ~19% | `coarse-modern` label IDEAL |
     | Under-extract | EY < 15% 邊界 | （無 — 應在所有 label 下打低分）|
     | Over-extract | EY > 22% / 高 CGA 邊界 | （無 — 應在所有 label 下打低分）|

   - **目前狀態（Phase 8 完成）：** Layer 1（`compounds.py` 純 Arrhenius × first-order）+ Layer 2（`data/labels.json` 4 個 label 島）都已落地。`tests/test_compound_calibration.py` 只看物理 band、`tests/test_label_scoring.py` 只看分數；`diagnose_anchor.py` 兩層分別顯示。`ratio_bonus` 全套（AC/CGA、SW/(MEL+CGA)、PS/CA）已刪除 — 每個 label 的 IDEAL 已內含 ratio 偏好。新增 label 是 `data/labels.json` 的 append-only 操作（Channel A discovery）；多 label cupping 比對用 `optimize_parallel()`（Channel B）。
   - **歷史症狀（Phase 8 前）：** `diagnose_anchor.py` 對每個錨點寫「物理檢查（AC>CGA）+ 分數檢查（>=60）」混合斷言；`ratio_bonus` 為了讓 April / Championship 在 Hoffman-IDEAL 下也高分而存在 — 都是「單層假裝多層」的代償補丁。Phase 8 拆掉之後通通消失。

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

### 四錨點各自「分數不低」的物理原因（Phase 8 後）

| 錨點 → label | 為何分數不低 | 關鍵信號 |
|------|------------|---------|
| Hoffman → balanced | predicted compound profile ≈ balanced IDEAL；TDS≈1.39 vs prefer 1.27（高側 sigma 0.65 寬腰） | compound_reward ≈ 1.0；tds_factor ≈ 0.99 |
| April → acid-forward | acid-forward IDEAL 本身就是 April predicted profile；TDS≈1.14 vs prefer 1.17 | compound_reward ≈ 1.0；tds_factor 接近 1.0 |
| Championship → sweet-body | sweet-body IDEAL = Champion predicted；TDS=1.55 vs prefer 1.56 | 同上 |
| Hedrick → coarse-modern | coarse-modern IDEAL = Hedrick predicted；TDS=1.44 vs prefer 1.40 | 同上 |

每個錨點都在**自己的 label**上拿高分，跨 label 比分數是 apples and oranges（cross_scores 在 `diagnose_anchor.py` 只是供參考）。Under/Over-extract 在**所有** label 上必須得低分（< 40 / < 50）。

---

**禁止為了讓某錨點通過而削弱某項懲罰** → 必須找出物理根本原因。對於某個 label 的口感矯正，優先動該 label 在 `data/labels.json` 的 `ideal` / `tds_prefer`（零副作用其他 label），最後才動 scoring/compounds 層的全域常數（會牽動所有 label）。
