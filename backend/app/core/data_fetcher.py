# backend/app/core/data_fetcher.py
import pandas as pd
import requests
import json
from datetime import datetime, timedelta
import os
import time
import random
from typing import Optional, Dict, Any, List, Tuple, Callable
import akshare as ak
import baostock as bs
import threading

from app.core.baostock_session import ensure_login
from app.core.board import is_bse_code
from app.core.config import settings
from app.core.source_priority import build_source_list

_bs_lock = threading.Lock()
FULL_HISTORY_START = "1990-01-01"


class StockDataFetcher:
    """股票数据获取器 - 整合你的代码"""

    FULL_HISTORY_START = FULL_HISTORY_START
    
    def __init__(self, cache_dir: str | None = None):
        root = cache_dir or settings.CACHE_DIR
        if os.path.basename(root.rstrip(os.sep)) == "klines":
            self.cache_dir = root
        else:
            self.cache_dir = os.path.join(root, "klines")
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def standardize_column_names(self, df: pd.DataFrame) -> pd.DataFrame:
        """标准化列名（使用你的代码）"""
        column_mapping = {
            '开盘价': 'open', '开盘': 'open',
            '最高价': 'high', '最高': 'high',
            '最低价': 'low', '最低': 'low',
            '收盘价': 'close', '收盘': 'close',
            '成交量': 'volume', '成交额': 'amount',
            '日期': 'timestamps', 'date': 'timestamps',
            '时间': 'timestamps', 'timestamp': 'timestamps'
        }
        
        # 重命名列
        df_columns = df.columns.tolist()
        new_columns = []
        
        for col in df_columns:
            col_lower = col.lower().strip()
            if col in column_mapping:
                new_columns.append(column_mapping[col])
            elif col_lower in column_mapping:
                new_columns.append(column_mapping[col_lower])
            else:
                if '开盘' in col or col == '开盘价':
                    new_columns.append('open')
                elif '最高' in col or col == '最高价':
                    new_columns.append('high')
                elif '最低' in col or col == '最低价':
                    new_columns.append('low')
                elif '收盘' in col or col == '收盘价':
                    new_columns.append('close')
                elif '成交额' in col:
                    new_columns.append('amount')
                elif '成交量' in col:
                    new_columns.append('volume')
                else:
                    new_columns.append(col)
        
        df.columns = new_columns
        
        # 只保留需要的列
        required_cols = ['open', 'high', 'low', 'close']
        optional_cols = ['volume', 'amount', 'timestamps']
        keep_cols = [col for col in required_cols + optional_cols if col in df.columns]
        
        return df[keep_cols] if keep_cols else df
    
    @staticmethod
    def _today_str() -> str:
        return datetime.now().strftime("%Y-%m-%d")

    @staticmethod
    def _last_trade_date(df: pd.DataFrame) -> str:
        if df is None or df.empty:
            return ""
        if "timestamps" in df.columns:
            return pd.to_datetime(df["timestamps"].iloc[-1]).strftime("%Y-%m-%d")
        if isinstance(df.index, pd.DatetimeIndex) or df.index.name == "timestamps":
            return pd.Timestamp(df.index[-1]).strftime("%Y-%m-%d")
        return ""

    @staticmethod
    def _first_trade_date(df: pd.DataFrame) -> str:
        if df is None or df.empty:
            return ""
        if "timestamps" in df.columns:
            return pd.to_datetime(df["timestamps"].iloc[0]).strftime("%Y-%m-%d")
        if isinstance(df.index, pd.DatetimeIndex) or df.index.name == "timestamps":
            return pd.Timestamp(df.index[0]).strftime("%Y-%m-%d")
        return ""

    def _full_cache_path(self, stock_code: str) -> str:
        code = str(stock_code).strip().zfill(6)
        return os.path.join(self.cache_dir, f"{code}_full.pkl")

    def _find_full_cache(
        self, stock_code: str
    ) -> tuple[str, pd.DataFrame] | tuple[None, None]:
        path = self._full_cache_path(stock_code)
        if not os.path.isfile(path):
            return None, None
        try:
            df = pd.read_pickle(path)
            if df is not None and len(df) >= 1:
                return path, df
        except Exception:
            return None, None
        return None, None

    @staticmethod
    def _merge_frames(old: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
        combined = pd.concat([old, new])
        if "timestamps" in combined.columns:
            combined = combined.drop_duplicates(subset=["timestamps"], keep="last")
            combined = combined.sort_values("timestamps")
        else:
            combined = combined[~combined.index.duplicated(keep="last")].sort_index()
        return combined

    def _slice_df_range(
        self, df: pd.DataFrame, start_date: str, end_date: str
    ) -> pd.DataFrame:
        if df is None or df.empty:
            return df
        out = df.copy()
        if "timestamps" in out.columns:
            ts = pd.to_datetime(out["timestamps"])
            mask = (ts >= pd.to_datetime(start_date)) & (ts <= pd.to_datetime(end_date))
            return out.loc[mask].copy()
        if isinstance(out.index, pd.DatetimeIndex) or out.index.name == "timestamps":
            idx = pd.to_datetime(out.index)
            mask = (idx >= pd.to_datetime(start_date)) & (idx <= pd.to_datetime(end_date))
            return out.loc[mask].copy()
        return out

    def sync_full_history(self, stock_code: str, *, quiet: bool = True) -> dict[str, Any]:
        """全量 pkl：无文件则拉上市至今；有文件则仅补 last+1 ~ 今日（差几天补几天）。"""
        code = str(stock_code).strip().zfill(6)
        path = self._full_cache_path(code)
        end_date = self._today_str()
        incremental = False
        gap_days = 0
        fetch_start = FULL_HISTORY_START
        bars_before = 0
        try:
            if os.path.isfile(path):
                df_old = pd.read_pickle(path)
                bars_before = len(df_old)
                last = self._last_trade_date(df_old)
                if last and len(df_old) >= 30:
                    last_key = last[:10]
                    if last_key >= end_date:
                        return {
                            "status": "skipped",
                            "symbol": code,
                            "bars": len(df_old),
                            "first_date": self._first_trade_date(df_old),
                            "last_date": last,
                            "cache_file": os.path.basename(path),
                            "incremental": False,
                            "gap_days": 0,
                            "message": "已包含今日数据",
                        }
                    last_dt = datetime.strptime(last_key, "%Y-%m-%d").date()
                    end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
                    gap_days = max(0, (end_dt - last_dt).days)
                    fetch_start = (last_dt + timedelta(days=1)).strftime("%Y-%m-%d")
                    incremental = True
                    if fetch_start > end_date:
                        return {
                            "status": "skipped",
                            "symbol": code,
                            "bars": len(df_old),
                            "first_date": self._first_trade_date(df_old),
                            "last_date": last,
                            "cache_file": os.path.basename(path),
                            "incremental": False,
                            "gap_days": 0,
                            "message": "无需更新",
                        }
                    df_new = self.get_from_baostock(code, fetch_start, end_date)
                    df = (
                        self._merge_frames(df_old, df_new)
                        if df_new is not None and not df_new.empty
                        else df_old
                    )
                else:
                    df = self.get_from_baostock(code, FULL_HISTORY_START, end_date)
                    fetch_start = FULL_HISTORY_START
            else:
                df = self.get_from_baostock(code, FULL_HISTORY_START, end_date)
                fetch_start = FULL_HISTORY_START

            if df is None or df.empty:
                return {"status": "failed", "symbol": code, "error": "无日K数据"}

            df.to_pickle(path)
            first_d = self._first_trade_date(df)
            last_d = self._last_trade_date(df)
            bars_added = len(df) - bars_before
            if not quiet:
                if incremental:
                    print(
                        f"增量K线 {code}: +{bars_added} 根 "
                        f"({fetch_start}~{end_date}, 落后 {gap_days} 天)"
                    )
                else:
                    print(f"全量K线已缓存: {code} {first_d} ~ {last_d} ({len(df)} bars)")
            return {
                "status": "ok",
                "symbol": code,
                "bars": len(df),
                "bars_added": bars_added,
                "first_date": first_d,
                "last_date": last_d,
                "cache_file": os.path.basename(path),
                "incremental": incremental,
                "gap_days": gap_days,
                "fetch_start": fetch_start,
                "fetch_end": end_date,
            }
        except Exception as e:
            return {"status": "failed", "symbol": code, "error": str(e)}

    def _cache_should_use(self, cache_file: str, end_date: str) -> bool:
        """日 K 请求包含今天时：缓存须较新且最后一根 bar 不早于 end_date。"""
        if not os.path.isfile(cache_file):
            return False
        age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(cache_file))
        today = self._today_str()
        if end_date >= today:
            if age.total_seconds() > 1800:
                return False
            try:
                df = pd.read_pickle(cache_file)
                last = self._last_trade_date(df)
                if last and last < end_date:
                    return False
            except Exception:
                return False
            return True
        return age.days < 1

    def _df_to_records(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        """将 DataFrame 转为 API 记录；日期若在 index 中则写入 timestamps 字段。"""
        out = df.copy()
        if "timestamps" not in out.columns:
            if out.index.name == "timestamps" or isinstance(out.index, pd.DatetimeIndex):
                out = out.reset_index()
                first_col = out.columns[0]
                if first_col != "timestamps":
                    out = out.rename(columns={first_col: "timestamps"})
        if "timestamps" in out.columns:
            out["timestamps"] = pd.to_datetime(out["timestamps"]).dt.strftime("%Y-%m-%d")
        records = out.to_dict(orient="records")
        return records

    def get_stock_market(self, stock_code: str) -> str:
        """判断市场类型"""
        if stock_code.startswith(('0', '2', '3')):
            return '0'  # 深交所
        elif stock_code.startswith(('6', '9')):
            return '1'  # 上交所
        else:
            return '1'  # 默认上交所
    
    def get_from_eastmoney(self, stock_code: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """从东方财富获取数据"""
        try:
            market = self.get_stock_market(stock_code)
            secid = f"{market}.{stock_code}"
            
            url = "http://push2his.eastmoney.com/api/qt/stock/kline/get"
            params = {
                'secid': secid,
                'fields1': 'f1,f2,f3,f4,f5,f6',
                'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
                'klt': '101',
                'fqt': '1',
                'beg': start_date.replace("-", ""),
                'end': end_date.replace("-", ""),
                'lmt': '10000',
                'ut': 'fa5fd1943c7b386f172d6893dbfba10b',
                'cb': f'jQuery{random.randint(1000000, 9999999)}_{int(time.time()*1000)}'
            }
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://quote.eastmoney.com/',
            }
            
            time.sleep(random.uniform(1, 2))
            response = requests.get(url, params=params, headers=headers, timeout=10)
            
            if response.status_code == 200:
                response_text = response.text
                start_idx = response_text.find('(')
                end_idx = response_text.rfind(')')
                
                if start_idx != -1 and end_idx != -1:
                    json_str = response_text[start_idx + 1:end_idx]
                    data = json.loads(json_str)
                    
                    if data and data.get('data') is not None:
                        klines = data['data'].get('klines', [])
                        stock_data = []
                        
                        for kline in klines:
                            try:
                                items = kline.split(',')
                                if len(items) >= 6:
                                    stock_data.append({
                                        'timestamps': items[0],
                                        'open': float(items[1]),
                                        'close': float(items[2]),
                                        'high': float(items[3]),
                                        'low': float(items[4]),
                                        'volume': float(items[5]),
                                        'amount': float(items[6]) if len(items) > 6 else 0,
                                    })
                            except (ValueError, IndexError):
                                continue
                        
                        if stock_data:
                            df = pd.DataFrame(stock_data)
                            df['timestamps'] = pd.to_datetime(df['timestamps'])
                            df.set_index('timestamps', inplace=True)
                            df = df.sort_index()
                            return self.standardize_column_names(df)
            return None
        except Exception as e:
            print(f"东方财富数据获取失败: {e}")
            return None
    
    def get_from_akshare(self, stock_code: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """从AKShare获取数据"""
        try:
            df = ak.stock_zh_a_hist(
                symbol=stock_code,
                period="daily",
                start_date=start_date.replace("-", ""),
                end_date=end_date.replace("-", ""),
                adjust="qfq"
            )
            
            if df is not None and not df.empty:
                column_mapping = {
                    '日期': 'timestamps',
                    '开盘': 'open',
                    '收盘': 'close',
                    '最高': 'high',
                    '最低': 'low',
                    '成交量': 'volume',
                    '成交额': 'amount',
                }
                
                actual_mapping = {k: v for k, v in column_mapping.items() if k in df.columns}
                df = df.rename(columns=actual_mapping)
                
                if 'timestamps' in df.columns:
                    df['timestamps'] = pd.to_datetime(df['timestamps'])
                    df.set_index('timestamps', inplace=True)
                elif '日期' in df.columns:
                    df['timestamps'] = pd.to_datetime(df['日期'])
                    df.set_index('timestamps', inplace=True)
                    df = df.drop('日期', axis=1, errors='ignore')
                
                df = df.sort_index()
                return self.standardize_column_names(df)
            return None
        except Exception as e:
            print(f"AKShare数据获取失败: {e}")
            return None
    
    def _baostock_full_code(self, stock_code: str) -> str:
        code = str(stock_code).strip().zfill(6)
        if is_bse_code(code):
            return f"bj.{code}"
        market = self.get_stock_market(code)
        return f"sz.{code}" if market == "0" else f"sh.{code}"

    def get_from_baostock(self, stock_code: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """从 Baostock 获取数据（单例登录，避免并发 login 导致 socket 异常）。"""
        try:
            with _bs_lock:
                if not ensure_login():
                    return None

                full_code = self._baostock_full_code(stock_code)
                rs = bs.query_history_k_data_plus(
                    full_code,
                    "date,open,high,low,close,volume,amount",
                    start_date=start_date,
                    end_date=end_date,
                    frequency="d",
                    adjustflag="2",
                )
                if getattr(rs, "error_code", "1") != "0":
                    return None
                fields = getattr(rs, "fields", None) or []
                if not fields:
                    return None

                data_list = []
                while (rs.error_code == "0") & rs.next():
                    data_list.append(rs.get_row_data())

            if data_list:
                df = pd.DataFrame(data_list, columns=fields)
                df['date'] = pd.to_datetime(df['date'])
                df['open'] = pd.to_numeric(df['open'])
                df['high'] = pd.to_numeric(df['high'])
                df['low'] = pd.to_numeric(df['low'])
                df['close'] = pd.to_numeric(df['close'])
                df['volume'] = pd.to_numeric(df['volume'])
                df['amount'] = pd.to_numeric(df['amount'])
                
                df = df.rename(columns={'date': 'timestamps'})
                df.set_index('timestamps', inplace=True)
                df = df.sort_index()
                return self.standardize_column_names(df)
            return None
        except Exception as e:
            print(f"Baostock数据获取失败: {e}")
            return None
    
    def _cache_response(
        self,
        cache_file: str,
        stock_code: str,
        start_date: str,
        end_date: str,
        df: pd.DataFrame | None = None,
    ) -> Dict[str, Any]:
        if df is None:
            df = pd.read_pickle(cache_file)
        last_trade = self._last_trade_date(df)
        return {
            "success": True,
            "data": self._df_to_records(df),
            "metadata": {
                "symbol": stock_code,
                "start_date": start_date,
                "end_date": end_date,
                "last_trade_date": last_trade,
                "data_count": len(df),
                "data_source": "cache",
                "cached": True,
                "cache_file": os.path.basename(cache_file),
            },
        }

    def _find_local_cache(
        self, stock_code: str, start_date: str, end_date: str
    ) -> tuple[str, pd.DataFrame] | tuple[None, None]:
        """匹配本地 pkl：优先精确文件名，否则复用同代码最新有效缓存。"""
        code = str(stock_code).strip().zfill(6)
        exact = os.path.join(self.cache_dir, f"{code}_{start_date}_{end_date}.pkl")
        if self._cache_should_use(exact, end_date):
            return exact, pd.read_pickle(exact)

        prefix = f"{code}_"
        candidates: list[tuple[float, str]] = []
        try:
            for fn in os.listdir(self.cache_dir):
                if fn.startswith(prefix) and fn.endswith(".pkl"):
                    path = os.path.join(self.cache_dir, fn)
                    if self._cache_should_use(path, end_date):
                        candidates.append((os.path.getmtime(path), path))
        except OSError:
            return None, None
        candidates.sort(reverse=True)
        for _mtime, path in candidates:
            try:
                df = pd.read_pickle(path)
                if df is not None and len(df) >= 30:
                    return path, df
            except Exception:
                continue
        return None, None

    def _find_relaxed_local_cache(
        self, stock_code: str
    ) -> tuple[str, pd.DataFrame] | tuple[None, None]:
        """选股等场景：优先全量 pkl，不校验新鲜度。"""
        full_path, full_df = self._find_full_cache(stock_code)
        if full_path and full_df is not None:
            return full_path, full_df
        code = str(stock_code).strip().zfill(6)
        prefix = f"{code}_"
        candidates: list[tuple[float, str]] = []
        try:
            for fn in os.listdir(self.cache_dir):
                if fn.startswith(prefix) and fn.endswith(".pkl"):
                    candidates.append(
                        (os.path.getmtime(os.path.join(self.cache_dir, fn)), fn)
                    )
        except OSError:
            return None, None
        candidates.sort(reverse=True)
        for _mtime, fn in candidates:
            path = os.path.join(self.cache_dir, fn)
            try:
                df = pd.read_pickle(path)
                if df is not None and len(df) >= 30:
                    return path, df
            except Exception:
                continue
        return None, None

    def get_stock_data(
        self,
        stock_code: str,
        start_date: str = None,
        end_date: str = None,
        data_source: str = None,
        cache_only: bool = False,
        quiet: bool = False,
    ) -> Dict[str, Any]:
        """获取股票数据。cache_only=True 时仅读本地 pkl，不访问外网。"""
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

        full_path, full_df = self._find_full_cache(stock_code)
        if full_df is not None:
            sliced = self._slice_df_range(full_df, start_date, end_date)
            if sliced is not None and len(sliced) >= 1:
                if not quiet:
                    print(f"从全量本地缓存加载: {os.path.basename(full_path)}")
                return self._cache_response(
                    full_path, stock_code, start_date, end_date, sliced
                )

        cache_path, df = self._find_local_cache(stock_code, start_date, end_date)
        if cache_path and df is not None:
            if not quiet:
                print(f"从本地缓存加载: {os.path.basename(cache_path)}")
            return self._cache_response(cache_path, stock_code, start_date, end_date, df)

        if cache_only:
            cache_path, df = self._find_relaxed_local_cache(stock_code)
            if cache_path and df is not None:
                if not quiet:
                    print(f"从本地缓存加载(宽松): {os.path.basename(cache_path)}")
                return self._cache_response(cache_path, stock_code, start_date, end_date, df)
            return {
                "success": False,
                "error": "无本地全量K线，请先在选股器点击「同步数据」拉取上市至今行情",
                "metadata": {
                    "symbol": stock_code,
                    "start_date": start_date,
                    "end_date": end_date,
                    "data_source": "cache",
                    "cached": False,
                },
            }

        source_attempts: List[Tuple[str, Callable]] = build_source_list(self, data_source)
        errors: List[str] = []

        for name, func in source_attempts:
            if not quiet:
                print(f"尝试从 {name} 获取数据...")
            try:
                df = func(stock_code, start_date, end_date)
            except Exception as e:
                errors.append(f"{name}: {e}")
                continue
            if df is not None and not df.empty:
                last_trade = self._last_trade_date(df)
                return {
                    "success": True,
                    "data": self._df_to_records(df),
                    "metadata": {
                        "symbol": stock_code,
                        "start_date": start_date,
                        "end_date": end_date,
                        "last_trade_date": last_trade,
                        "data_count": len(df),
                        "data_source": name,
                        "cached": False,
                        "persisted": False,
                        "source_order": [n for n, _ in source_attempts],
                    },
                }
            errors.append(f"{name}: 无数据")

        return {
            "success": False,
            "error": "无法从任何数据源获取数据",
            "metadata": {
                "symbol": stock_code,
                "start_date": start_date,
                "end_date": end_date,
                "data_source": "none",
                "attempts": errors,
                "source_order": [n for n, _ in source_attempts],
            },
        }