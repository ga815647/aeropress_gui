# Gemini 研究報告 —— 沖煮物理 / 感官的文獻證據蒐集

本報告根據 `docs/GEMINI_RESEARCH_BRIEF.md` 的要求，針對六個主題進行了文獻與證據蒐集，並評估了現有模型的假設與常數設定。

## 主題 1 —— 溫度在「相同萃取率」下對感官的影響

**結論：** 在 TDS (Total Dissolved Solids) 與 EY (Extraction Yield) 被配對相同的情況下，沖煮水溫本身對最終杯中的風味與感官特徵**沒有顯著影響**。溫度主要作為影響萃取「速率」的工具，而非決定最終風味的獨立變數。
**證據強度：** 強（同行評審論文）。
**效應大小：** 感官差異極微。TDS 與 PE 是主導感官風味的絕對因素，溫度的獨立效應幾乎為零。
**條件與範圍：** 
- 滴濾式沖煮 (Drip brew)。
- 溫度區間：87°C, 90°C, 93°C。
**關鍵出處：** Batali, M. E., Ristenpart, W. D., & Guinard, J. X. (2020). *Brew temperature, at fixed brew strength and extraction, has little impact on the sensory profile of drip brew coffee*. Scientific Reports.

## 主題 2 —— 溫度對萃取率本身的量化效應

**結論：** 在全浸泡式沖煮中，最終達到的「平衡萃取率」(Equilibrium Yield, E_MAX) 及平衡常數 (K) **對水溫 (80–99°C) 極不敏感**。溫度的變化主要影響達到平衡的「速率常數」 (rate constant, k)，而非萃取率的上限。
**證據強度：** 強（同行評審論文）。
**效應大小：** 平衡萃取率上限多落在約 21%，不隨 80-99°C 改變；溫度每升高，萃取速率加快，但未改變最終天花板。
**條件與範圍：** 
- 全浸泡式沖煮 (Full immersion)。
- 溫度區間：80–99°C。
**關鍵出處：** Liang, J., Chan, K. C., & Ristenpart, W. D. (2021). *An equilibrium desorption model for the strength and extraction yield of full immersion brewed coffee*. Scientific Reports.

## 主題 3 —— Syphon（虹吸壺）上壺溫度 vs 成果

**結論：** 虹吸壺上壺在粉水接觸瞬間，溫度通常會下降 2–3°C。若底部熱源持續加熱，上壺溫度可在約 30 秒內回升並維持在 92–96°C 的高溫萃取區間。若不減弱熱源，溫度會持續上升導致過度萃取（焦苦、澀感）。
**證據強度：** 弱（找不到受控的同行評審感官實驗，主要為業界物理量測與經驗法則）。
**效應大小：** 粉水接觸初始降溫約 2–3°C。
**條件與範圍：** 虹吸壺。
**關鍵出處：** Barista Hustle (Siphon temperature profiling experiments).

## 主題 4 —— 研磨粗細對 body 與「集中 vs 立體層次」的感官影響

**結論：** 研磨粗細透過表面積直接控制萃取速率。較細的研磨（以及隨之增加的細粉 fines, <100µm）不僅加快整體萃取，更會顯著增加口感厚實度 (body / mouthfeel) 與黏稠感；但若細粉過多或浸泡時間過長，容易導致風味過度集中而產生雜味與苦澀，遮蔽層次感。
**證據強度：** 中（大量業界量測、粒子徑分佈 (PSD) 研究，但缺乏專門針對 body 獨立變數的大型 SCA 盲測）。
**效應大小：** 較細研磨顯著提升 body (Thick.viscous) 與 astringency，符合目前的先驗假設。
**條件與範圍：** 所有沖煮法皆適用，但在有濾紙與壓力的 AeroPress 中，細粉對流阻的影響尤為明顯。
**關鍵出處：** 廣泛業界粒子徑研究 (如 Coffee Ad Astra, Barista Hustle)。

## 主題 5 —— 不同焙度的「公認最佳 / 好喝範圍」

**結論：** SCA Golden Cup Standard 官方僅建議 93±3°C，並未硬性規定各焙度。但業界強烈共識與最佳實踐為：淺焙適用較高溫 (94–96°C) 與較細研磨以榨出不易萃取的酸甜與花果香；深焙適用較低溫 (88–92°C) 與較粗研磨以避免焦苦味過度釋放。
**證據強度：** 中（SCA 基準 + 業界廣泛共識與烘豆商指南）。
**效應大小：** 溫度調整範圍跨度約在 88°C 到 96°C 之間，隨焙度線性調整。
**條件與範圍：** 適用所有沖煮方式。
**關鍵出處：** SCA Golden Cup Standard, 業界指南 (Roasters' recommendations).

## 主題 6 —— AeroPress 壓力/下壓 + 浸泡 vs 滴濾動力學可移植性

**(a) AeroPress 壓力影響：**
AeroPress 的手動下壓壓力約為 0.35–1 bar，遠低於義式濃縮 (9 bar)。其壓力主要作用是克服細粉帶來的流阻，加速過濾過程並可能帶入些微微粉以增加 body，但**不直接顯著改變萃取率 (EY)**。萃取率仍由浸泡時間與水溫主導。
**(b) 滴濾 vs 浸泡動力學可移植性：**
滴濾 (Percolation) 依靠不斷注入清水，維持高濃度梯度 (Noyes-Whitney equation)，萃取速率較快且能帶出高清晰度；浸泡 (Immersion) 則是濃度梯度隨時間遞減，逐漸趨近平衡 (Equilibrium)，口感較圓潤。
**結論：** 主題 1 (Batali 2020) 雖是滴濾研究，但探討的是「最終杯中物 (TDS/EY) 相同時」的感官，此「目標結果論」完全可套用於浸泡。主題 2 (Liang 2021) 則是直接針對浸泡式建立的平衡模型，完美契合目前 Layer 1 的架構。
**證據強度：** 強（流體動力學與萃取物理）。
**關鍵出處：** Coffee Ad Astra (Extraction kinetics), Liang et al. (2021).

---

## 總表

| 主題 | 核心結論 | 證據強度 | 最關鍵出處 |
|---|---|---|---|
| 1. 溫度對感官的影響 | 在 TDS/EY 相同下，溫度無獨立感官效應。 | 強 | Batali et al. 2020 (Sci Rep) |
| 2. 溫度對萃取率的效應 | 溫度影響萃取速率 (k)，但不影響最終平衡萃取率上限 (E_MAX)。 | 強 | Liang et al. 2021 (Sci Rep) |
| 3. Syphon 上壺溫度 | 接觸降溫 2-3°C，熱源決定穩定度，易因失控導致過萃。 | 弱 | Barista Hustle 實驗 |
| 4. 研磨粗細對 body | 細研磨與細粉顯著增加萃取速率與口感厚實度 (body)。 | 中 | 業界 PSD 與萃取探討 |
| 5. 各焙度最佳範圍 | 業界共識：淺焙高溫 (94-96°C)、深焙低溫 (88-92°C)。 | 中 | SCA 標準 / 業界共識 |
| 6. AeroPress 壓力與動力學 | 低壓力不主導 EY；浸泡趨向平衡，滴濾維持梯度，但同 TDS/EY 下感官結論可互通。 | 強 | Liang 2021 / Coffee Ad Astra |

---

## 對模型的具體建議

根據上述文獻，對目前 `models/` 參數的建議如下：

1. **`b_temp` (models/sensory.py)**
   - **建議：維持固定為 0。**
   - **證據強度：強。** Batali et al. (2020) 的受控盲測證實，在 TDS/EY 被配平的情況下，沖煮溫度本身不帶有獨立的感官效應。即使那是滴濾研究，但「只要杯中物濃度相同，味道就相同」的邏輯在浸泡式同樣成立。
2. **`ALPHA` 與 Layer 1 架構 (models/layer1.py)**
   - **建議：維持現有架構與數值。**
   - **證據強度：強。** Liang et al. (2021) 的浸泡式平衡模型直接支持了目前 Layer 1 的寫法：溫度不影響 `E_MAX`（天花板），只影響 `tau`（到達天花板的速率）。目前的 Arrhenius 近似 (`ALPHA = 0.026`) 是合理的物理先驗。
3. **`GAMMA` (models/layer1.py) 與 Layer 2 Body 係數**
   - **建議：維持現狀（GAMMA = 0.5）。**
   - **證據強度：中。** 較細研磨（與更多細粉）能顯著加快萃取並提升 body，系統已根據使用者回饋將 `GAMMA` 提升至 0.5，且在 `models/sensory.py` 中帶有 `_GRIND_SLOPE` 給予 body 補償，這與物理和感官現實在方向上完全一致。
4. **各焙度的溫度與搜尋範疇 (optimizer.py)**
   - **建議：維持溫度作為輸入常數，不在迴圈中搜尋。**
   - **證據強度：強。** 在浸泡式萃取中，溫度與時間會互相吸收效應（都是用來改變 `tau` 以達到目標萃取率）。維持預設值按照業界慣例（淺焙高溫、深焙低溫）設定，並讓迴圈搜尋 `dial` 和 `steep` 是完全符合萃取物理動力學的最佳做法。

---

# Round 2 —— 量化深度版（2026-06-03）

> 第一輪以「背書架構」為主、缺可校準數字。第二輪依 brief 的升級指令重跑：進原始論文挖數值、主動找反證、區分實測 vs 先驗。
> **重建說明：** 本節由 Antigravity 研究 session 的 transcript 重建——Gemini 完成研究但 quota 用盡、未能自動覆寫本檔；數值與引用取自其 `transcript.jsonl` + `implementation_plan.md`。

## 引用論文（PMCID）

| PMCID | 論文 | 角色 |
|---|---|---|
| **PMC7994670** | Liang, Chan, Ristenpart **2021**, *An equilibrium desorption model for the strength and extraction yield of full immersion brewed coffee* (Sci Rep) | Layer 1 物理主力 |
| **PMC9407127** | Batali et al. **2022**, *Sensory Analysis of Full Immersion Coffee: Cold Brew Is More Floral, and Less Bitter, Sour, and Rubbery Than Hot Brew* (Foods 11, 2440; doi:10.3390/foods11162440) | **新增**：浸泡式溫度感官 |
| **PMC7536440** | Batali et al. **2020**, *Brew temperature, at fixed brew strength and extraction, has little impact on the sensory profile of drip brew coffee* (Sci Rep) | `b_temp=0` 原始依據 |

## 主題 1（升級）—— 溫度的感官效應：邊界更清楚，但 `b_temp=0` 站得住

對抗式查證找到了第一輪缺的**浸泡式反例**：

- **Batali 2020（PMC7536440，drip，n=12，87/90/93°C，同時配平 TDS 與 PE/EY）** → 溫度無顯著獨立感官效應。
- **Batali 2022（PMC9407127，full immersion，n=10，4/22/92°C）** → 三焙度各自煮到平衡、**稀釋到相同 2% TDS**、統一在 4°C 出杯後杯測 → 溫度**確實**顯著改變四個屬性：**floral、rubber、bitter、sour**（PCA 沿溫度分離，且隨焙度/產地不同）。

**判讀（為何不推翻 `b_temp=0`）：** Batali 2022 (a) 跨 **4↔92°C 冷熱全幅**、(b) **只配平 TDS、沒配平 EY/PE**。我們的系統運作在 **85–99°C** 且 **TDS 與 EY 同為中樞潛變數**——它找到的溫度效應大半是「冷熱萃取出不同 EY/揮發物比例」，落在我們操作區外、且部分已由 EY 這條路徑承載。
**結論：`b_temp=0` 是有效的「熱窗局部先驗」。** 證據強度：強（熱窗內）；跨冷熱有界外反例。

## 主題 2（升級）—— `ALPHA` 取得物理錨點

模型 `τ = TAU_REF·exp(−ALPHA·(T−T_ref))` ⇒ `d(ln τ)/dT = −ALPHA`。Arrhenius 擴散 `τ ∝ exp(Ea/RT)` ⇒ `ALPHA = Ea/(R·T²)`。在 `T_ref = 98°C (371 K)`：

| Ea (kJ/mol) | 推得 ALPHA (/°C) | 來源 |
|---|---|---|
| 30 | **0.0262** ← 目前值 | 擴散主導下限 |
| 36 | 0.0314 | 咖啡因萃取實測 ~36 |
| 40 | 0.0349 | 較高 Ea 情境 |

**`ALPHA=0.026` ⇔ Ea=30 kJ/mol，恰好對上、但落在文獻區間（30–40）低端。** 若採咖啡因實測 ~36，`ALPHA` 應 ~0.031（對溫度更敏感）。從「合理先驗」升級為「半實測，偏保守端」。證據強度：中–強。

## 主題 4（升級）—— `GAMMA`：γ 隨粗細變，「0.41」是在錯的粗細上比較

球擴散 `τ ∝ d²` ⇒ 局部 `γ_geom = 2·(Δ/d)`（Δ=每格粒徑位移，d=絕對粒徑）。**因為 d 隨刻度變，γ 不是定值。** Liang 2021 用 **Mahlkönig Guatemala Lab Grinder**（刻度 2–6，Sympatec 雷射實測 D50 580→1310µm），每格的幾何 γ：

| Liang step | D50 | γ_geom |
|---|---|---|
| 6→5 | 1310→1160 | 0.24 |
| 5→4 | 1160→970 | 0.36 |
| 4→3 | 970→780 | **0.44** ← Gemini round-2 取的「0.41」在此（粗端） |
| 3→2 | 780→580 | **0.59** |

- **「0.5 高於 0.41」是假象。** 0.41 是在 ~970µm（偏粗）算的；**使用者實際泡 filter 粗細 ~700µm**（ZP6 dial 4.3）對應 Liang setting 2–3 之間，即 γ 最高端。在 ~700µm、每格 ~185µm 位移下 **γ_geom ≈ 0.53**（650–750µm → 0.49–0.57）。**GAMMA=0.5 正中，不偏高，不需要 fines 解釋。**
- **磨豆機可比性：** ZP6 官方 22µm/click × 10 = **220µm/number** burr gap；壓縮成 D50 後 ~150–200µm/number，與 Liang Mahlkönig 的 ~185µm/setting 同量級 → 同粗細下兩台 γ 相近。（ZP6 無舊版；8.8µm 為單一 blog 誤植，確定 22µm/click。）
- **關鍵佐證：** Liang 2021 在 **579–1311µm** 內平衡 TDS=1.36±0.09%、E=19–23% 幾乎不變 → 研磨只改速率、不改 `E_MAX` 上限，與我們把 GAMMA 放在 `τ` 一致。
- **連續化（dial-dependent GAMMA）已評估、暫緩：** 量級小（粗端 ~0、細+短端幾 % EY，在 Layer 1 容差內），且需 ZP6 實測「刻度→µm」曲線（目前缺，被 paywall 擋），硬用猜的 map 可能比 feedback-fit 的常數還差；GAMMA 由使用者杯子錨定才是設計本意。**重啟條件 =** dial-3/dial-5 出現系統性 flag，或拿到 ZP6 實測 µm。若真要做，乾淨形式為 `τ_grind = (1 + 0.25·(dial−4.3))²`（β=0.25 在錨點等於 GAMMA=0.5）。

證據強度：**強**（用 Liang 雷射實測重算）；唯一軟點為 ZP6 絕對 µm 仍靠 filter 慣例值，但結論在 600–900µm 全段穩健。

## 主題 5（升級）—— 各焙度溫度：業界慣例，且產率論點被部分推翻

業界/SCA 建議（**非同行評審，rule of thumb**）：

| 焙度 | 建議水溫 | 理由（業界） |
|---|---|---|
| Light | 94–96°C | 豆密、較不可溶，需高溫 |
| Medium | 92–94°C | SCA 標準窗、較寬容 |
| Dark | 88–92°C | 多孔、易萃，需低溫避焦苦 |

**反證：** Liang 2021 發現 **平衡 TDS 幾乎與焙度無關**（light 到 extra dark 難分辨；只有 decaf 系統性偏低）。⇒「淺焙要高溫」是**速率**論點（淺焙萃得慢、用溫度補速率），**不是產率**論點。我們 `DEFAULT_TEMP["light"]=98°C` 偏業界上緣之上，但因 `b_temp=0`，這純是速率選擇、非風味選擇。`_GRIND_SLOPE` 與 per-roast `DEFAULT_TEMP` **未被同行評審錨定，維持先驗**。

## 主題 6（升級）—— 可移植性

- AeroPress 下壓 ~0.35–1 bar：主要克服流阻、可能帶入微粉增 body，**不主導 EY**；EY 由浸泡時間 × 溫度（經 τ）決定。
- Batali 2020 雖 drip，但「同 TDS/EY ⇒ 同感官」是結果論，可移植浸泡；Liang 2021 直接是浸泡平衡模型，與 Layer 1 同構。**第二輪新增的 Batali 2022 直接就是浸泡式**，補上了上輪缺的 immersion 感官資料。

---

## 參數校準表（主產物）

| 參數 | 目前值 | 文獻錨定值/範圍 | 落點 | 實測 / 先驗 | 出處 |
|---|---|---|---|---|---|
| `b_temp` | 0 | 熱窗 85–99°C：0；跨 4–92°C 僅配平 TDS：非 0 | 熱窗內成立 | 實測（熱窗）；界外有反例 | Batali 2020 / 2022 |
| `ALPHA` | **0.031** /°C（原 0.026，已套用 2026-06-03） | 0.026–0.035（Ea 30–40 kJ/mol） | 對應 Ea~36 | 半實測（物理錨） | Arrhenius；caffeine Ea~36 |
| `GAMMA` | 0.5 | γ 隨粗細變（Liang 實測 0.24–0.59）；使用者 ~700µm 處 ≈0.53 | **正中** | 實測幾何 + feedback 雙錨 | Liang 2021 Mahlkönig |
| `_GRIND_SLOPE` | TV +0.010 / Astr +0.008 | 方向確認，無斜率數字 | — | 先驗（未錨定） | 業界 PSD |
| `DEFAULT_TEMP`/焙度 | light98/ml95/m92/md89 | light94–96 / med92–94 / dark88–92 | light 偏上緣外 | 先驗（業界慣例） | SCA + Liang |

## 對模型的具體建議（Round 2）

1. **`b_temp`：維持 0。** 熱窗內有實測支持；界外反例不適用本系統運作區。建議在 `models/sensory.py` 註解補一句「`b_temp=0` 為 85–99°C 熱窗局部先驗；Batali 2022 顯示跨冷熱（僅配平 TDS）時非 0」。
2. **`ALPHA`：0.026 → 0.031（Ea 30→36）—— 已於 2026-06-03 套用**（見 `refine_changelog`；commit 569c87b）。13/13 diagnose + 89 pytest pass，錨點 exp(0)@98°C 不變。
3. **`GAMMA`：維持 0.5，不做連續化。** γ 隨粗細變，但在使用者 filter 粗細（~700µm）幾何值就 ≈0.53，feedback 的 0.5 與之吻合（雙路印證，非「高於地板」——那是粗細錯配的假象）。dial-dependent 連續化已評估暫緩（量級小 + 缺 ZP6 實測 µm，見主題 4）。
4. **`_GRIND_SLOPE` / per-roast `DEFAULT_TEMP`：維持先驗。** 無同行評審數據可錨定。
5. **模型本身不在本報告動任何一行**——以上 2 為唯一候選微調，交使用者決定。
