# Architecture

> 模組結構、資料流、評分公式細節。CLAUDE.md 只放紅線原則與錨點基準，
> 想看「程式怎麼跑」、「評分長什麼樣」翻這裡。

## Data Flow

```
main.py (CLI args)
  → runtime.py          # apply T_ENV, altitude, resolve water profile
  → optimizer.py        # grid search over (temp × dial × steep × dose)
      → models/ey_model.py      # calc_ey: extraction yield %
      → models/compounds.py     # predict_compounds: six-compound vector
      → models/tds_model.py     # calc_tds, press time, drip, retention
      → models/scoring.py       # flavor_score → final rank score
  → output/{terminal,export,radar}.py
```

## Grid Search (optimizer.py)

Iterates `temp × dial_x10 × steep × dose_x2`. For each point:
1. Compute `press_sec` via Darcy law (channeling collapse if > 60s threshold)
2. Compute EY using Arrhenius + concentration gradient model
3. Predict six compounds (AC, SW, PS, CA, CGA, MEL) at extraction conditions
4. Apply channeling correction to EY and compounds
5. Compute TDS, then `flavor_score`
6. Apply soft `dial_prefer` penalty (Gaussian, ±6% max; XL +0.10 brewer offset)

Results sorted by score; top-N returned. Top N diversification
(`TOP_DIVERSITY_*`) enforces dial/steep/dose differentiation across ranks
unless `diversify_top=False` (anchor validation uses this).

## Six-Compound Model (compounds.py)

| Compound | Flavor role |
|----------|-------------|
| AC | Acidity (chlorogenic-acid-derived) |
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
- CGA/AC 額外乘 `grind_kinetics = exp(GRIND_KINETICS_COEFF × (DIAL_BASE − dial))`（粗磨速率減緩）

`predict_compounds()` 在非倒置時跑兩次 `_predict_closed_compounds`：主流程
（`effective_steep`）+ drip 流程（`drip_contact ≈ drip_time × 0.2`），按
`drip_ratio` 加權混合，再依序套用 EY 冪律修正 + press_perc 滲流選擇性。

## Scoring Formula (scoring.py)

```
flavor_score = compound_reward
             × tds_factor
             × ey_factor              # EY_GAUSS_WEIGHT=0.0 → 恆 1.0
             × tds_floor_factor
             × grind_ey_factor        # Phase 5 lite
             × mismatch_factor        # Phase 5 lite+
```

### compound_reward — log-ratio Gaussian
- 每個化合物計算 `log(actual_perceived / ideal)` 偏差
- 非對稱 sigma：`COMPOUND_SIGMA_LO`（不足側）/ `COMPOUND_SIGMA_HI`（超標側），sigmoid 平滑混合
- 加權平均後取 exp。actual = ideal → reward = 1.0
- `WEIGHTS = {AC:1.0, SW:1.8, PS:1.3, CA/CGA/MEL:1.3}`（Phase 5 full：PS 2.0→1.3）
- `SIGMA_LO`: SW 0.15 嚴懲、PS 0.25、AC 0.30、苦味 0.80 寬鬆
- `SIGMA_HI`: CGA 0.18 / CA/MEL 0.25 嚴懲、AC 0.35、SW/PS 0.60 寬鬆

### 比值獎勵（降 compound_loss）
- AC/CGA（純淨酸質）、SW/(MEL+CGA)（甜苦比）、PS/CA（醇厚乾淨度）
- 三個 sigmoid 加分曲線，加權平均後最多降 `RATIO_WEIGHT=0.15` 的 loss
- Phase 5 full 文獻對齊：`AC_CGA_RATIO_IDEAL=1.25`、`SW_BITTER_RATIO_IDEAL=1.82`、`PS_CA_RATIO_IDEAL=2.29`

### 加速懲罰
- `ACCEL_W_PER_COMPOUND[CGA]=0.20`、`[MEL]=0.15`
- 超過 `PENALTY_ACCEL_THRESHOLD=2.5` 後 softplus 加速
- sigmoid 方向門控（只懲罰超標、不懲罰不足）

### ideal_abs
- 從 `IDEAL_FLAVOR[(roast, bracket)]` Gaussian 內插（`IDEAL_INTERP_SIGMA=0.15`）
- 三 bracket：low (1.00) / mid (1.20) / high (1.40)
- 苦味化合物再乘 `IDEAL_BITTER_REDUCTION=0.95`

### tds_factor — 不對稱 Super-Gaussian
- `TDS_GAUSS_SIGMA_LOW=0.15`（太淡嚴懲）
- `TDS_GAUSS_SIGMA_HIGH=0.65`（高濃縮寬鬆，支援 Championship 1.56%）
- 平頂指數 `TDS_SUPER_GAUSS_EXP=4`
- sigmoid 平滑混合斜率 `TDS_SIGMA_BLEND_K=5.0`

### tds_floor_factor — sigmoid
- `1 / (1 + exp(-TDS_FLOOR_K × (tds - TDS_FLOOR_MID)))`
- `MID=0.50`、`K=8.0`（全域連續可導，取代舊 `min(tds/0.80, 1)²`）

### grind_ey_factor（Phase 5 lite）
- 細磨象限（dial < DIAL_BASE）對 EY 不足嚴懲、粗磨豁免
- `GRIND_EY_DEMAND_K=10.0` sigmoid 銳轉換
- `EY_DEMAND_WEIGHT=0.30`，softplus(k=5) 單側平滑

### mismatch_factor（Phase 5 lite+）
- 低 TDS + 高 EY 雙條件 AND-gated（SCA under-concentrated 象限）
- `TDS_EY_MISMATCH_WEIGHT=2.0` / `TDS_EY_MISMATCH_K=10.0`

## 感知前處理（物理，在 compound_reward 之前）

- **KH 壓制酸質感知**：`AC × (KH_FLOOR + (1 − KH_FLOOR) × exp(−KH / KH_PERCEPT_DECAY_SMOOTH))`，`KH_FLOOR=0.65`、`KH_PERCEPT_DECAY_SMOOTH=42.0`（kh=30 → factor≈0.82；kh→∞ 漸近 0.65）
- **高溫 SW 香氣損失**：sigmoid 中心 `SW_AROMA_THRESH=97°C`，上限 `SW_AROMA_CAP=0.25`，斜率 `SW_AROMA_SIGMOID_K=3.0`
- **高溫焦苦放大（深焙）**：`SCORCH_PARAMS` per-roast 閾值，softplus 平滑（`SCORCH_SOFTPLUS_K=0.5`）
- **軟水苦味放大**：GH→0 時 CA/CGA/MEL ×(1+0.25)，sigmoid 過渡（`LOW_GH_THRESHOLD=20`、`GH_SOFT_SIGMOID_K=0.3`）
- **低溫萃取補正（calc_ey 內）**：`temp_initial < K_LOW_TEMP_FLOOR=87°C` 時飽和補正最高 4×（April 85°C / Championship 80°C 觸發）

## Key Files

| File | Role |
|------|------|
| `constants.py` | All tunable physics/flavor constants |
| `diagnose_anchor.py` | Six-anchor validation (run after every constants change) |
| `models/scoring.py` | Full scoring pipeline |
| `models/compounds.py` | Six-compound extraction prediction (Phase 6 pure physics) |
| `models/ey_model.py` | EY calculation |
| `models/tds_model.py` | TDS, press time, drip volume, retention |
| `optimizer.py` | Grid search engine + Top N diversification |
| `runtime.py` | Environment settings (T_ENV, altitude, water profile) |
| `data/water_presets.py` | Named water profiles (presets) |
| `webapp.py` | Flask web interface |

## ZP6 Dial Reference

- `dial < 4.5`: fine grind (Hoffman anchor 4.3 is here)
- `dial = 4.5`: model reference point (`DIAL_BASE`)
- `dial > 4.5`: coarse grind

`dial_prefer` per roast 儲存在 `ROAST_TABLE`；XL 額外加 `dial_offset = 0.10`
（在 `BREWER_PRESETS["xl"]` 內），optimizer 在計算 dial Gaussian 時套用。

## Water Quality Parameters

Water affects scoring through three channels:
- **GH (hardness)**: 控制化合物萃取效率（calc_ey 內套用）
- **KH (alkalinity)**: 壓制酸質感知；平滑公式 `KH_FLOOR=0.65 + 0.35 × exp(−KH / KH_PERCEPT_DECAY_SMOOTH=42.0)`（舊 `KH_PERCEPT_DECAY=150` 已棄用）
- **mg_frac**: Mg²⁺ 比例 boost AC/SW；Ca²⁺ 比例 boost PS/CGA
- Soft water (GH < `LOW_GH_THRESHOLD=20`，如 RO) 觸發額外苦味放大

Default water when unspecified: GH=50, KH=30, mg_frac=0.40.

## 常數修改方向參考（口感矯正用）

| 口感症狀 | 可能方向 | 注意 |
|---------|---------|------|
| 太苦 | 收緊 `COMPOUND_SIGMA_HI["CGA"/"MEL"]`、調高 `IDEAL_BITTER_REDUCTION` | 確認 Top3 TDS 不下移 |
| 酸不足 | 調整 `IDEAL_FLAVOR` AC 比例、降低 `KH_PERCEPT_DECAY_SMOOTH` | 確認 EY 不過高 |
| 太澀 | 收緊 `COMPOUND_SIGMA_HI["CGA"]` | 確認 120s 仍在 Top 10 |
| 甜感弱 | 調高 `IDEAL_FLAVOR` SW 比例、收緊 `COMPOUND_SIGMA_LO["SW"]` | 確認不影響 AC/SW 比例 |
| 醇厚不足 | 調整 `EY_PS_EXP`、`COMPOUND_SIGMA_LO["PS"]` | 確認 `EY_PREFER` 不低於 19.0 |
| 太濃 | 降低 `TDS_PREFER`（謹慎：不低於 1.20）| 確認 Hoffman EY 18-22% |
| 太淡 | 提高 `TDS_PREFER` | 確認不超過 1.35 |

修改後**必須**跑 `python diagnose_anchor.py` 確認六錨點全 PASS。
