#!/usr/bin/env python3
"""
Forge MCP Server — 讓 Cline 直接呼叫 forge 功能

零 LLM 呼叫。所有 tool 都是純 Python 讀寫磁碟。

安裝：pip install mcp
啟動：在 Cline MCP 設定裡加這個 server（見 README）
"""

import re
from datetime import datetime
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("forge", instructions="Forge memory-bank 管理工具。純 Python，零 LLM。")

# ── 設定 ──────────────────────────────────────────────────────

MEMORY_DIR = Path("memory-bank")
SKILLS_DIR = Path("skills")

MEMORY_FILES = [
    "activeContext.md",
    "progress.md",
    "systemPatterns.md",
    "productContext.md",
    "decisionLog.md",
    "techContext.md",
]

LINE_WARN = 100
LINE_CRIT = 200
TOKEN_WARN = 2000
TOKEN_CRIT = 4000


# ── Tools ─────────────────────────────────────────────────────


@mcp.tool()
def forge_health() -> str:
    """檢查 memory-bank 健康狀態。回傳膨脹警告和瘦身建議。
    開對話時呼叫一次，掌握記憶狀態。"""

    lines_out: list[str] = ["=== 設定檢查 ===", ""]

    # ── Setup Check ──
    setup_ok = True
    
    if not MEMORY_DIR.exists():
        lines_out.append("❌ memory-bank/ 不存在 → 請呼叫 forge_init")
        setup_ok = False
    else:
        lines_out.append("✅ memory-bank/ 存在")
        missing_files = [f for f in MEMORY_FILES if not (MEMORY_DIR / f).exists()]
        if missing_files:
            lines_out.append(f"❌ 缺少檔案：{', '.join(missing_files)} → 請呼叫 forge_init")
            setup_ok = False
        else:
            lines_out.append("✅ 6 個記憶檔案完整")

    if not Path(".clinerules").exists():
        lines_out.append("❌ .clinerules 不存在 → 請呼叫 forge_init")
        setup_ok = False
    else:
        lines_out.append("✅ .clinerules 存在")

    if not SKILLS_DIR.is_dir():
        lines_out.append("❌ skills/ 不存在 → 請呼叫 forge_init")
        setup_ok = False
    else:
        lines_out.append("✅ skills/ 存在")

    lines_out.append("")
    if not setup_ok:
        lines_out.append("⚠️ 提醒：確認 Cline MCP 設定有加 autoApprove：")
        lines_out.append('   "autoApprove": ["forge_health", "forge_umb", "forge_lessons", "forge_clean"]')
        lines_out.append("")
        lines_out.append("❗ 請先完成以上設定再開始工作。")
        return "\n".join(lines_out)
    else:
        lines_out.append("✅ 所有設定完成")
        lines_out.append("")

    if not MEMORY_DIR.exists():
        return "⚠️ memory-bank/ 不存在。請呼叫 forge_init"

    lines_out.append("=== Memory Bank 狀態 ===")
    lines_out.append("")
    total_tokens = 0
    bloated: list[str] = []

    for f in sorted(MEMORY_DIR.glob("*.md")):
        text = f.read_text(encoding="utf-8")
        lines = len(text.splitlines())
        tokens = len(text) // 4
        total_tokens += tokens

        if lines >= LINE_CRIT:
            lines_out.append(f"🔴 {f.name}: {lines} 行")
            bloated.append(f.name)
        elif lines >= LINE_WARN:
            lines_out.append(f"🟡 {f.name}: {lines} 行")
            bloated.append(f.name)
        else:
            lines_out.append(f"🟢 {f.name}: {lines} 行")

    lines_out.append("")
    if total_tokens >= TOKEN_CRIT:
        lines_out.append(f"🔴 總計約 {total_tokens} token — 嚴重膨脹")
    elif total_tokens >= TOKEN_WARN:
        lines_out.append(f"🟡 總計約 {total_tokens} token — 注意控制")
    else:
        lines_out.append(f"🟢 總計約 {total_tokens} token")

    if bloated:
        lines_out.append("")
        lines_out.append("🧹 瘦身建議：")
        
        # auto-trim 的檔案
        if "progress.md" in bloated:
            lines_out.append("  progress.md → 自動裁剪到 20 行（無需手動）")
        if "decisionLog.md" in bloated:
            lines_out.append("  decisionLog.md → 自動裁剪到 50 行（無需手動）")
        
        # 需要手動介入的檔案
        manual_bloated = [f for f in bloated if f not in ("progress.md", "decisionLog.md")]
        if manual_bloated:
            lines_out.append("")
            lines_out.append("⚠️ 需要手動介入：")
            if "systemPatterns.md" in manual_bloated:
                lines_out.append("  systemPatterns.md → 跑 forge_lessons，提煉成 skill")
            for f in manual_bloated:
                if f != "systemPatterns.md":
                    lines_out.append(f"  {f} → 壓縮到只留當前相關內容")

    # skills 狀態
    lines_out.append("")
    if SKILLS_DIR.is_dir():
        skills = sorted(SKILLS_DIR.glob("*.md"))
        if skills:
            lines_out.append("📁 Skills：")
            for s in skills:
                lines_out.append(f"  {s.name}")
        else:
            lines_out.append("📁 skills/ 是空的")
    else:
        lines_out.append("📁 skills/ 不存在")

    return "\n".join(lines_out)


@mcp.tool()
def forge_lessons() -> str:
    """分析 systemPatterns.md，找出重複關鍵詞和 pattern 標題。
    用來判斷哪些經驗值得提煉成 skill。"""

    patterns_file = MEMORY_DIR / "systemPatterns.md"
    if not patterns_file.exists():
        return "⚠️ systemPatterns.md 不存在"

    text = patterns_file.read_text(encoding="utf-8")
    if not text.strip():
        return "systemPatterns.md 是空的"

    lines_out: list[str] = ["=== Lessons 分析 ==="]

    # 重複關鍵詞
    words = re.findall(r"[a-zA-Z_-]{4,}", text)
    freq: dict[str, int] = {}
    for w in words:
        freq[w.lower()] = freq.get(w.lower(), 0) + 1
    repeated = sorted(((c, w) for w, c in freq.items() if c >= 2), reverse=True)

    if repeated:
        lines_out.append("")
        lines_out.append("📊 重複關鍵詞：")
        for count, word in repeated[:10]:
            lines_out.append(f"  {count}次: {word}")

    # Pattern 標題
    headings = [l.strip() for l in text.splitlines() if re.match(r"^#{1,3} ", l)]
    if headings:
        lines_out.append("")
        lines_out.append("📋 Pattern 標題：")
        for h in headings:
            lines_out.append(f"  {h}")

    lines_out.append("")
    lines_out.append("💡 從頭重做這個專案，這條規則值不值得 Day 1 就知道？")
    lines_out.append("  值得 → 寫進 skills/*.md")

    return "\n".join(lines_out)


@mcp.tool()
def forge_umb(
    context: str = "",
    decision: str = "",
    pattern: str = "",
) -> str:
    """更新 memory-bank。三個欄位都是 optional，空字串就跳過。

    重要：呼叫前先跟使用者確認要存什麼。不要自己編內容。
    建議流程：你先用一段話總結改動，使用者確認後再呼叫這個 tool。

    Args:
        context: 現在在忙什麼（覆寫 activeContext.md）
        decision: 剛做了什麼決定、為什麼（追加到 decisionLog.md）
        pattern: 新的規範或踩坑經驗（追加到 systemPatterns.md）
    """

    if not MEMORY_DIR.exists():
        return "⚠️ memory-bank/ 不存在。請呼叫 forge_init"

    if not any([context, decision, pattern]):
        return "（全部為空，未更新）"

    results: list[str] = []

    if context:
        (MEMORY_DIR / "activeContext.md").write_text(
            f"# Active Context\n\n{context}\n", encoding="utf-8"
        )
        results.append("✅ activeContext.md 已更新")

    if decision:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        with open(MEMORY_DIR / "decisionLog.md", "a", encoding="utf-8") as f:
            f.write(f"- [{timestamp}] {decision}\n")
        results.append("✅ decisionLog.md 已追加")
        
        # Auto-trim decisionLog.md 到 50 行
        decision_file = MEMORY_DIR / "decisionLog.md"
        text = decision_file.read_text(encoding="utf-8")
        lines = text.splitlines(keepends=True)
        if len(lines) > 50:
            trimmed = "".join(lines[-50:])
            decision_file.write_text(trimmed, encoding="utf-8")
            results.append("🔄 decisionLog.md 已自動裁剪到 50 行")

    if pattern:
        with open(MEMORY_DIR / "systemPatterns.md", "a", encoding="utf-8") as f:
            f.write(f"- {pattern}\n")
        results.append("✅ systemPatterns.md 已追加")

    return "\n".join(results)


@mcp.tool()
def forge_init() -> str:
    """初始化 memory-bank + skills + .clinerules。
    已存在的檔案會跳過。
    第一次使用時呼叫一次。"""

    MEMORY_DIR.mkdir(exist_ok=True)
    SKILLS_DIR.mkdir(exist_ok=True)

    results: list[str] = []

    for name in MEMORY_FILES:
        path = MEMORY_DIR / name
        if not path.exists():
            path.write_text("", encoding="utf-8")
            results.append(f"✅ 建立 {path}")
        else:
            results.append(f"⏭️  {path} 已存在")

    clinerules = Path(".clinerules")
    if not clinerules.exists():
        clinerules.write_text(
            "# Forge Rules for Cline\n\n"
            "1. 每次對話開始，呼叫 forge_health 檢查 memory-bank 狀態。讀取 memory-bank/ 和 skills/ 裡的所有 .md 檔案作為上下文。\n\n"
            "2. 收到模糊需求時，先用一段話複述你的理解（打算做什麼、影響範圍、假設），確認後再開始。\n\n"
            "3. 改完 code 後立即執行測試指令（pytest / npm test / make test）。不要只回報「已完成」——要實際跑測試並貼出結果。測試通過才 commit。\n\n"
            "4. 不要在 memory-bank/ 檔案裡記錄程式碼細節（變數名、API 列表），那些交給 codebase 本身。只記高階意圖與決策原因。\n\n"
            "5. commit 後，直接呼叫 forge_umb 存入 context 和 decision。不需等使用者確認。\n"
            "   只記高階意圖，不記程式碼細節。forge_umb 會自動裁剪膨脹的檔案。\n\n"
            "6. 看到 memory-bank 膨脹警告（🟡 或 🔴）時，主動建議瘦身方案，並協助使用者提煉成 skill。\n",
            encoding="utf-8",
        )
        results.append("✅ 建立 .clinerules（B+ 自動記憶版本）")
    else:
        results.append("⏭️  .clinerules 已存在")

    results.append("")
    results.append("🎉 初始化完成。Cline 已準備好使用 Forge MCP。")

    return "\n".join(results)


@mcp.tool()
def forge_clean() -> str:
    """清理殘留的 .tmp 檔案。"""

    count = 0
    for f in Path(".").glob("*.tmp"):
        f.unlink()
        count += 1

    if count:
        return f"🧹 清掉 {count} 個 .tmp 檔案"
    return "✅ 沒有殘留的 .tmp"


# ── 啟動 ──────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="stdio")
