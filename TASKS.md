# 待辦任務路線圖

## UI — Chip 標籤重寫（⚠️ 等 Phase 1-3 完成後才能做）

**目標：** Dose chip 的 7 段風味描述以 TDS 偏差為主軸，貼合人類感官現實。

**為什麼現在不能做：**
- Chip flavor 描述依賴 SW_abs / PS_abs（= compound fraction × TDS）
- 但化合物模型有系統性誤差（欠萃 SW 比正萃還高），Phase 1 尚未修正
- 基於錯誤的化合物預測設計標籤 = 建在沙上
- 必須等 Phase 1-3 完成，用校準後的模型重新推導各豆量段的真實風味走向
- Chip **機制**（限制豆量搜尋範圍）保留；flavor **文字描述**暫時移除或用中性標示

**背景資料（供日後設計參考）：**
- Optimizer 已嘗試補償低豆量的 TDS 不足（最細研磨 + 120s），但 20g/400ml 物理上限 TDS≈1.174，無法到達 TDS_PREFER=1.27
- Light+XL 的 TDS 最接近理想值在 25-26g（偏差 −0.2%）
- Medium/Moderately_dark 在 XL 全段 TDS 偏差 −10% 至 −16%，全段過淡
- 低 TDS + 高 EY = SCA under-concentrated 象限：酸感集中、澀鹹、無香（使用者實測確認）

**等 Phase 1-3 完成後要做的事：**
- [ ] 7 段標籤以新模型的 TDS 偏差 + 化合物絕對值重新設計
- [ ] 過淡區（偏差 > −5%）需標示酸澀風險，不能用正面詞彙
- [ ] Medium/dark 在 XL 上全段過淡，需誠實標示
- [ ] 標籤需按焙度組分組（淺焙 vs 中深焙行為不同）
- [ ] `getDoseFlavorHint()` 邏輯同步更新

---

## Phase 1 — 化合物模型修正（`compounds.py` + `constants.py`）

**目標：** 讓欠萃配方的化合物 profile 與正萃明顯不同，消除模型鑑別力不足問題。

**已知問題（已解決）：**
- ~~Under-extract (93C/6.5/60s) 的 SW fraction 比 Hoffman (98C/4.6/120s) 還高（欠萃比正萃還甜？）~~
- ~~根本原因：`COMPOUND_BASE` 基底佔比過大，時間/溫度修正幅度太小~~
- ~~壞配方和好配方的化合物 profile 幾乎相同，鑑別完全靠 TDS floor~~

**實作內容（2026-04-09）：**
- `constants.py`：新增 `SW_DIAL_COEFF = 0.10`（每 dial 單位 10% 對數線性修正）
- `compounds.py`：`_predict_closed_compounds()` 中 SW 計算末尾加入 `sw *= exp(SW_DIAL_COEFF * (DIAL_BASE - dial))`
- 物理意義：細研磨 → 更多接觸面積 → 更多香氣揮發物萃取。不用 EY 門控（因果倒置，見 constants.py 設計說明）
- 效果：Under SW_frac 0.376 → 0.335，Hoffman SW_frac 0.339；Under < Hoffman ✓

**完成狀態：**
- [x] 研磨粗細（粗研磨）顯著壓低 SW（`SW_DIAL_COEFF`）— EY-gate 改用研磨直接修正避免因果倒置
- [x] 確保 under-extract SW fraction < Hoffman SW fraction（0.335 < 0.339）
- [x] CGA/MEL 在過萃時明顯超標，欠萃時明顯偏低（Over CGA_frac 0.082 > Hoffman 0.067 > Under 0.052）
- [x] `python diagnose_anchor.py` 全部 `[ OK ]`（Hoffman/April/Championship/Under/Over 全 PASS）
- [ ] **待續（Phase 1.5 可選）：** SW_TIME_FLOOR 目前仍 0.50，短浸泡鑑別力尚有改善空間（但改動有破壞 Championship 風險，留 Phase 3 校準時評估）

---

## Phase 2 — 評分邊際曲線（`scoring.py`）

**目標：** 好配方得高分，壞配方被懲罰，鑑別度提升。

**要做的事：**
- [ ] 化合物好處邊際遞減（接近理想高報酬，超過後趨平）
- [ ] 化合物壞處邊際遞增（偏離越多，懲罰加速）
- [ ] 加入比值評分：AC/CGA（純淨酸質）、SW/MEL（甜苦比）、PS/CA（醇厚乾淨度）
- [ ] 各比值使用獨立的加分/扣分曲線
- [ ] 所有函數必須平滑連續（禁止 min/max/if-else 硬斷點，見 CLAUDE.md 設計原則）

---

## Phase 3 — 重新校準錨點（`diagnose_anchor.py` + `constants.py`）

**目標：** Phase 1+2 完成後，確認五錨點全部通過，物理合理性對齊。

**要做的事：**
- [ ] 五錨點全部重跑：Hoffman / April / Championship / Under-extract / Over-extract
- [ ] 確認化合物物理合理性（不只看分數，看每個化合物的絕對值和比例）
- [ ] 調整 `IDEAL_FLAVOR` 對齊新化合物模型的預測值
- [ ] 調整 `COMPOUND_SIGMA_LO/HI` 對齊新的鑑別度需求
- [ ] `diagnose_anchor.py` 全部 `[ OK ]` 才算完成
