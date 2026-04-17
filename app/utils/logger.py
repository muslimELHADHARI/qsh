from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


_CONFIGURED = False


def configure_logging(log_file: str = "logs/qsh.log", level: int = logging.INFO, syslog_host: str | None = None, syslog_port: int = 514) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger("qsh")
    root.setLevel(level)
    root.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)

    file_handler = RotatingFileHandler(log_path, maxBytes=2_000_000, backupCount=4, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    if syslog_host is not None:
        syslog_handler = logging.handlers.SysLogHandler(address=(syslog_host, syslog_port))
        syslog_handler.setFormatter(formatter)
        root.addHandler(syslog_handler)

    _CONFIGURED = True


def get_logger(name: str = "qsh") -> logging.Logger:
    return logging.getLogger(name if name.startswith("qsh") else f"qsh.{name}")


def log_event(logger: logging.Logger, event: str, **fields: object) -> None:
    chunks = [f"event={event}"]
    for key, value in fields.items():
        chunks.append(f"{key}={value!r}")
    logger.info(" ".join(chunks))
