import logging
import os
import sys


def setup_logging():
    level = logging.DEBUG if os.getenv("LOG_LEVEL", "INFO").upper() == "DEBUG" else logging.INFO

    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    datefmt = "%Y-%m-%dT%H:%M:%S"

    logging.basicConfig(
        stream=sys.stdout,
        level=level,
        format=fmt,
        datefmt=datefmt,
        force=True,
    )

    # Silence noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
