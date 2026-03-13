from __future__ import annotations

import argparse
import sys

from optimizer import optimize
from output.export import export_csv, export_json
from output.radar import plot_radar
from output.terminal import print_terminal
from runtime import apply_environment_settings, resolve_water_profile


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AeroPress 四向量最佳化系統 v5.8s")
    parser.add_argument("--brewer", default="xl", choices=["standard", "xl"])
    parser.add_argument("--roast", required=True, choices=["L+", "L", "LM", "M", "MD", "D"])
    parser.add_argument("--preset", default=None)
    parser.add_argument("--gh", type=float, default=None, help="手動 GH ppm（覆蓋 --preset）")
    parser.add_argument("--kh", type=float, default=None, help="手動 KH ppm（覆蓋 --preset）")
    parser.add_argument("--mg-frac", type=float, default=None, help="GH 中鎂離子比例 0.0–1.0")
    parser.add_argument("--top", type=int, default=3)
    parser.add_argument("--output", default="terminal", choices=["terminal", "json", "csv"])
    parser.add_argument("--radar", action="store_true")
    parser.add_argument("--t-env", type=float, default=25.0, help="環境室溫 °C（預設 25.0）")
    parser.add_argument("--tds-floor", type=float, default=None, help="褐水防禦底板 TDS%（預設 0.80）")
    parser.add_argument("--altitude", type=float, default=0.0, help="海拔高度 m（預設 0.0）")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    used_default_floor = apply_environment_settings(args.t_env, args.tds_floor, args.altitude)
    if used_default_floor:
        print(
            "\n提示：TDS_BROWN_WATER_FLOOR 使用預設值 0.80%，建議依個人口感以 --tds-floor 調整（說明：§15 第 28 點）\n",
            file=sys.stderr,
        )

    water_gh, water_kh, water_mg_frac, source = resolve_water_profile(
        gh=args.gh,
        kh=args.kh,
        mg_frac=args.mg_frac,
        preset=args.preset,
    )
    if source == "default":
        print("未指定水質，使用預設 GH=50 / KH=30 / mg_frac=0.40。", file=sys.stderr)

    results = optimize(
        roast_code=args.roast,
        brewer_size=args.brewer,
        water_gh=water_gh,
        water_kh=water_kh,
        water_mg_frac=water_mg_frac,
        top_n=args.top,
    )

    if args.output == "terminal":
        print_terminal(results, args.roast, water_gh, water_kh)
    elif args.output == "json":
        export_json(results, args.roast, water_gh, water_kh)
    elif args.output == "csv":
        export_csv(results, args.roast)

    if args.radar:
        plot_radar(results)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
