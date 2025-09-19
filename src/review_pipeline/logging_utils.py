from __future__ import annotations

import logging
import logging.config
from pathlib import Path
from typing import Dict

from .config import LoggingConfig


DEFAULT_LOGGING: Dict[str, object] = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "level": "INFO",
        }
    },
    "loggers": {
        "": {
            "handlers": ["console"],
            "level": "INFO",
        }
    },
}


def setup_logging(config: LoggingConfig) -> None:
    """Configure the logging subsystem based on the provided *config*."""

    log_config = DEFAULT_LOGGING.copy()
    fmt = config.fmt
    level = config.level.upper()
    logfile = Path(config.file)
    logfile.parent.mkdir(parents=True, exist_ok=True)

    log_config["formatters"] = {
        "standard": {
            "format": fmt,
        }
    }

    handlers = {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "level": level,
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "standard",
            "level": level,
            "filename": str(logfile),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 3,
            "encoding": "utf-8",
        },
    }

    log_config["handlers"] = handlers
    log_config["loggers"] = {
        "": {
            "handlers": ["console", "file"],
            "level": level,
        }
    }

    logging.config.dictConfig(log_config)
