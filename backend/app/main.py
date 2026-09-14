import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi import _rate_limit_exceeded_handler

from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.limiter import limiter
from app.db.session import SessionLocal
from app.openai_compat.router import router as openai_router
from app.services.llm_client import get_llm_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mybuddy")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    llm_client = get_llm_client()
    startup_models = [settings.ollama_model, settings.ollama_embedding_model]
    if settings.ollama_code_model and settings.ollama_code_model != settings.ollama_model:
        startup_models.append(settings.ollama_code_model)
    if settings.ollama_vision_model and settings.ollama_vision_model not in startup_models:
        startup_models.append(settings.ollama_vision_model)
    for model in startup_models:
        try:
            await llm_client.ensure_model(model)
            logger.info("Ollama model '%s' is ready", model)
        except Exception as exc:  # noqa: BLE001 - startup should not crash if Ollama is briefly unavailable
            logger.warning("Could not verify/pull model '%s': %s", model, exc)
    yield


app = FastAPI(title="MyBuddy API", version="0.1.0", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")
app.include_router(openai_router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/version")
def version():
    return {"version": app.version}


@app.get("/ready")
async def ready():
    checks = {"database": False, "llm": False}

    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            checks["database"] = True
        finally:
            db.close()
    except Exception:  # noqa: BLE001 - readiness probe reports status, doesn't raise
        pass

    try:
        checks["llm"] = await get_llm_client().health()
    except Exception:  # noqa: BLE001
        pass

    all_ready = all(checks.values())
    return {"ready": all_ready, "checks": checks}
