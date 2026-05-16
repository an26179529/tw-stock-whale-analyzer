"""
analysis/score_engine.py
綜合評分引擎：法人籌碼分 + 技術面分 → 0-100 總分 → 偏多/觀望/偏空訊號
"""

import logging

logger = logging.getLogger(__name__)

# 法人權重：影響力越高，連續買超的分數越重
_INSTITUTION_WEIGHT: dict[str, float] = {
    "外資":           1.5,
    "外資自營":        1.2,
    "投信":           1.2,
    "自營商（自行買賣）": 0.8,
    "自營商（避險）":   0.6,
    "自營商":          0.7,
}

# 連續買超天數 → 基礎分（上限 45，乘上法人權重後 cap 50）
_CONSECUTIVE_SCORE: list[tuple[int, int]] = [
    (10, 45),
    (7,  35),
    (5,  25),
    (3,  15),
    (1,  5),
]

# 訊號閾值
_SIGNAL_BULLISH  = 65
_SIGNAL_BEARISH  = 35
_STOP_LOSS_PCT   = 0.05   # ma20 不存在時，用收盤價 -5%


class ScoreEngine:
    """
    輸入：anomaly dict（含 tech_score、close、ma20）
    輸出：score_result dict，附加到原始 anomaly
    """

    def score_all(self, anomalies: list[dict]) -> list[dict]:
        results = []
        for a in anomalies:
            scored = {**a, **self.score(a)}
            results.append(scored)
            logger.info(
                f"[{a['stock_id']}] 總評分 {scored['total_score']} → {scored['signal']}"
            )
        return results

    def score(self, anomaly: dict) -> dict:
        inst_score = self._institutional_score(anomaly)
        tech_score = max(-30, min(50, anomaly.get("tech_score", 0)))
        raw        = inst_score + tech_score
        total      = max(0, min(100, raw))
        signal     = self._to_signal(total)
        stop_loss  = self._stop_loss(anomaly)
        sub_scores = self._sub_scores(anomaly, inst_score, tech_score)

        return {
            "inst_score":  inst_score,
            "tech_score":  tech_score,
            "total_score": total,
            "signal":      signal,
            "stop_loss":   stop_loss,
            "sub_scores":  sub_scores,
            "score_detail": self._format_detail(anomaly, inst_score, tech_score, total, signal, stop_loss),
        }

    # ──────────────────────────────────────────────────────────────
    # 法人評分
    # ──────────────────────────────────────────────────────────────

    def _institutional_score(self, anomaly: dict) -> int:
        days   = anomaly.get("consecutive", 0)
        name   = anomaly.get("name", "")
        weight = _INSTITUTION_WEIGHT.get(name, 1.0)

        base = 0
        for threshold, pts in _CONSECUTIVE_SCORE:
            if days >= threshold:
                base = pts
                break

        return min(50, int(base * weight))

    # ──────────────────────────────────────────────────────────────
    # 訊號與停損
    # ──────────────────────────────────────────────────────────────

    def _sub_scores(self, anomaly: dict, inst_score: int, tech_score: int) -> dict:
        consecutive = anomaly.get("consecutive", 0)
        return {
            "籌碼動能": min(consecutive * 10, 100),
            "法人動向": min(inst_score * 2, 100),
            "技術面":   max(0, min(100, tech_score + 50)),
            "趨勢強度": anomaly.get("trend_score", 0),
        }

    def _to_signal(self, score: int) -> str:
        if score >= _SIGNAL_BULLISH:
            return "偏多"
        if score <= _SIGNAL_BEARISH:
            return "偏空"
        return "觀望"

    def _stop_loss(self, anomaly: dict) -> float | None:
        close = anomaly.get("close")
        if not close:
            return None
        ma20 = anomaly.get("ma20")
        if ma20 and ma20 < close:
            return round(ma20, 2)
        return round(close * (1 - _STOP_LOSS_PCT), 2)

    # ──────────────────────────────────────────────────────────────
    # 格式化
    # ──────────────────────────────────────────────────────────────

    def _format_detail(
        self,
        anomaly: dict,
        inst_score: int,
        tech_score: int,
        total: int,
        signal: str,
        stop_loss: float | None,
    ) -> str:
        stock_id   = anomaly.get("stock_id", "")
        close      = anomaly.get("close")
        inst_name   = anomaly.get("name", "")
        signal_icon = {"偏多": "📈", "觀望": "📊", "偏空": "📉"}.get(signal, "")
        close_str   = f"{close}" if close is not None else "N/A"
        sl_str      = f"  停損參考 {stop_loss}" if stop_loss else ""

        return (
            f"[{stock_id}｜{inst_name}] {signal_icon} {signal}  "
            f"總分 {total}/100（法人 {inst_score} + 技術 {tech_score:+d}）"
            f"  現價 {close_str}{sl_str}"
        )
