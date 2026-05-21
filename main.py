from __future__ import annotations

import argparse
import sys

from models.labels import label_names
from optimizer import explore_bracket, optimize, optimize_parallel
from output.export import export_csv, export_json
from output.radar import plot_radar
from output.terminal import print_explore_bracket, print_terminal
from runtime import apply_environment_settings, resolve_water_profile


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AeroPress 四向量最佳化系統 v5.8s")
    parser.add_argument("--brewer", default="xl", choices=["standard", "xl"])
    parser.add_argument(
        "--roast",
        required=True,
        choices=[
            "very_light",
            "light",
            "medium_light",
            "medium",
            "moderately_dark",
            "dark",
            "very_dark",
        ],
    )
    parser.add_argument(
        "--label",
        default=None,
        help="Sensory label (e.g. balanced / acid-forward / sweet-body / coarse-modern). "
             "Omit to run Channel B — Top-1 per label, side-by-side.",
    )
    parser.add_argument(
        "--explore",
        default=None,
        metavar="LABEL",
        help="Exploration mode: print a calibration bracket for LABEL — the "
             "optimum plus single-axis temp/dose offsets. Brew & rate the set "
             "to accumulate feedback with a usable gradient. Terminal output only.",
    )
    parser.add_argument("--preset", default=None)
    parser.add_argument("--gh", type=float, default=None, help="GH ppm")
    parser.add_argument("--kh", type=float, default=None, help="KH ppm")
    parser.add_argument("--mg-frac", type=float, default=None, help="mg fraction 0.0-1.0")
    parser.add_argument("--top", type=int, default=3)
    parser.add_argument("--output", default="terminal", choices=["terminal", "json", "csv"])
    parser.add_argument("--radar", action="store_true")
    parser.add_argument("--t-env", type=float, default=25.0, help="Env Temp C")
    parser.add_argument("--altitude", type=float, default=0.0, help="Altitude m")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    apply_environment_settings(args.t_env, args.altitude)

    water_gh, water_kh, water_mg_frac, source = resolve_water_profile(
        gh=args.gh, kh=args.kh, mg_frac=args.mg_frac, preset=args.preset,
    )
    if source == "default":
        print("未指定水質，使用預設 GH=50 / KH=30 / mg_frac=0.40。", file=sys.stderr)

    if args.explore:
        if args.explore not in label_names():
            print(f"未知 label '{args.explore}'。可用 labels: {label_names()}", file=sys.stderr)
            return 2
        bracket = explore_bracket(
            roast_code=args.roast,
            brewer_size=args.brewer,
            water_gh=water_gh,
            water_kh=water_kh,
            water_mg_frac=water_mg_frac,
            label=args.explore,
        )
        print_explore_bracket(bracket, args.roast, args.explore, water_gh, water_kh)
        return 0

    if args.label:
        if args.label not in label_names():
            print(f"未知 label '{args.label}'。可用 labels: {label_names()}", file=sys.stderr)
            return 2
        results = optimize(
            roast_code=args.roast,
            brewer_size=args.brewer,
            water_gh=water_gh,
            water_kh=water_kh,
            water_mg_frac=water_mg_frac,
            top_n=args.top,
            label=args.label,
        )
    else:
        results = optimize_parallel(
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
        # plot_radar expects flat list; flatten parallel mode
        flat = (
            [item for items in results.values() for item in items]
            if isinstance(results, dict) else results
        )
        plot_radar(flat)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
