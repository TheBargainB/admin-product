"""
Logging configuration and utilities
"""

import logging
import logging.config
import sys
from pathlib import Path
from typing import Dict, Any
import structlog
from datetime import datetime

from config.settings import settings


def setup_logging():
    """Set up application logging configuration."""
    
    # Configure standard library logging
    logging_config = settings.get_log_config()
    logging.config.dictConfig(logging_config)
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="ISO"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer() if settings.is_development() 
            else structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = None) -> structlog.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


class ScrapingLogger:
    """Specialized logger for scraping operations."""
    
    def __init__(self, store_name: str, job_id: str = None):
        self.store_name = store_name
        self.job_id = job_id
        self.logger = get_logger(f"scraper.{store_name}")
        
    def info(self, message: str, **kwargs):
        """Log info message with scraping context."""
        self.logger.info(
            message,
            store=self.store_name,
            job_id=self.job_id,
            **kwargs
        )
    
    def warning(self, message: str, **kwargs):
        """Log warning message with scraping context."""
        self.logger.warning(
            message,
            store=self.store_name,
            job_id=self.job_id,
            **kwargs
        )
    
    def error(self, message: str, **kwargs):
        """Log error message with scraping context."""
        self.logger.error(
            message,
            store=self.store_name,
            job_id=self.job_id,
            **kwargs
        )
    
    def debug(self, message: str, **kwargs):
        """Log debug message with scraping context."""
        self.logger.debug(
            message,
            store=self.store_name,
            job_id=self.job_id,
            **kwargs
        )


class AgentLogger:
    """Specialized logger for LangGraph agents."""
    
    def __init__(self, agent_name: str, session_id: str = None):
        self.agent_name = agent_name
        self.session_id = session_id
        self.logger = get_logger(f"agent.{agent_name}")
    
    def log_action(self, action: str, details: Dict[str, Any] = None):
        """Log agent action."""
        self.logger.info(
            f"Agent action: {action}",
            agent=self.agent_name,
            session_id=self.session_id,
            action=action,
            details=details or {}
        )
    
    def log_decision(self, decision: str, reasoning: str = None, confidence: float = None):
        """Log agent decision."""
        self.logger.info(
            f"Agent decision: {decision}",
            agent=self.agent_name,
            session_id=self.session_id,
            decision=decision,
            reasoning=reasoning,
            confidence=confidence
        )
    
    def log_error(self, error: str, exception: Exception = None):
        """Log agent error."""
        self.logger.error(
            f"Agent error: {error}",
            agent=self.agent_name,
            session_id=self.session_id,
            error=error,
            exception=str(exception) if exception else None
        )


class PerformanceLogger:
    """Logger for performance monitoring."""
    
    def __init__(self):
        self.logger = get_logger("performance")
    
    def log_request_time(self, endpoint: str, method: str, duration: float, status_code: int):
        """Log API request performance."""
        self.logger.info(
            "API request completed",
            endpoint=endpoint,
            method=method,
            duration_ms=round(duration * 1000, 2),
            status_code=status_code
        )
    
    def log_scraping_performance(self, store: str, products_scraped: int, 
                               duration: float, errors: int = 0):
        """Log scraping performance metrics."""
        rate = products_scraped / duration if duration > 0 else 0
        
        self.logger.info(
            "Scraping performance",
            store=store,
            products_scraped=products_scraped,
            duration_seconds=round(duration, 2),
            products_per_second=round(rate, 2),
            errors=errors,
            success_rate=round((products_scraped - errors) / products_scraped * 100, 2) 
            if products_scraped > 0 else 0
        )
    
    def log_database_operation(self, operation: str, table: str, 
                             duration: float, rows_affected: int = None):
        """Log database operation performance."""
        self.logger.info(
            "Database operation",
            operation=operation,
            table=table,
            duration_ms=round(duration * 1000, 2),
            rows_affected=rows_affected
        )


# Create global logger instances
app_logger = get_logger("app")
api_logger = get_logger("api")
db_logger = get_logger("database")
performance_logger = PerformanceLogger() 