from __future__ import annotations

import base64
import hashlib
import io
import json
import os

from config import (
    CACHE_DIR,
    CACHE_MAX_ENTRIES,
    LABEL_READING_PROMPTS,
    MAX_RANKING_RESULTS,
    RANKING_PROMPTS,
    VISION_MODEL,
)
from logger import get_logger
from services.llm import LLMResponse, get_llm_client

log = get_logger("services.vision")


# ── LLM client singleton ────────────────────────────────────────────────────

_llm_client = None


def _get_client():
    global _llm_client
    if _llm_client is None:
        _llm_client = get_llm_client()
    return _llm_client


# ── Disk cache (LRU by mtime, keyed on image SHA-256) ───────────────────────

def _cache_path(image_bytes: bytes, media_type: str = "vinyl") -> "Path":
    from pathlib import Path
    key = hashlib.sha256(image_bytes + media_type.encode()).hexdigest()
    return Path(CACHE_DIR) / f"{key}.json"


def _read_cache(image_bytes: bytes, media_type: str = "vinyl") -> dict | None:
    path = _cache_path(image_bytes, media_type)
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


def _write_cache(image_bytes: bytes, label_data: dict, media_type: str = "vinyl") -> None:
    from pathlib import Path
    Path(CACHE_DIR).mkdir(parents=True, exist_ok=True)
    _evict_if_needed()
    path = _cache_path(image_bytes, media_type)
    path.write_text(json.dumps(label_data))
    log.info("Cache WRITE: %s", path.name)


def invalidate_cache(image_bytes: bytes, media_type: str = "vinyl") -> bool:
    """Remove the cache entry for the given image. Returns True if a file was deleted."""
    path = _cache_path(image_bytes, media_type)
    if path.exists():
        path.unlink()
        log.info("Cache INVALIDATE: %s", path.name)
        return True
    return False


def _evict_if_needed() -> None:
    from pathlib import Path
    cache_dir = Path(CACHE_DIR)
    entries = sorted(cache_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
    while len(entries) >= CACHE_MAX_ENTRIES:
        oldest = entries.pop(0)
        oldest.unlink()
        log.info("Cache EVICT: %s", oldest.name)


def _enhance_image(image_bytes: bytes, mime_type: str) -> tuple[bytes, str]:
    """Enhance label photo for better LLM readability.

    Applies auto-contrast and sharpening to improve text legibility on
    low-quality vinyl/CD label photos. Returns (enhanced_bytes, mime_type).
    """
    from PIL import Image, ImageEnhance, ImageOps

    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode != "RGB":
            img = img.convert("RGB")
        img = ImageOps.autocontrast(img, cutoff=1)
        img = ImageEnhance.Sharpness(img).enhance(1.5)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        log.debug("Image enhanced: %d → %d bytes", len(image_bytes), buf.tell())
        return buf.getvalue(), "image/jpeg"
    except Exception as e:
        log.warning("Image enhancement failed, using original: %s", e)
        return image_bytes, mime_type


def _chat(messages: list[dict]) -> tuple[str, list[dict], LLMResponse]:
    """Send messages to the LLM and return (response_text, updated_messages, llm_response)."""
    client = _get_client()
    log.debug("LLM request: model=%s messages=%d", VISION_MODEL, len(messages))
    response = client.chat(messages, model=VISION_MODEL)
    log.debug("LLM response length: %d chars", len(response.content))
    messages.append({"role": "assistant", "content": response.content})
    return response.content, messages, response


def _parse_json(raw: str) -> dict | list:
    cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        result = json.loads(cleaned)
        log.debug("JSON parsed successfully")
        return result
    except json.JSONDecodeError as e:
        log.error("JSON parse failed: %s — raw content: %.200s", e, cleaned)
        raise


def read_label_image(
    image_bytes: bytes, mime_type: str, media_type: str = "vinyl",
) -> tuple[dict, list[dict], bool, LLMResponse | None]:
    """Extract label metadata via vision.

    Returns (label_data, conversation_messages, cache_hit, llm_response).
    llm_response is None on cache hits.
    """
    log.info("Reading label image: size=%d bytes, mime=%s, media_type=%s", len(image_bytes), mime_type, media_type)

    # Enhance image for better LLM readability (cache key uses original bytes)
    enhanced_bytes, enhanced_mime = _enhance_image(image_bytes, mime_type)

    # Check cache first
    cached = _read_cache(image_bytes, media_type)
    if cached is not None:
        # Rebuild a minimal conversation so rank_results can append to it
        b64_image = base64.b64encode(enhanced_bytes).decode()
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{enhanced_mime};base64,{b64_image}"}},
                    {"type": "text", "text": "(label reading prompt — cached)"},
                ],
            },
            {"role": "assistant", "content": json.dumps(cached)},
        ]
        return cached, messages, True, None

    b64_image = base64.b64encode(enhanced_bytes).decode()

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{enhanced_mime};base64,{b64_image}"},
                },
                {"type": "text", "text": LABEL_READING_PROMPTS[media_type]},
            ],
        }
    ]

    raw, messages, llm_response = _chat(messages)
    label_data = _parse_json(raw)
    log.info(
        "Label extracted: albums=%s artists=%s",
        label_data.get("albums"), label_data.get("artists"),
    )

    _write_cache(image_bytes, label_data, media_type)

    return label_data, messages, False, llm_response


def rank_results(
    releases: list[dict],
    conversation: list[dict],
    media_type: str = "vinyl",
) -> tuple[list[int], list[int], LLMResponse]:
    """Ask the LLM to rank Discogs results using the same conversation context.

    Returns (likeliness_indexes, discarded_indexes, llm_response).
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
        "content": f"{RANKING_PROMPTS[media_type]}\n\n{json.dumps(candidates, indent=2)}",
    })

    raw, _, llm_response = _chat(conversation)
    try:
        result = _parse_json(raw)
    except json.JSONDecodeError:
        log.warning("LLM returned non-JSON during ranking, treating as 'discard all'")
        all_indexes = list(range(len(candidates)))
        return [], all_indexes, llm_response
    likeliness = result.get("likeliness", [])
    discarded = result.get("discarded", [])
    log.info("Ranking complete: %d ordered, %d discarded", len(likeliness), len(discarded))
    return likeliness, discarded, llm_response
