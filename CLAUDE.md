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
| EY | 19.9% | EY_PREFER["light"] = 19.0 |
| 研磨 | 450–600µm EK43 → ZP6 dial ≈ 4.3 | dial_prefer["light"] = 4.3 |
| 水溫 | 97.8°C（208°F） | 搜尋範圍 93–99°C，已涵蓋 |
| 浸泡 | 2:30 開始壓 → 模型 steep=135s 或 150s | 兩者等效，Top 10 需含其一 |

### 常數修改方向參考

| 口感症狀 | 可能方向 | 注意 |
|---------|---------|------|
| 太苦 | 降低 CGA_ASTRINGENCY_SLOPE、MEL_BITTER_COEFF | 確認 Top3 TDS 不下移 |
| 酸不足 | 調整 IDEAL_FLAVOR AC 比例、降低 KH_PERCEPT_DECAY | 確認 EY 不過高 |
| 太澀 | 降低 CGA_ASTRINGENCY_SLOPE 或 HARSHNESS_SLOPE | 確認 135s 仍在 Top 10 |
| 甜感弱 | 調高 IDEAL_FLAVOR SW 比例、檢查 SW_AROMA_THRESH | 確認不影響 AC/SW 比例 |
| 醇厚不足 | 調整 EY_PS_EXP、EY_PREFER | 確認 EY_PREFER 不低於 18.5 |
| 太濃 | 降低 TDS_PREFER（謹慎：不低於 1.20） | 確認 Hoffman EY 18–22% |
| 太淡 | 提高 TDS_PREFER | 確認不超過 1.35 |

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

`flavor_score = cosine_sim × conc_score × balance_penalties × tds_factor × cga_astringency × harshness × ey_factor × uneven_penalty × ...`

- **cosine_sim**: weighted cosine between `actual_perceived` and `ideal_abs` vectors
- **ideal_abs**: interpolated from `IDEAL_FLAVOR` table keyed by `(roast_code, tds_bracket)`
- **conc_score**: Huber-loss penalty on per-compound concentration deviation
- **tds_factor**: Gaussian penalty around `TDS_PREFER[roast_code]` (asymmetric σ)
- **cga_astringency**: triggers when `cga_ratio > CGA_ASTRINGENCY_THRESHOLD (1.25)`
- **ey_factor**: Gaussian penalty around `EY_PREFER[roast_code]` (asymmetric σ)
- **uneven_penalty**: shallow-roast short-steep (<120s) penalty

Perceived compounds are adjusted for: KH acid suppression, high-temp SW aroma loss, slurry-temp scorch (CGA/MEL amplification for dark roasts), soft-water bitter amplification.

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
