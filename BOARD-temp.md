# BOARD (Temporary)

## LLM-COST-001: LLM Cost Tracking & Provider Abstraction

**Priority:** High
**Status:** Open

### Description

Implement comprehensive LLM usage monitoring, cost tracking, and a provider-agnostic abstraction layer. Currently all LLM calls go through OpenRouter using `google/gemini-2.5-flash`. This ticket covers:

1. **Research OpenRouter token usage metrics** — Investigate the OpenRouter API response format for token usage data (prompt tokens, completion tokens, total tokens, cost). Determine how to reliably extract these from each API call in `backend/services/vision.py`.

2. **Research Google AI (Gemini) direct API pricing** — Compare the cost of using Gemini models directly via the Google AI / Vertex AI API versus through OpenRouter. Document the price difference and determine if direct Google API access is cheaper for our usage patterns.

3. **Implement a provider-agnostic LLM client** — Refactor the current OpenRouter-specific code in `backend/services/vision.py` and `backend/config.py` into a provider abstraction layer that:
   - Supports OpenRouter and Google AI (Gemini) as backends
   - Is easily configurable via environment variable (e.g. `LLM_PROVIDER=openrouter|google`)
   - Exposes a unified interface for chat completions with vision support
   - Makes adding new providers straightforward in the future

4. **Implement token usage collection for both providers** — After each LLM call (label reading and ranking), capture token usage metrics from the provider response:
   - OpenRouter: extract from response `usage` field
   - Google AI: extract from Gemini API response metadata

5. **Persist LLM usage data in MongoDB** — Create a new `llm_usage` collection storing per-request records with:
   - `timestamp`
   - `provider` (openrouter / google)
   - `model` (e.g. `google/gemini-2.5-flash`)
   - `operation` (label_reading / ranking)
   - `prompt_tokens`
   - `completion_tokens`
   - `total_tokens`
   - `cost_usd` (calculated from provider pricing or reported by provider)
   - `batch_id` / `item_id` (optional, for traceability)
   - `cache_hit` (boolean — skip logging cost on cache hits)

6. **Expose usage summary endpoint** — Add a `GET /api/usage` route returning aggregated stats (total cost, cost per day, cost per model, average tokens per request, etc.).

### Acceptance Criteria

- [ ] OpenRouter token usage is captured and stored for every non-cached LLM call
- [ ] Google AI direct pricing is researched and documented (comparison with OpenRouter)
- [ ] If Google AI is cheaper, direct Gemini API support is implemented
- [ ] Provider is configurable via environment variable with no code changes needed to switch
- [ ] `vision.py` calls go through the abstraction layer, not directly to a provider
- [ ] MongoDB `llm_usage` collection persists all fields listed above
- [ ] Usage summary endpoint returns meaningful aggregated cost data
- [ ] Existing tests pass; new tests cover the abstraction layer and usage logging
- [ ] Cache hits do not generate cost entries

### Relevant Files

- `backend/config.py` — Model config, OpenRouter URL, prompts
- `backend/services/vision.py` — Current OpenRouter API calls (label reading + ranking)
- `backend/services/search.py` — Search pipeline orchestration
- `backend/repository/mongo.py` — MongoDB operations
- `backend/repository/models.py` — Data classes
