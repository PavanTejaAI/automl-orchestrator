from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from src.api.rest import auth
from src.config import config
from src.database import init_database, close_database
from src.utils import logger

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_database()
    logger.info("Application started")
    yield
    await close_database()
    logger.info("Application shutdown")

app = FastAPI(
    title="AutoML Orchestrator",
    description="Automated ML pipeline with AI agents",
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str

@app.get("/", response_model=HealthResponse, tags=["health"])
async def root():
    return {
        "status": "ok",
        "service": "AutoML Orchestrator",
        "version": "0.1.0"
    }

@app.get("/health", response_model=HealthResponse, tags=["health"], summary="Health Check", description="Check if the service is healthy and running")
async def health():
    return {
        "status": "healthy",
        "service": "AutoML Orchestrator",
        "version": "0.1.0"
    }


def main():
    logger.info("Starting Granian server", port=config.port)
    pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=config.port,
        reload=True,
        log_level="info"
    )
