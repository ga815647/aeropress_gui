# Phase 10 — Step 2：Layer 2 風味模型（Sensory Model）

> **狀態：完成（2026-05-21）。** Phase 10 §11 執行步驟表的 Step 2 交付物。
> 程式：[`../models/sensory.py`](../models/sensory.py)。上游：[`PHASE10_STEP1_SENSORY_AXES.md`](PHASE10_STEP1_SENSORY_AXES.md)（6 軸定案）、[`PHASE10_SENSORY_REFOUNDING.md`](PHASE10_SENSORY_REFOUNDING.md)（藍圖 §7.1）。

---

## 1. 交付物摘要

- `models/sensory.py` —— `predict_axes(tds, ey, roast, temp, dial) → 6 感官軸`。
- (TDS, EY) 響應由 **cotter 27-cell 因子網格回歸**得到（資料驅動）；`roast` / `dial` 為文獻先驗偏移；`temp` 係數證實 ≈0、設為 0。
- 模型形式 = **低階多項式回歸**（非查表）—— 理由見 §4。
- 驗證：核心 TDS/EY 趨勢全部對上文獻（§6）；湧現概念 muted / clarity 通過；**tim ⭐2/⭐4 鑑別未解 —— 已知難題,Step 2 單獨無法修,見 §7**。

---

## 2. 資料與軸對應

訓練資料：`data/phase10_training/cotter_dataset.csv`（UC Davis，Dryad 10.25338/B8993H，CC0）。3×3×3 因子網格 = 溫度(87/90/93°C) × TDS(1.0/1.25/1.5%) × PE(16/20/24%) = **27 brew cell**，每 cell ~118 位消費者的 CATA（偵測/未偵測）。

每個 6 軸的強度 = 該軸對應 CATA 屬性在 cell 內的**平均偵測頻率**：

| 軸 | cotter CATA 欄位 |
|---|---|
| `acidity` | Sour, Citrus |
| `sweetness` | Sweet, Caramel |
| `body` | Thick.viscous |
| `bitterness` | Bitter |
| `astringency` | Astringent, Paper.wood |
| `roast` | Roasted, Burnt |

軸強度單位 = CATA 偵測頻率,名目 [0,1]。label IDEAL（Step 3）與評分（Step 5）沿用同一尺度。

---

## 3. 27-cell × 6-軸 觀測表

cell 命名 `溫度-目標TDS-目標PE`；TDS/PE 為該 cell 的**實測**均值。

| cell | TDS | PE | acid | sweet | body | bitt | astr | roast |
|---|---|---|---|---|---|---|---|---|
| 87-1.0-16 | 1.04 | 16.9 | 0.19 | 0.21 | 0.00 | 0.19 | 0.18 | 0.26 |
| 87-1.0-20 | 1.01 | 20.1 | 0.19 | 0.19 | 0.05 | 0.14 | 0.17 | 0.28 |
| 87-1.0-24 | 0.98 | 23.9 | 0.22 | 0.21 | 0.03 | 0.23 | 0.16 | 0.22 |
| 87-1.25-16 | 1.27 | 16.7 | 0.34 | 0.13 | 0.03 | 0.36 | 0.17 | 0.31 |
| 87-1.25-20 | 1.29 | 20.9 | 0.22 | 0.17 | 0.08 | 0.27 | 0.20 | 0.31 |
| 87-1.25-24 | 1.24 | 23.9 | 0.21 | 0.19 | 0.08 | 0.31 | 0.18 | 0.31 |
| 87-1.5-16 | 1.50 | 16.6 | 0.36 | 0.15 | 0.05 | 0.39 | 0.20 | 0.36 |
| 87-1.5-20 | 1.46 | 19.6 | 0.33 | 0.13 | 0.12 | 0.41 | 0.13 | 0.35 |
| 87-1.5-24 | 1.47 | 23.3 | 0.25 | 0.16 | 0.13 | 0.42 | 0.20 | 0.33 |
| 90-1.0-16 | 1.01 | 16.4 | 0.20 | 0.22 | 0.05 | 0.24 | 0.17 | 0.28 |
| 90-1.0-20 | 1.05 | 20.8 | 0.20 | 0.19 | 0.06 | 0.21 | 0.14 | 0.30 |
| 90-1.0-24 | 0.95 | 22.8 | 0.11 | 0.19 | 0.08 | 0.21 | 0.14 | 0.24 |
| 90-1.25-16 | 1.27 | 16.6 | 0.31 | 0.18 | 0.07 | 0.32 | 0.16 | 0.29 |
| 90-1.25-20 | 1.31 | 21.0 | 0.29 | 0.11 | 0.06 | 0.37 | 0.14 | 0.35 |
| 90-1.25-24 | 1.29 | 24.5 | 0.19 | 0.12 | 0.06 | 0.34 | 0.17 | 0.39 |
| 90-1.5-16 | 1.58 | 17.5 | 0.42 | 0.15 | 0.15 | 0.34 | 0.19 | 0.25 |
| 90-1.5-20 | 1.49 | 20.0 | 0.28 | 0.15 | 0.15 | 0.42 | 0.19 | 0.37 |
| 90-1.5-24 | 1.48 | 23.7 | 0.22 | 0.12 | 0.07 | 0.38 | 0.20 | 0.40 |
| 93-1.0-16 | 1.01 | 16.2 | 0.22 | 0.19 | 0.03 | 0.19 | 0.20 | 0.21 |
| 93-1.0-20 | 1.01 | 20.6 | 0.19 | 0.19 | 0.04 | 0.19 | 0.15 | 0.28 |
| 93-1.0-24 | 1.02 | 24.3 | 0.14 | 0.17 | 0.05 | 0.19 | 0.19 | 0.31 |
| 93-1.25-16 | 1.32 | 17.1 | 0.34 | 0.14 | 0.08 | 0.29 | 0.18 | 0.38 |
| 93-1.25-20 | 1.33 | 21.0 | 0.30 | 0.12 | 0.08 | 0.38 | 0.17 | 0.30 |
| 93-1.25-24 | 1.23 | 23.1 | 0.22 | 0.11 | 0.10 | 0.42 | 0.21 | 0.36 |
| 93-1.5-16 | 1.59 | 16.3 | 0.44 | 0.11 | 0.11 | 0.46 | 0.18 | 0.33 |
| 93-1.5-20 | 1.51 | 20.0 | 0.36 | 0.15 | 0.13 | 0.41 | 0.12 | 0.39 |
| 93-1.5-24 | 1.63 | 25.9 | 0.28 | 0.17 | 0.11 | 0.41 | 0.17 | 0.39 |

---

## 4. 模型形式與決策

### 4.1 回歸式

每軸：標準化預測子（z-score，對 cotter 均值/標準差）後 OLS：

```
intensity = base + b_tds·z(TDS) + b_ey·z(EY) + b_tds2·z(TDS)² + b_temp·z(temp)
          + roast_offset[roast] + grind_slope·(DIAL_REF − dial)
```

標準化常數（cotter）：TDS μ=1.272 σ=0.214；EY μ=20.36 σ=3.02；temp μ=90 σ=2.45。

| 軸 | base | b_tds | b_ey | b_tds2 | R² |
|---|---|---|---|---|---|
| acidity | 0.260 | **+0.061** | **−0.041** | +0.000 | 0.84 |
| sweetness | 0.142 | −0.020 | −0.003 | +0.018 | 0.68 |
| body | 0.072 | +0.027 | +0.005 | +0.004 | 0.56 |
| bitterness | 0.337 | **+0.081** | +0.007 | −0.022 | 0.83 |
| astringency | 0.175 | +0.003 | −0.002 | −0.002 | **0.03** |
| roast | 0.337 | +0.035 | +0.015 | −0.022 | 0.67 |

### 4.2 決策一：回歸,不查表（藍圖 §7.1 留的選擇）

選**低階多項式回歸**。理由：
- 27 個 cell 是消費者 CATA,帶噪。查表會把噪音一起記住 —— `astringency` R²=0.03（純噪音）若做成查表,等於把噪音當訊號。
- 回歸的平滑外推（單調 + 飽和）合理;查表在格點外無定義。
- 符合 CLAUDE.md 原則 #1（平滑連續函數）。

### 4.3 決策二：`b_temp` 設為 0

cotter 雖有溫度因子,但 6 軸對 temp 的擬合係數全部 |b_temp|≤0.011 —— 噪音等級,與 **Batali 2020 的結論一致**（固定 TDS/EY 下溫度對風味無影響）。錨點低至 80°C（Champion）遠在 cotter 87–93°C 之外,外推一個噪音級係數只會放大噪音。故 `b_temp` 一律設 0;`temp` 參數保留在簽名,目前不動任何東西。

### 4.4 決策三：`roast` / `dial` 為文獻先驗,非擬合

cotter 是**單一焙度**、且 grind 是「調去命中目標 TDS/EY」的依變數 —— 兩者都不是 cotter 的獨立因子,無法回歸。
- **`roast`**：以 cotter 焙度為 `medium` 參考（offset 0）。Guinard 2023 BCC 發現焙度是最大的感官效應:越淺 → 越亮（酸/甜↑）、越不苦/不焙烤。`_ROAST_OFFSET` 依此方向、量級設得與 (TDS,EY) 跨度相當（~±0.1），標為**先驗**,待 feedback 精修。
- **`dial`**：最弱的項,只給 body / astringency 小幅修正,`dial=None` 時整段跳過。

> 藍圖 §4 把 `roast` 列為主軸 —— 但本系統手上的 cotter 無法訓練它（單焙度）。Guinard 三焙度 raw 資料未公開（Step 1 §9）。故 `roast` 暫時是「主軸的方向、先驗的量級」,是 feedback 第一個該修的東西。

---

## 5. 模組介面

```python
from models.sensory import predict_axes, SENSORY_AXES

predict_axes(tds, ey, roast="medium_light", temp=90.0, dial=None) -> dict
# 回傳 {axis: intensity}，axis 依 SENSORY_AXES 順序
# intensity = CATA 偵測頻率，名目 [0,1]，未 clamp（純多項式，遠外推可能略出界）
```

`SENSORY_AXES = (acidity, sweetness, body, bitterness, astringency, roast)` —— 下游 labels.json（Step 3）、scoring（Step 5）一律跟此順序。

---

## 6. 驗證

### 6.1 單調掃描（medium_light，EY 20，溫度 inert）

| TDS | acid | sweet | body | bitt | roast |
|---|---|---|---|---|---|
| 1.0 | 0.222 | 0.217 | 0.034 | 0.162 | 0.195 |
| 1.2 | 0.279 | 0.171 | 0.053 | 0.271 | 0.261 |
| 1.4 | 0.337 | 0.157 | 0.079 | 0.342 | 0.288 |
| 1.6 | 0.394 | 0.175 | 0.113 | 0.374 | 0.278 |

`acidity` / `bitterness` / `body` 隨 TDS 單調↑、`sweetness` 隨 TDS↓（高端因二次項微回升）—— **全部對上文獻**（Batali：sour/bitter/viscous ↑TDS；Guinard：sweet ↓TDS）。`roast` 在 TDS 1.6 微降 0.01（飽和二次項輕微過衝）—— 極端端點的小瑕疵,可接受。

### 6.2 錨點（medium_light）

| 錨點 | TDS/EY | acid | sweet | body | bitt | roast |
|---|---|---|---|---|---|---|
| April | 1.17/18 | 0.298 | 0.178 | 0.046 | 0.252 | 0.243 |
| Hoffman | 1.23/21 | 0.274 | 0.166 | 0.058 | 0.286 | 0.272 |
| Hedrick | 1.52/19 | 0.385 | 0.165 | 0.097 | 0.363 | 0.282 |
| Champion | 1.56/18 | 0.410 | 0.171 | 0.102 | 0.366 | 0.273 |

`bitterness` / `body` 隨 TDS 單調 ✓。April 酸質 > Hoffman 雖 TDS 較低 —— 因 April EY 18 < Hoffman EY 21,acidity↓EY,正確 ✓。

### 6.3 湧現概念（Step 1 §7 的驗收）

- **muted**：低 TDS(0.98)/低 EY 杯 6 軸總和 0.93 < 在標杯 1.43 —— 萃取不足把全軸壓低 ✓。
- **roast 軸**：同 (TDS,EY) 下 medium_light=0.31 > light=0.25 —— 淺焙焙烤感較低 ✓。
- **clarity**：低 astringency + 低 roast 的杯 = 乾淨,由三負向軸湧現（待 Step 5 評分驗收）。

---

## 7. 已知限制 —— tim ⭐2/⭐4 鑑別未解（重要）

tim 三杯（淺焙）餵進 Layer 2：

| tim 杯 | TDS/EY | acid | bitt | roast | 使用者評語 |
|---|---|---|---|---|---|
| ⭐4 | 1.45/20.4 | 0.381 | 0.319 | 0.231 | 淺焙酸+茶感、乾淨 |
| ⭐3 | 1.39/20.5 | 0.362 | 0.305 | 0.230 | 偏薄、香味淡 |
| ⭐2 | 1.50/18.6 | 0.420 | 0.325 | 0.221 | ROASTY、失去淺焙特色、太濃 |

`bitterness` 把 ⭐2 排最高（對上「太濃」）—— 部分正確。但 **`roast` 軸把 ⭐2 排最低**,與使用者「ROASTY」的描述相反。

**根因（誠實說明）：** cotter 是單一中焙、`Roasted/Burnt` CATA 在其 TDS 範圍只隨 TDS 微升並飽和。使用者那杯 28g 高劑量淺焙「烤感/無趣」其實是 **高 TDS + 低 EY 的「濃而萃取不足」象限**（SCA under-developed）—— 一種「悶、生、失去花果亮度」的味道。cotter 沒有這種樣本,Layer 2 無從學到。

**使用者已確認（2026-05-21）：** 他說的「roasty」是**相對於同樣淺焙**而言 —— 不是 `roast` 軸（roasted/smoky/burnt 是深焙描述語）。意思是「相對其他淺焙杯,這杯悶、平、失去淺焙亮度」。因此 ⭐2 的壞並非「`roast` 軸偏高」,而是**萃取不足導致的低亮度/低 clarity**:對應到 6 軸應是 sweetness 偏低 + clarity 差（低 astringency 但整體 muddy）+ 失去酸質的「明亮」質感。這是 Step 3 寫 tim label IDEAL、Step 5 評分時要把握的方向。

**這不是 Step 2 能單獨修的。** 對應 [`project_tim_calibration`] 記憶裡早寫的「tim bug root NOT isolated；需要受控的單一變數（dose-only）對照組」。處置：
- 不在 Layer 2 硬塞非 cotter 支持的項（會違反「Layer 2 是 fit 出來、非手刻」原則）。
- 交給 Step 3（tim label IDEAL）+ Step 5（評分）+ feedback 精修。
- 若仍無法區分「乾淨有茶感的淺焙杯」vs「悶而無趣的淺焙杯」,即 Step 1 §6 watch-list 所指 —— 屆時才考慮第 7 軸或一個 under-developed 交互項。

---

## 8. 給 Step 3 的交接

1. `predict_axes()` 可直接餵錨點的 (TDS, EY, roast) → 得 6 軸向量 → 即該 label 的新 IDEAL（藍圖 §7.3 流程）。
2. label IDEAL 改用 6 軸 key（`SENSORY_AXES` 順序）取代舊 6 化合物分率。
3. `tds_prefer` 預期被吸收（藍圖 §7.2）：能產生該 6 軸 IDEAL 的 TDS 自然就是偏好 TDS。
4. 先驗項（`_ROAST_OFFSET`、`_GRIND_SLOPE`）是 feedback 第一順位精修對象。
5. tim label：§7 的限制 —— tim 的 IDEAL 不能只靠 ⭐4 杯反推,要結合使用者「乾淨/茶感」的定性描述。

---

## 9. 參考資料

- cotter 資料集 README：`data/phase10_training/README.md` / `README.txt`。
- Batali et al. 2020 — 溫度無感官效應（→ b_temp=0 的依據）。
- Guinard et al. 2023 — BCC，焙度是最大感官效應（→ `_ROAST_OFFSET` 方向）。
- 回歸分析、係數擬合：本文件 §3–§4 即完整紀錄,`models/sensory.py` 內嵌同一組數字。
