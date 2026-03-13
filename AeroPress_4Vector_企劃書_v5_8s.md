# AeroPress 四向量最佳化系統 — 企劃書 v5.8s

> ---
> ## ⚡ AGENT 快速導讀（實作專用）
>
> **實作必讀章節：§0（常數）、§1–§9（模型規格）、§10（主程式）、§11（輸出格式）、§12（CLI）、§13（檔案結構）**
> **可跳過：** 本標題以上所有版本歷史與 Gemini 討論（第 1–1024 行）——內容為設計溯源，不影響實作正確性。
> **校正參考：** §14（已知限制）、§15（待辦迭代）、§16（校正優先順序）——實作完成後再讀。
>
> **實作起點：** 從 `§0` 讀取所有常數 → `§10` 的 `optimize()` 為核心執行函數 → `§12` 的 CLI 規格為程式入口 → `§13` 的檔案結構為目錄佈局。
> **三個環境參數的注入時機（AGENT 必讀）：** `--t-env`、`--tds-floor`、`--altitude` 在 `main.py` 的 `argparse` 解析後、呼叫 `optimize()` 前，以全域覆寫方式注入：
> ```python
> # main.py 的 argparse 解析後立即執行（在 import constants 後、呼叫 optimize 前）：
> import constants
> constants.T_ENV = args.t_env
> constants.TDS_BROWN_WATER_FLOOR = args.tds_floor
> constants.TEMP_BOILING_POINT = 100.0 - args.altitude / 300.0
> ```
> ---

> **相較 v5.8r 的變更（v5.8s 規格書可實作性審查修正，共 6 項）：**
> ①**`get_water_preset()` 回傳型別修正（Crash Fix）**——原函數回傳 tuple，但 `main.py` 骨架以 dict 方式存取（`preset['gh']`），導致所有 `--preset` 呼叫直接 `TypeError` 崩潰；修正為回傳整個 dict `p`，main.py 骨架相容，不需同步修改。
> ②**全域常數注入模組隔離說明（靜默錯誤預防）**——`constants.T_ENV`、`TEMP_BOILING_POINT`、`TDS_BROWN_WATER_FLOOR` 三個由 CLI 在執行時覆寫的常數，若子模組以 `from constants import T_ENV` 方式引入，覆寫將靜默失效（拿到 import 時的舊值）；§13 新增強制說明：所有存取此三常數的子模組必須以 `constants.T_ENV` 屬性存取方式引用。
> ③**Swirl 時間三處文件衝突修正**——§4.2 步驟 4「旋轉 10 秒」與 §11.2 JSON 模板 `"swirl_sec": 10` 均與 `SWIRL_TIME_SEC = 5`（v4.8 定版）衝突；修正為 5 秒，並將 JSON 模板中的硬編碼數字改為說明應讀取常數。
> ④**層 7 `cga_excess_ratio` 不對稱設計補充說明**——酸澀協同層的 `cga_excess_ratio` 刻意使用澀感閾值（÷ `CGA_ASTRINGENCY_THRESHOLD`）而非對稱的 `ideal_abs` 除法；未說明易被 agent 改成對稱形式，使懲罰觸發門檻大幅降低；§9 層 7 注釋補充說明此設計意圖。
> ⑤**§13 殘留舊版常數值修正**——`SWIRL_CONVECTION_BASE=0.5` 為 v4.7 舊值（v4.8 已改為 1.0），殘留在 §13 歷史注釋中可能誤導 agent；修正為明確標示舊值已廢棄。
> ⑥**output 模組最小函數骨架補全**——`print_terminal()`、`export_json()`、`export_csv()`、`plot_radar()` 四個函數原無參數簽名定義；§13 補入各函數的最小骨架（簽名 + 參數說明 + 資料來源），消除 agent 自由發揮空間。


> **格式說明：** 所有參數、公式、流程均為可直接實作的規格，無需人工詮釋。
> **相較 v5.7 的變更（Gemini 壓力測試兩條 Bug，一條修正，一條澄清不存在）：**
> ①**sw_aroma_penalty 觸發變數修正（Bug Fix：大豆量免疫謬誤）**——觸發溫度從 `t_slurry` 改為 `temp_initial`（壺溫）；物理依據：揮發性芳香物質的閃蒸（Flash Volatilization）發生在水柱**接觸乾燥粉表面的瞬間**，此時水溫等於壺溫而非混合後漿體溫；使用 `t_slurry` 會導致大豆量（30g）以 100°C 沸水沖煮時，因漿體溫降至 93°C 低於觸發閾值而完全不被懲罰（大豆量免疫）；修正後任何豆量使用 100°C 沸水均觸發 −10% SW 感知扣減，物理行為符合現實。
> ②**注水代數對消 Bug（Gemini 描述不存在，澄清記錄）**——Gemini 聲稱 v5.7 同時存在 `pour_offset`（減法）與 `pour_equiv`（加法）導致相消；v5.7 明確不採納注水湍流正向等效，程式碼中**從未存在 `pour_equiv`**；`t_kinetic = max(0, steep_sec - pour_offset) + SWIRL_TIME_SEC × swirl_mult + press_equiv` 無對消問題；此為 Gemini 第三次描述不存在的程式碼（前兩次：v4.5 時序悖論、v4.6 漸近線 Bug）；§14 新增澄清條目，不修改任何程式碼。
> **§15 新增兩項（Gemini 壓力測試建議列入 §15）：**
> 第 21 點：粉床壓實豆量動態補償（compaction × dose 二元函數）；第 22 點：水合放熱 T_slurry 截距微調。
>
> **相較 v5.6 的變更（Gemini 壓力測試六條，三條採納，三條列入 §15）：**
> ①**高溫 SW 揮發逸散懲罰（Volatile Aroma Loss）**——`flavor_score` 感知過濾器新增 `sw_aroma_penalty`：當 `t_slurry > 95°C` 時，`actual_perceived['SW'] *= 1.0 - min((t_slurry - 95) × SW_AROMA_SLOPE, 0.30)`；斜率 `SW_AROMA_SLOPE = 0.02`（每 1°C 扣 2%，上限 −30%）；物理依據：揮發性芳香物質（花香、果酸甜感）在高溫下熱降解或隨蒸氣逸散，與 `predict_compounds` 的 SW 溶出拋物線正交——後者建模溶出量，本層建模鼻後嗅覺感知損失；與 KH 感知層同一入口，不影響 TDS 計算。
> ②**深焙焦澀協同（Ashy Synergy Penalty，第 8 層）**——`flavor_score` 新增第八層：僅對 MD/D 焙度啟用，`ashy_penalty = exp(−ASHY_SLOPE × mel_excess × cga_excess)`，`ASHY_SLOPE = 3.0`（低於酸澀協同 4.0，因焦澀感官閾值略高）；`mel_excess = max(actual_perceived['MEL'] / ideal_abs['MEL'] − 1, 0)`；`cga_excess` 同酸澀協同設計；單維超標不觸發（乘積為零），MEL=1.3×+CGA=1.3× 扣 23%，MEL=1.5×+CGA=1.5× 扣 53%；補足酸澀協同對深焙的盲區（深焙 AC 極低，無法觸發 AC×CGA 層），建立完整八層評分架構。
> ③**注水湍流正向等效（不採納）**——Gemini 建議將 `pour_offset` 從「扣除時間」改為正向湍流等效時間加入 `t_kinetic`；不採納理由：`pour_offset` 設計為平均接觸延遲修正（時間歸零），改成 `pour_time × 50%` 的正向加法等於多加整個注水時間（+33s）；湍流效率 50% 無實測依據，POUR_RATE 本身已是估算值，兩個估算相乘屬過擬合；列入 §15-18，待折射儀 A/B 實測（有/無注水延遲修正的 TDS 差值）後決定。
> **§15 新增三項（Gemini 壓力測試建議列入 §15）：**
> 第 18 點：注水湍流等效實測方案；第 19 點：蒸發率 TDS 濃縮補償；第 20 點：細粉率焙度動態補償（FINES_RATIO_BASE 改為焙度字典矩陣）。
>
> **相較 v5.5 的變更（理論推導值實作，兩條採納，一條模擬驗證後決定）：**
> ①**Swirl 粉床重置修正（Swirl Reset Fraction）**——`calc_press_time` 的 `compaction_mult` 改以 `effective_compaction_time = steep_sec × (1 − SWIRL_RESET_FRACTION) + swirl_wait_sec` 取代純 `steep_sec`；`SWIRL_RESET_FRACTION = 0.35` 由斯托克斯沉降理論推導（Swirl 渦流 Re≈500，可懸浮粒徑 <80μm 顆粒，約佔細粉層 35%；剩餘 65% 嵌入間隙不被重置）；240s 浸泡時 effective_time 從 240s 降至 189s（+swirl_wait），壓降阻力計算更符合真實 Swirl 後的粉床狀態；§14 標注來源為流體力學理論推導，待實測校正。
> ②**自由溶劑修正（Free Water Correction）**——`brew_capacity` 的分子從固定 `water_ml` 改為 `free_water = water_ml − dose × calc_retention(roast_code, dial)`；18g 淺焙（retention=2.00）：free_water=364ml，brew_capacity 0.978→0.979（差異微小）；30g 深焙（retention=2.50）：free_water=325ml，brew_capacity 0.964→0.955（差異 −0.9%）；物理框架從「總注水量」升級為「真正可自由擴散的溶劑量」，與批次平衡方程式的定義嚴格對齊；§14 標注 calc_retention 本身為估算值，修正精度上限受截留率不確定性約束。
> ③**深焙焦澀協同（Ashy Synergy Penalty）**——理論斜率 `ASHY_SLOPE = 3.0` 可從酸澀協同按感官閾值比例推導；但深焙過萃已受三重壓制（SCORCH MEL、CGA 絕對閾值、非對稱 Huber），是否存在排名盲區需先以模擬驗證；**暫不寫入主體，實作完成後跑極端深焙場景確認排名後決定**。

> **相較 v5.4 的變更（Gemini 評估三條，全部採納，實作校正）：**
> ①**有限溶劑濃度梯度衰減（Finite Sink Correction）**——`_ey_max` 新增粉水比批次平衡修正 `brew_capacity = WATER_ML / (WATER_ML + dose × CONC_GRADIENT_COEFF)`；18g 時修正 −0.9%、30g 時 −1.5%，差異 ~0.6%——反映高豆量下溶液濃度對擴散驅動力的微弱反壓；Gemini 建議的 0.1%/g 線性方案在數值上保守合理但物理框架不精確（修改的是平衡極限而非速率常數），改以批次平衡方程式實作；
> ②**粉床時間壓實效應（Bed Compaction Multiplier）**——`calc_press_time` 新增 `steep_sec` 參數，壓降阻力乘數加入 `compaction_mult = 1 + (steep_sec/240) × BED_COMPACTION_COEFF(0.15)`；物理依據：長浸泡使細粉持續沉降遷移至濾紙面形成緻密阻水層，Swirl 僅部分重置；240s 浸泡的壓降阻力比 60s 高約 11%；
> ③**酸澀協同劣變懲罰（Harshness Synergy Penalty）**——`flavor_score` 新增第七層：當 AC 與 CGA 同時超過理想值時觸發交叉乘積指數懲罰 `exp(−HARSHNESS_SLOPE × ac_excess × cga_excess)`；SLOPE=4.0（與 CGA 澀感層設計一致）；單維超標不觸發（乘積為零），AC=1.3×+CGA=1.3× 扣 30%，AC=1.5×+CGA=1.5× 扣 63%——捕捉人類口腔中「金屬酸澀」的毀滅性交互作用。

---

## ── 版本審查意見（v5.4 → v5.5 建議評估，來源：Gemini）──

> 本節記錄 Gemini 對 v5.4 的三條建議的可行性判斷，作為 v5.5 版本依據。

### Gemini 建議一｜有限溶劑濃度梯度衰減（**採納，實作方式修正**）

**物理方向正確，但 Gemini 的框架與量級需要校正。**

**問題確認存在：** `calc_ey` 的一階動力學 `EY(t) = EY_max × (1 − e^{−kt})` 隱含無限稀釋假設（Infinite Sink）——溶液中的溶質濃度不影響擴散驅動力。但在批次浸泡系統中，水中的 TDS 隨萃取上升，濃度梯度（固體表面 vs 溶液本體）逐漸縮小，擴散驅動力衰減。

**量級評估：** 在 AeroPress（400ml）中，30g 豆 20% EY → TDS ≈ 1.78%。咖啡可溶固體的溶劑飽和濃度約 20–25%，當前 TDS 僅佔飽和的 **7%**——驅動力衰減確實小。但 18g 佔 **4%** vs 30g 佔 **7%**，差異 ~3 個百分點。在精密排序的 70,525 組合中，這微弱的差異仍可能影響邊界排名。

**Gemini 的 0.1%/g 線性扣減 EY_max 問題：** EY_max 是熱力學極限（咖啡豆結構中可萃物質的理論上限），由豆種與溫度決定，與水量**無關**——將 30g 豆泡在 400ml 或 4000ml 水中，EY_max 相同，只是達到它的速率不同。Gemini 將批次平衡效應錯置於熱力學極限上。

**修正實作：批次平衡方程式。** 在有限溶劑的批次系統中，平衡 EY 低於理論 EY_max：
$$EY_{eq} = EY_{max} \times \frac{V_{water}}{V_{water} + dose \times K_d}$$
其中 $K_d$ 為溶質分配係數。$K_d$ 越大，溶質越傾向停留在固體中。以 $K_d = 0.5$（極保守估算，對應咖啡可溶物在水中的高溶解度）：
- 18g：`400/(400+9)` = 0.978（修正 −0.9%）
- 30g：`400/(400+15)` = 0.964（修正 −1.5%）
- 差異：~0.6%（略小於 Gemini 的 1.2%，但物理框架正確）

**執行：** §0 新增 `CONC_GRADIENT_COEFF = 0.5`；§5 `calc_ey` 中 `_ey_max` 計算加入 `brew_capacity` 修正；§14 新增限制條目。

---

### Gemini 建議二｜粉床時間壓實效應（**採納**）

**流體力學論據正確。** 斯托克斯沉降使細粉隨時間遷移至濾紙面，形成緻密阻水層。60s 浸泡時粉床仍相對鬆散；240s 浸泡後大量細粉已沉積，壓降阻力顯著增加。Swirl 雖然擾動粉床，但並非完全重置——已嵌入粉層間隙的細粉不會被 5s 的輕柔旋轉完全懸浮。

**量級合理性：** `compaction_mult = 1.0 + (steep_sec/240) × 0.15`
- 60s 浸泡：阻力增加 3.8%（幾乎無感）
- 120s：+7.5%（邊際效應）
- 240s：+15%（顯著，在極細粉場景可能將 press_sec 推過 Channeling 閾值 60s）

**與 Channeling 的連動效應：** dose=24g + dial=3.5 + steep=60s → press=79s（舊值 ~76s）；steep=240s → press=88s（舊值 ~76s）。長浸泡使 Stall 機率上升，`apply_channeling` 的 bypass_ratio 加大，CGA 飆升，系統自動引導優化器避開「極細粉 + 大豆量 + 極長浸泡」的物理死角。

**執行：** §0 新增 `BED_COMPACTION_COEFF = 0.15`；§6 `calc_press_time` 加入 `steep_sec` 參數與壓實修正；§10 `optimize()` 調用同步更新；§14 新增限制條目。

---

### Gemini 建議三｜酸澀協同劣變懲罰（**採納，斜率調低至 4.0**）

**口腔感官化學論據完全正確。** 高酸值（AC）+ 高澀/苦值（CGA/CA）在缺乏甜感（SW）包覆時，會產生「金屬味」或「胃酸」的極端劣變感（Harshness）。此效應是**乘積性**的——單維超標（只有 AC 高或只有 CGA 高）雖然不好，但可以被其他風味維度部分補償；雙維同時超標則產生不可逆的感官崩潰。

現行六層評分中，AC 超標在 Huber Loss 扣分、甜酸比扣分；CGA 超標在 Huber Loss 扣分、醇苦比扣分、澀感閾值扣分——但這些懲罰是**獨立相乘**，不存在交叉聯動。「AC=1.3× + CGA=1.3×」的組合在每個層各扣一點，最終可能仍得到「尚可接受」的分數，但在真實杯中這是「難以下嚥」的金屬酸澀感。

**不採用 Gemini 的 SLOPE=8.0：** AC=1.2× + CGA=1.2× 的輕微雙超標扣 27% 過於激進。改為 SLOPE=4.0（與 CGA_ASTRINGENCY_SLOPE 設計一致）：

| AC/ideal | CGA/ideal | 乘積 | penalty（SLOPE=4.0）| 說明 |
|---------|----------|------|-------------------|------|
| 1.0 | 1.4 | 0 | 1.000 | 單維超標不觸發 |
| 1.2 | 1.2 | 0.04 | 0.852（−15%）| 輕微雙超標，適度懲罰 |
| 1.3 | 1.3 | 0.09 | 0.698（−30%）| 中度，足以拉低排名 |
| 1.5 | 1.5 | 0.25 | 0.368（−63%）| 等同斬首 |

**執行：** §0 新增 `HARSHNESS_SLOPE = 4.0`；§9 `flavor_score` 新增第七層酸澀協同懲罰；§9 架構表更新；§14 新增限制條目。

---

## ── 版本審查意見（v5.3 → v5.4 建議評估，來源：Gemini）──

> 本節記錄 Gemini 對 v5.3 的三條建議的可行性判斷，作為 v5.4 版本依據。

### Gemini 建議一｜修復幽靈萃取時間（**採納，正確性修復**）

**問題確認存在。** v5.3 的 `optimize()` 執行順序：
1. `press_sec = calc_press_time(dose, dial)`（理論壓降秒數，如 90s）
2. `press_equiv = press_sec × 0.15`（基於理論時間，如 13.5s）
3. `calc_ey(… press_equiv=13.5)` 與 `predict_compounds(… press_equiv=13.5)`
4. `display_press_sec` 計算（如 66s）——但此時萃取已用了 90s 的等效時間

**物理問題：** 當通道貫穿粉餅後，物理阻力瓦解，使用者實際壓降時間為 `display_press_sec`（66s），水與粉餅的真實接觸時間只有 66s。但動力學方程式收到的等效時間卻基於 90s，多注入了 `(90-66)×0.15 = 3.6s` 不存在的「幽靈萃取」。

**影響範圍：** 僅影響 Stall/Channeling 場景（press_sec > 60s）。非通道場景 display_press_sec = press_sec，零影響。Stall 場景的修正量 1–4s，屬小幅但邏輯正確。

**與 `apply_channeling` 的關係——兩者正交，非重複扣減：**
- **press_equiv（時間修正）**：水與粉餅的接觸「多久」→ 基於 display_press_sec
- **apply_channeling（分佈修正）**：在接觸時間內，水的流量有「多少比例」繞道 → 基於 press_sec 嚴重度代理

**執行：** §10 `optimize()` 中將 `display_press_sec` 計算移至 `press_equiv` 之前；`press_equiv = display_press_sec × PRESS_EQUIV_FRACTION`。`apply_channeling` 仍使用 `press_sec`（嚴重度代理不變）。

---

### Gemini 建議二｜解耦 CGA 澀感絕對閾值（**採納，生物學校正**）

**問題確認存在且影響顯著。**

**現行設計的缺陷：** v5.2 的質量分率正規化後，`actual_abs['CGA'] = fraction × tds`、`ideal_abs['CGA'] = ideal_prop × tds`。CGA 澀感層的 `cga_ratio = actual / ideal` 中 TDS 對消——ratio 完全不受 TDS 影響。這意味著 TDS=0.70% 的極稀薄杯與 TDS=1.50% 的濃縮杯，只要 CGA 的分率偏差相同，就會收到**完全相同的澀感懲罰**。

**生物學謬誤：** 唾液 PRP（富含脯氨酸蛋白）與多酚/CGA 結合沉澱是**絕對濃度觸發**的生物機制。每毫升液體中的 CGA 分子數必須超過某個閾值才能耗盡唾液潤滑層。TDS=0.70% 杯中的 CGA 絕對量極低，即使分率偏高也不足以觸發蛋白質沉澱；TDS=1.50% 杯中的 CGA 絕對量是前者的 2.1 倍，在口腔中更具攻擊性。

**數值驗證（M 焙，actual CGA fraction=0.10 vs ideal=0.07）：**

| 實際 TDS | 舊 ratio（TDS 盲）| 舊 penalty | 新 ratio（TDS 錨定）| 新 penalty | Δ |
|---------|------------------|-----------|-------------------|-----------|---|
| 0.70%   | 1.429 | 0.922 | 0.800 | 1.000 | +0.08（稀薄杯免罰，正確）|
| 1.25%   | 1.429 | 0.922 | **1.429** | **0.922** | 0（理想 TDS，基準不變）|
| 1.50%   | 1.429 | 0.922 | 1.714 | **0.576** | −0.35（濃縮杯加罰，正確）|

**實作：** `flavor_score` 中 CGA 層的分母改為 `build_ideal_abs(roast_code, TDS_PREFER[roast_code])['CGA']`，即以各焙度的理想 TDS 下的 CGA 絕對濃度為錨點。`actual_perceived['CGA']` 仍使用 `actual_fraction × actual_tds`（v5.2 正規化後的真實絕對值）。

**執行：** §9 `flavor_score` 層 6 CGA 分母更新；§9 架構表新增說明。

---

### Gemini 建議三｜實裝熱力學平均擴散率（**採納，修補恆溫假設高估**）

**問題確認存在且影響顯著。**

**現行設計的缺陷：** v5.2 的阿瑞尼斯修正 `k_base_dynamic = K_BASE × exp((t_slurry − 90) × 0.05)` 使用 `t_slurry`（漿體起始溫度，即最高溫度）。但水溫從 `t_slurry` 持續冷卻，實際的分子擴散速率隨溫度下降。使用最高溫度系統性**高估**整個浸泡期間的平均速率常數。

**高估幅度（v5.3 COOL_RATE=0.0008）：**

| 場景 | t_slurry | T_avg | ΔT | k 高估幅度 |
|------|---------|-------|------|----------|
| M 90°C steep=60s | 90.0°C | 88.2°C | 1.8°C | +9% |
| M 90°C steep=120s | 90.0°C | 86.7°C | 3.3°C | **+18%** |
| L+ 94°C steep=240s | 94.5°C | 87.8°C | 6.7°C | **+40%** |
| D 82°C steep=240s | 82.0°C | 76.5°C | 5.5°C | **+32%** |

長浸泡時高估 30–40%，是不可忽略的系統性偏差。

**修正：** 以牛頓冷卻定積分的時間平均溫度取代起始溫度：

$$T_{avg} = T_{env} + \frac{T_{slurry} - T_{env}}{r \cdot t} \cdot (1 - e^{-rt})$$

**數學性質：** 封閉解析解（非數值積分）；僅依賴 `(T_slurry, COOL_RATE, t_kinetic)`，與 k 無循環依賴；t→0 時 $T_{avg} \to T_{slurry}$（洛必達法則，邊界正確）。

數值驗證：解析解 vs 10,000 步辛普森積分，誤差 < 10⁻⁶ °C。

**執行：** §5 `calc_ey` 中 `T_avg` 計算插入 `t_kinetic` 之後、速率常數之前；`k_base_dynamic` 改用 `T_avg`；docstring 更新。

---

## ── 版本審查意見（v5.2 → v5.3 建議評估，來源：Gemini）──

> 本節記錄 Gemini 對 v5.2 的三條建議的可行性判斷，作為 v5.3 版本依據。

### Gemini 建議一｜修復牛頓冷卻率（**採納，數值從 Gemini 的 0.0005 調整至 0.0008**）

**Gemini 的物理診斷完全正確，這是系統中隱藏最深的物理錯誤。**

**問題本質：** `COOL_RATE = 0.02` 在牛頓冷卻模型 $T(t) = T_{env} + (T_{slurry} - T_{env}) \cdot e^{-rt}$ 中意味著：

| 浸泡時間 | r=0.02 時水溫（起始 90°C）| 物理現實 |
|---------|-------------------------|---------|
| 30s     | **60.7°C**（降 29°C）    | 荒謬：等同將水倒入冰水中 |
| 60s     | **44.6°C**（降 45°C）    | 荒謬：比室溫僅高 20°C |
| 120s    | **30.9°C**（降 59°C）    | 荒謬：幾乎等於室溫 |
| 240s    | **25.5°C**（降 64.5°C）  | 荒謬：等同冷水 |

**真實的 AeroPress 冷卻行為：** 400ml 水在密封塑膠圓筒（活塞隔絕蒸發）中，熱傳導極慢。基於 $r = hA/(mc)$ 的熱力學估算（h=8 W/m²K 自然對流、A=260 cm² 側面+底面、m=0.4 kg、c=4186 J/kgK），理論 r ≈ 0.00012。考慮實際因素（活塞不完全密封、薄壁塑膠熱導率、少量蒸發損失），合理範圍 **r ≈ 0.0005–0.001**。

**不採用 Gemini 的 0.0005 而取 0.0008 的原因：** 0.0005 對應 240s 降溫僅 7.4°C（90→82.6°C），略偏保守。咖啡社群實測數據（開蓋 AeroPress）顯示 120s 降溫約 5–8°C，加蓋後約 4–6°C。0.0008 對應 120s 降 5.9°C（合蓋場景中間值），較具代表性。

**對 T_eff 的衝擊：** M 焙 dial=4.5 浸泡 120s 時，`T_eff` 從舊值 **51.4°C**（虛幻低溫）回升至 **87.1°C**（接近漿體溫），EY_max 相應從 14.8% 升至 25.5%。

**K_BASE 是否需要連帶重新校正？** 數值驗算（L+ 100°C dial=4.0 dose=20g steep=120s + Arrhenius）：舊模型 EY=12.3%（低於 EY_MIN！），新模型 EY=20.0%——新值反而更合理，淺焙細研磨 2 分鐘浸泡達 20% EY 符合實際沖煮經驗。**K_BASE 暫不調整**，待實測折射儀數據校正（見 §15 第 3 點）。

**執行：** §0 `COOL_RATE` 從 0.02 修正為 0.0008；§14 新增限制條目（附不確定性範圍）。

---

### Gemini 建議二｜重構壓降萃取（**採納，架構重構**）

**問題診斷正確：齊頭式 EY 加法違反物質演變的差異性。**

**現行設計（v4.6–v5.2）的問題：**
```python
ey += min(press_sec * PRESS_KINETIC_COEFF, PRESS_KINETIC_MAX)  # 每秒 +0.0015% EY
```
壓降期間的萃取被簡化為對巨觀 EY 的扁平加法。這帶來兩個物理謬誤：
1. **所有物質等比例增加**：但實際上壓降時 CA 已近飽和（>93%），額外萃取集中於慢速物質（PS、CGA）
2. **不影響 compound profile**：`predict_compounds` 在壓降加法前已完成計算，compound ratio 不隨壓降而變化；v5.2 的質量分率正規化進一步讓 compound ratio 與 TDS 完全脫鉤，使壓降的化學演變完全消失

**重構設計：以等效時間注入動力學方程式**

```python
press_equiv = press_sec * PRESS_EQUIV_FRACTION   # 0.15，壓降效率≈被動浸泡的 15%
```

- **注入 `calc_ey`**：`t_kinetic = steep_sec + swirl_equiv + press_equiv`。雙峰動力學自然處理差異萃取——粗粉（低 k，未飽和）獲得有意義的 EY 增補，細粉（高 k，已飽和）幾乎不變。
- **注入 `predict_compounds`**：`effective_steep = steep_sec + press_equiv`。各物質的時間依賴項使用 effective_steep，讓 PS/CGA 的漸近線推進、AC 的相對衰減、CA 的飽和接近均透過物理公式自然運算，無需人為分配。

**驗算：** press_sec=60s → press_equiv=9s 被動浸泡等效。CA（K_CA=0.030）在 steep=120s 已萃 97.3%，再加 9s 提升至 97.9%（+0.6%，可忽略）；PS（K_PS=0.005）在 steep=240s 的 extra_time=120+9=129s，指數漸近線從 0.090 微升至 0.094（+4.4%，有意義）。動力學方程式自動分配差異貢獻，無需額外常數。

**連帶清理：** 移除 `PRESS_KINETIC_COEFF`、`PRESS_KINETIC_MAX` 兩個常數（被 `PRESS_EQUIV_FRACTION` 單一常數取代）。`optimize()` 中壓降時間計算前移至 `calc_ey` 之前。

**執行：** §0 移除 PRESS_KINETIC_COEFF/MAX，新增 PRESS_EQUIV_FRACTION=0.15；§5 `calc_ey` 新增 `press_equiv` 參數；§7 `predict_compounds` 新增 `press_equiv` 參數；§10 `optimize()` 流程重構；§14 新增限制條目。

---

### Gemini 建議三｜封堵線性時間破窗（**CGA 採納；AC 連帶修復；SW 維持不變**）

**CGA 線性無界增長——與 PS（v5.1 已修復）、CA（v4.3 已修復）的設計哲學矛盾。**

`CGA *= 1 + max(steep_sec - 150, 0) * 0.004`：在搜尋空間內（240s）最大 1.36×，但若未來擴展搜尋範圍（冷萃、長浸泡），600s 時 CGA 飆至 2.8×——完全脫離飽和現實。v5.1 已修復 PS（指數漸近線 K_PS=0.005），CGA 是最後一個殘留的線性時間增長物質。

**修正：** `CGA *= 1.0 + CGA_TIME_MAX × (1 − exp(−K_CGA_TIME × extra))`

| steep | 舊線性 | 新指數（K=0.015, MAX=0.50）| 差異 |
|-------|-------|---------------------------|------|
| 150s  | 1.000 | 1.000 | 0 |
| 180s  | 1.120 | 1.181 | +0.06 |
| 240s  | 1.360 | **1.370** | **+0.01**（搜尋空間內完美匹配）|
| 400s  | 2.000 | 1.488 | −0.51（飽和封頂）|
| 600s  | 2.800 | 1.499 | −1.30（收斂至 1.50×）|

**AC 線性衰減的連帶修復：** `AC *= 1 - max(steep_sec - 150, 0) * 0.003` 在 steep > 483s 時 **AC 變負**——物理不可能。替換為指數衰減 `AC *= exp(−K_AC_DECAY × extra)`，K_AC_DECAY=0.0035（240s 時精確匹配舊值 0.730，且永不為負）。

**SW 不需修改：** `SW *= 1 + min(steep_sec - 120, 60) * 0.002` 已透過 `min(_, 60)` 硬封頂於 1.12×。雖然硬封頂的導數在 steep=180s 處不連續，但在實際搜尋空間（15s 步長）中此不連續性被步長解析度掩蓋，修改收益極低。

**執行：** §0 新增 K_CGA_TIME=0.015、CGA_TIME_MAX=0.50、K_AC_DECAY=0.0035；§7 `predict_compounds` 中 CGA 與 AC 時間項更新。

---

## ── 版本審查意見（v5.1 → v5.2 建議評估，來源：Gemini）──

> 本節記錄 Gemini 對 v5.1 的三條建議的可行性判斷，作為 v5.2 版本依據。

### Gemini 建議一｜總質量分率正規化（**採納，定位降級：評分鑑別力優化，非致命缺陷**）

**Gemini 的物理觀察基本正確，但「致命缺陷」定性過度。**

**問題確認：** `predict_compounds` 回傳的 `actual_raw` 各物質加總約 2.5–3.5（AC=1.0, CA=1.0, SW=0.5, …），而 `IDEAL_FLAVOR` 的比例值加總約 1.0。在 `flavor_score` 中 `actual_abs = raw × tds`、`ideal_abs = prop × tds`，層 2 的 Huber 相對誤差 `(actual - ideal) / ideal` 中 TDS 對消，實際比較的是 `(raw[k] - prop[k]) / prop[k]`。由於 raw 數值系統性地比 prop 大 2~4 倍，所有組合的基底相對誤差都極大（≈3.0），真正有意義的比例差異被淹沒在基底偏移中。

**為何不是致命缺陷：** Gemini 聲稱「AI 會發瘋去壓低 TDS」不成立——TDS 在分子分母同時對消，conc_score 完全不受 TDS 大小影響。所有組合的基底偏移一致（L+ 的 AC 永遠從 1.0 起算），排名差異來自溫度/時間/研磨的微調，優化器**仍能正確排序**，只是 conc_score 的鑑別力被嚴重壓縮。

**採納理由：** 正規化後 `actual_fraction` 與 `ideal_prop` 在同一尺度（總和皆為 1.0），Huber Loss 真正反映六維比例偏差，conc_score 的鑑別力大幅提升，與 cosine_sim（同樣對尺度不變）形成互補而非冗餘。

**實作修正（在 `flavor_score` 入口處）：**
```python
total_raw = sum(actual_raw.values())
actual_fraction = {k: actual_raw[k] / total_raw for k in KEYS}
actual_abs = {k: actual_fraction[k] * tds for k in KEYS}
```

**連帶影響：** 正規化後 `actual_abs` 的絕對數值降低至與 `ideal_abs` 同尺度（各物質約 0.05–0.40%），`CONC_SENSITIVITY_FLOOR = 0.02` 的底板保護仍在預期範圍內不影響正常計算，無需調整。

**執行：** §9 `flavor_score` 步驟 0 新增正規化邏輯；§9 架構表新增正規化說明。

---

### Gemini 建議二｜阿瑞尼斯動態速率常數（**採納，物理化學完全正確**）

**問題診斷完全正確。** `calc_ey` 中 `K_BASE = 0.010` 是固定常數，速率常數 `k_b`、`k_f` 完全不隨溫度變化。溫度目前只影響熱力學極限 `EY_max`（透過 `T_eff`），而非萃取「速度」。但在真實的固液萃取中，擴散係數 D 遵循阿瑞尼斯方程式 $k \propto e^{-E_a / RT}$，高溫顯著加速分子運動，低溫減速——這正是冷萃需要 12 小時而熱沖 2 分鐘的根本原因。

**影響量化（AeroPress 溫度範圍 82–100°C）：**

| t_slurry | k_base_dynamic / K_BASE | 說明 |
|----------|------------------------|------|
| 82°C（D 焙典型）| exp((82-90)×0.05) = **0.67×** | 深焙低溫，萃取速率慢 33% |
| 90°C（基準）| 1.00× | 基準不變 |
| 93°C（L+ 30g 典型）| exp((93-90)×0.05) = **1.16×** | 淺焙高溫，速率快 16% |
| 100°C（L+ 18g 極端）| exp((100-90)×0.05) = **1.65×** | 極高溫，速率快 65% |

**設計決策：以 `t_slurry`（漿體溫）為溫度輸入，非 `temp`（壺溫）或 `T_eff`。** 理由：
1. `t_slurry` 是咖啡粉與水的實際接觸溫度，決定初始擴散驅動力
2. 避免 `k → T_eff → k` 的循環依賴（`T_eff` 本身是 k 的函數）
3. 與 v4.9 SCORCH_PARAMS 使用 `t_slurry` 的設計一致

**修正公式（在 `calc_ey` 速率常數計算前）：**
```python
ARRHENIUS_COEFF = 0.05   # 每 °C 約 ±5% 速率變化
k_base_dynamic = K_BASE * math.exp((t_slurry - 90) * ARRHENIUS_COEFF)
```

**連帶影響：** `k_b`、`k_f` 均以 `k_base_dynamic` 取代 `K_BASE` 計算。`K_BASE = 0.010` 保留為 90°C 基準常數，物理語意不變。高溫場景（L+）的萃取速率增加 → EY 提升幅度大於舊模型，與實際沖煮經驗一致（淺焙高溫短時間即可達標 EY）；深焙低溫場景速率降低 → EY 提升較慢，需要更長浸泡或更細研磨補償，同樣符合實際。

**執行：** §0 新增 `ARRHENIUS_COEFF = 0.05`；§5 `calc_ey` 速率常數計算更新；§14 新增限制條目。

---

### Gemini 建議三｜通道效應阻力崩潰（**採納，定位為 UI 輸出修正**）

**物理觀察精準。** 當通道（Channel）一旦貫穿粉餅，水找到阻力最小路徑，物理阻力瞬間瓦解——活塞會「噗」一聲快速壓到底。在已發生嚴重 Channeling 的粉餅上「緩慢均勻施壓 90 秒」是物理上不可能的操作。使用者依照食譜看到「press 90s」會感到困惑。

**不修改 `apply_channeling` 內部邏輯的原因：** `press_sec` 在 `apply_channeling` 中是通道效應嚴重度的**代理指標**（press_sec 越長 → 粉餅阻力越高 → channeling 越嚴重 → bypass_ratio 越大）。這個計算本身是正確的，修改 press_sec 會破壞嚴重度估算的邏輯基礎。

**正確設計：新增 `display_press_sec`，僅影響輸出層。**

```python
# 在 optimize() 中，apply_channeling 之後計算顯示用壓降時間
if press_sec > CHANNELING_PRESS_THRESHOLD:
    # 超過 60s 的部分，因通道形成阻力瓦解，實際操作時間僅剩原本的 20%
    display_press_sec = int(
        CHANNELING_PRESS_THRESHOLD + (press_sec - CHANNELING_PRESS_THRESHOLD) * CHANNELING_COLLAPSE_RATIO
    )
else:
    display_press_sec = press_sec
```

| 內部 press_sec | display_press_sec | 說明 |
|---------------|-------------------|------|
| 55s           | 55s               | 未達閾值，正常顯示 |
| 70s           | 62s               | 超過 10s → 實際只多 2s |
| 90s           | 66s               | 超過 30s → 實際只多 6s |

**執行：** §0 新增 `CHANNELING_COLLAPSE_RATIO = 0.20`；§10 `optimize()` 新增 `display_press_sec` 計算；輸出結果中 `press_sec` 欄位改用 `display_press_sec`（內部 `press_sec` 保留供 `apply_channeling` 使用）；§14 新增限制條目。

---

## ── 版本審查意見（v5.0 → v5.1 建議評估，來源：Gemini）──

> 本節記錄 Gemini 對 v5.0 的三條建議的可行性判斷，作為 v5.1 版本依據。

### Gemini 建議一｜PS 線性時間破窗（**採納**）

**Gemini 診斷完全正確。** v5.0 的 `PS += max(steep_sec - 120, 0) * 0.002` 是線性公式，`min(PS, 1.0)` 的硬上限是懸崖而非漸近線——到達 1.0 前仍線性無限增長，違反固液萃取的一階動力學本質。

對照系統內部已有的動力學設計：CA 使用 `1 - exp(-K_CA × t)`，EY 使用雙峰動力學——PS 是唯一殘留的線性時間項，邏輯不一致。

**執行：** 採用 Gemini 建議的指數公式（`k_ps=0.005`，飽和值 0.2），替換 PS 時間線性項。`k_ps=0.005` 對應 PS 大分子（MW > 10,000 Da）的極慢擴散速率：240s 時貢獻約 0.090（舊線性 = 0.24），物理上更保守也更真實。

---

### Gemini 建議二｜GH 鈣鎂盲點（**採納，簡化實作**）

**化學論點正確。** Mg²⁺（小電荷半徑，親極性小分子）偏好萃取 AC/SW；Ca²⁺（偏向大分子）偏向 PS/CGA。目前系統中鳳林 Brita（GH=32，多 Ca）與鳳林 BWT（GH=22，多 Mg）的差異只體現在 EY 乘數幅度，`predict_compounds` 完全無視離子組成，抹殺水質微調意義。

**簡化實作決策：** 不引入完整 Ca/Mg 雙輸入（使用者負擔過重），以 `water_mg_frac`（GH 中鎂離子比例，0–1）為單一參數：
- 預設值 `0.40`（台灣一般自來水 Ca 偏多）
- BWT 預設設為 `0.90`（幾乎全 Mg）
- Aquacode 設為 `0.73`（原廠 Ca:Mg=1:2.7，Mg 佔 73%）
- 各 preset 補充 `mg_frac` 估算值

**影響幅度：** `mg_frac` 對各物質的修正上限各為 ±8%（`mg_frac` 在 0→1 的最大乘數範圍），不破壞現有評分量級。

---

### Gemini 建議三｜CGA 澀感生物閾值（**採納，修改實作方式**）

**口腔生物學論點完全正確。** CGA/多酚與唾液 PRP（富含脯氨酸蛋白）結合沉澱是觸覺而非味覺，存在真實的感官閾值。現有 `ASYM_BITTER_MULT=1.5` 的平滑 Huber Loss 無法捕捉這種「閾值後瞬間崩潰」的特性。

**不採用硬截斷 Guillotine（`score × 0.6`）的理由：** 違反 v4.5 以來確立的「消除評分斷崖」設計原則（SCORCH_PARAMS 連續矩陣就是為此而生）。CGA 超標 1% 時評分瞬降 40% 的硬切與系統哲學矛盾，且會讓優化器在閾值附近產生非連續行為。

**修改後實作：** 使用**指數衰減懲罰乘數**——在 CGA 超過理想值 `1.25×` 後觸發，超標越多懲罰指數加重：
- `excess_ratio = actual_CGA / (ideal_CGA × 1.25) - 1.0`
- `cga_penalty = exp(-CGA_ASTRINGENCY_SLOPE × excess_ratio²)`，斜率設為 4.0
- `actual_CGA / ideal_CGA = 1.25（剛超閾值）` → penalty ≈ 1.00（幾乎無懲罰）
- `actual_CGA / ideal_CGA = 1.50` → penalty ≈ 0.75（扣 25%）
- `actual_CGA / ideal_CGA = 1.75` → penalty ≈ 0.37（扣 63%，等同斬首）
- 函數連續，但閾值後陡峻，生物效果等同建議，評分不出現斷崖。

---

**Gemini 引述的化學知識正確（有機酸不揮發、質量只增不減），但批評了錯誤的對象。**

`predict_compounds` 的 docstring 明確說明：**「回傳各物質『萃取質量強度』（mass，未正規化）」**——這個輸出不是絕對物理質量，是**六維相對強度向量**，通過 `actual_raw[k] * tds` 縮放後才進入評分。

`AC *= 1 - max(steep_sec - 150, 0) * 0.003` 的正確語意是：**長時間萃取後，SW、PS、CGA 大量湧出，AC 在六維輪廓向量中的相對比重下降**——這建模的是「感知上酸感被其他物質遮蔽」的效果，在質量層以比重變化表達，與感知層分離的設計一致。

此設計與 KH 的架構對稱：KH 不在質量層扣 AC，而在感知層修正（v4.0 決定）；時間的酸感遮蔽同樣在質量層以相對比重變化建模，不引入第二套感知修正路徑。

**Gemini 建議的方案問題：** `AC *= 1.0 + (min(steep_sec, 90) / 90) * 0.1` 讓 AC 在 steep > 90s 後完全靜止，與 CGA（長浸泡顯著增加）、SW（中期緩慢增加）的動態不對稱，破壞六維向量在時間維度的邏輯一致性。

**執行：** 不修改程式碼；在 `predict_compounds` docstring 補充架構說明，防止未來產生相同誤解。

---

### Gemini 建議二｜物質專屬感官底板（**不採納，批評前提數學計算錯誤**）

**Gemini 的批評前提存在數學錯誤。**

Gemini 聲稱：「L+ MEL 的理想值約 0.04，底板 0.02 佔了其濃度的 50%，造成極端寬容。」

實際計算：`ideal_abs['MEL'] = IDEAL_FLAVOR[('L+', 'low')]['MEL'] × TDS = 0.04 × 1.35 ≈ **0.054**`

**0.054 > 0.02，底板完全不觸發。** `CONC_SENSITIVITY_FLOOR = 0.02` 的設計意圖是數值穩定安全網，只在 `ideal_abs[k] < 0.02` 時才介入——在現有 IDEAL_FLAVOR 表的所有焙度 × TDS 錨點組合中，所有物質的 `ideal_abs` 均遠高於 0.02，底板對正常評分計算**零影響**。

**Gemini 的 `CONC_FLOOR_DICT['MEL'] = 0.005` 反而是倒退：** 0.005 < 0.02，等於把 v4.9 的保護削弱；而 `CONC_FLOOR_DICT['SW'] = 0.03` 比 0.02 略大，對 SW（ideal ≈ 0.35~0.50）同樣不觸發，無實際意義。

**執行：** 不修改程式碼；在 §9 的 `CONC_SENSITIVITY_FLOOR` 旁補充觸發條件說明（`ideal < 0.02 才生效`），澄清底板的實際覆蓋範圍。

---

### Gemini 建議三｜TDS 水感動態懲罰權重（**採納，數值重新設計**）

**問題描述真實存在。** `_W3 = 0.10` 固定上限讓 TDS 最多扣 10%，在理論上允許「比例完美但極淡（TDS ≈ 0.67%）」的組合以 ~88 分擊敗「濃度理想但比例稍差（TDS 1.35%）」的 85 分組合。

**Gemini 的 `W3_LOW = 0.35` 數值過激：** 最差連乘 `(1-0.15)(1-0.12)(1-0.35) ≈ 0.497`，扣 50%——TDS 稍低即被斬首，扣分曲線過於不連續。

**重新設計：** `TDS_W3_LOW = 0.25`（水感嚴懲）/ `TDS_W3_HIGH = 0.10`（高濃度維持寬容）。

驗算最差情況（TDS 極低，tds_gauss ≈ 0）：
`(1-0.15) × (1-0.12) × (1-0.25) = 0.85 × 0.88 × 0.75 = 0.561`，最多扣約 44%。
TDS 偏低 0.3%（目標 1.35% → 實際 1.05%）：`tds_gauss = exp(-0.5×(0.3/0.15)²) = 0.135`，
`tds_factor = 1 - 0.25 + 0.25×0.135 = 0.784`，扣 22%——足以制裁但不斬首。

**執行：** §0 移除固定 `_W3`，新增 `TDS_W3_LOW = 0.25` / `TDS_W3_HIGH = 0.10`；§9 `flavor_score` 層 5 更新為動態權重；§9 架構表更新最大影響說明；§14 新增限制條目。

---

## ── 版本審查意見（v4.8 → v4.9 建議評估，來源：Gemini）──

> 本節記錄 Gemini 對 v4.8 的三條建議的可行性判斷，作為 v4.9 版本依據。

### Gemini 建議一｜高溫劣變壺溫/漿體溫錯位（**採納，但不採用 Gemini 的修正方案**）

**現象診斷正確。** Scorching 判斷目前使用 `temp`（壺溫），但熱裂解發生在咖啡粉與水的實際接觸介面，應以 `t_slurry`（漿體起始溫）為準。以極端案例說明差距：

| 場景 | temp（壺溫）| t_slurry（漿體溫）| 錯位幅度 |
|------|-----------|-----------------|---------|
| 30g 豆，96°C | 96°C | 96 − 4.5 − 2.5 = **89°C** | 7°C |
| 18g 豆，96°C | 96°C | 96 − 2.7 − 2.5 = **90.8°C** | 5.2°C |

D 焙的 SCORCH_PARAMS 閾值為 88°C：壺溫 96°C（30g 場景）t_slurry=89°C，仍觸發但 excess 從 8°C 縮至 1°C，懲罰大幅收斂。LM/M 的中溫焙度在壺溫 96°C、t_slurry 89°C 時，壺溫會觸發 LM 的懲罰（閾值 97°C 未超過，安全）——但 M 的閾值 95°C 在壺溫 96°C 時觸發 1°C，t_slurry=89°C 時不觸發，這才是真正的錯殺場景。

**不採用 Gemini 的方案原因：** Gemini 建議回退至 `if roast_code in ['MD', 'D'] and t_slurry > 92` 的硬切，這是對 v4.5 已消除之評分斷崖的倒退。正確做法是維持 `SCORCH_PARAMS` 連續閾值矩陣，僅將輸入從 `temp` 替換為 `t_slurry`。

**連帶調整：** `t_slurry_val` 目前在 `optimize()` 中是在 `flavor_score` 呼叫**之後**才計算，需要提前至評分前；`flavor_score` 簽名加入 `t_slurry` 參數取代 `temp`（`temp` 仍保留在迴圈，供輸出記錄使用）。

**執行：** `optimize()` 中 `t_slurry_val` 計算提前；`flavor_score` 簽名 `temp` → `t_slurry`；§9 Scorching 計算更新；§9 架構表說明更新。

---

### Gemini 建議二a｜濾紙 PS 吸附係數（**不採納，量對消的無效修正**）

**設計定位理解錯誤。** `predict_compounds` 的輸出是各物質的**相對強度向量**，`IDEAL_FLAVOR` 的目標向量同樣以真實杯中飲料（已通過紙濾）校準。加入 `FILTER_PAPER_PS_RETENTION = 0.90` 後，`actual_abs['PS']` 與 `ideal_abs['PS']` 同乘 0.9，Huber Loss 的相對誤差 `(actual - ideal) / ideal` **完全不變**，對 70,525 組合的排名零影響。

若要真正建模濾材差異，需為「紙濾」vs「金屬濾」建立兩套 `IDEAL_FLAVOR` 目標向量——超出當前系統範疇，列入 §15 第 14 點待辦。

---

### Gemini 建議二b｜Spritzer / Jeju 水質預設（**採納，直接實裝**）

台灣咖啡圈常用礦泉水，GH/KH 以品牌公開資料估算，標注待實測核對。

---

### Gemini 建議三｜微量物質相對誤差底板（**部分採納，數值設計重構**）

**問題存在但量級被誇大。** L+ 下 MEL 翻倍誤差對 `conc_score` 的實際扣分約 6%（`WEIGHTS['MEL']=1.0` 被 `_WEIGHT_TOTAL=7.8` 稀釋），不至於「摧毀總分」。但底板機制的正確用途是確保**數值穩定性**——防止浮點精度問題在極低濃度場景下放大 Huber Loss。

**Gemini 數值設計的問題：** `COMPOUND_SENSITIVITY_FLOOR['MEL'] = 0.10` 比 L+ 的 `ideal_abs['MEL'] ≈ 0.054` 還大，分母被人為抬高，相當於系統性降低 MEL 評分敏感度，副作用遠大於收益。

**採用的設計：** 全局統一底板 `CONC_SENSITIVITY_FLOOR = 0.02`（僅在 `ideal_abs[k] < 0.02` 時介入，保護極端稀薄場景而不干擾正常物質）。`_CONC_FLOOR = 1e-8` 原有零保護仍保留，兩者語意不同（前者防誇大懲罰，後者防除以零）。

**執行：** §0 新增 `CONC_SENSITIVITY_FLOOR = 0.02`；§9 層 2 分母更新；`_CONC_FLOOR` 保留於比率計算層。

---

## ── 版本審查意見（v4.6 → v4.7 建議評估，來源：Gemini）──

> 本節記錄 Gemini 對 v4.6 的三條建議的可行性判斷，作為 v4.7 版本依據。

### Gemini 建議一｜TDS 溶質質量守恆修正（**採納，化學定義正確**）

**化學論據正確。** TDS（Total Dissolved Solids）的嚴格定義是 `溶質質量 / 溶液總質量`，溶液總質量 = 溶劑（水）+ 已溶出固體。v4.6 的 `calc_tds` 分母僅含純水質量，確實是化學意義上的高估。

**數值影響量化：**

| 場景 | 分母（舊）| 分母（新）| TDS 差值 |
|------|---------|---------|---------|
| 30g 豆，EY=20%，截留=2.30 | 331.0g | 337.0g | +0.033% |
| 18g 豆，EY=18%，截留=2.10 | 362.2g | 365.4g | +0.009% |
| 24g 豆，EY=22%，截留=2.20 | 347.2g | 352.5g | +0.020% |

0.03% 的修正量雖然在人類感官層面幾乎不可見，但在非對稱高斯評分（SIGMA_LOW=0.15%）中，仍對評分排序產生系統性偏移——尤其是 TDS 接近目標的邊際組合。修正邏輯清晰、無副作用。

**執行：** `calc_tds` 函數更新，docstring 同步。

---

### Gemini 建議二｜PS 多糖體熱力學驅動係數（**採納，補上物理漏洞**）

**物理論據正確。** `predict_compounds` 中 AC、SW、CGA、MEL 均有溫度項，唯獨 PS 完全不受水溫影響——這與多糖體（大分子碳水化合物，MW 通常 > 10,000 Da）的溶解物理不符：

- 多糖體的細胞壁游離是吸熱過程（Endothermic），高溫顯著提升溶解驅動力
- 低溫（<85°C）下，無論浸泡多久，大分子仍難以穿越細胞壁進入溶液
- 現有模型等同「溫度與 Body 無關」，在 L+ 的高溫搜尋空間下尤其離譜

**細節調整：** 溫度乘數 `1.0 + (temp - 90) * 0.015` 在低溫端（如 D 焙的 82°C）給出 0.88× 是物理正確的（低溫確實少），但夾緊 `PS = min(PS, 1.0)` 必須在溫度修正後執行，以防止高溫場景突破 PS 的最大值。

**執行：** `predict_compounds` 中 PS 計算區塊加入溫度乘數，`min(PS, 1.0)` 移至溫度修正後。

---

### Gemini 建議三｜壓降漸近線修正（**不採納，批評的 Bug 不存在，改為語意整齊性修正**）

**Gemini 引述的破窗公式不存在於 v4.6。** Gemini 批評的公式 `press_sec * PRESS_KINETIC_COEFF * K_BASE * 100` 從未出現在任何版本的企劃書中——這是 Gemini 對程式碼的錯誤引述或幻覺生成。

**v4.6 的實際實作（第 1367 行）：**
```python
ey = round(min(ey + press_sec * PRESS_KINETIC_COEFF, ey + PRESS_KINETIC_MAX), 3)
```

`PRESS_KINETIC_MAX = 2.0` 確保 EY 最多被加 2%，而 `calc_ey` 出口本身已有 `min(ey, EY_ABSOLUTE_MAX)` 夾緊。Gemini 描述的「90s 壓降硬加 1.5% 打破 28% 天花板」在現有程式碼中物理上不可能發生。

**但現有夾緊邏輯有語意問題值得修正：** `min(ey + press_sec * coeff, ey + MAX)` 夾緊的是相對增量，若原始 EY 已是 27.5%，上限是 29.5%，再由外層截斷到 28%——語意不直觀，且依賴外層的隱性保護。改為對 `EY_ABSOLUTE_MAX` 的絕對夾緊 `min(ey + press_sec * PRESS_KINETIC_COEFF, EY_ABSOLUTE_MAX)` 語意更清晰，自給自足。此為**語意整齊性修正**，非 Gemini 描述的漸近線 Bug 修復。

**Gemini 的指數衰減方案不採納：** `(EY_ABSOLUTE_MAX - ey) * (1 - exp(-k * press_sec))` 雖然物理上更優雅，但引入了 `k_press = K_BASE * PRESS_KINETIC_COEFF` 的混合常數，語意模糊（K_BASE 是速率常數，PRESS_KINETIC_COEFF 是折算係數，兩者相乘沒有物理單位意義），且在壓降 30–90s 的實際範圍內，指數曲線與線性近似的差異遠小於係數估算誤差。

**執行：** 壓降補正夾緊改為 `min(ey + press_sec * PRESS_KINETIC_COEFF, EY_ABSOLUTE_MAX)`；docstring 更新說明此為絕對夾緊；§14 不新增限制條目（原有的「壓降萃取折算係數為估算值」已涵蓋）。

---

## ── 版本審查意見（v4.5 → v4.6 建議評估，來源：Gemini）──

> 本節記錄 Gemini 對 v4.5 的三條建議的可行性判斷，作為 v4.6 版本依據。

### Gemini 建議一｜時序悖論（**不採納，Bug 不存在於 v4.5**）

**Gemini 的批評描述的問題在 v4.5 中根本不存在。** 請核對 v4.5 §10 `optimize()` 的實際執行順序（行號為 v4.5 版本）：

```python
ey = calc_ey(...)                                          # 步驟 1：理論 EY
press_sec = calc_press_time(...)                           # 步驟 2：壓降時間
compounds_raw = predict_compounds(...)                     # 步驟 3：理論物質
ey, compounds = apply_channeling(ey, compounds_raw, ...)  # 步驟 4：通道修正
tds = calc_tds(roast_code, dose, ey, dial)                # 步驟 5：TDS 用修正後 EY ✅
ideal_abs = build_ideal_abs(roast_code, tds)              # 步驟 6：理想目標用修正後 TDS ✅
score = flavor_score(...)                                  # 步驟 7：評分
```

`apply_channeling` 已明確在 `calc_tds` **之前**執行，TDS 與理想目標均基於通道效應後的真實 EY 計算。Gemini 描述的「質量不守恆」正是 v4.5 設計的解決目標，且已正確實現。

**推測原因：** Gemini 可能批評的是 v4.4 或更早版本的狀態（在 v4.5 引入 `apply_channeling` 之前，確實沒有此邏輯），或在閱讀 v4.5 程式碼時遺漏了修正後的執行順序。

**執行：** 不修改任何程式碼；此說明記入版本審查節，建議未來收到 Gemini 建議時優先核對程式碼行號。

---

### Gemini 建議二｜SW 甜感峰值焙度動態化（**採納，化學論據正確**）

**化學論據充分正確。** 現有公式 `SW *= 1 - abs(temp - 90) * 0.01` 假設所有焙度的甜感溶出峰值均在 90°C，與烘焙物理不符：

- **極淺焙（L+）**：生豆細胞壁緊密，大分子焦糖化產物需要高溫（95–98°C）才能有效溶出；90°C 只能萃出尖銳的有機酸，甜感幾乎缺席
- **深焙（D）**：細胞壁已在烘焙時大量破壞，甜感物質（焦糖降解產物）在 83–85°C 即可溶出；超過 88°C 反而讓焦苦調性（MEL 的 Ashy 感）蓋過甜感

**修正公式：** `optimal_sw_temp = ROAST_TABLE[roast_code]['base_temp'] - 2`

| 焙度 | base_temp | optimal_sw_temp | 舊峰值溫度 |
|------|-----------|----------------|-----------|
| L+   | 100°C     | 98°C           | 90°C（差 8°C）|
| L    | 99°C      | 97°C           | 90°C |
| LM   | 95°C      | 93°C           | 90°C |
| M    | 92°C      | 90°C           | 90°C（相同）|
| MD   | 88°C      | 86°C           | 90°C |
| D    | 85°C      | 83°C           | 90°C（差 7°C）|

M 焙的峰值恰好與舊值一致（90°C），確認 M 焙是設計錨點，修正方向合理。`-2` 係數為估算值，記入 §14。

**執行：** §7 `predict_compounds` 中 SW 溫度修正公式更新；§14 新增限制條目。

---

### Gemini 建議三｜壓降隱形萃取（**部分採納，設計重構**）

**物理論據成立：** 壓降期間（30–90s）熱水依然接觸咖啡粉，確實持續萃取——尤其是長時間 Stall 場景，額外接觸時間對 CGA 和 PS 的後段慢速物質影響不可完全忽略。

**設計顧慮與重構：** Gemini 建議將 `press_sec * 0.3` 直接加回 `t_kinetic`，但這會引入循環依賴：`calc_ey` 需要 `press_sec` → `press_sec = calc_press_time(dose, dial)` → `dial` 和 `dose` 已是迴圈變數，本身沒有依賴問題，但修改 `t_kinetic` 會讓 EY 同時被壓降萃取**增加**又被 `apply_channeling` **減少**，在 `calc_ey` 函數內外各自修正 EY 的不同面向，邏輯分散、難以追蹤。

**更乾淨的設計：** 壓降萃取作為獨立的微量 EY 增補，緊接 `apply_channeling` 之後、`calc_tds` 之前：

```python
ey += min(press_sec * PRESS_KINETIC_COEFF, PRESS_KINETIC_MAX)
```

常數：`PRESS_KINETIC_COEFF = 0.0015`（每秒增加 0.15% EY，60s 壓降 +0.9%、90s +1.35%）；上限 `PRESS_KINETIC_MAX = 2.0`（最多 +2% EY，避免過度補償）。

**物理直覺驗算：** 60s 正常壓降 +0.9% EY（合理，壓降是動態流速萃取，效率低於浸泡）；90s Stall → 先 Channeling 扣 15% EY，再補 +1.35%，淨效果仍是大幅衰減，符合物理現實。

**執行：** §0 新增 `PRESS_KINETIC_COEFF = 0.0015`、`PRESS_KINETIC_MAX = 2.0`；§10 `optimize()` 在 `apply_channeling` 後加入壓降萃取補正；§4.3 接觸時間說明更新；§14 新增限制條目。

---

## ── 版本審查意見（v4.4 → v4.5 建議評估，來源：Gemini）──

> 本節記錄 Gemini 對 v4.4 的三條建議的可行性判斷，作為 v4.5 版本依據。

### Gemini 建議一｜常態化研磨空間（**不採納，誤解系統設計邊界**）

**技術擔憂成立，但前提錯誤。** 本系統**自 v1.0 起即明確標注為 1Zpresso ZP6 專用系統**。§4.4 的研磨參考表已列出 Comandante、Timemore 等主流磨豆機的對應刻度，正確使用方式是使用者查表換算後輸入 ZP6 等效刻度（例如 Comandante 13 clicks ≈ ZP6 4.5）——而非直接輸入其他機型的原始刻度值。

**引入 `G_norm` 重構底層物理常數的問題：**
1. **語意損失：** 物理公式的常數（如 `DARCY_PRESS_EXP=0.6`、`FINES_RATIO_DIAL_SLOPE=0.04`）目前具有真實物理意義，可與 ZP6 的實測數據直接對應校正。改為無單位 G_norm 後，所有常數失去直接可校正性。
2. **線性換算誤差：** 不同磨豆機的細粉分佈（fines distribution）在相同「粗細程度」下物理特性不同——Comandante 16 clicks 的粒徑標準差與 ZP6 6.5 不同，線性正規化會引入比現有近似更大的系統誤差。
3. **代價不對稱：** 重構影響全部物理函數（`calc_fines_ratio`、`calc_retention`、`calc_press_time`、`calc_swirl_wait`）；而正確使用方式（查表換算）已在 §4.4 提供，使用者負擔極低。

**本次執行：** §4.4 研磨參考表加入「建議 ZP6 等效刻度」欄位，並在說明中明確標注系統的磨豆機設計邊界與換算邏輯，不重構底層公式。

---

### Gemini 建議二｜通道效應物理懲罰（**採納，架構調整**）

**流體力學論據完全正確：** AeroPress 在極細粉（dial≤3.8）+ 大豆量（dose≥26g）的高壓場景下，確實會發生 Channeling（水流繞道通過阻力最小路徑）。結果是：流經通道的局部粉層嚴重過萃（CGA 飆升、咬喉澀感），未接觸水的粉餅死角完全未萃取，整體巨觀 EY 反而下降。v4.4 的 `calc_press_time` 已能預測 Stall（>60s），但此資訊從未反饋至 EY 或物質計算。

**架構調整：** Gemini 建議將懲罰寫在「計算完 EY 與 Compounds 後進行後處理」，但若直接修改 EY 後才調用 `calc_tds`，TDS 使用的是未修正 EY，會產生內部不一致。

正確設計是新增獨立函數 `apply_channeling(ey, compounds, press_sec)`，在 `optimize()` 中於 EY/Compounds 計算後、`calc_tds` 調用前統一套用——確保 EY、TDS、Compounds 三者的一致性。

**閾值：** `CHANNELING_PRESS_THRESHOLD = 60s`（Stall 邊界）；`CHANNELING_EY_SLOPE = 0.005`（每多 1s 降低 0.5% EY）；`CHANNELING_CGA_MULT = 2.5`（CGA 非線性放大倍率，對應局部過萃的嚴重性）。夾緊：bypass_ratio 上限 0.15（最多 15% 的水走旁路）。

**執行：** §0 新增三個 Channeling 常數；§6 後新增 `apply_channeling()` 函數；§10 `optimize()` 更新計算順序；§14 新增限制條目。

---

### Gemini 建議三｜連續焙度劣變閾值（**採納，數值重新設計**）

**數學論據成立：** v4.4 的 `if roast_code in ('MD', 'D')` 硬切確實會在 M→MD 邊界產生評分斷崖——相同水溫（例如 92°C），M 焙零懲罰，MD 焙已被懲罰，而 M 焙 CGA 基礎量通常比 MD 更高（烘焙時 CGA 降解較少），高溫水解量可能更大。

**數值重新設計：** Gemini 的 `L+ = 102°C、L = 100°C` 閾值在沸點夾緊後永遠不可達（L+ 最高 100°C、L 最高 100°C），等同關閉懲罰——設計無意義。改為以「各焙度的 base_temp + 3°C 上限」作為參考，閾值設在搜尋空間上端附近的有效溫度：

| 焙度 | 搜尋上限 | Scorch 閾值 | 靈敏度 | 說明 |
|------|---------|------------|-------|------|
| L+   | 100°C   | 100°C      | 0.00  | 沸點夾緊，無法觸發，關閉 |
| L    | 100°C   | 100°C      | 0.00  | 同上，關閉 |
| LM   | 98°C    | 97°C       | 0.05  | 接近搜尋上限時輕微懲罰 |
| M    | 95°C    | 95°C       | 0.08  | 在搜尋上限觸發，適度懲罰 |
| MD   | 91°C    | 91°C       | 0.15  | 搜尋上限即觸發，嚴格懲罰 |
| D    | 88°C    | 88°C       | 0.20  | 搜尋上限即觸發，最嚴格 |

> 注：MD/D 的 Scorch 閾值刻意設在各自的搜尋上限，意即「深焙用最高允許溫度就已觸發輕微懲罰」，強制引導優化器選擇較低溫度。

同時移除 §0 的 `SCORCHING_TEMP_THRESHOLD`、`SCORCHING_CGA_SLOPE`、`SCORCHING_MEL_SLOPE` 三個舊常數（合併進 `SCORCH_PARAMS` 字典）。MEL 的高溫劣變仍只對 MD/D 生效，但現在透過 `SCORCH_PARAMS` 的 `mel_sensitivity` 欄位控制（L+～M 設為 0.0）。

**執行：** §0 移除舊 Scorching 常數，新增 `SCORCH_PARAMS` 字典（含 threshold、cga_sensitivity、mel_sensitivity）；§9 `flavor_score` 感知過濾器更新；§14 更新限制條目。

---

## ── 版本審查意見（v4.3 → v4.4 建議評估，來源：Gemini）──

> 本節記錄 Gemini 對 v4.3 的三條建議的可行性判斷，作為 v4.4 版本依據。

### Gemini 建議一｜100°C 沸點夾緊（**採納，真實 Bug**）

**診斷正確。** `ROAST_TABLE['L+']['base_temp'] = 100`，搜尋迴圈 `range(100-3, 100+4)` 會產生 101°C、102°C、103°C 三個在標準大氣壓下物理上不存在的水溫值。這些虛擬高溫會產生系統性偏高的 EY 與 TDS 預測，並可能被推薦為第 1 名——一個手沖壺永遠無法執行的食譜。

> 補充：花蓮市海拔約 10 公尺，沸點約 99.97°C，實際上 100°C 已是可執行上限。高海拔地區（如 SCA 訓練規範提醒）沸點更低，未來可加入海拔修正常數。

**修正：** 在 `optimize()` 的溫度範圍計算中加入夾緊：`max_temp = min(base_temp + 3, TEMP_BOILING_POINT)`，並在 §0 新增 `TEMP_BOILING_POINT = 100`。

**執行：** §0 新增 `TEMP_BOILING_POINT = 100`；§3 搜尋空間說明更新；§10 `optimize()` 溫度迴圈修正。

---

### Gemini 建議二｜Swirl 時溫積分錯位（**不採納，數學論據不成立**）

**Gemini 的現象描述正確**（Swirl 確實發生在末端低溫），但**對現有公式的批評在數學上不成立**。

`_calc_t_eff` 是速率加權有效溫度的**封閉解析積分**：

$$T_{eff} = T_{env} + (T_{slurry} - T_{env}) \cdot \frac{k}{r+k} \cdot \frac{1-e^{-(r+k)t}}{1-e^{-kt}}$$

此公式的本質是 $\int_0^t k \cdot e^{-k\tau} \cdot T(\tau) \, d\tau \big/ \int_0^t k \cdot e^{-k\tau} \, d\tau$，其中 $T(\tau) = T_{env} + (T_{slurry} - T_{env}) e^{-r\tau}$ 是牛頓冷卻曲線。積分已完整涵蓋「末端溫度低、萃取貢獻少」的物理現實——浸泡後期溫度低，$k \cdot e^{-k\tau}$ 的萃取速率加權也小，兩者的乘積自然下降，$T_{eff}$ 已被正確拉低。

**Swirl 的等效時間延伸** `t_kinetic = steep_sec + SWIRL_TIME_SEC × swirl_mult` 是一個**速率補償**，表達「邊界層撕裂使接下來的這段時間萃取效率等同於更長的被動浸泡」。把 `t_kinetic` 作為積分上限傳入 `_calc_t_eff`，其含義是「在牛頓冷卻曲線上繼續積分 swirl_mult 倍的 Swirl 時間」，末端溫度低的效應**已隱含在解析解中**。

Gemini 提議的「EY_steep + EY_swirl 分段計算」會引入新問題：分段後 EY_max 的共享邊界條件、起點物質守恆、以及細粉/粗粉雙峰各自的分段邏輯——複雜度遠超現有近似誤差的量級。

**執行：** 列入 §15 第 12 點，附數學說明，供未來實測驗證時參考。

---

### Gemini 建議三｜高溫劣變感知懲罰（**採納，架構調整**）

**化學論據正確。** 綠原酸（CGA）在 >90°C 高溫下加速水解為奎尼酸（quinic acid）+ 咖啡酸，咖啡酸進一步熱裂解產生乙烯基兒茶酚（Vinylcatechol）等尖銳澀感物質；類黑素（MEL）在高溫下的焦炭調性（Ashy/Scorched）也更強烈。這些是真實的、與溫度相關的「質變」，不只是量的放大。

**架構調整：**
1. Gemini 將觸發條件限定為 `roast_code in ['MD', 'D']`，但物理化學上 CGA 的高溫水解在任何焙度都會發生——只是深焙 CGA 基礎量較少（熱裂解在烘焙時已預先發生），而中淺/淺焙 CGA 基礎量高，高溫時反而影響更大。因此改為：CGA 劣變對**所有焙度**生效；MEL 劣變僅對 MD/D 生效（淺焙 MEL 極少，影響可忽略）。
2. `flavor_score` 函數簽名需加入 `temp` 參數，`optimize()` 調用同步更新。
3. 閾值設定為 94°C（Gemini 原值），斜率 0.15/°C（96°C 時放大 1.30×，98°C 時放大 1.60×）。

新增常數：`SCORCHING_TEMP_THRESHOLD = 94`、`SCORCHING_CGA_SLOPE = 0.15`、`SCORCHING_MEL_SLOPE = 0.10`（MEL 劣變斜率略低，焦炭調性的溫度敏感度低於 CGA 水解）。

**執行：** §0 新增三個 Scorching 常數；§9 `flavor_score` 簽名加入 `temp`，感知過濾器新增 Scorching Penalty；§10 `optimize()` 調用更新；§14 新增限制條目。

---

## ── 版本審查意見（v4.2 → v4.3 建議評估，來源：Gemini）──

> 本節記錄 Gemini 對 v4.2 的三條建議的可行性判斷，作為 v4.3 版本依據。

### Gemini 建議一｜烘焙度截留率（**採納，數值重新推導**）

**診斷正確：** `calc_retention(dial)` 只依賴研磨刻度，忽略了深焙豆細胞壁膨脹、孔隙率顯著高於淺焙豆的物理現實。深焙粉（D）截留約 2.4–2.6 g/g，極淺焙粉（L+）約 1.8–2.0 g/g，差距可達 25%，對 TDS 預測影響不可忽略。

**數值調整：** Gemini 的 `RETENTION_BASE = {'M': 2.2}` 與 v4.2 在 dial=4.5 的現值（2.35 g/g）存在跳躍。本次以「dial=4.5 時各焙度的基準截留值」為錨點重新推導，並保留研磨度修正斜率：

$$retention = RETENTION\_BASE[roast] + (DIAL\_BASE - dial) \times RETENTION\_DIAL\_SLOPE[roast]$$

| 焙度 | 基準截留（dial=4.5）| 研磨斜率（/格）| dial=3.5 | dial=6.5 |
|------|---------------|------------|---------|---------|
| L+   | 2.00          | 0.10       | 2.10    | 1.80    |
| L    | 2.10          | 0.10       | 2.20    | 1.90    |
| LM   | 2.20          | 0.10       | 2.30    | 2.00    |
| M    | 2.30          | 0.10       | 2.40    | 2.10    |
| MD   | 2.40          | 0.09       | 2.49    | 2.22    |
| D    | 2.50          | 0.08       | 2.58    | 2.34    |

> 深焙豆結構疏鬆，研磨後顆粒更不規則，研磨刻度對截留的邊際效應略低（斜率 0.08 vs 淺焙 0.10）。夾緊範圍：[1.60, 2.80]。

**執行：** §0 新增 `RETENTION_BASE`、`RETENTION_DIAL_SLOPE` 字典；§6 `calc_retention` 升級為二元函數 `calc_retention(roast_code, dial)`；§6 `calc_tds`、§10 `optimize()` 中的呼叫同步加入 `roast_code` 參數；§14 更新截留係數限制條目。

---

### Gemini 建議二｜咖啡因早熟漸近線（**採納，參數傳遞調整**）

**診斷正確：** `CA = ca_roast * min(ey / 22, 1.0)` 強制 CA 與總 EY 線性綁定，低估短時間低 EY 沖煮中的咖啡因苦味（現實：90 秒內咖啡因已 90%+ 溶出）。

**修正：** 改用一階動力學漸近線，速率常數 `K_CA = 0.030`（90s 時約 93% 飽和、240s 時約 99.9% 飽和）。使用 `steep_sec` 而非 `t_kinetic`——後者是 `calc_ey` 的內部積分時間，不應透過函數簽名外漏；`steep_sec` 本身對咖啡因萃出的代表性已足夠（咖啡因在浸泡期間幾乎全部溶出，Swirl 補償意義不大）。

$$CA = ca\_roast \times (1 - e^{-K_{CA} \times steep\_sec})$$

| steep_sec | 萃取比例 |
|-----------|---------|
| 45s       | 74%     |
| 90s       | 93%     |
| 150s      | 99.0%   |
| 240s      | 99.9%   |

**執行：** §0 新增 `K_CA = 0.030`；§7 `predict_compounds` 中 CA 計算更新；§14 新增咖啡因動力學限制條目。

---

### Gemini 建議三｜斯托克斯動態沉降時間（**採納，公式修正夾緊**）

**論據正確：** 斯托克斯定律確實支持「粒徑平方正比於沉降速度」。粗研磨（dial=6.5）大顆粒沉降極快，10 秒已足；極細研磨（dial=3.5）細粉懸浮時間長，需要更長等待才能形成穩定粉床。固定 30 秒對兩端都不理想。

**公式：** `swirl_wait = 30 + (DIAL_BASE - dial) × SWIRL_WAIT_SLOPE`，夾緊至 `[10, 45]` 秒。

| dial | swirl_wait_sec |
|------|---------------|
| 3.5  | 40s（極細粉，等待粉床穩定） |
| 4.5  | 30s（基準不變） |
| 6.5  | 10s（粗粉，迅速沉底） |

**連帶更新：** `SWIRL_WAIT_SEC` 從常數移除（或保留為向下相容的文件用途說明），改為 `calc_swirl_wait(dial)` 函數。`optimize()` 的 `total_contact_sec` 與 `swirl_wait_sec` 輸出欄位使用動態值。`SWIRL_WAIT_SLOPE = 10`（每格研磨±10 秒）。

**執行：** §0 移除 `SWIRL_WAIT_SEC = 30`（改為說明）、新增 `SWIRL_WAIT_BASE = 30`、`SWIRL_WAIT_SLOPE = 10`、`SWIRL_WAIT_MIN = 10`、`SWIRL_WAIT_MAX = 45`；§6 新增 `calc_swirl_wait(dial)` 函數；§4 流程說明更新為動態靜置；§10 `optimize()` 同步；§14 新增限制條目。

---

## ── 版本審查意見（v4.1 → v4.2 建議評估，來源：Gemini）──

> 本節記錄 Gemini 對 v4.1 的三條除錯建議的可行性判斷，作為 v4.2 版本依據。

### Gemini 建議一｜達西壓降 18g 免疫 Bug（**採納，修正方案調整**）

**診斷正確：** `calc_press_time` 中 `dose_factor = (dose - 18) * PRESS_TIME_PER_G`，當 dose=18g 時 `dose_factor=0`，導致 `dial_modifier` 整個被乘以 0 抵銷。18g 極細粉的粉餅阻力確實應被計入壓降時間。

**Gemini 原方案的問題：** `PRESS_TIME_MIN * dose_ratio * dial_modifier` 在 dial=6.5（粗研磨）時 `dial_modifier≈0.30`，會算出 `30 × 1.0 × 0.30 = 9 秒`，遠低於實際施壓的最低物理需求（均勻施壓至少 15–20 秒），且違反 `PRESS_TIME_MIN` 的設計意圖（作為安全下限）。

**修正方案（v4.2）：** 採「固定基礎時間 + 增量乘數」的混合設計：

```python
# 舊（v4.1，有 Bug）：
dose_factor   = (dose - 18) * PRESS_TIME_PER_G
press_time = PRESS_TIME_MIN + dose_factor * dial_modifier
# → dose=18 時 dose_factor=0，dial_modifier 完全失效

# 新（v4.2）：
dose_ratio    = dose / 18.0          # 18g → 1.0；30g → 1.667
press_time = PRESS_TIME_MIN * dial_modifier + (dose - 18) * PRESS_TIME_PER_G * dial_modifier
           = dial_modifier * (PRESS_TIME_MIN + (dose - 18) * PRESS_TIME_PER_G)
# 等價於：press_time = PRESS_TIME_MIN_BASE * dial_modifier × dose_ratio（見下方公式說明）
```

實際上採用最清晰的分解式：

$$press\_time = dial\_modifier \times \left[PRESS\_TIME\_BASE + (dose - 18) \times PRESS\_TIME\_PER\_G\right]$$

| dose / dial | dial=3.5 (mod=1.82) | dial=4.5 (mod=1.00) | dial=6.5 (mod=0.30) |
|------------|---------------------|---------------------|---------------------|
| 18g        | **55s** ✅          | 30s                 | **9s → 夾緊 15s** |
| 24g        | **66s**             | 42s                 | **13s → 夾緊 15s** |
| 30g        | **76s**             | 54s                 | **18s** |

> 注：粗研磨 + 輕豆量組合在現實中壓降確實極快，夾緊至 `PRESS_TIME_MIN_FLOOR = 15`（下限安全值，確保均勻施壓）。

**執行：** §0 新增 `PRESS_TIME_MIN_FLOOR = 15`（物理安全下限），將 `PRESS_TIME_MIN = 30` 重命名含義為「基準增量起點」；§6 `calc_press_time` 公式更新；§14 新增限制條目。

---

### Gemini 建議二｜水質 GH 動力學位置錯置（**暫緩，列入 §15**）

**理論正確：** GH（Ca²⁺/Mg²⁺）在萃取化學動力學中扮演「溶劑催化劑」角色，應影響速率常數 $k$，而非最終 EY 的乘數縮放。Gemini 的化學論據成立：純水 $t\to\infty$ 時仍能萃出物質，只是極慢。

**暫緩原因：** GH 的影響幅度本身較小（±10%），修改 $k_b$/$k_f$ 的估算常數需重新校正兩個速率常數的量級關係，且 §14 已明列此為「已知限制」。在無實測 EY-GH 對照數據前，替換估算常數的邊際收益低於引入新誤差的風險。

**執行：** 列入 §15 第 11 點，附修正路徑說明。

---

### Gemini 建議三｜非對稱 TDS 高斯偏好懲罰（**採納，完全正確**）

**完全正確：** 原對稱高斯對「太淡（水感）」過於寬容。感官心理學上，TDS 偏低（水感、空洞）在杯中是不可逆的毀滅性缺陷；TDS 偏高可加冰或加水補救。不對稱懲罰的程式碼修改極小，邏輯清晰，無副作用。

**執行：** §0 `TDS_GAUSS_SIGMA=0.20` 拆分為 `TDS_GAUSS_SIGMA_LOW=0.15`、`TDS_GAUSS_SIGMA_HIGH=0.25`；§9 `flavor_score` 的 `tds_gauss` 計算更新；§14 更新限制條目。

---

## ── 版本審查意見（v3.8 → v3.9 建議評估）──

> 本節記錄各項修改建議的可行性判斷，作為版本依據。

### 建議一｜六大物質獨立動力學（**→ §15 待辦，不進入 v3.9**）

**方向正確，但現階段實作代價高於效益。**

批評精準：巨觀 EY 用嚴謹雙峰動力學計算，微觀物質卻用經驗乘數獨立推算，兩者在底層邏輯上確實解耦。終極解法是為六大物質各自建立獨立的雙峰動力學方程式，使 $\sum EY_i = EY_{total}$ 成立。

**暫緩原因：** 此架構需要為 6 種物質 × 細粉/粗粉 = 12 個速率常數，且全部需要 GC-MS 分離量測或高精度折射儀分餾實測才能校正。現階段若強行寫入，12 個估算常數比現有的「魔法數字」更不透明，且無法驗證。正確的執行序是：先蒐集足夠的實測數據，再以數據驅動替換。

**執行：** 列入 §15 第 10 點，附詳細的操作校正路徑（最小可行版本的量測步驟）。

---

### 建議二-1｜機身熱容修正 BREWER_TEMP_DROP（**採納，數值修正至 2.5°C**）

**實際性：高。** v3.8 的 $T_{slurry}$ 已修正咖啡粉吸熱，但忽略了 AeroPress 塑膠壺身的熱容。

**熱力學推導（為何失溫幅度與 XL/標準版無關）：**

初版估算以「壁面積比值（XL 約為標準版 1.8 倍）」推算 XL 失溫更大，此推論存在盲區。正確的分析框架如下：

$$\Delta T_{水} \propto \frac{m_{塑膠} \cdot c_{塑膠}}{m_{水} \cdot c_{水}} \approx \frac{m_{塑膠}}{m_{水} \times 4.2}$$

AeroPress XL 的塑膠壺身質量約為標準版的兩倍，但注水量同樣是兩倍（400ml 對 200ml）——**分子與分母等比例放大，比值幾乎不變**。因此：

> 無論標準版或 XL，冷機身造成的瞬間失溫幅度相同，約為 **2–3°C**。

這意味著 `BREWER_TEMP_DROP` 是一個**與機型無關的普適常數**，而非 XL 的專屬參數。取 2–3°C 範圍的中間值：**2.5°C**。

修正後公式：
$$T_{slurry} = T_{initial} - dose \times SLURRY\_TEMP\_DROP\_PER\_G - BREWER\_TEMP\_DROP$$

30g 豆量下的修正量：$4.5 + 2.5 = 7.0°C$，對應 EY_max 的修正約 $−2.1\%$（每 5°C 對應 ±1.5%），修正幅度有意義。

**執行：** §0 新增 `BREWER_TEMP_DROP = 2.5`；§5 `calc_ey` 中 `t_slurry` 計算更新。

---

### 建議二-2｜Swirl 強制對流補償（**採納**）

**實際性：高。** 粗粉在靜置浸泡時，表面會形成高濃度飽和邊界層，抑制後續擴散。Swirl 的物理攪動瞬間撕裂邊界層，等效於重新啟動高速擴散，對 PS（慢速物質）與 CGA（長時間萃出物質）的補充貢獻尤為顯著。

**實作方式：** 新增 `SWIRL_CONVECTION_MULT = 1.5`。在 `calc_ey` 中以：
$$t_{kinetic} = steep\_sec + SWIRL\_TIME\_SEC \times SWIRL\_CONVECTION\_MULT$$
作為雙峰動力學的積分時間（10 秒旋轉等效為 15 秒額外浸泡）。$T_{eff}$ 的計算同樣使用 $t_{kinetic}$，確保溫度衰減曲線與積分時間軸一致。

**重要說明：** `steep_sec` 仍是四向量搜尋變數（60–240s），`t_kinetic` 僅用於 `calc_ey` 內部計算，不影響輸出呈現的浸泡時間。

**執行：** §0 新增 `SWIRL_CONVECTION_MULT = 1.5`；§5 `calc_ey` 內 `t_kinetic` 計算更新；§14 新增對應已知限制條目。

---

### 建議三｜深焙 MEL 焦苦反噬修正（**採納**）

**實際性：高。** v3.8 的醇苦比分子為 PS，分母為 CA + CGA，對淺中焙正確。但在 MD/D 焙度中，高濃度 MEL（類黑素）在口腔中同樣貢獻焦苦（Ashy/Roasty bitterness）——尤其是過萃時，MEL 的焦炭調性會壓過其提供的 Body 感。目前將 MEL 完全排除在苦澀分母之外，會系統性獎勵 MD/D 的高萃取組合，導致輸出食譜偏向焦炭水。

**設計：** 新增 `MEL_BITTER_COEFF` 字典，依焙度定義 MEL 進入苦澀分母的權重：

```python
MEL_BITTER_COEFF = {
    'L+': 0.0, 'L': 0.0, 'LM': 0.0, 'M': 0.0,
    'MD': 0.5,  # MEL 開始顯著貢獻焦苦
    'D':  0.5,  # 同上（深焙焦苦）
}
```

醇苦比分母：`CA + CGA + MEL × MEL_BITTER_COEFF[roast_code]`

**連鎖修正：** `flavor_score` 函數需要 `roast_code` 參數（現有簽名無此參數），加入後 §10 `optimize()` 的調用同步更新。

**執行：** §0 新增 `MEL_BITTER_COEFF`；§9 `flavor_score` 加入 `roast_code` 參數；§10 調用同步更新；§13 檔案結構同步。

---

### 建議四｜感知層與質量層架構分離（**採納，v4.0 新增**）

**問題所在（質量不守恆悖論）：** v3.9 的 `predict_compounds` 以 `AC *= max(0.65, 1.0 - water_kh / 500)` 直接扣減 AC 的原始強度。此做法混淆了兩個獨立的物理現象：水中碳酸氫根（KH）會中和咖啡酸的 H⁺ 離子（改變 pH，降低**感官酸度**），但被中和的有機酸以鹽類形式留在杯中，其**質量**與**TDS 貢獻**並未消失。在質量層扣減 AC 會在未來「六大物質獨立動力學（$\sum EY_i = EY_{total}$）」實作時造成質量不守恆的致命錯誤。

**修正架構：**

```
predict_compounds() → 回傳真實萃取質量（AC_mass，不含 KH 扣減）
                          ↓
flavor_score() 入口處套用感知過濾器
    actual_perceived['AC'] = actual_abs['AC'] × KH_Penalty
                          ↓
    所有四層評分（cosine_sim、conc_score、b_ac_sw、b_ps）
    全部使用 actual_perceived 而非 actual_abs
```

**執行：** §0 新增 `KH_ACID_PERCEPT_COEFF = 500`；§7 `predict_compounds` 移除 KH 扣減行，加入說明注釋；§9 `flavor_score` 新增 `water_kh` 參數與感知過濾器；§10 `optimize()` 調用更新。

---

### 建議五｜達西定律壓降修正（**採納，v4.0 新增**）

**問題所在：** v3.9 的 `dial_modifier = 1.0 + (DIAL_BASE - dial) × 0.15` 給出 dial=3.5 時僅 1.15x 的線性阻力倍率。但在流體力學的達西定律中，多孔介質的流體阻力與顆粒直徑的平方成反比（$\Delta P \propto 1/d^2$）。極細粉的細粉遷移（Fines Migration）會堵塞濾紙孔隙，導致阻力呈非線性暴增，這是 AeroPress 「壓不下去（Stall）」的成因。1.15x 線性懲罰嚴重低估了物理現實。

**修正公式：**
$$dial\_modifier = e^{(DIAL_{BASE} - dial) \times DARCY\_PRESS\_EXP}$$

| dial | 舊線性倍率 | 新指數倍率（exp=0.6） |
|------|-----------|----------------------|
| 6.5  | 0.70×     | 0.30×                |
| 4.5  | 1.00×     | 1.00×                |
| 3.5  | 1.15×     | **1.82×**            |

**連帶修正：** `PRESS_TIME_MAX` 從 60 升至 90 秒，容許大豆量 + 極細粉的 Stall 場景（現實中 28–30g + dial 3.5 確實需要 70–80s）。

**執行：** §0 新增 `DARCY_PRESS_EXP = 0.6`，`PRESS_TIME_MAX` 改為 90；§6 `calc_press_time` 更新 `dial_modifier` 公式；§13、§14 同步更新。

---

### 建議六｜非對稱 Huber Loss（**採納，v4.0 新增**）

**問題所在：** 標準 Huber Loss 為對稱函數——某物質比理想值「多 20%」與「少 20%」的懲罰相同。但咖啡感官具有高度非對稱性：苦澀（CA/CGA）過量直接毀掉整杯咖啡，而苦澀不足頂多「缺乏層次」；甜感（SW）不足是嚴重缺陷，但甜感稍多通常被接受。對稱評分系統無法反映「寧可偏甜、絕不偏苦」的人類感官心理學，在邊界值優化時會輸出偏苦的食譜。

**修正設計：** 在 `conc_loss` 的每個物質計算中加入方向性懲罰倍率：

```
CA/CGA：若 actual > ideal（過量）→ huber_loss × ASYM_BITTER_MULT (1.5)
SW    ：若 actual < ideal（不足）→ huber_loss × ASYM_SWEET_MULT  (1.5)
其餘物質：維持對稱 Huber（倍率 = 1.0）
```

**執行：** §0 新增 `ASYM_BITTER_MULT = 1.5`、`ASYM_SWEET_MULT = 1.5`；§9 `_huber` 維持原函數不變（保持可重用性），`flavor_score` 內 conc_loss 迴圈改為逐物質計算並套用非對稱倍率；§14 新增限制條目。

---

### 建議七｜KH 感知過濾器改為指數衰減（**採納，v4.1 新增**）

**問題所在：** v4.0 的感知過濾器使用線性公式 `kh_penalty = max(0.65, 1.0 - water_kh / 500)`。但酸鹼緩衝的化學現實遵循 Henderson-Hasselbalch 方程式：當 KH 從 0 增加至 40 ppm 時，H⁺ 被中和的速率極快（初期效應劇烈）；超過 80 ppm 後，溶液已形成強大的緩衝體系，繼續增加 KH 對感知酸度的邊際破壞力遞減。線性公式低估低 KH 的中和強度，高估高 KH 的差異。

| KH (ppm) | 線性懲罰（舊）| 指數懲罰（新）| 差異 |
|---------|-------------|-------------|------|
| 0       | 1.000       | 1.000       | =    |
| 30      | 0.940       | **0.819**   | 更強 |
| 80      | 0.840       | **0.588** → 夾緊至 0.65 | 更強 |
| 150     | 0.700       | 0.368 → 夾緊至 0.65     | 夾緊收斂 |

**修正公式：**
$$kh\_penalty = \max(0.65,\ e^{-water\_kh \ /\ KH\_PERCEPT\_DECAY})$$

**執行：** §0 將 `KH_ACID_PERCEPT_COEFF = 500` 替換為 `KH_PERCEPT_DECAY = 150`；§9 `flavor_score` 的 `kh_penalty` 公式更新。

---

### 建議八｜Swirl 對流倍率改為豆量動態函數（**採納，v4.1 新增**）

**問題所在：** v3.9 的 `SWIRL_CONVECTION_MULT = 1.5` 為固定常數，忽略了「漿體黏滯度」隨豆量的變化。18g 細豆粉在 400ml 水中，Swirl 可產生大漩渦，對流效率高；30g 極細粉的漿體接近泥漿，同樣旋轉 10 秒，流速極慢，邊界層撕裂效果大打折扣。固定倍率對輕豆量低估對流貢獻，對重豆量高估。

**修正公式：**
$$swirl\_mult = 1.0 + SWIRL\_CONVECTION\_BASE \times \frac{SWIRL\_DOSE\_REF}{dose}$$

| dose | 舊固定倍率 | 新動態倍率 |
|------|-----------|-----------|
| 18g  | 1.5×      | **1.5×**（基準不變）|
| 24g  | 1.5×      | **1.375×**         |
| 30g  | 1.5×      | **1.3×**           |

**連帶影響：** `SWIRL_CONVECTION_MULT` 從 §0 常數移除，改為 §5 `calc_ey` 內的動態計算。§10 `optimize()` 的 `t_kinetic` 輸出行同步使用相同公式。

**執行：** §0 移除 `SWIRL_CONVECTION_MULT`，新增 `SWIRL_CONVECTION_BASE = 0.5`、`SWIRL_DOSE_REF = 18.0`；§5 `calc_ey` 更新 `t_kinetic` 計算；§10 `optimize()` 輸出行同步；§14 新增限制條目。

---

### 建議九｜全局 TDS 高斯偏好懲罰（**採納，v4.1 新增**）

**問題所在（「水感完美」漏洞）：** `build_ideal_abs` 以 `prop[k] × tds` 讓理想目標隨實際 TDS 動態縮放，解決了零和問題，但也消除了對「整體濃度」的絕對追求。驗證：dose=18g, ey=14%, dial=6.5 → TDS ≈ 0.69%，理想目標被縮放至同一低濃度，`conc_score` 虛高。人類感官中「均衡但極淡」永遠贏不了「均衡且濃度適中」。

**設計：五層評分新增第五層，全局 TDS 高斯軟懲罰：**

```python
TDS_PREFER = {                   # 各焙度人類偏好的 TDS 峰值（%）
    'L+': 1.35, 'L': 1.35,      # 淺焙：酸質在高濃度更突出
    'LM': 1.30, 'M': 1.25,      # 中淺/中焙：均衡區間
    'MD': 1.20, 'D': 1.20,      # 中深/深焙：低一點減少焦苦
}
TDS_GAUSS_SIGMA   = 0.20        # 高斯寬度（±0.20% TDS 內幾乎不扣分）
TDS_PREFER_WEIGHT = 0.10        # 最多軟性扣 10%（非硬截斷）
```

$$tds\_gauss = e^{-0.5 \times \left(\frac{TDS - TDS\_PREFER[roast]}{TDS\_GAUSS\_SIGMA}\right)^2}$$
$$tds\_factor = 1 - W_3 + W_3 \times tds\_gauss$$

| TDS 偏差 | tds_gauss | 扣分 |
|---------|-----------|------|
| ±0（命中峰值）| 1.000 | 0%   |
| ±0.20%       | 0.607 | −3.9% |
| ±0.40%       | 0.135 | −8.6% |
| ±0.60%+      | →0    | ≤−10%（上限）|

**最終五層評分：**
$$score = cosine \times conc \times (1-W_1+W_1 b_1) \times (1-W_2+W_2 b_2) \times tds\_factor \times 100$$

**執行：** §0 新增 `TDS_PREFER`、`TDS_GAUSS_SIGMA`、`TDS_PREFER_WEIGHT`；§9 `flavor_score` 簽名加入 `roast_code` 已有，新增第五層計算；§9 評分架構表格更新；§14 新增限制條目。

---

## 0. 基礎常數（Constants）

```python
import math

# ── 沖煮設備常數 ──────────────────────────────────────────
# WATER_ML 已從固定常數改為機型依賴（v5.5r：大小愛樂壓快選）
BREWER_PRESETS = {
    'standard': {
        'name':      'AeroPress 標準版',
        'water_ml':  200,
        'dose_min':  9.0,    # 最低豆量（g）→ 粉水比 1:22
        'dose_max':  18.0,   # 最高豆量（g）→ 粉水比 1:11
    },
    'xl': {
        'name':      'AeroPress XL',
        'water_ml':  400,
        'dose_min':  18.0,   # 最低豆量（g）→ 粉水比 1:22
        'dose_max':  30.0,   # 最高豆量（g）→ 粉水比 1:13
    },
}
# 物理設計說明：
# - COOL_RATE 兩機型幾乎相同（理論 r = hA/(mc)：標準版 0.000136，XL 0.000123，比值 1.10×）
#   → 保持單一 COOL_RATE 常數（機身表面積/水量比值等比例放大）
# - BREWER_TEMP_DROP 同理：塑膠質量與水量等比例放大，失溫幅度不變（v3.9 推導）
# - 搜尋空間：標準版 7×31×13×19 = 53,599 組合；XL 7×31×13×25 = 70,525 組合
DOSE_STEP         = 0.5

# ── 注水階段修正（v5.5r 新增）─────────────────────────────────
POUR_RATE         = 12     # 注水流速（ml/s）；Bonavita 鵝頸壺中高速倒水（Hoffman 快倒法）
                            # 搜尋數據：Brewista max=24 g/s、Fellow Stagg max=20 g/s、
                            # Bonavita 中速=10 g/s、慢速手沖=3 g/s
                            # Hoffman AeroPress 法為快速一次注滿（非緩慢繞圈手沖），
                            # Bonavita 中高速 ~12 ml/s 為合理預設
                            # pour_time = water_ml / POUR_RATE
                            # pour_offset = pour_time / 2（線性注水的平均接觸延遲）
                            # Standard 200ml：pour_time=16.7s → offset=8.3s
                            # XL 400ml：pour_time=33.3s → offset=16.7s
                            # 影響量級：XL 60s 浸泡時 EY −3.1%（結構性偏差），120s 時 −1.0%
                            # 此為系統性偏差（永遠高估浸泡時間），且可以秤+計時器實測校正
SWIRL_TIME_SEC    = 5      # v4.8 修正：真實操作時間（約 3 下旋轉，5 秒）
                             # 原始值 10 秒偏長，與 Hoffman 法實際手法不符
                             # 注意：操作時間與動力學等效補償已正式分離（見 SWIRL_CONVECTION_BASE）
# SWIRL_WAIT_SEC 已從固定常數改為動態函數（v4.3，見 §6 calc_swirl_wait）
SWIRL_WAIT_BASE   = 30     # v4.3：動態靜置時間基準（dial=4.5 時 30s，斯托克斯沉降原理）
SWIRL_WAIT_SLOPE  = 10     # v4.3：每格研磨增減 10 秒（細粉等更久、粗粉等更短）
SWIRL_WAIT_MIN    = 10     # v4.3：物理下限（粗粉最快 10s 沉底）
SWIRL_WAIT_MAX    = 45     # v4.3：物理上限（極細粉 45s 足以建立粉床）
                             # calc_swirl_wait(dial) = clamp(30 + (4.5-dial)×10, 10, 45)
                             # dial=3.5→40s；dial=4.5→30s；dial=6.5→10s
SWIRL_CONVECTION_BASE = 1.0   # v4.8 調整：從 0.5 升至 1.0，確保動力學等效補償維持不變
                                # 設計邏輯：SWIRL_TIME_SEC（操作時間）× swirl_mult（對流倍率）= 等效補償時間
                                # dose=18g：5s × (1 + 1.0 × 18/18) = 5 × 2.0 = 10s 等效（與 v4.7 相同）
                                # dose=24g：5s × (1 + 1.0 × 18/24) = 5 × 1.75 = 8.75s 等效
                                # dose=30g：5s × (1 + 1.0 × 18/30) = 5 × 1.60 = 8.0s 等效
                                # v4.7 舊值（BASE=0.5）：dose=18g → 10×1.5=15s；dose=30g → 10×1.3=13s
                                # v4.8 調整後（BASE=1.0）：dose=18g → 5×2.0=10s；dose=30g → 5×1.6=8s
                                # 注意：大豆量的等效補償略微降低（13s→8s），
                                # 物理上合理——5 秒的 Swirl 在高黏滯漿體中效率本就有限
SWIRL_DOSE_REF    = 18.0       # 對流倍率的基準豆量（g）；swirl_mult 在此豆量時為最大值

# ── 壓降時間（動態函數 calc_press_time(dose, dial)，見 §6）──
PRESS_TIME_MIN_FLOOR = 15  # v4.2 新增：物理安全下限（均勻施壓最少需要 15s）
PRESS_TIME_MIN    = 30     # 基準增量起點（18g 基礎壓降時間）
PRESS_TIME_MAX    = 90     # v4.0：從 60 升至 90（達西定律修正後，大豆量極細粉需要容忍空間）
PRESS_TIME_PER_G  = 2
DARCY_PRESS_EXP   = 0.6    # v4.0 新增：達西指數壓降倍率，dial_modifier = exp((4.5-dial)×0.6)
                             # dial=3.5 → 1.82×；dial=4.5 → 1.00×；dial=6.5 → 0.30×
                             # v4.2 Bug Fix：dial_modifier 現在乘以完整時間（含基礎 + 增量）
                             # 而非僅乘增量，18g 極細粉的基礎阻力不再被錯誤歸零
BED_COMPACTION_COEFF = 0.15  # v5.5 新增：粉床時間壓實修正係數
                              # v5.6：compaction_mult 改以 effective_compaction_time 計算
                              #   compaction_mult = 1.0 + (effective_compaction_time / 240) × 0.15
                              # 物理依據：斯托克斯沉降使細粉隨浸泡時間遷移至濾紙面，
                              # 形成緻密阻水層；Swirl 部分重置（見 SWIRL_RESET_FRACTION）
                              # 長浸泡使 Stall 機率上升，連動 apply_channeling 提升 CGA
SWIRL_RESET_FRACTION = 0.35   # v5.6 新增：Swirl 粉床重置比例（理論推導值）
                               # 物理依據：斯托克斯沉降 + 渦流雷諾數分析
                               #   Re ≈ 500（層流邊界）→ 可懸浮粒徑 < 80μm 顆粒
                               #   < 80μm 顆粒佔細粉層約 35%，剩餘 65% 嵌入間隙不被重置
                               # effective_compaction_time = steep_sec × (1 − SWIRL_RESET_FRACTION)
                               #                             + swirl_wait_sec
                               # 範例（dial=4.5，swirl_wait=30s）：
                               #   steep=60s  → eff = 60×0.65+30 = 69s（vs 舊值 60s）
                               #   steep=120s → eff = 120×0.65+30 = 108s（vs 舊值 120s）
                               #   steep=240s → eff = 240×0.65+30 = 186s（vs 舊值 240s）
                               # §14：來源為流體力學理論推導，待實測校正

# ── 動態截留係數（v4.3：烘焙度 × 研磨度二元函數，見 §6）────
RETENTION_BASE = {               # dial=4.5 時各焙度的基準截留值（g 水 / g 豆）
    'L+': 2.00, 'L': 2.10, 'LM': 2.20,
    'M':  2.30, 'MD': 2.40, 'D': 2.50,
}
RETENTION_DIAL_SLOPE = {         # 研磨度修正斜率（每格刻度的截留增量）
    'L+': 0.10, 'L': 0.10, 'LM': 0.10,
    'M':  0.10, 'MD': 0.09, 'D': 0.08,
}
# 深焙豆孔隙率高，研磨斜率略低（結構疏鬆，顆粒不規則性對截留邊際效應較小）
# retention = RETENTION_BASE[roast] + (4.5 - dial) × RETENTION_DIAL_SLOPE[roast]
# 夾緊至 [1.60, 2.80]
# 範例：L+ dial=3.5 → 2.10；M dial=4.5 → 2.30；D dial=6.5 → 2.34

# ── 咖啡因動力學常數（v4.3 新增）────────────────────────────
K_CA = 0.030   # 咖啡因一階萃取速率常數（/秒）
               # ca_extraction = 1 - exp(-K_CA × steep_sec)
               # steep=90s → 93% 飽和；steep=150s → 99%；steep=240s → 99.9%
               # 解耦總 EY 線性綁定，反映咖啡因「快速溶出、提早飽和」的化學本質

# ── EY 雙峰動力學——細粉率（函數化，見 calc_fines_ratio）──
FINES_RATIO_BASE       = 0.15
FINES_RATIO_DIAL_SLOPE = 0.04
# calc_fines_ratio(dial) = 0.15 + (4.5 - dial) × 0.04
# dial=3.5 → 19% | dial=4.5 → 15% | dial=6.5 → 7%（夾緊 5%–35%）

# ── EY 雙峰動力學——速率倍率 ────────────────────────────
K_FINES_MULT      = 10.0
K_BOULDERS_MULT   = 0.55

# ── 熱平衡失溫修正 ────────────────────────────────────────
# SLURRY_TEMP_DROP_PER_G = 0.15  # DEPRECATED（v5.8r：改以比熱混合方程式取代）
                                   # 舊線性公式 t_slurry = temp - dose×0.15 - 2.5 忽略 water_ml，
                                   # 導致 Standard(200ml) 與 XL(400ml) 同一豆量得到相同 t_slurry
                                   # 這在雙機型設計下是結構性錯誤（18g 冷卻 200ml 幅度 > 400ml）
COFFEE_SPECIFIC_HEAT_RATIO = 0.33  # v5.8r 新增：咖啡熟豆比熱 / 水比熱（無量綱）
                                    # 咖啡熟豆 c ≈ 1.4 J/(g·K)，水 c ≈ 4.18 J/(g·K)
                                    # 比值 ≈ 0.33（文獻值 0.30–0.38，取中間偏低）
                                    # 混合溫度：t_mix = (water_ml×T_w + dose×0.33×T_ENV) / (water_ml + dose×0.33)
                                    # t_slurry = t_mix − BREWER_TEMP_DROP
                                    # 驗算（M 92°C）：
                                    #   XL 400ml 22g: t_mix=(400×92+7.26×25)/407.26 = 90.8°C → t_slurry=88.3°C
                                    #   Std 200ml 14g: t_mix=(200×92+4.62×25)/204.62 = 90.5°C → t_slurry=88.0°C
                                    #   XL 400ml 30g: t_mix=(400×92+9.90×25)/409.90 = 90.4°C → t_slurry=87.9°C
                                    # 舊線性：22g→86.2°C（差 2.1°C）；30g→85.0°C（差 2.9°C）
BREWER_TEMP_DROP       = 2.5   # 塑膠機身熱容吸熱固定常數（°C，v3.9 新增）
                                 # 物理依據：ΔT_水 ∝ m_塑膠 / m_水；XL 與標準版的
                                 # 塑膠質量與注水量等比例放大，比值不變，
                                 # 故失溫幅度與機型無關，普適約 2–3°C，取 2.5°C。
# v5.8r：比熱混合方程式（見 COFFEE_SPECIFIC_HEAT_RATIO）
# t_mix = (water_ml × T_w + dose × 0.33 × T_ENV) / (water_ml + dose × 0.33)
# t_slurry = t_mix − BREWER_TEMP_DROP
# 100°C + 30g/XL → t_mix = (400×100 + 9.9×25)/409.9 = 98.2°C → t_slurry = 95.7°C

# ── EY 溫度模型常數 ───────────────────────────────────────
# ⚠️ AGENT 實作指示：T_ENV 與 TDS_BROWN_WATER_FLOOR 為「使用者環境參數」，
# 必須透過 CLI 參數注入，不得硬編碼。實作時須：
# 1. 解析 CLI 參數 --t-env（float，預設 25.0）後以 T_ENV = args.t_env 覆寫此行
# 2. 解析 CLI 參數 --tds-floor（float，預設 0.80）後以 TDS_BROWN_WATER_FLOOR = args.tds_floor 覆寫此行
# 兩者影響所有溫度計算與評分下限，屬首批啟動前必須確認的個人化常數。

T_ENV             = 25.0   # 環境室溫（°C）——由 CLI --t-env 覆寫（預設 25.0）
                            # 影響：①t_slurry（粉末初溫假設 = T_ENV）
                            #       ②牛頓冷卻終態溫度（漸近線 = T_ENV）
                            # 冬天寒流（15°C）vs 夏天冷氣房（25°C）差 10°C
                            # → t_slurry 差 ≈ 0.5°C；長浸泡冷卻速率差異更大
                            # 量測方式：用溫度計量測沖煮當下室溫即可，免費且即時
COOL_RATE         = 0.0008      # v5.3 修正：牛頓冷卻速率常數（/s）
                                 # v5.2 以前的 0.02 意味 120s 後水溫降至 31°C（荒謬）
                                 # 熱力學估算 r = hA/(mc) ≈ 0.00012（理論值）
                                 # 實測合理範圍 0.0005–0.001（取決於活塞密封程度）
                                 # 取 0.0008：對應 120s 降溫 5.9°C（90→84.1°C）
                                 # 修正後 T_eff 從虛幻的 51°C 回升至 87°C（M 焙 120s）
                                 # 長浸泡參數的鑑別力大幅提升，EY 輸出更符合實際沖煮經驗
                                 # 精確值需以 §15 第 2 點的實測方案校正
K_BASE            = 0.025       # v5.5 校準：90°C 基準速率常數
                                 # v5.2 原值 0.010 在舊 COOL_RATE=0.02 下「恰好」能產出合理 EY，
                                 # 但 v5.3 修正 COOL_RATE（→0.0008）+ v5.4 T_avg 修正後，
                                 # EY_max 天花板從虛幻的 ~15% 回升至真實的 ~25%，
                                 # 舊 K_BASE 太慢，M 焙基準配方僅產出 EY=12.5%（不可飲用）。
                                 # 二元搜尋校準：以 M 焙 92°C/dial4.5/120s/22g → EY≈19% 為目標，
                                 # K_BASE ≈ 0.023–0.025。取 0.025 為暫定值，待折射儀實測校正。
K_MIN             = 0.006       # v5.5 校準：速率常數下限夾緊
                                 # v5.2 原值 0.003 在 D 焙低溫場景（T_avg≈76°C）下過度限制，
                                 # 導致深焙 EY 系統性偏低（~13%）。上調至 0.006 緩解下限瓶頸，
                                 # 待 D 焙實測 TDS 後精確校正。
K_MAX             = 0.060
DIAL_BASE         = 4.5
EY_ABSOLUTE_MAX   = 28.0
EY_MIN            = 14.0

# ── 阿瑞尼斯動態速率修正（v5.2 新增）─────────────────────────
ARRHENIUS_COEFF = 0.05  # 溫度每升高 1°C，萃取速率常數增加約 5%
                         # k_base_dynamic = K_BASE × exp((T_avg − 90) × 0.05)
                         # v5.4：以 T_avg（牛頓冷卻定積分時間平均溫度）為輸入，
                         # 修補 v5.2 以 t_slurry（起始最高溫）為輸入的恆溫假設偏差
                         # 物理依據：固液擴散遵循阿瑞尼斯方程式 k ∝ exp(−Ea/RT)

# ── 有限溶劑濃度梯度修正（v5.5 新增）────────────────────────
CONC_GRADIENT_COEFF = 0.5  # 溶質分配係數 K_d（批次平衡方程式）
                            # brew_capacity = WATER_ML / (WATER_ML + dose × K_d)
                            # 18g → 0.978（−0.9%）；24g → 0.971（−1.4%）；30g → 0.964（−1.5%）
                            # 物理依據：有限溶劑中 TDS 上升壓抑濃度梯度驅動力
                            # K_d=0.5 極保守，咖啡可溶物在水中溶解度極高
                            # 18g→30g 差異僅 ~0.6%，在搜尋空間中屬微弱修正

# ── 動態截留係數（v4.3：見 §6 calc_retention）──────────────────
# retention = RETENTION_BASE[roast] + (4.5 - dial) × RETENTION_DIAL_SLOPE[roast]
# 夾緊至 [1.60, 2.80]

# ── 風味評分常數 ──────────────────────────────────────────
CONC_HUBER_DELTA           = 0.5
BALANCE_PENALTY_WEIGHT     = 0.15   # AC/SW 甜酸比（v3.7）
BODY_BITTER_PENALTY_WEIGHT = 0.12   # PS/(CA+CGA+MEL×coeff) 醇苦比（v3.8）

MEL_BITTER_COEFF = {               # MEL 進入苦澀分母的焙度依賴係數（v3.9 新增）
    'L+': 0.0,                      # 淺焙 MEL 極少，不計入苦澀
    'L':  0.0,
    'LM': 0.0,
    'M':  0.0,
    'MD': 0.5,                      # 中深焙 MEL 開始顯著貢獻焦苦
    'D':  0.5,                      # 深焙焦苦（Ashy/Roasty）明顯
}
# 醇苦比分母：CA + CGA + MEL × MEL_BITTER_COEFF[roast_code]
# L+ → M：分母不含 MEL（與 v3.8 相同）
# MD → D：分母加入 MEL × 0.5，抑制深焙高萃取組合的過度獎勵

# ── 感知過濾器常數（v4.1 更新）─────────────────────────────
KH_PERCEPT_DECAY = 150   # v4.1：取代 v4.0 的 KH_ACID_PERCEPT_COEFF=500
                          # kh_penalty = max(0.65, exp(-water_kh / 150))
                          # 指數衰減擬合 Henderson-Hasselbalch 緩衝曲線：
                          #   KH=0 → 1.000；KH=30 → 0.819；KH=80 → 0.588 → 夾緊 0.65

# ── 非對稱 Huber Loss 係數（v4.0 新增）───────────────────
ASYM_BITTER_MULT = 1.5  # CA/CGA 過量（actual > ideal）時的懲罰倍率
ASYM_SWEET_MULT  = 1.5  # SW 不足（actual < ideal）時的懲罰倍率
# 反映人類感官非對稱性：苦澀過量的破壞力遠大於苦澀不足；甜感不足是缺陷

# ── 全局 TDS 高斯偏好懲罰（v4.1 新增）───────────────────
TDS_PREFER = {            # 各焙度人類偏好的 TDS 峰值（%）
    'L+': 1.35, 'L': 1.35,   # 淺焙：高濃度讓酸質更突出
    'LM': 1.30, 'M': 1.25,   # 中淺/中焙：均衡區間
    'MD': 1.20, 'D': 1.20,   # 中深/深焙：稍低以抑制焦苦
}
TDS_GAUSS_SIGMA_LOW  = 0.15  # v4.2：低於目標時（水感），衰減快，嚴格懲罰
TDS_GAUSS_SIGMA_HIGH = 0.25  # v4.2：高於目標時（濃郁），衰減慢，寬容高濃度
                              # 取代 v4.1 的對稱 TDS_GAUSS_SIGMA=0.20
                              # 感官依據：TDS 偏低（空洞水感）是不可逆缺陷；
                              #           TDS 偏高可加冰/加水補救，容忍度更高
# TDS_PREFER_WEIGHT = 0.10  # DEPRECATED（v5.0 已被 TDS_W3_LOW/HIGH 動態雙權重取代）

# ── 多糖體一階動力學常數（v5.1：修復 PS 線性時間破窗）──────
K_PS        = 0.005   # PS 緩速擴散速率常數（/s）；大分子（MW>10,000 Da）極慢擴散
PS_TIME_MAX = 0.20    # PS 時間項最大貢獻值（240s 時約 0.090，遠低於舊線性 0.24）
# 舊線性公式：PS += max(steep_sec-120, 0) × 0.002（到達 1.0 前無上界）
# 新漸近公式：PS += 0.20 × (1 − exp(−0.005 × extra_time))
# 對比：steep=240s 時，舊公式 +0.24，新公式 +0.090；更保守且物理正確

# ── CGA 一階動力學時間漸近線（v5.3：封堵線性時間破窗）─────────
K_CGA_TIME    = 0.015   # CGA 時間項萃取速率常數（/s）
CGA_TIME_MAX  = 0.50    # CGA 時間項最大乘數貢獻（飽和值）
# 舊線性公式：CGA *= 1 + max(steep-150, 0) × 0.004（600s 時飆至 2.8×，無界！）
# 新漸近公式：CGA *= 1 + 0.50 × (1 − exp(−0.015 × extra))
# 校準：240s 時新值 1.370 vs 舊值 1.360（搜尋空間內完美匹配）
# 長時間收斂至 1.50×（物理飽和），消除外推爆炸風險

# ── AC 相對衰減指數化（v5.3：封堵線性衰減負值 Bug）────────────
K_AC_DECAY    = 0.0035  # AC 時間項指數衰減速率（/s）
# 舊線性公式：AC *= 1 − max(steep-150, 0) × 0.003（steep > 483s 時 AC 變負！）
# 新指數公式：AC *= exp(−0.0035 × extra)（永不為負）
# 校準：240s 時新值 0.730 vs 舊值 0.730（精確匹配）
# 語意不變：長浸泡後其他物質湧出，AC 在六維向量中的相對比重指數下降

# ── CGA 澀感指數懲罰（v5.1：生物閾值連續函數，取代 Huber 不敏感問題）──
CGA_ASTRINGENCY_THRESHOLD = 1.25   # 觸發澀感指數懲罰的 CGA 倍率閾值（相對理想值）
                                     # 低於 1.25× ideal：走正常 ASYM_BITTER Huber Loss
                                     # 超過 1.25× ideal：額外觸發指數衰減懲罰乘數
                                     # 生物依據：CGA 與唾液 PRP（富含脯氨酸蛋白）結合沉澱
                                     # 閾值以下幾乎察覺不到；超過後口腔潤滑瞬間失效
CGA_ASTRINGENCY_SLOPE     = 4.0    # 指數懲罰陡峻係數（越大閾值後曲線越陡）
                                     # excess_ratio = actual/（ideal×1.25）- 1
                                     # penalty = exp(−SLOPE × excess_ratio²)
                                     # excess=0（剛達閾值）→ penalty=1.00（無額外懲罰）
                                     # excess=0.20（超標 20%，即 actual/ideal=1.50）→ 0.852
                                     # 等效 actual/ideal 倍率的感知效果：
                                     #   1.50× → penalty ≈ 0.75（扣 25%）
                                     #   1.75× → penalty ≈ 0.37（扣 63%，等同斬首）
                                     # 函數連續，但閾值後陡峻，無評分斷崖

# ── 酸澀協同劣變懲罰（v5.5 新增）──────────────────────────
HARSHNESS_SLOPE = 4.0   # AC×CGA 交叉乘積指數懲罰斜率（與 CGA_ASTRINGENCY_SLOPE 設計一致）
                         # harshness_product = max(AC/ideal-1, 0) × max(CGA/ideal-1, 0)
                         # penalty = exp(−4.0 × harshness_product)
                         # 單維超標（乘積=0）不觸發；雙維同時超標觸發交叉懲罰
                         # AC=1.3×+CGA=1.3× → product=0.09 → penalty=0.698（−30%）
                         # AC=1.5×+CGA=1.5× → product=0.25 → penalty=0.368（−63%）
                         # 口腔化學依據：高酸+高澀在缺乏甜感包覆時產生「金屬味/胃酸」
                         # 的毀滅性交互作用（Harshness），為乘積性非加法性效應

# ── 高溫揮發芳香逸散（v5.7 新增）──────────────────────────
SW_AROMA_SLOPE   = 0.02  # 每 1°C 超過 95°C，SW 感知衰減 2%
SW_AROMA_THRESH  = 95.0  # 觸發閾值（°C）；v5.8 修正：使用 temp_initial（壺溫），非 t_slurry
SW_AROMA_CAP     = 0.30  # 最大衰減上限 30%（防止極端高溫完全斬首甜感）
                          # 物理依據：揮發性芳香物質（Linalool、Furaneol 等花香/果甜來源）
                          # 在 >95°C 時熱降解速率加快，且高溫蒸氣攜帶更多揮發物逸散
                          # 此效應與 predict_compounds 的 SW 溶出拋物線正交：
                          #   溶出層：高溫多溶出焦糖化產物（質量層）
                          #   逸散層：高溫揮發性香氣損失（感知層，作用於 actual_perceived['SW']）
                          # 適用場景：L+ 以 t_slurry=98°C 沖煮 → SW 感知 × 0.94（−6%）
                          #            L+ 以 t_slurry=100°C 沖煮 → SW 感知 × 0.90（−10%）
                          # §14：SW_AROMA_SLOPE=0.02 及閾值 95°C 為感官化學估算值，非盲測數據

# ── 深焙焦澀協同懲罰（v5.7 新增，第 8 層）────────────────────
ASHY_SLOPE       = 3.0   # MEL×CGA 交叉乘積指數懲罰斜率
                          # 低於酸澀協同（4.0）：焦澀感官閾值約比酸澀高 25%
                          # penalty = exp(−3.0 × mel_excess × cga_excess)
                          # 僅對 MD/D 焙度啟用（深焙 AC 極低，無法觸發 AC×CGA 層）
                          # MEL=1.3×+CGA=1.3× → product=0.09 → penalty=0.763（−23%）
                          # MEL=1.5×+CGA=1.5× → product=0.25 → penalty=0.472（−53%）
                          # 感官化學依據：類黑素（Melanoidins）與多酚（CGA）競爭唾液
                          # PRP 結合位點，同時過萃時產生「煙灰/燒焦橡膠」的感官崩潰；
                          # 補足酸澀協同對深焙的盲區，完成完整八層評分架構
                          # §14：ASHY_SLOPE=3.0 為感官化學推導值，非盲測數據

# ── 水質鈣鎂比例（v5.1：GH Ca²⁺/Mg²⁺ 離子分軌）───────────────
MG_FRAC_AC_SW_MULT = 0.16  # Mg²⁺ 比例對 AC/SW 的最大正向乘數（mg_frac=1 時 AC/SW ×1.16）
MG_FRAC_PS_CGA_MULT = 0.08 # Ca²⁺ 比例對 PS/CGA 的最大正向乘數（mg_frac=0 時 PS/CGA ×1.08）
# 物理依據：Mg²⁺（帶電半徑小）與極性小分子（有機酸、游離糖）親和力高；
#           Ca²⁺（偏向大分子）傾向萃取多糖體、加速綠原酸溶出
# 設計：乘數範圍 ±8%，不破壞現有評分量級；mg_frac=0.5（預設）時修正為 0，與 v5.0 行為相同
DIAL_STEP         = 0.1
STEEP_STEP        = 15

# ── 溫度物理邊界（v4.4 新增）────────────────────────────────
TEMP_BOILING_POINT = 100   # 標準大氣壓下液態水的物理上限（°C）——由 CLI --altitude 自動計算覆寫
                             # 搜尋迴圈上限：min(base_temp + 3, TEMP_BOILING_POINT)
                             # ⚠️ AGENT 實作指示：解析 CLI --altitude（float，預設 0.0，單位公尺）後自動計算：
                             #   TEMP_BOILING_POINT = 100.0 - altitude / 300.0
                             #   （每升高 300m 沸點降約 1°C，SCA 標準近似）
                             #   花蓮市區（altitude≈10m）：99.97°C，差異可忽略
                             #   合歡山主峰（altitude≈3416m）：88.6°C，影響顯著
                             # ★必實作（但預設值 0m 對平地使用者零影響）

# ── 高溫劣變感知懲罰（Scorching Penalty，v4.5：連續焙度閾值矩陣，取代 v4.4 硬切）──
SCORCH_PARAMS = {
    # (threshold_°C, cga_sensitivity/°C, mel_sensitivity/°C)
    # threshold：超過此溫度才觸發懲罰
    # cga_sensitivity：CGA 感知放大斜率（所有焙度，依據 CGA 高溫水解化學）
    # mel_sensitivity：MEL 感知放大斜率（淺焙 MEL 極少設為 0.0，僅 MD/D 生效）
    'L+': (100, 0.00, 0.00),  # 沸點夾緊後永不觸發，關閉
    'L':  (100, 0.00, 0.00),  # 同上，關閉
    'LM': ( 97, 0.05, 0.00),  # 接近搜尋上限（98°C）時輕微懲罰
    'M':  ( 95, 0.08, 0.00),  # 搜尋上限（95°C）即觸發，適度懲罰
    'MD': ( 91, 0.15, 0.10),  # 搜尋上限（91°C）即觸發，嚴格懲罰 CGA + MEL
    'D':  ( 88, 0.20, 0.15),  # 搜尋上限（88°C）即觸發，最嚴格
}
# 物理依據：CGA 高溫水解（→奎尼酸+咖啡酸→乙烯基兒茶酚，尖銳澀感）對所有焙度有效；
# MEL 焦炭調性惡化（Ashy/Scorched）主要在深焙高濃度 MEL 下顯著。
# 連續函數取代 v4.4 的 if MD/D 硬切，消除 M→MD 邊界的評分斷崖。

# ── 通道效應物理懲罰（Channeling Penalty，v4.5 新增）────────
CHANNELING_PRESS_THRESHOLD = 60  # 超過此壓降時間（秒）觸發通道效應懲罰
CHANNELING_EY_SLOPE        = 0.005  # 每超過 1s 降低 0.5% 的巨觀 EY（水流 Bypass）
CHANNELING_CGA_MULT        = 2.5    # 通道效應局部過萃導致 CGA 感知非線性放大倍率
CHANNELING_BYPASS_MAX      = 0.15   # bypass_ratio 上限（最多 15% 的水走旁路）
# 物理依據：極細粉+大豆量高壓場景下，水沿阻力最小路徑繞道（Channeling），
# 導致局部粉層過萃（CGA飆升）同時粉餅死角完全未萃取，整體 EY 下降。
# calc_press_time > 60s 是 Stall 邊界的代理指標。
CHANNELING_COLLAPSE_RATIO  = 0.20   # v5.2 新增：通道貫穿後阻力崩潰的時間折算比
                                      # 超過 60s 的部分，因通道形成物理阻力瓦解，
                                      # 使用者實際操作時間僅剩原本的 20%
                                      # display_press_sec = 60 + (press_sec - 60) × 0.20
                                      # 內部 press_sec 不變（仍為嚴重度代理指標）
                                      # press_sec=70 → display=62s；press_sec=90 → display=66s

# ── 壓降等效時間折算（Press-Phase Equivalent Time，v5.3 重構）─────
PRESS_EQUIV_FRACTION = 0.15   # 壓降效率折算比（相對被動浸泡的萃取效率）
                               # press_equiv = display_press_sec × 0.15（v5.4：基於阻力崩潰後的真實接觸時間）
                               # 物理依據：壓降期間水流穿過粉餅，溫度低、流速非恆定，
                               # 萃取效率遠低於靜態浸泡，估算約 15%
                               # 注入 calc_ey（t_kinetic 延伸）與 predict_compounds（effective_steep）
                               # 動力學方程式自動處理差異萃取：CA 已飽和（+0.6%），PS 未飽和（+4.4%）
```

---

## 1. 先決條件（使用者輸入）

| 輸入項 | 型別 | 建議範圍 | 說明 |
|---|---|---|---|
| `brewer_size` | str | `standard` / `xl` | **愛樂壓機型**（v5.5r 新增）：標準版 200ml / XL 400ml；決定注水量與豆量搜尋範圍 |
| `roast_code` | str | `L+` / `L` / `LM` / `M` / `MD` / `D` | 烘焙度代號（6 選 1） |
| `water_gh` | int | 0 – 300（ppm CaCO3） | **用水總硬度**（Ca²⁺ + Mg²⁺）；最佳區間 40–100 ppm。 |
| `water_kh` | int | 0 – 150（ppm CaCO3） | **碳酸鹽硬度（KH）**；中和有機酸，建議 ≤ 50 ppm。 |
| `water_mg_frac` | float | 0.0 – 1.0 | **GH 中鎂離子比例**（v5.1 新增）；Mg²⁺ 萃取 AC/SW，Ca²⁺ 萃取 PS/CGA。預設 0.40（台灣自來水 Ca 偏多）。 |

> **目標 TDS 不由使用者指定**——程式直接搜尋四向量空間，計算每組合的實際 TDS，取最高評分輸出。

---

## 1.1 水質快選預設（Water Presets）

```python
WATER_PRESETS = {

    'ro': {
        'name': 'RO 純水（逆滲透）', 'gh': 2, 'kh': 2, 'mg_frac': 0.50,
        'note': '近乎純水；GH/KH 接近 0，萃取驅動力最弱。建議勾兌礦物質或改用 Aquacode。',
    },

    # ── 花蓮自來水 + Brita（GH -10%，KH -35%）────────────
    'hualien_fenglin_brita': {
        'name': '花蓮鳳林自來水 + Brita（估算）', 'gh': 32, 'kh': 15, 'mg_frac': 0.38,
        'note': '東台灣軟水，Ca 偏多（mg_frac≈0.38），酸感清爽。建議水族用試劑實測後覆蓋。',
    },
    'hualien_guangfu_brita': {
        'name': '花蓮光復自來水 + Brita（估算）', 'gh': 41, 'kh': 18, 'mg_frac': 0.38,
        'note': '略硬於鳳林，GH 充足。建議實測後覆蓋。',
    },

    # ── 花蓮自來水 + BWT（Ca²⁺→Mg²⁺，KH -85%）─────────
    'hualien_fenglin_bwt': {
        'name': '花蓮鳳林自來水 + BWT（估算）', 'gh': 22, 'kh': 4, 'mg_frac': 0.90,
        'note': '幾乎全 Mg²⁺（mg_frac≈0.90），KH 接近零，酸質極明亮。GH 偏低，中深焙可能偏薄。建議實測後覆蓋。',
    },
    'hualien_guangfu_bwt': {
        'name': '花蓮光復自來水 + BWT（估算）', 'gh': 28, 'kh': 5, 'mg_frac': 0.90,
        'note': '光復略硬，BWT 後 GH 比鳳林版稍高，適合 L 至 M。建議實測後覆蓋。',
    },

    # ── 精品咖啡用水 ─────────────────────────────────────
    'aquacode_7l': {
        'name': 'Aquacode（1包 + 7L RO 水）', 'gh': 65, 'kh': 5, 'mg_frac': 0.73,
        'note': 'TDS ≈ 85 ppm，氯化物基底，Ca:Mg ≈ 1:2.7（mg_frac=0.73），KH 近零。SCA 認證，適合所有焙度。',
    },
    'aquacode_5l': {
        'name': 'Aquacode（1包 + 5L RO 水）', 'gh': 90, 'kh': 7, 'mg_frac': 0.73,
        'note': 'TDS ≈ 120 ppm，礦物質更濃，適合淺焙萃取困難豆或追求更多 Body。',
    },

    # ── 常見天然礦泉水（GH/KH 為估算值，建議以試劑實測後覆蓋）────
    'spritzer': {
        'name': 'Spritzer 天然礦泉水（馬來西亞）', 'gh': 85, 'kh': 60, 'mg_frac': 0.30,
        'note': '富含偏矽酸（H₂SiO₃），Ca 偏多（mg_frac≈0.30），GH 中等、KH 偏高。KH 會抑制酸感，'
                '適合中焙至深焙；淺焙酸感可能被抑制。GH/KH 為品牌資料估算，建議試劑實測。',
    },
    'jeju_samdasoo': {
        'name': 'Jeju 濟州三多水（韓國）', 'gh': 18, 'kh': 15, 'mg_frac': 0.45,
        'note': '火山岩盤極軟水，GH/KH 均極低，接近 RO 水（mg_frac≈0.45，近中性）。萃取驅動力弱，酸感清爽通透，'
                '適合極淺焙（L+/L）或強調酸質純淨感的豆款。建議搭配較高水溫補償萃取力。'
                'GH/KH 為品牌資料估算，建議試劑實測。',
    },
}

def get_water_preset(preset_key):
    """
    回傳指定水質預設的完整 dict（含 name / gh / kh / mg_frac / note）。
    v5.8s 修正：原版回傳 tuple (gh, kh, mg_frac)，但 main.py 骨架以 dict 方式存取
    （preset['gh']），導致所有 --preset 呼叫直接 TypeError 崩潰。
    修正後回傳整個 dict，main.py 以 preset['gh']、preset['kh']、preset.get('mg_frac', 0.40) 存取。
    """
    if preset_key not in WATER_PRESETS:
        raise ValueError(f"未知水質預設 '{preset_key}'。可用：{', '.join(WATER_PRESETS)}")
    return WATER_PRESETS[preset_key]
```

> - Brita/BWT 數值為二次估算值，建議以水族用 GH/KH 試劑實測後用 `--gh` `--kh` 手動覆蓋。
> - **Brita vs BWT：** Brita 保留大部分 Ca²⁺，KH -35%；BWT 置換為 Mg²⁺，KH -85%，接近 Aquacode 輪廓。
> - 特定礦泉水（Spritzer、Jeju）請實測 GH/KH 後直接手動輸入（詳見 §15 第 9 點）。

---

## 2. 烘焙度設定表（Roast Table）

```python
ROAST_TABLE = {
    'L+': {'name': '極淺焙', 'base_temp': 100, 'base_ey': 17.0},
    'L':  {'name': '淺焙',   'base_temp': 99,  'base_ey': 17.0},
    'LM': {'name': '中淺焙', 'base_temp': 95,  'base_ey': 19.0},
    'M':  {'name': '中焙',   'base_temp': 92,  'base_ey': 19.0},
    'MD': {'name': '中深焙', 'base_temp': 88,  'base_ey': 21.0},
    'D':  {'name': '深焙',   'base_temp': 85,  'base_ey': 21.0},
}
```

---

## 3. 四向量搜尋空間

| 向量 | 符號 | 範圍 | 步長 | 說明 |
|---|---|---|---|---|
| 水溫 | `T` | `base_temp ± 3°C`，**上限夾緊至 100°C** | 1°C | v4.4 Bug Fix：L+ base_temp=100 時防止產生 101–103°C 虛構參數 |
| 研磨刻度 | `G` | 3.5 – 6.5 | 0.1 | ZP6 實際可調範圍 |
| 被動浸泡時間 | `S` | 60 – 240 秒 | 15 秒 | Hoffman 基準 120s |
| 豆量 | `D` | **標準版 9–18g / XL 18–30g** | 0.5 g | 第四向量；範圍依機型自動切換 |
| （固定） | — | 旋轉 **5s**（v4.8）+ 靜置 30s | — | 旋轉進入 t_kinetic（見 §5） |
| （動態） | — | 壓降 30–60s | — | `calc_press_time(dose, dial, steep_sec)` |

> **搜尋空間大小：** 標準版 7 × 31 × 13 × 19 = **53,599 組合**；XL 7 × 31 × 13 × 25 = **70,525 組合**

---

## 4. Hoffman 法標準沖煮流程

> **與標準 Hoffman 法的差異：** ①支援 AeroPress 標準版（200ml）與 XL（400ml）；②壓降時間依豆量與研磨度動態調整（30–60 秒）。

### 4.1 核心原則

- 正置（Standard Position）非倒置；插入活塞 1cm 製造真空止滴
- 旋轉（Swirl）在浸泡結束後 10 秒，靜置 30 秒後壓降
- 不潤濕濾紙、不預熱機身
- 輕柔均勻施壓穿過嗤聲壓到底

### 4.2 完整步驟

```
步驟 1  T=0:00             AeroPress 正置，裝濾紙（無需潤濕）、裝研磨粉（豆量 D）
步驟 2  T=0:00             注入 water_ml 熱水（標準版 200ml / XL 400ml），插入活塞 1cm 防滴
步驟 3  T=0:00–S           被動浸泡 steep_sec 秒
步驟 4  T=S                輕柔旋轉 **5 秒**（Swirl，v4.8 定值）——強制對流，邊界層撕裂，萃取突波
步驟 5  T=S+10             靜置 calc_swirl_wait(dial) 秒（v4.3：10–45s，研磨度動態化）
步驟 6  T=S+40             緩慢下壓 calc_press_time(dose, dial) 秒，壓到底穿過嗤聲
步驟 7  T=S+40+press_sec   Contact End
```

### 4.3 接觸時間定義

| 階段 | 時長（秒） | 動力學處理 |
|---|---|---|
| **注水** | **標準版 ~17s / XL ~33s** | **v5.5r：扣除平均接觸延遲 `pour_offset = pour_time/2`（線性注水，第一滴 t=0、最後一滴 t=pour_time）；Standard −8.3s / XL −16.7s** |
| 被動浸泡 | 60–240（可調）| 主要積分時間（已扣除 pour_offset）|
| 旋轉 Swirl | **5（v4.8 修正，SWIRL_TIME_SEC 常數值）**| 等效 10s（dose=18g 時 ×2.0 對流倍率），計入 t_kinetic |
| 靜置 | **10–45（v4.3 動態，依 dial）** | 未計入動力學（斯托克斯沉降，粉床建立）|
| 壓降 | 15–90（動態）| **v5.3：以 `press_equiv = display_press_sec × 0.15` 注入 calc_ey 與 predict_compounds**；Channeling 懲罰獨立作用；**v5.2：輸出顯示 `display_press_sec`** |

### 4.4 研磨度參考

> **系統設計說明：** 底層物理公式（細粉率、截留係數、達西壓降）以 **1Zpresso ZP6 刻度（3.5–6.5）** 為錨點設計。使用其他磨豆機時，請查下表換算 ZP6 等效刻度後輸入 `--dial` 參數。等效刻度為實戰估算值，建議以折射儀量測 EY 後微調校正。

| 磨豆機 | 淺焙原始刻度 | 中焙原始刻度 | **建議 ZP6 等效刻度** |
|---|---|---|---|
| 1Zpresso ZP6 | 3.5–4.5 | 4.5–5.5 | **直接輸入，無需換算** |
| 1Zpresso JX Pro | 3.2.0 | — | ≈ 4.0–4.5 |
| 1Zpresso JX | 42–48 clicks | — | ≈ 3.8–4.5 |
| 1Zpresso K-max | 5–5.5 | — | ≈ 4.0–4.5 |
| Aergrind | 1.3–1.9 | — | ≈ 3.8–4.5 |
| Baratza Encore | 12–14 | — | ≈ 4.5–5.0 |
| Comandante C40 | 11–14 clicks | 14–16 clicks | ≈ 3.8–4.5 / 4.5–5.0 |
| Timemore C2 | 11 clicks | 12–14 clicks | ≈ 4.0–4.5 |
| Timemore C3/C3 Pro | — | 11 clicks | ≈ 4.5 |
| Porlex Mini | 5–7 clicks | — | ≈ 4.0–4.5 |
| Wilfa Aroma | AeroPress 刻度 | — | 直接參考廠商標示 |

> **為何不導入常態化研磨空間（G_norm）：** 不同磨豆機的細粉分佈（fines distribution）在相同「粗細程度」下物理特性不同，線性正規化會引入比現有近似更大的系統誤差；且底層常數（`DARCY_PRESS_EXP`、`FINES_RATIO_DIAL_SLOPE`）具有可與 ZP6 實測數據直接對應的物理語意，重構後將失去可校正性。正確擴展路徑是建立各磨豆機的「ZP6 等效換算表」（即本表），而非重構底層物理引擎。

---

## 5. EY 計算模型（雙峰動力學 + 動態細粉率 + 三重熱力修正 + 阿瑞尼斯動態速率 + 壓降等效注入）

> **v3.9 熱力修正完整架構：**
>
> | 修正項 | 公式 | 修正量（30g 示例） |
> |---|---|---|
> | 粉水熱交換失溫 | $dose \times 0.15$ | −4.5°C |
> | 機身熱容失溫 | $BREWER\_TEMP\_DROP$ | −2.5°C |
> | **合計 T_slurry 修正** | **−7.0°C（30g）** | **−5.2°C（18g）** |
>
> **阿瑞尼斯動態速率（v5.4：改用 T_avg 時間平均溫度）：**
> $$T_{avg} = T_{env} + \frac{T_{slurry} - T_{env}}{r \cdot t} \cdot (1 - e^{-rt})$$
> $$k_{base,dynamic} = K_{BASE} \times e^{(T_{avg} - 90) \times ARRHENIUS\_COEFF}$$
> v5.2 以 T_slurry（最高溫）為輸入，高估 k 達 18–40%。T_avg 為封閉解析解、無循環依賴。
> M焙 120s：T_avg=86.7°C（vs T_slurry=90°C），k 下修 15%；L+ 240s：T_avg=87.8°C（vs 94.5°C），k 下修 29%。
>
> **牛頓冷卻率修正（v5.3）：** `COOL_RATE` 從 0.02 修正為 0.0008（120s 降溫 5.9°C vs 舊值 59°C）
>
> **壓降等效時間注入（v5.3 新增）：**
> $$press\_equiv = press\_sec \times PRESS\_EQUIV\_FRACTION \quad (0.15)$$
> $$t_{kinetic} = steep\_sec + SWIRL\_TIME\_SEC \times swirl\_mult + press\_equiv$$
> 60s 壓降 → +9s 等效被動浸泡；90s Stall → +13.5s。動力學方程式自動處理差異萃取。
>
> **Swirl 強制對流補償（v4.8：操作時間與對流補償正式分離）：**
> $$swirl\_mult = 1.0 + SWIRL\_CONVECTION\_BASE \times \frac{SWIRL\_DOSE\_REF}{dose}$$
> $$t_{kinetic} = steep\_sec + SWIRL\_TIME\_SEC \times swirl\_mult$$
> dose=18g → swirl_mult=2.0，等效補償 5×2.0=**10s**；dose=30g → swirl_mult=1.6，等效 5×1.6=**8s**。
> v4.8 調整：操作時間 5s（真實）× 更高的 BASE（1.0）= 等效補償量維持 v4.7 的 dose=18g 基準值不變。

```python
def calc_fines_ratio(dial):
    """
    動態細粉率（v3.8）：刻度越細，細粉率越高。
    f(dial) = FINES_RATIO_BASE + (DIAL_BASE - dial) × FINES_RATIO_DIAL_SLOPE
    夾緊至 [5%, 35%]。
    """
    ratio = FINES_RATIO_BASE + (DIAL_BASE - dial) * FINES_RATIO_DIAL_SLOPE
    return max(0.05, min(ratio, 0.35))


def _calc_t_eff(temp_slurry, k, r, t):
    """
    萃取速率加權有效溫度（封閉解析解）。
    T_eff = T_env + (T_slurry - T_env) × [k/(r+k)] × [(1 - e^{-(r+k)t}) / (1 - e^{-kt})]

    t = t_kinetic（已含 Swirl 對流補償）。
    T_slurry = 粉水混合漿體真實起始溫度（已扣除粉吸熱與機身熱容）。
    t=0 邊界：洛必達法則下 T_eff → T_slurry。
    """
    kt = k * t
    if kt < 1e-9:
        return temp_slurry
    return T_ENV + (temp_slurry - T_ENV) * (k / (r + k)) * (
        (1 - math.exp(-(r + k) * t)) / (1 - math.exp(-kt))
    )


def calc_ey(roast_code, temp_initial, dial, steep_sec, dose, water_ml=400, water_gh=50, water_kh=30, press_equiv=0, pour_offset=0):
    """
    雙峰動力學 EY 模型（v5.5）。

    water_ml     : 注水量（ml）；標準版 200 / XL 400（v5.5r 新增）
    pour_offset  : 注水階段平均接觸延遲（秒，v5.5r 新增）
                   = (water_ml / POUR_RATE) / 2；從 steep_sec 扣除

    temp_initial : 注水初始溫度（手沖壺水溫，°C）
    steep_sec    : 被動浸泡時間（秒，不含旋轉與壓降）
    dose         : 豆量（g）；用於熱平衡失溫修正與 Swirl 黏滯度修正
    water_gh     : 用水總硬度（ppm CaCO3）；驅動萃取
    water_kh     : 不影響 EY（影響 AC 感知，見 §9）
    press_equiv  : 壓降等效被動浸泡時間（秒，v5.3 新增）
                   = press_sec × PRESS_EQUIV_FRACTION（0.15）
                   注入 t_kinetic 使壓降萃取透過動力學方程式自然分配

    比熱混合溫度（v5.8r：取代線性近似，正確反映 water_ml 影響）：
      t_mix = (water_ml × T_initial + dose × 0.33 × T_ENV) / (water_ml + dose × 0.33)
      T_slurry = t_mix − BREWER_TEMP_DROP
    Swirl 動態對流補償（v4.8：操作時間與補償分離）：
      swirl_mult = 1.0 + SWIRL_CONVECTION_BASE × (SWIRL_DOSE_REF / dose)
      t_kinetic  = steep_sec + SWIRL_TIME_SEC × swirl_mult + press_equiv
    阿瑞尼斯動態速率（v5.4：改用 T_avg 時間平均溫度）：
      T_avg = T_env + (T_s - T_env)/(r×t) × (1 - e^{-r×t})
      k_base_dynamic = K_BASE × exp((T_avg - 90) × ARRHENIUS_COEFF)
      修補 v5.2 以 t_slurry（最高溫）為輸入的恆溫假設（高估 k 達 18–40%）
    牛頓冷卻率修正（v5.3）：COOL_RATE 從 0.02 修正為 0.0008
    """
    cfg = ROAST_TABLE[roast_code]
    r   = COOL_RATE

    # ── 比熱混合溫度（v5.8r：取代線性近似，正確反映 water_ml 影響）──
    # 舊公式：t_slurry = temp - dose×0.15 - 2.5（忽略 water_ml，雙機型結構性錯誤）
    # 新公式：比熱平衡方程式 + 機身熱容
    heat_water  = water_ml * 1.0                            # 水的熱容量（g × 比熱比 1.0）
    heat_coffee = dose * COFFEE_SPECIFIC_HEAT_RATIO         # 咖啡粉等效熱容量
    t_mix = (heat_water * temp_initial + heat_coffee * T_ENV) / (heat_water + heat_coffee)
    t_slurry = t_mix - BREWER_TEMP_DROP

    # ── Swirl 動態對流補償（v4.8：操作時間 5s × 倍率，與 BASE=1.0 配合維持補償量）
    # 豆量越大，漿體越黏，Swirl 的邊界層撕裂效率越低
    swirl_mult = 1.0 + SWIRL_CONVECTION_BASE * (SWIRL_DOSE_REF / dose)
    t_kinetic = max(0, steep_sec - pour_offset) + SWIRL_TIME_SEC * swirl_mult + press_equiv  # v5.5r：扣除注水延遲

    # ── 動態細粉率（v3.8）────────────────────────────────
    f = calc_fines_ratio(dial)

    # ── 阿瑞尼斯動態速率常數（v5.4：以 T_avg 取代 t_slurry）──────
    # v5.2 原始設計以 t_slurry（最高溫度）為輸入，系統性高估平均速率（120s +18%、240s +40%）
    # v5.4：以牛頓冷卻定積分的時間平均溫度取代——封閉解析解、無循環依賴
    # T_avg = T_env + (T_s - T_env)/(r×t) × (1 - e^{-r×t})
    rt = r * t_kinetic
    if rt > 1e-9:
        T_avg = T_ENV + (t_slurry - T_ENV) / rt * (1.0 - math.exp(-rt))
    else:
        T_avg = t_slurry  # t→0 邊界：T_avg → T_slurry
    k_base_dynamic = K_BASE * math.exp((T_avg - 90) * ARRHENIUS_COEFF)

    # ── 速率常數（v5.2：使用溫度敏感的 k_base_dynamic）──────
    k_b = k_base_dynamic * K_BOULDERS_MULT * (1.8 ** ((DIAL_BASE - dial) / 0.5))
    k_b = max(K_MIN, min(k_b, K_MAX))
    k_f = min(k_b * K_FINES_MULT, K_MAX * K_FINES_MULT)

    # ── 各峰的 T_eff（使用 t_kinetic 與 T_slurry）────────────
    t_eff_f = _calc_t_eff(t_slurry, k_f, r, t_kinetic)
    t_eff_b = _calc_t_eff(t_slurry, k_b, r, t_kinetic)

    # ── 各峰的 EY_max（v5.6：自由溶劑修正升級）──────────────
    base_t = cfg['base_temp']
    # brew_capacity：有限溶劑中的平衡 EY 低於理論 EY_max（Infinite Sink Correction）
    # v5.5：brew_capacity = water_ml / (water_ml + dose × K_d)
    # v5.6：以 free_water（扣除截留水後的真正可用溶劑）取代總注水量
    #   free_water = water_ml − dose × calc_retention(roast_code, dial)
    #   brew_capacity = free_water / (free_water + dose × K_d)
    # 物理意義：截留水在粉床內部已飽和，不參與巨觀溶劑池的濃度平衡；
    #           只有 free_water 才是真正驅動擴散的溶劑量
    # 數值影響（K_d=0.5）：
    #   18g L+（ret=2.00）：free=364ml，capacity=0.978→0.979（差異微小）
    #   30g D  （ret=2.50）：free=325ml，capacity=0.964→0.955（差異 −0.9%）
    free_water = water_ml - dose * calc_retention(roast_code, dial)
    free_water = max(free_water, 1.0)   # 防止極端豆量/截留下除以零
    brew_capacity = free_water / (free_water + dose * CONC_GRADIENT_COEFF)
    def _ey_max(t_eff):
        return min((cfg['base_ey'] + 8.0) + (t_eff - base_t) / 5 * 1.5, EY_ABSOLUTE_MAX) * brew_capacity

    # ── 雙峰 EY 合計（使用 t_kinetic 積分）──────────────────
    ey = (f * _ey_max(t_eff_f) * (1 - math.exp(-k_f * t_kinetic)) +
          (1 - f) * _ey_max(t_eff_b) * (1 - math.exp(-k_b * t_kinetic)))

    # ── 水質 GH 修正 ──────────────────────────────────────
    if water_gh < 20:
        ey *= 0.94
    elif water_gh <= 100:
        ey *= 1.0 + (water_gh - 20) / 800
    else:
        ey *= max(0.97, 1.10 - (water_gh - 100) / 1000)

    return round(min(ey, EY_ABSOLUTE_MAX), 3)
```

---

## 6. TDS 計算模型（動態截留係數 + 雙變數壓降時間 + 動態沉降時間）

```python
def calc_retention(roast_code, dial):
    """
    動態截留係數（v4.3：烘焙度 × 研磨度二元函數）。

    v4.2 舊版（僅依賴 dial）：
      Retention = 2.5 - (dial - 3.5) × 0.15  ← 忽略烘焙度差異

    v4.3 新版（烘焙度基準 + 研磨度微調）：
      retention = RETENTION_BASE[roast] + (DIAL_BASE - dial) × RETENTION_DIAL_SLOPE[roast]

    物理依據：深焙豆細胞壁在二爆後大幅膨脹，孔隙率顯著高於淺焙豆。
    相同研磨刻度下，深焙粉（D）截留約 2.4–2.6 g/g，淺焙粉（L+）約 1.8–2.1 g/g。
    忽略此差異會使深焙的實際出液量被高估，導致 TDS 系統性偏高。

    深焙斜率（0.08）< 淺焙斜率（0.10）：深焙豆結構疏鬆，研磨刻度對截留的邊際影響略低。
    夾緊範圍：[1.60, 2.80] g/g。
    """
    base  = RETENTION_BASE[roast_code]
    slope = RETENTION_DIAL_SLOPE[roast_code]
    return round(max(1.60, min(base + (DIAL_BASE - dial) * slope, 2.80)), 2)


def calc_tds(roast_code, dose, ey, dial, water_ml=400):
    """
    計算實際 TDS（%）。截留係數由烘焙度與研磨度共同決定（v4.3）。
    water_ml：注水量（ml），v5.5r 新增——標準版 200 / XL 400。

    v4.7：修正溶液質量守恆（溶質質量 Bug Fix）。
    TDS 的嚴格定義：溶質質量 / 溶液總質量（溶劑 + 溶質）。
    """
    retention          = calc_retention(roast_code, dial)
    extracted_solids_g = dose * (ey / 100)
    water_yield_g      = water_ml - dose * retention
    yield_mass_g       = water_yield_g + extracted_solids_g   # 真實溶液總質量
    if yield_mass_g <= 0:
        return 0.0
    return round((extracted_solids_g / yield_mass_g) * 100, 4)


def calc_swirl_wait(dial):
    """
    動態靜置時間（v4.3 新增：斯托克斯沉降原理）。

    Hoffman 靜置步驟的目的是讓咖啡粉渣自然沉降，在濾紙上方形成天然粉床過濾層，
    防止細粉直接堵塞濾紙孔隙（導致 Stall）。

    根據斯托克斯定律（Stokes' Law），顆粒沉降速度與半徑平方成正比：
      v ∝ r²  →  粗粉（大 r）沉降極快，細粉（小 r）長時間懸浮

    公式：swirl_wait = clamp(SWIRL_WAIT_BASE + (DIAL_BASE - dial) × SWIRL_WAIT_SLOPE, MIN, MAX)
      dial=3.5（極細）→ 30 + 10 = 40s
      dial=4.5（基準）→ 30 + 0  = 30s
      dial=6.5（粗）  → 30 - 20 = 10s

    夾緊範圍：[SWIRL_WAIT_MIN=10, SWIRL_WAIT_MAX=45] 秒。
    """
    raw = SWIRL_WAIT_BASE + (DIAL_BASE - dial) * SWIRL_WAIT_SLOPE
    return int(max(SWIRL_WAIT_MIN, min(raw, SWIRL_WAIT_MAX)))


def calc_press_time(dose, dial, steep_sec=120):
    """
    動態壓降時間（v5.6：Swirl 粉床重置修正）。

    v4.2 新公式（Bug Fix）：
      press_time = dial_modifier × (PRESS_TIME_MIN + (dose - 18) × PRESS_TIME_PER_G)

    v5.5 新增：粉床時間壓實（Bed Compaction）
      compaction_mult = 1.0 + (steep_sec / 240) × BED_COMPACTION_COEFF

    v5.6 修正：Swirl 部分重置粉床（SWIRL_RESET_FRACTION = 0.35，理論推導值）
      真正決定壓降阻力的不是完整浸泡時間，而是「Swirl 重置後的二次沉降時間」：
        effective_compaction_time = steep_sec × (1 − SWIRL_RESET_FRACTION) + swirl_wait_sec
      物理依據：
        Swirl 渦流（Re≈500）可懸浮粒徑 <80μm 顆粒（約佔細粉層 35%），
        剩餘 65% 已嵌入粉層間隙，不被 5s 輕柔旋轉重置。
        Swirl 後粉床重新沉降時間 = calc_swirl_wait(dial)，
        這段時間是最後一批細粉沉積到濾紙面的時間窗口。

    compaction_mult = 1.0 + (effective_compaction_time / 240) × BED_COMPACTION_COEFF
    dial_modifier = exp((DIAL_BASE - dial) × DARCY_PRESS_EXP) × compaction_mult

    範例（dial=4.5，swirl_wait=30s）：
      steep=60s  → eff=69s  → mult=1.043；dial=3.5 → 1.82×1.043=1.898
      steep=120s → eff=108s → mult=1.068；dial=3.5 → 1.82×1.068=1.943
      steep=240s → eff=186s → mult=1.116；dial=3.5 → 1.82×1.116=2.031
    """
    swirl_wait_sec = calc_swirl_wait(dial)
    effective_compaction_time = steep_sec * (1.0 - SWIRL_RESET_FRACTION) + swirl_wait_sec
    compaction_mult = 1.0 + (effective_compaction_time / 240.0) * BED_COMPACTION_COEFF
    dial_modifier = math.exp((DIAL_BASE - dial) * DARCY_PRESS_EXP) * compaction_mult
    base_time     = PRESS_TIME_MIN + (dose - 18) * PRESS_TIME_PER_G
    raw_time      = dial_modifier * base_time
    return int(min(max(raw_time, PRESS_TIME_MIN_FLOOR), PRESS_TIME_MAX))


def apply_channeling(ey, compounds, press_sec):
    """
    通道效應後處理（v4.5 新增）。

    當壓降時間超過 CHANNELING_PRESS_THRESHOLD（60s）時，判定為 Stall / 高壓場景，
    觸發通道效應（Channeling）物理懲罰：

    流體力學依據：
      極細粉（dial≤3.8）+ 大豆量（dose≥26g）的高壓粉餅中，水會尋找阻力最小路徑
      形成通道（Channel），導致：
        ① 通道附近粉層嚴重過萃 → CGA 非線性飆升（尖銳咬喉澀感）
        ② 粉餅死角完全未萃取  → 整體巨觀 EY 下降

    計算：
      bypass_ratio = min((press_sec - 60) × 0.005, CHANNELING_BYPASS_MAX)
      ey_out       = ey × (1 - bypass_ratio)
      CGA_out      = CGA × (1 + bypass_ratio × CHANNELING_CGA_MULT)

    必須在 calc_tds() 調用前套用，確保 EY、TDS、Compounds 三者一致。
    press_sec ≤ 60 時直接回傳原值，無效能損耗。
    """
    if press_sec <= CHANNELING_PRESS_THRESHOLD:
        return ey, compounds

    bypass_ratio = min(
        (press_sec - CHANNELING_PRESS_THRESHOLD) * CHANNELING_EY_SLOPE,
        CHANNELING_BYPASS_MAX
    )
    ey_out = ey * (1.0 - bypass_ratio)

    compounds_out = dict(compounds)
    compounds_out['CGA'] = compounds['CGA'] * (1.0 + bypass_ratio * CHANNELING_CGA_MULT)

    return round(ey_out, 3), compounds_out
```

---

## 7. 風味物質預測模型

### 7.1 六類物質定義

| 代號 | 物質類別 | 感官貢獻 | 萃取特性 |
|---|---|---|---|
| `AC` | 有機酸（檸檬酸、蘋果酸） | 明亮酸質、清爽 | 早期萃取，高溫加速，淺焙含量高；受 KH 中和 |
| `SW` | 游離糖與焦糖化產物 | 甜感、Body 骨架 | 中期萃取，中溫最佳，深焙衰減 |
| `PS` | 多糖體（Polysaccharides） | 醇厚度、滑順感 | 慢速擴散，細研磨＋長時間才釋出 |
| `CA` | 咖啡因 | 苦感輪廓 | 高溫快速萃取，中段趨於飽和 |
| `CGA` | 綠原酸及其內酯 | 後段苦感、澀感 | 高溫長時間萃出，深焙轉化後減少 |
| `MEL` | 類黑素（Melanoidins） | 焦糖深度 / 深焙焦苦 | 深焙大量生成；低濃度提供 Body，高濃度轉為焦苦 |

### 7.2 預測公式

```python
def predict_compounds(roast_code, temp, dial, steep_sec, ey, water_kh=30, water_mg_frac=0.40, press_equiv=0, pour_offset=0):
    """
    回傳各物質「萃取質量強度」（mass，未正規化）。

    【v4.0 架構說明：感知層與質量層分離】
    KH 對 AC 的中和作用（改變感官酸度）不在此函數處理。
    AC 回傳值為真實萃取質量——KH 僅降低 H⁺ 濃度，有機酸鹽仍留在杯中。
    感知修正由 flavor_score() 入口的「感知過濾器」負責，確保底層質量守恆。
    water_kh 參數保留於簽名，供未來擴展（如 CGA 酸鹼解離修正）使用。

    【v5.0 架構澄清：AC 時間衰減項的語意】
    AC 的時間衰減不是「有機酸質量消失」（物質不滅定律不違反）。
    這是六維相對強度向量的比重建模：長時間萃取後 SW/PS/CGA 大量湧出，
    AC 在輪廓向量中的相對比重下降，建模「感知上酸感被其他物質遮蔽」的效果。
    真實物理的絕對酸質量守恆，由 flavor_score 的質量分率正規化（v5.2）保證。

    【v5.3 重構：壓降等效時間注入】
    press_equiv：壓降期間的等效被動浸泡秒數（= press_sec × 0.15）。
    effective_steep = steep_sec + press_equiv。
    所有時間依賴項使用 effective_steep，讓壓降期間的物質演變透過動力學方程式自然分配：
    CA 已近飽和（steep=120s 時 97.3%，+9s equiv → 97.9%，幾乎不變）；
    PS/CGA 仍在曲線早段，獲得有意義的漸近線推進。

    【v5.3 修復：CGA 線性時間破窗 → 指數漸近線】
    舊公式：CGA *= 1 + max(steep-150, 0) × 0.004（600s 時 2.8×，無界）
    新公式：CGA *= 1 + CGA_TIME_MAX × (1 − exp(−K_CGA_TIME × extra))
    240s 時新值 1.370 vs 舊值 1.360（搜尋空間內完美匹配），長時間收斂至 1.50×。

    【v5.3 修復：AC 線性衰減 → 指數衰減（防止負值 Bug）】
    舊公式：AC *= 1 − max(steep-150, 0) × 0.003（steep > 483s 時 AC 變負！）
    新公式：AC *= exp(−K_AC_DECAY × extra)
    240s 時精確匹配舊值 0.730，且永不為負。
    """
    # ── v5.3/v5.5r：壓降等效 + 注水延遲扣除 ────────────────────
    effective_steep = max(0, steep_sec - pour_offset) + press_equiv
    # ── Mg²⁺/Ca²⁺ 分軌修正係數（v5.1）──────────────────────────
    mg_delta      = water_mg_frac - 0.50          # 相對中性基準的偏差（+：Mg 多；-：Ca 多）
    ac_sw_mult    = 1.0 + mg_delta * MG_FRAC_AC_SW_MULT    # mg_frac=0.90 → 1.064
    ps_cga_mult   = 1.0 + (-mg_delta) * MG_FRAC_PS_CGA_MULT  # mg_frac=0.90 → 0.968

    ac_roast = {'L+':1.0, 'L':0.9, 'LM':0.7, 'M':0.5, 'MD':0.3, 'D':0.2}
    AC = ac_roast[roast_code]
    AC *= 1 + (temp - 90) * 0.02
    # v5.3：指數衰減取代線性（舊公式 steep > 483s 時 AC 變負；指數永不為負）
    # effective_steep 包含壓降等效時間
    ac_extra = max(effective_steep - 150, 0)
    AC *= math.exp(-K_AC_DECAY * ac_extra)
    AC *= ac_sw_mult   # v5.1：Mg²⁺ 對 AC 的分軌修正
    # ↑ v4.0：移除 AC *= max(0.65, 1.0 - water_kh / 500)
    #   KH 不消滅有機酸質量，感官中和效果移至 flavor_score 感知過濾器

    sw_roast = {'L+':0.5, 'L':0.7, 'LM':0.9, 'M':1.0, 'MD':0.8, 'D':0.5}
    SW = sw_roast[roast_code]
    # v4.6：甜感峰值溫度焙度動態化（取代固定 90°C 的化學謬誤）
    optimal_sw_temp = ROAST_TABLE[roast_code]['base_temp'] - 2
    SW *= 1 - abs(temp - optimal_sw_temp) * 0.01
    SW *= 1 + min(effective_steep - 120, 60) * 0.002   # v5.3：使用 effective_steep（含壓降等效）
    SW *= ac_sw_mult   # v5.1：Mg²⁺ 對 SW 的分軌修正

    PS = 0.3
    PS += max(4.5 - dial, 0) * 0.15
    # v5.1：修復 PS 線性時間破窗——改為緩速指數漸近線
    # v5.3：使用 effective_steep（含壓降等效時間）
    if effective_steep > 120:
        extra_time = effective_steep - 120
        PS += PS_TIME_MAX * (1.0 - math.exp(-K_PS * extra_time))
    PS *= {'L+':0.6, 'L':0.7, 'LM':0.8, 'M':1.0, 'MD':1.1, 'D':1.2}[roast_code]
    # v4.7：多糖體熱力學驅動係數（吸熱反應，低溫溶解度大幅降低）
    PS *= max(0.0, 1.0 + (temp - 90) * 0.015)
    PS *= ps_cga_mult  # v5.1：Ca²⁺ 對 PS 的分軌修正（高 Ca → PS 略高）
    PS = min(PS, 1.0)

    ca_roast = {'L+':1.0, 'L':1.0, 'LM':0.95, 'M':0.9, 'MD':0.85, 'D':0.8}
    # v4.3：CA 解耦總 EY，改為一階動力學漸近線
    # v5.3：使用 effective_steep（含壓降等效；CA 已近飽和，壓降影響可忽略：97.3%→97.9%）
    ca_extraction_ratio = 1.0 - math.exp(-K_CA * effective_steep)
    CA = ca_roast[roast_code] * ca_extraction_ratio

    cga_roast = {'L+':0.5, 'L':0.6, 'LM':0.8, 'M':1.0, 'MD':0.7, 'D':0.4}
    CGA = cga_roast[roast_code]
    CGA *= 1 + max(temp - 92, 0) * 0.03
    # v5.3：指數漸近線取代線性（舊公式 600s 時 CGA 飆至 2.8×，無界）
    # effective_steep 包含壓降等效時間
    cga_extra = max(effective_steep - 150, 0)
    CGA *= 1.0 + CGA_TIME_MAX * (1.0 - math.exp(-K_CGA_TIME * cga_extra))
    CGA *= ps_cga_mult  # v5.1：Ca²⁺ 對 CGA 的分軌修正（高 Ca → CGA 略高）

    mel_roast = {'L+':0.1, 'L':0.2, 'LM':0.4, 'M':0.6, 'MD':0.9, 'D':1.0}
    MEL = mel_roast[roast_code] * (1 + (temp - 90) * 0.01)

    return {
        'AC':  round(AC,  4), 'SW':  round(SW,  4), 'PS':  round(PS,  4),
        'CA':  round(CA,  4), 'CGA': round(CGA, 4), 'MEL': round(MEL, 4),
    }
```

---

## 8. 理想風味表（Ideal Flavor Target）

```python
TDS_ANCHORS = {'low': 1.00, 'mid': 1.20, 'high': 1.40}

IDEAL_FLAVOR = {
    ('L+', 'low'):  {'AC':0.28, 'SW':0.30, 'PS':0.18, 'CA':0.12, 'CGA':0.08, 'MEL':0.04},
    ('L+', 'mid'):  {'AC':0.25, 'SW':0.32, 'PS':0.20, 'CA':0.11, 'CGA':0.08, 'MEL':0.04},
    ('L+', 'high'): {'AC':0.22, 'SW':0.35, 'PS':0.22, 'CA':0.10, 'CGA':0.07, 'MEL':0.04},

    ('L',  'low'):  {'AC':0.25, 'SW':0.32, 'PS':0.18, 'CA':0.13, 'CGA':0.08, 'MEL':0.04},
    ('L',  'mid'):  {'AC':0.22, 'SW':0.35, 'PS':0.20, 'CA':0.12, 'CGA':0.07, 'MEL':0.04},
    ('L',  'high'): {'AC':0.20, 'SW':0.37, 'PS':0.22, 'CA':0.11, 'CGA':0.06, 'MEL':0.04},

    ('LM', 'low'):  {'AC':0.18, 'SW':0.35, 'PS':0.20, 'CA':0.14, 'CGA':0.09, 'MEL':0.04},
    ('LM', 'mid'):  {'AC':0.15, 'SW':0.38, 'PS':0.22, 'CA':0.13, 'CGA':0.08, 'MEL':0.04},
    ('LM', 'high'): {'AC':0.13, 'SW':0.40, 'PS':0.23, 'CA':0.12, 'CGA':0.08, 'MEL':0.04},

    ('M',  'low'):  {'AC':0.12, 'SW':0.38, 'PS':0.22, 'CA':0.14, 'CGA':0.08, 'MEL':0.06},
    ('M',  'mid'):  {'AC':0.10, 'SW':0.40, 'PS':0.24, 'CA':0.13, 'CGA':0.07, 'MEL':0.06},
    ('M',  'high'): {'AC':0.09, 'SW':0.42, 'PS':0.24, 'CA':0.12, 'CGA':0.07, 'MEL':0.06},

    ('MD', 'low'):  {'AC':0.08, 'SW':0.32, 'PS':0.22, 'CA':0.13, 'CGA':0.08, 'MEL':0.17},
    ('MD', 'mid'):  {'AC':0.07, 'SW':0.34, 'PS':0.23, 'CA':0.12, 'CGA':0.07, 'MEL':0.17},
    ('MD', 'high'): {'AC':0.06, 'SW':0.35, 'PS':0.24, 'CA':0.11, 'CGA':0.07, 'MEL':0.17},

    ('D',  'low'):  {'AC':0.05, 'SW':0.28, 'PS':0.22, 'CA':0.12, 'CGA':0.06, 'MEL':0.27},
    ('D',  'mid'):  {'AC':0.05, 'SW':0.30, 'PS':0.23, 'CA':0.11, 'CGA':0.05, 'MEL':0.26},
    ('D',  'high'): {'AC':0.04, 'SW':0.30, 'PS':0.24, 'CA':0.10, 'CGA':0.05, 'MEL':0.27},
}
```

---

## 9. 風味評分公式（八層評分架構 + 協同懲罰 + 質量分率正規化）

> **八層評分架構（v5.7）：**
>
> | 層 | 機制 | 捕捉目標 | 上限影響 |
> |---|---|---|---|
> | `cosine_sim` | 加權餘弦相似度 | 六維輪廓方向 | 主要項 |
> | `conc_score` | 非對稱 Huber Loss（v4.0）+ **質量分率正規化**（v5.2） | 各物質絕對濃度；v5.2 修正尺度失真 | 主要項 |
> | `b_ac_sw` | AC/SW 比值 Huber Loss | 甜酸感官遮蔽 | 最多 −15% |
> | `b_ps` | PS/(CA+CGA+MEL×coeff) Huber Loss | 醇苦感官遮蔽（v3.9：焙度依賴 MEL） | 最多 −12% |
> | `tds_factor` | **動態非對稱** TDS 高斯懲罰（v5.0） | 全局濃度偏好 | 水感最多 −25%；濃郁最多 −10% |
> | `cga_astringency` | **指數衰減懲罰乘數**（v5.4：TDS_PREFER 錨定） | CGA 澀感生物閾值 | 超過 1.25× anchor 後指數劣化 |
> | `harshness_penalty` | **AC×CGA 交叉乘積**（v5.5） | 酸澀協同劣變（淺/中焙） | AC=1.3×+CGA=1.3× 扣 30% |
> | `ashy_penalty` | **MEL×CGA 交叉乘積**（v5.7，MD/D 限定） | 焦澀協同劣變（深焙） | MEL=1.3×+CGA=1.3× 扣 23% |
>
> **最終評分（v5.7）：**
> $$score = cosine \times conc \times (1{-}W_1{+}W_1 b_1) \times (1{-}W_2{+}W_2 b_2) \times tds \times cga\_ast \times harshness \times ashy \times 100$$

```python
KEYS         = ['AC', 'SW', 'PS', 'CA', 'CGA', 'MEL']
WEIGHTS      = {'AC':1.2, 'SW':1.8, 'PS':1.5, 'CA':1.0, 'CGA':1.3, 'MEL':1.0}

_TDS_ANCHOR_LIST = [1.00, 1.20, 1.40]
_WEIGHT_TOTAL    = sum(WEIGHTS.values())   # = 7.8
_CONC_FLOOR      = 1e-8
_W1              = BALANCE_PENALTY_WEIGHT       # = 0.15
_W2              = BODY_BITTER_PENALTY_WEIGHT   # = 0.12
# _W3 已升級為動態雙權重（v5.0）：
TDS_W3_LOW  = 0.25  # v5.0：TDS 低於目標（水感）時的動態懲罰權重；最多扣 25%
                     # 設計依據：水感（TDS 偏低）是不可逆的毀滅性缺陷，必須強制制裁
                     # 最差連乘：(1-0.15)×(1-0.12)×(1-0.25)=0.561，最多扣約 44%
TDS_W3_HIGH = 0.10  # v5.0：TDS 高於目標（濃郁）時維持原有寬容權重（v4.1 以來不變）
                     # 高濃度可加冰/加水補救，容忍度較高
CONC_SENSITIVITY_FLOOR = 0.02  # v4.9：微量物質誤差底板
                                 # 防止極低濃度場景（如 L+ 的 MEL ideal≈0.054）中，
                                 # 絕對誤差被轉化為過大的相對懲罰，影響數值穩定性。
                                 # 【觸發條件】僅在 ideal_abs[k] < 0.02 時介入——
                                 # 現有 IDEAL_FLAVOR 表的所有焙度×TDS錨點組合中，
                                 # 所有物質的 ideal_abs 均 > 0.02，正常情況零影響。
                                 # 與 _CONC_FLOOR=1e-8 語意不同：前者防誇大懲罰，後者防除以零。
TDS_BROWN_WATER_FLOOR = 0.80   # v5.8r 新增：褐水防禦底板（TDS %）——由 CLI --tds-floor 覆寫（預設 0.80）
                                 # ⚠️ AGENT 實作指示：此值為個人感官設定，不得假設 0.80 為普適值。
                                 # 使用者首次執行前應先完成 §16 Wave 1 #5 的四杯盲評（§15 第 28 點），
                                 # 以 --tds-floor <實測底線> 傳入；若使用者未提供，維持預設 0.80 並
                                 # 在終端輸出提示：「提示：TDS_BROWN_WATER_FLOOR 使用預設值 0.80%，
                                 # 建議依個人口感以 --tds-floor 調整（說明：§15 第 28 點）」
                                 # 人類對過濾咖啡的味覺認知下限約 TDS 0.80%
                                 # TDS < 0.80 時觸發二次衰減：final *= (tds / 0.80)²
                                 # 搜尋空間邊界（18g/XL 或 9g/Standard, EY≈15%）可產出 TDS≈0.70–0.75%
                                 # 僅靠 TDS_W3_LOW=0.25 不足以斬殺（仍可得 ~67 分）
                                 # 0.75% → ×0.88；0.60% → ×0.56；0.40% → ×0.25


def _huber(x, delta):
    """標準對稱 Huber Loss（內部工具，供比率懲罰層使用）。"""
    ax = abs(x)
    return 0.5 * ax * ax if ax <= delta else delta * (ax - 0.5 * delta)


def _huber_asym(x, delta, compound):
    """
    非對稱 Huber Loss（v4.0）。
    在標準 Huber 基礎上，對感官高度不對稱的物質加入方向性懲罰：
      CA/CGA 過量（x > 0）：× ASYM_BITTER_MULT（1.5）
      SW 不足  （x < 0）：× ASYM_SWEET_MULT （1.5）
    其餘物質維持對稱（倍率 = 1.0）。
    反映人類感官心理學：苦澀過量的破壞力遠大於苦澀不足；甜感不足是嚴重缺陷。
    """
    base = _huber(x, delta)
    if compound in ('CA', 'CGA') and x > 0:
        return base * ASYM_BITTER_MULT
    if compound == 'SW' and x < 0:
        return base * ASYM_SWEET_MULT
    return base


def build_ideal_abs(roast_code, tds):
    """三錨點線性插值推算理想絕對濃度向量（v3.5）。"""
    tds_c = max(0.90, min(tds, 1.50))
    if tds_c <= _TDS_ANCHOR_LIST[0]:
        prop = IDEAL_FLAVOR[(roast_code, 'low')]
    elif tds_c >= _TDS_ANCHOR_LIST[-1]:
        prop = IDEAL_FLAVOR[(roast_code, 'high')]
    else:
        if tds_c <= _TDS_ANCHOR_LIST[1]:
            t  = (tds_c - 1.00) / 0.20
            p0, p1 = IDEAL_FLAVOR[(roast_code, 'low')], IDEAL_FLAVOR[(roast_code, 'mid')]
        else:
            t  = (tds_c - 1.20) / 0.20
            p0, p1 = IDEAL_FLAVOR[(roast_code, 'mid')], IDEAL_FLAVOR[(roast_code, 'high')]
        prop = {k: p0[k] * (1 - t) + p1[k] * t for k in KEYS}
    return {k: prop[k] * tds for k in KEYS}


def flavor_score(actual_raw, ideal_abs, tds, roast_code, water_kh=30, t_slurry=90, temp_initial=90):
    """
    八層評分架構（v5.8）。

    計算流程：
      0. actual_raw 正規化為質量分率（v5.2：總和強制為 1.0）→ × tds → actual_abs
      1. 感知過濾器：
         1a. KH 酸感中和
         1b. 高溫 SW 揮發逸散（v5.8 修正：觸發變數改為 temp_initial 壺溫）
         1c. 高溫劣變懲罰（t_slurry 漿體溫，v4.9）
      2. 加權餘弦相似度（使用 actual_perceived）
      3. 非對稱 Huber Loss 絕對濃度接近度（六維，v4.0）
      4. AC/SW 甜酸比平衡懲罰（v3.7）
      5. PS/(CA+CGA+MEL×coeff) 醇苦比平衡懲罰（v3.9）
      6. TDS 非對稱高斯偏好懲罰（v5.0：動態雙權重）
      7. CGA 澀感指數懲罰（v5.4：絕對濃度錨定至 TDS_PREFER）
      8. 酸澀協同劣變懲罰（v5.5：AC×CGA 交叉乘積）
      9. 焦澀協同劣變懲罰（v5.7：MEL×CGA，僅 MD/D 焙度）
     10. score = cosine × conc × (1-W1+W1×b1) × (1-W2+W2×b2) × tds_factor
               × cga_astringency × harshness_penalty × ashy_penalty × 100

    temp_initial : 壺溫（°C），v5.8 新增——僅用於 SW 揮發逸散觸發判斷
                   芳香閃蒸發生在水柱接觸乾燥粉的瞬間，此時溫度 = 壺溫，非漿體溫
    t_slurry     : 漿體起始溫（°C），仍用於 Scorch 劣變判斷（熱平衡後溫度正確）
    """
    # ── 步驟 0：質量分率正規化 + 絕對濃度計算（v5.2）──────────
    # predict_compounds 回傳的 raw 是六維相對強度向量（總和≈2.5–3.5），
    # 非物理質量分率。強制正規化為總和=1.0 的分率後乘以 TDS，
    # 使 actual_abs 與 ideal_abs（prop 總和≈1.0 × tds）在同一尺度。
    total_raw = sum(actual_raw[k] for k in KEYS)
    if total_raw > 0:
        actual_fraction = {k: actual_raw[k] / total_raw for k in KEYS}
    else:
        actual_fraction = {k: 0.0 for k in KEYS}
    actual_abs = {k: actual_fraction[k] * tds for k in KEYS}

    # ── 步驟 0+1a：KH 感知過濾器（v4.1：指數衰減 KH 懲罰）────
    kh_penalty = max(0.65, math.exp(-water_kh / KH_PERCEPT_DECAY))
    actual_perceived = dict(actual_abs)
    actual_perceived['AC'] = actual_abs['AC'] * kh_penalty

    # ── 步驟 1b：高溫 SW 揮發逸散（v5.8 修正：觸發變數改為 temp_initial）────
    # 物理依據：揮發性芳香物質的閃蒸（Flash Volatilization）發生在水柱接觸
    # 乾燥粉表面的瞬間，此時水溫 = 壺溫（temp_initial），非熱平衡後的漿體溫。
    # v5.7 Bug（大豆量免疫）：使用 t_slurry 時，30g 豆 + 100°C 壺溫
    #   → t_slurry = 100 - 4.5 - 2.5 = 93°C < 閾值 95°C → 完全不觸發（物理錯誤）
    # v5.8 修正：改用 temp_initial，任何豆量使用 100°C 均觸發 −10% SW 感知扣減：
    #   temp_initial=98°C → penalty = 1 - (3×0.02) = 0.94（−6%）
    #   temp_initial=100°C → penalty = 1 - (5×0.02) = 0.90（−10%）
    #   temp_initial=103°C → penalty = 1 - min(8×0.02, 0.30) = 0.84（−16%，沸騰場景上限前）
    # 與 predict_compounds SW 溶出拋物線正交（後者建模質量，本層建模感知）
    if temp_initial > SW_AROMA_THRESH:
        sw_loss = min((temp_initial - SW_AROMA_THRESH) * SW_AROMA_SLOPE, SW_AROMA_CAP)
        actual_perceived['SW'] = actual_abs['SW'] * (1.0 - sw_loss)

    # ── 步驟 1c：高溫劣變感知懲罰（v4.9：改用 t_slurry 漿體溫）────
    scorch_threshold, cga_sens, mel_sens = SCORCH_PARAMS[roast_code]
    if t_slurry > scorch_threshold and (cga_sens > 0 or mel_sens > 0):
        excess = t_slurry - scorch_threshold
        if cga_sens > 0:
            actual_perceived['CGA'] = actual_abs['CGA'] * (1.0 + excess * cga_sens)
        if mel_sens > 0:
            actual_perceived['MEL'] = actual_abs['MEL'] * (1.0 + excess * mel_sens)

    # ── 層 1：加權餘弦相似度 ─────────────────────────────
    dot    = sum(WEIGHTS[k] * actual_perceived[k] * ideal_abs[k] for k in KEYS)
    norm_a = math.sqrt(sum(WEIGHTS[k] * actual_perceived[k] ** 2 for k in KEYS))
    norm_i = math.sqrt(sum(WEIGHTS[k] * ideal_abs[k] ** 2 for k in KEYS))
    cosine_sim = dot / (norm_a * norm_i) if (norm_a > 0 and norm_i > 0) else 0.0

    # ── 層 2：非對稱 Huber Loss 絕對濃度接近度（v4.9）──────
    conc_loss = sum(
        WEIGHTS[k] * _huber_asym(
            (actual_perceived[k] - max(ideal_abs[k], CONC_SENSITIVITY_FLOOR)) /
             max(ideal_abs[k], CONC_SENSITIVITY_FLOOR),
            CONC_HUBER_DELTA, k
        )
        for k in KEYS
    ) / _WEIGHT_TOTAL
    conc_score = math.exp(-conc_loss)

    # ── 層 3：AC/SW 甜酸比平衡懲罰 ──────────────────────
    i_ac_sw = ideal_abs['AC']       / max(ideal_abs['SW'],       _CONC_FLOOR)
    a_ac_sw = actual_perceived['AC'] / max(actual_perceived['SW'], _CONC_FLOOR)
    b_ac_sw = math.exp(-_huber((a_ac_sw - i_ac_sw) / max(i_ac_sw, _CONC_FLOOR),
                                CONC_HUBER_DELTA))

    # ── 層 4：PS/(CA+CGA+MEL×coeff) 醇苦比平衡懲罰（v3.9）──
    mel_coeff = MEL_BITTER_COEFF[roast_code]
    i_bitter = max(ideal_abs['CA']          + ideal_abs['CGA']          + ideal_abs['MEL']          * mel_coeff, _CONC_FLOOR)
    a_bitter = max(actual_perceived['CA']   + actual_perceived['CGA']   + actual_perceived['MEL']   * mel_coeff, _CONC_FLOOR)
    i_ps_r   = ideal_abs['PS']         / i_bitter
    a_ps_r   = actual_perceived['PS']  / a_bitter
    b_ps     = math.exp(-_huber((a_ps_r - i_ps_r) / max(i_ps_r, _CONC_FLOOR),
                                 CONC_HUBER_DELTA))

    # ── 層 5：全局 TDS 動態非對稱高斯懲罰（v5.0：動態雙權重）────
    tds_prefer = TDS_PREFER[roast_code]
    diff       = tds - tds_prefer
    sigma      = TDS_GAUSS_SIGMA_LOW if diff < 0 else TDS_GAUSS_SIGMA_HIGH
    tds_gauss  = math.exp(-0.5 * (diff / sigma) ** 2)
    _w3        = TDS_W3_LOW if diff < 0 else TDS_W3_HIGH
    tds_factor = 1 - _w3 + _w3 * tds_gauss

    # ── 層 6：CGA 澀感指數懲罰（v5.4：絕對濃度錨定）──────────
    # 生物依據：CGA 與唾液 PRP 結合沉澱是絕對濃度觸發的機制。
    # v5.3 以前：ratio = actual/ideal，TDS 對消（正規化後），懲罰完全 TDS 盲。
    # v5.4：分母錨定至 TDS_PREFER 下的理想 CGA 絕對濃度，使懲罰反映真實的口腔 CGA 濃度：
    #   低 TDS（水感杯）→ 分子小、分母不變 → ratio 低 → 不觸發（正確：稀薄杯 CGA 不足以耗盡唾液）
    #   高 TDS（濃縮杯）→ 分子大、分母不變 → ratio 高 → 嚴格觸發（正確：濃縮杯 CGA 具攻擊性）
    #   TDS = TDS_PREFER → 與舊版行為完全一致
    cga_anchor_ideal = build_ideal_abs(roast_code, TDS_PREFER[roast_code])
    cga_ideal_anchor = max(cga_anchor_ideal['CGA'], _CONC_FLOOR)
    cga_actual       = actual_perceived['CGA']
    cga_ratio        = cga_actual / cga_ideal_anchor
    cga_astringency  = 1.0
    if cga_ratio > CGA_ASTRINGENCY_THRESHOLD:
        excess_ratio    = cga_ratio / CGA_ASTRINGENCY_THRESHOLD - 1.0
        cga_astringency = math.exp(-CGA_ASTRINGENCY_SLOPE * excess_ratio ** 2)

    # ── 層 7：酸澀協同劣變懲罰（v5.5：Harshness Synergy）────────
    # 口腔化學依據：AC（高酸值）+ CGA（高澀值）同時超標時，產生乘積性的
    # 「金屬味/胃酸」劣變感（Harshness），感官破壞力遠大於兩者獨立的加總。
    # 單維超標（只有 AC 高或只有 CGA 高）不觸發（乘積為零）——
    # 已有 Huber Loss、甜酸比、澀感閾值等獨立懲罰處理。
    # 雙維同時超標時，交叉乘積捕捉協同效應：
    #   AC=1.3×+CGA=1.3× → product=0.09 → penalty=0.698（−30%）
    #   AC=1.5×+CGA=1.5× → product=0.25 → penalty=0.368（−63%）
    ac_excess_ratio  = max(actual_perceived['AC'] / max(ideal_abs['AC'], _CONC_FLOOR) - 1.0, 0)
    cga_excess_ratio = max(cga_ratio / CGA_ASTRINGENCY_THRESHOLD - 1.0, 0)  # 複用已計算的 cga_ratio
    # ⚠️ AGENT 實作注意：cga_excess_ratio 刻意使用澀感錨定閾值（÷ CGA_ASTRINGENCY_THRESHOLD），
    # 而非對稱的 max(actual/ideal - 1, 0)。
    # 設計意圖：酸澀協同（Harshness）的協同觸發條件與澀感閾值同步——
    #   只有 CGA 已達「唾液 PRP 耗盡」的危險濃度時，AC 才會與之產生毀滅性交互作用。
    #   若改成對稱形式（actual/ideal > 1 即觸發），懲罰門檻大幅降低，任何 CGA 輕微超標
    #   都會引爆酸澀協同，使中淺焙正常高溫組合被過度懲罰。請勿對稱化此計算。
    harshness_product = ac_excess_ratio * cga_excess_ratio
    harshness_penalty = math.exp(-HARSHNESS_SLOPE * harshness_product) if harshness_product > 0 else 1.0

    # ── 層 8：焦澀協同劣變懲罰（v5.7：Ashy Synergy，僅 MD/D）────
    # 感官化學依據：類黑素（MEL，焦苦）+ 綠原酸內酯（CGA，澀感）同時過萃，
    # 競爭唾液 PRP 結合位點，產生「煙灰/燒焦橡膠」感官崩潰（Ashy/Rubbery）。
    # 深焙的 AC 極低（無法觸發層 7 的 AC×CGA），本層補足深焙的協同盲區。
    # 斜率 3.0 < 4.0：焦澀感官閾值比酸澀高約 25%，懲罰略緩。
    # 單維超標不觸發（乘積為零）。
    #   MEL=1.3×+CGA=1.3× → product=0.09 → penalty=0.763（−23%）
    #   MEL=1.5×+CGA=1.5× → product=0.25 → penalty=0.472（−53%）
    ashy_penalty = 1.0
    if roast_code in ('MD', 'D'):
        mel_excess_ratio = max(actual_perceived['MEL'] / max(ideal_abs['MEL'], _CONC_FLOOR) - 1.0, 0)
        ashy_product = mel_excess_ratio * cga_excess_ratio   # 複用 cga_excess_ratio
        ashy_penalty = math.exp(-ASHY_SLOPE * ashy_product) if ashy_product > 0 else 1.0

    # ── 最終評分（八層）─────────────────────────────────────
    final = (cosine_sim * conc_score
             * (1 - _W1 + _W1 * b_ac_sw)
             * (1 - _W2 + _W2 * b_ps)
             * tds_factor
             * cga_astringency
             * harshness_penalty
             * ashy_penalty)

    # ── 褐水防禦底板（v5.8r：極端低 TDS 毀滅性懲罰）──────────────
    # 搜尋空間邊界（最低豆量 + 低 EY）可產出 TDS < 0.80%，
    # 八層評分 + TDS_W3_LOW 不足以將「有咖啡味的洗鍋水」打入地獄。
    # 二次衰減在 TDS_BROWN_WATER_FLOOR 以下額外斬殺。
    if tds < TDS_BROWN_WATER_FLOOR:
        final *= (tds / TDS_BROWN_WATER_FLOOR) ** 2

    return round(final * 100, 1)
```

---

## 10. 主程式（完整可執行版本）

```python
def optimize(roast_code, brewer_size='xl', water_gh=50, water_kh=30, water_mg_frac=0.40, top_n=3):
    """
    四向量窮舉最佳化（Hoffman 法 + AeroPress 標準版/XL）。
    brewer_size：'standard'（200ml, 9–18g）或 'xl'（400ml, 18–30g）
    """
    cfg       = ROAST_TABLE[roast_code]
    base_temp = cfg['base_temp']
    brewer    = BREWER_PRESETS[brewer_size]
    water_ml  = brewer['water_ml']
    dose_min_x2 = int(brewer['dose_min'] * 2)   # 9g→18, 18g→36
    dose_max_x2 = int(brewer['dose_max'] * 2)   # 18g→36, 30g→60

    # v5.5r：注水階段平均接觸延遲（線性注水假設）
    # 第一滴水在 t=0 接觸咖啡粉，最後一滴在 t=pour_time
    # 平均有效浸泡起始時間 = pour_time / 2
    pour_time   = water_ml / POUR_RATE           # Standard: 16.7s, XL: 33.3s
    pour_offset = pour_time / 2.0                # Standard: 8.3s,  XL: 16.7s

    results   = []

    # v4.4 Bug Fix：夾緊溫度上限至 100°C（物理沸點）
    # 原始迴圈在 L+（base_temp=100）時會搜尋 101–103°C，違反物理現實
    max_temp = min(base_temp + 3, TEMP_BOILING_POINT)

    for temp in range(base_temp - 3, max_temp + 1):
        for dial_x10 in range(35, 66):
            dial = dial_x10 / 10
            for steep in range(60, 241, 15):
                for dose_x2 in range(dose_min_x2, dose_max_x2 + 1):  # 機型依賴豆量範圍
                    dose = dose_x2 / 2

                    # v5.3：壓降時間提前計算（不依賴 EY，僅需 dose 與 dial）
                    # v5.5：加入 steep_sec（粉床時間壓實修正）
                    press_sec   = calc_press_time(dose, dial, steep)

                    # v5.4：通道效應阻力崩潰——計算真實壓降時間（移至 press_equiv 之前）
                    # 修復幽靈萃取：通道貫穿後活塞快速壓到底，實際水-粉餅接觸時間為 display_press_sec
                    # 舊設計在 Stall 場景額外注入 1–4s 不存在的「幽靈萃取時間」
                    if press_sec > CHANNELING_PRESS_THRESHOLD:
                        display_press_sec = int(
                            CHANNELING_PRESS_THRESHOLD
                            + (press_sec - CHANNELING_PRESS_THRESHOLD) * CHANNELING_COLLAPSE_RATIO
                        )
                    else:
                        display_press_sec = press_sec

                    # v5.4：press_equiv 基於 display_press_sec（真實接觸時間），非理論 press_sec
                    press_equiv = display_press_sec * PRESS_EQUIV_FRACTION

                    # EY：雙峰動力學 + 動態細粉率 + 三重熱力修正 + Swirl 補償
                    # v5.3：press_equiv 注入 t_kinetic，壓降萃取透過動力學方程式自然分配
                    ey = calc_ey(roast_code, temp, dial, steep, dose, water_ml, water_gh,
                                 press_equiv=press_equiv, pour_offset=pour_offset)
                    if ey < EY_MIN:
                        continue

                    # v5.8r：比熱混合漿體溫度（必須在 predict_compounds 之前計算）
                    # 物質溶出量由漿體溫驅動，非壺溫（calc_ey 已用 T_avg，SCORCH 用 t_slurry）
                    t_slurry_val = round(
                        (water_ml * temp + dose * COFFEE_SPECIFIC_HEAT_RATIO * T_ENV)
                        / (water_ml + dose * COFFEE_SPECIFIC_HEAT_RATIO)
                        - BREWER_TEMP_DROP, 1
                    )

                    # v5.3：predict_compounds 接收 press_equiv，使各物質的時間演變
                    # v5.8r：接收 t_slurry（取代 temp），物質溶出量以漿體溫計算
                    compounds_raw = predict_compounds(roast_code, t_slurry_val, dial, steep, ey, water_kh,
                                                      water_mg_frac, press_equiv=press_equiv,
                                                      pour_offset=pour_offset)

                    # v4.5：通道效應後處理（必須在 calc_tds 前套用，確保 EY/TDS/Compounds 一致）
                    ey, compounds = apply_channeling(ey, compounds_raw, press_sec)

                    # v5.3：移除 v4.6 的齊頭式 EY 加法（ey += press_sec × PRESS_KINETIC_COEFF）
                    # 壓降萃取已透過 press_equiv 注入 calc_ey（動力學自然分配至雙峰）
                    # 與 predict_compounds（物質演變隨 effective_steep 推進）

                    # v4.3：calc_tds 加入 roast_code（截留係數烘焙度修正）
                    tds       = calc_tds(roast_code, dose, ey, dial, water_ml)
                    ideal_abs = build_ideal_abs(roast_code, tds)

                    # t_slurry_val 已在 predict_compounds 之前計算（v5.8r 前移）

                    # flavor_score 加入 roast_code（v3.9：MEL 焦苦修正）
                    # flavor_score 加入 water_kh（v4.0：感知過濾器用於 KH 中和修正）
                    # flavor_score 加入 t_slurry（v4.9：取代 temp，Scorching 用漿體溫判斷）
                    # flavor_score 加入 temp_initial（v5.8：SW 揮發逸散用壺溫觸發）
                    score     = flavor_score(compounds, ideal_abs, tds, roast_code, water_kh, t_slurry_val, temp)

                    # v4.3：動態靜置時間（斯托克斯沉降）
                    swirl_wait = calc_swirl_wait(dial)

                    # display_press_sec 已在迴圈頂端計算（v5.4）

                    results.append({
                        'brewer':            brewer['name'],     # v5.5r：機型名稱
                        'water_ml':          water_ml,           # v5.5r：注水量
                        'temp':              temp,
                        'dial':              dial,
                        'steep_sec':         steep,
                        'dose':              dose,
                        'swirl_sec':         SWIRL_TIME_SEC,
                        'swirl_wait_sec':    swirl_wait,
                        'press_sec':         display_press_sec,   # v5.2：輸出使用阻力崩潰後的顯示時間
                        'press_sec_internal': press_sec,          # v5.2：保留內部計算用原始壓降時間
                        'total_contact_sec': steep + SWIRL_TIME_SEC + swirl_wait + display_press_sec,
                        'ey':                ey,
                        'tds':               tds,
                        'fines_ratio':       calc_fines_ratio(dial),
                        't_slurry':          t_slurry_val,
                        't_kinetic':         round(max(0, steep - pour_offset) + SWIRL_TIME_SEC * (1.0 + SWIRL_CONVECTION_BASE * (SWIRL_DOSE_REF / dose)) + press_equiv, 1),
                        'retention':         calc_retention(roast_code, dial),
                        'compounds':         compounds,
                        'score':             score,
                    })

    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:top_n]
```

---

## 11. 輸出格式規格

### 11.1 終端輸出（Terminal）

```
════════════════════════════════════════════════════════
 AeroPress 四向量最佳化結果（Hoffman 法）
 機型：[標準版 200ml / XL 400ml]  |  烘焙度：中焙 (M)
 水質：GH XXX ppm  /  KH XX ppm
════════════════════════════════════════════════════════

▶ 第 1 名  風味評分：XX.X / 100
  水溫 XX°C → 漿體起始 XX.X°C  |  刻度 X.X（細粉率 XX.X%）
  被動浸泡 X:XX → 動力學等效 X:XX（含 Swirl ×X.X，豆量相依）  |  豆量 XX.Xg
  EY XX.X%  |  實際 TDS X.XXX%  |  截留係數 X.XX g/g

  ── Hoffman 沖煮流程 ─────────────────────────────────────
  T=0:00        注入 XXXml 熱水（XX°C）；正置，不預熱機身、不潤濕濾紙
  T=0:00        立刻插入活塞 1cm，開始浸泡 X:XX
  T=X:XX        被動浸泡結束，輕柔旋轉 5 秒（Swirl）
  T=X:XX+0:10   靜置 30 秒等粉渣沉底
  T=X:XX+0:40   緩慢下壓（XX 秒，依豆量 XX.Xg × 刻度 X.X），壓到底
                 v5.2：若壓降觸發通道效應（>60s），顯示阻力崩潰後的實際操作時間
  全程接觸時間：XXX 秒（X:XX）

  物質絕對強度（raw × TDS）：
  酸(AC) X.XXXX  甜(SW) X.XXXX  醇(PS) X.XXXX
  苦(CA) X.XXXX  澀(CGA) X.XXXX  焦/Body(MEL) X.XXXX
  甜酸比（AC/SW）：實際 X.XX  |  理想 X.XX
  醇苦比（PS/苦澀）：實際 X.XX  |  理想 X.XX  [深焙苦澀含 MEL×0.5]

  說明：[風味特徵一句話說明]
```

### 11.2 JSON 輸出格式

```json
{
  "input": {"roast_code": "M", "roast_name": "中焙", "water_gh_ppm": 50, "water_kh_ppm": 30},
  "hoffman_constants": {
    "water_ml": 400, "position": "standard",
    "swirl_time_sec": "★ 讀取 SWIRL_TIME_SEC 常數（v4.8 定值 = 5，勿硬編碼）",
    "swirl_convection_mult": "dynamic: 1.0 + SWIRL_CONVECTION_BASE × (18/dose)",
    "swirl_wait_sec": 30,
    "press_time_note": "dynamic, 30–60s, f(dose, dial)",
    "press_style": "all_the_way_through_hiss",
    "filter_rinsing": false, "preheating": false
  },
  "results": [
    {
      "rank": 1, "score": 0.0,
      "vectors": {"temp_c": 0, "dial": 0.0, "steep_sec": 0, "dose_g": 0.0},
      "derived": {
        "fines_ratio_pct": 0.0,
        "t_slurry_c": 0.0,
        "t_kinetic_sec": 0.0,
        "mel_bitter_coeff": 0.0
      },
      "hoffman_flow": {
        "steep_sec": 0, "swirl_sec": 10, "swirl_wait_sec": 30,
        "press_sec": 0, "total_contact_sec": 0
      },
      "metrics": {"ey_pct": 0.0, "tds_pct": 0.0, "retention_g_per_g": 0.0},
      "compounds_abs": {
        "AC": 0.0, "SW": 0.0, "PS": 0.0, "CA": 0.0, "CGA": 0.0, "MEL": 0.0,
        "ac_sw_ratio_actual": 0.0, "ac_sw_ratio_ideal": 0.0,
        "ps_bitter_ratio_actual": 0.0, "ps_bitter_ratio_ideal": 0.0
      }
    }
  ]
}
```

---

## 12. CLI 介面規格

> ⚠️ **AGENT 實作強制要求：** 標記 `★必實作` 的參數必須無條件加入，不需等待使用者要求。標記 `★個人化` 的參數在使用者未提供時須輸出提示語（見 §0 對應常數的注釋）。

```bash
python aeropress_optimizer.py \
  --brewer   xl                \   # standard（200ml, 9–18g）| xl（400ml, 18–30g）
  --roast    M                 \   # L+, L, LM, M, MD, D
  --preset   aquacode_7l       \   # 可用：ro | hualien_fenglin_brita | hualien_guangfu_brita
                                   #       hualien_fenglin_bwt | hualien_guangfu_bwt
                                   #       aquacode_7l | aquacode_5l | spritzer | jeju_samdasoo
  --gh       70                \   # 手動 GH（覆蓋 --preset）
  --kh       50                \   # 手動 KH（覆蓋 --preset）
  --t-env    25                \   # ★必實作  環境室溫（°C），預設 25.0，覆寫常數 T_ENV
                                   #          冬天寒流 15°C / 夏天冷氣房 25°C 均常見
                                   #          量測：沖煮當下用溫度計量室溫即可，免費且即時
  --tds-floor 0.80             \   # ★個人化  褐水防禦底板（TDS %），預設 0.80
                                   #          未提供時終端輸出提示語（見 §0 TDS_BROWN_WATER_FLOOR 注釋）
                                   #          個人化方法：§15 第 28 點四杯盲評後以此參數覆寫
  --altitude  0                \   # ★必實作  海拔高度（公尺），預設 0.0
                                   #          自動計算：TEMP_BOILING_POINT = 100 - altitude/300
                                   #          平地使用者（花蓮 ≈ 10m）：差異可忽略
                                   #          山區使用者（合歡山 3416m）：沸點降至 88.6°C，影響顯著
  --top      3                 \
  --output   terminal          \   # terminal / json / csv
  --mg-frac   0.40             \   # GH 中鎂離子比例（0.0–1.0），預設 0.40（台灣自來水 Ca 偏多）
                                   # 使用 --preset 時自動從預設表讀取，手動 --gh 時需自行指定
                                   # BWT 濾水壺（高 Mg）→ 0.90；一般自來水 → 0.38；Aquacode → 0.73
  --radar                          # 雷達圖（需 matplotlib）
```

### 12.1 CLI 參數 → 程式內部映射表

> ⚠️ **AGENT 實作強制要求：** 下表為 `main.py` 的完整 argparse → 常數/函數 映射規格，必須完整實作，不得遺漏。

| CLI 參數 | 型別 | 預設值 | 注入方式 | 注入時機 |
|---|---|---|---|---|
| `--brewer` | str | `xl` | `optimize(brewer_size=args.brewer)` | 呼叫 optimize() 時傳入 |
| `--roast` | str | `M` | `optimize(roast_code=args.roast)` | 呼叫 optimize() 時傳入 |
| `--preset` | str | `None` | 查 `WATER_PRESETS[args.preset]`，解出 `gh`/`kh`/`mg_frac` | 解析後覆蓋 gh/kh/mg_frac |
| `--gh` | int | `50` | `optimize(water_gh=args.gh)` | 呼叫 optimize() 時傳入 |
| `--kh` | int | `30` | `optimize(water_kh=args.kh)` | 呼叫 optimize() 時傳入 |
| `--mg-frac` | float | `0.40` | `optimize(water_mg_frac=args.mg_frac)` | 呼叫 optimize() 時傳入 |
| `--t-env` | float | `25.0` | `constants.T_ENV = args.t_env` | **argparse 解析後、optimize() 呼叫前，全域覆寫** |
| `--tds-floor` | float | `0.80` | `constants.TDS_BROWN_WATER_FLOOR = args.tds_floor` | **argparse 解析後、optimize() 呼叫前，全域覆寫** |
| `--altitude` | float | `0.0` | `constants.TEMP_BOILING_POINT = 100.0 - args.altitude / 300.0` | **argparse 解析後、optimize() 呼叫前，全域覆寫** |
| `--top` | int | `3` | `optimize(top_n=args.top)` | 呼叫 optimize() 時傳入 |
| `--output` | str | `terminal` | 傳給 output 模組選擇渲染器 | optimize() 結果回傳後 |
| `--radar` | flag | `False` | 傳給 `radar.py` | output 完成後 |

> **全域覆寫的執行順序：**
> ```python
> # main.py 骨架（AGENT 必須依此結構實作）
> import constants                                   # 1. 先 import constants 模組
> args = parser.parse_args()                         # 2. 解析 CLI
> constants.T_ENV = args.t_env                       # 3. 全域覆寫環境參數（三行，順序不限）
> constants.TDS_BROWN_WATER_FLOOR = args.tds_floor
> constants.TEMP_BOILING_POINT = 100.0 - args.altitude / 300.0
> if args.preset:                                    # 4. preset 展開（覆蓋 gh/kh/mg_frac）
>     p = WATER_PRESETS[args.preset]
>     args.gh, args.kh, args.mg_frac = p['gh'], p['kh'], p['mg_frac']
> results = optimize(                                # 5. 執行最佳化
>     roast_code=args.roast, brewer_size=args.brewer,
>     water_gh=args.gh, water_kh=args.kh,
>     water_mg_frac=args.mg_frac, top_n=args.top
> )
> ```
> **注意：** `--tds-floor` 未提供時（使用預設 0.80），`main.py` 須在 argparse 解析後輸出提示：
> `「提示：TDS_BROWN_WATER_FLOOR 使用預設值 0.80%，建議依個人口感以 --tds-floor 調整（說明：§15 第 28 點）」`


---

## 12.1 main.py 完整入口骨架（AGENT 必實作）

> ⚠️ **AGENT 實作指示：** 下方骨架為 `main.py` 的完整 `argparse` + 常數注入 + 輸出路由。**必須逐行實作，不得省略任何步驟。** 三個環境常數（`T_ENV`、`TDS_BROWN_WATER_FLOOR`、`TEMP_BOILING_POINT`）的全域注入**必須在任何模型函數被呼叫之前**完成。

```python
# main.py
import argparse
import sys
import constants                     # §0 所有常數定義於此
from models.ey_model import calc_ey, calc_fines_ratio, _calc_t_eff
from models.tds_model import calc_tds, calc_retention, calc_swirl_wait, calc_press_time, apply_channeling
from models.compounds import predict_compounds
from models.scoring import flavor_score, build_ideal_abs
from optimizer import optimize
from output.terminal import print_terminal
from output.export import export_json, export_csv
from output.radar import plot_radar
from data.water_presets import get_water_preset


def main():
    parser = argparse.ArgumentParser(description='AeroPress 四向量最佳化系統 v5.8r')

    # ── 沖煮參數 ────────────────────────────────────────
    parser.add_argument('--brewer',     default='xl',      choices=['standard', 'xl'])
    parser.add_argument('--roast',      required=True,     choices=['L+','L','LM','M','MD','D'])
    parser.add_argument('--preset',     default=None)
    parser.add_argument('--gh',         type=float,        default=None, help='手動 GH ppm（覆蓋 --preset）')
    parser.add_argument('--kh',         type=float,        default=None, help='手動 KH ppm（覆蓋 --preset）')
    parser.add_argument('--mg-frac',    type=float,        default=None,
                        help='GH 中鎂離子比例 0.0–1.0（預設 0.40）；使用 --preset 時自動讀取，手動 --gh/--kh 時建議指定')
    parser.add_argument('--top',        type=int,          default=3)
    parser.add_argument('--output',     default='terminal', choices=['terminal','json','csv'])
    parser.add_argument('--radar',      action='store_true')

    # ── 環境參數（★必實作）───────────────────────────────
    parser.add_argument('--t-env',      type=float, default=25.0,
                        help='環境室溫 °C（預設 25.0）；影響 T_ENV → t_slurry 與牛頓冷卻終態')
    parser.add_argument('--tds-floor',  type=float, default=None,
                        help='褐水防禦底板 TDS%%（預設 0.80）；建議先完成 §15 #28 四杯盲評後設定')
    parser.add_argument('--altitude',   type=float, default=0.0,
                        help='海拔高度 m（預設 0.0）；自動計算 TEMP_BOILING_POINT = 100 - altitude/300')

    args = parser.parse_args()

    # ── 步驟 1：環境常數注入（必須在任何模型函數呼叫前完成）──
    constants.T_ENV = args.t_env
    constants.TEMP_BOILING_POINT = 100.0 - args.altitude / 300.0

    if args.tds_floor is not None:
        constants.TDS_BROWN_WATER_FLOOR = args.tds_floor
    else:
        # ★個人化提示語：使用者未提供時輸出
        print(
            '\n⚠️  提示：TDS_BROWN_WATER_FLOOR 使用預設值 0.80%。'
            '\n    建議依個人口感以 --tds-floor 調整（說明：§15 第 28 點）\n',
            file=sys.stderr
        )

    # ── 步驟 2：水質解析 ────────────────────────────────
    if args.gh is not None and args.kh is not None:
        water_gh, water_kh = args.gh, args.kh
        water_mg_frac = args.mg_frac if args.mg_frac is not None else 0.40
    elif args.preset is not None:
        preset = get_water_preset(args.preset)
        water_gh, water_kh, water_mg_frac = preset['gh'], preset['kh'], preset.get('mg_frac', 0.40)
    else:
        # 預設值：台灣常見自來水估算中位數
        water_gh, water_kh, water_mg_frac = 50.0, 30.0, 0.40
        print('⚠️  未指定水質，使用預設 GH=50 / KH=30 / mg_frac=0.40 ppm。', file=sys.stderr)

    # ── 步驟 3：執行最佳化 ──────────────────────────────
    results = optimize(
        roast_code=args.roast,
        brewer_size=args.brewer,
        water_gh=water_gh,
        water_kh=water_kh,
        water_mg_frac=water_mg_frac,
        top_n=args.top,
    )

    # ── 步驟 4：輸出路由 ────────────────────────────────
    if args.output == 'terminal':
        print_terminal(results, args.roast, water_gh, water_kh)
    elif args.output == 'json':
        export_json(results, args.roast)
    elif args.output == 'csv':
        export_csv(results, args.roast)

    if args.radar:
        plot_radar(results)


if __name__ == '__main__':
    main()
```

---

## 12.2 實作自驗錨點（AGENT 必執行）

> ⚠️ **AGENT 實作指示：** 程式碼實作完成後，**必須執行以下驗證組合，確認輸出數值在容許誤差範圍內後才算實作完成。** 若任何數值超出範圍，表示有函數被錯誤實作，需要回頭排查。

**驗證指令：**
```bash
python main.py --brewer xl --roast M --gh 50 --kh 30 --t-env 25 --altitude 0 --tds-floor 0.80 --top 1
```

**預期輸出範圍（M 焙 / GH=50 / KH=30 / 室溫 25°C / 海平面）：**

| 指標 | 預期範圍 | 說明 |
|---|---|---|
| 最佳水溫 | 89–95°C | M 焙 base_temp=92，搜尋空間 89–95 |
| 最佳研磨刻度 | 4.0–5.5 | 中焙中細研磨典型範圍 |
| 最佳被動浸泡 | 90–180s | M 焙中等浸泡 |
| 最佳豆量 | 20–26g | XL 中段豆量 |
| EY | 18–22% | SCA 最佳萃取率 18–22% |
| TDS | 1.10–1.35% | SCA 最佳濃度 1.15–1.35% |
| 風味評分 | > 70 / 100 | 低於此值表示評分函數異常 |
| `t_slurry` | 比壁溫低 3–7°C | 比熱混合 + 機身熱容，XL 30g 約 −6°C |

**若數值超出範圍，優先檢查：**
1. EY 偏低（< 15%）→ `K_BASE` 注入異常或 `T_ENV` 未正確覆寫
2. TDS 偏高（> 1.5%）→ `calc_retention` 或 `water_ml` 傳參錯誤
3. 風味評分全部 < 50 → `flavor_score` 的 `roast_code` 或 `t_slurry` 傳參順序錯誤
4. `t_slurry` 等於 `temp` → `BREWER_TEMP_DROP` 或比熱混合公式未正確實作

---

## 13. 檔案結構

```
aeropress_optimizer/
├── main.py
├── constants.py             # ⚠️ 所有 §0 常數定義於此；以下為版本摘要（以最新為準）
│                            #   v5.8r：TDS_BROWN_WATER_FLOOR=0.80、COFFEE_SPECIFIC_HEAT_RATIO=0.33
│                            #          T_ENV=25.0（CLI --t-env 覆寫）
│                            #          TEMP_BOILING_POINT=100（CLI --altitude 覆寫）
│                            #   v5.7：SW_AROMA_SLOPE=0.02、ASHY_SLOPE=3.0
│                            #   v5.6：SWIRL_RESET_FRACTION=0.35
│                            #   v5.5：CONC_GRADIENT_COEFF=0.5、BED_COMPACTION_COEFF=0.15、
│                            #          HARSHNESS_SLOPE=4.0、PRESS_EQUIV_FRACTION=0.15、
│                            #          K_CGA_TIME=0.015、CGA_TIME_MAX=0.50、K_AC_DECAY=0.0035
│                            #   v5.3：ARRHENIUS_COEFF=0.05、COOL_RATE=0.0008（修正 0.02）
│                            #   v5.1：K_PS=0.005、PS_TIME_MAX=0.20、CGA_ASTRINGENCY_*、
│                            #          MG_FRAC_AC_SW_MULT=0.16、MG_FRAC_PS_CGA_MULT=0.08
│                            #   v4.x：CHANNELING_*、DARCY_PRESS_EXP、ASYM_*_MULT、
│                            #          TDS_PREFER、TDS_GAUSS_SIGMA_*、KH_PERCEPT_DECAY=150
│                            #          SWIRL_CONVECTION_BASE=1.0（v4.8 修正；v4.7 以前舊值 0.5，已廢棄）
│                            #          SWIRL_DOSE_REF=18
│                            #   v3.9：BREWER_TEMP_DROP=2.5、MEL_BITTER_COEFF dict
├── models/
│   ├── ey_model.py          # calc_ey()（v5.5：有限溶劑 brew_capacity 修正 _ey_max）
│   │                        #           （v5.4：T_avg 時間平均溫度 Arrhenius）
│   │                        # calc_fines_ratio()（v3.8：動態細粉率）
│   │                        # _calc_t_eff()（v3.7，輸入改為 t_slurry + t_kinetic）
│   ├── tds_model.py         # calc_retention(roast_code, dial) → float
│   │                        # calc_tds(roast_code, dose, ey, dial, water_ml=400) → float
│   │                        # calc_swirl_wait(dial) → int
│   │                        # calc_press_time(dose, dial, steep_sec=120) → int   ← v5.4 加入 steep_sec
│   │                        # apply_channeling(ey, compounds, press_sec) → (float, dict)
│   ├── compounds.py         # predict_compounds(roast_code, temp, dial, steep_sec, ey,
│   │                        #                   water_kh=30, water_mg_frac=0.40,
│   │                        #                   press_equiv=0, pour_offset=0) → dict
│   └── scoring.py           # flavor_score(actual_raw, ideal_abs, tds, roast_code,
│                            #              water_kh=30, t_slurry=90, temp_initial=90) → float
│                            #   ⚠️ 八層架構（v5.7 定版）：
│                            #   層1 余弦相似度 | 層2 Huber 濃度接近（非對稱）| 層3 甜酸比
│                            #   層4 醇苦比（MEL 係數）| 層5 TDS 高斯（動態 W3）
│                            #   層6 CGA 澀感絕對閾值 | 層7 酸澀協同（AC×CGA）
│                            #   層8 焦澀協同（MEL×CGA，僅 MD/D）
├── data/
│   ├── roast_table.py       # ⚠️ AGENT 實作指示：ROAST_TABLE 定義於 constants.py（§0）
│   │                        #   此檔可選擇性實作為 from constants import ROAST_TABLE 的重導出
│   │                        #   或直接由各模型 from constants import ROAST_TABLE 使用，二擇一即可
│   ├── ideal_flavor.py      # ⚠️ 同上：IDEAL_FLAVOR、TDS_ANCHORS 定義於 constants.py（§0）
│   │                        #   build_ideal_abs() 於 models/scoring.py，直接 import constants 使用
│   └── water_presets.py     # WATER_PRESETS（含 BWT，v3.6）+ get_water_preset() 函數
├── optimizer.py             # optimize()（v3.9：flavor_score 調用加入 roast_code；
│                            #            輸出新增 t_kinetic、mel_bitter_coeff）
├── output/
│   ├── terminal.py          # 新增漿體溫度、動力學等效時間、焦苦修正顯示
│   ├── export.py            # JSON/CSV 新增 derived 欄位
│   └── radar.py
└── README.md
```

> ⚠️ **AGENT 強制實作規則：全域常數注入的模組隔離（v5.8s 新增）**
>
> `T_ENV`、`TEMP_BOILING_POINT`、`TDS_BROWN_WATER_FLOOR` 三個常數由 `main.py` 在執行期以 CLI 參數覆寫：
> ```python
> constants.T_ENV = args.t_env
> constants.TEMP_BOILING_POINT = 100.0 - args.altitude / 300.0
> constants.TDS_BROWN_WATER_FLOOR = args.tds_floor
> ```
> 此覆寫**只有在子模組以屬性存取方式引用時才生效**。
>
> | 引用方式 | CLI 覆寫是否生效 | 說明 |
> |---|:---:|---|
> | `import constants` → 使用 `constants.T_ENV` | ✅ 生效 | 每次存取都經由模組物件讀取最新值 |
> | `from constants import T_ENV` → 直接使用 `T_ENV` | ❌ 靜默失效 | import 時綁定的是當時的值（25.0），main.py 的覆寫永遠看不到 |
>
> **強制要求：** `ey_model.py`、`tds_model.py`、`compounds.py`、`scoring.py`、`optimizer.py` 中所有存取上述三個常數的程式碼，**必須**以 `constants.T_ENV`（而非 `T_ENV`）的形式存取。違反此規則的函數，`--t-env`、`--altitude`、`--tds-floor` 等 CLI 參數將靜默無效。
>
> **建議的標準引用模式：**
> ```python
> # 各子模組頂端
> import constants
>
> def calc_ey(...):
>     r = constants.COOL_RATE          # 非環境覆寫常數，可也用此模式統一風格
>     t_slurry = t_mix - constants.BREWER_TEMP_DROP
>     T_avg = constants.T_ENV + ...    # ← 必須用 constants.T_ENV
>     ...
>
> def flavor_score(...):
>     if tds < constants.TDS_BROWN_WATER_FLOOR:  # ← 必須用 constants.TDS_BROWN_WATER_FLOOR
>         final *= ...
> ```

---

### 13.1 output 模組函數最小骨架（AGENT 必實作）

> ⚠️ **AGENT 實作指示：** 下列四個函數為 `output/` 模組的最小實作規格，包含完整簽名與各欄位資料來源。**必須逐參數實作，不得自行推斷缺失的欄位來源。**

```python
# output/terminal.py

def print_terminal(results: list[dict], roast_code: str, water_gh: float, water_kh: float) -> None:
    """
    results    : optimize() 回傳的 list[dict]（已依 score 降序排列）
    roast_code : 焙度代號（如 'M'），用於顯示 ROAST_TABLE[roast_code]['name']
    water_gh   : GH ppm（整數或浮點數）
    water_kh   : KH ppm（整數或浮點數）

    各欄位來源對照（§11.1 模板）：
      水溫           → r['temp']
      漿體起始溫     → r['t_slurry']
      刻度           → r['dial']
      細粉率         → r['fines_ratio'] × 100（%）
      被動浸泡       → r['steep_sec']（秒→分:秒格式）
      動力學等效時間 → r['t_kinetic']（秒→分:秒格式）
      Swirl 倍率     → 1.0 + constants.SWIRL_CONVECTION_BASE × (constants.SWIRL_DOSE_REF / r['dose'])
      豆量           → r['dose']
      EY             → r['ey']
      TDS            → r['tds']
      截留係數        → r['retention']
      壓降秒數       → r['press_sec']（阻力崩潰後顯示時間）
      靜置時間       → r['swirl_wait_sec']
      全程接觸時間   → r['total_contact_sec']
      物質絕對強度   → r['compounds']（dict，六個鍵值）
      甜酸比（實際） → r['compounds']['AC'] / r['compounds']['SW']（以 actual_abs 計算）
      甜酸比（理想） → 從 build_ideal_abs(roast_code, r['tds']) 計算
      醇苦比（實際） → r['compounds']['PS'] / (CA + CGA + MEL × MEL_BITTER_COEFF[roast_code])
      醇苦比（理想） → 從 build_ideal_abs(roast_code, r['tds']) 計算
      風味評分       → r['score']
      機型           → r['brewer']
      注水量         → r['water_ml']
    """
    ...


# output/export.py

def export_json(results: list[dict], roast_code: str, filepath: str = 'output.json') -> None:
    """
    results    : optimize() 回傳的 list[dict]
    roast_code : 焙度代號
    filepath   : 輸出路徑（預設 output.json）

    JSON 結構依 §11.2 規格：
      "input"            → roast_code + ROAST_TABLE[roast_code]['name'] + water_gh/kh（從 results[0] 不可得，需由呼叫端傳入或從 constants 讀取——
                           ⚠️ 簡化做法：在 export_json 簽名加入 water_gh, water_kh 參數，main.py 傳入）
      "hoffman_constants"→ water_ml = r['water_ml']、swirl_time_sec = constants.SWIRL_TIME_SEC（★ 不得硬編碼為 10）
      "results[i]"       → 依 §11.2 的 rank / score / vectors / derived / hoffman_flow / metrics / compounds_abs 格式

    mel_bitter_coeff 來源：from constants import MEL_BITTER_COEFF; MEL_BITTER_COEFF[roast_code]
    """
    ...


def export_csv(results: list[dict], roast_code: str, filepath: str = 'output.csv') -> None:
    """
    扁平化輸出：每個 result 為一行，欄位為 results[i] 所有 key + compounds 展開的六個子欄位。
    compounds dict 展開為 compounds_AC、compounds_SW... 等六欄。
    """
    ...


# output/radar.py

def plot_radar(results: list[dict], top_n: int = 3) -> None:
    """
    results : optimize() 回傳的 list[dict]；只繪製前 top_n 筆
    需要 matplotlib（import matplotlib.pyplot as plt）
    雷達圖六維：AC / SW / PS / CA / CGA / MEL
    資料來源：r['compounds']（六個物質的 raw 值），需正規化為 0–1 以供雷達圖顯示

    建議正規化方式：
      six_max = {k: max(r['compounds'][k] for r in results[:top_n]) for k in KEYS}
      normalized = {k: r['compounds'][k] / max(six_max[k], 1e-8) for k in KEYS}
    """
    ...
```

---

## 14. 模型已知限制

| 限制 | 說明 |
|---|---|
| 機身熱容為普適固定常數 | `BREWER_TEMP_DROP = 2.5°C` 基於熱力學比值推導（塑膠質量與水量等比例放大，失溫幅度與機型無關），未考慮環境溫度、注水速度的差異；精確值需量測注水後 5 秒的漿體溫度 |
| Swirl 對流倍率為估算值 | `SWIRL_CONVECTION_BASE = 1.0`（v4.8）無實驗依據；操作時間 `SWIRL_TIME_SEC = 5s` 同樣為估算值（真實手法約 3 下，可能更接近 3–4 秒）；兩者乘積決定等效補償時間，需以折射儀實測同步校正（見 §15 第 13 點）|
| 動態細粉率為線性估算 | `FINES_RATIO_DIAL_SLOPE = 0.04` 基於物理直覺，非 ZP6 實測值；實際分佈可能為非線性 |
| 熱平衡失溫為簡化公式 | 忽略杯體預熱狀態、注水速度、環境溫度等變數 |
| MEL 焦苦係數為主觀設定 | `MEL_BITTER_COEFF['MD'] = 0.5` 為保守估算；實際 MEL 焦苦轉換點取決於烘焙曲線與豆種 |
| 巨觀 EY 與微觀物質解耦 | `calc_ey` 與 `predict_compounds` 底層邏輯獨立，物質加總不等於總 EY（終極解法見 §15 第 10 點）|
| 感知過濾器係數為估算值 | `KH_PERCEPT_DECAY = 150`（v4.1 指數衰減版）基於緩衝化學推算，非感官測試數據；實際感知中和效率受咖啡原始 pH、溫度、個人敏感度影響 |
| Swirl 黏滯度函數為線性近似 | `swirl_mult = 1.0 + 0.5 × (18/dose)` 為一階近似；實際漿體黏滯度隨豆量的變化是非線性的（與溫度、細粉率、粒徑分佈有關），建議未來以實測 EY 反推校正 |
| TDS 偏好峰值為主觀先驗 | `TDS_PREFER` 字典基於一般感官認知（淺焙偏高濃度以突出酸質、深焙偏低以抑制焦苦），非個人化設定；建議實際沖煮後依個人喜好調整各焙度峰值。v4.2 升級為非對稱高斯（`SIGMA_LOW=0.15` / `SIGMA_HIGH=0.25`），兩個 Sigma 值均為主觀估算，建議以盲測評分（對稱偏差量的主觀評分差異）迭代校正 |
| 達西指數壓降為近似值 | `DARCY_PRESS_EXP = 0.6` 未經 AeroPress 實測；實際 Stall 閾值取決於細粉率分佈、濾紙類型（金屬濾紙 vs 紙濾紙）與施壓速率。v4.2 Bug Fix 後，18g 基礎壓降時間也受 `dial_modifier` 影響，極粗研磨（dial=6.5）夾緊至 `PRESS_TIME_MIN_FLOOR=15s` |
| 非對稱懲罰倍率為主觀設定 | `ASYM_BITTER_MULT / ASYM_SWEET_MULT = 1.5` 基於感官心理學直覺；建議未來以盲測評分數據（相同組合、不同苦澀/甜感偏差量）迭代校正 |
| 感官平衡懲罰為線性混合 | W1=0.15、W2=0.12 為主觀設定，建議實際沖煮後對照主觀評分調整 |
| 物質強度為半定量預測 | 基於物理化學原理建模，非 GC-MS 數據 |
| 各物質焙度基礎值為主觀先驗 | `ac_roast`、`sw_roast`、`ps_roast`、`ca_roast`、`cga_roast`、`mel_roast` 六組焙度字典均為感官經驗估算，非 GC-MS 或 HPLC 量測值；建議未來以分段萃取實驗（§15 #10）反推各物質的真實焙度依賴基準值 |
| 六維評分權重為主觀設定 | `WEIGHTS = {AC:1.2, SW:1.8, PS:1.5, CA:1.0, CGA:1.3, MEL:1.0}` 基於感官重要性直覺（甜感最重要、苦感最低），非盲測數據；建議以相同配方不同偏差方向的盲測評分反推各維度的真實感官權重 |
| K_PS/PS_TIME_MAX 為定性設定 | `K_PS=0.005`（大分子極慢擴散）與 `PS_TIME_MAX=0.20`（漸近線飽和值）基於分子量推理，非獨立物理量測；修正幅度受 PS 在六維向量中的權重（WEIGHTS['PS']=1.5）稀釋，對最終排名的邊際影響較小；建議以不同浸泡時間的 Body 感官評分間接校正 |
| K_MAX / EY_MIN 為設計選擇 | `K_MAX=0.060` 為速率常數安全夾緊上限（防止極細粉 + 高溫場景下 k 爆炸），`EY_MIN=14.0` 為搜尋空間過濾門檻（SCA 最低可接受萃取率附近）；兩者均為架構防呆而非物理量測值，若實測顯示正常配方的 k 或 EY 觸及夾緊邊界，應調整而非移除 |
| K_BASE/K_MIN 為暫定校準值 | `K_BASE=0.025`、`K_MIN=0.006` 以 M 焙基準配方（92°C/dial4.5/120s/22g）→ EY≈19% 為目標的二元搜尋校準值；v5.2 原值 0.010/0.003 在 v5.3 COOL_RATE 修正 + v5.4 T_avg 修正後產出不合理的 EY（12.5%）；暫定值待折射儀實測 3–5 組配方後精確校正（見 §15 第 3 點） |
| 注水流速為估算值 | `POUR_RATE=12 ml/s` 基於 Bonavita 鵝頸壺中高速注水的文獻數據推估（Brewista max=24、Fellow Stagg max=20、慢速手沖=3）；Hoffman 法為快速一次注滿（非緩慢繞圈），12 ml/s 為保守預設；實際流速因壺型、傾斜角度、水位高度而異；建議以電子秤+計時器量測「注滿 200/400ml 所需秒數」後直接校正 |
| 理想風味表為主觀先驗 | 建議實際沖煮後迭代校正 IDEAL_FLAVOR |
| 未考慮豆種與處理法差異 | 日曬／水洗／厭氧處理法會移動各類物質的基礎濃度 |
| 烘焙度截留率為推算估值 | `RETENTION_BASE` 字典數值（L+=2.00～D=2.50）基於烘焙物理推理，未經折射儀 + 磅秤實測（量測方法：固定條件沖煮後秤量出杯重，反推截留量）；深焙的研磨斜率（0.08）低於淺焙（0.10）亦為估算 |
| 咖啡因速率常數為估算值 | `K_CA = 0.030` 基於文獻描述（90s 內 85%+ 溶出）推算；實際值受豆種、研磨度、溫度影響；建議以不同浸泡時間（45s/90s/150s）量測折射儀 TDS 後，結合 CA 占比反推校正 |
| 斯托克斯沉降時間為線性近似 | `SWIRL_WAIT_SLOPE = 10`（每格研磨增減 10 秒）為一階線性近似；實際沉降速度與顆粒半徑平方、漿體黏滯度、溫度均有關，真實行為在極細端（dial<4.0）可能非線性加速；建議目視觀察不同研磨度的實際粉渣沉降時間後校正 |
| 沸點夾緊未含高海拔修正 | `TEMP_BOILING_POINT = 100` 預設為海平面值；現已支援 CLI `--altitude`（公尺）自動計算 `100 - altitude/300`。花蓮市區（≈10m）誤差 < 0.03°C 可忽略；台灣中高海拔（梨山 2000m → 93.3°C；合歡山 3416m → 88.6°C）影響顯著，建議山區使用者傳入實際海拔 |
| 高溫劣變閾值為估算值 | `SCORCH_PARAMS` 中各焙度的閾值與靈敏度基於化學知識與感官推理，非盲測數據；CGA 水解速率受豆種、pH 與具體溫度曲線影響。v4.5 改為連續函數後消除評分斷崖，但各焙度靈敏度仍需以高溫 vs 適溫同一食譜的盲測評分差異迭代校正 |
| 通道效應係數為估算值 | `CHANNELING_EY_SLOPE=0.005`（每秒 0.5% EY 衰減）、`CHANNELING_CGA_MULT=2.5`（局部過萃放大倍率）基於流體力學定性推理，非 AeroPress 實測值；實際通道效應的嚴重程度取決於施壓速率、濾紙類型、粉餅均勻度；建議以相同配方在不同施壓速度下量測 EY 與感官澀度後反推校正 |
| PS 溫度係數為估算值 | `PS *= 1.0 + (temp-90) * 0.015` 中斜率 0.015/°C 基於多糖體吸熱溶解的定性推理，未以不同溫度的出杯液體黏度或 Body 感官評分實測校正；各焙度、豆種的多糖體熱力學行為可能存在差異 |
| SW 甜感峰值溫度偏移為估算值 | `optimal_sw_temp = base_temp - 2` 的 `−2` 係數基於烘焙化學推理（M 焙錨點=90°C），未以不同溫度的甜感盲測數據校正；L+（98°C）與 D（83°C）的峰值偏移幅度尤其需要實測驗證 |
| 阿瑞尼斯速率係數為估算值 | `ARRHENIUS_COEFF=0.05`（每 °C ±5% 速率變化）基於一般固液擴散的活化能文獻值推算，非 AeroPress 專用實測值；不同物質（有機酸 vs 多糖體）的活化能可能不同，統一係數為一階近似；建議以不同溫度（82/90/98°C）固定其他參數的 EY 量測反推校正 |
| 質量分率正規化假設物質獨立 | `flavor_score` 入口的 `actual_raw` 正規化假設六大物質加總代表可溶物質的全貌，但實際可溶固體中還包含本系統未建模的微量物質（如脂質、三酸甘油脂等）；正規化後各物質的絕對濃度略低於真實值（因分母膨脹），但比例關係正確 |
| 通道效應阻力崩潰比為估算值 | `CHANNELING_COLLAPSE_RATIO=0.20` 基於流體力學定性推理（通道貫穿後阻力瓦解），非 AeroPress 實測；實際崩潰速度取決於通道直徑、粉餅厚度、施壓力道；建議以極細粉+大豆量場景的實際壓降時間觀察校正 |
| 牛頓冷卻率為估算值 | `COOL_RATE=0.0008` 基於熱力學估算（h×A/(m×c)≈0.00012）加實測經驗修正；合理範圍 0.0005–0.001，取決於活塞密封程度、環境溫度、注水量；建議以 §15 第 2 點的方案實測校正（浸泡開始與結束各量一次水溫，擬合牛頓冷卻曲線）。注意：v5.2 以前的 0.02 比真實值快 25–160 倍，為系統中隱藏最深的物理錯誤 |
| 壓降等效折算比為估算值 | `PRESS_EQUIV_FRACTION=0.15`（壓降效率≈被動浸泡的 15%）基於 v4.6 原始設計推理，非 AeroPress 實測；實際壓降萃取效率取決於流速、溫度、粉餅阻力；建議以相同配方不同壓降速度的 TDS 量測反推校正 |
| CGA/AC 指數常數為校準值 | `K_CGA_TIME=0.015`、`K_AC_DECAY=0.0035` 均以「搜尋空間邊界（240s）匹配舊線性值」為校準目標，非獨立物理推導；飽和極限 `CGA_TIME_MAX=0.50` 為估算值，建議以長浸泡（>300s）的 GC-MS 或感官數據校正 |
| T_avg 近似非精確 Arrhenius 積分 | $T_{avg}$ 是溫度的時間平均值，但阿瑞尼斯方程式中 $\langle e^{f(T)} \rangle \neq e^{\langle f(T) \rangle}$（Jensen 不等式）。在 AeroPress 溫度範圍（82–100°C）與 ARRHENIUS_COEFF=0.05 下，此近似誤差 < 2%，遠小於常數估算本身的不確定性；精確解需數值積分 $\bar{k} = \frac{1}{t}\int_0^t k_0 e^{A(T(\tau)-90)} d\tau$，計算成本高 70,525 倍且收益極低 |
| CGA 絕對閾值依賴 TDS_PREFER 估算 | v5.4 的 CGA 澀感分母錨定至 `build_ideal_abs(roast, TDS_PREFER)['CGA']`，TDS_PREFER 本身為主觀先驗（§14 已列）；TDS_PREFER 偏差會同時影響層 5（TDS 高斯）和層 6（CGA 閾值），建議以盲測校正 TDS_PREFER 後兩層自動同步 |
| 有限溶劑分配係數為估算值 | `CONC_GRADIENT_COEFF=0.5`（溶質分配係數 K_d）為極保守估算值；真實 K_d 取決於豆種、烘焙度、研磨度與水溫；18g→30g 的差異修正僅 ~0.6% EY_max，在搜尋空間中屬微弱修正；建議以不同豆量（18/24/30g）固定其他參數的 EY 量測反推校正 |
| 粉床壓實係數為估算值 | `BED_COMPACTION_COEFF=0.15` 基於斯托克斯沉降的定性推理，未以 AeroPress 實測壓降力道量測；v5.6 改以 `effective_compaction_time` 計算（已納入 Swirl 重置），實際壓實程度取決於細粉率、水溫（影響黏滯度）、容器幾何；建議以不同浸泡時間的壓降阻力（力量感測器或計時）校正 |
| Swirl 重置比例為理論推導值 | `SWIRL_RESET_FRACTION=0.35` 由斯托克斯沉降 + 渦流雷諾數（Re≈500）推導，非 AeroPress 實測；可懸浮粒徑 <80μm 的估算本身依賴細粉粒徑分佈假設；建議以不同浸泡時間（60s/120s/240s）的實際壓降力道量測反推校正 |
| 自由溶劑修正精度受截留率約束 | `free_water = water_ml − dose × calc_retention(roast_code, dial)`；`calc_retention` 本身為推算估值（RETENTION_BASE 未實測），截留率不確定性直接傳播至 `brew_capacity`；30g D 焙的修正差異 −0.9%，在截留率誤差範圍內；建議以磅秤實測出杯重後先校正截留率，再評估 brew_capacity 修正的有效性 |
| 酸澀協同懲罰斜率為估算值 | `HARSHNESS_SLOPE=4.0` 基於感官心理學定性推理（與 CGA_ASTRINGENCY_SLOPE 設計一致），非盲測數據；實際「金屬酸澀」感知閾值因人而異；建議以「AC 與 CGA 同時超標 vs 單一超標」的感官盲測評分差異校正 |
| 焦澀協同懲罰斜率為推導值 | `ASHY_SLOPE=3.0`（v5.7）由酸澀協同按感官閾值比例推導，非盲測數據；僅對 MD/D 焙度啟用；建議以「MEL 與 CGA 同時超標 vs 單一超標」的深焙盲測評分差異校正；若深焙排名在實測中已符合預期可考慮調低 SLOPE |
| 高溫 SW 逸散斜率為估算值 | `SW_AROMA_SLOPE=0.02`（v5.7）及閾值 95°C 基於揮發性芳香物質熱降解的感官化學推理，非量測數據；v5.8 觸發變數改為 `temp_initial`（壺溫），修正大豆量免疫問題；實際逸散率受豆種（含不同揮發物比例）、注水速度、容器開口面積影響；建議以相同配方、不同 temp_initial（90/95/100°C）的感官盲測甜感評分差異校正 |
| 注水湍流等效未實作（澄清） | v5.7 明確不採納注水正向湍流等效，`pour_equiv` 從未寫入程式碼；`t_kinetic = max(0, steep_sec - pour_offset) + SWIRL_TIME_SEC × swirl_mult + press_equiv` 無代數對消問題；Gemini v5.8 壓力測試描述的「`pour_offset` 與 `pour_equiv` 相消」在程式碼中不存在（此為 Gemini 第三次描述不存在的程式碼，前兩次：v4.5 時序悖論、v4.6 漸近線 Bug）；注水湍流等效待折射儀 A/B 實測後決定（§15-18）|
| Spritzer / Jeju GH/KH 為估算值 | `WATER_PRESETS` 中 Spritzer（GH=85, KH=60）與 Jeju（GH=18, KH=15）數值來自品牌公開資料與文獻估算，不同批次、產地可能有差異；建議以水族滴定試劑實測後覆蓋 |
| TDS 動態懲罰權重為主觀設定 | `TDS_W3_LOW=0.25` / `TDS_W3_HIGH=0.10` 基於「水感是不可逆缺陷、濃郁可補救」的感官判斷；實際最佳懲罰強度因人喜好而異，建議以盲測評分（相同輪廓、不同 TDS 的主觀評分差異）迭代校正 |
| 鈣鎂離子萃取偏好係數為估算值 | `MG_FRAC_AC_SW_MULT = 0.16`（Mg²⁺ 對 AC/SW 的最大正向乘數）與 `MG_FRAC_PS_CGA_MULT = 0.08`（Ca²⁺ 對 PS/CGA 的最大正向乘數）均基於「Mg²⁺ 偏好小分子有機酸、Ca²⁺ 偏好大分子多糖體」的化學親和力推理，量級為純粹估算值，非 GC-MS 或感官盲測數據；8%/16% 的實際影響幅度待「純鎂水 vs 純鈣水」對照實驗驗證（見 §15 第 27 點）|
| 細粉/粗粉速率倍率為文獻估算值 | `K_FINES_MULT = 10.0`（細粉萃取速率為粗粉的 10 倍）與 `K_BOULDERS_MULT = 0.55` 均來自文獻經驗法則（Rule of Thumb）；「細粉約快 10 倍」的數值因磨豆機機型與細粉定義（<100μm 或 <200μm）不同，真實倍率可能介於 5–15 倍之間；建議以篩粉器分離細粉後單獨萃取量測 EY，反推真實倍率（見 §15 第 3 點擴充內容）|
| 褐水防禦底板為個人化感官設定 | `TDS_BROWN_WATER_FLOOR = 0.80`（低於此 TDS 觸發二次懲罰）基於大眾對「水感咖啡」的普遍認知底線，非個人化量測值；偏好低濃度茶韻感（Tea-like Elegance）的使用者，0.75% 甚至更低的 TDS 可能屬「優雅」而非「洗鍋水」；建議以實際沖煮 0.70%–0.90% TDS 的對照組，依個人感受調整此閾值（見 §15 第 28 點）|
| Huber Loss 轉折點為數學超參數 | `CONC_HUBER_DELTA = 0.5` 為 Huber Loss 的線性/二次懲罰切換閾值（相對誤差 > 50% 時懲罰從二次改為線性），屬機器學習最佳化超參數（Hyperparameter），**無直接物理意義**；此值控制懲罰曲線的平滑度與極端值防發散能力，不需要物理實測；若感官盲測後發現評分分布過度集中或分散，可以 ±0.1 步進調整此值，無需配合任何量測實驗 |

---

## 15. 後續迭代方向

1. **實測校正 BREWER_TEMP_DROP**：注水後立即（5 秒內）量測漿體溫度，與手沖壺水溫的差值扣除 `dose × 0.15` 即為機身熱容修正量。理論預測此值與機型（標準版/XL）無關，建議在不同室溫下以兩款機身各重複量測，驗證比值不變性。
2. **實測校正 COOL_RATE 與 T_ENV**：在浸泡開始與結束時各量一次水溫，擬合牛頓冷卻曲線。
3. **實測校正 K_BASE 與雙峰參數**：以不同研磨度的 EY 量測（折射儀）反推速率常數；條件允許時可篩網分離細粉（建議 100μm 篩孔）實測細粉率，校正 `FINES_RATIO_DIAL_SLOPE`。
   - **K_FINES_MULT / K_BOULDERS_MULT 擴充實測：** 以篩粉器完整分離細粉後，取等量細粉（佔比對應刻度的估算細粉率）單獨浸泡 15s / 30s / 60s，折射儀量測各時間點 TDS；以全粉對照組擬合一階動力學曲線，再擬合細粉曲線，計算 $k_{fines} / k_{boulders}$ 真實比值。文獻 Rule of Thumb 為 10 倍，ZP6 真實值預期介於 **5–15 倍**（細粉定義 <100μm vs <200μm 對結果影響顯著）；同步反推 `K_BOULDERS_MULT` 相對 `K_BASE` 的實際縮放比例。
4. **FINES_RATIO 升級為二次函數**：細粉率在極細端可能呈加速增長（非線性），校正後改為 $f(dial) = a + b(DIAL_{BASE} - dial) + c(DIAL_{BASE} - dial)^2$。
5. **Swirl 對流倍率實測**：對同一食譜以不同 steep_sec（例如 60s 與 120s）量測 EY，控制 Swirl 強度，反推 `SWIRL_CONVECTION_MULT` 的真實值。
6. **MEL_BITTER_COEFF 細化**：區分 MD 與 D 的 MEL 焦苦係數（目前同為 0.5），或加入 LM/M 的微量 MEL 係數（0.1），使過渡更平滑。
7. **calc_press_time 進一步精細化**：`PRESS_DIAL_FACTOR` 建議實際施壓測試後校正；考慮改為查表而非線性公式。
8. **感官平衡懲罰擴充**：考慮 SW/CA（甜苦比），但注意各項 W 之和不應超過 0.35。
9. **天然礦泉水 GH/KH 實測**：以水族用試劑對 Spritzer、Jeju Samdasoo 等逐一滴定（100ml 直接滴定），確認各離子分量後建立 `WATER_PRESETS` 條目。
10. **終極目標：六大物質獨立動力學（架構替換）**
    - **現狀矛盾：** `calc_ey`（嚴謹雙峰動力學）與 `predict_compounds`（經驗乘數）底層邏輯解耦，物質加總不等於總 EY。
    - **終極解法：** 為六大物質各自建立獨立雙峰動力學方程式，$EY_i(t) = f(k_{i,fines}, k_{i,boulders}, T_{eff,i})$，合計 $\sum EY_i \equiv EY_{total}$。
    - **最小可行校正路徑（MVE）：**
      1. 以可溶性濾紙分段萃取（15s / 60s / 120s / 240s），用 HPLC 或近似儀器量測各時間點的 AC/SW/CA 絕對濃度
      2. 對每個物質擬合一階動力學曲線，推算 $k_i$ 值
      3. 細粉率修正：用篩網分離細粉（< 100μm），各別萃取量測，估算 $k_{i,fines}$ 與 $k_{i,boulders}$ 比值
      4. 以實測 $k_i$ 替換 `predict_compounds` 的經驗乘數
    - **前提條件：** 需要 HPLC 或高精度分離量測設備，或與具備 GC-MS 設備的研究機構合作。在此條件滿足前，v3.9 的混合模型（嚴謹巨觀 + 經驗微觀）是最佳可行近似。

11. **GH 修正移至動力學速率常數（Gemini 建議，理論正確、暫緩實作）**
    - **問題描述：** 現有的 GH 修正以最終 EY 乘數呈現（`ey *= 1.0 + (water_gh - 20) / 800`），在化學動力學上不嚴謹：GH（Ca²⁺/Mg²⁺）作為溶劑催化劑，影響的是萃取速率 $k$，而非熱力學極限 $EY_{max}$。純 RO 水（GH≈0）在 $t\to\infty$ 時仍能完全萃出物質，只是速率極慢。
    - **理論正確修正方向：**
      ```python
      gh_catalyst = 1.0 + (water_gh - 50) / 1000   # 以 50ppm 為基準 1.0
      k_b = (K_BASE * K_BOULDERS_MULT * (1.8 ** ((DIAL_BASE - dial) / 0.5))) * gh_catalyst
      ```
    - **暫緩原因：** GH 影響幅度相對較小（±10%），修改速率常數需重新校正 $k_b$/$k_f$ 的量級關係，且引入另一個估算常數（`gh_catalyst` 的分母 1000）的邊際誤差可能大於原始 EY 乘數的近似誤差。建議待第 10 點六大物質獨立動力學完成後，以實測 $k_i$-GH 對照數據驅動此修正。

12. **Swirl 時溫積分的數學澄清（Gemini 建議，不採納，附數學說明）**
    - **Gemini 的建議：** 拆分 EY_steep + EY_swirl，以末端溫度 $T_{end}$ 計算 Swirl 的萃取貢獻，認為現有公式「以平均溫度計算 Swirl 的低溫對流」。
    - **為何不採納：** `_calc_t_eff` 是速率加權有效溫度的**封閉解析積分**，其本質是：
      $$T_{eff} = \frac{\int_0^t k \cdot e^{-k\tau} \cdot T(\tau) \, d\tau}{\int_0^t k \cdot e^{-k\tau} \, d\tau}, \quad T(\tau) = T_{env} + (T_{slurry} - T_{env}) e^{-r\tau}$$
      積分已完整涵蓋牛頓冷卻曲線——後期 $T(\tau)$ 低，萃取速率 $k \cdot e^{-k\tau}$ 的加權也小，乘積自然遞減，$T_{eff}$ 已被正確拉低。`t_kinetic` 的延伸是速率補償（等效更長浸泡），末端低溫效應**隱含在解析解中，無需另行拆分**。
    - **未來驗證方向：** 實測「相同 steep_sec，Swirl 前後的 EY 差值」與「多 15 秒被動浸泡的 EY 差值」，若一致則現有 `SWIRL_CONVECTION_MULT` 近似成立；若有系統性偏差，再考慮拆分計算。

13. **實測校正 SWIRL_TIME_SEC 與 SWIRL_CONVECTION_BASE（v4.8 新增）**
    - **背景：** v4.8 將 `SWIRL_TIME_SEC` 從 10 修正為 5（真實操作約 3 下），但準確值仍不確定（可能為 3–5 秒）；`SWIRL_CONVECTION_BASE = 1.0` 決定對流補償倍率，同樣無實測依據。
    - **建議實驗方案（折射儀）：**
      1. 固定所有參數（豆種、研磨度、溫度、豆量）
      2. A 組：浸泡 120s + Swirl（正常操作），量測出杯 TDS
      3. B 組：浸泡 120s，**不做 Swirl**，直接靜置等壓，量測出杯 TDS
      4. C 組：浸泡 135s，不做 Swirl（增加 15s 被動浸泡作為對照），量測出杯 TDS
      5. 以 TDS 差值 A−B 代入模型，反推 Swirl 等效補償秒數；與 C−B 比較，確認 `SWIRL_CONVECTION_BASE` 的合理倍率
    - **預期結果：** 若 A−B ≈ C−B，說明 Swirl 等效約 15s 被動浸泡（支持舊值）；若 A−B 明顯小於 C−B，說明等效補償低於 15s（支持 v4.8 新值）。

14. **濾材差異建模（v4.9 新增，Gemini 建議二a 暫緩原因）**
    - **現狀：** 以乘以固定係數 `FILTER_PAPER_PS_RETENTION = 0.90` 修正 PS 的方式不影響組合排名（量對消），屬無效修正，故未採納。
    - **真正有效的濾材建模方向：** 為「紙濾」vs「金屬濾」分別建立 `IDEAL_FLAVOR_PAPER` / `IDEAL_FLAVOR_METAL` 兩套目標向量，在 CLI 加入 `--filter paper|metal` 參數，讓 `build_ideal_abs` 依濾材選擇對應目標。
    - **前提條件：** 需以同一食譜分別用紙濾和金屬濾沖煮，量測 TDS 差值與感官 Body 評分，推算兩套向量的 PS 比例差異。

15. **自由溶劑修正（v5.6 已實作）**
    - **實作內容：** `brew_capacity` 分子改為 `free_water = water_ml − dose × calc_retention(roast_code, dial)`，以真正可自由擴散的溶劑量取代總注水量。
    - **剩餘不確定性：** `calc_retention` 本身為推算估值（§14 已列），截留率誤差直接傳播至此修正；精度提升的前提是先以磅秤實測出杯重校正截留率（§15 第 1 點的附帶收益）。

16. **粉床壓實升級：Swirl 擾動重置（v5.6 已實作）**
    - **實作內容：** `effective_compaction_time = steep_sec × (1 − SWIRL_RESET_FRACTION) + swirl_wait_sec`，`SWIRL_RESET_FRACTION = 0.35`（斯托克斯沉降理論推導，Re≈500 渦流可懸浮 <80μm 顆粒約佔 35%）。
    - **校正方向：** 以不同浸泡時間（60s/120s/240s）量測實際壓降阻力（同施壓速度下計時），反推 SWIRL_RESET_FRACTION 的真實值；若實測值與 0.35 差異 >10%，建議更新常數。

17. **深焙焦澀協同懲罰（v5.7 已實作，第 8 層）**
    - **實作內容：** `ashy_penalty = exp(−3.0 × mel_excess × cga_excess)`，僅 MD/D 啟用，`cga_excess_ratio` 複用層 7 已計算值，零額外 overhead。
    - **校正方向：** 以深焙（D）高溫長浸泡組合（最高風險場景）跑 Top 10 排名，確認無過萃組合入榜；若仍有，可調低 `ASHY_SLOPE` 至 2.5；若排名已符合預期可維持 3.0。

18. **注水湍流等效萃取實測（v5.7 新增，不採納 Gemini 建議後列入）**
    - **問題描述：** Gemini 建議將 `pour_offset`（時間扣減）改為正向湍流等效時間加回 `t_kinetic`，物理方向正確但參數無依據（效率假設 50% 屬估算）。
    - **不採納理由：** 現有 `pour_offset` 已修正「注水時間算入浸泡時間」的系統性偏差；改為正向加法等於多加 ~33s 的估算萃取，在 POUR_RATE 本身就是估算值的情況下屬過擬合。
    - **建議實驗方案：** A 組正常操作（pour_offset 修正）；B 組人工延遲注水（注水後等 33s 才計浸泡時間）；量測 TDS 差值，若 A−B ≈ 0 則 pour_offset 設計正確；若 A > B，說明注水湍流確實有額外萃取貢獻，可考慮加入正向等效項。

19. **蒸發率 TDS 濃縮補償（v5.7 新增）**
    - **問題描述：** 90–100°C 浸泡 2–4 分鐘，AeroPress 敞口部分會蒸發 3–8g 水，導致實際 TDS 比模型預測略高。
    - **建議實作方向（待實測後）：** `effective_water = water_ml − EVAPORATION_RATE × steep_sec`（`EVAPORATION_RATE` 估算約 0.02–0.04 g/s），代入 `calc_tds` 分母。實測方法：固定條件下浸泡前後各秤量 AeroPress 總重，差值扣除出液重即為蒸發量。

20. **細粉率焙度動態補償（v5.7 新增）**
    - **問題描述：** `calc_fines_ratio` 僅依賴研磨刻度，未考慮烘焙度對豆質脆度的影響。深焙（D）結構酥鬆，相同刻度下細粉量比淺焙多 30–50%；現有系統低估深焙的通道效應風險。
    - **建議實作方向（待篩粉實測後）：** 將 `FINES_RATIO_BASE` 從固定常數改為焙度字典矩陣（`L+: 0.10, L: 0.11, LM: 0.13, M: 0.15, MD: 0.18, D: 0.22`，數值為估算），待篩粉器實測後校正各焙度的真實細粉率基準值。

21. **粉床壓實豆量動態補償（v5.8 新增）**
    - **問題描述：** v5.6/v5.7 的 `compaction_mult` 以 `effective_compaction_time` 為唯一變數，未考慮豆量影響。30g 豆量沉積在濾紙的細粉**總質量**是 15g 的兩倍，緻密阻水層厚度亦成比例增加，壓降阻力暴增不只與時間有關。
    - **建議實作方向（待推拉力計實測後）：** 升級為時間與豆量的二元函數：
      ```python
      compaction_mult = 1.0 + (effective_compaction_time / 240) * (dose / 18) * BED_COMPACTION_COEFF
      ```
      實測方法：以推拉力計量測不同豆量（18/24/30g）在相同浸泡時間下的壓降阻力，擬合豆量係數。

22. **水合放熱 T_slurry 截距微調（v5.8 新增）**
    - **問題描述：** v5.8r 的比熱混合方程式假設咖啡粉溫 = T_ENV（25°C），未考慮乾燥多孔咖啡粉吸水時的水合放熱（Hydration Enthalpy）。此放熱反應會微弱抬升實際 t_slurry 約 0.5–1.0°C。
    - **建議實作方向（待溫度計實測後）：** 以高精度數位溫度計量測粉水混合後 5 秒內的漿體溫度，與比熱方程式預測值比較差值；若差值系統性為正，微調 `COFFEE_SPECIFIC_HEAT_RATIO` 或引入微小正偏移常數。

23. **predict_compounds 的 `ey` 參數孤兒化（v5.8r 新增，Gemini 建議列入）**
    - **問題描述：** `predict_compounds(roast_code, temp, dial, steep_sec, ey, ...)` 簽名接收 `ey` 但函數內部從未使用——所有物質的推算已解耦為溫度 × 研磨 × 時間的獨立動力學。
    - **暫緩原因：** 移除參數會破壞 §10 `optimize()` 的調用簽名，屬程式碼重構（非邏輯修正）。且 §15 第 10 點「六大物質獨立動力學」未來可能重新需要 EY 參數。
    - **建議處置：** 實作時在函數體內加入 `_ = ey  # reserved for future use` 抑制 linter 警告，不移除參數。

24. **通道效應非線性崩潰（v5.8r 新增，Gemini 建議列入）**
    - **問題描述：** `bypass_ratio = (press_sec − 60) × 0.005` 為線性模型，但粉餅裂縫形成後水流集中是連鎖指數反應。
    - **暫緩原因：** 線性斜率在 `CHANNELING_BYPASS_MAX = 0.15` 夾緊下，與指數函數在 press_sec < 90s 的搜尋空間內差異極小（< 0.02）。不確定性遠小於 `CHANNELING_EY_SLOPE` 本身的估算誤差。
    - **建議實測方向：** 以 30g + 極細粉實際壓降，量測不同 press_sec 下的出杯 TDS 衰減曲線，擬合 bypass 函數形狀。

25. **T_ENV 環境溫度參數化（v5.8r 新增，Gemini 建議列入）**
    - **問題描述：** `T_ENV = 25.0` 硬編碼為室溫，影響比熱混合方程式（粉溫 = T_ENV）與牛頓冷卻曲線（終態溫度 = T_ENV）。夏天冷氣房（25°C）與冬天寒流（15°C）差 10°C，對 t_slurry 影響約 0.5°C，對長浸泡冷卻速率影響更大。
    - **建議實作方向：** CLI 新增 `--t-env`（預設 25），代入所有使用 T_ENV 的公式。低成本高收益。

26. **CGA 研磨度依賴（v5.8r 新增，Gemini 建議列入）**
    - **問題描述：** PS 有 `+= max(4.5 − dial, 0) × 0.15` 的研磨度依賴，但 CGA 完全無 dial 變數。極細粉（dial < 4.0）大量粉碎細胞壁，CGA 釋放率應高於粗粉——即使不發生通道效應（`CHANNELING_CGA_MULT` 僅在 press > 60s 觸發），細粉本身的 CGA 基礎量也更高。
    - **暫緩原因：** 修正幅度（估算 ±10%）小於 CGA 基礎值（`cga_roast` 字典）的估算不確定性。待感官回饋後校正。

27. **鈣鎂離子萃取偏好係數實測（MG_FRAC_AC_SW_MULT / MG_FRAC_PS_CGA_MULT）**
    - **問題描述：** `MG_FRAC_AC_SW_MULT = 0.16` 與 `MG_FRAC_PS_CGA_MULT = 0.08` 的量級為純粹估算值——Mg²⁺ 對酸甜感的正向強化幅度 16%、Ca²⁺ 對醇厚/澀感的提升幅度 8%，均無實驗依據（§14 已列）。
    - **建議實驗方案：** 以相同食譜（固定 roast / temp / dial / steep / dose），分別配製：
      1. 純鎂水：以 MgCl₂ 溶液調製 GH=60 ppm（全由 Mg²⁺ 貢獻，KH ≈ 0）
      2. 純鈣水：以 CaCl₂ 溶液調製相同 GH=60 ppm（全由 Ca²⁺ 貢獻，KH ≈ 0）
      3. 以折射儀確認兩組 TDS 近似相同（排除濃度差異干擾）
      4. 進行感官盲測（酸感 / 甜感 / Body / 澀感四維度打分）
    - **校正方式：** 酸甜感知差異百分比直接對應 `MG_FRAC_AC_SW_MULT`；Body 與澀感差異對應 `MG_FRAC_PS_CGA_MULT`。若兩組在感官上無顯著差異（p>0.1），可考慮移除這兩個係數以簡化模型。

28. **褐水防禦底板個人化校正（TDS_BROWN_WATER_FLOOR）**
    - **問題描述：** `TDS_BROWN_WATER_FLOOR = 0.80` 基於大眾對「水感咖啡」的普遍認知底線，但部分精品咖啡使用者對 L+/L 焙度的極淡萃取（Tea-like Elegance）有不同的感官評價（§14 已列）。
    - **建議個人化方法：** 以相同 L+ 焙度豆，分別沖煮 TDS 落在 0.70% / 0.75% / 0.80% / 0.85% 的四組對照杯（調整豆量：14g / 16g / 18g / 20g，其餘參數固定），依序盲評「哪一杯開始讓你感覺水感/洗鍋水」，所記錄的 TDS 臨界值即為你的個人化 `TDS_BROWN_WATER_FLOOR`；若底線低於 0.80%，直接在 §0 調低此常數即可，無需其他修改。

---

## 16. 校正優先順序路線圖

> 本節將 §14 已知限制與 §15 待辦事項中所有需要實測或人工校正的參數，依**難易度（E）與重要度（I）**統一評分排序，供實作階段按序執行。

### 16.1 評分方法

$$優先分 = E \times 2 + I \times 1$$

**難易度 E（1–5）：** 1 = 需要 GC-MS 等研究級設備，5 = 純代碼或日常廚房器材即可完成。難易度加權×2，因為「做得到」比「影響大」更能決定實際執行順序。

**重要度 I（1–5）：** 1 = 邊際修正（對排名幾乎無感知差異），5 = 核心錨點（偏差會系統性扭曲所有輸出）。

> 同分時以重要度高者優先；純代碼改動（不需量測）標記 ★，可立即執行。

---

### 16.2 完整排序表

| 排名 | 參數 / 參數群 | §15 | E | I | 分 | 所需工具 | 說明 |
|:---:|---|:---:|:---:|:---:|:---:|---|---|
| **1** | `RETENTION_BASE` 字典（各焙度截留率） | #1 | **5** | 4 | **14** | 電子秤 | 量出杯重反推截留量；是 `calc_tds` 與 `brew_capacity` 的共同上游，一次校正兩個模型 |
| **2** | `T_ENV` 參數化 → CLI `--t-env` ★ | #25 | **5** | 3 | **13** | 純代碼 | 無需量測，直接加 CLI 參數；冬夏室溫差 10°C 影響漿體溫及冷卻曲線 |
| **3** | `TDS_PREFER` + `TDS_GAUSS_SIGMA`（TDS 高斯峰值） | — | 4 | 4 | **12** | 折射儀 + 感官杯測 | 直接決定評分系統的「甜蜜點」，偏差會同步拖偏層 5（TDS 高斯）和層 6（CGA 絕對閾值）|
| **4** | `POUR_RATE`（注水流速） | — | **5** | 2 | **12** | 電子秤 + 計時器 | 秤量注滿 400ml 所需秒數；影響 `pour_offset`，從而影響 `t_kinetic` 起始點 |
| **5** | `TDS_BROWN_WATER_FLOOR`（褐水底板） | #28 | **5** | 2 | **12** | 只需沖四杯咖啡 | 盲評 0.70/0.75/0.80/0.85% 四組對照杯，確認個人底線；直接在 §0 覆寫即可 |
| **6** | `BREWER_TEMP_DROP` + `COFFEE_SPECIFIC_HEAT_RATIO`（熱平衡） | #1, #22 | 4 | 3 | **11** | 精密數位溫度計 | 注水後 5 秒內量漿體溫；同一實驗可同時校正兩個熱力常數 |
| **7** | `COOL_RATE`（牛頓冷卻速率） | #2 | 4 | 3 | **11** | 精密數位溫度計 | 浸泡開始與結束各量一次水溫，擬合冷卻曲線；可與第 6 項合並為同一實驗 |
| **8** | `SWIRL_TIME_SEC` + `SWIRL_CONVECTION_BASE`（Swirl 等效倍率） | #13 | 4 | 3 | **11** | 折射儀 | A/B/C 三組 TDS 對照實驗（§15 #13 詳述）；與第 9 項共用折射儀 |
| **9** | `K_BASE` + `ARRHENIUS_COEFF`（萃取速率核心常數） | #3 | 3 | **5** | **11** | 折射儀（多組） | 系統中影響最廣的兩個常數；3–5 組不同溫度 × 研磨度食譜的 EY 量測，反推二元組 |
| **10** | `IDEAL_FLAVOR`（六維理想風味向量） | — | 3 | **5** | **11** | 感官杯測（多焙度） | 整個評分系統的終極目標錨點；建議以「已知好喝的食譜」反推各焙度的物質比例，迭代修正 |
| **11** | `EVAPORATION_RATE`（蒸發率） | #19 | 4 | 2 | **10** | 電子秤 | 沖煮前後秤量總重，差值扣出液重；蒸發 3–8g 使實際 TDS 比預測略高約 1% |
| **12** | `WATER_PRESETS` GH/KH 實測（Spritzer / Jeju） | #9 | 4 | 2 | **10** | 水族 GH/KH 試劑 | 300 元內即可完成；消除品牌公開資料的批次差異 |
| **13** | `WEIGHTS`（六維評分權重） | — | 3 | 4 | **10** | 感官盲測（多次） | 以相同配方、不同偏差方向設計盲測，反推 AC/SW/PS/CA/CGA/MEL 各維度的真實感官權重 |
| **14** | `SCORCH_PARAMS`（高溫劣變閾值與靈敏度） | — | 3 | 3 | **9** | 感官盲測 | 高溫 vs 適溫同一食譜盲測；閾值偏差會讓評分系統對高溫場景過罰或欠罰 |
| **15** | `HARSHNESS_SLOPE` + `ASHY_SLOPE`（協同劣變斜率） | — | 3 | 3 | **9** | 感官盲測 | 「AC×CGA 同時超標」vs「單一超標」的對照評分；深焙場景優先測 ASHY_SLOPE |
| **16** | `SW_AROMA_SLOPE`（高溫甜感逸散斜率） | — | 3 | 3 | **9** | 感官盲測 | 90/95/100°C 相同食譜盲測甜感評分差異；斜率偏高會系統壓制高溫組合 |
| **17** | `MEL_BITTER_COEFF`（深焙焦苦係數） | #6 | 3 | 3 | **9** | 感官盲測 | MD/D 高萃取 vs 正常萃取的焦苦感知對照；目前 MD=D=0.5，可能需區分 |
| **18** | `SWIRL_WAIT_SLOPE`（靜置時間研磨度斜率） | — | 4 | 1 | **9** | 目視觀察 | 對著不同研磨度粉渣計時沉降；成本幾乎為零，但對評分影響極微 |
| **19** | `K_FINES_MULT` + `K_BOULDERS_MULT` + `FINES_RATIO_DIAL_SLOPE`（雙峰核心倍率） | #3 擴充 | 2 | 4 | **8** | 篩粉器（100μm）+ 折射儀 | 篩出細粉單獨萃取，擬合各峰速率常數；真實倍率預期 5–15×（文獻給 10×） |
| **20** | `PRESS_EQUIV_FRACTION`（壓降萃取效率折算） | — | 3 | 2 | **8** | 折射儀 | 相同食譜不同壓降速度的 TDS 差值；影響量約 ±3% EY |
| **21** | `K_CA`（咖啡因萃取速率） | — | 3 | 2 | **8** | 折射儀 | 45s/90s/150s 多時間點 TDS，結合 CA 占比反推；影響層 2 濃度接近度 |
| **22** | `ASYM_BITTER_MULT` / `ASYM_SWEET_MULT`（非對稱懲罰倍率） | — | 3 | 2 | **8** | 感官盲測 | 相同絕對偏差量，苦澀方向 vs 甜感方向的主觀評分差異 |
| **23** | `W1` + `W2` + `TDS_W3`（三組感官懲罰權重） | — | 3 | 2 | **8** | 感官盲測 | 目前 W1=0.15/W2=0.12 為主觀設定；需系統盲測後迭代 |
| **24** | `KH_PERCEPT_DECAY`（KH 感知中和衰減常數） | — | 3 | 2 | **8** | 感官盲測 | 高 KH vs 低 KH 同一食譜的酸感差異盲測；影響 AC 感知層 |
| **25** | `BED_COMPACTION_COEFF` + `SWIRL_RESET_FRACTION`（粉床壓實與重置） | #16, #21 | 3 | 2 | **8** | 計時器（壓降秒數） | 不同浸泡時間（60/120/240s）的壓降秒數計時即可；無需儀器 |
| **26** | `DARCY_PRESS_EXP`（達西壓降指數） | — | 3 | 2 | **8** | 計時器 | 不同研磨度的實際壓降秒數分布，確認 0.6 指數是否合理 |
| **27** | `PS_TIME_MAX` + `K_PS`（多糖體飽和動力學） | — | 3 | 2 | **8** | 感官盲測（Body 評分） | 不同浸泡時間（60/120/180/240s）的 Body 感知差異；PS 貢獻慢，差異可能在 180s 後才顯著 |
| **28** | `FINES_RATIO` 焙度字典（細粉率焙度補償） | #20 | 2 | 3 | **7** | 篩粉器（多焙度） | 深焙豆質酥鬆，相同刻度細粉率可能高 30–50%；篩粉後秤重計算各焙度細粉率 |
| **29** | `CHANNELING` 係數群（EY_SLOPE / CGA_MULT / COLLAPSE_RATIO） | — | 2 | 3 | **7** | 計時器 + 感官觀測 | 30g + 極細粉場景觀測壓降秒數與出杯渾濁度；通道效應難以精確量化，先確認觸發頻率 |
| **30** | `CONC_GRADIENT_COEFF`（有限溶劑分配係數） | — | 3 | 1 | **7** | 折射儀 | 不同豆量固定其他參數的 EY 量測；修正量僅 ~0.6%，優先度極低 |
| **31** | `MG_FRAC_AC_SW_MULT` + `MG_FRAC_PS_CGA_MULT`（鈣鎂離子偏好） | #27 | 2 | 2 | **6** | MgCl₂ + CaCl₂ 化學試劑 + 感官盲測 | 純鎂水 vs 純鈣水對照實驗；修正幅度 8–16%，但需要配製化學試劑，門檻較高 |
| **32** | 六組焙度字典（`ac_roast` / `sw_roast` 等） + 六大物質獨立動力學 | #10 | **1** | **5** | **7** | GC-MS / HPLC（研究設備） | 系統的終極架構問題；影響最大但需要研究機構合作，在此條件具備前維持現有混合模型 |

---

### 16.3 建議執行分波

| 波次 | 門檻 | 含項目（排名） | 預計單次工時 |
|:---:|---|---|---|
| **Wave 1** | 零器材 / 純代碼 | #2（T_ENV）、#5（褐水底板） | < 1 小時 |
| **Wave 2** | 電子秤 + 計時器 | #1（截留率）、#4（注水流速）、#11（蒸發率）、#25（粉床壓實計時）、#26（達西計時）、#18（靜置觀察） | 1–2 小時 |
| **Wave 3** | 精密數位溫度計 | #6（熱平衡）、#7（冷卻速率）——可合併為同一實驗 | 1 小時 |
| **Wave 4** | 折射儀 | #8（Swirl 倍率）、#9（K_BASE+ARRHENIUS）、#3（TDS_PREFER）、#20（壓降效率）、#21（K_CA）、#30（溶劑梯度） | 3–5 小時（多組量測） |
| **Wave 5** | 感官盲測 | #10（IDEAL_FLAVOR）、#13（WEIGHTS）、#14–17（各懲罰斜率）、#22–24（懲罰權重）、#27（PS Body） | 多輪累積，每輪 1–2 小時 |
| **Wave 6** | 水族試劑 | #12（礦泉水 GH/KH） | < 30 分鐘 |
| **Wave 7** | 篩粉器（100μm） | #19（雙峰倍率）、#28（細粉率焙度字典） | 2–3 小時 |
| **Wave 8** | 化學試劑（MgCl₂/CaCl₂） | #31（鈣鎂偏好） | 2 小時 |
| **Wave 9** | GC-MS / HPLC（研究設備） | #32（焙度字典 + 獨立動力學）——長期目標 | 數週 |

> **執行建議：** Wave 1–3 可在第一個沖煮早晨完成，Wave 4 建議集中一個週末，Wave 5 的感官盲測則分散在日常沖煮中逐步迭代。Wave 7 的篩粉器（如 Kruve、OCD 篩杯）投入約 1,500–5,000 元，但能同時校正三個核心雙峰參數，CP 值極高。Wave 9 屬長期目標，在此之前混合模型（嚴謹巨觀 + 經驗微觀）是最佳可行近似。

---

> **v5.8r 企劃書定版聲明：** 本版本基於 v5.8，新增三項修正：①`t_slurry` 從線性近似升級為比熱混合方程式（正確反映 water_ml 影響）；②褐水防禦底板（`TDS_BROWN_WATER_FLOOR = 0.80`）；③`predict_compounds` 的溫度輸入從壺溫 `temp` 修正為漿體溫 `t_slurry`（與 `calc_ey` 使用 T_avg、`SCORCH_PARAMS` 使用 t_slurry 一致，消除內部溫度變數錯位）。§15 共 26 項 → **28 項**（Gemini 最終常數盤點補入）。**企劃書不再升版，進入程式碼實作。**

*企劃書 v5.8r（定版）｜基於 v5.8：①t_slurry 升級為比熱混合方程式；②褐水防禦底板 TDS < 0.80%；③predict_compounds 溫度輸入從壺溫改為漿體溫（XL 30g 100°C 場景 CGA 乘數從 1.240 修正至 1.111，消除 −10% 的系統性高估）。§15 新增 #25 T_ENV 參數化、#26 CGA 研磨度依賴、#27 MG_FRAC 實測方案、#28 TDS_BROWN_WATER_FLOOR 個人化校正；§14 補入四個漏網魔法數字條目（MG_FRAC 係數、K_FINES_MULT/K_BOULDERS_MULT 倍率、TDS_BROWN_WATER_FLOOR 感官底板、CONC_HUBER_DELTA 超參數）。*
*所有模型參數均可在實際沖煮後迭代更新。*
