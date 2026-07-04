"""集中管理設定,全部從環境變數 / .env 讀取。"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LINE
    line_channel_access_token: str = ""
    line_channel_secret: str = ""
    line_admin_user_ids: str = ""  # 逗號分隔

    # Claude
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"

    # Google Sheets
    google_service_account_file: str = "./service_account.json"
    spreadsheet_id: str = ""
    source_sheet: str = "source"
    employee_sheet: str = "employees"
    log_sheet: str = "log"
    source_recipients_column: str = "員編"
    employee_id_column: str = "員編"
    employee_email_column: str = "email"

    # SMTP
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    mail_from: str = ""

    # 其他
    public_base_url: str = "http://localhost:8000"
    database_path: str = "./workflow.db"
    start_api_token: str = "change-me"

    @property
    def admin_ids(self) -> set[str]:
        return {x.strip() for x in self.line_admin_user_ids.split(",") if x.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
