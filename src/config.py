from pydantic_settings import BaseSettings
from typing import List
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # データベース設定
    db_host: str = os.getenv("DB_HOST", "localhost")
    db_port: int = int(os.getenv("DB_PORT", "3306"))
    db_user: str = os.getenv("DB_USER", "")
    db_password: str = os.getenv("DB_PASSWORD", "")
    db_name: str = os.getenv("DB_NAME", "matemane")

    # セキュリティ設定
    secret_key: str = os.getenv("SECRET_KEY", "your-secret-key-change-this")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    jwt_expire_minutes: int = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))

    # アプリケーション設定
    debug: bool = os.getenv("DEBUG", "True").lower() == "true"
    cors_origins: List[str] = os.getenv("CORS_ORIGINS", "http://localhost:8000").split(",")
    # 許可するホスト（本番で iPhone 等の外部端末からアクセスする場合はここに LAN IP/ドメインを追加）
    allowed_hosts: List[str] = os.getenv(
        "ALLOWED_HOSTS",
        "localhost,127.0.0.1,*.localhost"
    ).split(",")

    # ラベル印刷設定
    label_width_mm: int = int(os.getenv("LABEL_WIDTH_MM", "50"))
    label_height_mm: int = int(os.getenv("LABEL_HEIGHT_MM", "30"))
    qr_size_mm: int = int(os.getenv("QR_SIZE_MM", "20"))
    # production_schedule_path: str = os.getenv("PRODUCTION_SCHEDULE_PATH", r"\\192.168.1.200\共有\生産管理課\セット予定表.xlsx")
    production_schedule_path: str = os.getenv("PRODUCTION_SCHEDULE_PATH", r"セット予定表.xlsx")

    @property
    def database_url(self) -> str:
        return f"mysql+pymysql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

settings = Settings()