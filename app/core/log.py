import logging
import os
from logging.handlers import RotatingFileHandler
import sys

LOGS_DIR = "logs"
LOG_FILE = os.path.join(LOGS_DIR, "app.log")
MAX_BYTES = 5 * 1024 * 1024  # 5MB
BACKUP_COUNT = 5


def setup_logging() -> None:
    """Configure rotating file handler and console stdout logger."""
    os.makedirs(LOGS_DIR, exist_ok=True)

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Avoid duplicate handlers if already added
    if not root_logger.handlers:
        # Console Handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.INFO)
        root_logger.addHandler(console_handler)

        # Rotating File Handler
        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)
        root_logger.addHandler(file_handler)


logger = logging.getLogger("ai_news")
