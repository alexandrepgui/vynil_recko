import base64
import hashlib
import json
import os

import requests

from config import (
    CACHE_DIR,
    CACHE_MAX_ENTRIES,
    LABEL_READING_PROMPT,
    MAX_RANKING_RESULTS,
    OPENROUTER_URL,
    RANKING_PROMPT,
    VISION_MODEL,
)
from logger import get_logger

log = get_logger("services.vision")


# ── Disk cache (LRU by mtime, keyed on image SHA-256) ───────────────────────

def _cache_path(image_bytes: bytes) -> "Path":
    from pathlib import Path
    key = hashlib.sha256(image_bytes).hexdigest()
    return Path(CACHE_DIR) / f"{key}.json"


def _read_cache(image_bytes: bytes) -> dict | None:
    path = _cache_path(image_bytes)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        path.touch()  # bump mtime for LRU
        log.info("Cache HIT: %s", path.name)
        return data
    except (json.JSONDecodeError, OSError) as e:
        log.warning("Cache read error, ignoring: %s", e)
        return None


def _write_cache(image_bytes: bytes, label_data: dict) -> None:
    from pathlib import Path
    Path(CACHE_DIR).mkdir(parents=True, exist_ok=True)
    _evict_if_needed()
    path = _cache_path(image_bytes)
    path.write_text(json.dumps(label_data))
    log.info("Cache WRITE: %s", path.name)


def _evict_if_needed() -> None:
    from pathlib import Path
    cache_dir = Path(CACHE_DIR)
    entries = sorted(cache_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
    while len(entries) >= CACHE_MAX_ENTRIES:
        oldest = entries.pop(0)
        oldest.unlink()
        log.info("Cache EVICT: %s", oldest.name)


def _api_headers() -> dict:
    return {
        "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
        "Content-Type": "application/json",
    }


def _chat(messages: list[dict]) -> tuple[str, list[dict]]:
    """Send messages to the LLM and return (response_text, updated_messages)."""
    log.debug("LLM request: model=%s messages=%d", VISION_MODEL, len(messages))
    resp = requests.post(
        OPENROUTER_URL,
        headers=_api_headers(),
        json={"model": VISION_MODEL, "messages": messages},
    )
    log.debug("LLM response: status=%d", resp.status_code)
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    log.debug("LLM response length: %d chars", len(content))
    messages.append({"role": "assistant", "content": content})
    return content, messages


def _parse_json(raw: str) -> dict | list:
    cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        result = json.loads(cleaned)
        log.debug("JSON parsed successfully")
        return result
    except json.JSONDecodeError as e:
        log.error("JSON parse failed: %s — raw content: %.200s", e, cleaned)
        raise


def read_label_image(image_bytes: bytes, mime_type: str) -> tuple[dict, list[dict], bool]:
    """Extract label metadata via vision. Returns (label_data, conversation_messages, cache_hit).

    Results are cached on disk keyed by image SHA-256. On cache hit the LLM call
    is skipped entirely and a synthetic conversation is reconstructed so that
    downstream rank_results() still works.
    """
    log.info("Reading label image: size=%d bytes, mime=%s", len(image_bytes), mime_type)

    # Check cache first
    cached = _read_cache(image_bytes)
    if cached is not None:
        # Rebuild a minimal conversation so rank_results can append to it
        b64_image = base64.b64encode(image_bytes).decode()
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64_image}"}},
                    {"type": "text", "text": "(label reading prompt — cached)"},
                ],
            },
            {"role": "assistant", "content": json.dumps(cached)},
        ]
        return cached, messages, True

    b64_image = base64.b64encode(image_bytes).decode()

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{b64_image}"},
                },
                {"type": "text", "text": LABEL_READING_PROMPT},
            ],
        }
    ]

    raw, messages = _chat(messages)
    label_data = _parse_json(raw)
    log.info(
        "Label extracted: albums=%s artists=%s",
        label_data.get("albums"), label_data.get("artists"),
    )

    _write_cache(image_bytes, label_data)

    return label_data, messages, False


def rank_results(
    releases: list[dict],
    conversation: list[dict],
) -> tuple[list[int], list[int]]:
    """Ask the LLM to rank Discogs results using the same conversation context.

    Returns (likeliness_indexes, discarded_indexes).
    """
    candidates = []
    for i, r in enumerate(releases[:MAX_RANKING_RESULTS]):
        candidates.append({
            "index": i,
            "title": r.get("title"),
            "year": r.get("year"),
            "country": r.get("country"),
            "format": ", ".join(r.get("format", [])),
            "label": ", ".join(r.get("label", [])),
            "catno": r.get("catno"),
        })

    log.info("Ranking %d candidates", len(candidates))

    conversation.append({
        "role": "user",
        "content": f"{RANKING_PROMPT}\n\n{json.dumps(candidates, indent=2)}",
    })

    raw, _ = _chat(conversation)
    result = _parse_json(raw)
    likeliness = result.get("likeliness", [])
    discarded = result.get("discarded", [])
    log.info("Ranking complete: %d ordered, %d discarded", len(likeliness), len(discarded))
    return likeliness, discarded
