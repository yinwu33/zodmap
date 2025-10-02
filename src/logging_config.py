import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

_LOGGER_INITIALIZED = False
_LOG_FILE_PATH: Optional[Path] = None


def configure_logging(log_dir: Path | str = "logs") -> Path:
    """Configure logging to write to stdout and a timestamped file.

    Returns the path of the log file in case callers want to inspect it.
    """
    global _LOGGER_INITIALIZED, _LOG_FILE_PATH

    if _LOGGER_INITIALIZED and _LOG_FILE_PATH is not None:
        return _LOG_FILE_PATH

    log_directory = Path(log_dir)
    log_directory.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    _LOG_FILE_PATH = log_directory / f"{timestamp}.txt"

    log_format = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Clear existing handlers to avoid duplicate logs when re-configuring.
    root_logger.handlers.clear()

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter(log_format))
    root_logger.addHandler(stream_handler)

    file_handler = logging.FileHandler(_LOG_FILE_PATH)
    file_handler.setFormatter(logging.Formatter(log_format))
    root_logger.addHandler(file_handler)

    _LOGGER_INITIALIZED = True

    root_logger.debug("Logging configured. Log file: %s", _LOG_FILE_PATH)

    return _LOG_FILE_PATH


__all__ = ["configure_logging"]
