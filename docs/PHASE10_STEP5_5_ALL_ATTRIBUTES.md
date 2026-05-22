# Phase 10 — Step 5.5：Layer 2 全屬性重 fit

> **狀態：完成（2026-05-22）。** Phase 10 §11 之外的插入步驟，使用者裁決後加入，排在 Step 6 之前。
> 程式：[`../models/sensory.py`](../models/sensory.py)（重 fit）、[`../data/ideal.json`](../data/ideal.json)（schema v6）、[`../models/distance.py`](../models/distance.py)。
> 上游：[`PHASE10_STEP2_LAYER2.md`](PHASE10_STEP2_LAYER2.md)（被本步驟取代的 6 軸版）、[`PHASE10_STEP5_SCORING.md`](PHASE10_STEP5_SCORING.md)。

---

## 1. 為什麼有這一步（使用者裁決）

Step 2 的 Layer 2 把 10 個 cotter CATA 欄位**分組平均成 6 個感官軸**再回歸。Step 5（評分）落地後，討論「風味互動」（body 厚壓花果香、body 低顯苦澀）時，使用者指出更乾淨的路：

> 「cotter 所有感官評分因子全部放進去自然就解決了 —— 那些資料也是人感受的。」

**核心洞見正確：** cotter 的屬性值是**消費者感受後**的偵測頻率 —— 任何跨屬性遮蔽（厚 body 蓋掉花果香）**已經發生在試飲者嘴裡、已經烤進資料**。所以只要把每個屬性直接對沖煮座標 `(TDS, EY)` 回歸，那些互動就自動跟著進來，不需要手建互動模型。又因為系統裡 body 永遠是 TDS/EY 的下游、不能獨立轉動，「系統做得出來的每一種互動」定義上都已在『屬性 vs 座標』回歸裡。

**接著的精修（使用者第二個裁決）：** 不是「全 17 個都放」—— **先跑回歸，真的有線性關係才放，沒有就砍**。

---

## 2. 回歸與 R² 閘門

對全部 17 個 cotter CATA 屬性各做一次 OLS（27 cell、每 cell 118 人；屬性強度 = cell 內偵測頻率）：

```
intensity = base + b_tds·z(TDS) + b_ey·z(EY) + b_tds2·z(TDS)²
```

`b_temp` 維持 0（Step 2 / Batali 2020：固定 TDS/EY 下溫度無感官效應）。標準化常數與 Step 2 相同（TDS μ1.2718 σ0.2137；EY μ20.3631 σ3.0248）。**Sanity：** 把同組屬性係數平均回去，與 Step 2 的 6 軸係數幾乎完全一致 → 回歸管線正確。

| 屬性 | R² | 平均偵測率 | 去留 |
|---|---|---|---|
| Sour | 0.88 | .34 | ✅ 保留 |
| Bitter | 0.82 | .32 | ✅ |
| Dark.chocolate | 0.82 | .21 | ✅ |
| Burnt | 0.80 | .18 | ✅ |
| Sweet | 0.69 | .19 | ✅ |
| Tea.floral | 0.67 | .20 | ✅ |
| Citrus | 0.62 | .18 | ✅ |
| Cereal | 0.61 | .11 | ✅ |
| Thick.viscous | 0.55 | .08 | ✅ |
| Astringent | 0.44 | .11 | ✅ |
| — 閘門 R² 0.44 / 0.32 之間有乾淨斷層 — | | | |
| Roasted | 0.32 | .45 | ❌ 砍 |
| Green.veg | 0.26 | .13 | ❌ |
| Nutty | 0.19 | .29 | ❌ |
| Rubber | 0.16 | .07 | ❌ |
| Paper.wood | 0.15 | .23 | ❌ |
| Caramel | 0.12 | .13 | ❌ |
| Fruit | 0.08 | .16 | ❌ |

**保留 10 個（R² ≥ 0.44）、砍 7 個（R² ≤ 0.32）。**

### 為什麼砍掉 7 個沒有損失風味

被砍的每一個，它的風味家族都還有一個強屬性留著：

| 砍 | 家族代表（保留） |
|---|---|
| Roasted (.32) | Burnt (.80) |
| Caramel (.12) | Sweet (.69) |
| Paper.wood (.15) | Astringent (.44) |
| Fruit (.08) | Tea.floral (.67) / Citrus (.62) |
| Nutty (.19) | Dark.chocolate (.82) / Cereal (.61) |
| Green.veg (.26)、Rubber (.16) | 無雙胞，但低訊號純雜訊 |

Nutty 是唯一的判斷題（使用者曾提想要堅果味）—— 使用者裁定**照規則砍**（堅果家族由 Dark.chocolate / Cereal 代表）。

---

## 3. 三個發現

1. **「body 厚壓花果香」被資料證實。** `Tea.floral` 的 `b_tds = −0.044`（R² 0.67）—— TDS 越高、花果香偵測率越低。兩輪前討論「跑向量證實 vs 憑感覺」的答案：是向量證實的，正向結果。
2. **平均成軸會「消滅」訊號 —— Step 2 astringency 軸 R²=0.03 是假象。** `Astringent` 自己 R²=0.44、`Paper.wood` 自己 R²=0.15；但兩者 `b_tds` **方向相反**（+0.019 vs −0.012），平均後 TDS 訊號互相抵銷 → 軸 R²=0.03。當初「astringency 不可訓練」是平均造成的，不是屬性本身的問題。
3. **有些軸的 R² 全靠單一屬性撐。** `sweetness` 軸 R²=.69 全靠 Sweet（Caramel 自己只有 .12）；`roast` 軸 R²=.67 全靠 Burnt（Roasted 自己只有 .32）。平均把訊號和雜訊混在一起。

發現 2、3 都直接驗證了「分開、別平均」的方向。

---

## 4. 新模型（`models/sensory.py`）

- `predict_attributes(tds, ey, roast, temp, dial) → {attribute: intensity}` —— 取代 `predict_axes`。
- `ATTRIBUTES` —— 10 個保留屬性（依風味家族排序）：`Sour · Citrus · Tea.floral · Sweet · Cereal · Thick.viscous · Bitter · Astringent · Burnt · Dark.chocolate`。
- `roast` / `dial` 仍為文獻方向先驗（cotter 單焙度、grind 為依變數）。`_ROAST_OFFSET` 改成 per-family、各屬性經 `_ATTR_FAMILY` 繼承。**roast offset 在焙度內會抵銷**（預測與 IDEAL 帶同一個 offset）→ 不影響焙度內推薦，只設絕對 IDEAL 數字與 placeholder。
- **`AXIS_VIEW`** —— 6 軸（+`character`）→ 屬性的歸納表，保留作**顯示 / Step 6 問卷**的視圖，**不是模型表徵**。模型表徵 = 10 屬性；6 軸只是給人看的摘要。

---

## 5. 連帶改動

| 檔案 | 改動 |
|---|---|
| `models/sensory.py` | 重 fit：6 軸 → 10 屬性。取代 Step 2 交付物。|
| `data/ideal.json` | schema v5 → **v6**：per-roast IDEAL 從 6 軸改 10 屬性向量（`predict_attributes(**anchor_brew)` 重推）。|
| `models/distance.py` | `axis_distance` → `attribute_distance`；**改成純未加權 RMS**（10 屬性）。R²≥0.44 閘門已濾掉雜訊屬性 → 保留的等權重，不需要再 per-attribute 降權。|
| `optimizer.py` / `output/*` | 接線改 `predict_attributes` / `attribute_distance`；result dict `axes` → `attributes`。|

`models/ideal.py`（`roast_ideal` / `recipe_id`）、`main.py` 不需改 —— 它們對表徵維度泛型。

---

## 6. 驗證（CLI 全通）

| 檢查 | 結果 |
|---|---|
| 各焙度 Top-1 | light dist 0.0017 / medium_light 0.0006 / medium 0.0010 / moderately_dark 0.0119（placeholder 已知略不可達）|
| 鑑別度（medium_light XL 95°C）| 好杯 0.0013 ≪ 過萃 0.062 ≪ 欠萃 0.533 —— 單調 |
| tim bracket（light）| ⭐4 0.0000 < ⭐3 0.0142 < ⭐2 0.0256 —— 仍單調。10 屬性下 ⭐2 直接顯示 Burnt 最高、Bitter 最高、Tea.floral 最低，對上「ROASTY、太濃、失去淺焙亮度」|

tim ⭐2 距離仍只 0.026（與 ⭐4 差距小）—— Layer 2 仍看不出「悶」的根因（Step 2 §7 的 cotter 欠發展象限缺口未變），但 10 屬性的方向比 6 軸更可讀。

---

## 7. 給 Step 6 的交接

- Step 6 問卷只對這 10 個屬性設計問題（使用者「真的有線性關係才放、才設計問題」）。
- 問卷不必逐一問 10 題 —— 用 `AXIS_VIEW` 把 10 屬性歸納成 ~6-7 個使用者直覺得出的群（酸/甜/body/苦/澀/焙烤 + character），問群層級;模型內部仍是 10 屬性。
- 模型表徵（10 屬性）≠ 問卷粒度（~6 群）—— 兩者解耦。

---

## 8. 參考資料

- [`PHASE10_STEP2_LAYER2.md`](PHASE10_STEP2_LAYER2.md)（被取代的 6 軸版；回歸式、標準化常數沿用）。
- [`PHASE10_STEP5_SCORING.md`](PHASE10_STEP5_SCORING.md)（距離評分、無 0–100 分）。
- cotter 資料集 `data/phase10_training/`（UC Davis，Dryad 10.25338/B8993H，CC0）。
- 係數重現：對 27 cell 各屬性做 `intensity ~ z(TDS) + z(EY) + z(TDS)²` OLS，即得 `models/sensory.py` 的 `_COEF`。
