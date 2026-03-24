#!/usr/bin/env python3
"""
Forge — Aider 的確定性路由 wrapper

架構：Python if/else 做路由（0 token），Aider 做執行（用完即棄），memory-bank 住在磁碟。
哲學：LLM 是計算器不是員工。Python 不會幻覺。記憶不住在 LLM 腦子裡。

v5 — self-correct 閉環、信心路由、intent check、architect→code 銜接、
      強弱模型分工（architect/ask=sonnet, code=haiku）
"""

import shutil
import subprocess
import sys
import re
from datetime import datetime
from pathlib import Path

# ── 設定 ──────────────────────────────────────────────────────

MEMORY_DIR = Path("memory-bank")

# 各模式會讀的記憶檔案（由少到多）
MEMORY_BY_MODE: dict[str, list[str]] = {
    # ask：意圖確認，需要完整視野才能判斷 LLM 理解是否正確
    "ask": [
        "activeContext.md",
        "progress.md",
        "systemPatterns.md",
        "productContext.md",
        "decisionLog.md",
        "techContext.md",
    ],
    # code：當下脈絡 + 程式碼規範，不需要產品全貌
    "code": [
        "activeContext.md",
        "systemPatterns.md",
    ],
    # architect：需要完整視野，全部注入
    "architect": [
        "activeContext.md",
        "progress.md",
        "systemPatterns.md",
        "productContext.md",
        "decisionLog.md",
        "techContext.md",
    ],
}

# ── 模型設定 ──────────────────────────────────────────────────
# 三個角色三種成本，最大化分工效益
ARCHITECT_MODEL = "sonnet"       # 規劃用（貴但準）
CODE_MODEL      = "haiku"        # 執行用（照 plan 做，做錯有 auto-test 兜底）
ASK_MODEL       = "sonnet"       # 意圖確認用（審核 LLM 理解是否正確，需要強模型）
EDITOR_MODEL    = None           # architect 的 editor，None = aider 自動選

# ── Repo Map 精度 ────────────────────────────────────────────
# architect 需要全貌，給大 map；code 只要定位，用預設
MAP_TOKENS_BY_MODE: dict[str, int] = {
    "architect": 2048,   # 看全貌
    "code":      1024,   # aider 預設
    "ask":       1024,
}

# 扣除 code block 後，純描述字數超過這個才走 architect
LENGTH_THRESHOLD = 150

# 暫存 prompt 的路徑（避免 shell 跳脫問題）
PROMPT_TMP = Path(".forge_prompt.tmp")

# memory-bank 注入 token 警告閾值
MEMORY_TOKEN_WARN = 2000
MEMORY_TOKEN_CRIT = 4000

# ── 路由 signal 清單 ──────────────────────────────────────────

ARCHITECT_SIGNALS = [
    "架構", "設計", "重構", "規劃", "拆解", "新功能", "模組",
    "重新設計", "migration", "不確定怎麼",
    "refactor", "redesign", "architect", "design", "plan",
    "restructure", "migrate", "new feature", "module",
    "how should", "what approach",
]

ASK_SIGNALS = [
    "為什麼", "怎麼回事", "解釋", "什麼是", "差別是",
    "原因", "分析", "比較",
    "explain", "why does", "what is", "how does",
    "difference between", "analyze", "compare",
]

CODE_SIGNALS = [
    "typo", "修正", "加 log", "加上", "改成", "刪掉", "移除",
    "stage", "繼續", "接續", "從第",
    "rename", "fix", "add", "remove", "update", "change",
    "import", "lint", "format",
]

# 否定詞 pattern：比對「否定詞 + 最多 6 個字 + signal 起點」
_NEGATION = re.compile(r"(不|沒|非|不要|不用|無需|避免).{0,4}$")


def _has_signal_without_negation(text: str, signals: list[str]) -> bool:
    for s in signals:
        idx = text.find(s)
        if idx == -1:
            continue
        prefix = text[max(0, idx - 6): idx]
        if not _NEGATION.search(prefix):
            return True
    return False


# ── 路由（確定性，0 token）────────────────────────────────────

def route(message: str) -> tuple[str, str, str]:
    """
    確定性路由。回傳 (mode, confidence, reason)。

    confidence:
      "high" → 自動執行，不問使用者
      "low"  → 停下來讓使用者確認或秒改
    """
    msg = message.lower().strip()

    # 1. 手動 override
    if msg.startswith("!architect"): return "architect", "high", "手動指定"
    if msg.startswith("!code"):      return "code",      "high", "手動指定"
    if msg.startswith("!ask"):       return "ask",       "high", "手動指定"

    # 2. 報錯 log → 一定是解 bug，強制 code
    is_error = bool(re.search(
        r"(traceback \(most recent call last\):|error:|exception:|keyerror|at line \d+)",
        msg,
    ))
    if is_error:
        return "code", "high", "偵測到報錯 log"

    # 3. 扣除 code block 算真實描述字數
    text_only = re.sub(r"```.*?```", "", msg, flags=re.DOTALL).strip()
    real_len  = len(text_only)

    # 4. Signal 偵測（已排否定句）
    is_question   = msg.endswith("?") or msg.endswith("？")
    has_ask       = any(s in msg for s in ASK_SIGNALS)
    has_architect = _has_signal_without_negation(msg, ARCHITECT_SIGNALS)
    has_code      = _has_signal_without_negation(msg, CODE_SIGNALS)

    if (is_question or has_ask) and not has_architect and not has_code:
        return "ask", "high", "純問句"

    if has_architect and not has_code:
        return "architect", "high", "架構信號"

    if has_code and not has_architect:
        return "code", "high", "明確小改動"

    # 5. 混合 signal → 低信心，傾向 architect
    if has_architect and has_code:
        return "architect", "low", "混合信號，傾向架構"

    # 6. 純描述字數長 → 低信心
    if real_len > LENGTH_THRESHOLD:
        return "architect", "low", f"長訊息（{real_len} 字），無明確信號"

    # 7. 預設
    return "code", "low", "無明確信號，預設省 token"


# ── Memory Bank ───────────────────────────────────────────────

def get_read_args(mode: str) -> list[str]:
    args = []
    # memory-bank：依模式注入不同深度
    for name in MEMORY_BY_MODE.get(mode, []):
        path = MEMORY_DIR / name
        if path.exists():
            args.extend(["--read", str(path)])
    # skills：全模式注入（通用規則，Day 1 就該知道的）
    if SKILLS_DIR.is_dir():
        for skill in sorted(SKILLS_DIR.glob("*.md")):
            args.extend(["--read", str(skill)])
    return args


def check_memory_health():
    """啟動時檢查 memory-bank 行數 + 總 token 預估。膨脹時給具體指示。"""
    if not MEMORY_DIR.exists():
        return
    total_tokens = 0
    bloated: list[str] = []
    for f in MEMORY_DIR.glob("*.md"):
        text = f.read_text(encoding="utf-8")
        lines = len(text.splitlines())
        tokens = len(text) // 4
        total_tokens += tokens
        if lines >= 200:
            print(f"  🔴 {f.name}: {lines} 行 — 嚴重膨脹")
            bloated.append(f.name)
        elif lines >= 100:
            print(f"  🟡 {f.name}: {lines} 行 — 接近上限")
            bloated.append(f.name)
    if total_tokens >= MEMORY_TOKEN_CRIT:
        print(f"  🔴 memory-bank 總計約 {total_tokens} token — 嚴重膨脹")
    elif total_tokens >= MEMORY_TOKEN_WARN:
        print(f"  🟡 memory-bank 總計約 {total_tokens} token — 注意控制")
    if bloated:
        print()
        print("  🧹 瘦身建議：")
        if "progress.md" in bloated:
            print("     progress.md → 只保留最近 20 行，舊的刪掉（git log 有完整紀錄）")
        if "decisionLog.md" in bloated:
            print("     decisionLog.md → 已落實的決策搬進 skills/*.md，原文刪掉")
        if "systemPatterns.md" in bloated:
            print("     systemPatterns.md → 跑 lessons，提煉成 skill 後刪原文")
        remaining = [f for f in bloated if f not in ("progress.md", "decisionLog.md", "systemPatterns.md")]
        for f in remaining:
            print(f"     {f} → 壓縮到只留當前相關的內容")


SKILLS_DIR = Path("skills")

# Windows 子程序不一定繼承 PATH，預先解析 aider 完整路徑
_AIDER_BIN = shutil.which("aider") or "aider"


def _run_lessons():
    """分析 systemPatterns.md，找出值得提升為 skill 的 pattern。"""
    patterns_file = MEMORY_DIR / "systemPatterns.md"
    if not patterns_file.exists():
        print("  ⚠️ systemPatterns.md 不存在")
        return

    text = patterns_file.read_text(encoding="utf-8")

    # 關鍵詞頻率（≥2 次的英文詞）
    words = re.findall(r"[a-zA-Z_-]{4,}", text)
    freq: dict[str, int] = {}
    for w in words:
        w_lower = w.lower()
        freq[w_lower] = freq.get(w_lower, 0) + 1
    repeated = sorted(((c, w) for w, c in freq.items() if c >= 2), reverse=True)

    print("  === systemPatterns.md 分析 ===")
    print()
    if repeated:
        print("  📊 出現 ≥2 次的關鍵詞：")
        for count, word in repeated[:15]:
            print(f"     {count} 次: {word}")
    else:
        print("  📊 沒有重複關鍵詞")

    # Pattern 標題
    headings = [l.strip() for l in text.splitlines() if re.match(r"^#{1,3} ", l)]
    print()
    if headings:
        print("  📋 所有 pattern 標題：")
        for h in headings:
            print(f"     {h}")
    else:
        print("  📋 沒有 pattern 標題")

    # 現有 skills
    print()
    if SKILLS_DIR.is_dir():
        skills = list(SKILLS_DIR.glob("*.md"))
        if skills:
            print("  📁 目前已有的 skills：")
            for s in skills:
                print(f"     {s.name}")
        else:
            print("  📁 skills/ 是空的")
    else:
        print("  📁 skills/ 不存在（建議：mkdir skills）")

    print()
    print("  💡 判斷標準：從頭重做這個專案，這條規則值不值得 Day 1 就知道？")
    print("     值得 → 寫進 skills/*.md，forge 會自動 --read 注入")


def _git_head() -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        return r.stdout.strip()
    except subprocess.CalledProcessError:
        return ""


def _git_last_commit_msg() -> str:
    try:
        r = subprocess.run(
            ["git", "log", "-1", "--pretty=%s"],
            capture_output=True, text=True, check=True,
        )
        return r.stdout.strip()
    except subprocess.CalledProcessError:
        return ""


def update_progress(message: str, mode: str, head_before: str):
    if not MEMORY_DIR.exists():
        return

    progress = MEMORY_DIR / "progress.md"
    head_after = _git_head()
    if head_after and head_before and head_after != head_before:
        summary = _git_last_commit_msg() or message[:60]
    else:
        summary = message[:60].replace("\n", " ")
        if len(message) > 60:
            summary += "..."

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    line = f"- [{timestamp}] ({mode}) {summary}\n"
    with open(progress, "a", encoding="utf-8") as f:
        f.write(line)

    # 追加後檢查膨脹
    lines = len(progress.read_text(encoding="utf-8").splitlines())
    if lines >= 100:
        print(f"  🟡 progress.md 已 {lines} 行，建議只保留最近 20 行（git log 有完整紀錄）")


# ── Aider 環境偵測 ────────────────────────────────────────────

def _has_linter() -> bool:
    return any(shutil.which(t) for t in ("ruff", "flake8", "pylint", "eslint"))


def _get_test_cmd() -> str | None:
    if shutil.which("pytest") and (
        Path("pytest.ini").exists()
        or Path("pyproject.toml").exists()
        or Path("setup.cfg").exists()
        or Path("tests").is_dir()
    ):
        return "pytest --tb=long"
    if Path("package.json").exists() and shutil.which("npm"):
        return "npm test"
    if Path("Makefile").exists():
        try:
            content = Path("Makefile").read_text(encoding="utf-8")
            if re.search(r"^test:", content, re.MULTILINE):
                return "make test"
        except OSError:
            pass
    return None


def extract_file_args(message: str) -> list[str]:
    args = []
    pattern = re.compile(
        r"[\w./\-]+\.(?:py|js|ts|tsx|jsx|html|css|md|yaml|yml|toml|txt|json)"
    )
    seen: set[str] = set()
    for match in pattern.finditer(message):
        raw = match.group()
        if raw in seen:
            continue
        path = Path(raw)
        if path.exists():
            args.extend(["--file", str(path)])
            seen.add(raw)
    return args


# ── Aider 呼叫 ───────────────────────────────────────────────

def build_aider_cmd(message: str, mode: str, extra_flags: list[str] | None = None) -> list[str]:
    """組出 aider 指令。確定性，不靠 LLM 判斷。"""
    cmd = [_AIDER_BIN]


    # 模型選擇：三個角色三種成本
    if mode == "architect":
        cmd.extend(["--model", ARCHITECT_MODEL, "--architect"])
        if EDITOR_MODEL:
            cmd.extend(["--editor-model", EDITOR_MODEL])
    elif mode == "ask":
        cmd.extend(["--model", ASK_MODEL, "--chat-mode", "ask"])
    else:
        cmd.extend(["--model", CODE_MODEL])

    # Repo Map 精度依模式調整
    map_tokens = MAP_TOKENS_BY_MODE.get(mode, 1024)
    cmd.extend(["--map-tokens", str(map_tokens)])

    # Aider self-correct 閉環：lint + test + auto-test
    if mode in ("code", "architect"):
        if _has_linter():
            cmd.append("--lint")
        test_cmd = _get_test_cmd()
        if test_cmd:
            cmd.extend(["--test-cmd", test_cmd, "--auto-test"])

    # prompt cache（連續操作省 token，支援 Claude / DeepSeek）
    cmd.append("--cache-prompts")

    # Windows PowerShell 相容（避免 prompt toolkit 錯誤）
    cmd.append("--no-pretty")

    # 意圖/決策注入（精準依路由）
    cmd.extend(get_read_args(mode))

    # 從 message 抓出明確的檔案路徑
    cmd.extend(extract_file_args(message))

    # 非互動模式
    if message:
        clean = re.sub(r"^!(architect|code|ask)\s*", "", message).strip()
        PROMPT_TMP.write_text(clean, encoding="utf-8")
        cmd.extend(["--message-file", str(PROMPT_TMP)])
        # architect 不加 --yes：讓使用者看完 plan，再在 aider 裡 /code → go ahead
        # ask 不加 --yes：純對話，不會觸發修改確認
        # code 自動確認，用完即棄
        if mode == "code":
            cmd.append("--yes")

    if extra_flags:
        cmd.extend(extra_flags)

    return cmd


def run_aider(message: str, mode: str, extra_flags: list[str] | None = None) -> int:
    cmd = build_aider_cmd(message, mode, extra_flags)
    print(f"  → {' '.join(cmd[:6])}...")
    try:
        result = subprocess.run(cmd)
        return result.returncode
    finally:
        if PROMPT_TMP.exists():
            PROMPT_TMP.unlink()


# ── 主迴圈 ────────────────────────────────────────────────────

MODE_EMOJI = {"architect": "📐", "code": "⚡", "ask": "💬"}


def _confirm_mode(message: str, suggested: str, reason: str) -> tuple[str, str]:
    """
    低信心時停下來讓使用者確認。
    回傳 (mode, message)。mode 空字串 = 取消。
    v = ask 修飾 prompt → 自動接 architect。
    """
    print(f"  {MODE_EMOJI[suggested]} 建議: {suggested} — {reason}")
    print("  💡 不確定需求是否精準？按 v 讓 AI 幫你修飾 prompt 再進 architect")
    print("  [Enter] 繼續  v=修飾 prompt  a=architect  c=code  Ctrl+C 取消")
    try:
        ans = input("  > ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print("\n  取消")
        return "", message
    if ans == "v":
        print("  💬 ask — 修飾 prompt")
        refined = _run_intent_check(message)
        if refined:
            print(f"\n  📐 擷取到精準 prompt，自動進入 architect")
            return "architect", refined
        else:
            print(f"\n  ⚠️ 未擷取到精準 prompt，用原始需求進入 architect")
            return "architect", message
    if ans == "a": return "architect", message
    if ans == "c": return "code", message
    if ans == "q": return "ask", message
    return suggested, message


def _run_intent_check(message: str) -> str:
    """
    One-shot ask：LLM 修飾 prompt，自動擷取精準版本。
    回傳精準 prompt（擷取失敗回傳空字串，由呼叫端 fallback 原始訊息）。
    """
    clean = re.sub(r"^!(architect|code|ask)\s*", "", message).strip()
    intent = ("以下是使用者的原始需求。請幫忙：\n"
              "1. 釐清模糊的部分（如果有）\n"
              "2. 指出可能的假設或歧義\n"
              "3. 產出一段精準的描述，可以直接交給 architect 拆步驟\n"
              "不要開始規劃或寫 code。\n\n"
              "最後請把精準描述放在 <<<REFINED>>> 和 <<<END>>> 之間，"
              "方便系統自動擷取。\n\n" + clean)

    PROMPT_TMP.write_text(intent, encoding="utf-8")
    cmd = [_AIDER_BIN, "--model", ASK_MODEL, "--chat-mode", "ask",
           "--map-tokens", str(MAP_TOKENS_BY_MODE.get("ask", 1024)),
           "--no-pretty", "--cache-prompts", "--message-file", str(PROMPT_TMP), "--yes"]
    cmd.extend(get_read_args("ask"))

    # tee：使用者看得到，forge 也攔得到
    output_lines: list[str] = []
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        for line in proc.stdout:
            print(line, end="")
            output_lines.append(line)
        proc.wait()
    finally:
        PROMPT_TMP.unlink(missing_ok=True)

    # 擷取 <<<REFINED>>> ... <<<END>>> 之間的文字
    output = "".join(output_lines)
    # 去 ANSI escape codes
    clean_output = re.sub(r"\x1b\[[0-9;]*m", "", output)
    m = re.search(r"<<<REFINED>>>\s*(.+?)\s*<<<END>>>", clean_output, re.DOTALL)
    return m.group(1).strip() if m else ""


def _refine_umb(ctx: str, dec: str, pat: str) -> tuple[str, str, str] | None:
    """
    用 ask 修飾 UMB 內容，去除歧義。使用者確認後才寫入。
    回傳 (refined_ctx, refined_dec, refined_pat)，擷取失敗回傳 None。
    """
    parts = []
    if ctx: parts.append(f"activeContext: {ctx}")
    if dec: parts.append(f"decisionLog: {dec}")
    if pat: parts.append(f"systemPatterns: {pat}")
    if not parts:
        return None

    prompt = (
        "以下是開發者想記進 memory-bank 的筆記。請幫忙：\n"
        "1. 修飾成精準、無歧義的描述\n"
        "2. 不要改變原意，不要加入開發者沒提到的資訊\n"
        "3. 不要包含程式碼細節（變數名、API 列表），只記高階意圖\n\n"
        + "\n".join(parts) + "\n\n"
        "請用以下格式輸出（沒有內容的欄位留空）：\n"
        "<<<CTX>>>精準的 activeContext<<<END_CTX>>>\n"
        "<<<DEC>>>精準的 decisionLog<<<END_DEC>>>\n"
        "<<<PAT>>>精準的 systemPatterns<<<END_PAT>>>"
    )
    PROMPT_TMP.write_text(prompt, encoding="utf-8")
    cmd = [_AIDER_BIN, "--model", ASK_MODEL, "--chat-mode", "ask",
           "--map-tokens", str(MAP_TOKENS_BY_MODE.get("ask", 1024)),
           "--no-pretty", "--cache-prompts", "--message-file", str(PROMPT_TMP), "--yes"]
    cmd.extend(get_read_args("ask"))

    output_lines: list[str] = []
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        for line in proc.stdout:
            print(line, end="")
            output_lines.append(line)
        proc.wait()
    finally:
        PROMPT_TMP.unlink(missing_ok=True)

    raw = re.sub(r"\x1b\[[0-9;]*m", "", "".join(output_lines))
    r_ctx = _extract(raw, "<<<CTX>>>", "<<<END_CTX>>>") or ctx
    r_dec = _extract(raw, "<<<DEC>>>", "<<<END_DEC>>>") or dec
    r_pat = _extract(raw, "<<<PAT>>>", "<<<END_PAT>>>") or pat

    # 顯示修飾結果，讓使用者確認
    print()
    changed = False
    if ctx and r_ctx != ctx:
        print(f"  📝 activeContext: {r_ctx}")
        changed = True
    if dec and r_dec != dec:
        print(f"  📝 decisionLog: {r_dec}")
        changed = True
    if pat and r_pat != pat:
        print(f"  📝 systemPatterns: {r_pat}")
        changed = True

    if not changed:
        print("  （沒有修飾，用原始版本）")
        return None

    print("  [Enter] 接受修飾版  n=用原始版")
    try:
        ans = input("  > ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        return None
    if ans == "n":
        return None
    return r_ctx, r_dec, r_pat


def _extract(text: str, start: str, end: str) -> str:
    """擷取 start 和 end 標記之間的文字。"""
    m = re.search(re.escape(start) + r"\s*(.+?)\s*" + re.escape(end), text, re.DOTALL)
    return m.group(1).strip() if m else ""


def _cleanup_stale_tmp():
    """啟動時清理上一輪殘留的 .tmp，防止跨 session 污染。"""
    for f in Path(".").glob(".forge_*.tmp"):
        f.unlink(missing_ok=True)


def interactive():
    """互動模式：prompt loop，信心路由。"""
    _cleanup_stale_tmp()
    print("╔══════════════════════════════════════════╗")
    print("║  Forge v5 — Aider 確定性路由 wrapper     ║")
    print("║  !architect / !code / !ask  手動指定     ║")
    print("║  UMB 更新記憶  lessons 提煉經驗          ║")
    print("║  Ctrl+C 離開                             ║")
    print("╚══════════════════════════════════════════╝")
    print()

    check_memory_health()
    _run_lessons()
    print()

    code_fail_streak = 0

    while True:
        try:
            message = input("🔨 Forge > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n👋 掰")
            break

        if not message:
            continue
        if message.lower() in ("exit", "quit", "q"):
            print("👋 掰")
            break

        if message.upper() == "UMB":
            print("  📝 快速更新 memory-bank（Enter 跳過）：")
            try:
                ctx = input("  現在在忙什麼？ > ").strip()
                dec = input("  剛做了什麼決定、為什麼？ > ").strip()
                pat = input("  有新的規範或踩坑經驗？ > ").strip()

                if not any([ctx, dec, pat]):
                    print("  （全部跳過，沒有更新）")
                    continue

                # ask 修飾：去除歧義，但不改變原意
                refined = _refine_umb(ctx, dec, pat)
                if refined:
                    r_ctx, r_dec, r_pat = refined
                else:
                    r_ctx, r_dec, r_pat = ctx, dec, pat

                # 寫入
                if r_ctx:
                    with open(MEMORY_DIR / "activeContext.md", "w", encoding="utf-8") as f:
                        f.write(f"# Active Context\n\n{r_ctx}\n")
                    print("    ✅ activeContext.md 已更新")
                if r_dec:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
                    with open(MEMORY_DIR / "decisionLog.md", "a", encoding="utf-8") as f:
                        f.write(f"- [{timestamp}] {r_dec}\n")
                    print("    ✅ decisionLog.md 已追加")
                if r_pat:
                    with open(MEMORY_DIR / "systemPatterns.md", "a", encoding="utf-8") as f:
                        f.write(f"- {r_pat}\n")
                    print("    ✅ systemPatterns.md 已追加")
            except (KeyboardInterrupt, EOFError):
                print("\n  取消")
            continue

        if message.lower() == "lessons":
            _run_lessons()
            continue

        mode, confidence, reason = route(message)

        if confidence == "high":
            print(f"  {MODE_EMOJI[mode]} {mode} — {reason}")
        else:
            mode, message = _confirm_mode(message, mode, reason)
            if not mode:
                continue

        head_before = _git_head() if MEMORY_DIR.exists() else ""

        if mode == "architect":
            # architect 自動帶 message，使用者看完 plan 後可在 aider 裡 /code → go ahead → /exit
            print("  💡 規劃完 → /code → 'go ahead' → /exit 回到 Forge")
            run_aider(message, mode)
            update_progress(message, mode, head_before)

            print()
            print("  📐 Architect session 結束。")
            print("  [Enter] 回 aider（載入上輪對話，sonnet）")
            print("     c   → 開新 code session（haiku 省錢）")
            print("     n   → 結束，之後再說")
            try:
                ans = input("  > ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                ans = "n"

            if ans == "c":
                print("  ⚡ code session（haiku）")
                head2 = _git_head()
                run_aider("", "code")
                update_progress("(code continue)", "code", head2)
            elif ans == "n":
                print("  💡 有新的架構決策嗎？說 UMB 記下來，下次 session 才接得上")
            else:  # Enter → 回 aider
                print("  📐 回 aider（載入上輪對話）")
                head2 = _git_head()
                run_aider("", "architect", extra_flags=["--restore-chat-history"])
                update_progress("(architect continue)", "architect", head2)

        else:
            rc = run_aider(message, mode)
            update_progress(message, mode, head_before)
            if mode == "code":
                if rc != 0:
                    code_fail_streak += 1
                    if code_fail_streak >= 3:
                        print(f"  🔴 code 連續失敗 {code_fail_streak} 次，停下來。")
                        print("  💡 建議：!ask 分析原因，或 !architect 重新規劃")
                        code_fail_streak = 0
                    else:
                        print(f"  ⚠️ code 失敗（連續 {code_fail_streak}/3）")
                else:
                    code_fail_streak = 0
                    print("  💾 Done. 有新決策的話說 UMB。")
        print()


def oneshot(message: str):
    """單次模式：執行一個指令就退出。"""
    _cleanup_stale_tmp()
    check_memory_health()
    mode, confidence, reason = route(message)
    flag = "" if confidence == "high" else " ⚠️ 低信心"
    print(f"{MODE_EMOJI[mode]} {mode} — {reason}{flag}")
    head_before = _git_head() if MEMORY_DIR.exists() else ""
    run_aider(message, mode)
    update_progress(message, mode, head_before)


# ── 入口 ──────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) > 1:
        oneshot(" ".join(sys.argv[1:]))
    else:
        interactive()
