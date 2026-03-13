from __future__ import annotations

import constants
from models.scoring import build_ideal_abs, compute_actual_abs


def _fmt_mmss(seconds: float) -> str:
    total = int(round(seconds))
    return f"{total // 60}:{total % 60:02d}"


def _describe_flavor(actual_abs: dict) -> str:
    ordered = sorted(actual_abs.items(), key=lambda item: item[1], reverse=True)
    mapping = {"AC": "酸質", "SW": "甜感", "PS": "醇厚", "CA": "苦感", "CGA": "澀感", "MEL": "焦糖/烘焙感"}
    return f"主導輪廓偏向 {mapping[ordered[0][0]]} 與 {mapping[ordered[1][0]]}。"


def print_terminal(results: list[dict], roast_code: str, water_gh: float, water_kh: float) -> None:
    if not results:
        print("無可用結果。")
        return

    roast_name = constants.ROAST_TABLE[roast_code]["name"]
    print("════════════════════════════════════════════════════════")
    print(" AeroPress 四向量最佳化結果（Hoffman 法）")
    print(f" 機型：{results[0]['brewer']}  |  烘焙度：{roast_name} ({roast_code})")
    print(f" 水質：GH {water_gh:g} ppm  /  KH {water_kh:g} ppm")
    print("════════════════════════════════════════════════════════")
    print()

    for index, result in enumerate(results, start=1):
        actual_abs = compute_actual_abs(result["compounds"], result["tds"])
        ideal_abs = build_ideal_abs(roast_code, result["tds"])
        swirl_mult = 1.0 + constants.SWIRL_CONVECTION_BASE * (constants.SWIRL_DOSE_REF / result["dose"])
        actual_ac_sw = actual_abs["AC"] / max(actual_abs["SW"], 1e-8)
        ideal_ac_sw = ideal_abs["AC"] / max(ideal_abs["SW"], 1e-8)
        actual_ps_bitter = actual_abs["PS"] / max(
            actual_abs["CA"] + actual_abs["CGA"] + actual_abs["MEL"] * constants.MEL_BITTER_COEFF[roast_code],
            1e-8,
        )
        ideal_ps_bitter = ideal_abs["PS"] / max(
            ideal_abs["CA"] + ideal_abs["CGA"] + ideal_abs["MEL"] * constants.MEL_BITTER_COEFF[roast_code],
            1e-8,
        )

        print(f"第 {index} 名  風味評分：{result['score']:.1f} / 100")
        print(
            f"  水溫 {result['temp']}°C → 漿體起始 {result['t_slurry']:.1f}°C  |  "
            f"刻度 {result['dial']:.1f}（細粉率 {result['fines_ratio'] * 100:.1f}%）"
        )
        print(
            f"  被動浸泡 {_fmt_mmss(result['steep_sec'])} → 動力學等效 {_fmt_mmss(result['t_kinetic'])}"
            f"（含 Swirl ×{swirl_mult:.2f}）  |  豆量 {result['dose']:.1f}g"
        )
        print(f"  EY {result['ey']:.3f}%  |  實際 TDS {result['tds']:.4f}%  |  截留係數 {result['retention']:.2f} g/g")
        print()
        print("  ── Hoffman 沖煮流程 ─────────────────────────────────────")
        print(f"  T=0:00        注入 {result['water_ml']}ml 熱水（{result['temp']}°C）；正置，不預熱機身、不潤濕濾紙")
        print(f"  T=0:00        立刻插入活塞 1cm，開始浸泡 {_fmt_mmss(result['steep_sec'])}")
        print(f"  T={_fmt_mmss(result['steep_sec'])}        被動浸泡結束，輕柔旋轉 {result['swirl_sec']} 秒（Swirl）")
        print(f"  T={_fmt_mmss(result['steep_sec'] + result['swirl_sec'])}        靜置 {result['swirl_wait_sec']} 秒等粉渣沉底")
        print(f"  T={_fmt_mmss(result['steep_sec'] + result['swirl_sec'] + result['swirl_wait_sec'])}        緩慢下壓（{result['press_sec']} 秒），壓到底")
        print(f"  全程接觸時間：{result['total_contact_sec']} 秒（{_fmt_mmss(result['total_contact_sec'])}）")
        print()
        print("  物質絕對強度（raw × TDS 正規化後）：")
        print(f"  酸(AC) {actual_abs['AC']:.4f}  甜(SW) {actual_abs['SW']:.4f}  醇(PS) {actual_abs['PS']:.4f}")
        print(f"  苦(CA) {actual_abs['CA']:.4f}  澀(CGA) {actual_abs['CGA']:.4f}  焦/Body(MEL) {actual_abs['MEL']:.4f}")
        print(f"  甜酸比（實際）{actual_ac_sw:.2f}  |  理想 {ideal_ac_sw:.2f}")
        print(f"  醇苦比（實際）{actual_ps_bitter:.2f}  |  理想 {ideal_ps_bitter:.2f}")
        print(f"  說明：{_describe_flavor(actual_abs)}")
        print()
