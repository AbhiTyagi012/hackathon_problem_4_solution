import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import catalog, evaluate, health, logs, recommend, rules
from app.core.config import get_settings
from app.core.exceptions import PlatformError
from app.core.logging import get_logger, setup_logging

settings = get_settings()
setup_logging(settings.log_level)
logger = get_logger(__name__)

app = FastAPI(
    title=settings.app_name,
    description=(
        "Configurable decision automation platform, showcased as an e-commerce "
        "product recommendation engine. Rules are configured (not coded) and every "
        "decision returns a full explanation trace."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s -> %d (%.1fms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


@app.exception_handler(PlatformError)
async def platform_error_handler(request: Request, exc: PlatformError):
    content = {"error": exc.__class__.__name__, "message": exc.message}
    if exc.detail is not None:
        content["detail"] = exc.detail
    return JSONResponse(status_code=exc.status_code, content=content)


app.include_router(health.router)
app.include_router(rules.router)
app.include_router(recommend.router)
app.include_router(evaluate.router)
app.include_router(catalog.router)
app.include_router(logs.router)
