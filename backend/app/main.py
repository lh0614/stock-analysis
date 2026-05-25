# backend/app/main.py
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.cache_paths import bootstrap_cache
from app.core.baostock_session import logout as baostock_logout
from app.core.db import init_db
from app.api import (
    stock,
    analysis,
    workflow,
    strategy,
    settings as settings_api,
    watchlist,
    screener,
    news,
    alerts,
    universe,
)
from app.services.alerts import get_alert_service
from datetime import datetime

ALERT_POLL_SECONDS = 300


async def _alert_poll_loop():
    while True:
        await asyncio.sleep(ALERT_POLL_SECONDS)
        try:
            get_alert_service().evaluate_all()
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    cache_status = bootstrap_cache(settings.CACHE_DIR)
    app.state.cache_status = cache_status
    if cache_status.get("ok"):
        print(f"✓ 股票池数据目录: {cache_status['path']}")
    else:
        print(
            f"⚠ 股票池目录不可用: {cache_status.get('path')} "
            f"(readable={cache_status.get('readable')}, writable={cache_status.get('writable')})"
        )
        if cache_status.get("error"):
            print(f"  原因: {cache_status['error']}")
    init_db()
    task = asyncio.create_task(_alert_poll_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    baostock_logout()


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="股票分析系统API服务",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(
    stock.router,
    prefix=f"{settings.API_V1_STR}/stocks",
    tags=["stocks"]
)

app.include_router(
    analysis.router,
    prefix=f"{settings.API_V1_STR}/analysis",
    tags=["analysis"]
)

app.include_router(
    workflow.router,
    prefix=f"{settings.API_V1_STR}/workflows",
    tags=["workflows"]
)

app.include_router(
    strategy.router,
    prefix=f"{settings.API_V1_STR}/strategies",
    tags=["strategies"]
)

app.include_router(
    settings_api.router,
    prefix=f"{settings.API_V1_STR}/settings",
    tags=["settings"]
)

app.include_router(
    watchlist.router,
    prefix=f"{settings.API_V1_STR}/watchlist",
    tags=["watchlist"],
)

app.include_router(
    screener.router,
    prefix=f"{settings.API_V1_STR}/screener",
    tags=["screener"],
)

app.include_router(
    news.router,
    prefix=f"{settings.API_V1_STR}/news",
    tags=["news"],
)

app.include_router(
    alerts.router,
    prefix=f"{settings.API_V1_STR}/alerts",
    tags=["alerts"],
)

app.include_router(
    universe.router,
    prefix=f"{settings.API_V1_STR}/universe",
    tags=["universe"],
)

@app.get("/")
async def root():
    return {
        "message": "股票分析系统API服务已启动",
        "status": "running",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get(f"{settings.API_V1_STR}/health")
async def api_health_check():
    cache_status = getattr(app.state, "cache_status", None) or bootstrap_cache(
        settings.CACHE_DIR
    )
    healthy = cache_status.get("ok", False)
    return {
        "status": "healthy" if healthy else "degraded",
        "timestamp": datetime.now().isoformat(),
        "data_sources": settings.DATA_SOURCES,
        "cache_dir": cache_status.get("path"),
        "cache_access": {
            "readable": cache_status.get("readable"),
            "writable": cache_status.get("writable"),
            "ok": cache_status.get("ok"),
        },
    }