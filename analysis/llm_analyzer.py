"""
analysis/llm_analyzer.py
呼叫 LLM 解讀法人異常訊號

支援：
    - Ollama（本地，免費）
    - OpenAI（雲端，收費）

切換方式：
    analyzer = LLMAnalyzer(provider="ollama")
    analyzer = LLMAnalyzer(provider="openai")
"""

import logging
import sqlite3

import requests
from openai import OpenAI

from config.settings import settings
from database.db import get_connection

logger = logging.getLogger(__name__)

# 提示詞模板（中文，給 LLM 的指令）
PROMPT_TEMPLATE = """
你是一位台股籌碼分析師，請根據以下法人買賣超異常資料，用繁體中文給出簡短的分析與操作建議。

【異常資料】
股票代號：{stock_id}
法人：{name}
連續買超天數：{consecutive} 天
買超區間：{start_date} ~ {end_date}
累計買超股數：{total_net:,} 股

【分析要求】
1. 說明此訊號的意義（2～3 句）
2. 可能的後續走勢判斷（1～2 句）
3. 操作建議（1 句，保守為主）

請用條列式回答，總字數控制在 150 字以內。
""".strip()


class LLMAnalyzer:
    def __init__(self, provider: str = "ollama"):
        """
        :param provider: "ollama" 或 "openai"
        """
        if provider not in ("ollama", "openai"):
            raise ValueError(f"不支援的 provider：{provider}，請選 ollama 或 openai")

        self.provider = provider
        logger.info(f"LLM 使用：{provider}")

        # OpenAI 只在需要時初始化
        if provider == "openai":
            self.openai_client = OpenAI(api_key=settings.openai_api_key)

    # ──────────────────────────────────────────────────────────────
    # 公開方法
    # ──────────────────────────────────────────────────────────────

    def analyze_anomaly(self, anomaly: dict) -> str:
        """
        解讀單一異常，回傳 LLM 分析文字
        :param anomaly: institutional_analyzer 回傳的異常 dict
        :return:        LLM 分析結果字串
        """
        prompt = PROMPT_TEMPLATE.format(
            stock_id   = anomaly["stock_id"],
            name       = anomaly["name"],
            consecutive= anomaly["consecutive"],
            start_date = anomaly["start_date"],
            end_date   = anomaly["end_date"],
            total_net  = anomaly["total_net"],
        )

        logger.info(f"[{anomaly['stock_id']}] 呼叫 {self.provider} 分析...")

        if self.provider == "ollama":
            report = self._call_ollama(prompt)
        else:
            report = self._call_openai(prompt)

        # 寫回資料庫 anomaly_log.ai_report
        if report:
            self._save_report(anomaly["stock_id"], anomaly["name"], report)

        return report

    def analyze_all(self, anomalies: list[dict]) -> list[dict]:
        """
        批次解讀所有異常
        :param anomalies: 異常清單
        :return:          每個異常加上 ai_report 欄位
        """
        results = []
        for anomaly in anomalies:
            report = self.analyze_anomaly(anomaly)
            results.append({**anomaly, "ai_report": report})
        return results

    # ──────────────────────────────────────────────────────────────
    # 私有方法：呼叫 LLM
    # ──────────────────────────────────────────────────────────────

    def _call_ollama(self, prompt: str) -> str:
        """呼叫本地 Ollama API"""
        url = f"{settings.ollama_host}/api/generate"
        payload = {
            "model":  settings.ollama_model,
            "prompt": prompt,
            "stream": False,  # 不用串流，等待完整回應
        }
        try:
            resp = requests.post(url, json=payload, timeout=60)
            resp.raise_for_status()
            report = resp.json().get("response", "").strip()
            logger.info(f"Ollama 回應完成（{len(report)} 字）")
            return report
        except requests.exceptions.ConnectionError:
            logger.error("Ollama 連線失敗，請確認 Ollama 是否已啟動（ollama serve）")
            return ""
        except Exception as e:
            logger.error(f"Ollama 呼叫失敗：{e}")
            return ""

    def _call_openai(self, prompt: str) -> str:
        """呼叫 OpenAI API"""
        if not settings.openai_api_key:
            logger.error("OpenAI API Key 未設定，請確認 .env")
            return ""
        try:
            resp = self.openai_client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": "你是一位專業的台股籌碼分析師，回答簡潔精準。"},
                    {"role": "user",   "content": prompt},
                ],
                max_tokens=300,
                temperature=0.3,  # 低溫度，回答較穩定
            )
            report = resp.choices[0].message.content.strip()
            logger.info(f"OpenAI 回應完成（{len(report)} 字）")
            return report
        except Exception as e:
            logger.error(f"OpenAI 呼叫失敗：{e}")
            return ""

    # ──────────────────────────────────────────────────────────────
    # 私有方法：寫入資料庫
    # ──────────────────────────────────────────────────────────────

    def _save_report(self, stock_id: str, name: str, report: str) -> None:
        """將 AI 分析結果寫回 anomaly_log.ai_report"""
        conn = get_connection()
        try:
            conn.execute("""
                UPDATE anomaly_log
                SET ai_report = ?
                WHERE stock_id = ?
                  AND broker_id = ?
                  AND ai_report IS NULL
                  AND anomaly_type = '連續買超'
            """, (report, stock_id, name))
            conn.commit()
            logger.info(f"[{stock_id}] AI 分析已寫入 anomaly_log")
        except Exception as e:
            conn.rollback()
            logger.error(f"ai_report 寫入失敗：{e}")
        finally:
            conn.close()
