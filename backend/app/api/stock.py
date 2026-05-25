# backend/app/api/stock.py
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from typing import Optional
from datetime import datetime, timedelta
from app.core.data_fetcher import StockDataFetcher
from app.core.config import settings
from app.services.technical import compute_indicators
from app.services.export_data import build_export_payload, payload_to_csv, payload_to_json

router = APIRouter()
data_fetcher = StockDataFetcher(cache_dir=settings.CACHE_DIR)

@router.get("/{symbol}")
async def get_stock_data(
    symbol: str,
    start_date: Optional[str] = Query(None, description="开始日期，格式：YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期，格式：YYYY-MM-DD"),
    data_source: Optional[str] = Query(None, description="数据源：eastmoney/akshare/baostock")
):
    """
    获取股票历史数据
    """
    try:
        result = data_fetcher.get_stock_data(symbol, start_date, end_date, data_source)
        
        if result["success"]:
            return result
        else:
            raise HTTPException(status_code=404, detail=result["error"])
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取数据失败: {str(e)}")

@router.get("/{symbol}/indicators")
async def get_technical_indicators(
    symbol: str,
    indicators: str = Query("ma,macd,rsi", description="技术指标，逗号分隔")
):
    """
    计算技术指标
    """
    try:
        # 获取最近一年的数据
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        
        result = data_fetcher.get_stock_data(symbol, start_date, end_date)
        
        if not result["success"]:
            raise HTTPException(status_code=404, detail=result["error"])

        indicator_list = [x.strip() for x in indicators.split(",") if x.strip()]
        data = compute_indicators(result["data"], indicator_list)

        return {
            "symbol": symbol,
            "indicators": indicator_list,
            "data": data,
            "metadata": result.get("metadata"),
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"计算技术指标失败: {str(e)}")

@router.get("/{symbol}/summary")
async def get_stock_summary(symbol: str):
    """
    获取股票摘要信息
    """
    try:
        # 获取最近30天的数据
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        result = data_fetcher.get_stock_data(symbol, start_date, end_date)
        
        if not result["success"]:
            raise HTTPException(status_code=404, detail=result["error"])
        
        data = result["data"]
        if not data:
            raise HTTPException(status_code=404, detail="无数据")
        
        # 计算基本统计
        closes = [item["close"] for item in data]
        volumes = [item["volume"] for item in data if "volume" in item]
        
        latest = data[-1]
        first = data[0]
        
        price_change = latest["close"] - first["close"]
        price_change_pct = (price_change / first["close"]) * 100 if first["close"] > 0 else 0
        
        return {
            "symbol": symbol,
            "latest_price": latest["close"],
            "price_change": round(price_change, 2),
            "price_change_pct": round(price_change_pct, 2),
            "high_30d": max([item["high"] for item in data]),
            "low_30d": min([item["low"] for item in data]),
            "avg_volume": round(sum(volumes) / len(volumes), 2) if volumes else 0,
            "data_points": len(data),
            "period": f"{start_date} 至 {end_date}"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取股票摘要失败: {str(e)}")


@router.get("/{symbol}/export")
async def export_stock_data(
    symbol: str,
    format: str = Query("csv", pattern="^(csv|json)$"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    include_indicators: bool = Query(True),
):
    """Export OHLCV (+ optional indicators) as CSV or JSON."""
    try:
        payload = build_export_payload(
            data_fetcher, symbol, start_date, end_date, include_indicators
        )
        if format == "json":
            body = payload_to_json(payload)
            return Response(
                content=body,
                media_type="application/json",
                headers={
                    "Content-Disposition": f'attachment; filename="{symbol}_export.json"'
                },
            )
        body = payload_to_csv(payload)
        return Response(
            content=body.encode("utf-8-sig"),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{symbol}_export.csv"'
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")