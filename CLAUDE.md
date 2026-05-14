# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 待辦任務

見 [`TASKS.md`](TASKS.md)。

**已完成（2026-04-12）：** Phase 1（化合物模型修正，引入 `SW_DIAL_COEFF`）、Phase 2（評分邊際曲線 + 比值評分 + `ACCEL_W_PER_COMPOUND` 加速懲罰）、Phase 3（錨點重新校準，IDEAL_CGA 0.05→0.057、`CGA_ASTRINGENCY_THRESHOLD` 1.25→1.15）。

**已完成（2026-04-25）：** 焙度錨點重貼標。經查證 Hoffmann/El Tambo (Agtron 65-75) 實際是 **medium-light**（不是淺焙）；過去整套 Hoffmann 校準掛在 `light` 槽屬於誤標。已將 Hoffmann 校準參數（`EY_PREFER`/`TDS_PREFER`/`ROAST_TABLE`/`IDEAL_FLAVOR`/`COMPOUND_BASE`/`EY_SIGMA_*`）整體搬到 `medium_light`，新 `light` 槽改填 Nordic 真淺焙暫定值（`base_temp=99`、`dial_prefer=4.0`、`TDS_PREFER=1.30`、`dose_per_100ml=(5.5, 7.5)`），`diagnose_anchor.py` 五錨點 roast key 改為 `medium_light`。五錨點現況：Hoffman 94.6 / April 90.0 / Championship 69.8 / Under 0.0 / Over 35.2。

**已完成（2026-05-13）：** Phase 4 — 粗磨+長浸泡象限校準。原 CGA(time) 與 AC decay 速率/起始時間都跟研磨粗細無關，導致「粗+長」象限被誤判為 AC 流失 + CGA 暴增（過萃）。引入 `GRIND_KINETICS_COEFF=0.40`，讓 `K_AC_DECAY` / `AC_DECAY_START` / `K_CGA_TIME` / `CGA_TIME_ONSET` 同時隨研磨耦合（粗磨 → 起始延後、速率減緩，符合 Fuller & Rao 2017 first-order + plateau）。新增 Hedrick/Gagne 第六錨點（dial 6.0 / 14g / 95°C / 240s / target AC > CGA, score ≥ 55）驗證粗+長象限。同時加入 Top N 多樣化（`TOP_DIVERSITY_DIAL_MIN/STEEP_MIN/DOSE_MIN`）讓 Top 列表呈現「Hoffman 風 / 長浸泡 / 粗磨 / 多豆量」多樣代表，diagnose_anchor 傳 `diversify_top=False` 保留錨點驗證緊密性。六錨點全 PASS；over-extract 分數從 35→12（細磨長浸泡懲罰加重）。

**已完成（2026-05-13）：** Phase 4b — SW/PS 時間發展鑑別。原 `SW_TIME_FLOOR=PS_TIME_FLOOR=0.50` 太寬鬆，導致 60s 短浸泡跟 120s 完整浸泡的甜感/醇厚差距只有 ~17%（過萃 indistinguishable from 正萃）。降至 `0.30` 同時提速 `K_SW: 0.010→0.014` / `K_PS: 0.008→0.012`（讓 90-120s 仍接近平台，只懲罰 <60s 真短時）。效果：dose=22g/dial 4.3/60s 從 91.4 降到 84.5；Top 列表 Rank 2 不再是 60s 欠萃，而是 dial 4.7/180s 的正萃替代。六錨點仍全 PASS（Championship 100s/80°C 因 K 提速恰好補回 PS 損失）。

**已完成（2026-05-13）：** Phase 5 lite — grind-dependent EY deficit penalty。原評分 `EY_GAUSS_WEIGHT=0.0` 完全不看 EY，導致細磨高豆量 + EY 偏低 1-2%（如 dial 4.6/23g/120s/95°C，EY 19.2% vs target 21%）的「mild under-extraction」被誤判為高分（96.9）。新增 `GRIND_EY_DEMAND_K=10.0` / `EY_DEMAND_WEIGHT=0.30`：以 sigmoid 在 `DIAL_BASE=4.5` 為中心，細磨（dial<4.5）線性轉成 EY 嚴格要求，粗磨（dial>4.5）線性豁免；EY deficit 用 softplus(k=5) 平滑單側懲罰。效果：dial 4.6/23g 從 96.9→86.3（拉開 10 分），Hoffman 4.4/22g 從 96.0→95.4（幾乎不變），April/Champion/Hedrick 因粗磨完全豁免。`flavor_score` 簽名新增 `dial` 參數，已串接 optimizer.py 與 diagnose_anchor.py。**注意 CLAUDE.md「EY 不得作為主要扣分依據」原則 — 此懲罰僅在細磨象限觸發、單側（只懲罰不足）、最大扣分 ~25%（不主導）。**

**已完成（2026-05-13）：** Phase 5 lite+ — TDS-EY mismatch 懲罰（「低 TDS + 高 EY」象限）。Phase 5 lite 是單側懲罰，沒處理「dose 過瘦 → 必須過萃補 TDS」這個 TASKS.md 早記錄的「SCA under-concentrated 象限：酸感集中、澀鹹、無香」。用戶實測 dial 4.3 / 20g / 120s / 96°C / EY 22.0% / TDS 1.22% 模型給 95.1 分。新增 `TDS_EY_MISMATCH_WEIGHT=2.0` / `TDS_EY_MISMATCH_K=10.0`：`softplus(ey - ey_prefer) × softplus(tds_prefer - tds)` 雙條件 AND-gated（任一不滿足則 mismatch ≈ 0）。**參數選擇基於文獻（Frost & Ristenpart 2020 — TDS-酸質線性連續、非閾值）**：k=10 較平滑符合 gradient 感知，不為保護 Hoffman 經典分數而提高銳度。效果：用戶 20g 案例 95.1→77.9（拉開 17 分），Hoffman 最佳 95.4 基本不變，Hoffman 經典 95.8→92.3（略過 TDS_PREFER 誠實扣分），Phase 5 lite 案例（4.6/23g）86.3 不受影響。

**已完成（2026-05-13）：** Phase 5 full — IDEAL_FLAVOR + COMPOUND_BASE 文獻校準。`IDEAL_FLAVOR["medium_light"]` 三 bracket 改為文獻對齊值（mid: AC 15 / SW 40 / **PS 16** / CA 7 / **CGA 12** / **MEL 10**；low/high 對稱微調）；同步反推 `COMPOUND_BASE["medium_light"]` = (AC 0.123, SW 0.494, PS 0.146, CA 0.070, CGA 0.091, MEL 0.076)（從 Hoffman 實測動力學乘子 AC 1.116/SW 0.736/PS 0.996/CA 0.911/CGA 1.194/MEL 1.185 back-solve）；三個 ratio 閾值同步更新（`AC_CGA_RATIO_IDEAL`: 2.0→1.25、`SW_BITTER_RATIO_IDEAL`: 3.0→1.82、`PS_CA_RATIO_IDEAL`: 2.0→2.29）。PS 從主要 indicator 降為中等：`WEIGHTS["PS"]`: 2.0→1.3、`COMPOUND_SIGMA_LO["PS"]`: 0.15→0.25。診斷錨點重新校準：`CGA_ASTRINGENCY_THRESHOLD`: 1.15→1.10（IDEAL_CGA 升 2× 使比值天然下降），Championship `PS+SW` 閾值 0.40→0.35（PS base 砍半使絕對值下降）。**驗證：Hoffman 化合物 profile 落在新 IDEAL ±0.1pp（15.16 / 39.82 / 16.05 / 7.04 / 11.99 / 9.93）**。六錨點分數：Hoffman 92.9 / April 80.1 / Championship 56.4 / Under 0 / Over 11.5 / Hedrick 95.7（全 PASS）；Phase 5 lite 機制（EY=19.2 deficit fine grind 84.2 / coarse 94.5）與 Phase 5 lite+ 機制（TDS=1.22+EY=22 mismatch 78.4）均保留；11 pytest PASS。

**僅剩待辦（交接，詳見 [TASKS.md](TASKS.md)）：**
- **Phase 6 — 化合物模型純物理化（❌ 大重構，未完成）** — 用戶實測 98°C/4.4/90s/22g「酸澀重」但 model 給 94.1 分；根因為 `compounds.py` 內部多個非物理 gate（`SW_TIME_FLOOR=0.30`、`CGA_TIME_ONSET=150`、`AC_DECAY_START=150`、`MEL_TIME_ONSET=80`、tent function、softplus 溫度閾值）讓化合物預測「過早平台」、喪失 90s vs 120s 鑑別力。Phase 6 拆掉所有非物理 gate，改純 Arrhenius × 一階反應；走 CLAUDE.md 新原則 #4「化合物層純連續、感官層留閾值」。預估 5-8 輪錨點迭代。完整清單見 TASKS.md「Phase 6」。
- UI — Chip 標籤重寫（Phase 1-3 已完成、Phase 5 full IDEAL 對齊文獻後可進行）
- `light` 槽真淺焙錨點待補（目前用 `very_light` IDEAL_FLAVOR 暫頂；找到 Nordic-style AeroPress 食譜後校準）

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

**注意：Hoffmann/April/Championship 三錨點現掛在 `medium_light` 槽**（El Tambo 實際 Agtron 65-75 = 中淺焙）。`light` 槽留給 Nordic 真淺焙，與 Hoffmann 校準無關。

| 參數 | Hoffman 實測值 | 模型目標 |
|------|--------------|---------|
| TDS | 1.23%（稍粗）→ 原版 ~1.27% | TDS_PREFER["medium_light"] = 1.27 |
| EY | 20–22% | EY_PREFER["medium_light"] = 21.0 |
| 研磨 | 450–600µm EK43 → ZP6 dial ≈ 4.3 | dial_prefer["medium_light"] = 4.3 |
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

來源：2022 年文章《Brewing for Balance, Acidity, or Sweetness》，使用哥倫比亞 El Tambo 水洗豆（Agtron 65-75，Square Mile filter style，**對應本系統 `medium_light` 焙度槽**——早期版本誤標 `light` 已修正）。

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

**四條不可違反的架構原則：**

1. **禁止 min/max/if-else 硬斷點** — 物理世界是連續的。所有閾值、天花板、地板必須用平滑連續函數：
   - `max(x - threshold, 0)` → softplus 或 sigmoid gate
   - `min(x, cap)` → sigmoid saturation
   - `if x > threshold` → sigmoid transition
   - 不對稱 sigma → 平滑混合公式，不用 if/else
   - 例外：純離散邏輯（inverted=True/False）不在此限

2. **所有錨點用同一個評分公式** — April 和 Championship 必須通過 `flavor_score()` 得到高分，不允許用獨立的 `_anchor_cosine_score()`。如果一個評分系統無法同時獎勵 Hoffman 的均衡、April 的酸質、Championship 的甜醇，那是評分系統的問題，不是用特例繞過的理由。

3. **化合物模型必須自我鑑別** — 好喝的配方（Hoffman/April/Championship）的化合物 profile 進入評分公式後自然高分。難喝的配方（欠萃/過萃）的化合物 profile 自然低分。不需要靠 TDS floor 或 EY floor 來區分好壞 — 化合物信號本身就應該承載這個資訊。

4. **化合物層純連續物理；感官層允許閾值（嚴格二層分工）** — 物理化學是連續的，人類感知有閾值。兩者必須分層、不互相污染：
   - **化合物層 (`compounds.py`)**: **純連續物理動力學** — Arrhenius 速率 × 一階反應，從 t=0 連續到 t=∞、從 0K 到任何溫度全域可微。**禁止**：onset 時間（如 `CGA_TIME_ONSET=150`）、time floor（如 `SW_TIME_FLOOR=0.30`）、tent function（如 `1 - abs(temp - optimal)`）、softplus 溫度閾值（如 `softplus(temp - 92)`）— 即使數學上平滑，這些都是「閾值化偽裝」，不符合分子萃取物理（沒有臨界溫度才開始萃取的化合物）。
   - **感官層 (`scoring.py`)**: **sigmoid / softplus / Gaussian 可用** — 人類感知本來就有閾值（Weber-Fechner law、剛察覺/辨識/不適 thresholds）。合法的閾值化感知層成員：`SW_AROMA_THRESH`（高溫香氣熱失感知）、`SCORCH_PARAMS`（焦苦感知）、`TDS_FLOOR_MID`（水感閾值）、`KH_FLOOR`（KH 壓制酸質感知）。
   - **違反此原則的代價：** 化合物模型失去自我鑑別力（→ 違反原則 #3）→ 不同口感的配方產出相似化合物 profile → 評分只能靠 process-variable 後置 gate 補救（如 `acid_trap = sigmoid(temp - 96) × sigmoid(120 - steep)`）→ 這種補丁是症狀治療，根因仍在 compounds.py 內部的非物理 gate。

**原則 #1 vs #4 的關係（不衝突，是層次補強）：**

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

### 三食譜各自「分數不低」的物理原因

| 錨點 | 為何分數不低 | 關鍵信號 |
|------|------------|---------|
| Hoffman | 化合物 log-ratio 偏差小，TDS=1.27–1.35% 接近 TDS_PREFER=1.27 | compound_reward 接近 1.0；tds_factor 接近 1.0 |
| April | AC > CGA 且 AC > MEL（純淨酸質）；TDS=1.17% 在 SCA 範圍 | 以 ACIDITY_IDEAL + TDS_prefer=1.17 的 cosine 評分（獨立公式） |
| Championship | SW+PS > 0.70；SW > MEL/CGA（甜感主導）；TDS=1.56% 高濃縮 | 以 SWEETNESS_IDEAL + TDS_prefer=1.56 的 cosine 評分（獨立公式） |

April 和 Championship 在 `diagnose_anchor.py` 使用各自的 `ACIDITY_IDEAL`/`SWEETNESS_IDEAL` 及對應的 `TDS_prefer`，這**不是偷吃步**——而是正確地以「該食譜的目標風格」作為評分基準。高濃縮配方（Championship TDS=1.56%）不應被主力 TDS_PREFER=1.27 的 Gaussian 嚴懲，因為高濃縮下化合物品質本身仍優秀。

### 評分鑑別度改革紀錄（已完成）

1. **score_to_display** = raw × 100（線性映射，無 CDF）
2. **log-ratio Gaussian compound_reward**（取代舊 cosine_sim + conc_score）
3. **TDS Super-Gaussian 不對稱**：`TDS_GAUSS_SIGMA_LOW=0.15`、`TDS_GAUSS_SIGMA_HIGH=0.65`、`TDS_SUPER_GAUSS_EXP=4`（平頂寬容區，平滑混合斜率 `TDS_SIGMA_BLEND_K=5.0`）
4. **EY 完全退出評分**：`EY_GAUSS_WEIGHT=0.0`（EY 是過程變數；化合物模型已通過時間/溫度/研磨敏感度間接反映萃取程度）
5. **化合物比值獎勵**（`scoring.py`）：AC/CGA、SW/(MEL+CGA)、PS/CA — sigmoid 加分曲線，最多降 15% compound_loss（`RATIO_WEIGHT=0.15`）
6. **苦澀超標加速懲罰**：`ACCEL_W_PER_COMPOUND` 對 CGA(0.20)/MEL(0.15) 啟動，超過 `PENALTY_ACCEL_THRESHOLD=2.5` 後 softplus 加速
7. **TDS floor 改 sigmoid**：`1 / (1 + exp(-K(tds - MID)))`，`TDS_FLOOR_MID=0.50, K=8.0`（取代舊 `min(tds/0.80, 1)²`，全域連續可導）
8. **Phase 1 SW 研磨敏感度**：`SW_DIAL_COEFF=0.10`（log-線性，每 dial 單位 10%；細研磨 → 接觸面積大 → 香氣揮發物多）— 不用 EY-gate，避免因果倒置
9. **Phase 3 IDEAL_CGA 校準**：0.05→0.057 對齊 Hoffman 實測 CGA_frac≈0.064；AC 同步下調維持 sum=1.0
10. **禁止**為了讓某錨點通過而削弱某項懲罰 → 必須找出物理根本原因

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

`predict_compounds` in `models/compounds.py` models each compound as time/temp/grind functions, with pre-seal drip correction and press percolation selectivity. SW 額外乘上 `exp(SW_DIAL_COEFF * (DIAL_BASE - dial))`（細研磨增強香氣），確保短浸泡 + 粗研磨 SW fraction < Hoffman SW fraction（鑑別欠萃 vs 正萃）。

### Scoring Formula (models/scoring.py)

`flavor_score = compound_reward × tds_factor × tds_floor_factor`（EY 不進評分，`EY_GAUSS_WEIGHT=0.0`）

- **compound_reward**: log-ratio Gaussian — 每個化合物計算 `log(actual_perceived / ideal)` 偏差，以非對稱 sigma 衰減，加權平均後取 exp。黃金交叉在 actual = ideal（reward = 1.0）
  - `COMPOUND_SIGMA_LO`：化合物不足側（SW/PS 0.15 嚴懲，苦味 0.80 寬鬆）
  - `COMPOUND_SIGMA_HI`：化合物超標側（CGA 0.18 / MEL 0.25 嚴懲，SW/PS 0.60 寬鬆）
  - `WEIGHTS = {AC:1.0, SW:1.8, PS:2.0, CA/CGA/MEL:1.3}`
  - **比值獎勵**（降 compound_loss）：AC/CGA、SW/(MEL+CGA)、PS/CA 三個 sigmoid 加分，加權後最多降 `RATIO_WEIGHT=0.15`
  - **加速懲罰**：`ACCEL_W_PER_COMPOUND[CGA]=0.20`、`[MEL]=0.15`，超過 `PENALTY_ACCEL_THRESHOLD=2.5` 後 softplus 加速
- **ideal_abs**: 從 `IDEAL_FLAVOR` 表以 `(roast_code, tds_bracket)` Gaussian 內插（`IDEAL_INTERP_SIGMA=0.15`）；苦味化合物再乘 `IDEAL_BITTER_REDUCTION=0.95`
- **tds_factor**: 不對稱 Super-Gaussian（exp=4 平頂）— `TDS_GAUSS_SIGMA_LOW=0.15`（太淡）、`TDS_GAUSS_SIGMA_HIGH=0.65`（高濃縮寬鬆），sigmoid 平滑混合 `TDS_SIGMA_BLEND_K=5.0`
- **tds_floor_factor**: sigmoid `1 / (1 + exp(-TDS_FLOOR_K × (tds - TDS_FLOOR_MID)))`（`MID=0.50, K=8.0`），全域連續可導，取代舊 `min(tds/0.80, 1)²`

**感知前處理（物理，在評分之前）：**
- KH 壓制酸質感知：`AC × (KH_FLOOR + (1 - KH_FLOOR) × exp(−KH / KH_PERCEPT_DECAY_SMOOTH))`，`KH_FLOOR=0.65`、`KH_PERCEPT_DECAY_SMOOTH=42.0`（kh=30 → factor≈0.82；kh→∞ 漸近 0.65）
- 高溫 SW 香氣損失：sigmoid 中心 `SW_AROMA_THRESH=97°C`，上限 `SW_AROMA_CAP=0.25`，斜率 `SW_AROMA_SIGMOID_K=3.0`
- 高溫焦苦放大（深焙）：`SCORCH_PARAMS` per-roast 閾值，softplus 平滑（`SCORCH_SOFTPLUS_K=0.5`）
- 軟水苦味放大：GH→0 時 CA/CGA/MEL ×(1+0.25)，sigmoid 過渡（`LOW_GH_THRESHOLD=20`、`GH_SOFT_SIGMOID_K=0.3`）
- 低溫萃取補正（K_factor）：`temp_initial < K_LOW_TEMP_FLOOR=87°C` 時飽和補正最高 4×（April 85°C / Championship 80°C 觸發）

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
- **KH (alkalinity)**: 平滑公式 `KH_FLOOR=0.65 + 0.35 × exp(−KH / KH_PERCEPT_DECAY_SMOOTH=42.0)` 壓制酸質感知（舊常數 `KH_PERCEPT_DECAY=150` 已棄用）
- **mg_frac**: Mg²⁺ fraction boosts AC/SW, Ca²⁺ fraction boosts PS/CGA
- Soft water (GH < `LOW_GH_THRESHOLD=20`, e.g. RO) triggers extra bitter penalty

Default water when unspecified: GH=50, KH=30, mg_frac=0.40.
