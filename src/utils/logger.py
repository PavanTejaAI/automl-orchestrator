import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional

LOGGER_NAME = "automl-orchestrator"
ENV_VAR_NAME = "ENVIRONMENT"
PRODUCTION_ENV = "production"
DEFAULT_ENV = "development"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S.%f"
TIMESTAMP_PRECISION = 3


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "path": record.pathname,
        }
        
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "extra"):
            log_data.update(record.extra)
        
        return json.dumps(log_data, default=str)


class ColoredFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[35m",
    }
    RESET = "\033[0m"
    LEVEL_PADDING = 8
    
    def _format_timestamp(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created).strftime(TIMESTAMP_FORMAT)
        return timestamp[:-TIMESTAMP_PRECISION]
    
    def _format_module_info(self, record: logging.LogRecord) -> str:
        return f"{record.module}:{record.funcName}:{record.lineno}"
    
    def format(self, record: logging.LogRecord) -> str:
        log_color = self.COLORS.get(record.levelname, self.RESET)
        timestamp = self._format_timestamp(record)
        level_padded = f"{record.levelname:{self.LEVEL_PADDING}}"
        module_info = self._format_module_info(record)
        
        base_format = (
            f"{log_color}{timestamp} | {level_padded} | {self.RESET}"
            f"{record.name} | {module_info} | {record.getMessage()}"
        )
        
        if record.exc_info:
            base_format += f"\n{self.formatException(record.exc_info)}"
        
        return base_format


class AutoMLLogger:
    _instance: Optional["AutoMLLogger"] = None
    _initialized = False
    
    LEVEL_MAP = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.logger_name = LOGGER_NAME
        self.logger = logging.getLogger(self.logger_name)
        self.logger.setLevel(logging.DEBUG)
        
        if not self.logger.handlers:
            self._setup_handlers()
        
        self._initialized = True
    
    def _setup_handlers(self):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        
        is_production = self._is_production()
        
        if is_production:
            formatter = JSONFormatter()
        else:
            formatter = ColoredFormatter()
        
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        error_handler = logging.StreamHandler(sys.stderr)
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        self.logger.addHandler(error_handler)
    
    def _is_production(self) -> bool:
        env = os.getenv(ENV_VAR_NAME, DEFAULT_ENV).lower()
        return env == PRODUCTION_ENV
    
    def _log_with_context(
        self,
        level: int,
        message: str,
        extra: Optional[Dict[str, Any]] = None,
        exc_info: Optional[Any] = None
    ):
        if extra is None:
            extra = {}
        
        self.logger.log(level, message, extra=extra, exc_info=exc_info)
    
    def debug(self, message: str, **kwargs: Any) -> None:
        self._log_with_context(logging.DEBUG, message, extra=kwargs)
    
    def info(self, message: str, **kwargs: Any) -> None:
        self._log_with_context(logging.INFO, message, extra=kwargs)
    
    def warning(self, message: str, **kwargs: Any) -> None:
        self._log_with_context(logging.WARNING, message, extra=kwargs)
    
    def error(self, message: str, **kwargs: Any) -> None:
        self._log_with_context(logging.ERROR, message, extra=kwargs)
    
    def critical(self, message: str, **kwargs: Any) -> None:
        self._log_with_context(logging.CRITICAL, message, extra=kwargs)
    
    def exception(self, message: str, **kwargs: Any) -> None:
        self._log_with_context(logging.ERROR, message, extra=kwargs, exc_info=True)
    
    def get_logger(self, name: Optional[str] = None) -> logging.Logger:
        if name:
            return logging.getLogger(f"{self.logger_name}.{name}")
        return self.logger
    
    def set_level(self, level: str) -> None:
        level_upper = level.upper()
        log_level = self.LEVEL_MAP.get(level_upper, logging.INFO)
        self.logger.setLevel(log_level)
        
        for handler in self.logger.handlers:
            if handler.level > log_level:
                handler.setLevel(log_level)


logger = AutoMLLogger()


def get_logger(name: Optional[str] = None) -> logging.Logger:
    return logger.get_logger(name)
