"""
main.py
手動執行入口，收集資料並分析法人連續買超

用法：
    python main.py                        # 收集最近 7 天，分析全部法人
    python main.py --days 30              # 收集最近 30 天
    python main.py --institution 外資      # 只分析外資
    python main.py --institution 外資 投信 # 分析外資和投信
    python main.py --collect-only         # 只收集，不分析
    python main.py --analyze-only         # 只分析，不收集
"""

import argparse
import logging
from datetime import date, timedelta
from pathlib import Path

from database.db import init_db
from collectors.data_collector import DataCollector
from analysis.institutional_analyzer import InstitutionalAnalyzer

# ── logging 設定 ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

# watchlist 路徑（與 main.py 同目錄）
WATCHLIST_PATH = Path(__file__).parent / "watchlist.txt"


def load_watchlist() -> list[str]:
    """
    讀取 watchlist.txt，回傳股票代號清單
    忽略空行與 # 開頭的註解行
    """
    if not WATCHLIST_PATH.exists():
        logger.error(f"找不到股票清單：{WATCHLIST_PATH}")
        return []

    stock_ids = []
    for line in WATCHLIST_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            stock_ids.append(line)

    logger.info(f"載入股票清單：{stock_ids}")
    return stock_ids


def parse_args() -> argparse.Namespace:
    """解析命令列參數"""
    parser = argparse.ArgumentParser(description="台股大戶籌碼收集與分析")
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="往回收集幾天的資料（預設 7 天）",
    )
    parser.add_argument(
        "--institution",
        nargs="+",          # 接受一個或多個值
        default=None,       # None 代表全部法人
        metavar="法人名稱",
        help="要分析的法人（例如：外資 投信），不指定則分析全部",
    )
    parser.add_argument(
        "--collect-only",
        action="store_true",
        help="只收集資料，不執行分析",
    )
    parser.add_argument(
        "--analyze-only",
        action="store_true",
        help="只執行分析，不收集新資料",
    )
    return parser.parse_args()


def run_collect(stock_ids: list[str], start_date: str, end_date: str) -> None:
    """執行資料收集，並印出摘要"""
    collector = DataCollector()
    results   = collector.collect_multiple(stock_ids, start_date, end_date)

    print("\n" + "=" * 44)
    print(f"  收集完成｜{start_date} ~ {end_date}")
    print("=" * 44)
    total_inst  = 0
    total_price = 0
    for stock_id, result in results.items():
        inst  = result.get("institutional", 0)
        price = result.get("price", 0)
        total_inst  += inst
        total_price += price
        print(f"  {stock_id}  法人 {inst:>5} 筆  K線 {price:>4} 筆")
    print("-" * 44)
    print(f"  合計    法人 {total_inst:>5} 筆  K線 {total_price:>4} 筆")
    print("=" * 44)


def run_analyze(stock_ids: list[str], institutions: list[str] | None) -> None:
    """執行分析，並印出異常摘要"""
    analyzer  = InstitutionalAnalyzer()
    anomalies = analyzer.analyze(stock_ids, institutions)

    print("\n" + "=" * 44)
    inst_label = "、".join(institutions) if institutions else "全部法人"
    print(f"  分析完成｜{inst_label}")
    print("=" * 44)
    if not anomalies:
        print("  ✅ 無異常偵測到")
    else:
        for a in anomalies:
            print(f"  ⚠️  {a['detail']}")
    print("=" * 44 + "\n")


def main():
    args = parse_args()

    # 計算日期區間
    end_date   = date.today().strftime("%Y-%m-%d")
    start_date = (date.today() - timedelta(days=args.days)).strftime("%Y-%m-%d")

    # 初始化資料庫
    init_db()

    # 載入股票清單
    stock_ids = load_watchlist()
    if not stock_ids:
        logger.error("股票清單為空，請確認 watchlist.txt")
        return

    # 收集
    if not args.analyze_only:
        logger.info(f"收集區間：{start_date} ~ {end_date}（{args.days} 天）")
        run_collect(stock_ids, start_date, end_date)

    # 分析
    if not args.collect_only:
        run_analyze(stock_ids, args.institution)


if __name__ == "__main__":
    main()