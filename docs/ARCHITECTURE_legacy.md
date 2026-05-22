> ⚠️ **凍結 — 過期架構（Phase 8 / 六化合物時代）。**
>
> 本文件是 Phase 10 之前的 `ARCHITECTURE.md`，描述**已退役**的六化合物模型
> （`compounds.py` / `ey_model.py` / `tds_model.py` / `scoring.py` / `labels.py` /
> `water_presets.py`）、感官 label 島、log-ratio Gaussian 評分公式、水質參數。
>
> **這些模組與概念在 Phase 10 已全部刪除**（保留於 git branch
> `compound-model-legacy`）。本文件只在那個 branch 上仍然成立 —— 留在這裡是為了
> 歷史對照，**不要照它改 main 上的程式**。
>
> 目前（Phase 10/11）的架構見 [`../ARCHITECTURE.md`](../ARCHITECTURE.md)。
> Phase 10 改了什麼、為什麼，見 `PHASE10_*.md`；Phase 11 迴圈引擎見
> [`PHASE11_LOOP_ENGINE.md`](PHASE11_LOOP_ENGINE.md)。

---

# Architecture

> 模組結構、資料流、評分公式細節。CLAUDE.md 只放紅線原則與錨點基準，
> 想看「程式怎麼跑」、「評分長什麼樣」翻這裡。

## Data Flow

```
main.py (CLI args)
  → runtime.py          # apply T_ENV, altitude, resolve water profile
  → optimizer.py        # grid search over (temp × dial × steep × dose)
      ├─ optimize(label=X)         # single label → Top-N
      └─ optimize_parallel()       # Channel B → Top-1 per label, shared physical pass
      → models/ey_model.py         # calc_ey: extraction yield %
      → models/compounds.py        # predict_compounds: six-compound vector
      → models/tds_model.py        # calc_tds, press time, drip, retention
      → models/labels.py           # load_labels, ideal_abs, recipe_id
      → models/scoring.py          # flavor_score(label=X) → final rank score
  → output/{terminal,export,radar}.py
```

## Grid Search (optimizer.py)

`_grid_candidates()` iterates `temp × dial_x10 × steep × dose_x2` once. For each:
1. Compute `press_sec` via Darcy law (channeling collapse if > 60s threshold)
2. Compute EY using Arrhenius + concentration gradient model
3. Predict six compounds (AC, SW, PS, CA, CGA, MEL) at extraction conditions
4. Apply channeling correction
5. Compute TDS
6. Stamp `recipe_id` (sha1 hex prefix of brew params — Phase 9 feedback link)

`_score_against_label()` then scores each physical candidate against one label;
`optimize_parallel()` reuses the same physical pass across every label (Channel B).
Top-N selection is per-label, by `_score_raw` descending. Soft `dial_prefer` Gaussian
penalty (±15% max; XL +0.10 brewer offset) is applied per candidate per label.

Phase 8 removed the old `TOP_DIVERSITY_*` mechanism — multi-label parallel Top
(Channel B) supersedes it.

## Six-Compound Model (compounds.py)

| Compound | Flavor role |
|----------|-------------|
| AC | Acidity (organic-acid-derived) |
| SW | Sweetness / aroma volatiles |
| PS | Polysaccharides → body / mouthfeel |
| CA | Caffeic acid (mild bitterness) |
| CGA | Chlorogenic acid (astringency) |
| MEL | Melanoidins (roasty bitterness) |

**Phase 6（2026-05-14 完成）：純 Arrhenius × 一階反應**
- 統一架構：`base × (1 − exp(−k·t))`，`k = K_ref × arr(T) × grind_kinetics`
- AC 特例：`base × (1 − exp(−k_ext·t)) × exp(−k_deg·t)`（萃取 + 衰減雙 Arrhenius）
- `_arrhenius(T, Ea)` = `exp(Ea/R × (1/T_ref − 1/T))`，T_ref = 98°C
- 每個化合物的 Ea（kJ/mol，文獻對齊）：AC_EXT 30 / AC_DEG 70 / SW 35 / PS 45 / CA 40 / CGA 55 / MEL 50
- **化合物層禁所有閾值**（onset / floor / tent / softplus(temp − X)）；溫度敏感全走 Arrhenius、時間用 first-order
- SW 額外乘 `exp(SW_DIAL_COEFF × (DIAL_BASE − dial))`（細研磨增表面積、香氣多）
- PS 額外乘 `exp(PS_DIAL_COEFF × (DIAL_BASE − dial))`（連續取代舊 softplus）
- CGA/AC/MEL 額外乘 `grind_kinetics = exp(GRIND_KINETICS_COEFF × (DIAL_BASE − dial))`（粗磨速率減緩；Phase 7 將同耦合套到 MEL）

`predict_compounds()` 在非倒置時跑兩次 `_predict_closed_compounds`：主流程
（`effective_steep`）+ drip 流程（`drip_contact ≈ drip_time × 0.2`），按
`drip_ratio` 加權混合，再依序套用 EY 冪律修正 + press_perc 滲流選擇性。

## Sensory Labels (Phase 8)

Phase 8 split the pre-existing single `IDEAL_FLAVOR[(roast, bracket)]` into
per-label islands. Each label is one self-contained sensory target:

```
data/labels.json
└─ <label>
   ├─ ideal: { AC, SW, PS, CA, CGA, MEL }   # compound fractions, ~sum=1
   ├─ tds_prefer: number                    # 1.17 / 1.27 / 1.40 / 1.56
   ├─ description: human-readable summary
   └─ bullseye_anchor: name of seed calibration recipe (or null for hypothetical)
```

**Initial 4 labels (Phase 8):** `balanced` (Hoffman), `acid-forward` (April),
`sweet-body` (Championship), `coarse-modern` (Hedrick).

**Zero-coupled** by construction — editing one label cannot alter another's
scores. New labels are append-only via `data/labels.json` (Channel A discovery).
Multi-label parallel Top is Channel B (`optimize_parallel()`).

`models.labels.ideal_abs(label, tds)` replaces the deprecated Gaussian-bracket
`build_ideal_abs(roast, tds)`. No more TDS low/mid/high interpolation — each
label has one IDEAL, period.

## Scoring Formula (scoring.py)

```
flavor_score(actual, tds, roast, label, ...) =
       compound_reward
     × tds_factor               # vs label.tds_prefer (per-label Super-Gaussian centre)
     × ey_factor                # EY_GAUSS_WEIGHT=0.0 → ≡ 1.0
     × tds_floor_factor
     × grind_ey_factor          # Phase 5 lite (fine + EY deficit)
     × mismatch_factor          # Phase 5 lite+ (low TDS + high EY)
```

### compound_reward — log-ratio Gaussian
- 每個化合物計算 `log(actual_perceived / ideal_from_label)` 偏差
- 非對稱 sigma：`COMPOUND_SIGMA_LO`（不足側）/ `COMPOUND_SIGMA_HI`（超標側），sigmoid 平滑混合
- 加權平均後取 exp。actual = ideal → reward = 1.0
- `WEIGHTS = {AC:1.0, SW:1.8, PS:1.3, CA/CGA/MEL:1.3}`
- `SIGMA_LO`: SW 0.15 嚴懲、PS 0.25、AC 0.30、苦味 0.80 寬鬆
- `SIGMA_HI`: CGA 0.18 / CA/MEL 0.25 嚴懲、AC 0.35、SW/PS 0.60 寬鬆

### 加速懲罰
- `ACCEL_W_PER_COMPOUND[CGA]=0.20`、`[MEL]=0.15`
- 超過 `PENALTY_ACCEL_THRESHOLD=2.5` 後 softplus 加速
- sigmoid 方向門控（只懲罰超標、不懲罰不足）

### ideal_abs（Phase 8）
- `models.labels.ideal_abs(label, tds, roast=None)` — 直接從 `data/labels.json[label].ideal` × `tds`
- 苦味化合物（CA/CGA/MEL）在 scoring 內部再乘 `IDEAL_BITTER_REDUCTION=0.95`
- **No more bracket interpolation** — old `build_ideal_abs(roast, tds)` 已廢除
- **roast override（labels.json v3）**：label 可帶 `ideal_by_roast`，某焙度搆不到預設 ideal 時改用自己的 bullseye。目前只有 `balanced.light`（淺焙搆不到 medium_light 的 CGA/MEL 0.12/0.11）—— 粗略 model-derived、無實測錨點，待 light-roast balanced 食譜出現後精修

### tds_factor — 不對稱 Super-Gaussian
- `TDS_GAUSS_SIGMA_LOW=0.15`（太淡嚴懲）
- `TDS_GAUSS_SIGMA_HIGH=0.65`（高濃縮寬鬆，支援 Championship 1.56%）
- 平頂指數 `TDS_SUPER_GAUSS_EXP=4`
- 中心點：每個 label 的 `tds_prefer`（Phase 8 改 per-label，取代舊 per-roast `TDS_PREFER`）

### tds_floor_factor — sigmoid
- `1 / (1 + exp(-TDS_FLOOR_K × (tds - TDS_FLOOR_MID)))`
- `MID=0.50`、`K=8.0`（全域連續可導，取代舊 `min(tds/0.80, 1)²`）

### grind_ey_factor — REMOVED (2026-05-21)
細磨欠萃 EY-floor 懲罰（舊 `GRIND_EY_DEMAND_K` / `EY_DEMAND_WEIGHT`）已移除：它按
EY×dial（皆過程變數）扣分，撞紅線「EY 不得作為主要扣分依據」。錨點探針證實移除後
真欠萃（TDS~1.0）仍只拿 10–14 分 —— `compound_reward` + `tds_floor_factor` 自我鑑別
承載好壞（原則 #3）。它本是 base_ey 17.0 時代的 Phase 5 lite 補丁，TDS 校準後 EY 整體
下移使其誤傷低於 98°C 的細磨好 brew。

### mismatch_factor（Phase 5 lite+）
- 低 TDS + 高 EY 雙條件 AND-gated（SCA under-concentrated 象限）
- `TDS_EY_MISMATCH_WEIGHT=2.0` / `TDS_EY_MISMATCH_K=10.0`

### ratio_bonus — REMOVED (Phase 8)
舊 AC/CGA、SW/(MEL+CGA)、PS/CA 全域加分曲線已廢除。每個 label 的 IDEAL 已隱含
這些 ratio 偏好，全域 ratio 加分變成「在 IDEAL 之上再疊加偏好」的雙重作用。

## 感知前處理（物理，在 compound_reward 之前）

- **KH 壓制酸質感知**：`AC × (KH_FLOOR + (1 − KH_FLOOR) × exp(−KH / KH_PERCEPT_DECAY_SMOOTH))`，`KH_FLOOR=0.65`、`KH_PERCEPT_DECAY_SMOOTH=42.0`（kh=30 → factor≈0.82；kh→∞ 漸近 0.65）
- **高溫 SW 香氣損失**：sigmoid 中心 `SW_AROMA_THRESH=97°C`，上限 `SW_AROMA_CAP=0.25`，斜率 `SW_AROMA_SIGMOID_K=3.0`
- **高溫焦苦放大（深焙）**：`SCORCH_PARAMS` per-roast 閾值，softplus 平滑（`SCORCH_SOFTPLUS_K=0.5`）
- **軟水苦味放大**：GH→0 時 CA/CGA/MEL ×(1+0.25)，sigmoid 過渡（`LOW_GH_THRESHOLD=20`、`GH_SOFT_SIGMOID_K=0.3`）
- **低溫萃取補正（calc_ey 內）**：`temp_initial < K_LOW_TEMP_FLOOR=87°C` 時飽和補正最高 4×（April 85°C / Championship 80°C 觸發）

## Key Files

| File | Role |
|------|------|
| `constants.py` | Tunable physics constants (Layer 1) |
| `data/labels.json` | Sensory label islands (Layer 2 — IDEAL + TDS_PREFER per label) |
| `diagnose_anchor.py` | Two-layer anchor validation (Layer 1 physics bands + Layer 2 label scoring) |
| `models/labels.py` | label loader, `ideal_abs()`, `recipe_id()` |
| `models/scoring.py` | label-parameterized `flavor_score()` |
| `models/compounds.py` | Six-compound extraction prediction (Phase 6 pure physics) |
| `models/ey_model.py` | EY calculation |
| `models/tds_model.py` | TDS, press time, drip volume, retention |
| `optimizer.py` | Grid search + `optimize()` (single-label) / `optimize_parallel()` (Channel B) |
| `runtime.py` | Environment settings (T_ENV, altitude, water profile) |
| `data/water_presets.py` | Named water profiles |
| `webapp.py` | Flask web interface (handles single-label + Channel B) |
| `tests/test_compound_calibration.py` | Layer 1 physics-only tests |
| `tests/test_label_scoring.py` | Layer 2 label-scoring-only tests |
| `docs/FEEDBACK_FORMAT.md` | `data/feedback.jsonl` schema spec (Phase 9 hook) |

## ZP6 Dial Reference

- `dial < 4.5`: fine grind (Hoffman anchor 4.3 is here)
- `dial = 4.5`: model reference point (`DIAL_BASE`)
- `dial > 4.5`: coarse grind

`dial_prefer` per roast 儲存在 `ROAST_TABLE`；XL 額外加 `dial_offset = 0.10`
（在 `BREWER_PRESETS["xl"]` 內），optimizer 在計算 dial Gaussian 時套用。

## Water Quality Parameters

Water affects scoring through three channels:
- **GH (hardness)**: 控制化合物萃取效率（calc_ey 內套用）
- **KH (alkalinity)**: 壓制酸質感知；平滑公式 `KH_FLOOR=0.65 + 0.35 × exp(−KH / KH_PERCEPT_DECAY_SMOOTH=42.0)`
- **mg_frac**: Mg²⁺ 比例 boost AC/SW；Ca²⁺ 比例 boost PS/CGA
- Soft water (GH < `LOW_GH_THRESHOLD=20`，如 RO) 觸發額外苦味放大

Default water when unspecified: GH=50, KH=30, mg_frac=0.40.

## 常數修改方向參考（口感矯正用）

| 口感症狀 | 可能方向 | 注意 |
|---------|---------|------|
| 太苦 | 收緊 `COMPOUND_SIGMA_HI["CGA"/"MEL"]`、調高 `IDEAL_BITTER_REDUCTION` | 確認 Top3 TDS 不下移 |
| 酸不足（某 label） | 調 `data/labels.json[<label>].ideal["AC"]` ↑、降 `KH_PERCEPT_DECAY_SMOOTH` | 不影響其他 label |
| 太澀 | 收緊 `COMPOUND_SIGMA_HI["CGA"]` | 確認 anchor 仍 PASS |
| 甜感弱（某 label） | 調 `data/labels.json[<label>].ideal["SW"]` ↑、收緊 `COMPOUND_SIGMA_LO["SW"]` | 後者影響所有 label |
| 太濃 | 調該 label 的 `tds_prefer` ↓ | 不影響其他 label |
| 太淡 | 調該 label 的 `tds_prefer` ↑ | 同上 |
| 想要新風味檔案 | append 一個 label 到 `data/labels.json`（Channel A）| 零風險，不動任何既有 label |

修改後**必須**跑 `python diagnose_anchor.py` 確認六錨點全 PASS、`pytest` 全綠。
