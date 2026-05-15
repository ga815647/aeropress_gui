# Feedback format — `data/feedback.jsonl`

Phase 8 freezes the schema. Phase 9 wires the webapp UI write path.

## Why JSONL (append-only)

- Concurrent appends from multiple browser tabs survive without a write lock.
- `tail -n 100 data/feedback.jsonl` works.
- Easy to grep / aggregate from Claude in a conversation — no DB driver.
- No mutation = no migration anxiety. Edits go through a new entry, not in-place.

## Entry schema

One JSON object per line. UTF-8. Newline-terminated.

```json
{
  "timestamp": "2026-05-15T17:30:00+08:00",
  "recipe_id": "abc123def456",
  "label": "balanced",
  "rating": "good",
  "stars": 4,
  "comment": "偏酸 — Heath bar 味道不夠，可能 dose 太低",
  "tags": ["acidic", "thin"],
  "roast": "medium_light",
  "brewer": "xl",
  "water": {"gh": 50, "kh": 30, "mg_frac": 0.40}
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `timestamp` | ISO-8601 string with timezone | yes | wall-clock at submit |
| `recipe_id` | 12-char sha1 hex | yes | from `models.labels.recipe_id()` — deterministic for a given (roast, brewer, dial, steep, temp, dose, water) tuple |
| `label` | string | yes | matches a key in `data/labels.json` at the time of writing |
| `rating` | `"good"` / `"ok"` / `"bad"` / `null` | optional | quick categorical |
| `stars` | int 1-5 or `null` | optional | 1-5 quick rating |
| `comment` | string | **primary input** | free-text — this is the main signal; LLM-readable |
| `tags` | string array | optional | quick chips: `acidic`, `thin`, `great-body`, `bitter`, `muted`, `floral`, ... |
| `roast` | string | yes | matches a key in `constants.ROAST_TABLE` |
| `brewer` | string | yes | `standard` / `xl` |
| `water` | `{gh: number, kh: number, mg_frac: number}` | yes | water profile snapshot |

## Write rules (Phase 9 must enforce)

1. **Append-only.** Never rewrite or delete lines. Corrections go in as new entries with a `correction_of` field referencing the prior `timestamp`.
2. **Atomic line writes.** Use `open(..., 'a')` + `\n` terminator; do not split a record across lines.
3. **No PII.** No emails, no usernames, no IPs. This file may be shared with Claude verbatim.
4. **Snapshot `label` and `roast` strings, not foreign keys.** If `balanced`'s IDEAL changes later, the historical feedback still has the right label name.

## Read flow (Phase 9 refine layer)

The intended workflow is Claude in conversation acting as the refine layer — no `refine_label.py` script. Typical session:

1. User: "Last few balanced brews tasted thin to me."
2. Claude: reads `data/feedback.jsonl`, filters `label=balanced` recent N entries, looks at `comment` + `tags`.
3. Claude proposes a diff to `data/labels.json`. e.g. raise `balanced.tds_prefer` from 1.27 → 1.30, or fork `balanced-mine` with a personalised IDEAL.
4. User approves; Claude edits `data/labels.json` directly. No new code is run — the loader (`models.labels.load_labels` with `@lru_cache`) picks up the change on next restart.

## Why no `--rate` CLI in Phase 8

Decided 2026-05-15: the natural moment a user wants to give feedback is *after brewing*, when they're looking at the recipe card in the webapp. Adding `--rate` would require a separate look-up flow. Webapp UI captures comment + tags inline next to the recipe being rated. CLI `--rate` may land in Phase 10+ for headless users — same append path.
