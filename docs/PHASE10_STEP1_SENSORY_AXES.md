# Phase 10 — Step 1：感官軸定案（Sensory Axes Finalized）

> **狀態：完成（2026-05-21）。** 本文件是 Phase 10 §11 執行步驟表的 Step 1 交付物。
> 上游藍圖：[`PHASE10_SENSORY_REFOUNDING.md`](PHASE10_SENSORY_REFOUNDING.md)。
> Step 1 的任務是「整理 BCC 屬性表、定案 6 感官軸」。本文件鎖定 6 軸，Step 2 起不再更動軸的定義。

---

## 1. 交付物摘要

- **6 感官軸已定案、鎖定**：`acidity` / `sweetness` / `body` / `bitterness` / `astringency` / `roast`。
- **第 6 軸 = `astringency`**（不是 `clarity`）—— 使用者裁決，理由見 §5。
- **不加第 7 軸 `aroma-character`** —— 茶感/花果香是 TDS/EY 空間裡的「位置」，由 6 軸隱含表達，理由見 §6。
- **三個非軸概念被明確區分**：`clarity`（乾淨度）、`muted`（香味淡 / 低香氣強度）、`aroma-character`（茶感/花香）—— 三者**互不相同**，各有獨立的「從 6 軸湧現」路徑，見 §7。
- Dryad 原始資料目前**無法程式化下載**（資料集存在但不可檢視）；不影響 Step 1，但 Step 2 需處理，見 §9。

---

## 2. 調查的文獻來源

| 代號 | 研究 | 方法 | 屬性數 | 用途 |
|---|---|---|---|---|
| **BCC** | Guinard et al. 2023, *A new Coffee Brewing Control Chart*（J Food Sci 88(5):2168–2177）| drip，3×3×3 因子（TDS 1.0/1.25/1.5%；PE 16/20/24%；roast light/medium/dark）| Sensory BCC + Consumer BCC | (TDS,EY)→感官 的因子網格骨架 |
| **TEMP** | Batali et al. 2020, *Brew temperature … has little impact …*（Sci Rep s41598-020-73341-4）| drip，固定 TDS/EY，溫度 87/90/93°C | **31** | 完整 TDS/PE 相關性符號表；溫度次要軸上界 |
| **IMM** | Sci Rep 2024, *Sensory analysis … full immersion … over time*（PMC11335879）| 全浸泡，2 roast × 3 溫度（4/22/92°C）× 5 時間點 = 30 樣本 | **28** | 浸泡專屬屬性表 + PCA 結構 |

三份研究都出自 UC Davis Ristenpart/Guinard 體系，共用一套訓練 panel 詞彙，屬性高度一致 —— 這是把它們合併成一張屬性表的前提。

---

## 3. 合併屬性表（BCC 屬性表）

把 31（TEMP）與 28（IMM）的屬性合併、依「在 6 軸模型裡的角色」分三類。第三欄的 TDS/PE 符號來自 TEMP 的相關性分析。

### 3.1 強度維度屬性（→ 直接組成感官軸）

| 屬性 | 模態 | TDS / PE 行為（TEMP）| 歸入軸 |
|---|---|---|---|
| sour | taste | ↑TDS、↓PE | `acidity` |
| citrus | flavor | ↑TDS、↓PE | `acidity` |
| sweet | taste | ↓TDS（BCC）| `sweetness` |
| brown sugar / molasses | flavor | （甜側 flavor）| `sweetness` |
| viscous（body）| mouthfeel | ↑TDS | `body` |
| bitter | taste | ↑TDS | `bitterness` |
| astringent | mouthfeel | ↑TDS | `astringency` |
| papery / musty（paper）| flavor | （過萃 / 老化負向）| `astringency` |
| roasted | flavor | roast level 主導 | `roast` |
| smoky | flavor | ↑TDS、↓PE | `roast` |
| burnt | flavor | roast level 主導 | `roast` |
| brown roast / ashy | flavor | ↑TDS、↑PE | `roast` |

### 3.2 風味性格描述語（→ **不**是軸；是「喝起來像什麼」，由豆+焙度決定）

berry、fruity、floral、black tea、cocoa / dark chocolate、nutty、dried fruit、whiskey、brown spice、black pepper、cereal、tobacco、woody、herbal。

> 這些是 cupping 風味輪的「note」，描述**哪一種**香氣，不是**多強**的一個維度。它們由綠豆品種與焙度決定，不是泡法旋鈕能獨立調出的純量 → 不能當評分軸。它們在模型裡的處理見 §6。

### 3.3 缺陷 / 雜味描述語（→ 不是軸；由負向軸偏高間接表達）

rubber、earthy、fermented、broth、savory、cooked green / dark green / fresh green、green-vegetative。

> 一杯「rubber + earthy + fermented 偏高」= 渾濁過萃的杯子，在 6 軸模型裡會表現為 `astringency` ↑ + `roast` ↑ + `bitterness` ↑（偏離任何 label IDEAL → 低分）。不需要為每個雜味開軸。

### 3.4 PCA 結構（IMM，前 2 維解釋 85% 變異）

- **Dim 1**：burnt / smoky / roasted / rubber / bitter —— 深焙極。等同 `roast` + `bitterness` 軸。
- **Dim 2**：fermented / savory / broth / sour —— 發酵/低萃極。
- IMM 的 3 個**無顯著差異**屬性：`black tea`、`paper`、`herbal`（浸泡法在該設計下未拉開這 3 項 —— 對第 7 軸的判斷有影響，見 §6）。

---

## 4. 定案的 6 感官軸

| # | 軸 key | 中文 | 定義（在杯中物層的意義）| 組成 DA 屬性 | 對 TDS / EY / roast 的行為 | 使用者詞彙 | 舊化合物約略對應 |
|---|---|---|---|---|---|---|---|
| 1 | `acidity` | 酸質 | 明亮、爽口的酸感強度 | sour, citrus | ↑TDS、**↓EY**；淺焙高 | 酸 / acidic | AC |
| 2 | `sweetness` | 甜感 | 焦糖/紅糖的甜感強度 | sweet, brown sugar, molasses | ↓TDS（BCC）；中段 EY 達峰 | 焦糖甜感 / 甜 | SW |
| 3 | `body` | 醇厚 / 質地 | 口腔的厚度、黏稠、份量 | viscous | ↑TDS | great-body / 薄 thin / CREAMY | PS |
| 4 | `bitterness` | 苦 | 苦味強度 | bitter | ↑TDS、↑EY | 苦 / bitter | CGA / CA |
| 5 | `astringency` | 澀 / 粗糙 | 收斂、刮舌、紙板感 | astringent, papery/musty | ↑TDS、過萃（高 EY）↑ | 澀 / harsh | （舊模型無乾淨對應）|
| 6 | `roast` | 焙烤感 | 焙烤、煙燻、燒焦的雜味 | roasted, smoky, burnt, ashy, brown roast | roast level 主導、↑EY、↑TDS | ROASTY | MEL |

**軸的選取準則（三條都要滿足）：**
1. **可訓練** —— 是 BCC/TEMP/IMM 任一份直接量測的 DA panel 屬性（→ 有公開資料能 fit Layer 2）。
2. **可被泡法調動** —— 在 TEMP 的相關性表裡隨 TDS/EY 移動（→ optimizer 推薦旋鈕時有意義）。
3. **是強度維度** —— 是「多強」的純量，不是「哪一種」的類別（→ 能進 log-ratio Gaussian 評分）。

§3.2 的風味性格語通不過準則 3；§3.3 的雜味語通不過準則 1。只有 6 個屬性群同時滿足三條 —— 就是上表。

> **軸鎖定。** Step 2 起 `data/labels.json` 的 `ideal` 改用這 6 個 key；`models/scoring.py` 的 sensory-space 距離在這 6 維上算。新增「風味性格」需求一律走 label IDEAL 的座標表達，不再開新軸。

---

## 5. 已解決：第 6 軸 = `astringency`（開放問題 a）

藍圖 §5 留的問題：第 6 軸取 `astringency` 還是 `clarity`？

**裁決：`astringency`。**

- `astringent` 是 BCC / TEMP / IMM **三份研究都直接量測**的 DA mouthfeel 屬性，TEMP 明確列為隨 TDS 上升 → **完全可訓練**。
- `clarity` / `cleanliness` 在三份研究**都沒有對應的 panel 屬性**（它是 cupping 品質總評，不是 DA 強度屬性）→ 無主軸訓練資料，違反 Phase 10「每條軸都要有公開資料」的初衷。
- 使用者詞彙「澀」「harsh」「不澀」直接對應 `astringency`。

> **使用者明確提醒（必須遵守）：`clarity / cleanliness` 跟 `muted / 香味淡` 是兩回事，不可混為一談。**
> 早期分析曾把兩者並用討論，已更正。三者的精確區分見 §7 —— 這是本文件最容易出錯、也最該講清楚的地方。

---

## 6. 已解決：維持 6 軸，不加第 7 軸 `aroma-character`（開放問題 b）

藍圖 §5 留的問題：要不要為 floral / fruity / black tea 開第 7 軸？tim 的回饋很在意「茶感」「柑橘」「花香」。

**裁決：不加。維持 6 軸。**

理由（資料 + 使用者框架一致）：

1. **茶感/花果香是「位置」不是「軸」。** TEMP 的相關性表裡，`black tea` 是**唯一**隨 TDS 下降、隨 PE（萃取率）上升的屬性；`floral` / `fruity` 隨 TDS 下降（BCC）。換句話說「茶感」= 低 TDS + 高萃取 + 低焙烤 的一個**座標區域**，不是一條獨立強度軸。
2. **6 軸定位得到那個區域。** 一個 `roast` 低、`astringency` 低、`bitterness` 不高、TDS 達標的點 = 乾淨淺焙杯 = 茶感/花香會表現出來。使用者自己的框架：「六軸有對應到，就是淺焙且味道 clean、濃度也達標，理論上就有」—— 與資料一致。
3. **aroma-character 是 categorical 不是 scalar。** 「花香 vs 果香 vs 茶感」是並列的類別，不是同一條軸的高低；硬塞成一條軸無法進 log-ratio Gaussian 評分。
4. **它由豆+焙度決定，不是泡法旋鈕能調的純量** —— 放進「knob→評分」的模型裡名實不符。
5. IMM 研究中 `black tea` 是 3 個無顯著差異屬性之一 —— 即使想開軸，浸泡資料也撐不起來。

> **未解風險（記入 Step 2 watch-list）：** 若 Phase 10 上線後,使用者 feedback 顯示模型無法區分「乾淨而有茶感的淺焙杯」與「乾淨但無趣的淺焙杯」,那就是 6 軸不夠、需要第 7 軸（aromatic intensity）的訊號。屆時再加 —— 加軸是 append，不破壞既有 5 軸。現在不預先加無資料的軸。

---

## 7. 三個非軸概念的精確區分（使用者更正後重寫）

使用者指出 `clarity` 與 `muted` 是兩回事。實際上有**三個**容易混淆的概念，全都**不是軸**，但各自有獨立的湧現路徑。Step 2 建 Layer 2 與 label IDEAL 時必須照這張表處理：

| 概念 | 是什麼 | **不是**什麼 | 從 6 軸如何湧現 |
|---|---|---|---|
| **clarity / 乾淨度** | 杯子乾淨、風味界線分明、無渾濁雜味 | ≠ 香味強弱。乾淨的杯子可以很淡 | 低 `astringency` + 低 `roast` + `bitterness` 不偏高。三個負向軸都低 = 乾淨 |
| **muted / 香味淡 / 低香氣強度** | 香氣**音量小**、風味微弱安靜 | ≠ 乾淨度。淡的杯子可以很乾淨；渾濁的杯子可以很濃 | 低 TDS / 萃取不足 → 6 軸**整體**被壓低 → 平坦 profile 遠離任何 label IDEAL → 低分 |
| **aroma-character / 茶感・花香・果香** | **哪一種**香氣性格 | ≠ 強度,≠ 乾淨度 | 區域:低 `roast` + 低 `astringency` + TDS 達標的座標(見 §6) |

四種組合都存在,證明三者正交、不可互相替代:

- 乾淨 + 淡 = ⭐3 tim「香味淡…clean」(clarity 高、muted 高)
- 渾濁 + 濃 = 過萃杯(clarity 低、muted 低)
- 乾淨 + 響亮 = 理想杯(clarity 高、muted 低、aroma-character 表現)
- 渾濁 + 淡 = ⭐2 tim「ROASTY…完全失去淺焙特色…無趣」(clarity 低、muted 高)

**結論：** 6 軸**不直接**有 clarity 軸、不直接有 aromatic-intensity 軸。但
- `clarity` 由「三個負向軸都低」充分湧現 —— 信心高。
- `muted` 由「TDS 低 → 全軸壓低」湧現 —— 信心中等，是 §6 watch-list 的核心觀察點。
- `aroma-character` 由座標區域湧現 —— 信心中等，靠 label IDEAL 定位 + 使用者 feedback 精修。

---

## 8. 對照使用者 `data/feedback.jsonl` 詞彙

把 6 筆 feedback 用過的 tag 與 comment 關鍵詞全部映射,驗證 6 軸涵蓋使用者實際語言:

| 使用者詞彙（tag / comment）| 對應 | 備註 |
|---|---|---|
| acidic、酸、「酸苦澀」之酸 | 軸 `acidity` | 直接 |
| 焦糖甜感、甜 | 軸 `sweetness` | 直接 |
| great-body、CREAMY、body 支撐 | 軸 `body`（高側）| 直接 |
| thin、薄、BODY 不夠 | 軸 `body`（低側）| 直接 |
| bitter、苦、「酸苦澀」之苦 | 軸 `bitterness` | 直接 |
| harsh、澀、不澀、「酸苦澀」之澀 | 軸 `astringency` | 直接 |
| ROASTY | 軸 `roast` | 直接 |
| 順（smooth）| 低 `astringency` + 低 `bitterness` | 組合 |
| clean | clarity（§7）| 湧現:三負向軸低 |
| muted、香味淡、無趣、「豆子特色消磨殆盡」| muted（§7）| 湧現:低 TDS 壓低全軸 |
| floral、fruity、花果香、柑橘味、茶感 | aroma-character（§7）| 湧現:低 roast + 乾淨 + TDS 達標的座標 |
| balanced | 整體接近 label IDEAL | meta,非單軸 |

6 軸 + §7 三個湧現概念 = 涵蓋全部使用者詞彙,**無孤兒詞**。

---

## 9. 訓練資料取得狀態（2026-05-21 更新）

取得紀錄與欄位對應整理於 [`../data/phase10_training/README.md`](../data/phase10_training/README.md)。

### ✅ 已取得 —— `cotter_dataset.csv`（UC Davis 消費者偏好因子網格）

- Cotter / Ristenpart / Guinard，Dryad `doi:10.25338/B8993H`，**CC0 授權**。已下載至 `data/phase10_training/`。
- **3×3×3 完整因子設計**：溫度（87/90/93°C）× TDS（1.0/1.25/1.5%）× PE（16/20/24%）= 27 brew cell，~118 人/cell，3186 筆。
- 每筆有**實測** TDS / PE / pH / 滴定酸度,加 **17 個 CATA 感官屬性**（含 Sour / Sweet / Caramel / Thick.viscous / Bitter / Astringent / Paper.wood / Roasted / Burnt / Tea.floral / Fruit / Citrus …）+ hedonic liking + JAR。
- **這正是藍圖 §8 要的「(TDS,EY) 因子網格骨架」** —— 17 屬性直接覆蓋 6 軸（對應表見 data README）。性質是消費者 CATA（偵測頻率,非 trained-panel 強度量表）—— 反而更貼模型目的（評分=預測使用者感知）。Step 2 以此為 Layer 2 主回歸骨架。

### ❌ 未取得 —— 浸泡 DA 研究 raw 資料（`10.5061/dryad.v15dv423h`）

- **研判從未正式公開。** 該 DOI 在 DataCite **未註冊**、doi.org 回 404；Dryad 後端有紀錄（dataset id 124603）但任何端點都回「Identifier cannot be viewed … missing required elements」;Dryad/DataCite 多種關鍵詞搜尋 0 筆。論文引用了一個沒上線的資料集 DOI。
- **影響有限**：Step 1 軸定案不需它（靠已發表的 28 屬性表 + PCA,§2–§3 已擷取）。浸泡專屬修正改靠使用者 `feedback.jsonl` 持續精修 —— 本就是藍圖 §8 的設計。

### ❌ 未取得 —— Batali 2020 / Guinard BCC 的 trained-panel 強度資料

- Dryad / DataCite 找不到對應的開放 deposit。論文的 TDS/PE 相關符號表與屬性表已擷取於本文件 §3。
- Step 2 若需 trained-panel 強度網格,可考慮:抓論文補充檔、或寫信向 UC Davis Coffee Center（Ristenpart `wdristenpart@ucdavis.edu`）索取。非阻擋項 —— `cotter_dataset.csv` 的 27-cell 網格已足以建第一版 Layer 2。

---

## 10. 給 Step 2 的交接

1. **6 軸 key 鎖定**：`acidity` `sweetness` `body` `bitterness` `astringency` `roast`。Step 3 重寫 `data/labels.json` 的 `ideal` 用這 6 個 key。
2. **每軸訓練信心分層**（決定 Layer 2 該軸主項/次項權重）：
   - **Tier A（主項，BCC 3×3×3 + TEMP 都有強相關）**：`acidity`、`body`、`bitterness`。
   - **Tier A−（主項但較弱）**：`sweetness` —— 隨 TDS **下降**、是文獻公認的弱/halo 屬性,Layer 2 對它的把握最低,優先靠 feedback 校。
   - **Tier B（可訓練但須防共線）**：`roast` —— 與 `bitterness` 在深焙端共線（IMM PCA Dim 1 兩者同群）；靠「淺焙過萃 = 苦但不 roasty」的樣本拆開。
   - **Tier B（過萃端待次要軸）**：`astringency` —— ↑TDS 明確,但「高 EY 過萃 → 澀」的響應要靠次要軸（研磨）才完整。
3. **§7 三概念**不是軸,但 Layer 2 / 評分要能讓它們正確湧現 —— 當成驗收測試:`clarity` 杯應落在三負向軸低,`muted` 杯應因低 TDS 全軸塌陷,茶感杯應落在 §6 座標。
4. **訓練資料**：`data/phase10_training/cotter_dataset.csv`（27-cell TDS×EY×溫度因子網格 + 17 CATA 屬性）已就位,當 Layer 2 主回歸骨架。浸泡 raw 資料無法取得（§9）—— 浸泡修正改靠 `feedback.jsonl`。

---

## 11. 參考資料

- Guinard et al. 2023 — *A new Coffee Brewing Control Chart…*。J Food Sci 88(5):2168–2177。PubMed 36988107。
- Batali et al. 2020 — *Brew temperature, at fixed brew strength and extraction, has little impact on the sensory profile of drip brew coffee*。Sci Rep s41598-020-73341-4。PMC7536440。
- Sci Rep 2024 — *Sensory analysis of the flavor profile of full immersion hot, room temperature, and cold brewed coffee over time*。PMC11335879。raw 資料 Dryad `10.5061/dryad.v15dv423h`（取得狀態見 §9）。
