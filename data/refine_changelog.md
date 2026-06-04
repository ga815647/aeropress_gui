# Refine changelog — Claude's model edits

Phase 11 tier-3 intervention log — see
[`docs/PHASE10_STEP6_FEEDBACK_LOOP.md`](../docs/PHASE10_STEP6_FEEDBACK_LOOP.md)
§6 discipline 3 ("每筆 Claude 改動留痕、可回退、使用者看得懂").

Whenever Claude changes a **model artefact** in response to feedback — the
per-roast IDEAL in [`data/ideal.json`](ideal.json), a coefficient in
[`models/sensory.py`](../models/sensory.py), a Layer 1 prior, a distance weight —
it appends **one line** here. Each entry is traceable, revertible, and readable.

What does **not** belong here:

- The loop's own automatic champion updates — those live in
  `data/loop_state.json` (per-cycle `history`). The loop running is not a
  "Claude change".
- Code refactors / new features with no model-behaviour change.

## Format

One entry per change:

```
YYYY-MM-DD | <file> | <what changed> | why: <feedback pattern> | revert: <how>
```

- **what changed** — the concrete edit (`ideal.json medium IDEAL Sour 0.39→0.36`).
- **why** — the feedback pattern that justified it (cite a flag, a run of
  comments, or a repeated direction-error — never a single noisy cup, §6
  discipline 2).
- **revert** — how to undo it (the prior value, or the commit).

## Entries

<!-- Append below this line, newest last. -->

2026-05-22 | (none) | Phase 11 loop engine landed; changelog file created | why: scaffolding, no model change | revert: n/a
2026-05-28 | models/layer1.py | GAMMA (grind→rate) 0.32→0.5 | why: user reported coarse+long brews taste thin while fine+short tastes too thick; model ranked them backwards (coarse+long line7 TDS 1.238 ≥ fine champion 1.213) — grind under-rated, long steep wrongly compensated for coarse. New value reproduces the body ordering of 4 logged light cups (champion>line10>line9>line7). Anchor-safe: DIAL_REF term=exp(0), Hoffman TDS 1.23 unchanged. | revert: set GAMMA back to 0.32 in models/layer1.py AND restore light ideal/anchor_brew below
2026-05-28 | data/ideal.json (light) | re-derived light IDEAL + anchor_brew under new GAMMA: anchor_brew tds 1.2081→1.2524 / ey 17.0592→17.692; IDEAL shifted +0.0106 RMS (+Bitter/Burnt/Dark.choc, −Tea.floral/Sweet) | why: forced consistency after GAMMA change — light IDEAL = predict_attributes(tim ⭐4 recipe); new physics makes that recipe extract more, so the model's estimate of the cup moves (not a preference change). Restores tim bracket (star4=0 nearest). | revert: restore prior light ideal {Sour 0.4359, Citrus 0.2742, Tea.floral 0.2744, Sweet 0.2263, Cereal 0.1413, Thick.viscous 0.0436, Bitter 0.2310, Astringent 0.1113, Burnt 0.0429, Dark.chocolate 0.0884} + anchor_brew tds 1.2081/ey 17.0592 (paired with GAMMA revert)
2026-06-02 | data/ideal.json (light) + diagnose_anchor.py + tests/test_optimizer.py | re-anchored light IDEAL from tim ⭐4 archetype to Hoffman 'Brewing for Balance' archetype: anchor_brew tds 1.2524→1.2297 / ey 17.692→19.10 / dial 3.7→4.3; IDEAL shifted RMS 0.0130 (Sour −0.032, Citrus −0.019, Astringent −0.012, others small) | why: user judged the tim-anchored champion (3.6/60/25/98°C) consistently uninspired across multiple cycles ("no aroma, uninteresting"); after side-by-side debate user chose to set the light target to Hoffman's canonical 'balanced' recipe scaled to XL (dial 4.3 / 120s / 23g / 98°C — closer in archetype to user's medium_light ⭐5 cups). diagnose_anchor.py: tim bracket retired (tim no longer the light reference), replaced with light good/over/under discrimination check. test_optimizer.py::test_roast_method_emerges: removed dial-finer-than-dark assertion (no longer holds under Hoffman archetype which uses moderate grind); kept steep-shorter-than-dark. 13/13 diagnose + 89 pytest pass. | revert: restore prior light ideal {Sour 0.4458, Citrus 0.2727, Tea.floral 0.2652, Sweet 0.2161, Cereal 0.1373, Thick.viscous 0.05, Bitter 0.2512, Astringent 0.1136, Burnt 0.0572, Dark.chocolate 0.1011} + anchor_brew tds 1.2524/ey 17.692/dial 3.7 + restore tim bracket in diagnose + restore dial assertion in test
2026-06-03 | models/layer1.py | ALPHA (temp→rate) 0.026→0.031 | why: round-2 literature ([`docs/GEMINI_RESEARCH_REPORT.md`](../docs/GEMINI_RESEARCH_REPORT.md)) anchored ALPHA to the Arrhenius relation ALPHA=Ea/(R·T_ref²). The old 0.026 implied Ea~30 kJ/mol — the low end of the 30–40 kJ/mol coffee-extraction range; caffeine-extraction Ea ~36 kJ/mol gives 0.031 (Q10 1.3→1.4). Makes extraction rate slightly more temperature-sensitive off the anchor (all roasts, via tau). Anchor-safe: temp term = exp(0) at T_REF=98°C, so Hoffman TDS 1.23 is unchanged; 13/13 diagnose + 89 pytest pass. | revert: set ALPHA back to 0.026 in models/layer1.py
2026-06-04 | data/ideal.json (light) + diagnose_anchor.py | re-anchored light IDEAL from the Hoffman archetype (4.3/120/23, which the user logged ⭐2 — '怪, 沒baseline, 滑') to the user's 2026-05-27 ⭐4 cup (98°C / dial 4.8 / 26g / 90s): anchor_brew tds 1.2297→1.1944 / ey 19.10→16.12 / dial 4.3→4.8; IDEAL shifted RMS 0.019 (Sour +0.031, Citrus +0.029 brighter; Bitter −0.023, Dark.choc −0.022, Burnt −0.021 less roasty; Thick.viscous 0.044→0.029 thinner) | why: the feedback normalization (commit 184bc62) let all 17 logged cups be recomputed on ONE model scale ([`models/analysis.py`](../models/analysis.py)); the four ⭐4 light cups then formed a tight box — temp ≥98°C + steep ≤90s + dial 3.5–4.8 + dose 25–26g → TDS 1.19–1.27 / EY 16–18 — and every ⭐2 broke exactly one wall (dose 28 太濃 / 5.5+120s 太粗太長 / 92°C 太冷 / 120s+23g 太長). The earlier table that looked TDS-scattered (1.21–1.45) was a stale-model artifact; on the consistent scale the ⭐4 cluster is tight. The prior Hoffman anchor was itself a ⭐2 cup; this cup is the one the user named '乾淨茶感帶酸香'. diagnose light good cup 4.3/120/23 → 4.8/90/26. Loop reseeded (champion → ⭐4 archetype). 13/13 diagnose + 91 pytest pass. FOLLOW-UP: detect_flags() now shows model over-predicts light Bitter/roast (Layer 2 calibration, separate). | revert: restore prior light ideal {Sour 0.4136, Citrus 0.2541, Tea.floral 0.2704, Sweet 0.2205, Cereal 0.1445, Thick.viscous 0.0438, Bitter 0.2455, Astringent 0.1017, Burnt 0.0564, Dark.chocolate 0.1027} + anchor_brew tds 1.2297/ey 19.1001/dial 4.3 + diagnose good cup back to 98/4.3/120/23
