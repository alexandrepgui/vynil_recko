# Groove Log — UI Redesign Decisions

This document captures every design decision for the UI overhaul. Use it as a reference when making further changes or asking an agent to modify specific aspects.

---

## Phase 1: Theme System

### D1: CSS Custom Properties
Replace all 46 hardcoded color values in App.css with CSS custom properties on `:root`. See D46 for final palette. **Status: DONE**

### D2: Dark Theme
~~Add dark theme overrides.~~ **Status: DROPPED (see D43)**

### D3: ThemeProvider Context
~~Create a React context for theme switching.~~ **Status: DROPPED (see D43)**

### D4: Theme Toggle in Nav
~~Sun/moon icon button.~~ **Status: DROPPED (see D43)**

---

## Phase 2: Color Corrections

### D5: Replace Blue with Accent
Replace every instance of `#4a90d9` with `var(--accent)` / `var(--accent-hover)`. **Status: DONE**

### D6: Replace Green Action Buttons with Accent
Green `#2e7d32` is only for success text/status indicators. All action buttons use `var(--accent)`. **Status: DONE**

### D7: Standardize Danger Red
Replace three different reds with a single `var(--danger)`. **Status: DONE**

### D8: Standardize Success Green
Replace `#2e7d32` in success contexts with `var(--success)`. **Status: DONE**

### D9: Warm All Neutral Grays
Replace every cool gray with warm CSS variable equivalents. **Status: DONE**

---

## Phase 3: Navigation & Information Architecture

### D10: Consolidate Nav to Two Primary Items + Avatar
Merge into `[Identify] [Collection]` on left, `[avatar]` on right. Review/Issues become sub-views of Identify with badge counters. **Status: DONE (worktree: agent-a1829302)** — Review findings to fix:
1. Badge counters go stale after user reviews/dismisses items — need to pass `fetchCounts` down as prop or callback
2. No 404/catch-all route inside nested `IdentifyPage` routes or `AppInner` — blank content on unknown paths
3. Dead CSS class `.tab-icon` — remove it

### D11: Logo in Nav Bar, Left-Aligned
Place the icon + wordmark horizontal lockup at the left edge of a sticky top bar. **Status: DONE**

### D12: Remove Subtitle from Authenticated Views
"Identify your records by photo" only appears on the login page. **Status: DONE**

### D13: Default Route to Collection
If the user has a synced collection, route `/` to `/collection`. If no collection, route to `/identify`. **Status: TODO** (not yet implemented — D10 routes `/` to `/identify` for now)

### D14: Review and Issues as Contextual Sub-views
Within Identify, show badge/counter for pending review items as sub-tabs. **Status: DONE (with D10)**

---

## Phase 4: Card & Layout Styling

### D15: Remove Borders from All Cards
Remove borders, use `var(--surface)` background against `var(--bg)` + subtle shadow. **Status: DONE**

### D16: Square Album Art (No Rounded Corners)
`border-radius: 0` on all covers. **Status: DONE**

### D17: Hover Lift on Collection Cards
`translateY(-2px)` + shadow + amber bottom border on hover. **Status: DONE**

### D18: Larger Collection Cards
Card width `minmax(200px, 1fr)`. **Status: DONE**

### D19: Restyle Inputs (LITA-Inspired)
Bottom-border-only style with accent focus. **Status: DONE**

### D20: Warm Upload Zone
Accent border + tint on hover/drag. **Status: DONE**

### D21: Warm Modal Overlays
Warm backdrop + `var(--surface)` modal background. **Status: DONE**

### D22: Warm Selection Toolbar
Accent-tinted background and selected card outline. **Status: DONE**

### D23: Missing-Cover Placeholder
`var(--surface)` background + centered vinyl icon via CSS mask at 40% size, 30% opacity. **Status: DONE (worktree: agent-a90b17d6)** — Review: add `role="img" aria-label="No cover available"` and `aria-hidden="true"` on icon div.

---

## Phase 5: Typography

### D24: Load JetBrains Mono
Added to Google Fonts link in `index.html`. **Status: DONE**

### D25: Apply JetBrains Mono to Metadata
Applied to `.result-meta span`, `.collection-card-meta span`, `.debug-panel`. **Status: DONE**

### D26: Apply Coustard to Headings
Replaced Noto Serif Display with Coustard (see D45). **Status: DONE**

### D27: Lowercase App Title
`<title>groove log</title>`. **Status: DONE**

---

## Phase 6: Button System

### D34: Redefine Button Variants
Primary (accent bg), Secondary (outline), Danger (danger bg), Ghost (text-only). **Status: DONE**

### D35: Fix btn-nav
Secondary style: transparent background, `var(--text-secondary)` text, `var(--surface)` on hover. **Status: DONE**

---

## Phase 7: Interaction Polish

### D28: Vinyl Spinner
Replace border-spinner with rotating `vinyl.svg` via CSS mask-image. 1.2s linear infinite. **Status: DONE**

### D29: Skeleton Loading for Collection Grid
Shimmer placeholder cards during collection load. **Status: DONE (worktree: agent-acf1c1c9)** — Review findings to fix:
1. Shimmer animates `background-position` (not GPU-composited) — should use `transform` on pseudo-element
2. Missing `aria-hidden="true"` on skeletons, `aria-busy` on container
3. Remove unused `collection-skeleton-grid` CSS class or define it
4. Skeleton count should match `pageSize` instead of hardcoded 8

### D30: Improve Empty States
Warm copy for empty collection, review, and issues states. **Status: DONE**

### D31: Toast Notification System
Bottom-center toast container with auto-dismiss 3s. ToastProvider context + portal. Wired into CollectionView (delete/copy) and ImageUpload. **Status: DONE (worktree: agent-afc40997)** — Review findings to fix:
1. **Critical**: setTimeout handles never stored/cancelled — memory leak on unmount. Needs `useRef` timer tracking + `useEffect` cleanup
2. Remove `role="status"` from individual toasts (redundant with `aria-live="polite"` container, causes double-announcement)

### D32: Page Transition Animations
200ms fade-in on route mount. **Status: DONE**

### D33: Accessible Focus Rings
Global `:focus-visible` with `var(--accent)`. **Status: DONE**

---

## Phase 8: Iconography

### D36: Consistent Icon Style
All SVG icons converted to 1.5px stroke outline style with `currentColor`. 6 filled icons replaced (batch, single-search, hide, view, cd, profile). Brand assets (vinyl, icon, logo) untouched. Tab icons converted from `<img>` to inline React SVG components (`Icons.tsx`). **Status: DONE (worktree: agent-a8932c64)** — Review findings to fix:
1. **Merge conflict expected**: worktree built on old nav structure (`.mode-tabs`), but D10 replaces nav entirely — `Icons.tsx` is good but must be re-wired into D10's `nav-link` / `identify-subtab` pattern
2. Duplicate `:root` CSS variables in `App.css` — remove them (already in `index.css`)
3. Add `aria-hidden="true"` to decorative nav icons
4. Remove orphaned SVG asset files (single-search, batch, review, issues, collection, view, hide) — now superseded by `Icons.tsx`
5. Icon `size` prop is overridden by CSS `.tab-icon` width/height — remove SVG width/height attrs, rely on CSS

### D37: Active Tab Icon Color
Active tab icons now use `color: var(--accent)` with `opacity: 1` (inherits via `currentColor` in inline SVGs). **Status: DONE (with D36)** — needs adaptation to D10 nav structure

---

## Phase 9: Login Page

### D38: Rebrand Login Page
Warm background, surface card, logo lockup, accent buttons/focus. **Status: DONE**

### D39: Warm Login Subtitle
Shortened and warmed. **Status: DONE**

---

## Phase 10: Miscellaneous

### D40: Human-Friendly Error Copy
All user-facing error strings rewritten to conversational phrasing across 12 files. **Status: DONE (worktree: agent-ae0f27c8)** — Review findings to fix:
1. `App.tsx:51` — "Something went wrong." is the only fallback without a retry hint
2. `batch.py:83,248` — "Check server logs for details." leaks to users via Issues tab (backend fix needed)
3. Minor tone inconsistency: some messages end with `?`, others don't (e.g., LoginPage)

### D41: Toggle Switch to Accent
`.toggle-switch.toggle-on` background: `var(--accent)`. **Status: DONE**

### D42: Avatar Border Warm
`.profile-avatar-large` border: `var(--border)`. **Status: DONE**

### D43: Drop Dark Mode
Remove dark mode entirely. Delete `ThemeContext.tsx`, remove `ThemeProvider` wrapper from `App.tsx`, remove `ThemeToggle` component, remove `[data-theme="dark"]` and `@media (prefers-color-scheme: dark)` blocks from `index.css`, remove `.btn-theme-toggle` CSS. Light-only for now. **Status: DONE**

### D44: Vibrant Color Palette (Mamdani-inspired)
Replace the muted amber palette with a more vibrant, energetic one inspired by the Zohran Mamdani campaign (warm, energetic, approachable):
- `--accent`: `#D4A843` → `#F5A623` (vibrant amber)
- `--accent-hover`: `#E8C060` → `#FFB938`
- `--accent-text`: `#8F6E1A` → `#B07A0A`
- `--accent-subtle`: updated to match
- `--danger`: `#C45040` → `#E84230` (warmer vermillion)
- `--danger-subtle`: updated to match
**Status: DONE**

### D45: Swap Heading Font to Coustard
Replace Noto Serif Display with Coustard (chunky vintage serif, 400/900 weights). Updated Google Fonts link and all CSS references. **Status: DONE**

### D46: Zohran-Inspired Color Palette
Full palette swap based on Zohran Mamdani campaign colors:
- `--bg`: `#F4E3CD` (beige), `--surface`: `#ECD5B8`
- `--accent`: `#2B1BDF` (lighter blue), `--accent-text`: `#2717B0` (deeper blue)
- `--accent-hover`: `#3D2EF0`, `--on-accent`: `#F4E3CD` (beige on blue)
- `--danger`: `#F31C05` (red), `--on-danger`: `#FFFFFF`
- `--text-primary`: `#1A1520`, `--text-secondary`: `#5C4F6A`
- Yellow `#F49E03` available as secondary accent (not yet assigned to a token)
**Status: DONE**

### D48: Outline-Style Action Buttons
`.btn-collection`, `.btn-dismiss`, `.btn-wrong` converted from filled to 1.5px outline style with subtle hover fills. **Status: DONE (worktree: agent-aa084947)** — Review findings to fix:
1. `.btn` base transition changed from `0.15s` to `0.2s` — affects all filled buttons; revert timing
2. `.btn-dismiss-all` inherits new border from `.btn-dismiss` — may need override for mini buttons
3. `.btn-dismiss:hover` uses `var(--surface)` instead of a subtle tint like the other two buttons — add `rgba(92,79,106,0.08)` for consistency

### D47: Logo SVGs — Beige Fill with Blue Outline
Updated `icon.svg` and `logo.svg`: `fill="#F4E3CD"` with `stroke="#2717B0"` and `paint-order="stroke fill"`. Removed `currentColor`. TODO: finalize stroke width in a vector editor and expand strokes to paths. **Status: IN PROGRESS**

---

## Security Findings (From Review)

These should be addressed alongside the UI update:

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| S1 | HIGH | Open redirect via unvalidated `authorize_url` — added `isValidDiscogsUrl()` in `utils.ts`, validates against `https://discogs.com` before redirect in ProfilePage + DiscogsAuth | **DONE (worktree: agent-aadd1028, changes uncommitted!)** — Review also flagged backend redirect issues in `discogs_oauth.py:57,101` (`FRONTEND_URL` and `OAUTH_CALLBACK_URL` unvalidated) — separate scope, add as new ticket |
| S2 | HIGH | 5 MB file size limit on image upload | **DONE** |
| S3 | HIGH | 750 MB ZIP size limit on batch upload | **DONE** |
| S4 | MEDIUM | 10 MB avatar pre-resize gate | **DONE** |
| S5 | MEDIUM | Clipboard API error handling | **DONE** |
| S6 | MEDIUM | Settings fetch error silently defaults (shows wrong state) | TODO |
| S7 | MEDIUM | Price API errors silently suppressed at two levels | TODO |

---

## Architecture Notes (From Exploration)

- **46 unique hardcoded colors** in App.css, zero CSS custom properties
- **Dead code**: `DiscogsAuth.tsx` is imported nowhere; `Ranchers` font referenced but never loaded
- **Mixed icon system**: 5/12 SVGs use `currentColor`, 7 have hardcoded black fills
- **No media queries**: responsive behavior is clamp + JS resize listener (inconsistent)
- **`window.confirm()`** in BatchReview (lines 131, 147) — can't be styled, needs custom modal
- **`CollectionView.tsx`** is 561 lines with ~15 state variables — needs decomposition
- **`SingleSearchPage` and `PublicCollectionPage`** defined inline in App.tsx — should be extracted

---

## Worktrees Pending Merge

All implementations complete. Each lives in a separate git worktree branched from `b646f4c` (dev). Merge in this order to minimize conflicts:

1. `worktree-agent-aadd1028` — S1 (open redirect fix) — **changes uncommitted, commit first!** Otherwise clean
2. `worktree-agent-ae0f27c8` — D40 (error copy) — fix App.tsx fallback + batch.py backend string before merge
3. `worktree-agent-aa084947` — D48 (outline buttons) — fix transition timing + dismiss hover color
4. `worktree-agent-a90b17d6` — D23 (missing-cover placeholder) — add a11y attrs
5. `worktree-agent-acf1c1c9` — D29 (skeleton loading) — fix shimmer perf + a11y + skeleton count
6. `worktree-agent-afc40997` — D31 (toast system) — **fix timer memory leak first**, then fix aria
7. `worktree-agent-a1829302` — D10/D14 (nav consolidation) — fix stale badge counters + add catch-all routes
8. `worktree-agent-a8932c64` — D36-D37 (icons) — **merge last**: must adapt `Icons.tsx` to D10's new nav structure, resolve duplicate CSS vars, clean up orphaned SVGs

---

## Remaining TODO

| Item | Description |
|------|-------------|
| D13 | Default route to `/collection` for users with synced collections (currently always `/identify`) |
| D47 | Logo SVG stroke finalization in vector editor + expand strokes to paths |
| S6 | Settings fetch error silently defaults to wrong state |
| S7 | Price API errors silently suppressed |
| S1-backend | Backend redirect validation for `FRONTEND_URL` and `OAUTH_CALLBACK_URL` in `discogs_oauth.py` (flagged by reviewer, separate from frontend fix) |
| Review fixes | Apply all review findings listed inline with each task's status above |
