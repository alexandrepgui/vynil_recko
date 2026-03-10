import time
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import UPLOADS_DIR
from logger import get_logger, setup_logging
from routes.discogs_oauth import router as discogs_router
from routes.search import router as search_router
from routes.batch import router as batch_router
from routes.collection import router as collection_router
from routes.usage import router as usage_router

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env", override=True)
setup_logging()

log = get_logger("main")


app = FastAPI(title="Groove Log")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(discogs_router)
app.include_router(search_router)
app.include_router(batch_router)
app.include_router(collection_router)
app.include_router(usage_router)

UPLOADS_DIR.mkdir(exist_ok=True)
app.mount("/api/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    log.info("%s %s — %d in %.2fs", request.method, request.url.path, response.status_code, duration)
    return response
