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

    _SIGNAL_THEME = {
        "偏多": {"header_bg": "#0D3B26", "bar_color": "#2ECC71", "badge_bg": "#E8F5E9", "badge_text": "#27AE60", "icon": "📈", "change_color": "#27AE60"},
        "觀望": {"header_bg": "#2C2C3E", "bar_color": "#F39C12", "badge_bg": "#FFF8E1", "badge_text": "#E67E22", "icon": "📊", "change_color": "#E67E22"},
        "偏空": {"header_bg": "#3D0F0F", "bar_color": "#E74C3C", "badge_bg": "#FCEBEB", "badge_text": "#A32D2D", "icon": "📉", "change_color": "#E74C3C"},
    }

    def _build_flex(self, anomaly: dict) -> dict:
        stock_id    = anomaly.get("stock_id", "")
        name        = anomaly.get("name", "")
        consecutive = anomaly.get("consecutive", 0)
        start_date  = anomaly.get("start_date", "")
        end_date    = anomaly.get("end_date", "")
        total_net   = anomaly.get("total_net", 0)
        ai_report   = anomaly.get("ai_report", "")
        total_score = anomaly.get("total_score", 0)
        signal      = anomaly.get("signal", "觀望")
        stop_loss   = anomaly.get("stop_loss")
        close       = anomaly.get("close")
        change      = anomaly.get("change", 0) or 0
        change_pct  = anomaly.get("change_pct", 0) or 0
        support     = anomaly.get("support")
        resistance  = anomaly.get("resistance")
        sub_scores  = anomaly.get("sub_scores", {})

        theme       = self._SIGNAL_THEME.get(signal, self._SIGNAL_THEME["觀望"])
        close_str   = f"{close}" if close is not None else "N/A"
        sl_str      = f"{stop_loss}" if stop_loss is not None else "N/A"
        sup_str     = f"{support}" if support is not None else "N/A"
        res_str     = f"{resistance}" if resistance is not None else "N/A"
        arrow       = "▲" if change >= 0 else "▼"
        change_str  = f"{arrow} {abs(change):.2f} ({abs(change_pct):.2f}%)"

        ai_lines = [l.strip() for l in ai_report.splitlines() if l.strip()][:4]
        ai_contents = [
            {"type": "text", "text": line, "size": "xs", "color": "#444444", "wrap": True, "margin": "xs"}
            for line in ai_lines
        ] or [{"type": "text", "text": "（本次未啟用 AI 分析）", "size": "xs", "color": "#aaaaaa"}]

        return {
            "type": "flex",
            "altText": f"{theme['icon']} {stock_id} {name}｜{signal} {total_score}/100",
            "contents": {
                "type": "bubble",
                "size": "mega",

                # ── Header ─────────────────────────────────────────
                "header": {
                    "type": "box", "layout": "vertical",
                    "backgroundColor": theme["header_bg"],
                    "paddingAll": "16px",
                    "contents": [
                        {
                            "type": "box", "layout": "horizontal", "alignItems": "center",
                            "contents": [
                                {
                                    "type": "box", "layout": "vertical",
                                    "width": "40px", "height": "40px", "cornerRadius": "20px",
                                    "backgroundColor": "#ffffff22",
                                    "justifyContent": "center", "alignItems": "center",
                                    "contents": [{"type": "text", "text": "📊", "size": "lg"}],
                                },
                                {
                                    "type": "box", "layout": "vertical", "margin": "md",
                                    "contents": [
                                        {"type": "text", "text": "台股大戶偵測", "color": "#ffffff", "size": "md", "weight": "bold"},
                                        {"type": "text", "text": f"🗓 {end_date} 自動偵測", "color": "#aab4c8", "size": "xxs", "margin": "xs"},
                                    ],
                                },
                            ],
                        },
                    ],
                },

                # ── Body ───────────────────────────────────────────
                "body": {
                    "type": "box", "layout": "vertical", "paddingAll": "0px", "spacing": "none",
                    "contents": [

                        # 1. 股票代號 + 訊號 + 現價漲跌
                        {
                            "type": "box", "layout": "horizontal",
                            "paddingAll": "16px", "paddingBottom": "10px", "alignItems": "center",
                            "contents": [
                                {
                                    "type": "box", "layout": "vertical", "flex": 3,
                                    "contents": [
                                        {
                                            "type": "box", "layout": "horizontal", "alignItems": "center",
                                            "contents": [
                                                {"type": "text", "text": stock_id, "size": "xxl", "weight": "bold", "color": "#1A1A2E", "flex": 0},
                                                {
                                                    "type": "box", "layout": "vertical", "margin": "sm",
                                                    "backgroundColor": theme["badge_bg"], "cornerRadius": "20px",
                                                    "paddingStart": "10px", "paddingEnd": "10px",
                                                    "paddingTop": "3px", "paddingBottom": "3px",
                                                    "contents": [{"type": "text", "text": f"{theme['icon']} {signal}", "size": "xxs", "color": theme["badge_text"], "weight": "bold"}],
                                                },
                                            ],
                                        },
                                        {"type": "text", "text": name, "size": "xs", "color": "#888888", "margin": "xs"},
                                    ],
                                },
                                {
                                    "type": "box", "layout": "vertical", "flex": 2, "alignItems": "flex-end",
                                    "contents": [
                                        {"type": "text", "text": close_str, "size": "xl", "weight": "bold", "color": theme["change_color"], "align": "end"},
                                        {"type": "text", "text": change_str, "size": "xxs", "color": theme["change_color"], "align": "end", "margin": "xs"},
                                    ],
                                },
                            ],
                        },

                        # 2. 綜合評分 + 四維度小條
                        {
                            "type": "box", "layout": "vertical",
                            "backgroundColor": "#F8F9FA", "paddingAll": "14px",
                            "contents": [
                                {
                                    "type": "box", "layout": "horizontal", "alignItems": "flex-end",
                                    "contents": [
                                        {"type": "text", "text": "🎯 綜合評分", "size": "sm", "color": "#444444", "weight": "bold", "flex": 2},
                                        {"type": "text", "text": f"{total_score}", "size": "xxl", "weight": "bold", "color": theme["badge_text"], "align": "end", "flex": 1},
                                        {"type": "text", "text": "/100", "size": "xs", "color": "#888888", "align": "end", "flex": 0},
                                    ],
                                },
                                self._score_bar(total_score, theme["bar_color"], margin="sm"),
                                {"type": "separator", "margin": "md", "color": "#E0E0E0"},
                                *[
                                    self._sub_score_row(label, val, theme["bar_color"])
                                    for label, val in sub_scores.items()
                                ],
                            ],
                        },

                        # 3. 法人動向四欄
                        {
                            "type": "box", "layout": "vertical",
                            "paddingAll": "14px",
                            "contents": [
                                {"type": "text", "text": f"👤 法人動向（{name}）", "size": "sm", "weight": "bold", "color": "#1A1A2E"},
                                {
                                    "type": "box", "layout": "horizontal", "margin": "md", "spacing": "sm",
                                    "contents": [
                                        self._stat_card("連續買超", f"{consecutive} 天", theme["badge_text"]),
                                        self._stat_card("累計買超", f"{total_net // 1000}K 股", theme["badge_text"]),
                                        self._stat_card("起始日",   start_date[-5:], "#555555"),
                                        self._stat_card("截止日",   end_date[-5:],   "#555555"),
                                    ],
                                },
                            ],
                        },

                        {"type": "separator", "color": "#EEEEEE"},

                        # 4. 股價資訊 + AI 分析（左右排）
                        {
                            "type": "box", "layout": "horizontal",
                            "paddingAll": "14px", "spacing": "md",
                            "contents": [
                                # 股價資訊
                                {
                                    "type": "box", "layout": "vertical", "flex": 1,
                                    "backgroundColor": "#F8F9FA", "cornerRadius": "10px",
                                    "paddingAll": "10px", "spacing": "sm",
                                    "contents": [
                                        {"type": "text", "text": "📈 股價資訊", "size": "xxs", "weight": "bold", "color": "#444444"},
                                        {"type": "separator", "margin": "sm", "color": "#E0E0E0"},
                                        self._stat_row("現價",   close_str),
                                        self._stat_row("停損參考", sl_str,  highlight=True),
                                        self._stat_row("支撐",   sup_str),
                                        self._stat_row("壓力",   res_str),
                                    ],
                                },
                                # AI 分析
                                {
                                    "type": "box", "layout": "vertical", "flex": 1,
                                    "backgroundColor": "#F0F7FF", "cornerRadius": "10px",
                                    "paddingAll": "10px", "spacing": "sm",
                                    "contents": [
                                        {"type": "text", "text": "🧠 AI 分析", "size": "xxs", "weight": "bold", "color": "#1565C0"},
                                        {"type": "separator", "margin": "sm", "color": "#BBDEFB"},
                                        *ai_contents,
                                    ],
                                },
                            ],
                        },
                    ],
                },

                # ── Footer ─────────────────────────────────────────
                "footer": {
                    "type": "box", "layout": "vertical", "paddingAll": "0px", "spacing": "none",
                    "contents": [
                        # 四個按鈕列
                        {
                            "type": "box", "layout": "horizontal",
                            "paddingTop": "10px", "paddingBottom": "4px",
                            "paddingStart": "8px", "paddingEnd": "8px",
                            "spacing": "sm",
                            "contents": [
                                self._footer_btn("🔍 更多分析", f"https://tw.stock.yahoo.com/quote/{stock_id}"),
                                self._footer_btn("⭐ 加入自選", f"https://tw.stock.yahoo.com/quote/{stock_id}"),
                                self._footer_btn("🔔 設提醒", f"https://tw.stock.yahoo.com/quote/{stock_id}"),
                                self._footer_btn("🔗 分享", f"https://tw.stock.yahoo.com/quote/{stock_id}"),
                            ],
                        },
                        # 底部說明列
                        {
                            "type": "box", "layout": "horizontal",
                            "backgroundColor": "#06C755", "paddingAll": "8px",
                            "alignItems": "center",
                            "contents": [
                                {"type": "text", "text": "LINE  台股大戶偵測機器人  ｜  本訊息由程式自動發送，請勿直接回覆", "size": "xxs", "color": "#ffffff", "wrap": True, "align": "center"},
                            ],
                        },
                    ],
                },
            },
        }

    def _stat_row(self, label: str, value: str, highlight: bool = False) -> dict:
        return {
            "type": "box", "layout": "horizontal",
            "contents": [
                {"type": "text", "text": label, "size": "xs", "color": "#888888", "flex": 2},
                {"type": "text", "text": value, "size": "xs",
                 "color": "#E24B4A" if highlight else "#1A1A2E",
                 "weight": "bold" if highlight else "regular",
                 "flex": 3, "align": "end"},
            ],
        }

    def _stat_card(self, label: str, value: str, value_color: str) -> dict:
        """法人動向四欄卡片"""
        return {
            "type": "box", "layout": "vertical", "flex": 1,
            "backgroundColor": "#ffffff", "cornerRadius": "8px",
            "paddingAll": "8px", "alignItems": "center",
            "contents": [
                {"type": "text", "text": value, "size": "sm", "weight": "bold", "color": value_color, "align": "center"},
                {"type": "text", "text": label, "size": "xxs", "color": "#888888", "align": "center", "margin": "xs"},
            ],
        }

    def _score_bar(self, score: int, bar_color: str, margin: str = "md") -> dict:
        """橫向評分長條"""
        return {
            "type": "box", "layout": "horizontal",
            "backgroundColor": "#E0E0E0", "cornerRadius": "4px",
            "height": "8px", "margin": margin,
            "contents": [
                {"type": "box", "layout": "vertical",
                 "backgroundColor": bar_color, "cornerRadius": "4px",
                 "width": f"{max(score, 3)}%", "contents": []},
                {"type": "filler"},
            ],
        }

    def _sub_score_row(self, label: str, score: int, bar_color: str) -> dict:
        """四維度小條（雷達圖替代）"""
        return {
            "type": "box", "layout": "horizontal", "margin": "sm", "alignItems": "center",
            "contents": [
                {"type": "text", "text": label, "size": "xxs", "color": "#666666", "flex": 2},
                {
                    "type": "box", "layout": "horizontal", "flex": 5,
                    "backgroundColor": "#E0E0E0", "cornerRadius": "3px", "height": "6px",
                    "contents": [
                        {"type": "box", "layout": "vertical",
                         "backgroundColor": bar_color, "cornerRadius": "3px",
                         "width": f"{max(score, 3)}%", "contents": []},
                        {"type": "filler"},
                    ],
                },
                {"type": "text", "text": str(score), "size": "xxs", "color": "#888888", "align": "end", "flex": 1, "margin": "sm"},
            ],
        }

    def _footer_btn(self, label: str, uri: str) -> dict:
        """底部四個小按鈕"""
        return {
            "type": "box", "layout": "vertical", "flex": 1,
            "backgroundColor": "#F5F5F5", "cornerRadius": "8px",
            "paddingAll": "8px", "alignItems": "center",
            "action": {"type": "uri", "uri": uri},
            "contents": [
                {"type": "text", "text": label, "size": "xxs", "color": "#444444", "align": "center", "wrap": True},
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
