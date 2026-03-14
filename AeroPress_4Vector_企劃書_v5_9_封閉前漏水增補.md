# AeroPress 演算法白皮書 v5.9 相關章節增補

## 0. 本次決策

本版決定將「封閉前漏水（Pre-Seal Drip）」直接整合進現行模型，而不是延後到 §15。

理由有三點：

1. 它對現有模型的主效應是「自由溶劑減少」與「低 TDS、偏酸支流混合」，這兩件事都可以在不拆毀封閉段解析解的前提下納入。
2. `seal_delay` 只改變封閉前的漏水窗口，不改變封閉段牛頓冷卻 + 雙粒徑動力學的數學形式。
3. 目前 `Pre-Seal Drip` 的量級相對總水量仍屬小擾動，採一階混合近似的風險低於全面重寫流體模型的風險。

因此 v5.9 採用「保留封閉解析解主體 + 外掛 Pre-Seal 支流修正」。

---

## 3. 新物理架構：封閉前漏水

### 3.1 時間窗

定義：

- `pour_time = water_ml / POUR_RATE`
- `seal_delay`：注水完成到塞入活塞建立負壓的額外延遲，預設 `5 s`
- `t_drip = pour_time + seal_delay`

這裡 `t_drip` 不是封閉段時間，而是「存在漏水可能」的總時間窗。

### 3.2 漏水體積

建立：

```text
V_drip = min(k_drip * t_drip * (dial / DIAL_BASE)^eta, water_ml * r_max)
```

其中：

- `k_drip = PRE_SEAL_DRIP_RATE_REF`
- `eta = PRE_SEAL_DRIP_DIAL_EXP`
- `r_max = PRE_SEAL_DRIP_MAX_RATIO`

物理解讀（達西定律）：

- 與總漏水時間成正比：時間越長，漏水越多。
- 與研磨度成正比：粒徑越大（粗研磨、dial 越大）粉床阻力越低，相同靜水壓下流速越高，漏水量越多；`dial = DIAL_BASE` 時修正項為 1。
- 加上上限 `r_max`，避免在極細研磨或極長延遲下出現不合理的漏水量。

### 3.3 封閉段自由溶劑修正

原模型的自由溶劑為：

```text
free_water_base = water_ml - dose * retention
```

v5.9 改為：

```text
free_water_main = water_ml - V_drip - dose * retention
```

這代表封閉段真正可用來承載濃度梯度的液相減少。

### 3.4 封閉段主流萃取

封閉段沿用雙粒徑解析式，以 `free_water_main` 輸入：

```text
EY_main = EY_closed_form(free_water_main, t_kinetic)
```

批次平衡 `brew_capacity = free_water_main / (free_water_main + dose×K_d)` 已完整建模 V_drip 造成的溶劑減少；不再額外乘 `(1 - λ×V_drip/water_ml)`，否則構成雙重計算。

### 3.5 漏水支流的低 TDS 滴濾效應

封閉前漏水不是零萃取，而是短接觸時間的弱滴濾支流。

v5.9 用一個低效率支流近似：

```text
t_psd = PRE_SEAL_CONTACT_FRACTION * t_drip
EY_drip_raw = EY_closed_form(V_drip, t_psd)
EY_drip = epsilon_psd * EY_drip_raw
```

其中：

- `PRE_SEAL_CONTACT_FRACTION`：把「漏水窗口」折算成「有效床層停留時間」
- `epsilon_psd = PRE_SEAL_PERCOLATION_EFFICIENCY`：代表此支流為低 TDS、低質量回收效率

因此總萃取率為：

```text
EY_total = GH_adjust(EY_main + EY_drip)
```

這裡保留了使用者要求的三個核心現象：

1. 主壺自由溶劑減少。
2. 漏下去的水確實經歷短暫 percolation，而不是純水旁通。
3. `seal_delay` 直接增加 `t_drip`，因此增加 `V_drip`，並對總 EY 形成保守化修正。

---

## 5. `predict_compounds` 的支流混合

### 5.1 為什麼不用重寫整個風味動力學

現行 `predict_compounds` 是以「主流液相的相對物質向量」為核心，而不是逐滴做質量傳輸方程。

Pre-Seal Drip 對風味的主效應不是整體化學機制翻盤，而是：

- 比主流更偏 AC
- 更低甜感與厚度
- 苦澀生成較少，但會在最終杯中把酸質往前推

因此 v5.9 採用雙流混合：

```text
C_main = compounds_main(effective_steep)
C_drip = compounds_preseal(PRE_SEAL_CONTACT_FRACTION * t_drip)
```

再對 `C_drip` 套偏置：

```text
AC  *= PRE_SEAL_AC_MULT
SW  *= PRE_SEAL_SW_MULT
PS  *= PRE_SEAL_PS_MULT
CA  *= PRE_SEAL_CA_MULT
CGA *= PRE_SEAL_CGA_MULT
MEL *= PRE_SEAL_MEL_MULT
```

最後用體積比分流混合：

```text
phi = V_drip / water_ml
C_total = (1 - phi) * C_main + phi * C_drip
```

這代表：

- 主壺壓降咖啡仍是主體。
- 漏下壺的支流會把整杯往「早段酸質」方向拉。
- 因為 `phi` 小，所以不會摧毀現有風味空間。

---

## 8. 程式接口更新

### 8.1 新增變數

```python
SEAL_DELAY_DEFAULT = 5.0
```

### 8.2 新增函數

```python
calc_drip_volume(water_ml, dial, drip_time) -> float
```

### 8.3 更新函數簽名

```python
calc_ey(..., press_equiv=0, pour_offset=0, seal_delay=SEAL_DELAY_DEFAULT)
predict_compounds(..., press_equiv=0, pour_offset=0, water_ml=400, seal_delay=SEAL_DELAY_DEFAULT)
```

### 8.4 optimizer 新增輸出欄位

- `seal_delay`
- `pre_seal_drip_sec`
- `pre_seal_drip_ml`

---

## 14. 本版近似的邊界

v5.9 已可直接上線，但仍需明確承認以下近似：

1. `calc_drip_volume` 採 `(dial/DIAL_BASE)^eta` 與達西定律方向一致；仍是靜態經驗式，尚未顯式建模濾紙阻力、粉層高度、翻轉角度。
2. 主流程式僅以 `free_water_main` 輸入 `EY_closed_form`，不再乘 `(1 - λ×V_drip/water_ml)`，因 brew_capacity 路徑已完整建模溶劑減少，額外乘項構成雙重計算。
3. `EY_drip` 以低效率因子 `epsilon_psd` 吸收了真實的床層停留時間分布，尚非完整流體模型。
4. `predict_compounds` 的 Pre-Seal 支流偏置目前是物理方向正確的一階混合，仍需以折射儀 + 杯測反推最佳乘數。

這些限制不影響本版整合決策，因為它們屬參數精修，不屬方程結構錯誤。

---

## 15. 後續實測計畫（v5.9 延伸）

雖然本版已直接整合，但仍建議把下列量測列入 §15：

1. 固定 `water_ml / dose / roast`，只改 `seal_delay = 0 / 5 / 10 / 20 s`，量測實際漏水質量，回歸 `PRE_SEAL_DRIP_RATE_REF` 與 `PRE_SEAL_DRIP_DIAL_EXP`。
2. 收集漏下壺的 pre-seal 支流，單獨量測 TDS，校正 `PRE_SEAL_PERCOLATION_EFFICIENCY`。
3. 主流與 pre-seal 支流分杯杯測，檢查 AC/SW 是否真的上升，以及 `PRE_SEAL_AC_MULT` 等偏置是否方向正確。
4. 比較不同濾材與不同翻轉角度，確認 `PRE_SEAL_DRIP_MAX_RATIO` 是否需要按濾材分表。

結論：Pre-Seal Drip 在 v5.9 已是可執行的一階修正模組；後續實測的目標是校正係數，不是決定是否存在這個模組。

---

## 16. 初期漏水計算之再評估（低估／高估）

### 16.1 現行公式與典型數值

- **體積**：`V_drip = min(PRE_SEAL_DRIP_RATE_REF * t_drip * (dial/DIAL_BASE)^η, water_ml * 0.12)`
- **常數**：`PRE_SEAL_DRIP_RATE_REF = 0.30`（ml/s）、`η = 1`、上限 12%。
- **典型（修正前）**：dial=4.5 時 `V_drip≈11.4 ml`（約 2.85%）；dial=6 時約 15 ml。
- **修正後（§16 貼近現實）**：`PRE_SEAL_DRIP_RATE_REF=0.38`、`η=1.2`、上限 18%。dial=4.5 時 `V_drip≈0.38×38×1≈14.4 ml`（約 3.6%）；dial=6 時約 18 ml（約 4.5%）；長 seal_delay 時最多 18% 總水量。

### 16.2 物理與實務對照

| 項目 | 現行設計 | 可能偏差 | 結論 |
|------|----------|----------|------|
| **漏水速率 (0.30 ml/s)** | 固定參考速率 × (dial/4.5) | 直立沖煮時注水階段即開始滴漏，實務常見 5–15% 總水量流失；目前 2.8–4% 落在偏低區間 | **傾向低估** 漏水量，尤其長 seal_delay 或粗研磨 |
| **dial 指數 η=1** | 漏水量 ∝ dial（線性） | 達西定律流速 ∝ 滲透率，粒徑平方級；dial 若近似粒徑，η≈2 更貼近；η=1 使粗研磨漏水量較不敏感 | 粗研磨時 **傾向低估** 漏水量 |
| **上限 12%** | 漏水不超過 water_ml×12% | 若 seal_delay 很長（如 15–20 s），實際可漏 15–25%；12% 會壓低此情境的 V_drip | 長延遲時 **低估** |
| **接觸時間 (CONTACT_FRACTION=0.20)** | 支流有效接觸 = 20%×t_drip | 滴出液體接觸時間分布從近 0 到近 t_drip，0.20 為簡化平均 | 不確定，需實測；若實際平均 >20% 則支流萃取 **低估** |
| **支流萃取效率 (PERCOLATION_EFF=0.03)** | 支流 EY 僅 3% 計入總 EY | 支流偏弱，3% 屬保守；若漏水量被低估，整體支流貢獻也會被低估 | 與漏水量同向，多數情境 **低估** 支流對 EY 的貢獻 |

### 16.3 綜合結論

- **漏水量（V_drip）**：在常見參數下（dial 3.5–6.5、seal_delay 5 s）**傾向低估**；長 seal_delay 或粗研磨時低估更明顯。
- **支流對總 EY／風味的影響**：因 V_drip 偏低且效率係數保守，**整體支流貢獻傾向低估**；主流自由溶劑的減少（`free_water_main = water_ml - V_drip - retention`）也隨之偏小，故封閉段 EY 可能略為 **高估**（因以為可用溶劑比實際多）。
- **已採修正（貼近現實）**：`PRE_SEAL_DRIP_RATE_REF` 0.30 → 0.38、`PRE_SEAL_DRIP_DIAL_EXP` 1.0 → 1.2、`PRE_SEAL_DRIP_MAX_RATIO` 0.12 → 0.18；程式已更新，後續可依 §15 實測再微調。
