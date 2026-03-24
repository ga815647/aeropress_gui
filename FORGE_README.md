# Forge v5 — Aider 確定性路由 Wrapper

一個 Python 檔案。路由不靠 LLM，記憶不住在 LLM 腦裡，每次呼叫用完即棄。

## 架構

```
你打字
  ↓
forge.py（Python if/else 路由，0 token）
  ↓
自動注入 memory-bank/ + skills/
  ↓
aider --architect / --code / --ask（用完即棄）
  ↓
aider 自動 git commit + lint + test
  ↓
forge.py 更新 progress.md
  ↓
回到 prompt
```

## 安裝

**macOS / Linux：**

```bash
# 1. 裝 aider
pip install aider-install
aider-install

# 2. 設 API key（選一個或多個）
export ANTHROPIC_API_KEY=your-key
export OPENAI_API_KEY=your-key
export DEEPSEEK_API_KEY=your-key

# 3. 把 forge.py 放進專案根目錄
cp forge.py /path/to/your/project/

# 4. 建 memory-bank
mkdir -p memory-bank
touch memory-bank/{activeContext,progress,systemPatterns,productContext,decisionLog,techContext}.md

# 5.（選配）建 skills 目錄
mkdir -p skills
```

**Windows（PowerShell）：**

```powershell
# 1. 裝 aider
pip install aider-install
aider-install

# 2. 設 API key（永久，存到使用者環境變數）
[System.Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "your-key", "User")
# ⚠️ 設完要重開 PowerShell 才會生效

# 3. 把 forge.py 放進專案根目錄（手動複製即可）

# 4. 建 memory-bank
mkdir memory-bank
New-Item memory-bank\activeContext.md, memory-bank\progress.md, memory-bank\systemPatterns.md, memory-bank\productContext.md, memory-bank\decisionLog.md, memory-bank\techContext.md -ItemType File

# 5.（選配）建 skills 目錄
mkdir skills
```

## Windows 踩坑紀錄

| 坑 | 原因 | 解法 |
|---|---|---|
| `export` 指令無效 | `export` 是 Linux/Mac 語法，PowerShell 不認識 | 改用 `[System.Environment]::SetEnvironmentVariable(...)` |
| 設完環境變數沒生效 | 同一個 PowerShell 視窗不會讀到新值 | 設完一定要重開新的 PowerShell 視窗 |
| `aider` 指令找不到 | aider 裝在 `C:\Users\user\.local\bin`，但該路徑不在 PATH | 加入 PATH：`[System.Environment]::SetEnvironmentVariable("PATH", $env:PATH + ";C:\Users\user\.local\bin", "User")` 後重開視窗 |
| `No Windows console found` | aider 的 prompt toolkit 不相容 PowerShell | forge.py 已內建 `--no-pretty` 修正（v5.1+） |

## 使用

```bash
python forge.py            # 互動模式
python forge.py "修 typo"   # 單次模式
```

## 指令

| 指令 | 效果 |
|------|------|
| 直接打需求 | 自動路由到 architect / code / ask |
| `!architect` | 手動強制走 architect |
| `!code` | 手動強制走 code |
| `!ask` | 手動強制走 ask |
| `UMB` | 更新記憶（ask 幫你修飾，你確認後存） |
| `lessons` | 分析 systemPatterns.md，找值得提煉的 skill |
| `q` / `exit` | 離開 |

## 路由規則

所有路由是 Python if/else，0 token，不呼叫 LLM。

| 優先順序 | 條件 | 路由 | 信心 |
|---|---|---|---|
| 1 | `!architect` / `!code` / `!ask` | 手動指定 | high |
| 2 | 偵測到 traceback / error | code | high |
| 3 | 純問句，無改 code 意圖 | ask | high |
| 4 | 有架構關鍵詞（排除否定句） | architect | high |
| 5 | 有小改動關鍵詞（排除否定句） | code | high |
| 6 | 架構+小改動混合信號 | architect | low |
| 7 | 訊息超過 150 字（扣除 code block） | architect | low |
| 8 | 以上都不符合 | code | low |

低信心時會停下來讓你確認，一個字母切換，或按 `v` 修飾 prompt。

## 信心路由 + 修飾 prompt

低信心時：

```
  📐 建議: architect — 長訊息（180 字），無明確信號
  💡 不確定需求是否精準？按 v 讓 AI 幫你修飾 prompt 再進 architect
  [Enter] 繼續  v=修飾 prompt  a=architect  c=code  Ctrl+C 取消
  > v
  💬 ask — 修飾 prompt
  [ask 修飾完，自動擷取精準 prompt]
  📐 擷取到精準 prompt，自動進入 architect
```

按 `v`：ask（sonnet）修飾你的需求 → 自動擷取精準版本 → 直接帶進 architect。
全程不用手動貼上。

## Architect 銜接

architect session 結束後：

```
  📐 Architect session 結束。
  [Enter] 回 aider（載入上輪對話，sonnet）
     c   → 開新 code session（haiku 省錢）
     n   → 結束，之後再說
```

| 選項 | 交接介質 | 模型 | plan 保留 |
|---|---|---|---|
| Enter | aider chat history | sonnet | 完整 |
| c | git diff + repo state | haiku | 看得到結果，自己帶 context |
| n | 無（下次靠 UMB） | — | 要說 UMB |

## UMB（更新記憶）

```
🔨 Forge > UMB
  📝 快速更新 memory-bank（Enter 跳過）：
  現在在忙什麼？ > 認證模組快好了
  剛做了什麼決定、為什麼？ > 用strategy因為要加saml
  有新的規範或踩坑經驗？ > [Enter]

  [ask 修飾，去除歧義]

  📝 activeContext: 認證模組重構接近完成，已實作 Strategy Pattern 抽象層
  📝 decisionLog: 採用 Strategy Pattern，原因是未來需支援 SAML
  [Enter] 接受修飾版  n=用原始版
  > [Enter]
    ✅ activeContext.md 已更新
    ✅ decisionLog.md 已追加
```

你打粗略筆記 → ask 修飾成精準版 → 你確認 → Python 存。
LLM 只幫你想清楚，寫進磁碟的是你按 Enter 確認過的。

## 模型分工

```python
ARCHITECT_MODEL = "sonnet"    # 規劃（貴但準）
CODE_MODEL      = "haiku"     # 執行（照 plan 做，做錯有 auto-test 兜底）
ASK_MODEL       = "sonnet"    # 修飾 prompt / UMB 修飾（要準）
```

省錢組合範例：

```python
# DeepSeek
ARCHITECT_MODEL = "deepseek/deepseek-reasoner"
CODE_MODEL      = "deepseek/deepseek-chat"
ASK_MODEL       = "deepseek/deepseek-reasoner"

# 混搭
ARCHITECT_MODEL = "sonnet"
CODE_MODEL      = "haiku"
ASK_MODEL       = "sonnet"
```

## Memory Bank

```
memory-bank/
├── activeContext.md     ← 現在在忙什麼（UMB 覆寫）
├── progress.md          ← 做了什麼（forge 自動追加）
├── systemPatterns.md    ← 規範和踩坑（UMB 追加）
├── productContext.md    ← 產品背景
├── decisionLog.md       ← 決策紀錄（UMB 追加）
└── techContext.md       ← 技術棧
```

依路由注入不同深度：

| mode | 注入的檔案 | 原因 |
|---|---|---|
| code | activeContext + systemPatterns | 只要知道現在在幹嘛和規範 |
| ask | 全部 | 修飾 prompt / 確認意圖需要全貌 |
| architect | 全部 | 規劃需要完整視野 |

## Skills

```
skills/
├── api-patterns.md      ← 「API 一律加 retry + timeout」
└── db-conventions.md    ← 「migration 先備份」
```

所有 mode 自動注入 `skills/*.md`。Day 1 就該知道的規則放這裡。

提煉方式：`lessons` 指令分析 systemPatterns.md → 值得的寫進 skills/ → forge 自動注入。

## 自動護欄

| 護欄 | 觸發 | 動作 |
|---|---|---|
| lint | 偵測到 ruff/flake8/eslint | `--lint` 自動加 |
| test | 偵測到 pytest/npm test/make test | `--test-cmd` + `--auto-test`（改→測→修 全自動） |
| code 連續失敗 3 次 | return code ≠ 0 連續 3 次 | 停下來，建議 !ask 或 !architect |
| progress.md 膨脹 | 追加後超 100 行 | 提醒只保留最近 20 行 |
| memory 膨脹 | 啟動時檢查 | 具體瘦身指示 |
| .tmp 殘留 | 啟動時 | 自動清理 `.forge_*.tmp` |
| prompt cache | 每次 | `--cache-prompts` 省 token |

## 瘦身指引

啟動時自動檢查，膨脹時會告訴你怎麼修：

| 檔案 | 瘦身方式 |
|---|---|
| progress.md | 只保留最近 20 行，舊的刪掉（git log 有完整紀錄） |
| decisionLog.md | 已落實的決策搬進 skills/*.md，原文刪掉 |
| systemPatterns.md | 跑 lessons，提煉成 skill 後刪原文 |
| 其他 | 壓縮到只留當前相關的內容 |

## 切專案

```bash
cd project-a && python forge.py   # 用 project-a 的 memory-bank
cd project-b && python forge.py   # 用 project-b 的 memory-bank，完全隔離
```

不跨 repo 共享記憶。跨專案通用規則放 skills/。

## 不做的事

- 不讓 LLM 寫 memory（人寫，ask 修飾，人確認，Python 存）
- 不讓 LLM 做路由（Python if/else）
- 不跨 session 累積 context（每次用完即棄）
- 不用向量搜尋（memory-bank 控制在 4000 token 以內，全文注入更準）
- 不需要 Docker / PostgreSQL / 額外框架
