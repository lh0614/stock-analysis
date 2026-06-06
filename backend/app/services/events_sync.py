"""事件与公告同步（M13）。"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import akshare as ak
import pandas as pd

from app.core.data_paths import events_path
from app.services.data_store import read_parquet, write_parquet


def sync_symbol_events(symbol: str, limit: int = 20) -> list[dict[str, Any]]:
    code = symbol.zfill(6)[:6]
    rows: list[dict] = []
    try:
        df = ak.stock_news_em(symbol=code)
        if df is not None and not df.empty:
            for _, r in df.head(limit).iterrows():
                rows.append(
                    {
                        "symbol": code,
                        "event_date": str(r.get("发布时间", datetime.now().strftime("%Y-%m-%d")))[:10],
                        "event_id": str(uuid.uuid4()),
                        "type": "news",
                        "title": str(r.get("新闻标题", "")),
                        "url": str(r.get("新闻链接", "")),
                        "source": "akshare",
                    }
                )
    except Exception:
        pass
    return rows


def sync_events(symbols: list[str]) -> dict[str, Any]:
    all_rows: list[dict] = []
    for sym in symbols[:50]:
        all_rows.extend(sync_symbol_events(sym, limit=10))
    if all_rows:
        existing = read_parquet(events_path())
        combined = pd.concat([existing, pd.DataFrame(all_rows)], ignore_index=True) if not existing.empty else pd.DataFrame(all_rows)
        write_parquet(combined, events_path())
    return {"events": len(all_rows), "path": events_path()}


def recent_events(symbol: str, limit: int = 10) -> list[dict[str, Any]]:
    df = read_parquet(events_path())
    if df.empty:
        return sync_symbol_events(symbol, limit)
    sub = df[df["symbol"] == symbol.zfill(6)[:6]].tail(limit)
    return sub.to_dict("records")
