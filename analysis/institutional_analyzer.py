"""
analysis/institutional_analyzer.py
分析三大法人買賣超，偵測連續買超異常

主要功能：
    - 計算每支股票每個法人的連續買超天數
    - 超過門檻天數則寫入 anomaly_log
"""

import logging
import sqlite3
from datetime import date

import pandas as pd

from database.db import get_connection
from config.settings import settings

logger = logging.getLogger(__name__)

# 所有支援的法人名稱
ALL_INSTITUTIONS = [
    "外資",
    "外資自營",
    "投信",
    "自營商（自行買賣）",
    "自營商（避險）",
    "自營商",
]


class InstitutionalAnalyzer:
    def __init__(self):
        # 從 settings 讀取門檻天數
        self.consecutive_days = settings.anomaly_config["consecutive_buy_days"]

    # ──────────────────────────────────────────────────────────────
    # 公開方法
    # ──────────────────────────────────────────────────────────────

    def analyze(
        self,
        stock_ids: list[str],
        institutions: list[str] | None = None,
    ) -> list[dict]:
        """
        分析指定股票清單的法人連續買超
        :param stock_ids:    股票代號清單
        :param institutions: 要分析的法人清單，None 代表全部
        :return:             偵測到的異常清單
        """
        if institutions is None:
            institutions = ALL_INSTITUTIONS

        logger.info(f"開始分析：{stock_ids}，法人：{institutions}，門檻：{self.consecutive_days} 天")

        all_anomalies = []
        for stock_id in stock_ids:
            anomalies = self._analyze_stock(stock_id, institutions)
            all_anomalies.extend(anomalies)

        logger.info(f"分析完成，共偵測到 {len(all_anomalies)} 個異常")
        return all_anomalies

    # ──────────────────────────────────────────────────────────────
    # 私有方法
    # ──────────────────────────────────────────────────────────────

    def _analyze_stock(
        self,
        stock_id: str,
        institutions: list[str],
    ) -> list[dict]:
        """分析單支股票，回傳異常清單"""
        df = self._load_data(stock_id, institutions)
        if df.empty:
            logger.warning(f"[{stock_id}] 無資料，跳過")
            return []

        anomalies = []
        # 每個法人分開計算連續買超
        for name, group in df.groupby("name"):
            result = self._detect_consecutive_buy(stock_id, name, group)
            if result:
                anomalies.append(result)
                self._save_anomaly(result)

        return anomalies

    def _load_data(
        self,
        stock_id: str,
        institutions: list[str],
    ) -> pd.DataFrame:
        """從資料庫載入法人買賣超資料，依日期排序"""
        conn = get_connection()
        try:
            # 用 IN 子句篩選指定法人
            placeholders = ",".join("?" * len(institutions))
            query = f"""
                SELECT date, stock_id, name, buy_vol, sell_vol, net_vol
                FROM institutional_investors
                WHERE stock_id = ?
                  AND name IN ({placeholders})
                ORDER BY name, date ASC
            """
            df = pd.read_sql_query(query, conn, params=[stock_id] + institutions)
        except Exception as e:
            logger.error(f"[{stock_id}] 資料載入失敗：{e}")
            df = pd.DataFrame()
        finally:
            conn.close()
        return df

    def _detect_consecutive_buy(
        self,
        stock_id: str,
        name: str,
        df: pd.DataFrame,
    ) -> dict | None:
        """
        計算連續買超天數
        連續買超：net_vol > 0
        回傳最新一段連續買超的資訊，若未達門檻則回傳 None
        """
        # 標記每一天是否買超
        df = df.copy()
        df["is_buy"] = df["net_vol"] > 0

        # 計算連續買超天數（從最新日往回數）
        consecutive = 0
        for is_buy in reversed(df["is_buy"].tolist()):
            if is_buy:
                consecutive += 1
            else:
                break  # 遇到非買超就停止

        if consecutive < self.consecutive_days:
            return None

        # 取得這段連續買超的資訊
        buy_streak = df.tail(consecutive)
        total_net  = int(buy_streak["net_vol"].sum())
        start_date = buy_streak.iloc[0]["date"]
        end_date   = buy_streak.iloc[-1]["date"]

        detail = (
            f"{name} 連續 {consecutive} 天買超，"
            f"區間：{start_date} ~ {end_date}，"
            f"累計買超：{total_net:,} 股"
        )
        logger.info(f"[{stock_id}] 偵測到異常：{detail}")

        return {
            "stock_id":    stock_id,
            "name":        name,
            "consecutive": consecutive,
            "total_net":   total_net,
            "start_date":  start_date,
            "end_date":    end_date,
            "detail":      detail,
        }

    def _save_anomaly(self, anomaly: dict) -> None:
        """將異常寫入 anomaly_log 資料表"""
        conn = get_connection()
        try:
            conn.execute("""
                INSERT INTO anomaly_log
                    (stock_id, broker_id, anomaly_type, detail)
                VALUES (?, ?, ?, ?)
            """, (
                anomaly["stock_id"],
                anomaly["name"],        # 用 broker_id 欄位存法人名稱
                "連續買超",
                anomaly["detail"],
            ))
            conn.commit()
            logger.info(f"[{anomaly['stock_id']}] 異常已寫入 anomaly_log")
        except Exception as e:
            conn.rollback()
            logger.error(f"anomaly_log 寫入失敗：{e}")
        finally:
            conn.close()
