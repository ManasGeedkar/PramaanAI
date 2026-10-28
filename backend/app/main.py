from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from app.db import init_db, engine
from app.seed import seed_database_if_empty
from app.mock.router import router as mock_router
from app.api.applications import router as applications_router

import threading
from sqlmodel import select
from app.models import Application
from app.pipeline.run import run_pipeline
from app.api.evaluate import router as evaluate_router
from app.api.rules import router as rules_router
from app.api.documents import router as documents_router
from app.api.entities import router as entities_router
from app.api.reviews import router as reviews_router
from app.api.stats import router as stats_router
from app.api.audit import router as audit_router
from app.api.quality import router as quality_router

def run_all_background():
    with Session(engine) as session:
        # Only run for applications that are pending validation
        apps = session.exec(select(Application).where(Application.status == "processing")).all()
        for a in apps:
            try:
                run_pipeline(a.id, session)
            except Exception as e:
                print(f"Error in background pipeline run for app {a.id}: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite database tables
    init_db()
    # Seed initial 10 applications and documents if empty
    with Session(engine) as session:
        seed_database_if_empty(session)
    
    # Run all 10 applications in background on startup
    threading.Thread(target=run_all_background, daemon=True).start()
    yield

app = FastAPI(
    title="PramaanAI Scrutiny System",
    description="Backend API for AICTE Document & Approval Scrutiny System",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(mock_router)
app.include_router(applications_router)
app.include_router(evaluate_router)
app.include_router(rules_router)
app.include_router(documents_router)
app.include_router(entities_router)
app.include_router(reviews_router)
app.include_router(stats_router)
app.include_router(audit_router)
app.include_router(quality_router)


from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

if FRONTEND_DIST.exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/health")
def health():
    return {"status": "healthy"}


RESERVED_SPA_PREFIXES = ("api/", "mock/", "docs", "redoc", "openapi.json", "health")


@app.get("/{full_path:path}")
def serve_spa(full_path: str):
    clean_path = full_path.lstrip("/")

    # If the requested path starts with api/, mock/, docs, redoc, openapi.json or health,
    # return a JSON 404 rather than the SPA index.html
    for prefix in RESERVED_SPA_PREFIXES:
        base = prefix.rstrip("/")
        if clean_path == base or clean_path.startswith(f"{base}/"):
            raise HTTPException(status_code=404, detail="Not Found")

    if FRONTEND_DIST.exists():
        if clean_path:
            requested_file = FRONTEND_DIST / clean_path
            if requested_file.is_file():
                return FileResponse(requested_file)
        index_html = FRONTEND_DIST / "index.html"
        if index_html.is_file():
            return FileResponse(index_html)

    return {
        "service": "PramaanAI Backend",
        "status": "online",
        "docs_url": "/docs"
    }
