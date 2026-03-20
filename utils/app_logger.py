"""In-process ring-buffer logging for the IT Resource Planner.

Usage in any service/module:
    from utils.app_logger import get_logger
    logger = get_logger("excel")
    logger.info("Import avviato: %s", piano_nome)

The module is a Python singleton (imported once per process), so records
persist across Streamlit reruns within the same server process.
"""

import logging
from collections import deque
from datetime import datetime

# Ring buffer: keeps the last 500 log records in memory
_BUFFER: deque = deque(maxlen=500)


class _MemHandler(logging.Handler):
    """Custom handler that appends records to the in-memory buffer."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            _BUFFER.append({
                "ts": datetime.fromtimestamp(record.created).strftime("%H:%M:%S.%f")[:-3],
                "level": record.levelname,
                "logger": record.name.replace("planner.", "", 1),
                "msg": self.format(record),
            })
        except Exception:
            pass  # never let logging errors propagate


def get_logger(name: str) -> logging.Logger:
    """Return (and configure) a named logger that writes to the in-memory buffer.

    Args:
        name: Short logger name (e.g. "excel", "allocazione").
              Will be prefixed with "planner." internally.

    Returns:
        Configured Logger instance.
    """
    full_name = f"planner.{name}"
    logger = logging.getLogger(full_name)
    # Attach handler only once (modules are cached after first import)
    if not any(isinstance(h, _MemHandler) for h in logger.handlers):
        handler = _MemHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
    return logger


def get_records() -> list:
    """Return a copy of buffered records, most recent first.

    Each record is a dict with keys: ts, level, logger, msg.
    """
    return list(reversed(_BUFFER))


def clear_records() -> None:
    """Empty the log buffer."""
    _BUFFER.clear()
