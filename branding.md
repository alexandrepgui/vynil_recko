# Groove Log — Branding Guide

## Vision

A tool for vinyl collectors who care about their records. Warm, curated, unpretentious. The app should feel like a well-lit independent record store — inviting, personal, and a little bit cool without trying too hard.

AI powers the search but stays invisible. The brand is about **the collector and the music**, not the tech.

## Reference

Primary inspiration: [Light in the Attic Records](https://lightintheattic.net/) — minimalist, high-contrast, reverence for the music. Clean lines, square album art front and center, sophisticated through restraint.

---

## Color Palette

Both themes share the same accent colors and maintain warm undertones — no sterile blues or cool grays. The dark theme feels like a dimly lit record store; the light theme feels like a sunlit one.

Default follows the user's system preference (`prefers-color-scheme`), with a manual toggle available.

### Dark Theme

| Role             | Color       | Hex       | Notes                                                |
|------------------|-------------|-----------|------------------------------------------------------|
| Background       | Warm black  | `#1A1714` | Not pure black — slightly warm/brown undertone       |
| Surface          | Charcoal    | `#2A2520` | Cards, elevated containers                           |
| Primary text     | Cream       | `#F5F0E8` | Warm off-white, easier on the eyes than pure white   |
| Secondary text   | Warm gray   | `#A09888` | Metadata, labels, timestamps                         |
| Border           | Soft edge   | `#3A3530` | Subtle separation, not harsh lines                   |

### Light Theme

| Role             | Color       | Hex       | Notes                                                |
|------------------|-------------|-----------|------------------------------------------------------|
| Background       | Warm white  | `#FAF7F2` | Slight parchment/cream tint — not clinical white     |
| Surface          | Light sand  | `#F0EBE3` | Cards, elevated containers                           |
| Primary text     | Warm black  | `#1A1714` | Same as dark-theme background — keeps continuity     |
| Secondary text   | Warm brown  | `#7A6F62` | Metadata, labels, timestamps                         |
| Border           | Soft edge   | `#E0D8CE` | Subtle warm separation                               |

### Shared (both themes)

| Role             | Color       | Hex       | Notes                                                |
|------------------|-------------|-----------|------------------------------------------------------|
| Accent           | Amber       | `#D4A843` | Links, active states, highlights — like warm light   |
| Accent hover     | Light amber | `#E8C060` | Hover/focus state for accent elements                |
| Danger           | Muted red   | `#C45040` | Destructive actions, errors                          |
| Success          | Sage green  | `#6B8F5E` | Confirmations, sync complete                         |

### Implementation

Use CSS custom properties on `:root` for the default (light), and `[data-theme="dark"]` or `@media (prefers-color-scheme: dark)` for dark overrides:

```css
:root {
  --bg:           #FAF7F2;
  --surface:      #F0EBE3;
  --text-primary: #1A1714;
  --text-secondary: #7A6F62;
  --border:       #E0D8CE;
  --accent:       #D4A843;
  --accent-hover: #E8C060;
  --danger:       #C45040;
  --success:      #6B8F5E;
}

[data-theme="dark"] {
  --bg:           #1A1714;
  --surface:      #2A2520;
  --text-primary: #F5F0E8;
  --text-secondary: #A09888;
  --border:       #3A3530;
}
```

A toggle in the nav or profile page switches `data-theme` on `<html>` and persists to localStorage.

## Logo

**Icon:** Vinyl record with a single concentric groove line, where the record edge opens into horizontal lines representing stacked records — groove meets collection in one connected mark. Uses `currentColor` for theme adaptability.

**Wordmark:** "groove log" in lowercase, custom vectorized letterforms in a bold, rounded, geometric Bauhaus-inspired style. Generated via AI, vectorized, and stored as SVG paths (no font dependency).

**Lockup:** Icon to the left of the wordmark, vertically centered. Icon at 5rem, wordmark at 4rem height.

**Files:**
- `frontend/src/assets/icon.svg` — logo icon
- `frontend/src/assets/logo.svg` — wordmark

## Typography

| Role        | Font                      | Weight     | Size    | Notes                                  |
|-------------|---------------------------|------------|---------|----------------------------------------|
| Logo        | Custom vectorized SVG     | —          | 4rem    | Bauhaus-inspired geometric rounded, lowercase "groove log" |
| Headings    | **Noto Serif Display** (Google Fonts) | 400–700 | 1.5–2.5rem | Clean, elegant serif — Apple New York vibe |
| Body        | **Inter** (Google Fonts)  | 400–500    | 0.875–1rem | Clean, modern, highly readable at small sizes |
| Mono/labels | Monospace (e.g. **JetBrains Mono**) | 400 | 0.75rem | Catalog numbers, IDs, technical metadata |

- Logo is a vectorized SVG — no web font needed for the app name
- Headings in Noto Serif Display give warmth and editorial feel without being quirky
- Body in Inter keeps it functional and modern (closest open-source equivalent to Apple SF Pro)
- No all-caps except small labels (e.g. genre tags)

## Layout Principles

- **Full-width pages** (per T11) with generous horizontal padding (`clamp(1rem, 4vw, 5rem)`)
- **Theme background** fills the entire viewport — no contrasting gutters
- **Content density varies by page:** collection grid is dense, search/profile are more spacious
- **Album art is the hero** — square, prominent, high quality. Everything else serves the artwork.
- **Minimal borders** — use spacing and subtle background shifts to separate sections, not lines
- **Consistent spacing scale:** 0.25 / 0.5 / 1 / 1.5 / 2 / 3 / 4 rem

## Component Style

### Cards (Collection Items)
- `var(--surface)` background
- No border by default — subtle border or soft glow on hover
- Square cover image fills the top, no padding
- Title and artist below in `var(--text-primary)` / `var(--text-secondary)`, truncated with ellipsis
- Gentle hover: slight lift (`translateY(-2px)`) and accent border-bottom or soft shadow
- In light mode, cards get a subtle shadow instead of relying on background contrast

### Navigation
- Sticky top bar, `var(--bg)` background
- Active tab: amber underline or text color
- Inactive: `var(--text-secondary)`
- No background color change on tabs — just text/underline treatment
- App name in serif heading font, left-aligned
- Theme toggle icon (sun/moon) in the nav bar

### Buttons
- **Primary:** Amber background, dark text (`#1A1714`), slightly rounded (4px) — same in both themes
- **Secondary:** Transparent with amber border, amber text
- **Danger:** Muted red background, cream/white text
- **Ghost:** No border, `var(--text-secondary)`, hover reveals subtle `var(--surface)` background

### Inputs / Search
- `var(--surface)` background
- Bottom-border-only style (like LITA's search) or minimal rounded border
- `var(--text-primary)` text, `var(--text-secondary)` placeholder
- Focus: amber bottom-border or outline

### Dialogs / Modals
- `var(--surface)` background
- Centered, max-width ~480px
- Semi-transparent backdrop — dark: `rgba(26,23,20,0.85)`, light: `rgba(26,23,20,0.5)`

## Iconography

- Thin line icons (1.5–2px stroke), not filled
- Warm gray default, cream or amber on interaction
- Keep icon usage minimal — text labels preferred where space allows

## Imagery

- Album covers displayed at square aspect ratio, always
- No rounded corners on album art (records are square)
- On hover: no overlay filters — keep the artwork pure
- Fallback for missing covers: `var(--surface)` placeholder with a subtle vinyl/record icon

## Tone of Voice

- Short, direct copy — no marketing fluff
- Slightly informal but not jokey
- "Your collection" not "Your library"
- "Sync from Discogs" not "Import your data"
- Error messages are human: "Couldn't reach Discogs. Try again?" not "Error 503: Service Unavailable"

---

## Open Questions

- [x] ~~Logo: text-only wordmark in serif, or a simple icon?~~ Icon (vinyl+stack) + vectorized wordmark lockup
- [x] ~~App name typography: "Groove Log" or "groove log" or "GROOVE LOG"?~~ "groove log" — all lowercase
- [x] ~~Should the light/warm feel extend to a light-mode option, or commit to dark-only?~~ Both themes supported, system default + manual toggle
- [x] ~~Favicon / PWA icon design~~ Done — favicon icons already created
- [x] ~~Specific body/heading font selection~~ Noto Serif Display (headings) + Inter (body)
