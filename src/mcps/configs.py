import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# Project root for resolving paths regardless of cwd
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    ENV: str = Field(default="local")
    LOGS_DIR: str = Field(default="./logs")
    LOG_LEVEL: str = Field(default="INFO")
    LOG_TO_FILE: bool = Field(default=True)

    model_config = SettingsConfigDict(
        env_file=(
            [str(_PROJECT_ROOT / ".env"), ".env"]
            if not os.getenv("ENVPATH")
            else os.getenv("ENVPATH")
        ),
        extra="allow",
    )


settings = Settings()


def setup_logging() -> None:
    """
    Configure root logging based on Settings.

    Logs are formatted as:
    `timestamp [LEVEL] [logger_name] message`, where `logger_name` typically
    corresponds to the module or service name.
    """
    level_name = (settings.LOG_LEVEL or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    # If already configured, don't do it again.
    if getattr(setup_logging, "_configured", False):
        return

    log_format = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
    formatter = logging.Formatter(log_format)

    handlers: list[logging.Handler] = []

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    handlers.append(console_handler)

    if settings.LOG_TO_FILE:
        try:
            logs_dir = settings.LOGS_DIR
            if not Path(logs_dir).is_absolute():
                logs_dir = str(_PROJECT_ROOT / logs_dir)
            os.makedirs(logs_dir, exist_ok=True)
            log_file = os.path.join(logs_dir, "go2_sport_control.log")
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=5 * 1024 * 1024,  # 5MB
                backupCount=3,
            )
            file_handler.setFormatter(formatter)
            handlers.append(file_handler)
        except Exception:
            pass

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)

    for h in handlers:
        root_logger.addHandler(h)

    setattr(setup_logging, "_configured", True)
