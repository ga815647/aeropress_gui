"""
Hoffman 錨點驗證腳本
每次口感矯正（修改 constants.py）後執行，確認模型未偏離 Hoffman 實測基準。

Hoffman Ultimate AeroPress Recipe（標準版，第三方實測）：
  研磨：4 EK43 / 450–600µm → ZP6 等效 dial ≈ 4.3
  水溫：208°F = 97.8°C
  浸泡：2:00 旋轉 → 2:30 開始壓（模型 steep = 135s 或 150s）
  TDS ：1.23%（稍粗版）→ Hoffman 原版預估 1.25–1.27%
  EY  ：19.9%（由 TDS=1.23%, brew=178g, dose=11g 反推）
"""

import sys
from optimizer import optimize

# ── 錨點定義 ──────────────────────────────────────────────────────────────────
ANCHOR = {
    "roast":      "light",
    "brewer":     "xl",
    "water_gh":   50,
    "water_kh":   30,
    # Top 3 整體驗證範圍
    "tds_lo":     1.20,
    "tds_hi":     1.34,
    "ey_min":     16.0,   # 防欠萃底線（短浸泡可低至 17%，不應低於 16%）
    "dial_lo":    3.8,
    "dial_hi":    4.8,
    "score_min":  95.0,
    # Hoffman 配方特定驗證（Top 10 中含 135s 或 150s 時）
    "steep_ok":   {135, 150},
    "hoffman_ey_lo":  18.0,  # Hoffman 長浸泡 EY 必須 >= 18%
    "hoffman_ey_hi":  22.0,
}


def _fmt(ok: bool) -> str:
    return "OK  " if ok else "FAIL"


def run_anchor_check(verbose: bool = True) -> bool:
    results = optimize(
        ANCHOR["roast"],
        brewer_size=ANCHOR["brewer"],
        water_gh=ANCHOR["water_gh"],
        water_kh=ANCHOR["water_kh"],
        top_n=10,
    )

    if not results:
        print("FAIL: optimizer 返回空結果")
        return False

    top3 = results[:3]
    top10 = results[:10]

    # 1. 分數閾值
    top1_score = top3[0]["score"]
    score_ok = top1_score >= ANCHOR["score_min"]

    # 2. TDS 範圍（Top 3 都必須在範圍內）
    tds_ok = all(ANCHOR["tds_lo"] <= r["tds"] <= ANCHOR["tds_hi"] for r in top3)

    # 3. EY 最低底線（Top 3 不得低於 16%，防止模型推薦欠萃配方）
    ey_ok = all(r["ey"] >= ANCHOR["ey_min"] for r in top3)

    # 4. Dial 範圍（Top 3）
    dial_ok = all(ANCHOR["dial_lo"] <= r["dial"] <= ANCHOR["dial_hi"] for r in top3)

    # 5. Hoffman steep（135s 或 150s 必須在 Top 10 內，且 EY 需在合理範圍）
    top10_steeps = {r["steep_sec"] for r in top10}
    hoffman_results = [r for r in top10 if r["steep_sec"] in ANCHOR["steep_ok"]]
    steep_ok = bool(hoffman_results)
    hoffman_ey_ok = all(
        ANCHOR["hoffman_ey_lo"] <= r["ey"] <= ANCHOR["hoffman_ey_hi"]
        for r in hoffman_results
    ) if hoffman_results else False

    all_pass = score_ok and tds_ok and ey_ok and dial_ok and steep_ok and hoffman_ey_ok

    if verbose:
        print("=" * 55)
        print("Hoffman anchor check (light / XL / GH50 KH30)")
        print("=" * 55)
        print("\nTop 3:")
        for i, r in enumerate(top3):
            print(f"  #{i+1}: dial={r['dial']}, steep={r['steep_sec']}s, "
                  f"temp={r['temp']}C, TDS={r['tds']:.3f}%, "
                  f"EY={r['ey']:.1f}%, score={r['score']}")

        hoffman_steep_found = sorted(top10_steeps & ANCHOR["steep_ok"])
        print(f"\nHoffman steep ({sorted(ANCHOR['steep_ok'])}s) in Top 10: "
              f"{hoffman_steep_found if hoffman_steep_found else 'NONE'}")
        if hoffman_results:
            for r in hoffman_results:
                print(f"  steep={r['steep_sec']}s: EY={r['ey']:.1f}%, TDS={r['tds']:.3f}%")

        print(f"\nChecks:")
        print(f"  {_fmt(score_ok)}  Top1 score {top1_score} >= {ANCHOR['score_min']}")
        print(f"  {_fmt(tds_ok)}  Top3 TDS in [{ANCHOR['tds_lo']}, {ANCHOR['tds_hi']}]%")
        print(f"  {_fmt(ey_ok)}  Top3 EY >= {ANCHOR['ey_min']}% (no under-extraction)")
        print(f"  {_fmt(dial_ok)}  Top3 dial in [{ANCHOR['dial_lo']}, {ANCHOR['dial_hi']}]")
        print(f"  {_fmt(steep_ok)}  Hoffman steep in Top 10")
        print(f"  {_fmt(hoffman_ey_ok)}  Hoffman steep EY in [{ANCHOR['hoffman_ey_lo']}, {ANCHOR['hoffman_ey_hi']}]%")

        print(f"\n{'[ ALL PASS ]' if all_pass else '[ FAIL - check constants.py ]'}")
        print("=" * 55)

    return all_pass


if __name__ == "__main__":
    ok = run_anchor_check(verbose=True)
    sys.exit(0 if ok else 1)
