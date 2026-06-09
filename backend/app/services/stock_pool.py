"""P2 stock pool adapter over the existing universe and local price store."""
from __future__ import annotations

from typing import Any

from app.services.data_store import read_daily_bars
from app.services.fundamentals_sync import get_valuation
from app.services.universe import get_universe_service


def get_all_symbols() -> list[dict[str, Any]]:
    return get_universe_service().query()


def get_stock_info(symbol: str) -> dict[str, Any] | None:
    code = symbol.zfill(6)[:6]
    items = get_universe_service().query(symbols=[code])
    base = items[0] if items else {"symbol": code, "name": code, "board": "unknown"}
    valuation = get_valuation(code).get("record") or {}
    bars = read_daily_bars(symbol=code)
    last_price = float(bars["close"].iloc[-1]) if not bars.empty else None
    return {
        **base,
        "industry": base.get("industry") or base.get("board") or "未知",
        "market_cap": valuation.get("market_cap") or 0,
        "last_price": last_price,
    }
