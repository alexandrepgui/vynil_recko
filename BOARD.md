# Project Board

## Rules

- **All ticket-worker agents must run `make full-test` before marking a ticket as "Awaiting Validation" and fix any failures.**

---

## Backlog

### T2: "Wrong Record" Button + Issues Tab

**Goal:** Add "Wrong" action button (layout: Wrong / Dismiss / Accept). Wrong records and errored items visible in a separate "Issues" tab for retry or manual add.

**Details:**
- Backend: add `WRONG = "wrong"` to `ReviewStatus` in `backend/models.py`
- Frontend BatchReview: change action bar to `Wrong / Dismiss / Accept+Add`; "Wrong" calls `reviewItemGlobal(itemId, 'wrong')`
- Frontend types: add `'wrong'` to `review_status` union
- Backend route: add `status` query param to `GET /api/review/items` (currently only filters by `review_status`)
- New `IssuesView.tsx` component: two sections — "Wrong matches" and "Errors"; shows image, label data, error; actions: Retry, Dismiss
- Add "Issues" tab in `App.tsx`

**Files to create/modify:**
- `backend/models.py`
- `backend/routes/batch.py`
- `frontend/src/types.ts`
- `frontend/src/components/BatchReview.tsx`
- `frontend/src/api.ts`
- `frontend/src/components/IssuesView.tsx` (create)
- `frontend/src/App.tsx`
- `frontend/src/App.css`

---

### T3: Fuzzy Matching — OR Instead of AND

**Goal:** Change fuzzy artist/album matching from AND to OR logic.

**Details:**
- In `backend/services/discogs.py`, function `_sanity_check()`: change return condition from `artist_sim >= threshold and album_sim >= threshold` to `artist_sim >= threshold or album_sim >= threshold`

**Files to modify:**
- `backend/services/discogs.py`

---

### T4: Replace "Not present in label" with null

**Goal:** Remove the sentinel string from LLM prompts. Use `null` for missing album/artist.

**Details:**
- Update both prompts in `backend/config.py`: albums/artists should be `array of strings or null` (null if not visible)
- Update `backend/services/search.py`: change sentinel string detection to null/empty check (`candidate_albums is None or len(candidate_albums) == 0`)
- Keep self-titled logic intact

**Files to modify:**
- `backend/config.py`
- `backend/services/search.py`

---

### T5: Collection Page

**Goal:** Fetch user's Discogs collection and display it with images, search, and sorting (default: genre → artist → year).

**Details:**
- Backend: add `get_collection(page, per_page, sort, sort_order)` to `backend/services/discogs.py`; add `GET /api/collection` endpoint
- Reference existing pattern in `scripts/discogs_collection_wipe.py` for Discogs collection API usage
- Frontend: new `CollectionView.tsx` — grid of items with cover images, search bar, sort controls, pagination
- Add "Collection" tab in `App.tsx`

**Files to create/modify:**
- `backend/services/discogs.py`
- `backend/routes/collection.py` (create)
- `backend/main.py` (register new router)
- `frontend/src/api.ts`
- `frontend/src/components/CollectionView.tsx` (create)
- `frontend/src/types.ts`
- `frontend/src/App.tsx`
- `frontend/src/App.css`

---

---

## In Progress

_(empty)_

## Awaiting Validation

### T6: LLM Cost Tracking & Provider Abstraction

**Goal:** Implement LLM usage monitoring, cost tracking, and a provider-agnostic abstraction layer supporting OpenRouter and Google AI (Gemini), configurable via environment variable.

**Details:**
- Research OpenRouter token usage metrics from API response (`usage` field: prompt/completion/total tokens, cost) in `backend/services/vision.py`
- Research Google AI (Gemini) direct API pricing vs OpenRouter; document cost comparison to determine if direct access is cheaper
- Refactor `vision.py` and `config.py` into a provider abstraction layer: supports OpenRouter and Google AI, unified interface for chat completions with vision, configurable via `LLM_PROVIDER=openrouter|google` env var
- Capture token usage after each LLM call (label reading and ranking) for both providers
- Persist per-request records in a new MongoDB `llm_usage` collection: `timestamp`, `provider`, `model`, `operation`, `prompt_tokens`, `completion_tokens`, `total_tokens`, `cost_usd`, `batch_id`/`item_id`, `cache_hit`
- Cache hits must not generate cost entries
- Add `GET /api/usage` endpoint returning aggregated stats (total cost, cost per day, cost per model, average tokens per request)

**Files to create/modify:**
- `backend/config.py`
- `backend/services/vision.py`
- `backend/services/search.py`
- `backend/repository/mongo.py`
- `backend/repository/models.py`
- `backend/routes/usage.py` (create)
- `backend/main.py` (register new router)

---

### T1: Test Pipeline & CI/CD

**Goal:** Understand and improve unit tests. Create GitHub Actions CI pipeline with test execution, coverage thresholds, and mutation testing. Add Makefile commands.

**Details:**
- 5 existing pytest test files in `backend/tests/` — review them, identify gaps, add missing tests
- Add `conftest.py` with shared fixtures
- Add `pytest-cov` and `mutmut` to `requirements.txt`
- Create `pyproject.toml` with pytest, coverage (threshold: 70%), and mutmut config
- Create `.github/workflows/ci.yml` — jobs: test, coverage, mutation; trigger on push to main and PRs
- Makefile: add `test-coverage`, `test-mutation`, `full-test` (runs entire pipeline) targets
- After completion, update this BOARD.md Rules section to enforce `make full-test` for all future tickets

**Files to create/modify:**
- `.github/workflows/ci.yml` (create)
- `backend/tests/conftest.py` (create)
- `backend/requirements.txt`
- `pyproject.toml` (create)
- `Makefile`
- `backend/tests/` (new/improved test files)

## Finished

_(empty)_
