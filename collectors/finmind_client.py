import logging
import pandas as pd
from datetime import date, timedelta
from typing import Optional
from FinMind.data import DataLoader

from config.settings import settings

logger = logging.getLogger(__name__)

# FinMind 法人名稱（英文）→ 中文對照表
INSTITUTION_NAME_MAP = {
    "Foreign_Investor":    "外資",
    "Foreign_Dealer_Self": "外資自營",
    "Investment_Trust":    "投信",
    "Dealer_self":         "自營商（自行買賣）",
    "Dealer_Hedging":      "自營商（避險）",
    "Dealer":              "自營商",
}


class FinMindClient:
    def __init__(self):
        self.api = DataLoader()
        if settings.finmind_token:
            self.api.login_by_token(api_token=settings.finmind_token)
            logger.info("FinMind 登入成功")
        else:
            logger.warning("FinMind Token 未設定，使用匿名模式（有速率限制）")

    def get_broker_trades(
        self,
        stock_id: str,
        start_date: str,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """取得個股分點買賣明細（逐日抓取，需付費）"""
        if end_date is None:
            end_date = date.today().strftime("%Y-%m-%d")

        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        all_df = []

        current = start
        while current <= end:
            date_str = current.strftime("%Y-%m-%d")
            try:
                df = self.api.taiwan_stock_trading_daily_report(
                    stock_id=stock_id,
                    date=date_str,
                )
                if not df.empty:
                    all_df.append(df)
                    logger.info(f"[{stock_id}] {date_str} 取得 {len(df)} 筆")
            except Exception as e:
                logger.warning(f"[{stock_id}] {date_str} 失敗：{e}")
            current += timedelta(days=1)

        if not all_df:
            return pd.DataFrame()

        result = pd.concat(all_df, ignore_index=True)
        result = result.rename(columns={
            "date":                 "date",
            "stock_id":             "stock_id",
            "securities_trader_id": "broker_id",
            "securities_trader":    "broker_name",
            "buy_price":            "buy_price",
            "buy_volume":           "buy_vol",
            "sell_price":           "sell_price",
            "sell_volume":          "sell_vol",
        })

        for col in ["buy_price", "sell_price"]:
            result[col] = pd.to_numeric(result[col], errors="coerce").fillna(0)
        for col in ["buy_vol", "sell_vol"]:
            result[col] = pd.to_numeric(result[col], errors="coerce").fillna(0).astype(int)

        cols = ["date", "stock_id", "broker_id", "broker_name",
                "buy_price", "buy_vol", "sell_price", "sell_vol"]
        return result[[c for c in cols if c in result.columns]]

    def get_daily_price(
        self,
        stock_id: str,
        start_date: str,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """取得個股日K線"""
        if end_date is None:
            end_date = date.today().strftime("%Y-%m-%d")

        try:
            df = self.api.taiwan_stock_daily(
                stock_id=stock_id,
                start_date=start_date,
                end_date=end_date,
            )
        except Exception as e:
            logger.error(f"[{stock_id}] K線資料拉取失敗：{e}")
            return pd.DataFrame()

        if df.empty:
            return df

        # 實際欄位：date, stock_id, Trading_Volume, open, max, min, close, ...
        df = df.rename(columns={
            "max":            "high",
            "min":            "low",
            "Trading_Volume": "volume",
        })

        for col in ["open", "high", "low", "close"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["volume"] = pd.to_numeric(df.get("volume", 0), errors="coerce").fillna(0).astype(int)
        df["stock_id"] = stock_id

        return df[["date", "stock_id", "open", "high", "low", "close", "volume"]]

    def get_institutional_investors(
        self,
        stock_id: str,
        start_date: str,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        取得三大法人買賣超資料（免費）
        FinMind 實際欄位：date, stock_id, buy, name, sell
        name 為英文，透過 INSTITUTION_NAME_MAP 轉為中文
        回傳欄位：date, stock_id, name, buy_vol, sell_vol, net_vol
        """
        if end_date is None:
            end_date = date.today().strftime("%Y-%m-%d")

        try:
            df = self.api.taiwan_stock_institutional_investors(
                stock_id=stock_id,
                start_date=start_date,
                end_date=end_date,
            )
        except Exception as e:
            logger.error(f"[{stock_id}] 三大法人資料拉取失敗：{e}")
            return pd.DataFrame()

        if df.empty:
            logger.warning(f"[{stock_id}] {start_date}~{end_date} 三大法人無資料")
            return pd.DataFrame()

        # 對應實際欄位名稱：buy → buy_vol、sell → sell_vol
        df = df.rename(columns={
            "buy":  "buy_vol",
            "sell": "sell_vol",
        })

        # 數值轉換
        for col in ["buy_vol", "sell_vol"]:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

        # 自行計算買賣超（API 沒有 net 欄位）
        df["net_vol"] = df["buy_vol"] - df["sell_vol"]

        # 英文法人名稱轉中文
        df["name"] = df["name"].map(INSTITUTION_NAME_MAP).fillna(df["name"])

        df["stock_id"] = stock_id

        cols = ["date", "stock_id", "name", "buy_vol", "sell_vol", "net_vol"]
        return df[[c for c in cols if c in df.columns]]