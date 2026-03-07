import os
from pathlib import Path

# All available via OpenRouter (https://openrouter.ai/models)
#
# Vision models (for label reading + ranking):
#   "google/gemini-2.5-flash"       — best value: top-tier vision, ~$0.15/$0.60 per 1M tokens
#   "openai/gpt-4o-mini"            — solid alternative: $0.15/$0.60 per 1M tokens
#   "moonshotai/kimi-k2.5"          — decent quality: ~$0.60/$2.00 per 1M tokens
#   "anthropic/claude-haiku-4.5"    — great quality, pricier: $1.00/$5.00 per 1M tokens
VISION_MODEL = "google/gemini-2.5-flash"

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Per-1M-token pricing (input, output) — used for cost estimation
# Source: https://openrouter.ai/models, https://ai.google.dev/gemini-api/docs/pricing
LLM_PRICING = {
    "google/gemini-2.5-flash": {"input": 0.30, "output": 2.50},
    "openai/gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "anthropic/claude-haiku-4.5": {"input": 1.00, "output": 5.00},
}

CACHE_DIR = Path(__file__).resolve().parent / ".cache"
CACHE_MAX_ENTRIES = 200

UPLOADS_DIR = Path(__file__).resolve().parent / ".uploads"

DISCOGS_BASE_URL = "https://api.discogs.com"
DISCOGS_USER_AGENT = "VynilRecko/1.0"

MAX_RANKING_RESULTS = 20

DEV_MODE = os.getenv("DEV_MODE", "").lower() in ("1", "true", "yes")

# Single-image searches are stored as BatchItems with this sentinel batch_id
# so they appear in the unified review queue alongside batch items.
SINGLE_SEARCH_BATCH_ID = "single-search"

# ── LLM Prompts ──────────────────────────────────────────────────────────────

VINYL_LABEL_READING_PROMPT = (
    "Look at this vinyl record label image. "
    "Extract as much information as possible. "
    "Return multiple possible variations ordered from most likely to least likely for albums and artists. "
    "For albums: include the full title, shorter versions without subtitles, and any plausible variations. "
    "For artists: include variations (e.g. with/without featured artists). "
    "Do NOT include individual track or song names — only album titles. "
    "If the album or artist name is not visible on the label, use null. "
    "Keep in mind that albums may be self-titled. "
    "Also extract any optional metadata visible on the label. "
    "Output ONLY a JSON object with these keys:\n"
    '- "albums": array of strings or null (null if not visible on the label)\n'
    '- "artists": array of strings or null (null if not visible on the label)\n'
    '- "country": string or null (ONLY if explicitly printed on the label — do NOT guess from language or artist origin. Use Discogs-style names: "Brazil", "US", "UK", "Europe", "Japan", etc.)\n'
    '- "format": string or null (e.g. "LP", "45 RPM", "EP")\n'
    '- "label": string or null (record label name, e.g. "Columbia", "RCA")\n'
    '- "catno": string or null (catalog number)\n'
    '- "year": string or null (release year if visible)\n'
    "Nothing else."
)

CD_LABEL_READING_PROMPT = (
    "Look at this CD image (disc, jewel case, or booklet). "
    "Extract as much information as possible. "
    "Return multiple possible variations ordered from most likely to least likely for albums and artists. "
    "For albums: include the full title, shorter versions without subtitles, and any plausible variations. "
    "For artists: include variations (e.g. with/without featured artists). "
    "Do NOT include individual track or song names — only album titles. "
    "If the album or artist name is not visible on the disc or case, use null. "
    "Keep in mind that albums may be self-titled. "
    "Also extract any optional metadata visible on the disc or case. "
    "Output ONLY a JSON object with these keys:\n"
    '- "albums": array of strings or null (null if not visible on the disc or case)\n'
    '- "artists": array of strings or null (null if not visible on the disc or case)\n'
    '- "country": string or null (ONLY if explicitly printed on the disc or case — do NOT guess from language or artist origin. Use Discogs-style names: "Brazil", "US", "UK", "Europe", "Japan", etc.)\n'
    '- "format": string or null (e.g. "CD", "CD, Album", "CD, Single")\n'
    '- "label": string or null (record label name)\n'
    '- "catno": string or null (catalog number)\n'
    '- "barcode": string or null (barcode if visible)\n'
    '- "year": string or null (release year if visible)\n'
    "Nothing else."
)

LABEL_READING_PROMPTS = {"vinyl": VINYL_LABEL_READING_PROMPT, "cd": CD_LABEL_READING_PROMPT}

VINYL_RANKING_PROMPT = (
    "I searched Discogs and found these candidate releases. "
    "Based on the vinyl label you just analyzed, rank them by how likely each one is the exact record shown in the image. "
    "Output ONLY a JSON object with two keys:\n"
    '- "likeliness": array of index values ordered from most likely to least likely\n'
    '- "discarded": array of index values for records that are FOR SURE not the correct record '
    "(e.g. completely wrong artist, wrong album, clearly a different release). "
    "Only discard records you are certain about."
)

CD_RANKING_PROMPT = (
    "I searched Discogs and found these candidate releases. "
    "Based on the CD you just analyzed, rank them by how likely each one is the exact release shown in the image. "
    "Output ONLY a JSON object with two keys:\n"
    '- "likeliness": array of index values ordered from most likely to least likely\n'
    '- "discarded": array of index values for records that are FOR SURE not the correct record '
    "(e.g. completely wrong artist, wrong album, clearly a different release). "
    "Only discard records you are certain about."
)

RANKING_PROMPTS = {"vinyl": VINYL_RANKING_PROMPT, "cd": CD_RANKING_PROMPT}
