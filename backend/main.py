from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from database import init_db
from routers import sessions, schema, generate, settings, profiles
from app_config import MAX_VOLUME_RECORDS


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="AI Test Data Generator", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(schema.router, prefix="/api/schema", tags=["schema"])
app.include_router(generate.router, prefix="/api/generate", tags=["generate"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(profiles.router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/config")
async def get_config():
    """Return read-only application configuration for the frontend."""
    return {
        "max_volume_records": MAX_VOLUME_RECORDS,
    }
