import sqlite3
import logging
from config.settings import settings

logger = logging.getLogger(__name__)


def get_connection() -> sqlite3.Connection:
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(settings.db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_connection()
    try:
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS broker_trades (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                date        TEXT    NOT NULL,
                stock_id    TEXT    NOT NULL,
                broker_id   TEXT    NOT NULL,
                broker_name TEXT    NOT NULL,
                buy_price   REAL    DEFAULT 0,
                buy_vol     INTEGER DEFAULT 0,
                sell_price  REAL    DEFAULT 0,
                sell_vol    INTEGER DEFAULT 0,
                created_at  TEXT    DEFAULT (datetime('now','localtime')),
                UNIQUE(date, stock_id, broker_id)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS broker_positions (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_id     TEXT NOT NULL,
                broker_id    TEXT NOT NULL,
                broker_name  TEXT NOT NULL,
                avg_cost     REAL NOT NULL,
                net_vol      INTEGER NOT NULL,
                hold_days    INTEGER DEFAULT 1,
                first_buy    TEXT,
                last_updated TEXT,
                UNIQUE(stock_id, broker_id)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS daily_price (
                date     TEXT NOT NULL,
                stock_id TEXT NOT NULL,
                open     REAL,
                high     REAL,
                low      REAL,
                close    REAL,
                volume   INTEGER,
                PRIMARY KEY (date, stock_id)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS anomaly_log (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                detected_at  TEXT DEFAULT (datetime('now','localtime')),
                stock_id     TEXT NOT NULL,
                broker_id    TEXT,
                anomaly_type TEXT NOT NULL,
                detail       TEXT,
                ai_report    TEXT,
                notified     INTEGER DEFAULT 0
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS fetch_log (
                date       TEXT NOT NULL,
                stock_id   TEXT NOT NULL,
                fetched_at TEXT DEFAULT (datetime('now','localtime')),
                status     TEXT DEFAULT 'ok',
                PRIMARY KEY (date, stock_id)
            )
        """)

        conn.commit()
        logger.info(f"資料庫初始化完成：{settings.db_path}")

    except Exception as e:
        conn.rollback()
        logger.error(f"資料庫初始化失敗：{e}")
        raise
    finally:
        conn.close()