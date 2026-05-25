"""News and announcements for a symbol."""
from __future__ import annotations

from datetime import datetime
from typing import Any

import akshare as ak
import pandas as pd


def _df_rows(df: pd.DataFrame, limit: int) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    rows = []
    for _, row in df.head(limit).iterrows():
        item = {str(k): (None if pd.isna(v) else str(v)) for k, v in row.items()}
        rows.append(item)
    return rows


def get_stock_news(symbol: str, limit: int = 20) -> list[dict[str, Any]]:
    """Eastmoney stock news via AKShare."""
    try:
        df = ak.stock_news_em(symbol=symbol)
        events = []
        for row in _df_rows(df, limit):
            title = row.get("新闻标题") or row.get("title") or ""
            pub = row.get("发布时间") or row.get("datetime") or ""
            url = row.get("新闻链接") or row.get("url") or ""
            source = row.get("文章来源") or row.get("source") or "东方财富"
            events.append(
                {
                    "type": "news",
                    "title": title,
                    "published_at": pub,
                    "url": url,
                    "source": source,
                    "sentiment": None,
                }
            )
        return events
    except Exception:
        return []


def get_stock_announcements(symbol: str, limit: int = 15) -> list[dict[str, Any]]:
    """Company announcements when available."""
    try:
        df = ak.stock_notice_report(symbol=symbol, date=datetime.now().strftime("%Y%m%d"))
        events = []
        for row in _df_rows(df, limit):
            title = row.get("公告标题") or row.get("title") or "公告"
            pub = row.get("公告日期") or row.get("date") or ""
            events.append(
                {
                    "type": "announcement",
                    "title": title,
                    "published_at": pub,
                    "url": row.get("公告链接") or "",
                    "source": "交易所公告",
                    "sentiment": None,
                }
            )
        return events
    except Exception:
        return []


def get_events_timeline(symbol: str, limit: int = 30) -> dict[str, Any]:
    news = get_stock_news(symbol, limit=limit)
    announcements = get_stock_announcements(symbol, limit=min(10, limit))
    merged = sorted(
        news + announcements,
        key=lambda x: x.get("published_at") or "",
        reverse=True,
    )[:limit]
    return {
        "symbol": symbol,
        "events": merged,
        "disclaimer": "资讯来源于公开渠道，仅供参考",
    }
