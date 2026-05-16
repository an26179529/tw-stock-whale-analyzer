"""
main.py
手動執行入口：收集資料 → 分析異常 → LLM 解讀 → Line 通知

用法：
    python main.py                            # 收集 7 天，分析全部法人
    python main.py --days 30                  # 收集 30 天
    python main.py --institution 外資          # 只分析外資
    python main.py --llm ollama               # 用 Ollama（預設）
    python main.py --llm openai               # 用 OpenAI
    python main.py --no-llm                   # 不呼叫 LLM
    python main.py --notify                   # 發送 Line 通知
    python main.py --collect-only             # 只收集
    python main.py --analyze-only             # 只分析（含通知）
    python main.py --analyze-only --llm ollama --notify  # 只分析，指定用 Ollama，並發送通知
    python main.py --analyze-only --institution 外資 --notify  # 只分析外資，並發送通知
"""

import argparse
import logging
from datetime import date, timedelta
from pathlib import Path

from database.db import init_db
from collectors.data_collector import DataCollector
from analysis.institutional_analyzer import InstitutionalAnalyzer
from analysis.technical_analyzer import TechnicalAnalyzer
from analysis.score_engine import ScoreEngine
from analysis.llm_analyzer import LLMAnalyzer
from notifiers.line_notifier import LineNotifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

WATCHLIST_PATH = Path(__file__).parent / "watchlist.txt"


def load_watchlist() -> list[str]:
    """讀取 watchlist.txt，忽略空行與 # 註解"""
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
    parser = argparse.ArgumentParser(description="台股大戶籌碼收集與分析")
    parser.add_argument("--days",        type=int, default=7,       help="往回收集幾天（預設 7）")
    parser.add_argument("--institution", nargs="+", default=None,   metavar="法人", help="指定法人，不填則全部")
    parser.add_argument("--llm",         choices=["ollama","openai"], default="ollama", help="LLM 選擇（預設 ollama）")
    parser.add_argument("--no-llm",      action="store_true",       help="不呼叫 LLM")
    parser.add_argument("--notify",      action="store_true",       help="發送 Line 通知")
    parser.add_argument("--collect-only",action="store_true",       help="只收集，不分析")
    parser.add_argument("--analyze-only",action="store_true",       help="只分析，不收集")
    return parser.parse_args()


def run_collect(stock_ids: list[str], start_date: str, end_date: str) -> None:
    """執行資料收集並印出摘要"""
    collector = DataCollector()
    results   = collector.collect_multiple(stock_ids, start_date, end_date)

    print("\n" + "=" * 44)
    print(f"  收集完成｜{start_date} ~ {end_date}")
    print("=" * 44)
    total_inst = total_price = 0
    for stock_id, r in results.items():
        inst  = r.get("institutional", 0)
        price = r.get("price", 0)
        total_inst  += inst
        total_price += price
        print(f"  {stock_id}  法人 {inst:>5} 筆  K線 {price:>4} 筆")
    print("-" * 44)
    print(f"  合計    法人 {total_inst:>5} 筆  K線 {total_price:>4} 筆")
    print("=" * 44)


def run_analyze(
    stock_ids: list[str],
    institutions: list[str] | None,
    llm_provider: str | None,
    notify: bool,
) -> None:
    """執行分析 → LLM 解讀 → Line 通知"""

    # 第一步：法人籌碼分析
    analyzer  = InstitutionalAnalyzer()
    anomalies = analyzer.analyze(stock_ids, institutions)

    # 第二步：技術面分析，將完整結果合併至異常清單
    tech_analyzer = TechnicalAnalyzer()
    tech_results  = {r["stock_id"]: r for r in tech_analyzer.analyze(stock_ids)}
    for a in anomalies:
        tech = tech_results.get(a["stock_id"])
        if tech:
            a["tech_score"]   = tech["tech_score"]
            a["tech_detail"]  = tech["detail"]
            a["tech_signals"] = tech["signals"]
            a["close"]        = tech["close"]
            a["ma20"]         = tech["ma20"]
            a["change"]       = tech["change"]
            a["change_pct"]   = tech["change_pct"]
            a["support"]      = tech["support"]
            a["resistance"]   = tech["resistance"]
            a["trend_score"]  = tech["trend_score"]

    # 第三步：綜合評分
    anomalies = ScoreEngine().score_all(anomalies)

    inst_label = "、".join(institutions) if institutions else "全部法人"
    print("\n" + "=" * 44)
    print(f"  分析完成｜{inst_label}")
    print("=" * 44)

    if not anomalies:
        print("  ✅ 無異常偵測到")
        print("=" * 44 + "\n")
        return

    for a in anomalies:
        print(f"  {a['score_detail']}")

    # 第二步：LLM 解讀
    if llm_provider:
        print(f"\n  📡 呼叫 {llm_provider} 解讀中...")
        print("-" * 44)
        llm     = LLMAnalyzer(provider=llm_provider)
        anomalies = llm.analyze_all(anomalies)   # 加上 ai_report 欄位

        for a in anomalies:
            if a.get("ai_report"):
                print(f"\n【{a['stock_id']} {a['name']}】")
                print(a["ai_report"])

    # 第三步：Line 通知
    if notify:
        print("\n  📲 發送 Line 通知...")
        notifier = LineNotifier()
        sent = notifier.notify_all(anomalies)
        print(f"  Line 通知：{sent}/{len(anomalies)} 則發送成功")

    print("\n" + "=" * 44 + "\n")


def main():
    args = parse_args()

    end_date   = date.today().strftime("%Y-%m-%d")
    start_date = (date.today() - timedelta(days=args.days)).strftime("%Y-%m-%d")

    init_db()

    stock_ids = load_watchlist()
    if not stock_ids:
        logger.error("股票清單為空，請確認 watchlist.txt")
        return

    llm_provider = None if args.no_llm else args.llm

    if not args.analyze_only:
        logger.info(f"收集區間：{start_date} ~ {end_date}（{args.days} 天）")
        run_collect(stock_ids, start_date, end_date)

    if not args.collect_only:
        run_analyze(stock_ids, args.institution, llm_provider, args.notify)


if __name__ == "__main__":
    main()