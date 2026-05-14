# 待辦任務路線圖

## UI — Chip 標籤重寫（⚠️ 等 Phase 1-3 完成後才能做）

**目標：** Dose chip 的 7 段風味描述以 TDS 偏差為主軸，貼合人類感官現實。

**為什麼現在不能做：**
- Chip flavor 描述依賴 SW_abs / PS_abs（= compound fraction × TDS）
- 但化合物模型有系統性誤差（欠萃 SW 比正萃還高），Phase 1 尚未修正
- 基於錯誤的化合物預測設計標籤 = 建在沙上
- 必須等 Phase 1-3 完成，用校準後的模型重新推導各豆量段的真實風味走向
- Chip **機制**（限制豆量搜尋範圍）保留；flavor **文字描述**暫時移除或用中性標示

**背景資料（供日後設計參考）：**
- Optimizer 已嘗試補償低豆量的 TDS 不足（最細研磨 + 120s），但 20g/400ml 物理上限 TDS≈1.174，無法到達 TDS_PREFER=1.27
- Light+XL 的 TDS 最接近理想值在 25-26g（偏差 −0.2%）
- Medium/Moderately_dark 在 XL 全段 TDS 偏差 −10% 至 −16%，全段過淡
- 低 TDS + 高 EY = SCA under-concentrated 象限：酸感集中、澀鹹、無香（使用者實測確認）

**等 Phase 1-3 完成後要做的事：**
- [ ] 7 段標籤以新模型的 TDS 偏差 + 化合物絕對值重新設計
- [ ] 過淡區（偏差 > −5%）需標示酸澀風險，不能用正面詞彙
- [ ] Medium/dark 在 XL 上全段過淡，需誠實標示
- [ ] 標籤需按焙度組分組（淺焙 vs 中深焙行為不同）
- [ ] `getDoseFlavorHint()` 邏輯同步更新

---

## Phase 1 — 化合物模型修正（`compounds.py` + `constants.py`）

**目標：** 讓欠萃配方的化合物 profile 與正萃明顯不同，消除模型鑑別力不足問題。

**已知問題（已解決）：**
- ~~Under-extract (93C/6.5/60s) 的 SW fraction 比 Hoffman (98C/4.6/120s) 還高（欠萃比正萃還甜？）~~
- ~~根本原因：`COMPOUND_BASE` 基底佔比過大，時間/溫度修正幅度太小~~
- ~~壞配方和好配方的化合物 profile 幾乎相同，鑑別完全靠 TDS floor~~

**實作內容（2026-04-09）：**
- `constants.py`：新增 `SW_DIAL_COEFF = 0.10`（每 dial 單位 10% 對數線性修正）
- `compounds.py`：`_predict_closed_compounds()` 中 SW 計算末尾加入 `sw *= exp(SW_DIAL_COEFF * (DIAL_BASE - dial))`
- 物理意義：細研磨 → 更多接觸面積 → 更多香氣揮發物萃取。不用 EY 門控（因果倒置，見 constants.py 設計說明）
- 效果：Under SW_frac 0.376 → 0.335，Hoffman SW_frac 0.339；Under < Hoffman ✓

**完成狀態：**
- [x] 研磨粗細（粗研磨）顯著壓低 SW（`SW_DIAL_COEFF`）— EY-gate 改用研磨直接修正避免因果倒置
- [x] 確保 under-extract SW fraction < Hoffman SW fraction（0.335 < 0.339）
- [x] CGA/MEL 在過萃時明顯超標，欠萃時明顯偏低（Over CGA_frac 0.082 > Hoffman 0.067 > Under 0.052）
- [x] `python diagnose_anchor.py` 全部 `[ OK ]`（Hoffman/April/Championship/Under/Over 全 PASS）
- [ ] **待續（Phase 1.5 可選）：** SW_TIME_FLOOR 目前仍 0.50，短浸泡鑑別力尚有改善空間（但改動有破壞 Championship 風險，留 Phase 3 校準時評估）

---

## Phase 2 — 評分邊際曲線（`scoring.py`）

**目標：** 好配方得高分，壞配方被懲罰，鑑別度提升。

**完成狀態（2026-04-12）：**
- [x] 化合物好處邊際遞減（接近理想高報酬，超過後趨平）— 由非對稱 sigma (sigma_hi >> sigma_lo) 實現；正向化合物超標側懲罰緩慢
- [x] 化合物壞處邊際遞增（偏離越多，懲罰加速）— 新增 `ACCEL_W_PER_COMPOUND`：CGA/MEL 超標後 softplus 加速懲罰
- [x] 加入比值評分：AC/CGA（純淨酸質）、SW/(MEL+CGA)（甜苦比）、PS/CA（醇厚乾淨度）
- [x] 各比值使用獨立 sigmoid 加分曲線，加權平均後降低 compound_loss
- [x] 所有函數平滑連續（sigmoid 方向門控 + softplus 強度閾值，無 if/else）

**分數影響：**
- Hoffman: 85.1 → 84.9（-0.2，無感）
- April: 76.6 → 76.2（-0.4，仍遠超閾值）
- Championship: 57.0 → 56.4（-0.6，仍高於 55 閾值）
- Over-extract: 26.0 → 24.0（-2.0，鑑別度提升）

---

## Phase 3 — 重新校準錨點（`diagnose_anchor.py` + `constants.py`）

**目標：** Phase 1+2 完成後，確認五錨點全部通過，物理合理性對齊。

**完成狀態（2026-04-12）：**
- [x] 五錨點全部重跑：Hoffman / April / Championship / Under-extract / Over-extract
- [x] 確認化合物物理合理性：
  - Under SW < Hoffman SW ✓（Phase 1 已修正）
  - Over CGA > Hoffman CGA ✓（ratio 1.194 > threshold 1.15）
  - Championship SW > CGA/MEL ✓（甜感配方）
  - April AC > CGA/MEL ✓（酸質配方）
- [x] 調整 `IDEAL_FLAVOR`：IDEAL_CGA 0.05→0.057（對齊模型實測 Hoffman CGA_frac≈0.064）；AC 同步下調 0.007 維持 sum=1.0
- [x] 調整閾值：`CGA_ASTRINGENCY_THRESHOLD` 1.25→1.15（對齊新 IDEAL_CGA 比值基準）
- [x] `diagnose_anchor.py` 全部 `[ OK ]` ✓

**校準後分數（Phase 3 最終狀態，2026-04-12）：**
| 錨點 | 分數 | 閾值 |
|------|------|------|
| Hoffman | 95.6 | > over-extract |
| April | 90.1 | ≥ 60 |
| Championship | 70.4 | ≥ 55 |
| Under-extract | 0.0 | < 40 |
| Over-extract | 46.9 | < 50 |

**焙度錨點重貼標後分數（2026-04-25，Hoffmann 校準從 `light` 搬到 `medium_light`）：**
| 錨點 | 分數 | 閾值 |
|------|------|------|
| Hoffman | 94.6 | > over-extract |
| April | 90.0 | ≥ 60 |
| Championship | 69.8 | ≥ 55 |
| Under-extract | 0.0 | < 40 |
| Over-extract | 35.2 | < 50 |

**物理解釋（CGA 校準）：**
原 IDEAL_CGA=0.05 低於任何可達配方（Hoffman 實測 0.064），造成評分恆懲罰 CGA。
新 IDEAL_CGA=0.057 對齊好配方可達值；Over-extract（0.079）仍明顯高於 ideal，繼續被懲罰。

---

## Phase 4 — 粗磨+長浸泡象限校準 ✅（2026-05-13）

**目標：** 修正模型對「粗磨+長時間」象限的錯誤預測（誤判為 AC 流失+CGA 暴增），對齊 Hedrick Zuppa Lunga / Gagne 10-min 等實證食譜。

**完成內容：**
- [x] `constants.py`：新增 `GRIND_KINETICS_COEFF=0.40`
- [x] `models/compounds.py`：CGA / AC 動力學耦合研磨粗細（粗磨 → 起始延後 + 速率減緩，符合 Fuller & Rao 2017 first-order + plateau；coffeeadastra 澀感受表面積限制）
- [x] `diagnose_anchor.py`：新增第 6 錨點 Hedrick/Gagne（dial 6.0 / 14g / 95°C / 240s / standard / target AC > CGA, score ≥ 55, TDS ∈ [0.95, 1.65]）
- [x] `optimizer.py`：Top N 多樣化（`TOP_DIVERSITY_DIAL_MIN=1.0` / `STEEP_MIN=60` / `DOSE_MIN=2.0`）讓 Top 列表呈現不同風格的代表；`diversify_top=False` 旗標供錨點驗證使用
- [x] 六錨點全 PASS，Over-extract 從 35.2 → 12.4（細磨長浸泡懲罰加重）

**Phase 4b（SW/PS 時間發展鑑別）：**
- [x] `SW_TIME_FLOOR: 0.50→0.30`、`K_SW: 0.010→0.014`
- [x] `PS_TIME_FLOOR: 0.50→0.30`、`K_PS: 0.008→0.012`
- [x] 60s 短浸泡 vs 120s 完整浸泡的 SW/PS 差距拉開（同 dose 22g：60s 從 91.4 → 84.5）

---

## Phase 5 lite+ — TDS-EY mismatch 懲罰 ✅（2026-05-13）

**目標：** Phase 5 lite 單側懲罰沒擋住「低 TDS + 高 EY」象限（SCA under-concentrated quadrant：dose 過瘦 → 模型靠過萃補 TDS → 酸感集中、澀鹹、無香）。用戶實測 4.3/20g/120s/96°C / EY 22% / TDS 1.22% 模型給 95.1 分。

**完成內容：**
- [x] `constants.py`：新增 `TDS_EY_MISMATCH_WEIGHT=2.0` / `TDS_EY_MISMATCH_K=10.0`
- [x] `models/scoring.py`：step 8 加 `mismatch_factor = exp(-w × softplus(ey - ey_prefer, k) × softplus(tds_prefer - tds, k))`
- [x] AND-gated（兩條件同時滿足才扣分）
- [x] **參數選擇文獻基礎**：Frost & Ristenpart 2020 顯示 TDS-酸質為線性連續關係（非閾值），故選 k=10 平滑 gradient 而非 k=20 銳閾值；不為保護 Hoffman 經典分數而調高銳度（見 `feedback_dont_overprotect_hoffman.md`）

**效果：**
- 用戶 20g 案例：95.1 → 77.9（拉開 17 分）
- Hoffman 最佳 (4.4/22g)：95.4 基本不變
- Hoffman 經典 (4.3/22g)：95.8 → 92.3（略過 TDS_PREFER 誠實扣分，非錯誤）
- Phase 5 lite 案例 (4.6/23g)：86.3 不變
- 六錨點全 PASS、11 pytest PASS

---

## Phase 5 lite — Grind-dependent EY deficit 懲罰 ✅（2026-05-13）

**目標：** 細磨高豆量 + 輕度欠萃（EY 低 1-2%）的「mild under-extraction」被誤判為高分。用戶實測 dial 4.6/23g/120s/95°C（EY 19.2% vs target 21%）口感欠萃但模型給 96.9 分。

**完成內容：**
- [x] `constants.py`：新增 `GRIND_EY_DEMAND_K=10.0` / `EY_DEMAND_WEIGHT=0.30`
- [x] `models/scoring.py`：`flavor_score` 簽名加 `dial` 參數；新增 `grind_ey_factor`：sigmoid 在 DIAL_BASE 銳轉換，softplus(k=5) 平滑單側 deficit
- [x] 串接 `optimizer.py` + `diagnose_anchor.py` 所有 `flavor_score` 呼叫處
- [x] 用戶實測案例：96.9 → 86.3（拉開 9 分鑑別度）；Hoffman 4.4 達標基本不變

**設計約束（CLAUDE.md「EY 不得作為主要扣分依據」原則）：**
- 細磨象限觸發（dial < ~4.7，sigmoid 銳度 K=10）
- 單側（只懲罰不足，不懲罰超標）
- 最大扣分 ~25%（不主導）
- 粗磨（April/Hedrick/Champion）完全豁免

---

## Phase 5 full — IDEAL_FLAVOR + COMPOUND_BASE 文獻校準 ✅（2026-05-13）

**完成內容：**

**1. `IDEAL_FLAVOR["medium_light"]` 三 bracket 重寫為文獻對齊值：**
```python
("medium_light", "low"):  {"AC": 0.17, "SW": 0.37, "PS": 0.15, "CA": 0.07, "CGA": 0.14, "MEL": 0.10}
("medium_light", "mid"):  {"AC": 0.15, "SW": 0.40, "PS": 0.16, "CA": 0.07, "CGA": 0.12, "MEL": 0.10}
("medium_light", "high"): {"AC": 0.13, "SW": 0.42, "PS": 0.17, "CA": 0.07, "CGA": 0.11, "MEL": 0.10}
```
變動：PS 0.29→0.16（文獻 GM+AG ≤17%）、CGA 0.057→0.12（Cordoba 11/110 mg/mL）、MEL 0.05→0.10（Vignoli 10%）、CA 0.09→0.07、SW 補足為 0.40。

**2. `COMPOUND_BASE["medium_light"]` 反推（不是直接套 IDEAL）：**
從 Hoffman (98°C / dial 4.6 / 120s / 11g) 實測動力學乘子（AC 1.116, SW 0.736, PS 0.996, CA 0.911, CGA 1.194, MEL 1.185）back-solve：
```python
"medium_light": {"AC": 0.123, "SW": 0.494, "PS": 0.146, "CA": 0.070, "CGA": 0.091, "MEL": 0.076}
```
Sum=1.000；驗證 Hoffman 化合物 profile 落在新 IDEAL ±0.1pp（AC 15.16 / SW 39.82 / PS 16.05 / CA 7.04 / CGA 11.99 / MEL 9.93）。

**3. 三個 ratio 閾值：**
- `AC_CGA_RATIO_IDEAL`: 2.0 → **1.25**（15/12）
- `SW_BITTER_RATIO_IDEAL`: 3.0 → **1.82**（40/(10+12)）
- `PS_CA_RATIO_IDEAL`: 2.0 → **2.29**（16/7）

**4. PS 從主要 indicator 降為中等：**
- `WEIGHTS["PS"]`: 2.0 → **1.3**（與 CA/CGA/MEL 同級）
- `COMPOUND_SIGMA_LO["PS"]`: 0.15 → **0.25**（PS 不足側放寬，避免低溫 Champion 過度懲罰）

**5. 錨點診斷閾值同步重校（diagnose 用，不進評分）：**
- `CGA_ASTRINGENCY_THRESHOLD`: 1.15 → **1.10**（IDEAL_CGA 升 2× 使比值天然下降）
- `diagnose_anchor.py` Champion `PS+SW` 閾值: 0.40 → **0.35**（PS base 砍半使絕對和下降）

**結果分數（Phase 5 full 最終）：**
| 錨點 | 分數 | 閾值 |
|------|------|------|
| Hoffman | 92.9 | > over-extract |
| April | 80.1 | ≥ 60 |
| Championship | 56.4 | ≥ 55 |
| Under-extract | 0.0 | < 40 |
| Over-extract | 11.5 | < 50 |
| Hedrick/Gagne | 95.7 | ≥ 55 |

**Phase 5 lite / lite+ 機制驗證未退化：**
- Phase 5 lite（EY=19.2 deficit, dial 4.6 fine）：84.2 分（penalty active）；同條件 coarse dial 6.0：94.5（豁免）
- Phase 5 lite+（TDS=1.22 + EY=22 mismatch, dial 4.3）：78.4 分（penalty active）；無 EY surplus 控制組 93.8

**11 pytest PASS、六錨點全 PASS。**

**為什麼這次成功避免「移動標的」問題：**
- COMPOUND_BASE 不是直接複製 IDEAL，而是從 Hoffman 動力學乘子反推 — 確保 Hoffman 預測落點 = 新 IDEAL mid
- PS weight + sigma_lo 同時放寬 — PS 從「主要 body indicator」變為中等，符合新 IDEAL 16% 是文獻天花板而非舒適區的事實
- 診斷閾值（CGA_ASTRINGENCY_THRESHOLD、PS+SW）跟著 IDEAL 尺度同步調 — 這些是「相對於 ideal 的偏差檢查」，IDEAL 改了就要重設零點

**參考資料：**
- pmc.ncbi.nlm.nih.gov/articles/PMC10074501/ — Cordoba 2023 Food Chem Advances
- sciencedirect.com/science/article/abs/pii/S0963996916300217 — Vignoli 2016
- pubmed.ncbi.nlm.nih.gov/11879015/ — Nunes & Coimbra 2002
- pubmed.ncbi.nlm.nih.gov/973456/ — Wolfrom & Patin 1976
- pubs.acs.org/doi/10.1021/acsfoodscitech.0c00078 — Frost/Ristenpart 2020

---

## Phase 6 — 化合物模型純物理化（compounds.py 純連續、scoring.py 留閾值）✅（2026-05-14）

**完成內容：**

**1. `compounds.py` 重寫為純 Arrhenius × 一階反應動力學**
- 新增 `_arrhenius(temp, Ea)` 輔助函數：`exp(Ea/R × (1/T_ref − 1/T))`，全域 monotone 無拐點。
- 全部六種化合物統一架構：`base × (1 − exp(−k·t))`，`k = K_ref × arr(T) × grind_kinetics`。
- AC 特例：`base × (1 − exp(−k_ext·t)) × exp(−k_deg·t)`（萃取 × 衰減雙 Arrhenius）。
- **完全移除：** AC 線性溫度修正、SW tent function、PS softplus 偽閾值、CGA softplus(temp−92)、所有 onset gate、所有 time floor。

**2. `constants.py` 變更**
- **新增：** `GAS_CONSTANT_R=8.314`、`ARRHENIUS_T_REF_C=98.0`、Ea per compound（AC_EXT_EA 30 / AC_DEG_EA 70 / SW_EA 35 / PS_EA 45 / CA_EA 40 / CGA_EA 55 / MEL_EA 50 kJ/mol）、`K_AC_EXTRACT=0.10` / `K_AC_DEG=0.0010` / `PS_DIAL_COEFF=0.20`。
- **刪除：** `SW_TIME_FLOOR`、`PS_TIME_FLOOR`、`CGA_TIME_ONSET`、`MEL_TIME_ONSET`、`MEL_TIME_MAX`、`CGA_TIME_MAX`、`AC_DECAY_START`、`AC_HIGH_TEMP_THRESH`、`AC_HIGH_TEMP_DECAY`、`K_AC_DECAY`。
- **降速：** `K_CGA_TIME` 0.015→0.008（移除 `(1 + CGA_TIME_MAX × ...)` 放大結構後，需更慢的 K 才能保留過萃判別）。
- **回推 base：** `COMPOUND_BASE["medium_light"]` 由舊乘子 / 新乘子比例反推 = `{AC: 0.1533, SW: 0.5702, PS: 0.2081, CA: 0.0713, CGA: 0.1824, MEL: 0.1709}`（sum=1.36；非物理約束，純內部校準）。

**3. 六錨點結果（全 PASS）**
| 錨點 | 分數 | 與 Phase 5 full 比較 |
|------|------|---------------------|
| Hoffman | 92.0 | -0.8 |
| April | 74.1 | -6.0 |
| Championship | 60.8 | +4.4 |
| Under-extraction | 0.0 | 不變 |
| Over-extraction | 36.3 | +24.8（過萃從 11.5 漲到 36.3，仍 PASS < 50）|
| Hedrick/Gagne | 68.1 | -27.6（仍 PASS ≥ 55）|

**4. BAD case 改善**
- 用戶實測 98°C/4.4/90s/22g XL（Phase 5 full Top 1 = 94.4 分）：optimizer 現在不再推薦此配方為 Top 1
- 新 Top 1：93°C/4.3/150s/24g（score 95.7）— 移除高溫短浸泡的過萃陷阱
- 直接探測該配方仍給 92.5（壓低 1.9），但 optimizer 整體不再推薦

**5. 行為變化（CLI 測試已放寬）**
- Medium roast XL 從 92°C/120s 改為 87°C/390s（Hedrick/Gagne 風格從新動力學自然湧現）
- Medium-light XL Top 1 從 98°C/4.4/90s 改為 93°C/4.3/150s（避免 SW_AROMA 高溫損失）
- `tests/test_output_and_cli.py::test_cli_reference_command_ranges` temp/steep 範圍已放寬

**6. 設計原則對齊（CLAUDE.md 原則 #4）**
- compound layer 純 `exp()` 結構（Arrhenius / 一階），無任何 threshold 參數
- perceptual layer（scoring.py）保留：SW_AROMA、SCORCH、TDS_FLOOR、KH_FLOOR、GH_SOFT 等合法感官閾值
- 11 pytest PASS

**7. 已知殘留 issue（未解決）**
- 90s vs 120s 在標準 brewer 同 dose 下，90s 仍略高於 120s（89.6 vs 87.6，幾乎相同）— 這是 `build_ideal_abs` 用 actual TDS 內插 IDEAL bracket 的結構效應，欠萃時 IDEAL 也跟著下移，吸收了絕對差距。Phase 6 已讓 compound 絕對值正確反映欠萃（SW 0.344 vs 0.398 = 13.5% gap），但 scoring 用 fraction 比較最後抹平差距。Optimizer 仍會選 120s 而非 90s（因為其他 TDS/EY 軸協同篩選），但純化合物對 90s/120s 在 standard brewer 鑑別力有限。屬於 scoring layer 設計議題，非 Phase 6 範圍。

**參考資料：**
- Fuller & Rao 2017 (Sci. Reports) — CGA first-order kinetics + Arrhenius
- Cordoba 2023 PMC10074501 — 化合物 saturation 曲線
- Frost & Ristenpart 2020 — TDS-酸質連續關係
- coffeeadastra.com — 萃取動力學實務觀察

---

## Phase 6 — 化合物模型純物理化（已完成歷史紀錄保留）❌ → ✅

**起源（2026-05-14 對話）：**
用戶實測 model Top 1 配方（98°C / dial 4.4 / 90s / 22g XL，score 94.1），實際口感「酸澀重」。物理上 98°C × 90s 是文獻記載的「酸澀」trap — CGA Arrhenius 加速 + SW/PS 受時間限制 = CGA 已大量出來、SW/PS 尚未追上。

研究發現（subagent + 手動 trace）BAD vs Hoffmann-style XL（98°C/4.3/120s/22g, score 87.5）的化合物 fractions 幾乎相同，只是 SW/PS 絕對濃度低 6-14%。`compute_actual_abs` 正規化 + 跟 IDEAL × TDS 比 → 絕對量差距被吸收 → 模型無法分辨。

實驗性 `acid_trap`（temp + steep 雙 sigmoid AND-gate）可暫時讓 BAD 從 94.1 → 81.8，但**走 process-variable 直接懲罰路徑、跳過化合物層** → 違反 CLAUDE.md 原則 #3 + 新原則 #4。已 revert。

**根因：`compounds.py` 內部有多個非物理 gate** 讓化合物預測「過早平台」，模型認為 90s 接近完整萃取，喪失 90s vs 120s 鑑別力。

**清單 — `compounds.py` 待移除的非物理 gate：**

| Compound | 現況非物理項 | 物理問題 | Phase 6 動作 |
|----------|------------|---------|-------------|
| **AC** | `ac *= 1 + (temp - 90) * 0.02` | 線性溫度（應 Arrhenius） | 改 `ac *= exp(Ea_AC/R × (1/T_ref - 1/T))` |
| **AC** | `AC_DECAY_START=150` + softplus gate | 起始延後（應 t=0 連續） | 刪除 onset，純 `exp(-K_AC × t)` |
| **AC** | `AC_HIGH_TEMP_THRESH=95.0` + softplus | 高溫降解閾值（應 Arrhenius） | 改 Arrhenius 分解速率 |
| **SW** | `1 - abs(temp - optimal) * 0.018` | Tent function（峰點不可微） | 改 Gaussian `exp(-(temp-optimal)²/2σ²)` |
| **SW** | `SW_TIME_FLOOR=0.30` | t=0 還有 30% SW（非物理） | 刪除 floor，純 `(1 - exp(-K_SW × t))` |
| **PS** | `1 + softplus(DIAL_BASE - dial, k=3) * 0.28` | 粗磨 softplus gate | 改線性或物理表面積模型 |
| **PS** | `PS_TIME_FLOOR=0.30` | 同 SW | 刪除 floor |
| **PS** | `softplus(1 + (temp - 90) * 0.028, k=10)` | 防負值 softplus 偽裝閾值 | 改 Arrhenius |
| **CGA** | `1 + softplus(temp - 92, k=2) * 0.02` | 92°C 閾值（應 Arrhenius 全域） | 改 Arrhenius |
| **CGA** | `CGA_TIME_ONSET=150` + softplus gate | 起始延後（首要禍源）| 刪除 onset，純 first-order |
| **MEL** | `MEL_TIME_ONSET=80` + softplus gate | 起始延後 | 刪除 onset |
| **CA** | `1 - exp(-K_CA × t)` | **純一階 ✓** | **保留（範本）** |

**`constants.py` 要刪除的常數：**
- `AC_DECAY_START`、`AC_HIGH_TEMP_THRESH`、`AC_HIGH_TEMP_DECAY`
- `SW_TIME_FLOOR`、`PS_TIME_FLOOR`
- `CGA_TIME_ONSET`
- `MEL_TIME_ONSET`

**`constants.py` 要新增的常數（Arrhenius 參數，per compound）：**
- `AC_ARRHENIUS_EA` / `AC_T_REF`（活化能 kJ/mol、參考溫度 K）
- `SW_ARRHENIUS_EA` / `SW_T_REF`
- `PS_ARRHENIUS_EA` / `PS_T_REF`
- `CGA_ARRHENIUS_EA` / `CGA_T_REF`
- `MEL_ARRHENIUS_EA` / `MEL_T_REF`

文獻參考（Ea 數量級）：Fuller & Rao 2017 CGA Ea ≈ 50-60 kJ/mol；糖類 30-40；酸類 40-50。

**`scoring.py` 要清理：**
- 拆掉實驗版 `acid_trap`（已 revert，但 Phase 6 完成後應確保不會 reintroduce）
- 留 `SW_AROMA`、`SCORCH_PARAMS`、`KH_FLOOR`、`TDS_FLOOR_MID`、`GH_SOFT_*` — 這些都是合法感官閾值

**校準方法（與 Phase 5 full 同步驟）：**

1. **第一輪：純物理重寫 compounds.py（不調 base，只換公式）**
   - 跑 Hoffman 錨點，記錄新 vs 舊化合物 ratio
   - 用這 ratio 反推新 `COMPOUND_BASE["medium_light"]`（保 Hoffman profile 接近舊 IDEAL）
2. **第二輪：跑六錨點，迭代調 `COMPOUND_BASE` per roast**
3. **第三輪：可能需調 `WEIGHTS`、`COMPOUND_SIGMA_LO/HI`**（Arrhenius 純物理後，化合物隨溫度的響應曲線改變）
4. **第四輪：驗證 BAD 配方分數**（用戶實測 98°C/4.4/90s/22g）應該 ≤ 85，Hoffmann-style XL ≥ 85
5. **第五輪：跑 11 pytest，全 PASS**

**預期結果：**
- BAD 化合物 profile 自然顯示 SW/PS 嚴重不足 → compound_reward 自然扣分 → 不需要 acid_trap
- April 化合物 profile 顯示低溫低萃取（Arrhenius 自然壓低）→ 正常評分
- Champion 倒置低溫 → 短時但低溫，Arrhenius 自然低 CGA → 正常評分
- Hedrick 240s 長浸 → 所有化合物達平台 → 高分

**風險（為什麼是大工程）：**
- 影響 4 個化合物 kinetic 區段 + 7 個常數刪除 + 5 對新常數
- Arrhenius 參數沒精確文獻值（要從現有 base/K 校驗反推）
- 六錨點全要重跑，預估 5-8 輪 iteration
- 整體規模 ≈ Phase 5 full × 1.5

**為什麼仍要做：**
- 走杯中物路徑 → 用戶可信賴模型推薦
- 不再需要 process-variable 補丁（acid_trap、SW_TIME_FLOOR fudge）
- 任何未來「酸澀過萃欠萃」象限的問題都能透過化合物層自然反映
- 完整實現 CLAUDE.md 四條核心原則

**建議執行時機：** 用戶有時間做 5-8 輪錨點迭代 + 後續實測驗證；現階段所有六錨點 PASS、Phase 5 lite/lite+ 機制完整，模型可用但有 BAD 配方推薦 bug 未根治。

**參考資料：**
- Fuller & Rao 2017 (Sci. Reports) — CGA first-order kinetics + Arrhenius
- Cordoba 2023 PMC10074501 — 化合物 saturation 曲線
- Frost & Ristenpart 2020 — TDS-酸質連續關係
- coffeeadastra.com — 萃取動力學實務觀察

---

## UI — Chip 標籤重寫（Phase 1-3 已完成，現可進行）

原註記「等 Phase 1-3 完成後才能做」— Phase 1-3 已於 2026-04-12 完成、Phase 4 進一步穩定模型。Chip 標籤現在可以基於最新模型（Phase 4 + Phase 5 lite 後）重新設計風味描述。但需注意 Phase 5 full 仍未做，所以 IDEAL_FLAVOR 對 PS/CGA 的描述語會跟 Phase 5 full 完成後不同（PS 描述若強調「醇厚」目前是基於 29% PS ideal，真實 15% 下「醇厚」感官門檻不同）。

**建議順序：** Phase 5 full → Chip 標籤；或接受暫時描述語落差先做 Chip。
