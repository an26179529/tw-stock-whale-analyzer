from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────
    app_env:        str = "development"
    app_secret_key: str = ""

    # ── GitHub ───────────────────────────────────
    github_token: str = ""
    github_repo:  str = ""

    # ── FinMind ──────────────────────────────────
    finmind_token:   str = ""
    finmind_api_url: str = "https://api.finmindtrade.com/api/v4/data"

    # ── OpenAI ───────────────────────────────────
    openai_api_key: str = ""
    openai_model:   str = "gpt-4o"

    # ── Ollama ───────────────────────────────────
    ollama_host:  str = "http://localhost:11434"
    ollama_model: str = "qwen2.5"

    # ── 資料庫 ────────────────────────────────────
    db_path: Path = BASE_DIR / "database" / "whale.db"

    # ── 排程 ─────────────────────────────────────
    schedule_hour:   int = 17
    schedule_minute: int = 30

    # ── Line ─────────────────────────
    line_channel_access_token: str = ""
    line_user_ids:      str = ""  # 逗號分隔，例如 "Uaaa,Ubbb"

    @property
    def line_user_id_list(self) -> list[str]:
        """將逗號分隔的 user_ids 轉成清單"""
        return [uid.strip() for uid in self.line_user_ids.split(",") if uid.strip()]
    
    # ── 分析參數 ──────────────────────────────────
    @property
    def anomaly_config(self) -> dict:
        return {
            "consecutive_buy_days": 3,
            "volume_multiplier":    2.0,
            "volume_ma_days":       20,
            "cost_vs_price_pct":    5.0,
            "min_position_lots":    10,
        }


settings = Settings()