from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol


class StatusLike(Protocol):
    mac_address: str
    paired: bool
    bonded: bool
    trusted: bool
    connected: bool


def ensure_log_dir(log_dir: str | Path) -> Path:
    path = Path(log_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def normalize_component_name(component: str) -> str:
    return component.replace(".", "_").replace("/", "_")


def get_hub_logger(component: str, log_dir: str | Path) -> logging.Logger:
    normalized_component = normalize_component_name(component)
    log_path = ensure_log_dir(log_dir) / f"{normalized_component}.log"
    logger = logging.getLogger(f"polar_ble_tools.{normalized_component}.{log_path.resolve()}")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    existing_paths = {getattr(handler, "baseFilename", None) for handler in logger.handlers}
    if str(log_path.resolve()) not in existing_paths:
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger


def log_event(logger: logging.Logger, event: str, **fields: object) -> None:
    if fields:
        rendered_fields = " ".join(f"{key}={value}" for key, value in sorted(fields.items()))
        logger.info("%s %s", event, rendered_fields)
        return
    logger.info("%s", event)


def log_status(logger: logging.Logger, event: str, status: StatusLike) -> None:
    log_event(
        logger,
        event,
        mac=status.mac_address,
        paired=status.paired,
        bonded=status.bonded,
        trusted=status.trusted,
        connected=status.connected,
    )
