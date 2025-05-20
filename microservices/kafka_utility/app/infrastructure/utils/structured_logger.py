"""
Structured logger with trace context support.
"""

import logging
import json
from typing import Any, Dict, Optional
from opentelemetry import trace
from datetime import datetime

class StructuredLogger:
    """
    Logger that outputs structured logs with trace context.
    """
    
    def __init__(self, name: str, service_name: str):
        """
        Initialize structured logger.
        
        Args:
            name: Logger name
            service_name: Service name for logs
        """
        self.logger = logging.getLogger(name)
        self.service_name = service_name
    
    def _get_trace_context(self) -> Dict[str, str]:
        """Get current trace context."""
        span = trace.get_current_span()
        if not span:
            return {}
            
        span_ctx = span.get_span_context()
        if not span_ctx.is_valid:
            return {}
            
        return {
            "trace_id": format(span_ctx.trace_id, "032x"),
            "span_id": format(span_ctx.span_id, "016x"),
            "parent_span_id": format(span_ctx.parent_span_id, "016x") if span_ctx.parent_span_id else None
        }
    
    def _log(self, level: int, message: str, **kwargs: Any) -> None:
        """Create structured log with trace context."""
        # Get trace context
        trace_ctx = self._get_trace_context()
        
        # Build log data
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "service": self.service_name,
            "level": logging.getLevelName(level),
            "message": message,
            **trace_ctx,
            **kwargs
        }
        
        # Log as JSON
        self.logger.log(level, json.dumps(log_data))
    
    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message."""
        self._log(logging.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message."""
        self._log(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message."""
        self._log(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, error: Optional[Exception] = None, **kwargs: Any) -> None:
        """Log error message."""
        if error:
            kwargs["error"] = {
                "type": error.__class__.__name__,
                "message": str(error)
            }
        self._log(logging.ERROR, message, **kwargs)
    
    def critical(self, message: str, error: Optional[Exception] = None, **kwargs: Any) -> None:
        """Log critical message."""
        if error:
            kwargs["error"] = {
                "type": error.__class__.__name__,
                "message": str(error)
            }
        self._log(logging.CRITICAL, message, **kwargs)
