"""
collectors/data_collector.py
負責將 FinMind 資料拉取後寫入 SQLite 資料庫
目前支援：
  - 三大法人買賣超（免費）→ institutional_investors 表
  - 日K線              （免費）→ daily_price 表
"""

import logging
import sqlite3
from datetime import date, timedelta

import pandas as pd

from collectors.finmind_client import FinMindClient
from database.db import get_connection

logger = logging.getLogger(__name__)


class DataCollector:
    def __init__(self):
        # 初始化 FinMind 客戶端
        self.client = FinMindClient()

    # ──────────────────────────────────────────────────────────────
    # 公開方法
    # ──────────────────────────────────────────────────────────────

    def collect_institutional_investors(
        self,
        stock_id: str,
        start_date: str,
        end_date: str | None = None,
    ) -> int:
        """
        收集三大法人買賣超並寫入資料庫
        :param stock_id:   股票代號，例如 "2330"
        :param start_date: 起始日期，格式 "YYYY-MM-DD"
        :param end_date:   結束日期，預設今天
        :return:           寫入筆數
        """
        if end_date is None:
            end_date = date.today().strftime("%Y-%m-%d")

        logger.info(f"[{stock_id}] 開始收集三大法人資料：{start_date} ~ {end_date}")

        df = self.client.get_institutional_investors(stock_id, start_date, end_date)
        if df.empty:
            logger.warning(f"[{stock_id}] 無三大法人資料，跳過")
            return 0

        count = self._save_institutional_investors(df)
        logger.info(f"[{stock_id}] 三大法人資料寫入完成，共 {count} 筆")
        return count

    def collect_daily_price(
        self,
        stock_id: str,
        start_date: str,
        end_date: str | None = None,
    ) -> int:
        """
        收集日K線並寫入資料庫
        :param stock_id:   股票代號
        :param start_date: 起始日期
        :param end_date:   結束日期，預設今天
        :return:           寫入筆數
        """
        if end_date is None:
            end_date = date.today().strftime("%Y-%m-%d")

        logger.info(f"[{stock_id}] 開始收集日K線：{start_date} ~ {end_date}")

        df = self.client.get_daily_price(stock_id, start_date, end_date)
        if df.empty:
            logger.warning(f"[{stock_id}] 無K線資料，跳過")
            return 0

        count = self._save_daily_price(df)
        logger.info(f"[{stock_id}] K線資料寫入完成，共 {count} 筆")
        return count

    def collect_all(
        self,
        stock_id: str,
        start_date: str,
        end_date: str | None = None,
    ) -> dict:
        """
        一次收集單支股票的所有免費資料（法人 + K線）
        :return: {"institutional": 筆數, "price": 筆數}
        """
        result = {
            "institutional": self.collect_institutional_investors(stock_id, start_date, end_date),
            "price":         self.collect_daily_price(stock_id, start_date, end_date),
        }
        logger.info(f"[{stock_id}] 全部收集完成：{result}")
        return result

    def collect_multiple(
        self,
        stock_ids: list[str],
        start_date: str,
        end_date: str | None = None,
    ) -> dict:
        """
        批次收集多支股票
        :param stock_ids: 股票代號清單，例如 ["2330", "2454", "2317"]
        :return: {stock_id: {"institutional": 筆數, "price": 筆數}, ...}
        """
        results = {}
        total = len(stock_ids)
        for i, stock_id in enumerate(stock_ids, 1):
            logger.info(f"進度 {i}/{total}：{stock_id}")
            results[stock_id] = self.collect_all(stock_id, start_date, end_date)
        return results

    # ──────────────────────────────────────────────────────────────
    # 私有方法：寫入資料庫
    # ──────────────────────────────────────────────────────────────

    def _save_institutional_investors(self, df: pd.DataFrame) -> int:
        """
        將三大法人資料寫入 institutional_investors 表
        使用 INSERT OR IGNORE 避免重複寫入（依 UNIQUE(date, stock_id, name)）
        """
        conn = get_connection()
        count = 0
        try:
            cur = conn.cursor()
            for _, row in df.iterrows():
                cur.execute("""
                    INSERT OR IGNORE INTO institutional_investors
                        (date, stock_id, name, buy_vol, sell_vol, net_vol)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    row["date"],
                    row["stock_id"],
                    row["name"],
                    int(row.get("buy_vol", 0)),
                    int(row.get("sell_vol", 0)),
                    int(row.get("net_vol", 0)),
                ))
                if cur.rowcount > 0:
                    count += 1
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"三大法人資料寫入失敗：{e}")
            raise
        finally:
            conn.close()
        return count

    def _save_daily_price(self, df: pd.DataFrame) -> int:
        """
        將日K線寫入 daily_price 表
        使用 INSERT OR IGNORE 避免重複寫入（依 PRIMARY KEY (date, stock_id)）
        """
        conn = get_connection()
        count = 0
        try:
            cur = conn.cursor()
            for _, row in df.iterrows():
                cur.execute("""
                    INSERT OR IGNORE INTO daily_price
                        (date, stock_id, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    row["date"],
                    row["stock_id"],
                    float(row.get("open",  0) or 0),
                    float(row.get("high",  0) or 0),
                    float(row.get("low",   0) or 0),
                    float(row.get("close", 0) or 0),
                    int(row.get("volume",  0) or 0),
                ))
                if cur.rowcount > 0:
                    count += 1
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"K線資料寫入失敗：{e}")
            raise
        finally:
            conn.close()
        return count