# Project Board

## Rules

- **All ticket-worker agents must run `make full-test` before marking a ticket as "Awaiting Validation" and fix any failures.**

---

## Backlog

### T22: Move PDF Generation to Frontend (@react-pdf/renderer)

**Goal:** Offload PDF catalog generation from the backend (WeasyPrint) to the frontend using `@react-pdf/renderer`, eliminating server CPU/memory pressure and the heavy native WeasyPrint dependency.

**Why:**
- WeasyPrint is CPU/memory intensive on the server (Pango/Cairo native libs, image downloading, HTML rendering)
- Cover images are already loaded/cached in the browser from the collection grid — no need to re-download on the server
- Scales better: each user's browser does its own rendering instead of the server handling all exports
- Removes a heavy native dependency from the backend

**Details:**
- Replace `backend/services/export.py` PDF path with a frontend-only flow
- Use `@react-pdf/renderer` (React components → vector PDF, supports custom fonts and page breaks)
- Rewrite the PDF template in `<Document>`, `<Page>`, `<View>`, `<Text>`, `<Image>` primitives (not CSS — Yoga layout engine)
- Replicate: title page with stats, format grouping, record cards with cover art, page numbers, custom fonts (Shrikhand, DM Sans, JetBrains Mono)
- Keep CSV/Excel export on the backend (lightweight, no benefit from moving)
- Remove WeasyPrint and Pillow from `backend/requirements.txt` once PDF backend path is removed
- Keep the spinning vinyl loading dialog (already in frontend)

**Files to create/modify:**
- `frontend/package.json` — add `@react-pdf/renderer`
- `frontend/src/services/pdfExport.tsx` (create) — PDF document component and generation logic
- `frontend/src/components/CollectionView.tsx` — call frontend PDF generator instead of backend export API for PDF format
- `frontend/src/api.ts` — remove PDF from `exportCollection` (keep CSV/XLSX)
- `backend/services/export.py` — remove `generate_pdf`, `_download_cover_b64`, `_download_all_covers`, and related helpers
- `backend/routes/export.py` — remove PDF from supported formats
- `backend/requirements.txt` — remove `weasyprint` (keep `pillow` if used elsewhere)

---

### T15: Update Navbar - Logo/Brand Left, Profile Picture Right

**Goal:** Move logo and app name to the left side of the navbar. Replace current logo position with user's profile picture. Clicking logo/brand should redirect to home page.

**Details:**
- Navbar left side: app icon + "Groove Log" wordmark side by side
- Navbar right side: user's profile avatar (circular, with hover effect)
- Logo/brand link should navigate to "/" (home/identify page)
- Profile avatar maintains existing click behavior (goes to /profile)

**Files to modify:**
- `frontend/src/App.tsx` — navbar structure update
- `frontend/src/App.css` — navbar layout styles, logo/brand spacing, avatar positioning

---

### T9: Configure Supabase Cloud & Google OAuth (Manual)

**Goal:** Set up production-ready Supabase project with Google sign-in provider. This is a manual task — no code changes needed.

**Steps:**
1. Create a Supabase project at [supabase.com](https://supabase.com)
2. Copy to **Project URL**, **anon key**, and **JWT secret** (Settings → API → JWT Settings)
3. Enable Google provider in Authentication → Providers → Google:
   - Create a Google OAuth app in [Google Cloud Console](https://console.cloud.google.com) (APIs & Services → Credentials → OAuth 2.0 Client ID, type "Web application")
   - Set authorized redirect URI to `https://<your-project>.supabase.co/auth/v1/callback`
   - Paste to Google Client ID and Client Secret into Supabase Google provider settings
4. Set Site URL in Authentication → URL Configuration to your frontend URL (e.g. `http://localhost:5173` for dev). Add it to Redirect URLs too.
5. Update `.env` with production values:
   ```
   SUPABASE_JWT_SECRET=<your-jwt-secret>
   VITE_SUPABASE_URL=https://<your-project>.supabase.co
   VITE_SUPABASE_ANON_KEY=<your-anon-key>
   ```
6. Create a `covers` storage bucket (public, same config as `avatars`) — used by the "Change Cover" feature for custom cover image uploads
7. Test: sign up via login page → verify email → log in → confirm API calls work

**Note:** Local dev already works with `make dev` (uses Supabase CLI). This ticket is for production/cloud setup only.

---

### T18: Landing Page

**Goal:** Create a landing page at `/` for unauthenticated users. Tells the story of why cataloging matters and how Groove Log makes it effortless. Authenticated users are redirected to the app.

**Details:**
- Route: `/` for unauthenticated users (existing SmartRedirect handles authenticated users)
- Animation library: Framer Motion (scroll-triggered reveals, before/after transition)
- Hero: mix of real vinyl photography and product screenshots, with grain overlay
- Before/After section: animated transition (old manual flow dissolves into Groove Log flow)
- Sections: Hero → Problem/Fix → How It Works (3 steps) → Batch Mode → Why Catalog? → Your Data, Your Way (export: CSV, Excel, PDF, Obsidian) → Collection Showcase → CTA Footer
- Tone: warm, human, slightly irreverent. Never corporate. Lead with pain relief, not tech.
- Must match existing design system: dark theme, DM Sans / Shrikhand / JetBrains Mono, film grain, indigo accent

**Key messaging:**
- "Finally catalog your collection." — lead with the tedium of manual Discogs searching
- "Your exact pressing, not just any version." — speaks to collectors who care about releases
- Why catalog: gifts (no duplicates), buy/sell/exchange, treat your collection with care
- "Technology should serve your hobby, not replace it." — analog-first philosophy
- "Your data, your way." — export to CSV, Excel, PDF, Obsidian vaults

**Files to create/modify:**
- `frontend/package.json` — add `framer-motion`
- `frontend/src/components/LandingPage.tsx` (create)
- `frontend/src/App.tsx` — show LandingPage for unauthenticated users at `/`
- `frontend/src/App.css` — landing page styles

---

### T19: Remotion Promo Video Generation (Future)

**Goal:** Set up Remotion as a build-time tool for generating promo videos (social media, Product Hunt launch) from React code. Not user-facing — developer/marketing tool only.

**Details:**
- Separate from the main app bundle (build-time only, not shipped to users)
- Compositions: hero animation (vinyl spin + app demo), feature showcase, "how it works" sequence
- Export to MP4/GIF for social media, Product Hunt, README
- Reuse landing page visual assets and brand tokens

**Files to create:**
- `remotion/` directory with compositions
- `remotion/package.json` — Remotion dependencies
- `remotion/remotion.config.ts`

### T21: Obsidian Vault Export

**Goal:** Add Obsidian vault as an export format for the collection. Generates a .zip file containing markdown files with YAML frontmatter per record, compatible with Obsidian Dataview plugin.

**Details:**
- New format option `obsidian` in the existing export endpoint (`GET /api/collection/export?format=obsidian`)
- Each record becomes a markdown file: `collection/{Artist} - {Title}.md`
- YAML frontmatter: title, artist, year, format, genres, styles, release_id, discogs_url, cover_image, date_added
- Cover images referenced as URLs (not downloaded into the vault)
- Uses stdlib `zipfile` — no new dependencies
- Add "Obsidian Vault" option to the frontend Export dropdown

**Files to modify:**
- `backend/services/export.py` — add `generate_obsidian_vault()` function
- `backend/routes/export.py` — add `obsidian` to format pattern, media types, filenames, generators
- `frontend/src/api.ts` — add `'obsidian'` to `ExportFormat` type
- `frontend/src/components/CollectionView.tsx` — add menu item to Export dropdown
- `backend/tests/test_export.py`, `backend/tests/test_export_service.py` — add Obsidian tests

---

## In Progress

_(empty)_

## Awaiting Validation

### T20: Collection Export (CSV, Excel, PDF)

**Goal:** Let users export their collection as CSV, Excel (.xlsx), or PDF catalog files.

**Details:**
- Single endpoint: `GET /api/collection/export?format=csv|xlsx|pdf`
- Respects current sort/search filters ("export what you see")
- CSV: UTF-8 with BOM for Excel compatibility
- Excel: styled headers, auto-width columns, Discogs hyperlinks, frozen header row
- PDF: title page + table with cover art thumbnails (downloaded in parallel)
- Export dropdown button in collection toolbar (owner-only)

**Files created:**
- `backend/services/export.py` — `generate_csv()`, `generate_xlsx()`, `generate_pdf()`
- `backend/routes/export.py` — export endpoint with format validation
- `backend/tests/test_export.py` — route integration tests
- `backend/tests/test_export_service.py` — service unit tests

**Files modified:**
- `backend/main.py` — registered export router (before collection router to avoid `/api/collection/{username}` conflict)
- `backend/requirements.txt` — added `openpyxl`, `fpdf2`
- `frontend/src/api.ts` — added `exportCollection()` function and `ExportFormat` type
- `frontend/src/components/CollectionView.tsx` — Export dropdown button with CSV/Excel/PDF options
- `frontend/src/App.css` — export dropdown styles

---

### T16: Collection Page - Grouping Options

**Goal:** Add grouping options to collection page allowing users to group records by artist or genre. Ensure groups are not broken across page boundaries.

**Details:**
- Add group selector (dropdown): Artist / Genre / None
- When grouped, records display in sections with headers for each group
- Pagination must respect group boundaries - don't split a group across pages
- Group headers should show group name and record count
- Sorting disabled when grouped
- Store group preference in localStorage
- Debounced group changes for performance
- Shows limit notice when collection exceeds 250 items (client-side grouping limit)

**Files modified:**
- `frontend/src/components/CollectionView.tsx` — added `currentGroups` state for storing paginated groups; added `loadGroup()` (localStorage), `GROUP_OPTIONS` (Artist/Genre/None), `CollectionGroup` interface; added `getGroupKey()` (Artist/Genre only), `groupItems()`, `getPaginatedGroups()`, `calculateTotalPages()` helper functions; added `groupTimerRef` for debouncing; added `handleGroupChange()` with 150ms debounce; updated `fetchCollection()` to fetch all items and compute groups client-side when grouping; updated effect to compute page groups when page/pageSize changes; updated controls to include group selector with disabled sort; updated rendering to use `currentGroups` directly (avoids re-grouping); added group limit notice for 250+ items; fixed `handleDeleteSelected()` and `handleDeleteConfirm()` to pass `group` parameter
- `frontend/src/App.css` — added `.collection-group`, `.collection-group-header`, `.collection-group-name`, `.collection-group-count`, `.collection-group-select`, `.collection-limit-notice` styles

---

### T15: Update Navbar - Logo/Brand Left, Profile Picture Right

**Goal:** Move logo and app name to the left side of the navbar. Replace current logo position with user's profile picture. Clicking logo/brand should redirect to home page.

**Details:**
- Navbar left side: app icon + "groove log" wordmark (lower case) side by side
- Navbar right side: user's profile avatar (circular, with hover effect)
- Logo/brand link should navigate to "/" (home/identify page)
- Profile avatar maintains existing click behavior (goes to /profile)
- Navbar content is truly left-aligned (breaks out of centered `.app` container)

**Files modified:**
- `frontend/src/App.tsx` — navbar now uses `icon.svg` (standalone icon) + text span for "groove log" wordmark (lower case, matches login page); `logo.svg` retained for public collection page header (`/collection/:username`) only
- `frontend/src/App.css` — updated `.navbar-wordmark` to style text with Shrikhand font (1.75rem, letter-spacing); added `left: 0; right: 0; width: 100vw;` to `.app-navbar` for true left-alignment; updated mobile responsive font-size (1.4rem)

---

### T17: Collection Page - Record Card Context Menu

**Goal:** When clicking on a record card (outside the cover image area), open a context menu/dialog with options like delete, view on Discogs, view pricing, etc.

**Details:**
- Click anywhere on card except cover image opens action dialog
- Dialog options:
  - View on Discogs (opens new tab to Discogs release page)
  - View Pricing (opens Discogs marketplace pricing)
  - Delete from Collection (opens confirmation, then deletes)
  - Cancel
- Dialog should show record title/artist for context
- Maintain existing multi-select behavior (checkbox in corner unaffected)
- Style dialog as modal with backdrop blur

**Files modified:**
- `frontend/src/components/CollectionView.tsx` — added context menu state (`showContextMenu`, `contextItem`, `showDeleteConfirm`), card click handler (`handleCardClick`), dialog handlers (`handleViewOnDiscogs`, `handleViewPricing`, `handleDeleteFromCollection`, `handleDeleteConfirm`), context menu dialog component, delete confirmation dialog for single item, `collection-cover-wrapper` with `onClickCapture` to prevent opening menu
- `frontend/src/App.css` — added `.collection-cover-wrapper`, `.context-menu-overlay`, `.context-menu`, `.context-menu-title`, `.context-menu-subtitle`, `.context-menu-actions`, `.context-menu-item`, `.context-menu-item-danger`, `.context-menu-divider` styles with backdrop blur
- `frontend/src/api.ts` — added `getDiscogsReleaseUrl()` and `getDiscogsMarketplaceUrl()` helper functions

---

## Finished

### T11: Full-Width Responsive Layout

**Goal:** Remove fixed `max-width: 860px` container so all pages use full viewport width and adapt to any screen size.

**Files modified:**
- `frontend/src/App.css` — replaced `max-width: 860px` with `padding: 2rem clamp(1rem, 3vw, 4rem)` on `.app`

---

### T12: Adaptive Collection Grid with Custom Page Size

**Depends on:** T11

**Goal:** Let users choose how many records per page (up to 250) and make grid dynamically adapt columns-per-row so last row is always full (or as close as possible).

**Files modified:**
- `frontend/src/components/CollectionView.tsx` — page-size selector, adaptive grid logic (`computeOptimalColumns`), localStorage persistence
- `frontend/src/App.css` — `.collection-page-size-select` styles
- `backend/routes/collection.py` — raised `per_page` max from 100 to 250

---

### T13: Multi-Select & Batch Delete from Collection

**Depends on:** T12

**Goal:** Allow users to select multiple records and delete them from both local collection and Discogs, with a confirmation dialog.

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

**Goal:** Let users make their collection publicly viewable at `/collection/:username`. Add a privacy toggle in profile page.

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

**Goal:** Replace individual `requests.get()`/`requests.post()` calls to Discogs API with a shared `requests.Session` to reuse TCP/TLS connections and avoid redundant header construction.

**Files modified:**
- `backend/services/discogs.py` — module-level `_session` with HTTPAdapter retry; all calls use `_session.get/post`; `_headers()` now returns auth-only (User-Agent moved to session)
- `backend/services/discogs_auth.py` — `_auth_session` with same retry config; OAuth calls use `_auth_session`; `build_oauth_headers()` returns auth-only header
- `backend/tests/test_discogs_auth.py` — updated patches and assertions
- `backend/tests/test_auth_routes.py` — updated patches
- `backend/tests/test_search_endpoint.py` — updated patches
- `backend/tests/test_search_pipeline.py` — updated patches

---

### T7: Page-based Routing (Replace Tabs)

**Goal:** Replace tab-based navigation with proper client-side routes so each section has its own URL.

**Files modified:**
- `frontend/package.json` — added `react-router-dom ^7.0.0`
- `frontend/src/App.tsx` — replaced tab state with `BrowserRouter` + `Routes`; tab buttons replaced with `NavLink`; single-search view extracted to `SingleSearchPage` component
- `frontend/src/App.css` — added `text-decoration: none; text-align: center` to `.mode-tab` for anchor rendering

---

### T10: User Profile Page with Avatar

**Goal:** Add a user profile page with account details, avatar upload, Discogs connection management, and sign-out.

**Details:**
- Profile tab in top nav bar with user icon (alongside other pages)
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

**Files created/modified:**
- `.github/workflows/ci.yml` (create)
- `backend/tests/conftest.py` (create)
- `backend/requirements.txt`
- `pyproject.toml` (create)
- `Makefile`
- `backend/tests/` (new/improved test files)

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

**Goal:** Remove sentinel string from LLM prompts. Use `null` for missing album/artist.

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
