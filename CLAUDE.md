# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 路由

| 想看什麼 | 去哪 |
|---------|------|
| 待辦任務 / phase 歷史 / 評分鑑別度改革紀錄 | [`TASKS.md`](TASKS.md) |
| 泡法時間軸 / 各時間參數定義 / 三錨點時間圖 | [`BREW_PROTOCOL.md`](BREW_PROTOCOL.md) |
| Data flow / 兩層模型 / Grid search / 迴圈引擎 / Key files / 調整方向表 | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| 舊六化合物架構（凍結，僅 `compound-model-legacy` branch 成立）| [`docs/ARCHITECTURE_legacy.md`](docs/ARCHITECTURE_legacy.md) |
| Phase 10 感官重構藍圖（架構、訓練資料、8 步執行步驟）| [`docs/PHASE10_SENSORY_REFOUNDING.md`](docs/PHASE10_SENSORY_REFOUNDING.md) |
| Phase 10 Step 1 — 6 感官軸定案 | [`docs/PHASE10_STEP1_SENSORY_AXES.md`](docs/PHASE10_STEP1_SENSORY_AXES.md) |
| Phase 10 Step 2 — Layer 2 風味模型（6 軸版，已被 5.5 取代）| [`docs/PHASE10_STEP2_LAYER2.md`](docs/PHASE10_STEP2_LAYER2.md) |
| Phase 10 Step 3 — per-roast 感官 IDEAL（label 移除）| [`docs/PHASE10_STEP3_LABELS.md`](docs/PHASE10_STEP3_LABELS.md) |
| Phase 10 Step 4 — 薄 Layer 1（knob→TDS/EY，平衡脫附式、Hoffman 單錨點）| [`docs/PHASE10_STEP4_LAYER1.md`](docs/PHASE10_STEP4_LAYER1.md) |
| Phase 10 Step 5 — 感官距離 + optimizer 重接線（無 0–100 評分） | [`docs/PHASE10_STEP5_SCORING.md`](docs/PHASE10_STEP5_SCORING.md) |
| Phase 10 Step 5.5 — Layer 2 改 10 cotter 屬性各自回歸 | [`docs/PHASE10_STEP5_5_ALL_ATTRIBUTES.md`](docs/PHASE10_STEP5_5_ALL_ATTRIBUTES.md) |
| Phase 10 Step 6 + Phase 11 — Feedback 迴圈設計（藍圖 + 裁決紀錄）| [`docs/PHASE10_STEP6_FEEDBACK_LOOP.md`](docs/PHASE10_STEP6_FEEDBACK_LOOP.md) |
| Feedback schema 規格（pairwise + ordinal）| [`docs/FEEDBACK_FORMAT.md`](docs/FEEDBACK_FORMAT.md) |
| Phase 11 迴圈引擎落地紀錄（狀態機、digest、skip、flag、changelog）| [`docs/PHASE11_LOOP_ENGINE.md`](docs/PHASE11_LOOP_ENGINE.md) |
| Claude tier-3 模型改動紀錄（每筆 refine 一行） | [`data/refine_changelog.md`](data/refine_changelog.md) |

## 目前狀態（2026-05-23）

**Phase 10 + Phase 11 都已完成、合進 `main`。** 系統現在是:

- **管線:** `knobs → models/layer1.py:brew → {TDS, EY} → models/sensory.py:predict_attributes → 10 感官屬性 → models/distance.py:attribute_distance → 距該焙度 IDEAL 的 RMS`。沒有 0–100 評分;排序的數字就是顯示的數字。詳見 [`ARCHITECTURE.md`](ARCHITECTURE.md)。
- **per-roast IDEAL 信心分層** —— `medium_light` = 使用者 ⭐5 杯(Tier A);`light` = tim feedback(暫定,tim 不是 Layer 1 錨點);`medium` / `moderately_dark` = 佔位,待該焙度有 feedback 才真錨定。
- **Phase 11 迴圈引擎是主要精修機制** —— per-roast (1+λ) 演化搜尋,三杯循環 `[實驗1, 實驗2, 冠軍重泡]`,使用者用 §4 對照問卷比較,系統往使用者偏好收斂(約 10–30 杯)。webapp 點「迴圈精修」頁籤進入。詳見 [`docs/PHASE11_LOOP_ENGINE.md`](docs/PHASE11_LOOP_ENGINE.md)。
- **75 pytest PASS;`diagnose_anchor.py` 13/13(exit 0)。**
- **舊六化合物模型**(Phase 8 及之前)凍結在 git branch `compound-model-legacy`;舊架構文件凍結在 [`docs/ARCHITECTURE_legacy.md`](docs/ARCHITECTURE_legacy.md)。`main` 上**沒有** `compounds.py` / `scoring.py` / `labels.py` / `ey_model.py` / `tds_model.py` / `water_presets.py`。

## Commands

```bash
# CLI(一次性 Top-N 最佳化器)
python main.py --roast medium_light --brewer xl --top 3
python main.py --roast light --brewer xl --temp 98 --output json --radar

# Web(含 Phase 11 迴圈精修)
python webapp.py
# → http://localhost:8000
#   左側選焙度 / 容量 / 水溫;右側兩個頁籤:
#   「最佳化器」 = Top-N 菜單(迴圈前的純 exploit)
#   「迴圈精修」 = 三杯循環 + 跳過 + §4 問卷 + 命名配方庫

# 模型診斷(改 model 檔後強制跑)
python diagnose_anchor.py    # exit 0 = 13/13 PASS

# 測試
python -m pytest tests/      # 75 PASS
```

**CLI flags:** `--roast`(必填,`light` / `medium_light` / `medium` / `moderately_dark`)、`--brewer`(`standard` / `xl`)、`--temp`(°C,省略則用 `constants.DEFAULT_TEMP[roast]`)、`--top N`、`--output`(`terminal` / `json` / `csv`)、`--radar`。

**已移除的 flag(別用):** `--label`、`--preset`、`--gh` / `--kh` / `--mg-frac`、`--t-env`、`--altitude` —— Phase 10 移除 label 與水質,Phase 10 Step 4 移除 T_ENV 路徑。

---

## 精修工作流程

當使用者反映口感問題(「太苦」「酸不足」「澀感高」「甜感弱」)或對推薦不滿:

**首選:用迴圈。** 開 webapp「迴圈精修」頁籤,泡三杯循環、填 §4 對照問卷 —— 迴圈本來就是為此而生,會在約 10–30 杯內把該焙度的冠軍往使用者偏好收斂。**別手動調參數去追單一杯的口感** —— 那是迴圈要取代的事。

**改某焙度的風味目標**(移動靶位置):動 `data/ideal.json[<roast>].ideal` 的 10 屬性值。零副作用其他焙度。

**模型預測方向反了(flag 重複出現):** `detect_flags()` 找 `model_attributes_vs` ↔ `attributes_vs` 重複反向矛盾(`FLAG_REPEAT_THRESHOLD=2`,任一邊為 `?` 排除)。flag 浮現 → 使用者開對話 → Claude 讀 `feedback.jsonl` 一次看一批 → 動 `models/sensory.py:_COEF` 或 `models/layer1.py` 參數。**每筆 Claude 動模型必須**在 [`data/refine_changelog.md`](data/refine_changelog.md) append 一行(日期 / 檔 / 改什麼 / 為什麼 / 怎麼回退)。**迴圈本身永不自動改模型。**

**改完任何模型檔**(`models/layer1.py` / `models/sensory.py` / `models/distance.py` / `models/ideal.py` / `data/ideal.json`)**必須**:

```bash
python diagnose_anchor.py    # exit 0 = 13/13 PASS
python -m pytest tests/       # 75 PASS
```

`.claude/hooks/anchor_check.py` hook 會在你 Edit/Write 這些檔案時自動跑 diagnose,exit 非 0 會 block(這修掉了舊版「diagnose 崩潰 → grep 不到 `[ FAIL ]` → 注入假 PASS」的 bug)。

**禁止為了讓某個錨點 / 焙度通過而削弱模型** —— 必須找物理或資料根因。對某焙度的口感矯正,優先動 `data/ideal.json[<roast>]`(零副作用其他焙度),最後才動 Layer 1 / Layer 2 模組常數(會牽動所有焙度)。

---

## Layer 1 校準錨點 — Hoffman(純浸泡)

`models/layer1.py` 的唯一錨定點。`E_MAX_REF` 由它解出(讓 predicted TDS = 實測 1.23%),其餘 4 個參數(`TAU_REF` / `ALPHA` / `GAMMA` / `K_RATIO`)是物理先驗。

| 參數 | Hoffman 實測 | 模型對應 |
|------|------------|---------|
| TDS | 1.23%(實測) | `diagnose_anchor.py`: assert `\|predicted − 1.23\| ≤ 0.05` |
| EY | 20–22% | `diagnose_anchor.py` band `[17, 23]`(EY 不進評分,只做合理性 sanity)|
| 研磨 | 450–600µm EK43 ≈ ZP6 dial 4.3 | `models/layer1.py:DIAL_REF = 4.3` |
| 水溫 | 97.8°C (208°F) | `T_REF = 98.0` |
| 浸泡 | 2:00 → swirl → press | 錨點檢查 `fixed_steep = 120s` |
| 劑量 / 水量 | 11g / 200ml | — |

**注意:April / Championship 已不是 Layer 1 錨點。** Phase 10 Step 4 把它們剔除 —— 它們是技法沖煮(半密封 / 倒置 + agitation),屬「不同黑箱」,不該用來校準純浸泡模型(`docs/PHASE10_STEP4_LAYER1.md` §6)。三錨點完整食譜仍在 [`BREW_PROTOCOL.md`](BREW_PROTOCOL.md),當歷史 / 感官參考。

---

## 模型設計原則(紅線,禁止偏離)

**好喝不好喝跟「怎麼泡」無關。系統只看杯中物 —— Layer 2 預測的 10 感官屬性。**
- 溫度 / 浸泡時間 / 研磨 / dose 是過程變數,只**經 Layer 1 的 TDS / EY** 進入感官預測,**不可作為主要扣分依據**。
- TDS / EY 是中樞潛變數(使用者無折射儀、不實測),它們對風味的影響已**完全經 10 屬性表達**(`models/sensory.py:_COEF`),距離公式不再有獨立的 `tds_factor`。
- 排序的數字就是顯示的數字:`distance` = 10 屬性 vs IDEAL 的純未加權 RMS,**沒有 0–100 評分**(cotter hedonic 資料證實無「客觀最好」)。

### 五條不可違反的架構原則

1. **平滑連續、無硬斷點** —— 物理世界是連續的。`models/layer1.py` / `models/sensory.py` / `models/distance.py` 三個模組都不准出現 `min` / `max` / `if/else` 硬斷點。所有閾值、天花板、地板必須用平滑連續函數:
   - `max(x − threshold, 0)` → softplus
   - `min(x, cap)` → sigmoid saturation
   - `if x > threshold` → sigmoid transition
   - 例外:純離散邏輯(如 `brewer="xl" / "standard"` 影響 `water_ml`)不在此限。

2. **單一管線、單一公式** —— 所有焙度、所有候選配方都走同一個 `optimizer.evaluate_recipe`:`layer1.brew → sensory.predict_attributes → distance.attribute_distance`。距離公式對所有焙度結構相同,只是 IDEAL 不同。**禁止任何錨點 / 焙度走特例 scoring path**(舊有「`_anchor_cosine_score()`」「per-label `flavor_score`」這類分支已不准重現)。

3. **模型自我鑑別** —— 好杯(`medium_light` 的使用者 ⭐5、`light` 的 tim ⭐4)的預測屬性自然落在 IDEAL 附近;爛杯(欠/過萃)自然遠。`diagnose_anchor.py` 的「good ≪ over-extract ≪ under-extract」檢查就是這條原則的閘門。**不准靠 TDS floor 或 EY floor 區分好壞** —— Layer 1 + Layer 2 信號本身要承載這個資訊。違反的徵兆:寫出來欠萃跟好杯距離差不開,然後想加一個 `tds_factor` / `ey_floor` 補救 —— 那是治標,根因在 Layer 1 / Layer 2 某個係數。

4. **兩層嚴格分工:Layer 1 純 `exp()`、Layer 2 純資料、distance 純 RMS** —— 三個模組各司其職、不互相污染:
   - **Layer 1(`models/layer1.py`)—— 物理。** **禁所有閾值**:onset 時間、time floor、tent function、`softplus(x − threshold)`、`sigmoid(k·(x − threshold))`。只准全域單調、無拐點、無 threshold 參數的 `exp()` 結構(Arrhenius / 一階)。即使數學上平滑,**藏 threshold 參數的函數一律禁止**。
   - **Layer 2(`models/sensory.py`)—— 感官。** 係數從 cotter 27-cell 資料 OLS 回歸而來,**不手寫感官閾值**(舊 `SW_AROMA_THRESH` / `SCORCH_PARAMS` / `KH_FLOOR` 等通通隨 `scoring.py` 刪了)。新屬性必須過 R² ≥ 0.44 閘門才進。`b_temp` 固定 0(Batali 2020 + cotter:固定 TDS/EY 下溫度無感官效應)。
   - **distance(`models/distance.py`)—— 純未加權 RMS。** 沒有 `tds_factor`、沒有 floor、沒有 ratio bonus、沒有加權。閘門過了的 10 個屬性等權進入。
   - **代價(歷史教訓):** 任一層偷塞閾值或補丁 → 模型自我鑑別力下降(→ 違反 #3)→ 評分得靠 process-variable 後置 gate 補救(`acid_trap = sigmoid(temp − 96) × sigmoid(120 − steep)`)→ 補丁治標、根因仍在模組內部的非物理 gate。Phase 8/9 累積的這類補丁就是 Phase 10 重寫的動機。

5. **錨點兩層:Layer 1 物理校準錨點 vs Layer 2 感官目標** —— 嚴格角色分工,共用數字、不同角色:
   - **Layer 1 物理校準錨點** —— 唯一是 **Hoffman**(98°C / dial 4.3 / 120s / 11g / 200ml → 實測 TDS 1.23%)。`E_MAX_REF` 由它解出。**與好不好喝無關** —— 它只回答「物理模型對不對」。可以無限多(多了只是更多 fit 點,不會互相打架);April / Champion 是技法沖煮,**剔除**。
   - **Layer 2 感官目標(per-roast IDEAL)** —— 每個焙度一份 10 屬性目標(`data/ideal.json`)。**這是 Phase 11 迴圈在搜尋的移動靶,不是手設的固定靶。** `medium_light` = 使用者 ⭐5 杯(Tier A);`light` = tim feedback(暫定);`medium` / `moderately_dark` = 佔位,待 feedback 校準。可以有「沒對應感官目標的純物理錨點」(只進 Layer 1)、也可以有「沒對應物理錨點的感官目標」(per-roast IDEAL 都靠 feedback,不需要對應物理錨點)。
   - **違反此原則的徵兆:** 加新焙度時動到舊焙度的分數;改某焙度 IDEAL 動到 Hoffman 的物理重現 —— 兩層沒拆乾淨。
   - **歷史(供對照):** Phase 4 加 Hedrick 時打亂 Hoffman / April 的分數,就是這條原則沒落實的症狀;Phase 8 拆 label 島、Phase 10 改 per-roast IDEAL,把兩層的角色完全分開,該症狀絕跡。

### 原則 #1 vs #4 的關係

| 角度 | #1(全域)| #4(分層)|
|------|---------|---------|
| 規定 | **怎麼寫**閾值(要平滑)| **哪裡可以有**閾值(三個模組都不准)|
| Layer 1 | 不能用硬斷點 | 連平滑閾值也禁止,只能用 `exp()` |
| Layer 2 | 不能用硬斷點 | 係數從資料來,不手寫閾值 |
| distance | 不能用硬斷點 | 純未加權 RMS,沒有 factor / floor |

**關鍵:`exp()` vs `sigmoid` / `softplus` 結構不同:**
- `exp(−Ea/RT)`、`1 − exp(−k·t)`:**全域 monotone、無拐點、無 threshold 參數** → 純物理曲線。
- `sigmoid(k·(x − threshold))`、`softplus(x − threshold)`:**顯式 threshold 參數、有 inflection 點** → 閾值化(即使平滑)。

Layer 1 即使用平滑的 `softplus(temp − 92)`,雖然滿足 #1 但違反 #4(藏 threshold);改成 `exp(Ea/R × (1/T_ref − 1/T))` 才同時滿足兩者。Phase 10 重寫的 [`models/layer1.py`](models/layer1.py) 全是後者。

### Phase 11 補述(迴圈紅線)

- **靠喝評判、不靠讀配方。** 迴圈一次只提**一杯**(單杯 + 跳過),使用者用味覺評。**不做「多選一菜單」** —— 那會讓使用者挑「最像現在愛喝那杯」、探索死亡。Top-N 菜單只留給迴圈前的純 exploit 最佳化器。
- **跳過 = 後勤性,不是味覺回饋。** 跳過會在**同探索半徑**重抽,使用者不能靠連續跳過漂向安全牌。
- **迴圈永不自動改模型。** 模型方向預測錯了,記 flag、邀請對話。改模型是 Claude tier-3 工作,每筆寫一行 `data/refine_changelog.md`、可回退。
