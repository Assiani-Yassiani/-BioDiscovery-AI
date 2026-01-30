"""
BioDiscovery AI - Main FastAPI Application
Multi-modal biological recommendation system
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging
import os

from app.api.routes import router
from app.config import get_settings
from app.core.qdrant_client import get_qdrant
from app.core.encoders import get_encoder


# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan events
    """
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    # Initialize components
    try:
        # Initialize Qdrant connection
        qdrant = get_qdrant()
        collections = qdrant.list_collections()
        logger.info(f"Connected to Qdrant. Collections: {collections}")

        # Pre-load encoders (optional, for faster first request)
        if os.getenv("PRELOAD_ENCODERS", "false").lower() == "true":
            logger.info("Pre-loading encoders...")
            encoder = get_encoder()
            _ = encoder.encode_text("test")
            logger.info("Encoders loaded")

    except Exception as e:
        logger.error(f"Startup error: {e}")

    yield

    # Shutdown
    logger.info("Shutting down...")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="""
    🧬 **BioDiscovery AI** - Multi-modal Biological Recommendation System
    
    A powerful system for discovering biological insights across multiple data types:
    - 🔬 Proteins (sequences, functions)
    - 📄 Articles (literature)
    - 🖼️ Images (pathways, profiles)
    - 📊 Experiments (GEO datasets)
    - 🔮 Structures (PDB, AlphaFold)
    
    ## Features
    - **Multi-modal input**: Text, sequence, image, or structure
    - **Hybrid search**: Vector + keyword search
    - **LLM-powered**: Gemini 2.5 Flash for intelligent analysis
    - **Design assistant**: Diverse candidate suggestions
    - **Evidence links**: Scientific traceability
    - **Neighbor graph**: Visual exploration
    """,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static/pdb", StaticFiles(directory="data/structures_pdb"), name="pdb")
app.mount(
    "/static/alphafold",
    StaticFiles(directory="data/structures_alphafold"),
    name="alphafold",
)
app.mount("/static/images", StaticFiles(directory="data/images"), name="images")
# Include API routes
app.include_router(router, prefix="/api/v1", tags=["API"])

# Serve static files (for images)
static_path = os.path.join(os.path.dirname(__file__), "..", "data", "files")
if os.path.exists(static_path):
    app.mount("/files", StaticFiles(directory=static_path), name="files")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/api/v1/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
