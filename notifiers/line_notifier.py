"""
notifiers/line_notifier.py
透過 Line Messaging API 發送 Flex Message 異常通知

設定（.env）：
    LINE_CHANNEL_ACCESS_TOKEN=你的 channel access token
    LINE_USER_IDS=Uaaa,Ubbb   （逗號分隔，可多人）
"""

import logging
import requests

from config.settings import settings

logger = logging.getLogger(__name__)

LINE_API_URL = "https://api.line.me/v2/bot/message/push"


class LineNotifier:
    def __init__(self):
        self.token    = settings.line_channel_access_token
        self.user_ids = settings.line_user_id_list

        if not self.token:
            logger.warning("LINE_CHANNEL_TOKEN 未設定，Line 通知將無法發送")
        if not self.user_ids:
            logger.warning("LINE_USER_IDS 未設定，沒有收件人")

    # ──────────────────────────────────────────────────────────────
    # 公開方法
    # ──────────────────────────────────────────────────────────────

    def notify_anomaly(self, anomaly: dict) -> bool:
        """
        發送單一異常通知給所有收件人
        :param anomaly: 包含 ai_report 的異常 dict
        :return:        是否全部發送成功
        """
        if not self.token or not self.user_ids:
            logger.error("Line 設定不完整，跳過通知")
            return False

        flex = self._build_flex(anomaly)
        success = True
        for user_id in self.user_ids:
            ok = self._push(user_id, flex)
            if not ok:
                success = False
        return success

    def notify_all(self, anomalies: list[dict]) -> int:
        """
        批次發送所有異常通知
        :return: 成功發送的異常數量
        """
        if not anomalies:
            logger.info("無異常，不發送 Line 通知")
            return 0

        count = 0
        for anomaly in anomalies:
            if self.notify_anomaly(anomaly):
                count += 1

        logger.info(f"Line 通知發送完成：{count}/{len(anomalies)} 則成功")
        return count

    # ──────────────────────────────────────────────────────────────
    # 私有方法：組裝 Flex Message
    # ──────────────────────────────────────────────────────────────

    def _build_flex(self, anomaly: dict) -> dict:
        """組裝 Line Flex Message 卡片結構"""
        stock_id    = anomaly.get("stock_id", "")
        name        = anomaly.get("name", "")
        consecutive = anomaly.get("consecutive", 0)
        start_date  = anomaly.get("start_date", "")
        end_date    = anomaly.get("end_date", "")
        total_net   = anomaly.get("total_net", 0)
        ai_report   = anomaly.get("ai_report", "")

        # AI 分析拆行，最多 3 行
        ai_lines = [l.strip() for l in ai_report.splitlines() if l.strip()][:3]
        ai_contents = [
            {"type": "text", "text": line, "size": "xs", "color": "#555555", "wrap": True, "margin": "xs"}
            for line in ai_lines
        ] or [{"type": "text", "text": "（本次未啟用 AI 分析）", "size": "xs", "color": "#aaaaaa"}]

        return {
            "type": "flex",
            "altText": f"⚠️ {stock_id} {name} 連續 {consecutive} 天買超",
            "contents": {
                "type": "bubble",
                "size": "kilo",

                "header": {
                    "type": "box", "layout": "horizontal",
                    "backgroundColor": "#1A1A2E", "paddingAll": "14px",
                    "contents": [
                        {
                            "type": "box", "layout": "vertical",
                            "width": "36px", "height": "36px",
                            "cornerRadius": "18px", "backgroundColor": "#E24B4A",
                            "justifyContent": "center", "alignItems": "center",
                            "contents": [{"type": "text", "text": "⚠", "color": "#ffffff", "size": "lg"}],
                        },
                        {
                            "type": "box", "layout": "vertical", "margin": "md",
                            "contents": [
                                {"type": "text", "text": "法人異常買超通知", "color": "#ffffff", "size": "sm", "weight": "bold"},
                                {"type": "text", "text": f"{end_date} 自動偵測", "color": "#aab4c8", "size": "xxs", "margin": "xs"},
                            ],
                        },
                    ],
                },

                "body": {
                    "type": "box", "layout": "vertical", "paddingAll": "14px",
                    "contents": [
                        {
                            "type": "box", "layout": "horizontal", "alignItems": "center",
                            "contents": [
                                {"type": "text", "text": stock_id, "size": "xl", "weight": "bold", "color": "#1A1A2E", "flex": 0},
                                {
                                    "type": "box", "layout": "vertical",
                                    "backgroundColor": "#FCEBEB", "cornerRadius": "20px",
                                    "paddingStart": "8px", "paddingEnd": "8px",
                                    "paddingTop": "3px", "paddingBottom": "3px", "margin": "sm",
                                    "contents": [{"type": "text", "text": "連續買超", "size": "xxs", "color": "#A32D2D", "weight": "bold"}],
                                },
                            ],
                        },
                        {"type": "separator", "margin": "md", "color": "#f0f0f0"},
                        {
                            "type": "box", "layout": "vertical", "margin": "md", "spacing": "sm",
                            "contents": [
                                self._stat_row("法人",     name),
                                self._stat_row("連續買超", f"{consecutive} 天",          highlight=True),
                                self._stat_row("區間",     f"{start_date} ~ {end_date}"),
                                self._stat_row("累計買超", f"{total_net:,} 股",           highlight=True),
                            ],
                        },
                        {
                            "type": "box", "layout": "vertical",
                            "backgroundColor": "#f7f8fa", "cornerRadius": "10px",
                            "paddingAll": "10px", "margin": "md",
                            "contents": [
                                {"type": "text", "text": "AI 分析", "size": "xxs", "color": "#888888"},
                                *ai_contents,
                            ],
                        },
                    ],
                },

                "footer": {
                    "type": "box", "layout": "vertical", "paddingAll": "12px",
                    "contents": [{
                        "type": "button", "style": "primary", "color": "#06C755", "height": "sm",
                        "action": {
                            "type":  "uri",
                            "label": "查看更多分析",
                            "uri":   f"https://tw.stock.yahoo.com/quote/{stock_id}",
                        },
                    }],
                },
            },
        }

    def _stat_row(self, label: str, value: str, highlight: bool = False) -> dict:
        """數據列：label 左、value 右"""
        return {
            "type": "box", "layout": "horizontal",
            "contents": [
                {"type": "text", "text": label, "size": "xs", "color": "#888888", "flex": 2},
                {
                    "type": "text", "text": value, "size": "xs",
                    "color": "#E24B4A" if highlight else "#1A1A2E",
                    "weight": "bold" if highlight else "regular",
                    "flex": 3, "align": "end",
                },
            ],
        }

    # ──────────────────────────────────────────────────────────────
    # 私有方法：呼叫 Line API
    # ──────────────────────────────────────────────────────────────

    def _push(self, user_id: str, flex: dict) -> bool:
        """推送訊息給單一 user_id"""
        headers = {
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {self.token}",
        }
        payload = {"to": user_id, "messages": [flex]}
        try:
            resp = requests.post(LINE_API_URL, headers=headers, json=payload, timeout=10)
            if resp.status_code == 200:
                logger.info(f"Line 通知發送成功：{user_id}")
                return True
            else:
                logger.error(f"Line 通知發送失敗：{resp.status_code} {resp.text}")
                return False
        except Exception as e:
            logger.error(f"Line API 呼叫失敗：{e}")
            return False
