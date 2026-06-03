# Gemini 研究委託書 —— 沖煮物理 / 感官的文獻證據蒐集

> **給讀這份檔案的 AI agent（Gemini via Antigravity）：**
> 你有這個 repo 的讀取權限。請**先讀以下檔案**建立對模型的理解，再回答本文件下半部的研究題。
> 你的任務**不是改 code**，而是用網路搜尋蒐集「有原始數據 / 受控實驗支持」的證據，產出一份帶引用的研究報告。

## 先讀這些（建立背景，約 10 分鐘）

| 檔案 | 為什麼要讀 |
|------|-----------|
| [`CLAUDE.md`](../CLAUDE.md) | 全系統設計原則、兩層模型的紅線、目前狀態 |
| [`ARCHITECTURE.md`](../ARCHITECTURE.md) | 資料流、兩層模型、迴圈引擎、調整方向表 |
| [`models/layer1.py`](../models/layer1.py) | **Layer 1 物理**：knobs→TDS/EY，純 `exp()` 平衡脫附式。本研究的溫度/研磨係數就住在這 |
| [`models/sensory.py`](../models/sensory.py) | **Layer 2 感官**：TDS/EY→10 個 cotter CATA 感官屬性，OLS 回歸係數。`b_temp` 在此 |
| [`data/ideal.json`](../data/ideal.json) | 各焙度的感官目標（移動靶 = 使用者杯子），含 anchor_brew 出處 |

---

## 這套系統是什麼（一句話）

個人化 AeroPress / 浸泡式沖煮參數最佳化器。**核心建模假設**：

> 沖煮濃度 **TDS** 與萃取率 **EY** 是中樞潛變數，風味完全由它們決定。
> 水溫、浸泡時間、研磨粗細是「過程變數」，**只透過 TDS/EY** 影響風味，不直接進感官預測。

本研究就是要拿文獻證據來**檢驗、校準**這個假設與其中的數值常數。

## 你的答案會接到模型的哪裡（請針對這些給「可校準的數字」）

| 研究主題 | 對應模型參數 / 決策 | 目前的值 / 假設 |
|---------|-------------------|----------------|
| 1. 溫度在「相同萃取率」下的感官效應 | `models/sensory.py` 的 `b_temp` | 目前固定 **0**（85–99°C 內溫度無獨立感官效應） |
| 2. 溫度對萃取率本身的量化效應 | `models/layer1.py` τ 的溫度項 `ALPHA`（`τ = TAU_REF·exp(−ALPHA·(temp−T_REF))`） | **ALPHA ≈ 0.026**；對照 cotter 約 +0.014% TDS/°C |
| 4. 研磨粗細對 body / 層次的感官效應 | `models/layer1.py` 的 `GAMMA`（grind→rate）+ Layer 2 body 係數 | **GAMMA = 0.5**（從使用者回饋 0.32→0.5 校準過） |
| 5. 各焙度公認最佳範圍 | 是否把溫度/時間/粗細**錨定、移出搜尋範疇**的決策依據 | 目前皆在搜尋空間內（迴圈調） |
| 3. Syphon 上壺溫度 vs 成果 | （旁支好奇，無直接接線，純資料蒐集） | — |
| 6. 壓力 + 浸泡 vs 滴濾可移植性 | `models/layer1.py` 的 `T_PRESS_OFFSET`（下壓≈+10s）+ 判斷 drip 研究能否套用到 immersion | press offset = 10s |

> **特別注意**：主題 1、2、4 引用的研究若是 **drip / pour-over**，請務必在主題 6 評估其結論能否套到 **full-immersion（AeroPress / French press）**——這是這套模型最關鍵的可移植性問題。

---

## 引用與品質要求

- 優先：同行評審論文（Scientific Reports、Journal of Food Science、Food Research International、J. Agric. Food Chem. 等）、SCA / Specialty Coffee Association 官方資料、方法清楚的受控實驗。
- 部落格 / 論壇 / YouTube 結論：可列，但**標明可信度較低**。
- 每個結論附：**出處、樣本與方法、效應大小（具體數字）、成立的條件範圍（焙度 / 溫度區間 / 沖煮法）**。
- 找不到證據時，請**明確寫「找不到受控實驗」**，不要用常識補洞。

---

## 研究題

### 主題 1 —— 溫度在「相同萃取率」下對感官的影響
在 TDS/EY 被刻意配對相同（matched-extraction）下，只改沖煮水溫，杯中風味是否還有可被感官辨識的差異？請找 sensory descriptive analysis 或 consumer panel 的受控研究。
已知線索（請確認其具體數據、找反例或更新研究）：
- **Batali et al. 2020 (Scientific Reports, drip, matched TDS/PE)** —— 確認感官顯著項與效應大小。
- **Liang, Cameron, Ristenpart 2021** —— 萃取速率常數 K 在 80–99°C 近似不變，確認數值。
- 特別想要 **immersion / AeroPress / French press** 的資料。
- **搜尋關鍵字**：`coffee brewing temperature sensory matched extraction`；`Batali Guinard coffee temperature 2020`；`coffee extraction kinetics rate constant temperature Ristenpart`；`immersion coffee temperature flavor controlled study`

### 主題 2 —— 溫度對萃取率本身的量化效應
每升高 1°C，TDS(%) 或 EY(%) 大約變化多少？請給 **immersion / full-immersion** 條件的數字與出處（只有 drip/pour-over 資料也列出並註明）。
- **搜尋關鍵字**：`brew temperature effect on extraction yield percent`；`coffee TDS vs water temperature immersion`；`full immersion coffee temperature extraction yield study`

### 主題 3 —— Syphon（虹吸壺）上壺溫度 vs 成果
有沒有人做過「虹吸壺上壺水溫（或熱源強度造成的溫度差）對最終風味 / 萃取率」的受控對照實驗或量測？包含：上壺實際水溫通常幾度、攪拌與停留時間、不同溫度的杯測結果。盡量找具體實驗；沒有就明確說「找不到」，並列最接近的相關討論。
- **搜尋關鍵字**：`siphon coffee brewing temperature experiment`；`vacuum pot coffee upper chamber temperature`；`syphon coffee extraction yield study`；`虹吸 サイフォン 抽出 温度 実験`

### 主題 4 —— 研磨粗細對 body 與「集中 vs 立體層次」的感官影響
浸泡式沖煮中，較細 vs 較粗研磨（萃取率配平或不配平）對「醇厚度 body / 口感集中度 / 風味層次複雜度」有無受控研究？是否有「過細導致風味集中、層次變弱」的證據，還是只是萃取率差異的表現？請**務必區分**：(a) 平均粒徑 (mean particle size)、(b) 細粉比例 (fines / particle size distribution) 兩種效應。
- **搜尋關鍵字**：`coffee grind size sensory body extraction`；`particle size distribution coffee flavor fines`；`grind size descriptive sensory analysis coffee`；`coffee grind fineness mouthfeel study`

### 主題 5 —— 不同焙度的「公認最佳 / 好喝範圍」
淺焙 / 中淺焙 / 中焙 / 中深焙，是否有被廣泛接受或有實驗支持的建議範圍——水溫、浸泡時間、研磨粗細、粉水比？「淺焙建議較高水溫 / 較細研磨 / 較長時間」這類說法有無量化或受控依據，還是業界經驗法則？請分開標示可信度：**SCA Gold Cup standard / World Brewers Cup 冠軍配方 / 知名烘豆商建議 / 同行評審研究**。
- **搜尋關鍵字**：`roast level brewing temperature recommendation light dark`；`SCA gold cup extraction roast`；`light roast higher temperature finer grind evidence`；`roast degree optimal brew parameters study`

### 主題 6 —— AeroPress 壓力/下壓 + 浸泡 vs 滴濾動力學可移植性
(a) AeroPress 的下壓（plunge / 低壓 ~1 bar）對萃取率或風味有沒有可量測影響？壓力 / 流速在 AeroPress 中是否顯著，還是浸泡時間主導？
(b) 主題 1/2/4 若引用 drip / pour-over 研究，其萃取動力學結論能否套用到 full-immersion（AeroPress / French press）？兩種沖煮法萃取曲線差異多大？
- **搜尋關鍵字**：`AeroPress extraction pressure plunge effect`；`immersion vs drip coffee extraction kinetics comparison`；`AeroPress brewing variables study`；`full immersion vs percolation extraction yield`

---

## 產出格式

1. 每個主題一節，含上述「結論 / 證據 / 效應大小 / 條件」四要素。
2. 最後一個**總表**：每主題一行，欄位 = `主題 | 核心結論 | 證據強度（強·中·弱·無）| 最關鍵出處`。
3. 若有任何結論**直接建議調整上表中的模型參數**（`b_temp` / `ALPHA` / `GAMMA` / 是否錨定某焙度範圍），請在報告末尾獨立列一節「對模型的具體建議」，每條附證據強度——但**不要直接改 code**，交回給使用者與 Claude 決定。

---

# 第二輪 —— 深度研究升級指令

> 第一輪報告（`docs/GEMINI_RESEARCH_REPORT.md`）以「背書現有架構」為主，但多為定性確認、缺少可校準的原始數字。本輪把標準提高：**每條結論都要無法用「維持現狀」打發**——逼進原始論文挖數字、主動找反證。

請開啟 Deep Research / 瀏覽模式，允許實際下載並讀取論文 PDF，可多步、多輪。對上面六個主題，這次標準為：

1. **【原始數據，不要摘要】** 每條結論必須附：具體數值、樣本數 n、信賴區間或誤差、R²（若是回歸）、以及出處的圖/表編號或頁碼。禁止只引用 abstract 的定性描述。
   - 主題 2：從 Liang/Ristenpart 2021 報出每個溫度的速率常數 k、活化能 Ea、E_MAX 平衡值、τ，以及它們的溫度相依關係式（用來校準 `ALPHA`）。
   - 主題 4：找「平均粒徑(µm)↔萃取速率」與「細粉比例↔body/口感強度（可量尺度）」的數字，給能擬合斜率的資料點（校準 `GAMMA` 與 `_GRIND_SLOPE`）。

2. **【對抗式查證】** 每條結論都要主動反向搜尋反例，而非只找支持證據：
   - 主題 1：有沒有「配平 TDS/EY 下仍測到溫度感官效應」的研究？特別是 >93°C、或浸泡式（immersion）的？Batali 2020 只測到 87–93°C 的滴濾，需確認 94–99°C 與浸泡式是直接證據還是純外推。
   - 找不到反例時，明確寫「主動搜尋後未發現反例」，而非預設沒有。

3. **【先驗 vs 測量】** 明確區分每個數字是「實測/回歸得到」還是「業界經驗法則」。主題 4、5 上一輪多靠 Barista Hustle / Coffee Ad Astra / 烘豆商指南——本輪請找這些說法背後是否有同行評審原始研究，沒有就標為「未錨定」。
   - 主題 5：淺焙要高溫，是因為**豆子密度/可溶性物質溶解度確實隨焙度改變**（真實萃取事實），還是純慣例？找 roast degree ↔ solubility / extractability 的量化研究。

4. **【可移植性要有數字】** 主題 6：給滴濾 vs 浸泡的萃取曲線**實際差異量**（到達同一 EY 的時間差、同 EY 下感官差的效應大小），不要只給定性描述。

5. **【自我批判再一輪】** 寫完後列出：(a) 完全找不到原始數據的主題、(b) 整份報告最弱的一條結論。然後針對這兩項再做一次搜尋，把結果補進去。

**【產出】** 除原本格式外，新增一張「參數校準表」：

| 參數 | 目前值 | 文獻建議值/範圍 | 信賴區間 | 證據是實測還是先驗 | 出處 |
|------|--------|----------------|---------|------------------|------|

針對 `b_temp` / `ALPHA`（或 Ea）/ `GAMMA` / `_GRIND_SLOPE` / 各焙度 `DEFAULT_TEMP` 各一行。有實測數字才填，沒有就寫「未錨定—維持先驗」。
