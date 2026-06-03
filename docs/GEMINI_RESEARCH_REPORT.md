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
