#!/usr/bin/env python3
"""
Forge — Cline 的紀律管家

不做路由（你在 Cline 裡手動選 Plan/Act）。
只做 Cline 不會幫你做的事：記憶管理、膨脹警告、經驗提煉。
零 LLM 呼叫，零 token，純 Python。

用法：
  python forge.py          顯示狀態（health + lessons）
  python forge.py umb      更新記憶
  python forge.py init     初始化 memory-bank + skills
  python forge.py clean    清理殘留 .tmp
"""

import sys
import re
from datetime import datetime
from pathlib import Path

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

# 膨脹閾值
LINE_WARN = 100
LINE_CRIT = 200
TOKEN_WARN = 2000
TOKEN_CRIT = 4000

# ── init ──────────────────────────────────────────────────────

def cmd_init():
    """初始化 memory-bank + skills，已存在就跳過。"""
    MEMORY_DIR.mkdir(exist_ok=True)
    SKILLS_DIR.mkdir(exist_ok=True)
    for name in MEMORY_FILES:
        path = MEMORY_DIR / name
        if not path.exists():
            path.write_text("", encoding="utf-8")
            print(f"  ✅ 建立 {path}")
        else:
            print(f"  ⏭️  {path} 已存在")

    clinerules = Path(".clinerules")
    if not clinerules.exists():
        clinerules.write_text(
            "# Forge Rules for Cline\n\n"
            "1. 每次對話開始，讀取 memory-bank/ 和 skills/ 裡的所有 .md 檔案作為上下文。\n\n"
            "2. 收到模糊需求時，先用一段話複述你的理解（打算做什麼、影響範圍、假設），確認後再開始。\n\n"
            "3. 改完 code 後跑測試。測試通過才 commit。\n\n"
            "4. 不要在 memory-bank/ 檔案裡記錄程式碼細節（變數名、API 列表），那些交給 codebase 本身。只記高階意圖與決策原因。\n",
            encoding="utf-8",
        )
        print(f"  ✅ 建立 .clinerules")
    else:
        print(f"  ⏭️  .clinerules 已存在")

    print()
    print("  🎉 初始化完成。在 Cline 裡開始工作吧。")
    print("     大專案：先 Plan mode 規劃，再 Act mode 執行")
    print("     小專案：直接 Act mode")
    print("     做完後：python forge.py umb 記下決策")


# ── health ────────────────────────────────────────────────────

def cmd_health():
    """檢查 memory-bank 健康 + lessons 分析。啟動時一次看完。"""
    if not MEMORY_DIR.exists():
        print("  ⚠️  memory-bank/ 不存在。跑 python forge.py init")
        return

    # ── 膨脹檢查 ──
    total_tokens = 0
    bloated: list[str] = []
    print("  === Memory Bank 狀態 ===")
    print()
    for f in sorted(MEMORY_DIR.glob("*.md")):
        text = f.read_text(encoding="utf-8")
        lines = len(text.splitlines())
        tokens = len(text) // 4
        total_tokens += tokens
        if lines >= LINE_CRIT:
            print(f"  🔴 {f.name}: {lines} 行")
            bloated.append(f.name)
        elif lines >= LINE_WARN:
            print(f"  🟡 {f.name}: {lines} 行")
            bloated.append(f.name)
        else:
            print(f"  🟢 {f.name}: {lines} 行")

    print()
    if total_tokens >= TOKEN_CRIT:
        print(f"  🔴 總計約 {total_tokens} token — 嚴重膨脹")
    elif total_tokens >= TOKEN_WARN:
        print(f"  🟡 總計約 {total_tokens} token — 注意控制")
    else:
        print(f"  🟢 總計約 {total_tokens} token")

    if bloated:
        print()
        print("  🧹 瘦身建議：")
        if "progress.md" in bloated:
            print("     progress.md → 只保留最近 20 行（git log 有完整紀錄）")
        if "decisionLog.md" in bloated:
            print("     decisionLog.md → 已落實的決策搬進 skills/，原文刪掉")
        if "systemPatterns.md" in bloated:
            print("     systemPatterns.md → 跑 lessons，提煉成 skill 後刪原文")
        for f in bloated:
            if f not in ("progress.md", "decisionLog.md", "systemPatterns.md"):
                print(f"     {f} → 壓縮到只留當前相關的內容")

    # ── lessons ──
    _run_lessons()

    # ── skills 狀態 ──
    print()
    if SKILLS_DIR.is_dir():
        skills = sorted(SKILLS_DIR.glob("*.md"))
        if skills:
            print(f"  📁 Skills（自動注入所有 Cline 對話）：")
            for s in skills:
                print(f"     {s.name}")
        else:
            print("  📁 skills/ 是空的（值得 Day 1 知道的規則放這裡）")
    else:
        print("  📁 skills/ 不存在（建議：python forge.py init）")


def _run_lessons():
    """分析 systemPatterns.md。"""
    patterns_file = MEMORY_DIR / "systemPatterns.md"
    if not patterns_file.exists():
        return

    text = patterns_file.read_text(encoding="utf-8")
    if not text.strip():
        return

    words = re.findall(r"[a-zA-Z_-]{4,}", text)
    freq: dict[str, int] = {}
    for w in words:
        freq[w.lower()] = freq.get(w.lower(), 0) + 1
    repeated = sorted(((c, w) for w, c in freq.items() if c >= 2), reverse=True)

    print()
    print("  === Lessons（systemPatterns.md 分析）===")
    if repeated:
        print()
        print("  📊 重複關鍵詞：")
        for count, word in repeated[:10]:
            print(f"     {count}次: {word}")

    headings = [l.strip() for l in text.splitlines() if re.match(r"^#{1,3} ", l)]
    if headings:
        print()
        print("  📋 Pattern 標題：")
        for h in headings:
            print(f"     {h}")

    print()
    print("  💡 從頭重做這個專案，這條規則值不值得 Day 1 就知道？")
    print("     值得 → 寫進 skills/*.md，Cline 會透過 .clinerules 自動讀取")


# ── umb ───────────────────────────────────────────────────────

def cmd_umb():
    """更新記憶。三個問題，Enter 跳過，Python 直接寫。"""
    if not MEMORY_DIR.exists():
        print("  ⚠️  memory-bank/ 不存在。跑 python forge.py init")
        return

    print("  📝 更新 memory-bank（Enter 跳過）：")
    print("  💡 不確定怎麼寫？先在 Cline 裡問 AI 幫你整理再來。")
    print()
    try:
        ctx = input("  現在在忙什麼？ > ").strip()
        dec = input("  剛做了什麼決定、為什麼？ > ").strip()
        pat = input("  有新的規範或踩坑經驗？ > ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\n  取消")
        return

    if not any([ctx, dec, pat]):
        print("  （全部跳過）")
        return

    if ctx:
        with open(MEMORY_DIR / "activeContext.md", "w", encoding="utf-8") as f:
            f.write(f"# Active Context\n\n{ctx}\n")
        print("  ✅ activeContext.md 已更新")
    if dec:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        with open(MEMORY_DIR / "decisionLog.md", "a", encoding="utf-8") as f:
            f.write(f"- [{timestamp}] {dec}\n")
        print("  ✅ decisionLog.md 已追加")
    if pat:
        with open(MEMORY_DIR / "systemPatterns.md", "a", encoding="utf-8") as f:
            f.write(f"- {pat}\n")
        print("  ✅ systemPatterns.md 已追加")


# ── clean ─────────────────────────────────────────────────────

def cmd_clean():
    """清理殘留的 .tmp 檔案。"""
    count = 0
    for f in Path(".").glob("*.tmp"):
        f.unlink()
        count += 1
    if count:
        print(f"  🧹 清掉 {count} 個 .tmp 檔案")
    else:
        print("  ✅ 沒有殘留的 .tmp")


# ── 入口 ──────────────────────────────────────────────────────

COMMANDS = {
    "init":    cmd_init,
    "health":  cmd_health,
    "umb":     cmd_umb,
    "lessons": lambda: _run_lessons() if MEMORY_DIR.exists() else print("  ⚠️  memory-bank/ 不存在"),
    "clean":   cmd_clean,
}

def main():
    if len(sys.argv) < 2:
        # 沒參數 = 顯示狀態
        cmd_health()
        return

    cmd = sys.argv[1].lower()
    if cmd in COMMANDS:
        COMMANDS[cmd]()
    else:
        print(f"  ❌ 未知指令: {cmd}")
        print()
        print("  用法：")
        print("    python forge.py          狀態總覽")
        print("    python forge.py init     初始化 memory-bank + skills")
        print("    python forge.py umb      更新記憶")
        print("    python forge.py lessons  分析 systemPatterns")
        print("    python forge.py clean    清 .tmp")


if __name__ == "__main__":
    main()
