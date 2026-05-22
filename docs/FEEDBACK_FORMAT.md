# Feedback format — `data/feedback.jsonl`

Phase 10 **Step 6a** schema (2026-05-22). The feedback log is the training signal
for the Phase 11 recipe-generator loop, so the schema is built around the §4
questionnaire of [`PHASE10_STEP6_FEEDBACK_LOOP.md`](PHASE10_STEP6_FEEDBACK_LOOP.md):
**pairwise, ordinal, memory-based**. Every cup is judged against the *previous*
cup; answers are ordinal — `>` / `=` / `<` for overall preference, `>` / `?` /
`<` per attribute (`?` = noticed no difference / unsure). No magnitude — fuzzy
taste memory cannot support it, and the sign hill-climb never uses magnitude
anyway.

> This supersedes the Phase 8/9 schema (`label` + `water` + `stars` + `tags` +
> `recipe.score`). Pre-Step-6 entries are still valid on disk and still read —
> see *Legacy entries* below — they simply lack the new fields.

## Why JSONL (append-only)

- Concurrent appends from multiple browser tabs survive without a write lock.
- `tail -n 100 data/feedback.jsonl` works.
- Easy to grep / aggregate from Claude in a conversation — no DB driver.
- No mutation = no migration anxiety. Edits go through a new entry, not in-place.

## Entry schema

One JSON object per line. UTF-8. Newline-terminated.

```json
{
  "timestamp": "2026-05-22T15:30:00+08:00",
  "recipe_id": "abc123def456",
  "roast": "medium_light",
  "brewer": "xl",
  "recipe": {"temp": 95, "dial": 4.4, "dose": 24.0, "steep_sec": 150,
             "tds": 1.366, "ey": 20.11, "distance": 0.012},
  "compared_to": "2026-05-20T14:00:00+08:00",
  "overall": ">",
  "attributes_vs": {"acidity": "?", "sweetness": ">", "body": ">",
                    "bitterness": "<", "astringency": "?", "roast": "?",
                    "character": ">"},
  "model_attributes_vs": {"acidity": "?", "sweetness": ">", "body": "?",
                          "bitterness": "?", "astringency": "?", "roast": "?",
                          "character": "?"},
  "absolute": "good",
  "comment": "比上一杯 body 更扎實，苦味收斂",
  "stars": 5,
  "tags": ["great-body"],
  "water_note": ""
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `timestamp` | ISO-8601 string with timezone | yes | wall-clock at submit, server-side |
| `recipe_id` | 12-char sha1 hex | yes | from `models.ideal.recipe_id()` — deterministic for `(roast, brewer, dial, steep, temp, dose)` |
| `roast` | string | yes | a key in `constants.ROAST_TABLE` |
| `brewer` | string | yes | `standard` / `xl` |
| `recipe` | object or `null` | optional | brew snapshot `{temp, dial, dose, steep_sec, tds?, ey?, distance?}`. `temp/dial/dose/steep_sec` are durable inputs; `tds/ey/distance` are a model projection — **stale-able**, recompute with the current model on read (see *Recompute* below). |
| `compared_to` | string or `null` | optional | `timestamp` of the prior cup this one is judged against. `null` = no comparison (first cup, or skipped). |
| `overall` | `">"` / `"="` / `"<"` / `null` | optional | this cup vs the `compared_to` cup, **overall preference**. `>` = this one is better. This is the loop's search signal. |
| `attributes_vs` | object or `null` | optional | per-questionnaire-group `>` / `?` / `<` vs the `compared_to` cup. Keys ⊆ the 7 `AXIS_VIEW` groups (below). `>` = *more* of that attribute, `<` = *less*, **`?` = noticed no difference / unsure**. There is deliberately no `=`: fuzzy 2-cup memory cannot support a confident "exactly equal" per attribute, so the middle answer is honestly "no directional signal". A partial dict is fine — unanswered groups are simply absent. |
| `model_attributes_vs` | object or `null` | optional | the model's **prefilled prediction** of `attributes_vs` — the `>` / `?` / `<` the Layer 1+2 model expected between the two cups (`?` = within the prefill dead-band, model expects no perceptible change). Stored verbatim so Phase 11 can flag *model direction-errors* without re-deriving a possibly-recalibrated model. |
| `absolute` | `"good"` / `"ok"` / `"bad"` / `null` | optional | the occasional **absolute-anchor** question — "drink it on its own, is it good" — independent of any comparison. Guards against a long chain of "slightly better than last" drifting somewhere globally bad (§4). |
| `comment` | string | **primary free input** | free-text — the main qualitative signal; LLM-readable. |
| `stars` | int 1-5 or `null` | optional | quick gut rating. **Not** the loop's signal (the hill-climb uses only the ordinal `overall`); kept for the logbook view + as a legacy-compatible quick check. |
| `tags` | string array | optional | legacy quick chips; not required. |
| `water_note` | string | optional | free-text water note. Phase 10 does **not** model water, so it is deliberately unstructured (no `gh/kh/mg_frac`). |

An entry must carry at least one of `comment` / `overall` / `attributes_vs` /
`absolute` / `stars` / `tags` — an empty submission is rejected.

### The 7 questionnaire groups (`AXIS_VIEW`)

`attributes_vs` / `model_attributes_vs` are keyed by the display groups in
`models.sensory.AXIS_VIEW` — the 10 model attributes rolled up to the ~7 things
a person can actually taste apart:

| group | model attributes summarized |
|-------|-----------------------------|
| `acidity` | Sour, Citrus |
| `sweetness` | Sweet |
| `body` | Thick.viscous |
| `bitterness` | Bitter |
| `astringency` | Astringent |
| `roast` | Burnt |
| `character` | Tea.floral, Cereal, Dark.chocolate |

The model **representation** is the 10 attributes (`models.sensory.ATTRIBUTES`);
the **questionnaire** asks at this coarser group level — the two are decoupled
on purpose (§4: ask only what a human can distinguish).

### Model prefill (`model_attributes_vs`)

For a cup `R` compared against prior cup `P`, the webapp runs `predict_attributes`
for both, rolls each 10-attribute vector up to the 7 groups (group value = mean
of its attributes), and fills each group with `>` / `?` / `<` from the sign of
`group(R) − group(P)`, with a small dead-band (`|Δ| < ORDINAL_DEADBAND` → `?`).
That prefill is what the user sees; they only correct the groups the model got
wrong. Both the prefill (`model_attributes_vs`) and the corrected answer
(`attributes_vs`) are stored — their disagreement is exactly the Phase 11
direction-error flag (§6 tier 2).

### `?` does not feed correction (Phase 11)

`?` ("noticed no difference / unsure") is **recorded** but is **not a training
signal**: Phase 11's model-error flag and per-attribute calibration must skip
any group where either side is `?`. Only a clear, opposite ">" vs "<" between
`model_attributes_vs` and `attributes_vs` is a genuine direction-error. The
reason is honesty about perception: with two-cup taste memory, "I didn't notice
a difference" is an *absence of signal*, not a confident assertion that the two
cups are equal on that attribute — so it cannot confirm or contradict the model.
(`overall` is different — its `=` is a real answer and the search uses it.)

## Write rules

1. **Append-only.** Never rewrite or delete lines. Corrections go in as new
   entries (a fresh comparison), not in-place edits.
2. **Atomic line writes.** `open(..., 'a')` + `\n` terminator; never split a
   record across lines.
3. **No PII.** No emails, usernames, IPs — this file may be shared with Claude
   verbatim.
4. **Snapshot `roast` as a string, not a foreign key.** Historical feedback
   keeps the right roast name even if `data/ideal.json` changes later.
5. A short in-window edit (`EDIT_WINDOW_HOURS`) is allowed for the misclick
   case — `models.feedback.update_feedback` — but is the only exception to (1).

## Legacy entries (pre-Step-6)

Entries written before Step 6 carry `label`, a structured `water` object,
`rating`, and `recipe.score`; they have none of `compared_to` / `overall` /
`attributes_vs` / `absolute`. They remain valid: `read_all()` parses them, the
logbook renders them as history, and `recompute_entry()` still refreshes their
`tds`/`ey` (now also `distance`/`attributes`) from the recipe snapshot. The new
loop simply has no pairwise signal from them — they are gut-rating history.

## Recompute (stale derived fields)

`recipe.tds` / `ey` / `distance` are the model's projection *at log time*. After
a model recalibration the snapshot drifts. `models.feedback.recompute_entry()`
re-derives `ey` / `tds` / `distance` / `attributes` from the durable recipe
inputs (`temp/dial/dose/steep_sec`) through the **current** model
(`optimizer.score_logged_recipe`). The on-disk JSONL is never mutated by this —
the history view displays the recompute, the file stays append-only.

## Read flow — Claude as the refine layer

The intended workflow is Claude in conversation acting as the refine layer — no
`refine_*.py` script. A typical session (Phase 11 tier-3, §6):

1. The loop flags *repeated* model direction-errors (`model_attributes_vs` vs
   `attributes_vs` disagree the same way across cups).
2. User opens a conversation; Claude reads `data/feedback.jsonl`, looks at the
   flagged groups + `comment` text.
3. Claude distinguishes *model error* (per-attribute contradiction → fix Layer 2
   coefficients / `data/ideal.json`) from *preference shift* (overall preference
   moved, attributes all agreed → the loop's own job, not Claude's).
4. Claude proposes a diff (e.g. `data/ideal.json` IDEAL, a `models/sensory.py`
   coefficient), the user approves, Claude edits + logs a one-line changelog.
