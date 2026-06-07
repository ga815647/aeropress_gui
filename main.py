from __future__ import annotations

import argparse
import sys

import constants
from models import grind
from models.ideal import available_roasts
from optimizer import optimize
from output.export import export_csv, export_json
from output.radar import plot_radar
from output.terminal import print_terminal


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="AeroPress 感官最佳化系統 — Phase 10（6 感官軸）"
    )
    parser.add_argument("--brewer", default="xl", choices=["standard", "xl"])
    parser.add_argument(
        "--roast",
        required=True,
        choices=available_roasts(),
        help="烘焙度 — 須有 data/ideal.json 定義的 per-roast 感官 IDEAL。",
    )
    parser.add_argument(
        "--temp",
        type=float,
        default=None,
        help="沖煮水溫 °C。省略 → 該焙度的慣例預設（constants.DEFAULT_TEMP）。",
    )
    parser.add_argument("--top", type=int, default=3)
    parser.add_argument(
        "--grinder",
        default=grind.NATIVE,
        choices=grind.supported(),
        help="顯示用磨豆機刻度單位。模型一律在 ZP6 軸上搜尋；非 ZP6 會換算顯示"
        "（同時保留 ZP6 原值以利溯源）。預設 zp6。",
    )
    parser.add_argument("--output", default="terminal", choices=["terminal", "json", "csv"])
    parser.add_argument("--radar", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    temp = args.temp if args.temp is not None else constants.DEFAULT_TEMP[args.roast]
    if args.temp is None:
        print(f"未指定水溫，使用 {args.roast} 慣例預設 {temp:g}°C。", file=sys.stderr)

    results = optimize(
        roast_code=args.roast,
        brewer_size=args.brewer,
        temp=temp,
        top_n=args.top,
    )

    if args.output == "terminal":
        print_terminal(results, args.roast, temp, grinder=args.grinder)
    elif args.output == "json":
        export_json(results, args.roast, temp, grinder=args.grinder)
    elif args.output == "csv":
        export_csv(results, args.roast, grinder=args.grinder)

    if args.radar:
        plot_radar(results)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
