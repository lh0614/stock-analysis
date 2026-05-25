# backend/app/core/config.py
from pathlib import Path
from typing import List

from pydantic import model_validator
from pydantic_settings import BaseSettings

from app.core.cache_paths import DEFAULT_STOCK_POOL_DIR, resolve_cache_dir


class Settings(BaseSettings):
    # API配置
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "股票分析系统"

    # CORS配置（开发环境）
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]

    # 数据源配置
    DATA_SOURCES: List[str] = ["eastmoney", "akshare", "baostock"]
    DEFAULT_DATA_SOURCE: str = "eastmoney"

    # 股票池数据根目录（默认：~/Documents/AI/stock-pool）
    CACHE_DIR: str = str(DEFAULT_STOCK_POOL_DIR)
    CACHE_EXPIRE_DAYS: int = 1

    class Config:
        env_file = ".env"

    @model_validator(mode="after")
    def _normalize_cache_dir(self) -> "Settings":
        object.__setattr__(self, "CACHE_DIR", resolve_cache_dir(self.CACHE_DIR))
        return self


settings = Settings()
