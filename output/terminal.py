from __future__ import annotations

import constants
from models import grind
from models.sensory import ATTRIBUTES

# attribute → Chinese label for the terminal table.
_ATTR_ZH = {
    "Sour": "酸",
    "Citrus": "柑橘",
    "Tea.floral": "花茶香",
    "Sweet": "甜",
    "Cereal": "穀物",
    "Thick.viscous": "醇厚",
    "Bitter": "苦",
    "Astringent": "澀",
    "Burnt": "焦",
    "Dark.chocolate": "黑巧",
}


def _fmt_mmss(seconds: float) -> str:
    total = int(round(seconds))
    return f"{total // 60}:{total % 60:02d}"


def _dial_segment(result: dict, grinder: str) -> str:
    """Grind segment of the recipe line. ZP6 stays byte-identical to the
    historical output; other grinders show their own converted setting with
    the model's ZP6 value kept in parentheses for traceability."""
    dial = result["dial"]
    if grinder == grind.NATIVE:
        return f"刻度 {dial:.1f}"
    label = grind.GRINDERS[grinder]["label"]
    return f"{label} {grind.format_dial(grinder, dial)}（ZP6 {dial:.1f}）"


def _print_single(result: dict, index: int, grinder: str = grind.NATIVE) -> None:
    rid = result.get("recipe_id", "")
    print(
        f"第 {index} 名   距目標 {result['distance']:.4f}"
        + (f"   recipe_id={rid}" if rid else "")
    )
    total_sec = result['steep_sec'] + 65  # 旋轉 5s + 靜置 30s + 穩定下壓 30s (固定，std/XL 相同)
    print(
        f"  {result['temp']:g}°C · {_dial_segment(result, grinder)} · "
        f"浸泡 {_fmt_mmss(result['steep_sec'])} · 總時長 {_fmt_mmss(total_sec)} · "
        f"豆量 {result['dose']:.1f}g"
    )
    print(
        f"  注水後插活塞 1cm → 浸泡 → 旋轉 5s → 靜置 30s → 穩定下壓 30s"
    )
    print(
        f"  預測 TDS {result['tds']:.3f}% · EY {result['ey']:.2f}% · "
        f"水量 {result['water_ml']}ml"
    )
    print("  屬性          預測  / IDEAL /    差")
    for attr in ATTRIBUTES:
        pred = result["attributes"][attr]
        ideal = result["ideal"][attr]
        delta = pred - ideal
        label = f"{_ATTR_ZH[attr]} {attr}"
        print(f"  {label:<20} {pred:6.3f} / {ideal:6.3f} / {delta:+.3f}")
    print()


def print_terminal(results, roast_code: str, temp: float, grinder: str = grind.NATIVE) -> None:
    """Print a flat Top-N list of Phase 10 sensory-optimized recipes,
    ranked by distance to the roast IDEAL (nearest first)."""
    if not results:
        print("無可用結果。")
        return

    roast_name = constants.ROAST_TABLE[roast_code]["name"]
    print("════════════════════════════════════════════════════════")
    print(" AeroPress 感官最佳化結果 — Phase 10（10 感官屬性）")
    print(f" 機型：{results[0]['brewer']}  |  烘焙度：{roast_name} ({roast_code})")
    print(f" 水溫：{temp:g}°C  |  排序：距該焙度 IDEAL（越小越近，非評分）")
    if grinder != grind.NATIVE:
        print(f" 磨豆機：{grind.GRINDERS[grinder]['label']}（刻度由 ZP6 換算，~ = 超出對照表外插）")
    print("════════════════════════════════════════════════════════\n")
    for i, r in enumerate(results, start=1):
        _print_single(r, i, grinder)
