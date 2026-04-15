from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from db.base import create_all_tables
from api.patients import router as patients_router
from api.studies import router as studies_router
from api.analysis import router as analysis_router
from api.pdf_studies import router as pdf_studies_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    Path(settings.PROCESSED_DIR).mkdir(parents=True, exist_ok=True)
    create_all_tables()
    yield
    # Shutdown (nothing to clean up for SQLite POC)


app = FastAPI(
    title="EEG AI Platform — MANAS-1 Demo",
    description="Clinical EEG analysis platform powered by MANAS-1 foundation model",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(patients_router)
app.include_router(studies_router)
app.include_router(pdf_studies_router)
app.include_router(analysis_router)


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0"}
