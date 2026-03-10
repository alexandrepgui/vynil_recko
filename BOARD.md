# Project Board

## Rules

- **All ticket-worker agents must run `make full-test` before marking a ticket as "Awaiting Validation" and fix any failures.**

---

## Backlog

### T11: Full-Width Responsive Layout

**Goal:** Remove the fixed `max-width: 860px` container so all pages use the full viewport width and adapt to any screen size.

**Details:**
- Remove or replace `max-width: 860px` on `.app` in `App.css`; use generous horizontal padding instead (e.g. `padding: 2rem clamp(1rem, 3vw, 4rem)`)
- Ensure the nav bar, header, and all page content stretch to fill the available width
- Verify all existing pages (Single Search, Batch, Review, Issues, Collection, Profile) look correct at various widths (mobile, tablet, desktop, ultrawide)
- Profile page already has its own `max-width: 480px` — keep that as-is
- Search/Batch/Review pages with centered content may benefit from a narrower readable max-width on their own (optional, use judgement)

**Files to modify:**
- `frontend/src/App.css` — `.app` container styles
- Possibly `frontend/src/App.tsx` if structural changes are needed

---

### T12: Adaptive Collection Grid with Custom Page Size

**Depends on:** T11

**Goal:** Let users choose how many records per page (up to 250) and make the grid dynamically adapt columns-per-row so the last row is always full (or as close as possible).

**Details:**
- **Custom page size:** Add a page-size selector to the collection controls (e.g. dropdown: 25, 50, 100, 150, 200, 250). Persist choice in localStorage. Default remains 50.
- **Backend:** Increase `per_page` max from 100 to 250 in `GET /api/collection` query validation
- **Adaptive columns:** Instead of pure CSS `auto-fill`, use JS to compute the optimal number of columns:
  1. Measure available container width
  2. Given a preferred card width (~160–200px), compute max columns that fit
  3. From that max, pick the largest divisor of the current item count (or total visible items) so the last row is complete. If no perfect divisor exists, pick the column count that minimizes empty cells in the last row.
  4. Apply via inline `grid-template-columns: repeat(N, 1fr)` or a CSS variable
  5. Recalculate on window resize (debounced)
- Update `PAGE_SIZE` constant to read from state; wire the selector to `fetchCollection()`

**Files to modify:**
- `frontend/src/components/CollectionView.tsx` — page-size selector, adaptive grid logic
- `frontend/src/App.css` — adjust `.collection-grid` styles
- `frontend/src/api.ts` — no changes needed (already accepts `perPage` param)
- `backend/routes/collection.py` — raise `per_page` max to 250

---

### T13: Multi-Select & Batch Delete from Collection

**Depends on:** T12

**Goal:** Allow users to select multiple records and delete them from both the local collection and Discogs, with a confirmation dialog.

**Details:**
- **Selection UI:** Add a checkbox overlay on each collection card (visible on hover or when selection mode is active). Add a toolbar that appears when ≥1 item is selected showing: selected count, "Select All (page)", "Deselect All", "Delete Selected" button.
- **Confirmation dialog:** When "Delete Selected" is clicked, show a modal warning: "You are about to remove N record(s) from your collection. This will also delete them from your Discogs account. This action cannot be undone." with "Cancel" and "Delete" buttons.
- **Backend:** Add `DELETE /api/collection` endpoint accepting `{ instance_ids: number[] }`. For each instance_id:
  1. Call Discogs API to remove the release from the user's collection (`DELETE /users/{username}/collection/folders/0/releases/{release_id}/instances/{instance_id}`)
  2. Remove the record from MongoDB
  3. Return summary: `{ deleted: number, errors: { instance_id: number, error: string }[] }`
- **Frontend:** On successful delete, remove items from local state and refresh pagination counts. Show toast/message with result.

**Files to create/modify:**
- `frontend/src/components/CollectionView.tsx` — selection state, toolbar, delete handler
- `frontend/src/App.css` — selection checkbox, toolbar, modal styles
- `frontend/src/api.ts` — add `deleteCollectionItems(instanceIds: number[])` function
- `backend/routes/collection.py` — add DELETE endpoint
- `backend/services/discogs.py` — add `remove_from_collection(instance_id, release_id, tokens)` function
- `backend/repository/mongo.py` — add `delete_collection_items(user_id, instance_ids)` method

---

### T14: Public Collection Page

**Depends on:** T13

**Goal:** Let users make their collection publicly viewable at `/collection/:username`. Add a privacy toggle in the profile page.

**Details:**
- **Privacy setting:** Add a "Collection visibility" toggle to ProfilePage (Public / Private, default Private). Store in Supabase user metadata (`collection_public: boolean`) or a new `user_settings` MongoDB collection.
- **Backend:**
  - Add `GET /api/collection/{username}` public endpoint (no auth required). Returns the same collection response but:
    - Looks up the user by Discogs username (or app display name)
    - Returns 404 if user not found or collection is private
    - Does not expose delete or sync endpoints
  - Add `PUT /api/me/settings` endpoint to update visibility preference
  - Add `GET /api/me/settings` to retrieve current settings
- **Frontend:**
  - New route `/collection/:username` rendering a read-only version of CollectionView (no sync button, no delete, no selection checkboxes)
  - Show the owner's display name / avatar at the top
  - The existing `/collection` route (authenticated) keeps full controls
  - ProfilePage: add toggle switch in a "Collection" section with explanatory text: "When public, anyone can view your collection at /collection/your-username"
- **Sharing:** When public, show a "Copy link" button on the authenticated collection page so the user can easily share their URL

**Files to create/modify:**
- `frontend/src/components/CollectionView.tsx` — add `readOnly` prop to hide controls; support loading by username
- `frontend/src/components/ProfilePage.tsx` — add visibility toggle
- `frontend/src/App.tsx` — add `/collection/:username` route
- `frontend/src/App.css` — styles for public collection header, toggle switch
- `frontend/src/api.ts` — add `getPublicCollection(username, ...)`, `getSettings()`, `updateSettings()`
- `frontend/src/types.ts` — add `UserSettings` interface
- `backend/routes/collection.py` — add public GET endpoint
- `backend/routes/profile.py` — add settings endpoints
- `backend/repository/mongo.py` — add user settings storage/retrieval (if using MongoDB)

---

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
