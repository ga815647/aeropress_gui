# AeroPress Optimizer

這個專案用來計算 AeroPress 沖煮參數組合，依照烘焙度、水質與器材尺寸，找出分數最高的建議配方。專案同時提供命令列工具與 Flask Web 介面。

## 功能

- 掃描沖煮溫度、研磨刻度、浸泡時間與粉量組合
- 依烘焙度與風味模型計算 EY、TDS、化合物向量與總分
- 支援 `standard` 與 `xl` 兩種 AeroPress 容量
- 支援手動輸入水質，或套用內建水質 preset
- 可輸出終端摘要、`output.json`、`output.csv`
- 可額外產生 `radar_top3.png`
- 提供 Web UI 與 `/api/optimize` API

## 需求

- Python 3.10 以上

## 安裝

```bash
pip install -e .
```

若需要跑測試：

```bash
pip install -e .[dev]
```

## 專案結構

```text
.
├─ main.py                # CLI 入口
├─ webapp.py              # Flask Web 入口
├─ optimizer.py           # 參數搜尋與排序
├─ constants.py           # 模型常數與預設值
├─ runtime.py             # 環境與水質參數解析
├─ data/water_presets.py  # 內建水質 preset
├─ models/                # EY / TDS / compounds / scoring 模型
├─ output/                # terminal / json / csv / radar 輸出
├─ templates/             # Web 頁面模板
├─ static/                # Web 靜態資源
└─ tests/                 # pytest 測試
```

## CLI 使用方式

最基本的執行方式：

```bash
python main.py --roast M --gh 50 --kh 30
```

使用內建水質 preset：

```bash
python main.py --roast M --preset aquacode_7l
```

輸出 JSON 與雷達圖：

```bash
python main.py --roast M --preset aquacode_7l --top 3 --output json --radar
```

輸出 CSV：

```bash
python main.py --roast MD --brewer xl --gh 60 --kh 20 --mg-frac 0.7 --output csv
```

### 主要參數

| 參數 | 說明 | 預設值 |
| --- | --- | --- |
| `--roast` | 烘焙度，支援 `L+` `L` `LM` `M` `MD` `D` | 必填 |
| `--brewer` | AeroPress 容量，支援 `standard` `xl` | `xl` |
| `--preset` | 套用內建水質 preset | 無 |
| `--gh` | 手動指定 GH ppm | 無 |
| `--kh` | 手動指定 KH ppm | 無 |
| `--mg-frac` | GH 中鎂比例，範圍 0.0 到 1.0 | `0.40` |
| `--top` | 輸出前幾個最佳結果 | `3` |
| `--output` | `terminal` `json` `csv` | `terminal` |
| `--radar` | 額外輸出雷達圖 | 關閉 |
| `--t-env` | 環境溫度（攝氏） | `25.0` |
| `--tds-floor` | TDS 下限 | `0.80` |
| `--altitude` | 海拔高度（公尺） | `0.0` |

### 水質輸入規則

- 若同時提供 `--gh` 與 `--kh`，會優先使用手動輸入的水質
- 若未提供手動水質但提供 `--preset`，會套用對應 preset
- 若兩者都沒有提供，會使用預設值 `GH=50`、`KH=30`、`mg_frac=0.40`

目前內建 preset key：

- `ro`
- `hualien_fenglin_brita`
- `hualien_guangfu_brita`
- `hualien_fenglin_bwt`
- `hualien_guangfu_bwt`
- `aquacode_7l`
- `aquacode_5l`
- `spritzer`
- `jeju_samdasoo`

## 輸出檔案

- `output.json`: 結構化結果，包含輸入條件、Hoffman 流程參數、分數與化合物指標
- `output.csv`: 扁平化表格，方便匯入試算表分析
- `radar_top3.png`: 前三名結果的雷達圖

## Web 介面

啟動方式：

```bash
python webapp.py
```

預設會以 `0.0.0.0:8000` 啟動，且 `debug=True`。若只想在本機開啟：

```bash
python webapp.py --host 127.0.0.1 --port 8000 --no-debug
```

### API

- `GET /`
  - 回傳 Web 操作頁面
- `GET /api/config`
  - 回傳烘焙度、器材選項、水質 preset 與預設值
- `POST /api/optimize`
  - 送入沖煮條件並回傳最佳結果

`POST /api/optimize` 範例：

```json
{
  "brewer": "xl",
  "roast": "M",
  "preset": "aquacode_7l",
  "top": 3,
  "t_env": 25,
  "tds_floor": 0.8,
  "altitude": 0
}
```

## 測試

```bash
pytest
```

目前測試涵蓋：

- CLI 參數與輸出檔案
- Web 路由與 API
- 水質 preset 套用
- 模型與輸出格式的基本驗證

## 開發備註

- CLI 與 Web API 共用同一套核心最佳化邏輯，入口分別在 `main.py` 與 `webapp.py`
- `runtime.py` 會在執行時覆寫環境溫度、沸點與 TDS 下限等全域常數
- 若要調整模型假設，優先檢查 `constants.py` 與 `models/`
