from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./eeg_poc.db"
    UPLOAD_DIR: str = str(Path(__file__).parent / "storage" / "uploads")
    PROCESSED_DIR: str = str(Path(__file__).parent / "storage" / "processed")
    MAX_UPLOAD_SIZE_MB: int = 200
    MANAS1_MOCK_LATENCY_MS: int = 120  # per-epoch simulated latency
    EEG_DISPLAY_SAMPLE_RATE: int = 250
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000", "*"]

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
