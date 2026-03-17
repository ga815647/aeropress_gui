# AeroPress Optimizer — Claude 工作規則

## 口感矯正工作流程（強制）

每當使用者提供口感矯正指示（例如「太苦」「酸不足」「澀感高」「甜感弱」等），
必須在修改 `constants.py` 後**立即執行**：

```bash
python diagnose_anchor.py
```

若輸出顯示 `[ FAIL ]`，**必須修正常數直到全部通過**，才能回報完成。

### 錨點基準（勿偏離）

| 參數 | Hoffman 實測值 | 模型目標 |
|------|--------------|---------|
| TDS | 1.23%（稍粗）→ 原版 ~1.27% | TDS_PREFER["light"] = 1.27 |
| EY | 19.9% | EY_PREFER["light"] = 19.0 |
| 研磨 | 450–600µm EK43 → ZP6 dial ≈ 4.3 | dial_prefer["light"] = 4.3 |
| 水溫 | 97.8°C（208°F） | 搜尋範圍 93–99°C，已涵蓋 |
| 浸泡 | 2:30 開始壓 → 模型 steep=135s 或 150s | 兩者等效，Top 10 需含其一 |

### 常數修改方向參考

| 口感症狀 | 可能方向 | 注意 |
|---------|---------|------|
| 太苦 | 降低 CGA_ASTRINGENCY_SLOPE、MEL_BITTER_COEFF | 確認 Top3 TDS 不下移 |
| 酸不足 | 調整 IDEAL_FLAVOR AC 比例、降低 KH_PERCEPT_DECAY | 確認 EY 不過高 |
| 太澀 | 降低 CGA_ASTRINGENCY_SLOPE 或 HARSHNESS_SLOPE | 確認 135s 仍在 Top 10 |
| 甜感弱 | 調高 IDEAL_FLAVOR SW 比例、檢查 SW_AROMA_THRESH | 確認不影響 AC/SW 比例 |
| 醇厚不足 | 調整 EY_PS_EXP、EY_PREFER | 確認 EY_PREFER 不低於 18.5 |
| 太濃 | 降低 TDS_PREFER（謹慎：不低於 1.20） | 確認 Hoffman EY 18–22% |
| 太淡 | 提高 TDS_PREFER | 確認不超過 1.35 |

## 模型關鍵檔案

| 檔案 | 內容 |
|------|------|
| `constants.py` | 所有可調常數，口感矯正修改此檔 |
| `diagnose_anchor.py` | Hoffman 錨點驗證，每次修改後必跑 |
| `models/scoring.py` | 評分邏輯（cosine_sim、懲罰項） |
| `models/compounds.py` | 六化合物萃取預測 |
| `models/ey_model.py` | EY 計算 |
| `optimizer.py` | 網格搜尋主體 |

## ZP6 Dial 參照

- `dial < 4.5`：細研磨（Hoffman 錨點 4.3 在此範圍）
- `dial = 4.5`：模型參考點（DIAL_BASE）
- `dial > 4.5`：粗研磨

各焙度 `dial_prefer` 已寫入 `ROAST_TABLE`，修改時勿移除此欄位。
