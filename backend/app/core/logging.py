import itertools
import logging
import sys
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any

_CONFIGURED = False

# Bounded in-memory ring buffer feeding the live log viewer (GET /logs/recent,
# GET /logs/stream). Every logger.info/warning/error(...) call anywhere in the
# app already flows through the root logger, so this needs zero new logging
# calls elsewhere — it just taps the existing stream.
_BUFFER_MAXLEN = 500
_buffer: deque[dict[str, Any]] = deque(maxlen=_BUFFER_MAXLEN)
_buffer_lock = threading.Lock()
_seq_counter = itertools.count(1)


class BroadcastLogHandler(logging.Handler):
    """Appends every log record to the shared ring buffer as a structured dict."""

    def emit(self, record: logging.LogRecord) -> None:
        entry = {
            "seq": next(_seq_counter),
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        with _buffer_lock:
            _buffer.append(entry)


def get_recent_logs(limit: int = 200, since: int = 0) -> list[dict[str, Any]]:
    """Entries with seq > since, most recent `limit` of them, oldest first."""
    with _buffer_lock:
        entries = [e for e in _buffer if e["seq"] > since]
    return entries[-limit:]


def setup_logging(level: str = "INFO") -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
    )
    root = logging.getLogger()
    root.setLevel(level.upper())
    root.handlers.clear()
    root.addHandler(handler)
    root.addHandler(BroadcastLogHandler())
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
