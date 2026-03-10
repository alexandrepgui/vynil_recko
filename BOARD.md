# Project Board

## Rules

- **All ticket-worker agents must run `make full-test` before marking a ticket as "Awaiting Validation" and fix any failures.**

---

## Backlog

### T9: Configure Supabase Cloud & Google OAuth (Manual)

**Goal:** Set up production-ready Supabase project with Google sign-in provider. This is a manual task — no code changes needed.

**Steps:**
1. Create a Supabase project at [supabase.com](https://supabase.com)
2. Copy the **Project URL**, **anon key**, and **JWT secret** (Settings → API → JWT Settings)
3. Enable Google provider in Authentication → Providers → Google:
   - Create a Google OAuth app in [Google Cloud Console](https://console.cloud.google.com) (APIs & Services → Credentials → OAuth 2.0 Client ID, type "Web application")
   - Set authorized redirect URI to `https://<your-project>.supabase.co/auth/v1/callback`
   - Paste the Google Client ID and Client Secret into the Supabase Google provider settings
4. Set Site URL in Authentication → URL Configuration to your frontend URL (e.g. `http://localhost:5173` for dev). Add it to Redirect URLs too.
5. Update `.env` with production values:
   ```
   SUPABASE_JWT_SECRET=<your-jwt-secret>
   VITE_SUPABASE_URL=https://<your-project>.supabase.co
   VITE_SUPABASE_ANON_KEY=<your-anon-key>
   ```
6. Test: sign up via the login page → verify email → log in → confirm API calls work

**Note:** Local dev already works with `make dev` (uses Supabase CLI). This ticket is for production/cloud setup only.

---

## In Progress

_(empty)_

## Awaiting Validation

### T11: Full-Width Responsive Layout

**Goal:** Remove the fixed `max-width: 860px` container so all pages use the full viewport width and adapt to any screen size.

**Files modified:**
- `frontend/src/App.css` — replaced `max-width: 860px` with `padding: 2rem clamp(1rem, 3vw, 4rem)` on `.app`

---

### T12: Adaptive Collection Grid with Custom Page Size

**Depends on:** T11

**Goal:** Let users choose how many records per page (up to 250) and make the grid dynamically adapt columns-per-row so the last row is always full (or as close as possible).

**Files modified:**
- `frontend/src/components/CollectionView.tsx` — page-size selector, adaptive grid logic (`computeOptimalColumns`), localStorage persistence
- `frontend/src/App.css` — `.collection-page-size-select` styles
- `backend/routes/collection.py` — raised `per_page` max from 100 to 250

---

### T13: Multi-Select & Batch Delete from Collection

**Depends on:** T12

**Goal:** Allow users to select multiple records and delete them from both the local collection and Discogs, with a confirmation dialog.

**Files modified:**
- `frontend/src/components/CollectionView.tsx` — selection state, toolbar, delete handler, confirmation modal
- `frontend/src/App.css` — checkbox overlay, selection toolbar, modal styles
- `frontend/src/api.ts` — `deleteCollectionItems()` function
- `backend/routes/collection.py` — `DELETE /api/collection` endpoint with `min_length=1, max_length=250` validation
- `backend/services/discogs.py` — `remove_from_collection()` function
- `backend/repository/mongo.py` — `delete_collection_items()`, `find_collection_items_by_instance_ids()` methods
- `backend/tests/test_collection_price.py`, `test_discogs_service.py`, `test_mongo_repository.py` — new tests

---

### T14: Public Collection Page

**Depends on:** T13

**Goal:** Let users make their collection publicly viewable at `/collection/:username`. Add a privacy toggle in the profile page.

**Files modified:**
- `frontend/src/components/CollectionView.tsx` — `readOnly` + `username` props, public endpoint loading
- `frontend/src/components/ProfilePage.tsx` — collection visibility toggle
- `frontend/src/App.tsx` — `/collection/:username` route
- `frontend/src/App.css` — toggle switch, public collection header styles
- `frontend/src/api.ts` — `getPublicCollection()`, `getSettings()`, `updateSettings()`
- `frontend/src/types.ts` — `UserSettings`, `PublicCollectionResponse` interfaces
- `backend/routes/collection.py` — `GET /api/collection/{username}` public endpoint, shared `_paginated_collection` helper
- `backend/routes/profile.py` — `GET/PUT /api/me/settings` endpoints
- `backend/repository/mongo.py` — `get_user_settings()`, `update_user_settings()`, `find_user_id_by_username()`, `find_discogs_username()`, `oauth_username_lookup` index
- `backend/tests/test_collection_price.py`, `test_profile_routes.py` — new tests

---

### T8: Use Persistent HTTP Session for Discogs API

**Goal:** Replace individual `requests.get()`/`requests.post()` calls to the Discogs API with a shared `requests.Session` to reuse TCP/TLS connections and avoid redundant header construction.

**Files modified:**
- `backend/services/discogs.py` — module-level `_session` with HTTPAdapter retry; all calls use `_session.get/post`; `_headers()` now returns auth-only (User-Agent moved to session)
- `backend/services/discogs_auth.py` — `_auth_session` with same retry config; OAuth calls use `_auth_session`; `build_oauth_headers()` returns auth-only header
- `backend/tests/test_discogs_auth.py` — updated patches and assertions
- `backend/tests/test_auth_routes.py` — updated patches
- `backend/tests/test_search_endpoint.py` — updated patches
- `backend/tests/test_search_pipeline.py` — updated patches

---

### T7: Page-based Routing (Replace Tabs)

**Goal:** Replace the tab-based navigation with proper client-side routes so each section has its own URL.

**Files modified:**
- `frontend/package.json` — added `react-router-dom ^7.0.0`
- `frontend/src/App.tsx` — replaced tab state with `BrowserRouter` + `Routes`; tab buttons replaced with `NavLink`; single-search view extracted to `SingleSearchPage` component
- `frontend/src/App.css` — added `text-decoration: none; text-align: center` to `.mode-tab` for anchor rendering

---

---

## Finished

### T10: User Profile Page with Avatar

**Goal:** Add a user profile page with account details, avatar upload, Discogs connection management, and sign-out.

**Details:**
- Profile tab in the top nav bar with user icon (alongside other pages)
- Profile page shows: avatar (from OAuth or uploaded), display name, email, sign-out button
- Avatar upload via Supabase Storage (`avatars` bucket), saved to user metadata
- Placeholder user icon SVG for fallback (no initials)
- Discogs connection section: connect/disconnect with status display
- Backend `GET /api/me` returns user info + Discogs connection status

**Files created/modified:**
- `backend/auth.py` — extended `User` dataclass with `name` and `avatar_url` from JWT `user_metadata`
- `backend/routes/profile.py` (created — `GET /api/me`)
- `backend/main.py` — registered profile router
- `backend/tests/test_profile_routes.py` (created)
- `frontend/src/types.ts` — added `UserProfile` interface
- `frontend/src/api.ts` — added `getProfile()`
- `frontend/src/assets/profile.svg` (created — user silhouette icon)
- `frontend/src/components/ProfilePage.tsx` (created — profile page with avatar upload)
- `frontend/src/App.tsx` — added Profile tab to nav bar, added `/profile` route
- `frontend/src/App.css` — profile page and avatar styles
- `supabase/config.toml` — added `avatars` storage bucket

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
