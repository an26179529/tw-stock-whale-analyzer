"""
analysis/technical_analyzer.py
技術面分析：KD 交叉、均線突破、成交量爆量、RSI
資料來源：daily_price 資料表
"""

import logging

import pandas as pd

from database.db import get_connection
from config.settings import settings

logger = logging.getLogger(__name__)

_MA_PERIODS = [5, 20, 60]
_KD_PERIOD  = 9
_RSI_PERIOD = 14


class TechnicalAnalyzer:
    def __init__(self):
        cfg = settings.anomaly_config
        self.volume_multiplier = cfg["volume_multiplier"]
        self.volume_ma_days    = cfg["volume_ma_days"]

    # ──────────────────────────────────────────────────────────────
    # 公開方法
    # ──────────────────────────────────────────────────────────────

    def analyze(self, stock_ids: list[str]) -> list[dict]:
        """
        分析所有股票的技術訊號
        回傳：每支有訊號的股票一筆 dict，包含各指標分數
        """
        results = []
        for stock_id in stock_ids:
            result = self._analyze_stock(stock_id)
            if result:
                results.append(result)
        logger.info(f"技術面分析完成，{len(results)}/{len(stock_ids)} 支有訊號")
        return results

    # ──────────────────────────────────────────────────────────────
    # 私有：單支股票分析
    # ──────────────────────────────────────────────────────────────

    def _analyze_stock(self, stock_id: str) -> dict | None:
        df = self._load_price_data(stock_id, days=90)
        if len(df) < _KD_PERIOD + 1:
            logger.warning(f"[{stock_id}] K線資料不足，跳過技術分析")
            return None

        df = self._enrich(df)

        signals = {
            "kd":     self._signal_kd(df),
            "ma":     self._signal_ma_breakout(df),
            "volume": self._signal_volume_surge(df),
            "rsi":    self._signal_rsi(df),
        }

        total_score = sum(s["score"] for s in signals.values())

        latest = df.iloc[-1]
        prev   = df.iloc[-2]
        change     = round(float(latest["close"] - prev["close"]), 2)
        change_pct = round(change / float(prev["close"]) * 100, 2) if prev["close"] else 0.0
        tail20     = df.tail(20)

        return {
            "stock_id":    stock_id,
            "close":       round(float(latest["close"]), 2),
            "ma20":        round(float(latest["ma20"]), 2) if not pd.isna(latest["ma20"]) else None,
            "change":      change,
            "change_pct":  change_pct,
            "support":     round(float(tail20["low"].min()), 2),
            "resistance":  round(float(tail20["high"].max()), 2),
            "trend_score": self._trend_score(latest),
            "date":        latest["date"],
            "tech_score":  total_score,
            "signals":     signals,
            "detail":      self._format_detail(stock_id, signals, latest),
        }

    # ──────────────────────────────────────────────────────────────
    # 私有：資料載入與指標計算
    # ──────────────────────────────────────────────────────────────

    def _load_price_data(self, stock_id: str, days: int) -> pd.DataFrame:
        conn = get_connection()
        try:
            df = pd.read_sql_query(
                """
                SELECT date, open, high, low, close, volume
                FROM daily_price
                WHERE stock_id = ?
                ORDER BY date ASC
                LIMIT ?
                """,
                conn,
                params=[stock_id, days],
            )
        except Exception as e:
            logger.error(f"[{stock_id}] 價格資料載入失敗：{e}")
            df = pd.DataFrame()
        finally:
            conn.close()
        return df

    def _enrich(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for p in _MA_PERIODS:
            df[f"ma{p}"] = df["close"].rolling(p).mean()
        df["vol_ma20"] = df["volume"].rolling(self.volume_ma_days).mean()
        df = self._calc_kd(df)
        df["rsi"] = self._calc_rsi(df)
        return df

    def _calc_kd(self, df: pd.DataFrame) -> pd.DataFrame:
        low_min  = df["low"].rolling(_KD_PERIOD).min()
        high_max = df["high"].rolling(_KD_PERIOD).max()
        rsv = (df["close"] - low_min) / (high_max - low_min).replace(0, 1) * 100
        df["k"] = rsv.ewm(com=2, adjust=False).mean()
        df["d"] = df["k"].ewm(com=2, adjust=False).mean()
        return df

    def _calc_rsi(self, df: pd.DataFrame) -> pd.Series:
        delta = df["close"].diff()
        gain  = delta.clip(lower=0).rolling(_RSI_PERIOD).mean()
        loss  = (-delta.clip(upper=0)).rolling(_RSI_PERIOD).mean()
        rs    = gain / loss.replace(0, 1)
        return 100 - 100 / (1 + rs)

    # ──────────────────────────────────────────────────────────────
    # 私有：訊號偵測
    # ──────────────────────────────────────────────────────────────

    def _signal_kd(self, df: pd.DataFrame) -> dict:
        if len(df) < 2:
            return {"triggered": False, "score": 0, "detail": ""}
        prev, curr = df.iloc[-2], df.iloc[-1]
        golden = prev["k"] < prev["d"] and curr["k"] >= curr["d"]
        death  = prev["k"] > prev["d"] and curr["k"] <= curr["d"]
        if golden:
            return {"triggered": True, "score": 20, "detail": f"KD 黃金交叉（K={curr['k']:.1f} D={curr['d']:.1f}）"}
        if death:
            return {"triggered": True, "score": -15, "detail": f"KD 死亡交叉（K={curr['k']:.1f} D={curr['d']:.1f}）"}
        return {"triggered": False, "score": 0, "detail": ""}

    def _signal_ma_breakout(self, df: pd.DataFrame) -> dict:
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        close = curr["close"]
        messages = []
        score = 0
        for p in _MA_PERIODS:
            ma_key = f"ma{p}"
            if pd.isna(curr[ma_key]):
                continue
            ma_val = curr[ma_key]
            crossed_up   = prev["close"] < prev[ma_key] and close >= ma_val
            crossed_down = prev["close"] > prev[ma_key] and close <= ma_val
            if crossed_up:
                bonus = 25 if p == 60 else (15 if p == 20 else 8)
                score += bonus
                messages.append(f"突破{p}日均線（{ma_val:.1f}）")
            elif crossed_down:
                penalty = -20 if p == 60 else (-12 if p == 20 else -5)
                score += penalty
                messages.append(f"跌破{p}日均線（{ma_val:.1f}）")
        return {
            "triggered": bool(messages),
            "score":     score,
            "detail":    "、".join(messages) if messages else "",
        }

    def _signal_volume_surge(self, df: pd.DataFrame) -> dict:
        curr = df.iloc[-1]
        if pd.isna(curr["vol_ma20"]) or curr["vol_ma20"] == 0:
            return {"triggered": False, "score": 0, "detail": ""}
        ratio = curr["volume"] / curr["vol_ma20"]
        if ratio >= self.volume_multiplier:
            score = min(int((ratio - 1) * 10), 25)
            return {
                "triggered": True,
                "score":     score,
                "detail":    f"成交量爆量（均量 {ratio:.1f}x）",
            }
        return {"triggered": False, "score": 0, "detail": ""}

    def _signal_rsi(self, df: pd.DataFrame) -> dict:
        rsi = df.iloc[-1]["rsi"]
        if pd.isna(rsi):
            return {"triggered": False, "score": 0, "detail": ""}
        if rsi <= 30:
            return {"triggered": True, "score": 15, "detail": f"RSI 超賣（{rsi:.1f}）"}
        if rsi >= 70:
            return {"triggered": True, "score": -10, "detail": f"RSI 超買（{rsi:.1f}）"}
        return {"triggered": False, "score": 0, "detail": ""}

    # ──────────────────────────────────────────────────────────────
    # 私有：格式化
    # ──────────────────────────────────────────────────────────────

    def _trend_score(self, latest: pd.Series) -> int:
        above = sum(
            1 for p in _MA_PERIODS
            if not pd.isna(latest.get(f"ma{p}")) and latest["close"] > latest[f"ma{p}"]
        )
        return int(above / len(_MA_PERIODS) * 100)

    def _format_detail(self, stock_id: str, signals: dict, latest: pd.Series) -> str:
        parts = [s["detail"] for s in signals.values() if s.get("detail")]
        return f"[{stock_id}] 技術評分 {sum(s['score'] for s in signals.values())} 分 ｜ " + "，".join(parts)
