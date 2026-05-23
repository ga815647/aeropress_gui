# Architecture

> 模組結構、資料流、Phase 10/11 管線。CLAUDE.md 只放紅線原則與錨點基準，
> 想看「程式怎麼跑」翻這裡。
>
> Phase 10 之前的六化合物架構（`compounds.py` / `scoring.py` / label 島 / 水質）
> 已退役 —— 那份舊架構文件凍結在 [`docs/ARCHITECTURE_legacy.md`](docs/ARCHITECTURE_legacy.md)，
> 只在 git branch `compound-model-legacy` 上成立。各 Phase 的「改了什麼、為什麼」
> 見 `docs/PHASE10_*.md`、[`docs/PHASE11_LOOP_ENGINE.md`](docs/PHASE11_LOOP_ENGINE.md)。

## 一句話

旋鈕 → 兩層模型算出風味 → 與該焙度的感官 IDEAL 比距離 → 排序。Phase 11 起，
IDEAL 不是手設的固定靶，而是**迴圈**一代代逼近出來的移動靶。

## Data Flow

```
使用者固定：roast、brewer(→water_ml)、temperature
使用者搜尋：dose × dial × steep

  optimizer.optimize(roast, brewer, temp, top_n)
    └─ 對網格上每個 (dial, steep, dose)：evaluate_recipe()
         ├─ models/layer1.py   brew()              旋鈕 → {tds, ey}
         ├─ models/sensory.py  predict_attributes() {tds,ey,roast,dial} → 10 感官屬性
         ├─ models/ideal.py    roast_ideal()        data/ideal.json → 該焙度 10 屬性 IDEAL
         └─ models/distance.py attribute_distance() 屬性 vs IDEAL → RMS 距離
    └─ 依 distance 升冪排序，回 Top-N

CLI：  main.py            → optimizer.optimize → output/{terminal,export,radar}
Web：  webapp.py          → /api/optimize（最佳化器模式）
                          → /api/loop/*（Phase 11 迴圈模式，見下）
                          → /api/feedback（§4 問卷）/ /api/recipes（命名配方）
```

管線只有一條：推薦配方與「重評一杯已記錄的配方」（feedback recompute）走的是
**同一個** `evaluate_recipe()` —— 一條 code path，已記錄的配方重評會與全新搜尋一致。

## 兩層模型

系統是「薄 Layer 1 → 中樞 TDS/EY → Layer 2 → 10 感官屬性」。中樞 TDS/EY 是
**內部潛變數**：使用者無折射儀、從不實測，它純粹是 Layer 1 的輸出、Layer 2 的輸入。
（幾何論證、為何是這個中樞，見 `docs/PHASE10_SENSORY_REFOUNDING.md` §3–§4。）

### Layer 1 — knob → TDS/EY（`models/layer1.py`）

平衡脫附式，單一一階逼近平衡天花板：

```
EY% = E_MAX · (1 − exp(−t_eff / τ)) · f_ratio
τ   = TAU_REF · exp(−ALPHA·(temp−T_REF)) · exp(−GAMMA·(DIAL_REF−dial))
f_ratio = water / (water + K_RATIO · dose)
TDS%    = 萃取固形物 / 出杯重 · 100
```

- 全 `exp()` 結構：全域單調、飽和、無閾值。
- 5 個參數，**全在 `layer1.py` 模組常數**（不在 `constants.py`）：`E_MAX_REF` 是唯一
  fit 的數（由 Hoffman 單一**素浸泡**錨點 98°C/4.3/120s/11g/200ml→TDS 1.23 解出），
  其餘 4 個（`TAU_REF`/`ALPHA`/`GAMMA`/`K_RATIO`）是物理先驗。
- **brewer-agnostic**：XL 與標準版只差 `water_ml`（與 dose 容量）—— 同沖煮比例下
  TDS/EY 相同。April/Champion 為技法沖煮、屬不同黑箱，故**不**當 Layer 1 錨點。
- per-roast `E_MAX_ROAST_FACTOR` / `RETENTION` 是文獻方向先驗，只 medium_light 錨定。

### Layer 2 — TDS/EY → 10 感官屬性（`models/sensory.py`）

`predict_attributes(tds, ey, roast, temp, dial)` → 10 個 cotter CATA 屬性各自的強度：

```
intensity = base + b_tds·z(TDS) + b_ey·z(EY) + b_tds2·z(TDS)²
```

- 10 個屬性：`Sour / Citrus / Tea.floral / Sweet / Cereal / Thick.viscous /
  Bitter / Astringent / Burnt / Dark.chocolate`（`ATTRIBUTES`）。
- 來源：UC Davis cotter 27-cell 因子網格，全 17 屬性各自對 (TDS,EY) 做 OLS、以
  R²≥0.44 閘門保留 10 個（砍掉的 7 個皆為保留屬性的弱雙胞或雜訊）。
- 跨屬性遮蔽（如厚 body 壓花香）**已內建於 cotter 資料**，直接回歸即捕捉，無需手建
  互動表。
- `b_temp` 固定 0（Batali 2020：固定 TDS/EY 下溫度無感官效應）。`roast` 經
  `_ROAST_OFFSET`（文獻方向先驗、未驗證）、`dial` 經 `_GRIND_SLOPE`（弱先驗）進入。
- `AXIS_VIEW` 把 10 屬性收成 7 群（酸/甜/body/苦/澀/焙烤/個性）—— 純**顯示 / §4 問卷
  視圖**，不是模型表徵。

### 距離 — 排序（`models/distance.py`）

```
distance = sqrt( mean over 10 屬性 of (predicted − ideal)² )
```

純未加權 RMS。**沒有 0–100 評分**（cotter hedonic 資料證實無「客觀最好」），
排序的數字就是顯示的數字。無 `tds_factor`、無 floor —— TDS 影響已完全經屬性表達，
欠/過萃靠屬性距離自我鑑別（CLAUDE.md 原則 #3）。10 個屬性過了 R² 閘門 → 等權重。

### per-roast IDEAL（`data/ideal.json` + `models/ideal.py`）

每個焙度一份 10 屬性 IDEAL（schema v6）。`roast_ideal(roast)` 是唯一讀路徑。
信心分層：`medium_light` = 使用者 ⭐5 杯（Tier A）；`light` = tim feedback（暫定，
tim 非 Layer 1 錨點）；`medium` / `moderately_dark` = 佔位（predict_attributes 在
medium_light 參考點 + roast offset 推得，待該焙度有 feedback 才真錨定）。

## Grid Search（`optimizer.py`）

`optimize(roast, brewer, temp, top_n)` 對 `dial × steep × dose` 三維網格窮舉：

- `dial`：3.0–7.5，步進 0.1（迴圈 `dial_x10` 30..75）。
- `steep`：30–420s，步進 `STEEP_STEP=30`。
- `dose`：brewer 容量 ∩ 該焙度 `dose_per_100ml`；XL 步進 1.0g、標準 0.5g。
- `temp`：**輸入、不搜尋** —— 它只經 Layer 1 的 EY/TDS 影響風味（Layer 2 `b_temp=0`），
  任一 (tds,ey,dial) 目標下不同溫度被不同 steep 吸收，搜它只得 tie-break 雜訊
  （`docs/PHASE10_STEP4_LAYER1.md` §8）。省略 → `constants.DEFAULT_TEMP[roast]`。

每個候選經 `evaluate_recipe()` 算出 attributes/distance，依 distance 升冪取 Top-N。
每個結果帶 `recipe_id`（`models/ideal.py:recipe_id()`，sha1 前 12 碼，feedback 反查鍵）。

## Phase 11 迴圈引擎（`models/loop.py`）

把一次性 Top-N 最佳化器升級成**配方產生機** —— per-roast (1+λ) 演化搜尋。
完整設計見 [`docs/PHASE11_LOOP_ENGINE.md`](docs/PHASE11_LOOP_ENGINE.md)。

```
冠軍（第 0 代 = optimizer Top-1 model-seed）
  └─ 三杯循環 [exp1, champion, exp2]   ← 冠軍夾在中間：兩個實驗都 cup-adjacent
       exp1, exp2 = 冠軍的單旋鈕擾動（半徑照排程早大後細，溫度不搜）
       champion   = 進來時的冠軍，在中間重泡（兩個實驗的味覺記憶錨點）
  └─ 三杯各走 §4 問卷 → 三杯到齊 → digest
       cup 2 的 overall → exp1 vs champion（invert）；cup 3 的 overall → exp2 vs champion
       明確 > 才換、平手守成；勝者 = 下一循環的冠軍；generation++
```

- 狀態存 `data/loop_state.json`（per-roast，lazy 產生）。
- `skip_proposal` = 後勤性重抽（同探索半徑，沒豆/沒時間），**非**味覺回饋。
- `detect_flags()` 掃 `feedback.jsonl` 找 `model_attributes_vs`↔`attributes_vs`
  重複反向矛盾（≥2 次、`?` 排除）→ 記 flag、邀請開對話，**永不自動改模型**。
- 第 3 杯固定為進來時的冠軍重泡（正統 (1+λ)：親代世代內固定）。

## Feedback 與命名配方

- `models/feedback.py` + `data/feedback.jsonl` —— §4 pairwise + ordinal 問卷
  （`compared_to` / `overall` `>/=/<` / `attributes_vs` `>/?/<` / `model_attributes_vs`
  / `absolute`）。schema 規格見 [`docs/FEEDBACK_FORMAT.md`](docs/FEEDBACK_FORMAT.md)。
  append-only；`recompute_entry()` 用當前模型重算 stale 的 tds/ey/distance。
- `models/saved.py` + `data/saved_recipes.json` —— 使用者手動命名儲存的配方庫。
- `data/refine_changelog.md` —— Claude tier-3 模型改動紀錄檔（§6 紀律 3）。

## Key Files

| File | Role |
|------|------|
| `constants.py` | `ROAST_TABLE` / `BREWER_PRESETS` / `DEFAULT_TEMP` / `DIAL_STEP` / `STEEP_STEP`。註：仍殘留化合物時代的未用常數（vestigial） |
| `models/layer1.py` | Layer 1 旋鈕→TDS/EY（平衡脫附式；5 參數為模組常數）|
| `models/sensory.py` | Layer 2 TDS/EY→10 屬性（`ATTRIBUTES` / `AXIS_VIEW` / `_COEF`）|
| `models/distance.py` | `attribute_distance()` —— 10 屬性 RMS 距離 |
| `models/ideal.py` | `roast_ideal()` per-roast IDEAL 載入 + `recipe_id()` |
| `data/ideal.json` | per-roast 10 屬性感官 IDEAL（schema v6）|
| `optimizer.py` | 網格搜尋 `optimize()` + `evaluate_recipe()` + `score_logged_recipe()` |
| `models/loop.py` | Phase 11 迴圈引擎（三杯循環、digest、skip、flag）|
| `models/saved.py` | 命名配方庫 |
| `models/feedback.py` | `feedback.jsonl` 讀寫（§4 schema）|
| `data/{loop_state,saved_recipes}.json`、`data/feedback.jsonl` | runtime 狀態（lazy）|
| `data/refine_changelog.md` | Claude 模型改動紀錄 |
| `diagnose_anchor.py` | Phase 10 兩層診斷（Layer 1 物理 + Layer 2 感官，13 檢查，以 exit code 回報）|
| `webapp.py` + `templates/` + `static/` | Flask UI（最佳化器 / 迴圈雙模式）|
| `main.py` | CLI（`--roast` 必填、`--brewer`/`--temp`/`--top`/`--output`/`--radar`）|
| `tests/` | `test_layer1` / `test_sensory_distance` / `test_optimizer` / `test_feedback` / `test_loop` / `test_output_and_cli` / `test_webapp`（75 PASS）|

## Grinder Dial Reference

模型的 `dial` 軸校準在 **1Zpresso ZP6**（使用者主力）。其他磨豆機透過下方的 µm
橋接，共同錨點是 **Hoffman 點**（ZP6 dial 4.3 ≈ 627µm）。

### 1Zpresso ZP6 — 模型原生軸

- 範圍 240–1050µm，9 numbered turns × 10 sub-clicks = 90 clicks。
  **每 click ≈ 9µm、每 numbered step ≈ 90µm。**
- 模型 `dial` 搜尋範圍 3.0–7.5，步進 0.1。**低 = 細、高 = 粗。**
- `models/layer1.py:DIAL_REF = 4.3`（Hoffman 錨點研磨，τ grind 項在此 = 1）。
- `models/sensory.py:_DIAL_REF = 4.3`（grind 先驗的參考點）。
- AeroPress 推薦範圍（原廠）：0.7 – 6.2。
- **無 brewer dial offset** —— Phase 10 Step 5 移除 `BREWER_TAU_MULT` 後，XL 與標準版
  不再有研磨偏移；Layer 1 brewer-agnostic（舊 `dial_offset = 0.10` 已不存在）。

來源：[1Zpresso ZP6 grind settings · Honest Coffee Guide](https://honestcoffeeguide.com/1zpresso-zp6-grind-settings/)、原廠手冊。

### Baratza Forte BG — 副磨豆機（Brewed Group 刀盤）

> **注意：**這是 **Baratza** 的產品，**不是 Mahlkönig**（常見混淆 —— Mahlkönig 有
> EK43 / Forte EK，但 Forte BG 是 Baratza 的）。Forte BG = "Brewed Group" 刀盤裝在
> Baratza Forte 機身，54mm flat steel burrs。

- 範圍 230–1150µm，260 個位置：**10 macro × 26 micro**。
- dial 寫法 `<macro><micro>` 例如 `3F`、`5I`、`8R`。
- **每 micro 步（A→B→…→Z）≈ 3.54µm；每 macro 步 ≈ 92µm。**
- 方向：**低 macro / 低 micro = 細**（跟 ZP6 同方向、數字越小越細）。物理「lever UP」
  = 降數字 = 變細。
- AeroPress 推薦範圍（原廠）：**2A – 8X**（寬，因為 AeroPress 風格多元 — Hoffman 細，
  April / Champion 粗）。

來源：[Baratza Forté BG grind settings · Honest Coffee Guide](https://honestcoffeeguide.com/baratza-forte-bg-grind-settings/)、[Baratza Forte AP/BG 原廠手冊 PDF](https://baratza.com/wp-content/uploads/2015/07/Forte-BG-AP-Manual-EN-v2.3-SmallSize.pdf)。

### 對應表（µm 線性中位數估算）

| ZP6 dial | ≈ µm | Forte BG | 用途 / 對應狀態 |
|---|---|---|---|
| 4.0 | 600 | **5A** | 比 Hoffman 略細 |
| **4.3** | **627** | **5I** | **Hoffman Layer 1 錨點 · medium_light IDEAL 來源** |
| 4.5 | 645 | 5N | 模型 `DIAL_REF` |
| 5.0 | 690 | 6A | 略粗 |
| 6.0 | 778 | 6Z | 粗磨象限（舊 coarse-modern 區） |
| 6.75 | 848 | 7S | 真粗（舊 April / Champion 區） |

**用法：** webapp 顯示 `dial 4.3` → Forte BG 轉到 `5I`；顯示 `dial 4.5` → `5N`；
依此類推。表的對應 = 兩台磨豆機 µm 範圍的線性中位數估算。

### 注：median 中位數 ≠ extraction-match —— 萃取對齊靠表面積

萃取速率其實取決於**總表面積**（Sauter mean D[3,2]），不只中位數 D[50]。同 D[50] 下：

- **ZP6（conical 手磨）**：fines（< 100µm）尾巴較多 → 同 D[50] 下表面積較大 → 萃取較快。
- **Forte BG（54mm flat）**：分布較單峰、fines 少 → 同 D[50] 下表面積較小 → 萃取較慢。

**結果：** 用 median-match 的 dial 設 Forte BG，泡出來的杯子會**比 ZP6 上的略淡**
（相同時間下萃出來的固形物較少）。要對「**喝起來像 ZP6**」的話，Forte BG 該比表上對應
**再細**一點補表面積。

**修正幅度：** Forte BG D[50] ≈ ZP6 D[50] × **0.85–0.95**（套用 conical vs flat 的
典型 D[3,2]/D[50] 比例 ~0.78–0.88 vs ~0.88–0.92）。中央估計 ratio ≈ 0.9 → 約 50–90µm
細、0.5–1 macro 步。

| ZP6 dial | median-match | extraction-match 範圍 | 中央估計（~0.9）|
|---|---|---|---|
| **4.3（Hoffman）**| **`5I`** | **`4I` – `5A`** | **~`4Q`** |
| 4.5 | `5N` | `4M` – `5E` | ~`4V` |
| 5.0 | `6A` | `4X` – `5Q` | ~`5G` |
| 6.0 | `6Z` | `5S` – `6O` | ~`6D` |

**沒精校** —— 沒有兩台磨豆機在你手上實測的粒徑分布、修正係數靠典型 conical vs flat
數據估。範圍給足容錯。**因為 Forte BG 不餵迴圈、就是換場所喝，差異靠舌頭微調幾個
micro 步即可**（每 micro 步 ≈ 3.5µm）。實務動作：**從中央估計起跑**，杯子太淡就再細
1–2 micro 步、太濃就反向。

> 簡化前提：surface-area 假設萃取由「初始 surface contact」主導，這對 AeroPress 的
> 短浸泡（~120s）成立；長浸泡（5+ 分鐘）下分布形狀效應更複雜，本估算會略偏。

### 使用情境 — Forte BG 是「換個地方泡同一個冠軍」，不參與迴圈

**迴圈在 ZP6 上跑**（那是模型校準的軸）。Forte BG **不另外跑迴圈、不餵 feedback** —— 它
存在的理由是：使用者在副場所想喝目前冠軍時，能查表把 `dial` 翻譯成 Forte BG 的
macro/micro，泡來喝就好。

- **不要為 Forte BG 上的 casual 杯送 §4 問卷的 `overall`**。送了就會把兩台磨豆機的
  粒徑分布差異混進同一個迴圈的搜尋訊號裡（磨豆機 bias 偽裝成風味漂移、把冠軍往
  錯誤方向推）。Casual 喝就 casual 喝。
- 若你純粹想記錄一筆「Forte BG 上的冠軍泡」當日記，可以在 webapp 提交 `comment` +
  `stars`，但**留空 `overall` 與 `attributes_vs`** —— 那是給味覺比較用的、Forte BG
  vs ZP6 不該進那條訊號。

### 注意事項（粒徑層面）

- **線性內插忽略分布形狀差異** —— ZP6 是 conical 手磨、Forte BG 是 54mm flat。中位數
  可能對得上，但**分布寬窄不同**（Forte BG 一般 spread 較窄、fines 較少）。同 dial
  µm 對應下，Forte BG 上的杯子味道仍可能略不同（正常範圍）。
- **µm 漂移源** —— 刀盤磨損、豆種、烘焙度、磨機溫度。表上對應是 ±30µm 級的估算，
  不是精校。若你發現某焙度系統性偏掉，自己微調 1–2 個 micro 步即可（這純粹是 Forte BG
  端的個人小校準，不動模型）。
- **BG vs AP 刀盤** —— 本對應假設 **BG**（brewed group，較適合 filter）。若你裝的是
  **AP**（all-purpose），分布特性略不同，但表仍可當起點。

## 調整方向參考

Phase 10/11 的「口感矯正」不再是調 scoring 常數 —— 改目標、或讓迴圈收斂：

| 想做的事 | 動哪裡 | 注意 |
|---------|--------|------|
| 收斂到「我的」偏好 | 用 **webapp 迴圈模式**，泡三杯循環、填 §4 問卷 | 別手動調 —— 迴圈就是為此而生 |
| 改某焙度的風味目標 | `data/ideal.json[<roast>].ideal` 的 10 屬性值 | 零副作用其他焙度 |
| 模型方向預測錯了（flag 重複出現）| `models/sensory.py` `_COEF` 該屬性係數 | 記一行 `data/refine_changelog.md`、可回退 |
| Layer 1 TDS/EY 整體偏掉 | `models/layer1.py` 的 5 個參數 | `E_MAX_REF` 動絕對尺度（多會抵銷）；`ALPHA/GAMMA/K_RATIO` 動相對響應 |
| 加新焙度 | `data/ideal.json` append + `constants.ROAST_TABLE` / `DEFAULT_TEMP` | 跟著補 `_ROAST_OFFSET` |
| 收藏一組好配方 | webapp 結果卡 / 冠軍卡的「★ 命名儲存」 | 進 `data/saved_recipes.json` |

改完模型相關檔（`layer1` / `sensory` / `distance` / `ideal.py` / `data/ideal.json`）
**必須**跑 `python diagnose_anchor.py`（exit 0 = 全 PASS）與 `python -m pytest tests/`。
