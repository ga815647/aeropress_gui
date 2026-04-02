# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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

# Run a single test file
python -m pytest tests/test_models.py -v

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

### 錨點基準（勿偏離）

| 參數 | Hoffman 實測值 | 模型目標 |
|------|--------------|---------|
| TDS | 1.23%（稍粗）→ 原版 ~1.27% | TDS_PREFER["light"] = 1.27 |
| EY | 20–22% | EY_PREFER["light"] = 21.0 |
| 研磨 | 450–600µm EK43 → ZP6 dial ≈ 4.3 | dial_prefer["light"] = 4.3 |
| 水溫 | 97.8°C（208°F） | 錨點檢查固定 98–99°C |
| 浸泡 | 2:00 → swirl → press | 錨點 fixed_steep=120s |

### 常數修改方向參考

| 口感症狀 | 可能方向 | 注意 |
|---------|---------|------|
| 太苦 | 收緊 COMPOUND_SIGMA_HI["CGA"/"MEL"]、調高 IDEAL_BITTER_REDUCTION | 確認 Top3 TDS 不下移 |
| 酸不足 | 調整 IDEAL_FLAVOR AC 比例、降低 KH_PERCEPT_DECAY | 確認 EY 不過高 |
| 太澀 | 收緊 COMPOUND_SIGMA_HI["CGA"] | 確認 120s 仍在 Top 10 |
| 甜感弱 | 調高 IDEAL_FLAVOR SW 比例、收緊 COMPOUND_SIGMA_LO["SW"] | 確認不影響 AC/SW 比例 |
| 醇厚不足 | 調整 EY_PS_EXP、COMPOUND_SIGMA_LO["PS"] | 確認 EY_PREFER 不低於 19.0 |
| 太濃 | 降低 TDS_PREFER（謹慎：不低於 1.20） | 確認 Hoffman EY 18–22% |
| 太淡 | 提高 TDS_PREFER | 確認不超過 1.35 |

---

## 三錨點食譜原始參數與評分原則

來源：2022 年文章《Brewing for Balance, Acidity, or Sweetness》，使用哥倫比亞 El Tambo 水洗豆。

### 三食譜實測值（原始資料）

| 錨點 | 劑量 | 水量 | 水溫 | 研磨 | 浸泡 | TDS | 目標風味 |
|------|------|------|------|------|------|-----|---------|
| Hoffman 平衡 | 11g | 200ml | 208°F (97.8°C) | 4 EK / 450-600µm（細） | 120s swirl → 150s press | 1.23% | 平衡（Heath bar + 檸檬點心） |
| April 酸質 | 13g | 200ml | 185°F (85°C) | 6.75 EK / 810µm（粗） | 90s total，含半密封 25s | 1.17% | 酸質為主（清爽、爽口、多汁） |
| Championship 甜感醇厚 | 17g | 200ml | 176°F (80°C) | 6.75 EK / 810µm（粗） | 100s 倒置，20s 壓 | 1.56% | 甜感＋醇厚（奶油、牛軋糖、濃稠感） |

### 模型設計原則（禁止偏離）

**好喝不好喝跟泡法無關。評分只看杯中物：化合物比例 + TDS。**

- EY、水溫、浸泡時間是過程變數，不是杯中物品質指標，**不得作為主要扣分依據**
- TDS 是杯中物品質的合法指標（太淡/太濃影響口感）
- 化合物向量（AC/SW/PS/CA/CGA/MEL 比例）是最核心的口感品質指標

**三條不可違反的架構原則：**

1. **禁止 min/max/if-else 硬斷點** — 物理世界是連續的。所有閾值、天花板、地板必須用平滑連續函數：
   - `max(x - threshold, 0)` → softplus 或 sigmoid gate
   - `min(x, cap)` → sigmoid saturation
   - `if x > threshold` → sigmoid transition
   - 不對稱 sigma → 平滑混合公式，不用 if/else
   - 例外：純離散邏輯（inverted=True/False）不在此限

2. **所有錨點用同一個評分公式** — April 和 Championship 必須通過 `flavor_score()` 得到高分，不允許用獨立的 `_anchor_cosine_score()`。如果一個評分系統無法同時獎勵 Hoffman 的均衡、April 的酸質、Championship 的甜醇，那是評分系統的問題，不是用特例繞過的理由。

3. **化合物模型必須自我鑑別** — 好喝的配方（Hoffman/April/Championship）的化合物 profile 進入評分公式後自然高分。難喝的配方（欠萃/過萃）的化合物 profile 自然低分。不需要靠 TDS floor 或 EY floor 來區分好壞 — 化合物信號本身就應該承載這個資訊。

### 三食譜各自「分數不低」的物理原因

| 錨點 | 為何分數不低 | 關鍵信號 |
|------|------------|---------|
| Hoffman | 化合物 log-ratio 偏差小，TDS=1.27–1.35% 接近 TDS_PREFER=1.27 | compound_reward 接近 1.0；tds_factor 接近 1.0 |
| April | AC > CGA 且 AC > MEL（純淨酸質）；TDS=1.17% 在 SCA 範圍 | 以 ACIDITY_IDEAL + TDS_prefer=1.17 的 cosine 評分（獨立公式） |
| Championship | SW+PS > 0.70；SW > MEL/CGA（甜感主導）；TDS=1.56% 高濃縮 | 以 SWEETNESS_IDEAL + TDS_prefer=1.56 的 cosine 評分（獨立公式） |

April 和 Championship 在 `diagnose_anchor.py` 使用各自的 `ACIDITY_IDEAL`/`SWEETNESS_IDEAL` 及對應的 `TDS_prefer`，這**不是偷吃步**——而是正確地以「該食譜的目標風格」作為評分基準。高濃縮配方（Championship TDS=1.56%）不應被主力 TDS_PREFER=1.27 的 Gaussian 嚴懲，因為高濃縮下化合物品質本身仍優秀。

### 評分鑑別度改革進度

**已完成：**
1. ~~移除 CDF~~ → `score_to_display` = raw × 100（直接線性映射）
2. ~~增強化合物平衡懲罰~~ → log-ratio Gaussian（取代舊 cosine_sim + conc_score）
3. ~~TDS 懲罰不對稱化~~ → sigma_low=0.10（太淡嚴懲）, sigma_high=0.20（高濃縮寬鬆）
4. ~~EY 懲罰降到最低~~ → EY_GAUSS_WEIGHT=0.06
5. **禁止**為了讓某錨點通過而削弱某項懲罰 → 應找出物理根本原因

**已知問題：化合物模型鑑別力不足**

Under-extract (93C/6.5/60s) 的化合物 fraction 比 Hoffman (98C/4.6/120s) 還「好看」：
- SW 0.446 > Hoffman 0.361（欠萃比正萃還甜？）
- CGA 0.049 ≈ Hoffman 0.048（欠萃和正萃一樣乾淨？）
- MEL 0.042 > Hoffman 0.034（欠萃焦苦更高？）

根本原因：`COMPOUND_BASE` 基底值佔比過大（SW base=0.42），時間/溫度/研磨修正幅度太小。
結果：壞配方和好配方的化合物 profile 幾乎相同，分數鑑別完全依靠 TDS floor。

**待實施改革路線（三階段）：**

**Phase 1 — 化合物模型修正（compounds.py + constants.py）**
- 引入 EY-gated 基底：SW/PS 等「發展型」化合物需足夠 EY 才會完整釋放
- 修正時間函數：短浸泡 + 粗研磨應顯著壓低 SW/PS
- 確保 under-extract SW fraction < Hoffman SW fraction
- CGA/MEL 在過萃時應明顯超標，欠萃時應明顯低

**Phase 2 — 評分邊際曲線（scoring.py）**
- 化合物好處邊際遞減（diminishing returns）：接近理想高報酬，超過後趨平
- 化合物壞處邊際遞增（steeper penalty）：偏離理想越多，懲罰加速
- 化合物比值評分：AC/CGA（純淨酸質）、SW/MEL（甜苦比）、PS/CA（醇厚乾淨度）
- 各比值使用獨立的加分/扣分曲線

**Phase 3 — 重新校準錨點**
- 所有 5 錨點重跑（Hoffman + April + Championship + Under + Over）
- 確認化合物物理合理性（不只看分數，看每個化合物的絕對值和比例）
- 調整 IDEAL_FLAVOR 對齊新的化合物模型預測

---

## Architecture

### Data Flow

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

### Grid Search (optimizer.py)

Iterates `temp × dial_x10 × steep × dose_x2`. For each point:
1. Compute `press_sec` via Darcy law (channeling collapse if > 60s threshold)
2. Compute EY using Arrhenius + concentration gradient model
3. Predict six compounds (AC, SW, PS, CA, CGA, MEL) at extraction conditions
4. Apply channeling correction to EY and compounds
5. Compute TDS, then `flavor_score`
6. Apply soft `dial_prefer` penalty (Gaussian, ±6% max)

Results sorted by score; top-N returned (always includes unconstrained #1).

### Six-Compound Model

| Compound | Flavor role |
|----------|-------------|
| AC | Acidity (chlorogenic-acid-derived) |
| SW | Sweetness / aroma volatiles |
| PS | Polysaccharides → body / mouthfeel |
| CA | Caffeic acid (mild bitterness) |
| CGA | Chlorogenic acid (astringency) |
| MEL | Melanoidins (roasty bitterness) |

`predict_compounds` in `models/compounds.py` models each compound as time/temp/grind functions, with pre-seal drip correction and press percolation selectivity.

### Scoring Formula (models/scoring.py)

`flavor_score = compound_reward × tds_factor × ey_factor × tds_floor_factor`

- **compound_reward**: log-ratio Gaussian — 每個化合物計算 `log(actual_perceived / ideal)` 偏差，以非對稱 sigma 衰減，加權平均後取 exp。黃金交叉在 actual = ideal（reward = 1.0）
  - `COMPOUND_SIGMA_LO`：化合物不足側（SW/PS 不足嚴懲，苦味不足寬鬆）
  - `COMPOUND_SIGMA_HI`：化合物超標側（CGA/MEL 超標嚴懲，SW/PS 超標寬鬆）
- **ideal_abs**: interpolated from `IDEAL_FLAVOR` table keyed by `(roast_code, tds_bracket)`；苦味化合物再乘 `IDEAL_BITTER_REDUCTION=0.95`
- **tds_factor**: asymmetric Gaussian around `TDS_PREFER[roast_code]` — sigma_low=0.10（太淡嚴懲），sigma_high=0.20（高濃縮寬鬆）
- **ey_factor**: Gaussian around `EY_PREFER[roast_code]` with `EY_GAUSS_WEIGHT=0.06`（過程變數，極低權重）
- **tds_floor_factor**: `min(tds / 0.80, 1)²` — TDS 低於 0.80% 連續硬懲罰

**感知前處理（物理，在評分之前）：**
- KH 壓制酸質感知：`AC × exp(−KH/150)`
- 高溫 SW 香氣損失：溫度超過 97°C 啟動，斜率 0.015/°C，上限 25%
- 高溫焦苦放大（深焙）：`SCORCH_PARAMS` per-roast 閾值
- 軟水苦味放大：GH < 20 時 CA/CGA/MEL +25%

### Key Files

| File | Role |
|------|------|
| `constants.py` | All tunable physics/flavor constants |
| `diagnose_anchor.py` | Hoffman anchor validation (run after every constants change) |
| `models/scoring.py` | Full scoring pipeline |
| `models/compounds.py` | Six-compound extraction prediction |
| `models/ey_model.py` | EY calculation |
| `models/tds_model.py` | TDS, press time, drip volume, retention |
| `optimizer.py` | Grid search engine |
| `runtime.py` | Environment settings (T_ENV, altitude, water profile) |
| `data/water_presets.py` | Named water profiles (presets) |
| `webapp.py` | Flask web interface |

### ZP6 Dial Reference

- `dial < 4.5`: fine grind (Hoffman anchor 4.3 is here)
- `dial = 4.5`: model reference point (`DIAL_BASE`)
- `dial > 4.5`: coarse grind

`dial_prefer` per roast is stored in `ROAST_TABLE` — never remove this field.

### Water Quality Parameters

Water affects scoring through three channels:
- **GH (hardness)**: controls compound extraction efficiency
- **KH (alkalinity)**: `KH_PERCEPT_DECAY=150` → suppresses perceived acidity (AC × exp(−KH/150))
- **mg_frac**: Mg²⁺ fraction boosts AC/SW, Ca²⁺ fraction boosts PS/CGA
- Soft water (GH < `LOW_GH_THRESHOLD=20`, e.g. RO) triggers extra bitter penalty

Default water when unspecified: GH=50, KH=30, mg_frac=0.40.
