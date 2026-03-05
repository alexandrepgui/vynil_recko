# Benchmark 1 — Vinyl Recko Batch Processing

**Date:** 2026-03-03  
**Model:** google/gemini-2.5-flash (via OpenRouter)  
**Input:** 138 vinyl label images (`all_labels.zip`, 239MB)  
**Pipeline:** Vision LLM → Discogs Search → LLM Ranking → User Review

---

## Processing Results

| Metric | Value |
|---|---|
| Total images | 138 |
| Completed | 135 (97.8%) |
| Errored | 3 (2.2%) |
| Batch wall-clock time | 31.5 min |
| Avg time per image | 13.7s (incl. 1s rate-limit sleep) |

**Errors:**
- `IMG_0874.jpg` — Vision could not extract album/artist
- `IMG_0928.jpg` — OpenRouter API returned non-JSON response
- `IMG_1019.jpg` — Vision could not extract album/artist

---

## Search Timing

| Percentile | Duration |
|---|---|
| p50 | 11.7s |
| p90 | 17.1s |
| p95 | 18.6s |
| p99 | 26.8s |
| Mean | 12.8s |
| Min | 7.6s |
| Max | 33.5s |

---

## Collection Add Timing

| Metric | Value |
|---|---|
| Successful adds | 126 |
| Failed adds | 1 |
| Mean | 1,018ms |
| p50 | 950ms |
| p90 | 1,358ms |
| Min | 741ms |
| Max | 2,304ms |

---

## Search Strategy Distribution

| Strategy | Count | % |
|---|---|---|
| Catalog number (catno) | 81 | 60% |
| Freeform query (q) | 54 | 40% |

Catno is tried first when the label has a visible catalog number. Falls back to freeform `artist + album` query otherwise.

---

## Accuracy / Hit Rate

| Metric | Count | % of completed |
|---|---|---|
| Accepted (correct match) | 126 | 93.3% |
| Dismissed (wrong match) | 6 | 4.4% |
| No results (ranking bug) | 3 | 2.2% |

**Effective hit rate: 93.3%** (126 / 135 completed)

Discogs collection after run: **126 releases** (matches accepted count exactly).

---

## Results per Search

| Metric | Value |
|---|---|
| Median | 4 |
| Mean | 71.0 |
| Min | 0 |
| Max | 492 |

High mean is skewed by freeform queries on popular artists returning hundreds of results. The LLM ranking step filters these down to the most likely match.

---

## Dismissed Items (6)

| Image | Label Extracted | Top Result Shown | Issue |
|---|---|---|---|
| IMG_0884 | Yes — Yes | Yes - The Yes Album | Too generic, wrong album |
| IMG_0894 | Alan Parsons Project — Turn of a Friendly Card | MIA. - Stille Post | catno matched unrelated release |
| IMG_0912 | Jean-Luc Ponty — Mystical Adventures | (none usable) | catno matched wrong release |
| IMG_0949 | Di Melo — Imorrível | Michael Meara - Nocturnal Panorama | Rare Brazilian record, catno mismatch |
| IMG_0993 | ELP — Tarkus | ELP - Best Of | Freeform matched compilation instead |
| IMG_1012 | RED ALERT — RED ALERT | Basement Jaxx - Red Alert | Generic name collision |

---

## Zero-Result Items (3)

| Image | Album | catno | Root Cause |
|---|---|---|---|
| IMG_0885 | Yes — Close to the Edge | 20.034-A | catno found results, LLM ranking discarded all |
| IMG_0890 | Neil Young — Harvest | 84.003-B | catno found results, LLM ranking discarded all |
| IMG_0997 | Pink Floyd — Wish You Were Here | 230.001 - A | catno found results, LLM ranking discarded all |

**Bug:** The ranking step could discard every result, producing 0 matches even when the search found valid releases. **Fixed** with a safety net that keeps results in likeliness order when all would be discarded.

---

## Token Usage / Pricing

> Not logged in this run — sub-step telemetry was not populated for batch items.

- Model: google/gemini-2.5-flash @ $0.15/1M input, $0.60/1M output
- 2 LLM calls per image (vision extraction + result ranking)
- **Total cost: $0.356** for 138 images ($0.0026/image)
- Per-call token breakdown not logged — action item for next benchmark

---

## Known Issues Found

1. **Ranking discards all results** — LLM could mark every search result as "discarded", returning 0 to the user. Fixed with safety net in `services/search.py`.
2. **Sub-step telemetry missing for batch** — `SearchRecord` vision/discogs/ranking fields are `null` for batch items (only `total_duration_ms` and `result` are populated).
3. **Token usage not captured** — OpenRouter response `usage` field is not parsed or stored.
