# Groove Log

Identify vinyl records by photographing their labels. Upload an image, and the app uses vision AI to extract metadata (artist, album, catalog number, etc.), then searches the [Discogs](https://www.discogs.com/) database to find matching releases. Results are ranked by relevance and can be added directly to your Discogs collection.

## Features

- **Single search** — Upload one label image to identify a record
- **Batch processing** — Upload a ZIP of label images for bulk identification
- **Review queue** — Unified view to confirm results and update your collection
- **Smart search strategy** — Multi-stage fallback (catalog number → artist/album → fuzzy matching) with LLM-powered ranking

## Tech Stack

| Layer | Stack |
|-------|-------|
| Backend | Python, FastAPI, MongoDB |
| Frontend | React 19, TypeScript, Vite |
| AI | OpenRouter (Gemini, GPT-4o, Claude, etc.) |
| Database | MongoDB (via Docker Compose) |

## Getting Started

### Prerequisites

- Python 3.x
- Node.js
- Docker (for MongoDB)

### Setup

1. Copy `.env.example` to `.env` and fill in your keys:
   - `DISCOGS_TOKEN` — [Discogs personal access token](https://www.discogs.com/settings/developers)
   - `OPENROUTER_API_KEY` — [OpenRouter API key](https://openrouter.ai/)

2. Start MongoDB:
   ```bash
   docker-compose up -d
   ```

3. Install dependencies and run:
   ```bash
   make install
   make dev
   ```

   Backend runs on `http://localhost:8000`, frontend on `http://localhost:5173`.

### Other Commands

```bash
make backend    # Backend only
make frontend   # Frontend only
make test       # Run tests
make stop       # Stop services
```

## Project Structure

```
backend/
├── routes/         # API endpoints (search, batch)
├── services/       # Vision AI, Discogs API, search pipeline
├── repository/     # MongoDB operations
└── tests/

frontend/
├── src/
│   ├── components/ # UI components
│   ├── api.ts      # Backend API calls
│   └── types.ts    # TypeScript interfaces
└── vite.config.ts
```
