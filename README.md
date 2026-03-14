# AeroPress Optimizer

根據烘焙度、水質與器材尺寸，搜尋分數最高的 AeroPress 沖煮參數組合。提供 CLI 與 Flask Web 介面。

## 功能

- 掃描溫度、研磨刻度、浸泡時間、粉量
- 依烘焙度與風味模型計算 EY、TDS、化合物向量與總分
- 支援 `standard` / `xl` 兩種 AeroPress 容量
- 手動水質或內建 preset
- 輸出：終端摘要、JSON、CSV、雷達圖
- Web UI 與 `/api/optimize` API

## 需求

- Python 3.10+

## 安裝

```bash
pip install -e .
```

開發與測試：

```bash
pip install -e .[dev]
```

## 專案結構

```
.
├── main.py              # CLI 入口
├── webapp.py            # Flask Web 入口
├── optimizer.py         # 參數搜尋與排序
├── constants.py         # 模型常數
├── runtime.py           # 環境與水質解析
├── AeroPress_4Vector_白皮書.md   # 完整規格（整合 v5.8s + 封閉前漏水 + 口感校正 + 焙度對照）
├── data/water_presets.py
├── models/              # EY / TDS / compounds / scoring
├── output/              # terminal / json / csv / radar
├── templates/
├── static/
└── tests/
```

## CLI

### 基本用法

```bash
python main.py --roast M --gh 50 --kh 30
```

```bash
python main.py --roast M --preset aquacode_7l
```

```bash
python main.py --roast M --preset aquacode_7l --top 3 --output json --radar
```

```bash
python main.py --roast MD --brewer xl --gh 60 --kh 20 --mg-frac 0.7 --output csv
```

### 參數

| 參數 | 說明 | 預設 |
| --- | --- | --- |
| `--roast` | 焙度（SCA 代號）`very_light` `light` `medium_light` `medium` `moderately_dark` `dark` `very_dark` | 必填 |
| `--brewer` | 容量 `standard` / `xl` | `xl` |
| `--preset` | 水質 preset | 無 |
| `--gh` | GH ppm | 無 |
| `--kh` | KH ppm | 無 |
| `--mg-frac` | 鎂比例 0.0–1.0 | `0.40` |
| `--top` | 輸出前 N 名 | `3` |
| `--output` | `terminal` / `json` / `csv` | `terminal` |
| `--radar` | 輸出雷達圖 | 關閉 |
| `--t-env` | 環境溫度 °C | `25.0` |
| `--altitude` | 海拔 m | `0` |

### 水質

- 有 `--gh` + `--kh` → 用手動值
- 僅 `--preset` → 用該 preset
- 皆無 → GH=50, KH=30, mg_frac=0.40

**焙度對照（SCA / Agtron）：** very_light 85–95 | light 75–80 | medium_light 60–70 | medium 50–55 | moderately_dark 40–45 | dark 30–35 | very_dark 20–25

**Preset key：** `ro` `aquacode_7l` `dr_you_jeju_yongamsoo` `tamsaa_jeju_water_j_creation` `volvic_pure` `top1_tamsaa_sweetness` `top2_volvic_balance` `top3_jeju_structure`

## 輸出檔案

- `output.json` — 結構化結果
- `output.csv` — 扁平化表格
- `radar_top3.png` — 前三名雷達圖

## Web

```bash
python webapp.py
```

預設 `0.0.0.0:8000`，debug 開啟。本機測試：

```bash
python webapp.py --host 127.0.0.1 --port 8000 --no-debug
```

### API

| 路由 | 說明 |
| --- | --- |
| `GET /` | 操作頁面 |
| `GET /api/config` | 烘焙度、器材、preset、預設值 |
| `POST /api/optimize` | 送出條件，回傳最佳結果 |

`POST /api/optimize` 範例：

```json
{
  "brewer": "xl",
  "roast": "medium",
  "preset": "aquacode_7l",
  "top": 3,
  "t_env": 25,
  "altitude": 0
}
```

## 測試

```bash
pytest
```

涵蓋：CLI 參數與輸出、Web 路由、水質 preset、模型基本驗證。

## 開發

- CLI 與 Web 共用 `optimizer` 核心
- `runtime.py` 覆寫 `T_ENV`、沸點等常數
- 模型常數在 `constants.py`，邏輯在 `models/`
