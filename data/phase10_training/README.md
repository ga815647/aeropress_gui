# Phase 10 訓練資料

Phase 10 Layer 2（`f(TDS,EY,roast,溫度,研磨)→6 感官軸`）的外部訓練資料。
取得紀錄與軸定案見 [`../../docs/PHASE10_STEP1_SENSORY_AXES.md`](../../docs/PHASE10_STEP1_SENSORY_AXES.md)。

---

## `cotter_dataset.csv` + `README.txt`（UC Davis 消費者偏好資料集）

- **來源**：Cotter, Ristenpart & Guinard (2022)，*Consumer preference data for black coffee*，Dryad `doi:10.25338/B8993H`。
- **授權**：CC0 1.0（公眾領域，可自由使用）。
- **原始論文**：Cotter et al., J Food Sci 2021（`10.1111/1750-3841.15561`）；Ristenpart et al., Sci Rep 2022（`10.1038/s41598-022-23904-4`）。
- 下載日期：2026-05-21。`README.txt` 是資料集原附的官方欄位說明（48 變數逐欄定義）。

### 為什麼這份資料對 Phase 10 有用

這就是藍圖 §8 要的 **(TDS, EY) 因子網格骨架**：

- **3×3×3 完整因子設計**：溫度（87/90/93°C）× TDS（1.0/1.25/1.5%）× PE 萃取率（16/20/24%）= 27 個 brew cell，每 cell ~118 人試飲，共 3186 筆。
- 每筆有**實測** `TDS__1`（折射儀）、`Percent Extraction`、`pH`、滴定酸度（NaOH 體積）—— 正好是 Phase 10 的中樞變數。實測 TDS 0.93–2.29%、PE 14.0–36.6%。
- **17 個感官屬性**以 CATA（check-all-that-apply）二元值記錄（0=未偵測 / 1=偵測）；跨 118 人聚合 → 每個 brew cell 得到每屬性的「偵測頻率」（連續 0–1 訊號）。
- 另有 hedonic `Liking`（9 分）、JAR 量表（Flavor.intensity / Acidity / Mouthfeel / Temp）、`Purchase.intent`。

### 17 CATA 屬性 → Phase 10 六感官軸對應

| 6 軸 | 本資料集 CATA 欄位 | 輔助欄位 |
|---|---|---|
| `acidity` | Sour, Citrus | `Acidity` JAR、`pH`、滴定酸度 |
| `sweetness` | Sweet, Caramel | — |
| `body` | Thick.viscous | `Mouthfeel` JAR |
| `bitterness` | Bitter | — |
| `astringency` | Astringent, Paper.wood | — |
| `roast` | Roasted, Burnt | — |
| （非軸 — 香氣性格區域）| Tea.floral, Fruit, Citrus, Green.veg, Cereal, Nutty, Dark.chocolate, Rubber | 驗證 Step 1 §6 |

**性質注意**：這是**消費者 CATA**（偵測/未偵測 → 頻率），不是 trained-DA-panel 的強度量表。優點是大樣本（118 人）、是 Phase 10 想要的因子網格、且「消費者實際感知」比訓練 panel 更貼模型目的（評分 = 預測使用者感知）。缺點是 binary，需以「cell 偵測頻率」當強度代理。Layer 2 回歸時以此為主骨架。

---

## 未取得的資料（移交後續處理）

- **浸泡 DA 研究**（Sci Rep 2024，PMC11335879）的原始 DA 資料，論文標註 Dryad `10.5061/dryad.v15dv423h`：
  **該 DOI 未在 DataCite 註冊、doi.org 無法解析；Dryad 後端有紀錄（dataset id 124603）但狀態為「cannot be viewed」（私有 / curation 未完成）。研判資料集從未正式公開。** 已無程式化取得途徑。
  替代：論文本身有 28 屬性表與 PCA loadings（已用於 Step 1）；浸泡專屬修正改靠使用者 `feedback.jsonl` 精修。
- **Batali 2020 溫度 DA 研究 / Guinard 2023 BCC roast 因子研究**的 trained-panel 強度資料：未在 Dryad / DataCite 找到開放 deposit。論文的相關性表與屬性表已擷取於 Step 1 文件。
