# Project Board

## Rules

- **All ticket-worker agents must run `make full-test` before marking a ticket as "Awaiting Validation" and fix any failures.**

---

## Backlog

### T8: Use Persistent HTTP Session for Discogs API

**Goal:** Replace individual `requests.get()`/`requests.post()` calls to the Discogs API with a shared `requests.Session` to reuse TCP/TLS connections and avoid redundant header construction.

**Details:**
- A single search can trigger 10-20+ Discogs API calls (paginated search across multiple strategies, collection sync). Each currently opens a new TCP+TLS connection.
- Create a module-level `requests.Session` in `backend/services/discogs.py` with shared headers (User-Agent, auth) and an `HTTPAdapter` with retry logic (similar to what OpenRouter already has).
- Replace all `requests.get()`/`requests.post()` calls in `discogs.py` with `session.get()`/`session.post()`.
- Handle OAuth header updates: when tokens change, update the session headers.
- Also update `backend/services/discogs_auth.py` and `backend/services/collection_sync.py` if they make direct `requests` calls to Discogs.
- OpenRouter already uses `requests.Session()` — no changes needed there.

**Files to modify:**
- `backend/services/discogs.py`
- `backend/services/discogs_auth.py`
- `backend/services/collection_sync.py`

---

### T7: Page-based Routing (Replace Tabs)

**Goal:** Replace the tab-based navigation with proper client-side routes so each section has its own URL.

**Details:**
- Install `react-router-dom` in the frontend
- Define routes: `/` (or `/search`) → Single Search, `/batch` → Batch Upload, `/review` → Batch Review, `/issues` → Issues, `/collection` → Collection
- Replace the tab state and conditional rendering in `App.tsx` with a `<Router>` + `<Routes>` tree
- Replace tab buttons with `<NavLink>` components so the active route is highlighted automatically
- Navigating directly to any route (e.g. `/collection`) must render the correct page without a full reload

**Files to create/modify:**
- `frontend/package.json` (add `react-router-dom`)
- `frontend/src/App.tsx`
- `frontend/src/App.css` (nav link active styles if needed)

---

## In Progress

_(empty)_

## Awaiting Validation

_(empty)_

---

## Finished

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

## Finished

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

**Files created/modified:**
- `.github/workflows/ci.yml` (create)
- `backend/tests/conftest.py` (create)
- `backend/requirements.txt`
- `pyproject.toml` (create)
- `Makefile`
- `backend/tests/` (new/improved test files)

---

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
- Fixed `batch_id`/`item_id` not being forwarded to `process_single_image` in batch routes

**Files created/modified:**
- `backend/config.py`
- `backend/services/vision.py`
- `backend/services/search.py`
- `backend/repository/mongo.py`
- `backend/repository/models.py`
- `backend/routes/usage.py` (created)
- `backend/routes/batch.py`
- `backend/main.py`

---

### T3: Fuzzy Matching — OR Instead of AND

**Goal:** Change fuzzy artist/album matching from AND to OR logic.

**Details:**
- In `backend/services/discogs.py`, function `_sanity_check()`: change return condition from `artist_sim >= threshold and album_sim >= threshold` to `artist_sim >= threshold or album_sim >= threshold`

**Files modified:**
- `backend/services/discogs.py`
- `backend/tests/test_discogs_service.py`

---

### T4: Replace "Not present in label" with null

**Goal:** Remove the sentinel string from LLM prompts. Use `null` for missing album/artist.

**Details:**
- Updated both prompts in `backend/config.py`: albums/artists are now `array of strings or null` (null if not visible)
- Updated `backend/services/search.py`: sentinel string detection replaced with null/empty check
- Self-titled logic intact

**Files modified:**
- `backend/config.py`
- `backend/services/search.py`
- `backend/tests/test_search_pipeline.py`

---

### T2: "Wrong Record" Button + Issues Tab

**Goal:** Add "Wrong" action button (layout: Wrong / Dismiss / Accept). Wrong records and errored items visible in a separate "Issues" tab for retry or manual add.

**Details:**
- Backend: added `WRONG = "wrong"` to `ReviewStatus` in `backend/models.py`
- Frontend BatchReview: action bar is now `Wrong / Dismiss / Accept+Add`; "Wrong" calls `reviewItemGlobal(itemId, 'wrong')`
- Frontend types: added `'wrong'` to `review_status` union
- Backend route: added `status` query param to `GET /api/review/items`
- New `IssuesView.tsx` component: two sections — "Wrong matches" and "Errors"; actions: Retry, Dismiss
- Added "Issues" tab in `App.tsx`

**Files created/modified:**
- `backend/models.py`
- `backend/routes/batch.py`
- `backend/repository/mongo.py`
- `frontend/src/types.ts`
- `frontend/src/components/BatchReview.tsx`
- `frontend/src/api.ts`
- `frontend/src/components/IssuesView.tsx` (created)
- `frontend/src/App.tsx`
- `frontend/src/App.css`

---

### T5: Collection Page

**Goal:** Fetch user's Discogs collection and display it with images, search, and sorting (default: genre → artist → year).

**Details:**
- Backend: added `get_collection(page, per_page, sort, sort_order)` to `backend/services/discogs.py`; added `GET /api/collection` endpoint
- Frontend: new `CollectionView.tsx` — grid of items with cover images, search bar, sort controls, pagination
- Added "Collection" tab in `App.tsx`

**Files created/modified:**
- `backend/services/discogs.py`
- `backend/routes/collection.py` (created)
- `backend/main.py` (registered new router)
- `frontend/src/api.ts`
- `frontend/src/components/CollectionView.tsx` (created)
- `frontend/src/types.ts`
- `frontend/src/App.tsx`
- `frontend/src/App.css`
