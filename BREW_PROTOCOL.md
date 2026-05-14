# 泡法時間軸與參數定義

> 這份文件是 `compounds.py` / `optimizer.py` / `diagnose_anchor.py` / `terminal.py`
> 之間所有時間參數的單一真相來源。Session 間如果搞不清楚「哪個參數對應哪個動作」，
> 先看這裡再讀程式碼。

## 1. 時間參數總表

所有時間單位為秒。「起算點」欄位指的是 **wall-clock t=0 = 開始注水**。

| 參數 | 來源 | 起算點 | 終點 | 用途 |
|------|------|-------|------|------|
| `steep_sec` | **使用者輸入 / optimizer 搜尋變數** | 開始注水 | swirl 啟動瞬間 | 主時間變數；CLI 顯示為「被動浸泡 M:SS」 |
| `pour_time` | 計算 `water_ml / POUR_RATE` | 開始注水 | 注水完成 | std=16.67s / XL=33.33s |
| `pour_offset` | 計算 `pour_time / 2` | — | — | 「平均水接觸時間」對 `steep_sec` 的修正；compounds.py 用 `softplus(steep_sec − pour_offset)` |
| `seal_delay` | 常數 `SEAL_DELAY_DEFAULT=5.0` | 注水完成 | 活塞密封 | 預密封漏水視窗的時長之一 |
| `drip_time` | 計算 `pour_time + seal_delay` | 開始注水 | 活塞密封 | `calc_drip_volume()` 輸入 |
| `partial_seal_sec` | 食譜參數（April 用） | 開始注水 | 半密封結束 | 活塞先插 1cm 形成受控滲流 |
| `pre_pour_sec` | 食譜參數（April 用） | 開始注水 | 預先注水結束 | bloom 階段時長 |
| `swirl_time_sec` | 常數 `SWIRL_TIME_SEC=5` | swirl 啟動 | swirl 結束 | 旋轉持續時長 |
| `swirl_wait_sec` | 常數（std 30 / XL 40） | swirl 結束 | 開始下壓 | 等粉渣沉底 |
| `press_sec` | 常數（std 30 / XL 40，固定） | 開始下壓 | 壓到底 | 由 `calc_press_time()` 回傳 |
| `press_equiv` | 計算 `collapsed_press × 0.15` | — | — | 下壓階段算入有效萃取時間的部分；當 press_sec ≤ 60 時 `collapsed_press = press_sec`，超過 60 觸發 channeling collapse 才會壓縮 |
| `extra_swirl_time` | 計算 `SWIRL_TIME_SEC × max(n_swirls−1, 0)` | — | — | **只用於 compounds.py 的 `effective_steep`**；calc_ey 走另一條 swirl scaling（見下方 ⚠️）|
| `effective_steep` | 計算（**送進 compounds.py 一階反應**）| — | — | `softplus(steep_sec − pour_offset, k=5) + press_equiv + extra_swirl_time` |
| `t_kinetic` (calc_ey 內部) | 計算（**進評分**：送進 `_calc_phase_ey()` 算 EY） | — | — | `max(0, steep_sec − pour_offset) + SWIRL × swirl_mult × max(n_swirls, 1) + swirl_wait × 0.3 + press_equiv`；`swirl_mult = 1 + SWIRL_CONVECTION_BASE × (SWIRL_DOSE_REF / dose)` |
| `t_kinetic` (optimizer 顯示) | 計算（**只顯示**，不進評分） | — | — | 公式跟 calc_ey 內部相似但**沒乘 n_swirls**，所以 multi-swirl 時兩處會發散；CLI 顯示為「動力學等效 M:SS」|
| `total_contact_sec` | 計算（**顯示用**） | 開始注水 | 壓到底 | `steep_sec + SWIRL_TIME_SEC + swirl_wait_sec + press_sec`（wall-clock）|

> ⚠️ **三個獨立的「動力學時間」一定要分清楚，公式都不一樣**：
>
> | 變數 | 位置 | Hoffman n=1 | 倒推 n=2 | 是否進評分 |
> |------|------|------------|----------|-----------|
> | `effective_steep` | compounds.py | 116.17s | 121.17s | ✓ 進評分（化合物一階反應）|
> | `t_kinetic` | ey_model.py `calc_ey` 內部 | 138.35s | 151.53s | ✓ 進評分（EY 計算）|
> | `t_kinetic` | optimizer.py 顯示用 | 138.35s | 138.35s | ✗ 純 CLI 顯示 |
>
> n=1 時 calc_ey 跟 optimizer 顯示版本巧合相等；n≥2 時 calc_ey 把 swirl 乘 n，optimizer 顯示版本不乘 → **兩者會發散**。`effective_steep` 用 softplus 不是 max，且不含 swirl_wait 項，所以永遠跟另兩個不同。

---

## 2. 通用泡法時間軸（Hoffman 風，正置非倒置）

```
t=0:00                                                          steep_sec        +5s       +swirl_wait    +press_sec
  │──── pour (pour_time) ────┼── seal_delay ──┼─── passive steep ───┼── swirl ──┼── settle ──┼─── press ───┤
  │                          │                │                     │           │            │             │
  │  注水（16.67s for std）  │  5s 延遲     │  剩餘浸泡時間        │  旋轉      │  等沉粉    │  下壓       │
  ▼                          ▼                                                                              ▼
  開始計時                   活塞插入密封                                                                   end of contact

  ↑─────────────────────────── steep_sec (e.g., 120s) ─────────────────────────↑
  ↑─────────────────────────────────────────── total_contact_sec ───────────────────────────────────────────↑
                              ↑─────── drip_time (= pour_time + seal_delay) ──────↑（用於 pre-seal drip 計算）
```

### 關鍵點
- `steep_sec` **包含**注水時間（從 t=0 開始算）
- compounds.py 內部用 `softplus(steep_sec − pour_offset)`，物理意義是「全水接觸後的等效時間」
- 預密封漏水（drip volume）發生在 `t=0 → drip_time` 區間，影響杯中化合物（drip_profile 與 main_profile 混合）

---

## 3. 三錨點時間圖

### Hoffman 平衡（standard / 11g / 200ml / 98°C / steep=120）

```
t=0:00 ──── pour 17s ──── t=0:17 ── seal 5s ── t=0:22 ── steep 98s ── t=2:00 ── swirl 5s ── t=2:05 ── wait 30s ── t=2:35 ── press 30s ── t=3:05
```

- `steep_sec = 120`, `swirl_wait = 30`, `press_sec = 30`
- `total_contact_sec = 120 + 5 + 30 + 30 = 185s`
- `pour_offset = 200/12/2 = 8.33s`
- `effective_steep ≈ softplus(120 − 8.33) + 30×0.15 + 0 = 111.67 + 4.5 ≈ 116.2s`
- `drip_time = 16.67 + 5 = 21.67s`，產生少量 pre-seal drip（dial 4.3、22g、std）

### April 酸質（standard / 13g / 200ml / 85°C / steep=90 / partial-seal 25s）

**物理協議（人類執行的步驟）：**
```
t=0:00 ──── pre-pour 30s（50ml）──── t=0:30 ── partial seal 25s（活塞 1cm）── t=0:55 ── 完全密封 + 浸泡 ── t=1:30 ── swirl ── press
```

- 食譜參數：`steep_sec=90`, `pre_pour_ml=50`, `pre_pour_sec=30`, `partial_seal_sec=25`, `partial_seal_water_ml=50`

⚠️ **Code 不依時序模擬上圖**，而是把兩個機制當「**疊加修正項**」處理：

1. **`pre_pour_sec` → free-water 權重混合**（ey_model.py:115-119）：
   ```
   w1 = min(pre_pour_sec / steep_sec, 1.0)  = min(30/90, 1) = 0.333
   effective_free_water = free_water_p1 × 0.333 + main_free_water × 0.667
   ```
   不是「先 30s 用 50ml」再「之後用 200ml」的兩階段，而是線性插值兩個情境的「自由水量」做為 EY 計算的單一輸入。

2. **`partial_seal_sec` → drip_volume 額外項**（tds_model.py:31-40）：
   ```
   ps_drip = PRE_SEAL_DRIP_RATE_REF × PARTIAL_SEAL_FLOW_FACTOR × partial_seal_sec × ...
   raw_volume += ps_drip
   ```
   不是真的模擬「半密封 25s 期間滴漏」的時間動力學，而是直接加一個體積到 pre-seal drip 總量。

- `steep_sec = 90` 仍是「注水→swirl 前的時長」概念（含 bloom + 半密封段），但 code 並沒有把這 90s 拆成多段處理
- `predict_compounds()` 在非倒置時跑兩次 `_predict_closed_compounds`：主流程（effective_steep）+ drip 流程（drip_contact ≈ drip_time × 0.2），按 drip_ratio 加權混合

### Championship 甜醇（standard / 17g / 200ml / 80°C / steep=100 / 倒置 / press=20s / n_swirls=2）

```
t=0:00（倒置）──── pour 17s ──── t=0:17 ── 浸泡 83s ── t=1:40 ── swirl ×2（10s）── t=1:50 ── settle 30s ── t=2:20 ── 翻正+press 20s ── t=2:40
```

- `inverted = True` → **沒有 pre-seal drip**：calc_ey 跳過 drip_ey 加總（ey_model.py:132-134）；compounds.py 強制 `drip_ratio = 0` 跳過 drip_profile 混合（compounds.py 內 `if inverted: drip_ratio = 0.0`）。除了「無漏水」之外的倒置物理差異（腔內氣壓、翻正抖動、密封性）目前**沒有**建模。
- `press_sec = 20`（**anchor 測試 hardcode**，覆蓋 `calc_press_time()` 對 standard brewer 的預設值 30s）；對應 `press_equiv = 20 × 0.15 = 3.0`
- `n_swirls = 2`：
  - compounds.py 加 `extra_swirl_time = 5 × (2−1) = 5s` 進 `effective_steep`
  - calc_ey 把 `SWIRL × swirl_mult × max(2, 1) = 5 × 2.06 × 2 ≈ 20.6s` 進 `t_kinetic`（**不只多 5 秒，是雙倍乘 swirl_mult**）
- 倒置→翻正的時間被併入「等沉粉」階段（code 上沒區分）

---

## 4. 常見陷阱

1. **`steep_sec` ≠ 「被動浸泡時間」字面意思**
   它包含整個 pour 過程（從 t=0 算起）。CLI 顯示「被動浸泡 2:00」=「注水→swirl 共 2:00」，不是「水到位後再泡 2:00」。

2. **`effective_steep` 跟 `t_kinetic` 是三件事，不是兩件**
   - `effective_steep` (compounds.py) = 化合物一階反應的 t（含 `press_equiv`、softplus 平滑、含 `(n−1)` swirl 累加）→ **進評分**
   - `t_kinetic` (calc_ey **內部**) = EY 計算用的 t（含 swirl_wait × 0.3、n_swirls × swirl_mult、press_equiv）→ **進評分**
   - `t_kinetic` (optimizer **顯示用**) = CLI「動力學等效」欄位（公式與 calc_ey 內部接近但**不乘 n_swirls**）→ 不進評分
   - 改 `SWIRL_CONVECTION_BASE` 會同時動 calc_ey 的 EY 跟顯示的 t_kinetic，但**不會動** compounds.py 的 effective_steep
   - 改 `SWIRL_WAIT_EXT_MULT` 只會動 calc_ey 內外兩個 t_kinetic，**不動** effective_steep
   - 改 `PRESS_EQUIV_FRACTION` 會動所有三個（press_equiv 加到全部）

3. **`total_contact_sec` 不進評分**
   只是顯示。評分用的是 `effective_steep`（化合物動力學）+ `steep_sec`（scoring.py 部分檢查）+ TDS/EY。

4. **`press_sec` 改了 `press_equiv` 跟著改，但化合物分層機制也跟著動**
   `predict_compounds()` 還有獨立的 `press_perc` 段（CGA/MEL/CA/SW 的下壓選擇性 +/−），跟 `press_equiv` 是兩條獨立通道：
   - `press_equiv` → 進 `effective_steep` 影響所有化合物動力學
   - `press_perc` → 額外的 CGA/MEL +X% / SW −X% 滲流偏好
   改 `PRESS_PERC_*` 不會影響 `effective_steep`，改 `PRESS_EQUIV_FRACTION` 不會影響 `press_perc`。

5. **倒置 (`inverted=True`) 實際作用：兩處跳過 drip 模型**
   - ey_model.py:103-104 `drip_volume = 0.0` → main_free_water 不被預密封漏水扣減
   - ey_model.py:132-134 跳過 `drip_ey + main_ey` 加總，只回傳 `main_ey`
   - compounds.py:155-156 `drip_ratio = 0.0` → 跳過 drip_profile 與 main_profile 的混合
   - **不會改** `effective_steep`、不會改溫度衰減、不會改 channeling、不會改腔內氣壓。倒置帶來的非漏水物理差異目前**沒**建模。

6. **`partial_seal` 跟 `inverted` 互斥但 code 不檢查**
   April 用 partial_seal 是因為正置；Champion 用 inverted。如果同時傳 `partial_seal_sec > 0 + inverted=True`，inverted 會吃掉 drip_ratio（=0），partial_seal 的滲流計算實際上不發生 — 但 `effective_steep` 計算不受影響。錨點驗證請維持 partial_seal XOR inverted。

7. **錨點固定參數 vs optimizer 自由搜尋的時間範圍不一樣**
   - `diagnose_anchor.py` 各錨點 `fixed_steep` 寫死（120 / 90 / 100 等）
   - `optimizer.py` 自由搜尋 `steep ∈ [30, 420]` 每 30s 一步
   - 改 `STEEP_STEP` 或上下界只影響 optimizer，**不影響錨點驗證**

---

## 5. 程式碼對應 cheatsheet

| 想做什麼 | 改哪 |
|---------|------|
| 改 Hoffman 錨點的浸泡時長 | `diagnose_anchor.py::ANCHOR["fixed_steep"]` |
| 改 April 預密封段時長 | `diagnose_anchor.py::run_april_anchor` 內 `partial_seal_sec=` |
| 改 optimizer 搜尋的 steep 範圍 | `optimizer.py` 內 `range(30, 421, STEEP_STEP)` |
| 改 std/XL 預設下壓時間 | `BREWER_PRESETS[*]["fixed_press_sec"]` |
| 改下壓時間佔有效萃取的比例 | `PRESS_EQUIV_FRACTION`（影響 `effective_steep`）|
| 改下壓的化合物選擇性（CGA/MEL/CA/SW） | `PRESS_PERC_*_DIFF` / `PRESS_PERC_REF_SEC`（**獨立通道**，不影響 `effective_steep`）|
| 改 swirl 後等沉粉時長 | `BREWER_PRESETS[*]["swirl_wait_sec"]` |
| 改 swirl convection 對 EY/t_kinetic 的加成 | `SWIRL_CONVECTION_BASE` / `SWIRL_DOSE_REF`（**影響 EY 評分** + CLI 顯示，不影響 compounds.py 的 effective_steep）|
| 改 swirl_wait 對 EY 的加權 | `SWIRL_WAIT_EXT_MULT`（**影響 EY 評分** + CLI 顯示）|
| 改注水流速 | `POUR_RATE`（影響 `pour_time` → `pour_offset` → `drip_time`） |
| 改密封延遲 | `SEAL_DELAY_DEFAULT`（影響 drip_time） |
