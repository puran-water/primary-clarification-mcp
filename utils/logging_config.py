"""
Structured logging configuration for primary clarifier MCP.

Provides:
- Trace ID generation for correlating logs across background jobs and CLI wrappers
- Structured log formatting
- Log level configuration
- Context-aware logging
"""

import logging
import uuid
import json
from typing import Optional, Dict, Any
from datetime import datetime
import contextvars

# Context variable for trace ID (thread-safe for async)
trace_id_var = contextvars.ContextVar('trace_id', default=None)


def generate_trace_id(prefix: str = "trace") -> str:
    """
    Generate a unique trace ID for correlating logs.

    Args:
        prefix: Prefix for the trace ID (e.g., "sizing", "simulation")

    Returns:
        Trace ID string (e.g., "sizing-abc123de")
    """
    short_uuid = str(uuid.uuid4())[:8]
    return f"{prefix}-{short_uuid}"


def set_trace_id(trace_id: str):
    """
    Set trace ID for current context.

    Args:
        trace_id: Trace ID to set
    """
    trace_id_var.set(trace_id)


def get_trace_id() -> Optional[str]:
    """
    Get trace ID from current context.

    Returns:
        Trace ID or None if not set
    """
    return trace_id_var.get()


class StructuredFormatter(logging.Formatter):
    """
    Custom formatter that outputs structured logs in JSON format.

    Includes:
    - Timestamp
    - Level
    - Logger name
    - Message
    - Trace ID (if available)
    - Additional context fields
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as structured JSON.

        Args:
            record: Log record to format

        Returns:
            JSON-formatted log string
        """
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage()
        }

        # Add trace ID if available
        trace_id = get_trace_id()
        if trace_id:
            log_data["trace_id"] = trace_id

        # Add job ID if present in record
        if hasattr(record, 'job_id'):
            log_data["job_id"] = record.job_id

        # Add any extra fields from record
        if hasattr(record, 'extra_fields'):
            log_data.update(record.extra_fields)

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


class ContextLogger:
    """
    Logger wrapper that adds context (trace ID, job ID) to all log messages.

    Usage:
        logger = ContextLogger("primary_clarifier.sizing", trace_id="sizing-abc123")
        logger.info("Starting sizing calculation")
    """

    def __init__(self, name: str, trace_id: Optional[str] = None, job_id: Optional[str] = None):
        """
        Initialize context logger.

        Args:
            name: Logger name
            trace_id: Optional trace ID for correlation
            job_id: Optional job ID for background jobs
        """
        self.logger = logging.getLogger(name)
        self.trace_id = trace_id
        self.job_id = job_id

    def _log_with_context(self, level: int, msg: str, extra_fields: Optional[Dict[str, Any]] = None):
        """
        Log message with context fields.

        Args:
            level: Log level
            msg: Log message
            extra_fields: Optional additional fields
        """
        extra = {"extra_fields": extra_fields or {}}

        if self.trace_id:
            extra["extra_fields"]["trace_id"] = self.trace_id

        if self.job_id:
            extra["job_id"] = self.job_id

        self.logger.log(level, msg, extra=extra)

    def debug(self, msg: str, **kwargs):
        """Log debug message."""
        self._log_with_context(logging.DEBUG, msg, kwargs)

    def info(self, msg: str, **kwargs):
        """Log info message."""
        self._log_with_context(logging.INFO, msg, kwargs)

    def warning(self, msg: str, **kwargs):
        """Log warning message."""
        self._log_with_context(logging.WARNING, msg, kwargs)

    def error(self, msg: str, **kwargs):
        """Log error message."""
        self._log_with_context(logging.ERROR, msg, kwargs)

    def critical(self, msg: str, **kwargs):
        """Log critical message."""
        self._log_with_context(logging.CRITICAL, msg, kwargs)


def configure_logging(
    level: str = "INFO",
    use_json: bool = False,
    log_file: Optional[str] = None
):
    """
    Configure logging for the application.

    Args:
        level: Log level ("DEBUG", "INFO", "WARNING", "ERROR")
        use_json: Use JSON structured logging (default: False)
        log_file: Optional file path for logging
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Create formatter
    if use_json:
        formatter = StructuredFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    root_logger.handlers = []

    # Add console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Add file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


# Default configuration (simple format for development)
configure_logging(level="INFO", use_json=False)
