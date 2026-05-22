# Phase 11 — 迴圈引擎（Loop Engine）

> **狀態：已實作（2026-05-22）。**
> 上游設計：[`PHASE10_STEP6_FEEDBACK_LOOP.md`](PHASE10_STEP6_FEEDBACK_LOOP.md) §3（三杯循環）、
> §5（搜尋演算法）、§6（Claude 介入）、§7（Phase 11 範圍 + 提案 UX 裁決）。
> 本文件記錄 Phase 11 實際落地的引擎、UI、與相對藍圖的實作裁決。

---

## 0. 一句話

把 Phase 10 的「一次性 Top-N 最佳化器」升級成**配方產生機**：一個 per-roast 的
(1+λ) 演化搜尋，留一個冠軍、每代提兩個擾動實驗，使用者泡了用 §4 對照問卷比較，
系統往使用者的偏好收斂。per-roast IDEAL 從此是迴圈在搜尋的**移動靶**，不是固定靶。

---

## 1. 落地清單

| 類別 | 檔案 | 內容 |
|---|---|---|
| 引擎 | [`models/loop.py`](../models/loop.py) | 三杯循環狀態機、(1+λ) 擾動、digest、skip、flag 偵測 |
| 命名配方 | [`models/saved.py`](../models/saved.py) | 手動命名儲存的配方庫（使用者 2026-05-22 加碼需求）|
| 狀態 | `data/loop_state.json` | per-roast 迴圈狀態（runtime 產生，lazy）|
| 配方庫 | `data/saved_recipes.json` | 命名配方清單（runtime 產生，lazy）|
| changelog | [`data/refine_changelog.md`](../data/refine_changelog.md) | Claude tier-3 模型改動紀錄檔（§6 紀律 3）|
| webapp | [`webapp.py`](../webapp.py) | `/api/loop`、`/api/loop/{start,reset,skip}`、`/api/recipes`、feedback→loop 鉤子 |
| UI | [`templates/index.html`](../templates/index.html)、[`static/js/webapp.js`](../static/js/webapp.js)、[`static/css/phase10.css`](../static/css/phase10.css) | 模式頁籤、單杯提案卡、跳過、冠軍/循環狀態、flag 通知、配方庫 |
| 測試 | [`tests/test_loop.py`](../tests/test_loop.py) | 20 個（引擎 + flag + saved）|

55（Phase 10）+ 20（Phase 11）= **75 pytest PASS**；`diagnose_anchor.py` 13/13（不受影響）。

---

## 2. 架構

```
                    ┌─────────────── data/loop_state.json ───────────────┐
                    │  per-roast: { champion, generation, cycle, history }│
                    └──────────────────────┬──────────────────────────────┘
 optimizer.optimize ─seed─► champion        │
                                            ▼
        ┌── 三杯循環 [exp1, exp2, champion] ──┐
        │  exp1, exp2 = 冠軍的單旋鈕擾動        │   ← (1+λ=2)，擾動半徑照排程
        │  champion   = 進來時的冠軍，重泡      │
        └───────────────┬─────────────────────┘
                         │  三杯各自走 §4 問卷 → feedback.jsonl
                         ▼
        register_feedback ──三杯到齊──► digest ──► 新冠軍 = {冠軍,exp1,exp2} 勝者
                                                   generation++ ，建下一循環
```

迴圈是 **per-roast** 的：每個焙度各跑各的迴圈，`data/loop_state.json` 以 roast 為 key。

---

## 3. 三杯循環 `[exp1, exp2, champion]`

每個循環三杯，照順序泡：

1. **exp1** — 冠軍的單旋鈕擾動。
2. **exp2** — 另一個、不同旋鈕的冠軍擾動。
3. **champion** — 本循環**進來時**的冠軍，原樣重泡。

**為什麼第 3 杯固定是進來時的冠軍**（不是 digest 後的贏家）—— 這是正統的
(1+λ)：親代（冠軍）在整個世代內固定，選擇是世代之間的離散步驟。第 3 杯重泡冠軍
重新錨定味覺記憶（藍圖 §3「重泡冠軍取代記住冠軍」）、給一杯能好好喝的、做絕對錨點
檢查。**digest 後的贏家成為下一個循環的冠軍** —— 勝出的實驗會在下一循環當第 3 杯
被重泡。藍圖 §3 字面另有「第 3 杯＝吃完回饋後算出的最佳」一句，但那會撞時序矛盾
（冠軍×exp2 那條成對边只在第 3 杯回饋後才存在），且讓狀態機分循環 1 / 循環 ≥2 兩套
寫法。實作選正統 (1+λ)：統一、可測、可逐杯獨立驗證。

---

## 4. digest —— 三杯到齊後選冠軍

藍圖 §6 紀律 2：靠記憶的單一比較有雜訊，**不可過度相信**。實作裁決：實驗只在
**明確 `>`** 贏過冠軍時才奪冠；平手 / 缺边一律冠軍守成。

成對边（以 §4 問卷的 `overall` 為來源，`compared_to` 指明對照杯）：

- **exp1 vs 冠軍** —— 循環 ≥2：exp1 對照上一循環的冠軍杯 → **直接**取得。
  循環 1：無上一循環，靠 `exp1↔exp2` 與 `exp2↔冠軍` 兩条边**轉移合成**（可能模糊）。
- **exp2 vs 冠軍** —— champion-slot 的回饋（對照 exp2）直接給出 `冠軍 vs exp2`。
- **exp1 vs exp2** —— exp2 的回饋（對照 exp1）給出，當 tiebreak。

`_select_winner`：兩個實驗都明確贏 → 取 `exp1↔exp2` 較好者；只有一個贏 → 該實驗；
都沒明確贏 → 冠軍守成。`_compose` 對方向相反的鏈（`>` 接 `<`）回傳 `None`（模糊），
合成不出明確訊號就視同冠軍守成。

webapp 會把每杯問卷的 `compared_to` 預選成迴圈建議的「上一杯」，所以正常流程下
digest 拿到的都是乾淨的直接边；使用者改選別杯時，該边取不到就退化成冠軍守成。

---

## 5. 擾動排程（早大後細）

藍圖 §5：步長由排程決定，不由資料決定。`models/loop.py` 模組常數：

```
GENERATION_DECAY = 0.78        每代半徑乘子（幾何衰減）
DIAL_RADIUS_0    = 0.6         dial 單位，第 0 代
STEEP_RADIUS_0   = 90 s        浸泡，第 0 代
DOSE_RADIUS_0    = 3.0 g (XL) / 1.5 g (標準)
```

`radius(gen) = R0 · DECAY^gen`，下限為一個 grid step（晚代實驗仍是「真的、泡得出來
的改變」）。每個實驗只動**一個**旋鈕（藍圖 §8 早期一次動一兩個 → 歸因乾淨）；一個
循環的 exp1 / exp2 盡量動**不同**旋鈕。RNG 由 `(roast, generation, cycle, salt)`
決定 → 可重現、可測；`salt` 隨每次 skip 遞增。溫度**不搜尋**（藍圖 §5 / Step 4 §8）。

第 0 代冠軍由 `optimizer.optimize` 的 Top-1 model-seed（藍圖 §2「不是亂槍打鳥」）。

---

## 6. skip —— 後勤性，不是味覺回饋

藍圖 §7：跳過 = 「這杯泡不了」（沒豆 / 沒時間 / 器材不在），**不是**「看起來會難
喝」。`skip_proposal` 在**同一個 generation 半徑**重抽一個擾動（換一個旋鈕方向，
排除已試過的 move 與另一個實驗的 move）→ 使用者不能靠連續跳過漂向安全牌。冠軍重泡
那一格不能跳過（它不是擾動）。`skips` 計數會顯示出來 —— 同一格被跳很多次 = 擾動排程
一直提不切實際的配方，是排程該收緊的健康訊號（藍圖 §7）。

---

## 7. flag 偵測 —— 模型方向偏差

`detect_flags()` 是對 `feedback.jsonl` 的**純掃描**，不碰迴圈狀態。它找出
`model_attributes_vs`（模型預填方向）與 `attributes_vs`（使用者答案）**明確相反**
（`>` vs `<`）的問卷群，依 `(roast, group, direction)` 分桶，桶內次數
≥ `FLAG_REPEAT_THRESHOLD`（=2）才升成 flag。任一邊是 `?` 一律跳過 —— `?` 是訊號
缺席、不是矛盾（[`FEEDBACK_FORMAT.md`](FEEDBACK_FORMAT.md)「`?` does not feed
correction」）。

迴圈**永不自動改模型**。flag 只是邀請使用者開一個對話，讓 Claude 一次看一批
（藍圖 §6 tier 2 → tier 3）。webapp 在迴圈頁籤頂端用琥珀色通知條顯示累積的 flag。

---

## 8. changelog —— Claude 改動紀錄檔

[`data/refine_changelog.md`](../data/refine_changelog.md)。藍圖 §6 紀律 3：每筆
Claude 對**模型 artefact**（`data/ideal.json` 的 IDEAL、`models/sensory.py` 係數、
Layer 1 先驗、distance 權重）的改動，append 一行：

```
YYYY-MM-DD | <file> | <what changed> | why: <feedback pattern> | revert: <how>
```

迴圈自己的自動冠軍更新**不**寫這裡（那寫在 `loop_state.json` 的 `history`）——
此檔只記 Claude 的手動模型編輯，每筆可追溯、可回退、使用者看得懂。

---

## 9. 提案 UX（藍圖 §7 裁決）

- **不做「多選一菜單」。** 迴圈一次產 2 個實驗，但那是**待泡佇列**（三杯都泡），
  不是讓使用者用眼睛挑。能讀配方挑 → 必挑最像現在愛喝的 → 探索死亡。系統紅線：
  **靠喝評判，不靠讀配方評判。** Top-N 菜單只留給迴圈前的純 exploit 最佳化器。
- webapp 用**頂部模式頁籤**：「最佳化器」(RUN→Top-N，原樣不動) / 「迴圈精修」。
  迴圈頁籤一次只顯示**一個**提案杯 + 跳過鈕 + §4 問卷 + 冠軍/循環狀態 + 重製鈕。
- **重製按鈕**（使用者 2026-05-22 加碼需求）—— 捨棄目前冠軍與循環，從新的
  model-seed 重跑；有 `confirm()` 確認防誤觸。

---

## 10. 命名配方庫（使用者 2026-05-22 加碼需求）

使用者要求「只紀錄唯一好喝 或是使用者手動存的參數，並且可以命名這組參數」。
[`models/saved.py`](../models/saved.py) + `data/saved_recipes.json`：手動命名儲存
任一配方（optimizer 結果卡、迴圈冠軍卡上的「★ 命名儲存」），可看 / 刪 / 帶回左側
表單。這是迴圈**自動**冠軍的手動互補 —— 冠軍是程式追蹤的「唯一好喝」，命名配方是
使用者親自蓋章的。

> **未採納：** 使用者另提「以 cotter 美味分數高的 TDS/EY 區當目標」。已在
> Phase 10 Step 4 查證 —— cotter 喜好曲面近乎平、消費者分兩群偏好相反
> （[`PHASE10_STEP4_LAYER1.md`](PHASE10_STEP4_LAYER1.md) §6），沒有「客觀美味
> TDS/EY」可框；這正是 IDEAL 改採使用者自己 ⭐5 杯的原因，也是迴圈的前提（IDEAL
> 是使用者在搜尋的移動靶）。placeholder 焙度（medium / moderately_dark）改用 cotter
> 較高喜好區重新 seed 是合理的未來精修，但屬 Layer 2 工作，與迴圈引擎分離。

---

## 11. 相對藍圖的實作裁決（彙整）

| 主題 | 藍圖 | Phase 11 實作 | 理由 |
|---|---|---|---|
| 第 3 杯 | §3 字面「digest 後的最佳」 | 進來時的冠軍重泡；勝者進下一循環 | 正統 (1+λ)、無時序矛盾、狀態機統一 |
| digest 時機 | — | 三杯全到齊後 | 統一、可測 |
| exp1↔冠軍 边 | §3 鏈式 exp2↔exp1 | 循環 ≥2 直接对照冠軍杯；循環 1 才合成 | 直接边比轉移合成乾淨 |
| 奪冠門檻 | §6 紀律 2 | 只在明確 `>` 換冠軍，否則守成 | 不過度相信單一噪音比較 |
| 命名配方 / 重製鈕 | §7 只列重製鈕 | 兩者都做 | 使用者 2026-05-22 加碼需求 |

---

## 12. 未解 / 開放項目

- **digest 的轉移合成（循環 1）有雜訊** —— 設計上接受；步長排程吸收（藍圖 §8）。
- **flag 門檻 2** 是初值，feedback 累積後可調（`FLAG_REPEAT_THRESHOLD`）。
- **擾動排程常數**（`*_RADIUS_0` / `GENERATION_DECAY`）是有理據的初值，非實測校準；
  使用者實泡幾個循環後可微調。
- **placeholder 焙度** 的迴圈一樣能跑，但 IDEAL 仍是佔位 —— 該焙度有 feedback 後
  才真錨定（與 Phase 10 一致）。
- **cotter-region 重 seed placeholder 焙度** —— §10 提及的未來 Layer 2 精修選項。
