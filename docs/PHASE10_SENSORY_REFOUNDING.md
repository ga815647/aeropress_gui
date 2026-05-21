# Phase 10 — 感官重新奠基（Sensory Re-founding）

> **狀態：設計藍圖。** 本文件是 Phase 10 的第一個 commit；程式改動在使用者過目、確認本藍圖後才開始。
> 舊的化合物模型已凍結在 branch `compound-model-legacy`（commit `ac789b8`）。
>
> 注意：`docs/FEEDBACK_FORMAT.md` 裡曾把「`recipe` snapshot 擴充」非正式地稱作 Phase 10 —— 那是小修；**本文件才是真正的 Phase 10**。

---

## 1. 動機 —— 為什麼要重新奠基

現行模型用 6 個「化合物」（AC / SW / PS / CA / CGA / MEL）當風味的核心表徵。這個抽象有一個結構性缺陷：

- **它是混血兒。** CGA、MEL 是真分子；AC（酸質）、SW（甜感）是**感知**。一半化學、一半感官。
- **它不可訓練。** 家裡能量到的只有 TDS（折射儀，1 個純量）。6 個化合物濃度量不到（要 HPLC）。所以 6 化合物的「拆分」永遠無法被實測校準 —— 只能靠先驗。
- **使用者的回饋是孤兒。** `feedback.jsonl` 的 tags（`acidic` / `bitter` / `great-body` / `clean` …）本身就是感官詞，但沒有任何量測能把「bitter」對應到一個 CGA 分率。回饋無法回流校準。
- **它一直生 bug。** tim「太黑 / roasty / 失去淺焙特色」就是症狀：模型把高劑量、偏黑的 ⭐2 杯（TDS 1.50）算得比 tea-brown 的 ⭐4 杯（TDS 1.45）分數高。根因在 Layer 1 對 light 焙 EY-dose 耦合的錯誤預測，而化合物層的 dose-blind 設計讓它無法自我修正。

**文獻的裁決很乾脆：** 所有被驗證過的咖啡萃取模型都**聚合** —— 全浸泡平衡脫附模型明文「把所有溶解物種當成一個聚合體，用單一平均常數，而不是追蹤個別化學物質」（數百種物種、家裡量不到）。沒有人「先算 N 個化合物再加總」。

但本系統的目的不是預測化學，是**預測風味**。所以正確的路不是回到純聚合（TDS/EY 兩軸不足以分辨 acid-forward 和 sweet-body），而是**把表徵從「假化學」換成「真感官」** —— 而感官這條軸，剛好有公開的訓練資料（見 §8）。

---

## 2. 核心決策

| | 現行（Phase 8/9）| Phase 10 |
|---|---|---|
| 風味表徵 | 6 化合物 AC/SW/PS/CA/CGA/MEL（半化學半感官）| 6 感官軸（純感知，對齊 SCA cupping / DA panel 詞彙）|
| Layer 1 | `ey_model` + `tds_model` + `compounds.py` 全套 Arrhenius 動力學 | 薄轉換器：knob → TDS/EY 粗估（平衡脫附式）|
| 中樞 | （無明確中樞）| **TDS / EY** —— 量得到、有公開風味資料 |
| Layer 2 | `compounds.py` 純物理動力學 → `compute_actual_abs` | 經驗風味模型 `f(TDS, EY, roast, 溫度, 研磨) → 6 感官軸`，**訓練**而非推導 |
| 校準資料 | 只有 TDS（錨不住拆分）| UC Davis BCC + 浸泡 DA 研究 + 使用者自己的 feedback log |
| `compounds.py` | 核心引擎 | 退役（保留在 `compound-model-legacy` branch）|

---

## 3. 架構

```
knobs ──┬──→ [薄 Layer 1] ──→ TDS / EY ──┐
(溫度/   │     knob→TDS/EY 粗估           │
 研磨/   │     會被實測修正               ├──→ [Layer 2 風味模型] ──→ 6 感官軸 ──→ [評分]
 dose/   └──→ 溫度, 研磨 ─────────────────┘     主軸: TDS / EY / roast        ↑
 水量/時間)        (次要殘差,直連)              次軸: 溫度, 研磨            label IDEAL
                                                                           (6 軸感官目標)

評估已沖的杯：TDS / EY 直接用「實測值」當 input，整段薄 Layer 1 被旁路。
```

- **薄 Layer 1（knob → TDS/EY）** —— 只在「推薦新配方」時需要，而且只要大概對；使用者沖完會實測，真正進評分的是實測值。
- **中樞 TDS / EY** —— 唯一在家量得到（TDS 折射儀；EY = TDS% × 出杯重 ÷ 粉重）、又有公開風味資料的量。
- **Layer 2（TDS/EY → 風味）** —— 系統的核心，可訓練、method-agnostic。
- **評分** —— 預測的 6 軸 vs label 的 6 軸 IDEAL，sensory-space 距離。

---

## 4. 為什麼是「TDS/EY + 兩個次要軸」（幾何論證）

固定一份食譜的 dose / 水量後，`TDS ≈ EY × dose ÷ 出杯重`，出杯重幾乎固定 —— **TDS 和 EY 幾乎共線，實質一個約束**。

於是 {溫度, 研磨, 時間} 這 3 個變數，被「固定 TDS/EY」約束掉 1 個自由度 → 剩下一個 **2D 解曲面**：所有泡出同一組 TDS/EY 的 (溫度, 研磨, 時間) 組合。

- 沿這個 2D 面移動，風味**會**變（選擇性 selectivity：同樣的萃取總量，溫度/研磨改變「哪些」化合物溶出的比例）。
- 所以 TDS/EY 不足以定位一杯咖啡 —— 還需要 **2 個座標**才能在 2D 面上定位。
- 取「帶最多風味資訊的兩個」：

| 變數 | 角色 | 進 Layer 2？ |
|---|---|---|
| 溫度 | 選擇性（哪些化合物溶出）| ✅ 次要軸 |
| 研磨 | body / 清澈度（細粉量、萃取均勻度）| ✅ 次要軸 |
| 時間 | 被決定的那個（溫度+研磨+EY 給定 → 時間落定）| ❌ 丟掉 |

**次要軸是「弱訓練」的：** UC Davis 實測「固定 TDS/EY 下溫度影響小」（87–93°C drip）；浸泡研究也顯示 TDS plateau 後時間殘差小。所以 `f` 對 TDS/EY/roast 是主項，對溫度/研磨是小修正項。模型必須誠實標出這個信心差。研磨係數實測**可能**很小（主要動 body/清澈度），但仍留在模型裡 —— 那個面是真的 2D，不能先驗砍掉某個方向。

---

## 5. 6 感官軸（暫定 —— Step 1 從資料定案）

對齊 SCA cupping form / DA panel 詞彙。暫定：

| 軸 | 中文 | 對齊的 DA 屬性（浸泡 28 屬性表）| 舊化合物約略對應 |
|---|---|---|---|
| `acidity` | 酸質 | sour, citrus | AC |
| `sweetness` | 甜感 | sweet, brown sugar | SW |
| `body` | 醇厚 / 質地 | viscous | PS |
| `bitterness` | 苦 | bitter | CGA / CA |
| `roast` | 焙烤感 | roasted, smoky, burnt | MEL |
| `astringency` | 澀 / 粗糙 | astringent, paper | （無乾淨對應）|

**待定案問題（Step 1 解決）：**
- 第 6 軸取 `astringency` 還是 `clarity`（乾淨度）？`astringency` 是 DA panel 直接量的、可訓練；`clarity`/clean cup 是 cupping 品質分，較難訓練。暫定 `astringency`。
- 花香 / 茶感 / 果香（floral / black tea / fruity）是**風味性格**，不是強度軸。tim label 很在意「茶感」。選項：(a) 維持 6 軸，茶感由「低 roast + 高 acidity + 低 astringency」的位置隱含表達；(b) 加第 7 軸 `aroma-character`。暫定 (a)，Step 1 看 Dryad 資料的屬性結構再定。

---

## 6. 薄 Layer 1 規格（knob → TDS/EY）

取代現行 `ey_model.py` + `tds_model.py` + `compounds.py` 的全套機械。依平衡脫附 / BCC 框架：

- `EY ≈ K · E_max` —— `K` 隨 roast / 溫度 / 研磨 / 時間 緩慢變化（浸泡在平衡態近似與 brew ratio 無關；愛樂壓短浸泡屬動力學區，brew ratio 仍有作用，需保留一個 dose 項）。
- `TDS ≈ EY × dose ÷ 出杯重`。
- 用現有的 Layer 1 錨點（Hoffman/April/Champion 的**實測 TDS**）校 `K` 與少數常數。
- **設計要求：只要粗估。** 推薦配方時給使用者一個起點；使用者沖完實測 TDS（+ 秤出杯重得 EY），評估時用實測值。Layer 1 的誤差不會污染風味評分。

---

## 7. Layer 2 規格、評分、與 `labels.json` 重寫

### 7.1 Layer 2 風味模型
`f(TDS, EY, roast, 溫度, 研磨) → {6 感官軸強度}`。從 §8 的資料回歸或查表得到：主項 (TDS, EY, roast)，次項 (溫度, 研磨) 小係數。

### 7.2 評分（`models/scoring.py` 重寫）
- 預測 6 軸向量 vs label 的 6 軸 IDEAL → **sensory-space 距離**（log-ratio Gaussian 或類似，沿用現有平滑結構）。
- **TDS 不再單獨評分。** TDS 對風味的影響已完全經 6 軸表達（TDS 太高 → `bitterness`/`roast` 軸過高 → 距離 IDEAL 遠 → 自然低分）。移除分離的 `tds_factor` —— 避免雙重計分。
- 同一個評分公式套所有 label（CLAUDE.md 原則 #2）。
- **`tds_prefer` 預期被吸收** —— label 的「偏好 TDS」就是「能產生那個 6 軸 IDEAL 的 TDS」，emergent，不需獨立欄位。Step 3 確認。

### 7.3 `data/labels.json` 重寫
每個 label 的 `ideal` 從「6 化合物分率」改成「6 感官軸目標強度」。重寫流程：
1. 取該 label 的 bullseye 錨點配方的**實測 TDS/EY**（+ 溫度/研磨）。
2. 餵進 Layer 2 → 得到 6 軸 sensory profile。
3. 那就是該 label 的新 IDEAL。
- `balanced`←Hoffman、`acid-forward`←April、`sweet-body`←Champion、`coarse-modern`←Hedrick、`tim`←Tim Wendelboe。
- `ideal_by_roast`、`dial_prefer` 等機制可沿用（語意改成感官軸）。

---

## 8. 訓練資料來源

| 資料 | 性質 | 用途 |
|---|---|---|
| **UC Davis 新 BCC**（Guinard 2023）| drip，3×3×3 因子（TDS×EY×roast），30 屬性，trained panel | (TDS,EY)→感官 的**密網格骨架** |
| **UC Davis 溫度研究**（Batali 2020）| drip，TDS×EY×溫度(87/90/93°C)，33 屬性 | 溫度次要軸的係數上界（實測「殘差小」）|
| **浸泡 DA 研究**（Sci Rep 2024）| 全浸泡，28 屬性，含 `black tea` 軸；**原始資料公開於 Dryad `10.5061/dryad.v15dv423h`** | 浸泡專屬修正 + 屬性表定案 6 軸 |
| **平衡脫附模型**（Sci Rep 2021）| 全浸泡 TDS/EY 物理 | 薄 Layer 1 |
| **使用者 `feedback.jsonl`** | 自己的豆 / 愛樂壓，tags 直接對應 6 軸 | 持續精修（每次沖煮都是訓練點）|

**drip vs 浸泡的取捨：** 愛樂壓是混血（浸泡為主 + 短下壓）。drip BCC 因子網格最密 → 當骨架；浸泡資料較少（emerging area）→ 當方法修正。橋樑是 BCC 的前提：杯中感官 ≈ f(TDS, EY)，與器具大致無關。

---

## 9. CLAUDE.md 原則改寫

| 原則 | 現行 | Phase 10 改寫方向 |
|---|---|---|
| #1 無硬斷點 | 不變 | 不變（平滑函數仍是紅線）|
| #2 統一評分公式 | 所有 label 共用 `flavor_score` | 不變 —— 改成共用「sensory-space 距離」公式 |
| #3 化合物模型自我鑑別 | 化合物 profile 自然分好壞，不靠 EY/TDS floor | 改成「**感官模型**自我鑑別」：壞杯的 6 軸向量自然偏離 IDEAL → 低分；不需 EY/TDS floor |
| #4 化合物層純物理 / 感官層可閾值 | `compounds.py` 純 Arrhenius，無閾值 | 改成「**Layer 1 物理粗估 / Layer 2 經驗訓練**」：Layer 2 是 fit 出來的，不是手調物理、也不是手刻閾值 |
| #5 錨點分 Layer 1 校準 / Layer 2 感官島 | 不變（仍成立）| Layer 1 錨點校薄轉換器；Layer 2 label 島改在 6 感官軸空間 |

---

## 10. feedback schema 擴充

`docs/FEEDBACK_FORMAT.md` 的 `recipe` 區塊加實測欄位（仍 append-only、向後相容、舊紀錄欄位為 `null`）：

```json
"recipe": {
  "temp": 98, "dial": 3.9, "dose": 28.0, "steep_sec": 60,
  "tds": 1.50,            // 改為「實測 TDS」（折射儀），無實測則 null
  "beverage_g": 240,      // 新增：出杯重（秤），用來算實測 EY
  "ey": 18.6,             // 由實測 tds × beverage_g ÷ dose 得；無實測則 null
  "score": 95.5
}
```

- webapp 沖煮回饋表單加「實測 TDS」「出杯重」兩個欄位（optional 但強烈鼓勵）。
- 有實測值的紀錄 = 對「你的豆 / 你的器具」的真實 (TDS,EY)→感官 訓練點。

---

## 11. 執行步驟

| # | 步驟 | 主要檔案 |
|---|---|---|
| 0 | ✅ 切 `compound-model-legacy` branch 凍結舊模型 | （git）|
| 1 | 下載 Dryad 資料、整理 BCC 屬性表，定案 6 感官軸 | docs |
| 2 | 建 Layer 2 `f(TDS,EY,roast,溫度,研磨)→6 軸`（回歸/查表）| `models/`（新檔）|
| 3 | 重寫 `data/labels.json` —— IDEAL 改 6 感官軸 | `data/labels.json` |
| 4 | 薄 Layer 1（平衡脫附式 knob→TDS/EY）| `models/`，退役 `ey_model`/`tds_model`/`compounds` |
| 5 | 重寫 `models/scoring.py`（sensory-space 距離，移除 `tds_factor`）| `models/scoring.py` |
| 6 | feedback schema + webapp 實測欄位 | `docs/FEEDBACK_FORMAT.md`、`webapp.py`、`static/js/` |
| 7 | 重寫 `diagnose_anchor.py` + `tests/`（Layer 1 物理 band / Layer 2 感官分數）| `diagnose_anchor.py`、`tests/` |
| 8 | 改寫 `CLAUDE.md` 原則 #3/#4/#5 + `ARCHITECTURE.md` + `TASKS.md` | docs |

每步都維持「錨點可獨立驗證」。規模 ≈ Phase 8 × 2，是目前最大的一次重構。

---

## 12. 風險與回退

- **回退保險：** `compound-model-legacy` branch 完整保留舊模型；main 走壞了隨時對照 / 回退。
- **行為大變：** optimizer 推薦會變；使用者習慣的 Top 會不同 —— UI 要同步說明。
- **資料缺口：** 浸泡 DA 研究只有一份（Sci Rep 2024）；次要軸（溫度/研磨）的訓練資料比主軸薄 —— 模型要誠實標出信心差，靠使用者 feedback 持續精修。
- **錨點遷移：** 6 個錨點（Hoffman/April/Champion/Hedrick/Under/Over）的 IDEAL 全要在感官軸空間重新表達；diagnose / tests 全部重寫。

---

## 13. 預期收益 + 未解問題

**收益：**
- 模型名實相符 —— 表徵就是使用者實際感知與標記的東西。
- 落在**有公開訓練資料**的軸上；使用者的 feedback 直接可用、每杯都是訓練點。
- **tim bug 預期自然消解：** 評估 tim ⭐2 杯時直接 input 實測 TDS 1.50 → Layer 2 給高 `roast` / 低 `sweetness` → 偏離 tim IDEAL → 低分，對上舌頭。壞掉的 light 焙 EY 預測被整段旁路。（待重構後驗證。）
- Layer 1 大幅簡化（平衡脫附論文發現溫度/研磨對 TDS/EY 幾乎無感，舊那套精細 Arrhenius 從未被驗證）。

**未解問題（Step 1 起逐一處理）：**
- 6 軸最終定案、第 6 軸 `astringency` vs `clarity`、要不要第 7 軸 `aroma-character`。
- drip 與浸泡資料的加權方式。
- `tds_prefer` 是否確定被 IDEAL 吸收。
- 實測 EY 需使用者秤出杯重 —— webapp UX 流程。

---

## 14. 參考資料

- Guinard et al. 2023 — *A new Coffee Brewing Control Chart relating sensory properties and consumer liking to brew strength, extraction yield, and brew ratio*. PubMed 36988107.
- Batali et al. 2020 — *Brew temperature, at fixed brew strength and extraction, has little impact on the sensory profile of drip brew coffee*. Sci Rep s41598-020-73341-4.
- Sci Rep 2024 — *Sensory analysis of the flavor profile of full immersion hot, room temperature, and cold brewed coffee over time*. PMC11335879. 原始資料 Dryad `10.5061/dryad.v15dv423h`.
- Sci Rep 2021 — *An equilibrium desorption model for the strength and extraction yield of full immersion brewed coffee*. PMC7994670 / s41598-021-85787-1.
- MDPI Foods 2022 — *Sensory Analysis of Full Immersion Coffee: Cold Brew Is More Floral, and Less Bitter, Sour, and Rubbery Than Hot Brew*. 11(16):2440.
- Moroney, Lee et al. 2016 — *Coffee extraction kinetics in a well mixed system*. PMC4986356.
