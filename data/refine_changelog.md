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
