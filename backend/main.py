import time
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from logger import get_logger, setup_logging
from routes.search import router as search_router
from routes.batch import router as batch_router

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env", override=True)
setup_logging()

log = get_logger("main")

app = FastAPI(title="Vinyl Recko")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search_router)
app.include_router(batch_router)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    log.info("%s %s — %d in %.2fs", request.method, request.url.path, response.status_code, duration)
    return response
