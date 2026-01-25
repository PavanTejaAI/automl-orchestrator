import json
import logging
import os
import sys
from unittest.mock import patch

import pytest

from src.utils.logger import AutoMLLogger, ColoredFormatter, JSONFormatter, get_logger, logger

TEST_LOGGER_NAME = "test"
TEST_PATHNAME = "/test/path.py"
TEST_LINENO = 10
TEST_FUNCTION = "test_function"
LOGGER_NAME = "automl-orchestrator"


def create_log_record(
    name: str = TEST_LOGGER_NAME,
    level: int = logging.INFO,
    msg: str = "Test message",
    exc_info=None,
) -> logging.LogRecord:
    return logging.LogRecord(
        name=name,
        level=level,
        pathname=TEST_PATHNAME,
        lineno=TEST_LINENO,
        msg=msg,
        args=(),
        exc_info=exc_info,
        func=TEST_FUNCTION,
    )


def reset_singleton():
    AutoMLLogger._initialized = False
    AutoMLLogger._instance = None


class TestJSONFormatter:
    def test_format_basic_log(self):
        formatter = JSONFormatter()
        record = create_log_record()
        result = formatter.format(record)
        data = json.loads(result)
        
        print(f"\nJSON Formatter Output: {result}")
        print(f"Parsed Data: {json.dumps(data, indent=2)}")
        
        assert data["level"] == "INFO"
        assert data["logger"] == TEST_LOGGER_NAME
        assert data["message"] == "Test message"
        assert data["module"] == "path"
        assert data["function"] == TEST_FUNCTION
        assert data["line"] == TEST_LINENO
        assert "timestamp" in data
    
    def test_format_with_exception(self):
        formatter = JSONFormatter()
        try:
            raise ValueError("Test error")
        except Exception:
            record = create_log_record(
                level=logging.ERROR,
                msg="Error occurred",
                exc_info=sys.exc_info(),
            )
            result = formatter.format(record)
            data = json.loads(result)
            
            print(f"\nJSON Formatter with Exception: {result}")
            print(f"Exception Data: {data.get('exception', 'N/A')[:200]}")
            
            assert data["level"] == "ERROR"
            assert "exception" in data
            assert "ValueError" in data["exception"]


class TestColoredFormatter:
    def test_format_basic_log(self):
        formatter = ColoredFormatter()
        record = create_log_record()
        result = formatter.format(record)
        
        print(f"\nColored Formatter Output: {result}")
        print(f"Contains ANSI colors: {'\\033' in result}")
        
        assert "INFO" in result
        assert "Test message" in result
        assert f"path:{TEST_FUNCTION}:{TEST_LINENO}" in result
        assert "\033[32m" in result or "INFO" in result
    
    def test_format_with_exception(self):
        formatter = ColoredFormatter()
        try:
            raise ValueError("Test error")
        except Exception:
            record = create_log_record(
                level=logging.ERROR,
                msg="Error occurred",
                exc_info=sys.exc_info(),
            )
            result = formatter.format(record)
            
            print(f"\nColored Formatter with Exception: {result[:300]}")
            
            assert "ERROR" in result
            assert "Error occurred" in result
            assert "ValueError" in result


class TestAutoMLLogger:
    def test_singleton_pattern(self):
        logger1 = AutoMLLogger()
        logger2 = AutoMLLogger()
        assert logger1 is logger2
    
    def test_logger_name(self):
        instance = AutoMLLogger()
        assert instance.logger_name == LOGGER_NAME
        assert instance.logger.name == LOGGER_NAME
    
    @pytest.mark.parametrize("level,method_name,message", [
        (logging.DEBUG, "debug", "Debug message"),
        (logging.INFO, "info", "Info message"),
        (logging.WARNING, "warning", "Warning message"),
        (logging.ERROR, "error", "Error message"),
        (logging.CRITICAL, "critical", "Critical message"),
    ])
    def test_log_levels(self, caplog, level, method_name, message):
        with caplog.at_level(level):
            instance = AutoMLLogger()
            method = getattr(instance, method_name)
            method(message)
            
            print(f"\n{method_name.upper()} Log Output:")
            print(f"  Captured Text: {caplog.text}")
            print(f"  Records: {len(caplog.records)}")
            if caplog.records:
                print(f"  First Record: {caplog.records[0].message}")
            
            assert message in caplog.text
    
    def test_exception_logging(self, caplog):
        with caplog.at_level(logging.ERROR):
            instance = AutoMLLogger()
            try:
                raise ValueError("Test exception")
            except Exception:
                instance.exception("Exception caught", context="test")
            assert "Exception caught" in caplog.text
            assert "ValueError" in caplog.text
    
    def test_get_logger_without_name(self):
        instance = AutoMLLogger()
        result = instance.get_logger()
        assert result.name == "automl-orchestrator"
    
    def test_get_logger_with_name(self):
        instance = AutoMLLogger()
        result = instance.get_logger("api")
        assert result.name == "automl-orchestrator.api"
    
    @pytest.mark.parametrize("level_name,expected_level", [
        ("WARNING", logging.WARNING),
        ("DEBUG", logging.DEBUG),
        ("INFO", logging.INFO),
    ])
    def test_set_level(self, level_name, expected_level):
        instance = AutoMLLogger()
        instance.set_level(level_name)
        assert instance.logger.level == expected_level
    
    def test_set_level_invalid(self):
        instance = AutoMLLogger()
        instance.set_level("INVALID")
        assert instance.logger.level == logging.INFO
    
    @pytest.mark.parametrize("env_value,expected", [
        ("production", True),
        ("development", False),
        ("PRODUCTION", True),
        ("Production", True),
    ])
    @patch.dict(os.environ, {}, clear=True)
    def test_environment_modes(self, env_value, expected):
        reset_singleton()
        os.environ["ENVIRONMENT"] = env_value
        instance = AutoMLLogger()
        assert instance._is_production() is expected
    
    def test_extra_context(self, caplog):
        with caplog.at_level(logging.INFO):
            instance = AutoMLLogger()
            instance.info("Message with context", job_id="123", user_id="456", status="pending")
            assert "Message with context" in caplog.text


class TestModuleLogger:
    def test_logger_instance(self):
        assert logger is not None
        assert isinstance(logger, AutoMLLogger)
    
    @pytest.mark.parametrize("name,expected_name", [
        (None, LOGGER_NAME),
        ("test.module", f"{LOGGER_NAME}.test.module"),
    ])
    def test_get_logger_function(self, name, expected_name):
        result = get_logger(name)
        assert result.name == expected_name


class TestIntegration:
    def test_logger_usage_flow(self, caplog):
        with caplog.at_level(logging.DEBUG):
            logger.info("Starting application", component="main")
            logger.debug("Debug info", value=42)
            logger.warning("Warning", threshold=0.9)
            logger.error("Error", code=500)
            
            custom_logger = logger.get_logger("api")
            custom_logger.info("API request")
            
            print(f"\nIntegration Test - All Logs:")
            print(f"  Total Records: {len(caplog.records)}")
            for i, record in enumerate(caplog.records, 1):
                print(f"  Record {i}: [{record.levelname}] {record.message}")
            print(f"  Full Captured Text:\n{caplog.text}")
            
            assert "Starting application" in caplog.text
            assert "API request" in caplog.text
    
    def test_exception_handling(self, caplog):
        with caplog.at_level(logging.ERROR):
            try:
                raise RuntimeError("Test runtime error")
            except Exception:
                logger.exception("Caught exception", context="integration_test")
            
            assert "Caught exception" in caplog.text
            assert "RuntimeError" in caplog.text or "Test runtime error" in caplog.text
