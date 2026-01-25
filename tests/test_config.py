import os
from pathlib import Path
from unittest.mock import patch

import pytest

from src.config import config


class TestConfigSingleton:
    def test_singleton_pattern(self):
        from src.config.config import Config
        config1 = Config()
        config2 = Config()
        assert config1 is config2
        assert id(config1) == id(config2)
    
    def test_singleton_persistence(self):
        from src.config.config import Config
        instance1 = Config()
        instance2 = Config()
        instance3 = Config()
        assert instance1 is instance2 is instance3


class TestConfigAttributes:
    def test_all_required_attributes_exist(self):
        required_attrs = [
            "port",
            "logger_level",
            "override_base_url",
            "research_agent_api_key",
            "research_agent_model",
            "supervisor_agent_api_key",
            "supervisor_agent_model",
            "code_agent_api_key",
            "code_agent_model",
            "analysis_agent_api_key",
            "analysis_agent_model",
            "report_agent_api_key",
            "report_agent_model",
        ]
        
        for attr in required_attrs:
            assert hasattr(config, attr), f"Missing attribute: {attr}"
            assert getattr(config, attr) is not None, f"Attribute {attr} is None"
    
    def test_port_type_and_range(self):
        assert isinstance(config.port, int)
        assert config.port > 0
        assert config.port <= 65535
        assert config.port == int(config.port)
    
    def test_logger_level_validation(self):
        assert isinstance(config.logger_level, str)
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        assert config.logger_level.upper() in valid_levels
    
    def test_override_base_url_format(self):
        assert isinstance(config.override_base_url, str)
        assert len(config.override_base_url) > 0
        assert config.override_base_url.startswith(("http://", "https://"))
        assert "." in config.override_base_url
    
    def test_agent_api_keys_not_empty(self):
        agents = ["research", "supervisor", "code", "analysis", "report"]
        for agent in agents:
            api_key = getattr(config, f"{agent}_agent_api_key")
            assert isinstance(api_key, str)
            assert len(api_key.strip()) > 0
            assert api_key == api_key.strip()
    
    def test_agent_models_not_empty(self):
        agents = ["research", "supervisor", "code", "analysis", "report"]
        for agent in agents:
            model = getattr(config, f"{agent}_agent_model")
            assert isinstance(model, str)
            assert len(model.strip()) > 0
            assert model == model.strip()


class TestConfigLoading:
    def test_loads_from_env_file_when_exists(self):
        env_file = Path(".env")
        if env_file.exists():
            assert config.port is not None
            assert config.logger_level is not None
            assert config.override_base_url is not None
    
    @patch.dict(os.environ, {
        "AUTOML_PORT": "9000",
        "AUTOML_LOGGER_LEVEL": "WARNING",
        "AUTOML_OVERRIDE_BASE_URL": "https://test-api.example.com",
        "AUTOML_RESEARCH_AGENT_API_KEY": "test-research-key-123",
        "AUTOML_RESEARCH_AGENT_MODEL": "gpt-4-turbo",
        "AUTOML_SUPERVISOR_AGENT_API_KEY": "test-supervisor-key-456",
        "AUTOML_SUPERVISOR_AGENT_MODEL": "gpt-4",
        "AUTOML_CODE_AGENT_API_KEY": "test-code-key-789",
        "AUTOML_CODE_AGENT_MODEL": "claude-3",
        "AUTOML_ANALYSIS_AGENT_API_KEY": "test-analysis-key-abc",
        "AUTOML_ANALYSIS_AGENT_MODEL": "gpt-3.5",
        "AUTOML_REPORT_AGENT_API_KEY": "test-report-key-def",
        "AUTOML_REPORT_AGENT_MODEL": "gpt-4",
    })
    def test_loads_all_values_from_environment(self):
        from src.config.config import Config
        
        Config._initialized = False
        Config._instance = None
        
        test_config = Config()
        
        assert test_config.port == 9000
        assert test_config.logger_level == "WARNING"
        assert test_config.override_base_url == "https://test-api.example.com"
        assert test_config.research_agent_api_key == "test-research-key-123"
        assert test_config.research_agent_model == "gpt-4-turbo"
        assert test_config.supervisor_agent_api_key == "test-supervisor-key-456"
        assert test_config.supervisor_agent_model == "gpt-4"
        assert test_config.code_agent_api_key == "test-code-key-789"
        assert test_config.code_agent_model == "claude-3"
        assert test_config.analysis_agent_api_key == "test-analysis-key-abc"
        assert test_config.analysis_agent_model == "gpt-3.5"
        assert test_config.report_agent_api_key == "test-report-key-def"
        assert test_config.report_agent_model == "gpt-4"


class TestConfigErrorHandling:
    @pytest.mark.parametrize("missing_var", [
        "AUTOML_PORT",
        "AUTOML_LOGGER_LEVEL",
        "AUTOML_OVERRIDE_BASE_URL",
        "AUTOML_RESEARCH_AGENT_API_KEY",
        "AUTOML_RESEARCH_AGENT_MODEL",
        "AUTOML_SUPERVISOR_AGENT_API_KEY",
        "AUTOML_SUPERVISOR_AGENT_MODEL",
        "AUTOML_CODE_AGENT_API_KEY",
        "AUTOML_CODE_AGENT_MODEL",
        "AUTOML_ANALYSIS_AGENT_API_KEY",
        "AUTOML_ANALYSIS_AGENT_MODEL",
        "AUTOML_REPORT_AGENT_API_KEY",
        "AUTOML_REPORT_AGENT_MODEL",
    ])
    @patch("src.config.config.Path")
    def test_missing_individual_env_var_raises_error(self, mock_path_class, missing_var):
        from src.config.config import Config
        
        mock_path_instance = mock_path_class.return_value
        mock_path_instance.exists.return_value = False
        
        all_vars = {
            "AUTOML_PORT": "8000",
            "AUTOML_LOGGER_LEVEL": "INFO",
            "AUTOML_OVERRIDE_BASE_URL": "https://test.com",
            "AUTOML_RESEARCH_AGENT_API_KEY": "key1",
            "AUTOML_RESEARCH_AGENT_MODEL": "model1",
            "AUTOML_SUPERVISOR_AGENT_API_KEY": "key2",
            "AUTOML_SUPERVISOR_AGENT_MODEL": "model2",
            "AUTOML_CODE_AGENT_API_KEY": "key3",
            "AUTOML_CODE_AGENT_MODEL": "model3",
            "AUTOML_ANALYSIS_AGENT_API_KEY": "key4",
            "AUTOML_ANALYSIS_AGENT_MODEL": "model4",
            "AUTOML_REPORT_AGENT_API_KEY": "key5",
            "AUTOML_REPORT_AGENT_MODEL": "model5",
        }
        
        all_vars.pop(missing_var)
        
        Config._initialized = False
        Config._instance = None
        
        with patch.dict(os.environ, all_vars, clear=True):
            with pytest.raises(ValueError) as exc_info:
                Config()
            
            assert missing_var in str(exc_info.value)
            assert "Required environment variable" in str(exc_info.value)
    
    @patch("src.config.config.Path")
    @patch.dict(os.environ, {}, clear=True)
    def test_missing_all_env_vars_raises_error(self, mock_path_class):
        from src.config.config import Config
        
        mock_path_instance = mock_path_class.return_value
        mock_path_instance.exists.return_value = False
        
        Config._initialized = False
        Config._instance = None
        
        with pytest.raises(ValueError, match="Required environment variable"):
            Config()
    
    @patch.dict(os.environ, {
        "AUTOML_PORT": "invalid-port",
        "AUTOML_LOGGER_LEVEL": "INFO",
        "AUTOML_OVERRIDE_BASE_URL": "https://test.com",
        "AUTOML_RESEARCH_AGENT_API_KEY": "key",
        "AUTOML_RESEARCH_AGENT_MODEL": "model",
        "AUTOML_SUPERVISOR_AGENT_API_KEY": "key",
        "AUTOML_SUPERVISOR_AGENT_MODEL": "model",
        "AUTOML_CODE_AGENT_API_KEY": "key",
        "AUTOML_CODE_AGENT_MODEL": "model",
        "AUTOML_ANALYSIS_AGENT_API_KEY": "key",
        "AUTOML_ANALYSIS_AGENT_MODEL": "model",
        "AUTOML_REPORT_AGENT_API_KEY": "key",
        "AUTOML_REPORT_AGENT_MODEL": "model",
    })
    def test_invalid_port_value_raises_error(self):
        from src.config.config import Config
        
        Config._initialized = False
        Config._instance = None
        
        with pytest.raises(ValueError):
            Config()
    
    @patch.dict(os.environ, {
        "AUTOML_PORT": "",
        "AUTOML_LOGGER_LEVEL": "INFO",
        "AUTOML_OVERRIDE_BASE_URL": "https://test.com",
        "AUTOML_RESEARCH_AGENT_API_KEY": "key",
        "AUTOML_RESEARCH_AGENT_MODEL": "model",
        "AUTOML_SUPERVISOR_AGENT_API_KEY": "key",
        "AUTOML_SUPERVISOR_AGENT_MODEL": "model",
        "AUTOML_CODE_AGENT_API_KEY": "key",
        "AUTOML_CODE_AGENT_MODEL": "model",
        "AUTOML_ANALYSIS_AGENT_API_KEY": "key",
        "AUTOML_ANALYSIS_AGENT_MODEL": "model",
        "AUTOML_REPORT_AGENT_API_KEY": "key",
        "AUTOML_REPORT_AGENT_MODEL": "model",
    })
    def test_empty_port_value_raises_error(self):
        from src.config.config import Config
        
        Config._initialized = False
        Config._instance = None
        
        with pytest.raises(ValueError):
            Config()
    
    @patch.dict(os.environ, {
        "AUTOML_PORT": "0",
        "AUTOML_LOGGER_LEVEL": "INFO",
        "AUTOML_OVERRIDE_BASE_URL": "https://test.com",
        "AUTOML_RESEARCH_AGENT_API_KEY": "key",
        "AUTOML_RESEARCH_AGENT_MODEL": "model",
        "AUTOML_SUPERVISOR_AGENT_API_KEY": "key",
        "AUTOML_SUPERVISOR_AGENT_MODEL": "model",
        "AUTOML_CODE_AGENT_API_KEY": "key",
        "AUTOML_CODE_AGENT_MODEL": "model",
        "AUTOML_ANALYSIS_AGENT_API_KEY": "key",
        "AUTOML_ANALYSIS_AGENT_MODEL": "model",
        "AUTOML_REPORT_AGENT_API_KEY": "key",
        "AUTOML_REPORT_AGENT_MODEL": "model",
    })
    def test_zero_port_value_allowed(self):
        from src.config.config import Config
        
        Config._initialized = False
        Config._instance = None
        
        test_config = Config()
        assert test_config.port == 0
    
    @patch.dict(os.environ, {
        "AUTOML_PORT": "-1",
        "AUTOML_LOGGER_LEVEL": "INFO",
        "AUTOML_OVERRIDE_BASE_URL": "https://test.com",
        "AUTOML_RESEARCH_AGENT_API_KEY": "key",
        "AUTOML_RESEARCH_AGENT_MODEL": "model",
        "AUTOML_SUPERVISOR_AGENT_API_KEY": "key",
        "AUTOML_SUPERVISOR_AGENT_MODEL": "model",
        "AUTOML_CODE_AGENT_API_KEY": "key",
        "AUTOML_CODE_AGENT_MODEL": "model",
        "AUTOML_ANALYSIS_AGENT_API_KEY": "key",
        "AUTOML_ANALYSIS_AGENT_MODEL": "model",
        "AUTOML_REPORT_AGENT_API_KEY": "key",
        "AUTOML_REPORT_AGENT_MODEL": "model",
    })
    def test_negative_port_value_allowed(self):
        from src.config.config import Config
        
        Config._initialized = False
        Config._instance = None
        
        test_config = Config()
        assert test_config.port == -1


class TestConfigEdgeCases:
    @patch.dict(os.environ, {
        "AUTOML_PORT": "65535",
        "AUTOML_LOGGER_LEVEL": "CRITICAL",
        "AUTOML_OVERRIDE_BASE_URL": "http://localhost:8080/api/v1",
        "AUTOML_RESEARCH_AGENT_API_KEY": "sk-very-long-api-key-with-special-chars-!@#$%^&*()",
        "AUTOML_RESEARCH_AGENT_MODEL": "gpt-4-turbo-preview-2024-01-01",
        "AUTOML_SUPERVISOR_AGENT_API_KEY": "key",
        "AUTOML_SUPERVISOR_AGENT_MODEL": "model",
        "AUTOML_CODE_AGENT_API_KEY": "key",
        "AUTOML_CODE_AGENT_MODEL": "model",
        "AUTOML_ANALYSIS_AGENT_API_KEY": "key",
        "AUTOML_ANALYSIS_AGENT_MODEL": "model",
        "AUTOML_REPORT_AGENT_API_KEY": "key",
        "AUTOML_REPORT_AGENT_MODEL": "model",
    })
    def test_boundary_values(self):
        from src.config.config import Config
        
        Config._initialized = False
        Config._instance = None
        
        test_config = Config()
        
        assert test_config.port == 65535
        assert test_config.logger_level == "CRITICAL"
        assert test_config.override_base_url == "http://localhost:8080/api/v1"
        assert "special-chars" in test_config.research_agent_api_key
    
    @patch.dict(os.environ, {
        "AUTOML_PORT": "1",
        "AUTOML_LOGGER_LEVEL": "DEBUG",
        "AUTOML_OVERRIDE_BASE_URL": "https://a.co",
        "AUTOML_RESEARCH_AGENT_API_KEY": "a",
        "AUTOML_RESEARCH_AGENT_MODEL": "b",
        "AUTOML_SUPERVISOR_AGENT_API_KEY": "c",
        "AUTOML_SUPERVISOR_AGENT_MODEL": "d",
        "AUTOML_CODE_AGENT_API_KEY": "e",
        "AUTOML_CODE_AGENT_MODEL": "f",
        "AUTOML_ANALYSIS_AGENT_API_KEY": "g",
        "AUTOML_ANALYSIS_AGENT_MODEL": "h",
        "AUTOML_REPORT_AGENT_API_KEY": "i",
        "AUTOML_REPORT_AGENT_MODEL": "j",
    })
    def test_minimum_length_values(self):
        from src.config.config import Config
        
        Config._initialized = False
        Config._instance = None
        
        test_config = Config()
        
        assert test_config.port == 1
        assert test_config.logger_level == "DEBUG"
        assert len(test_config.research_agent_api_key) == 1
        assert len(test_config.research_agent_model) == 1


class TestConfigWhitespaceHandling:
    @patch.dict(os.environ, {
        "AUTOML_PORT": "  8000  ",
        "AUTOML_LOGGER_LEVEL": "  INFO  ",
        "AUTOML_OVERRIDE_BASE_URL": "  https://test.com  ",
        "AUTOML_RESEARCH_AGENT_API_KEY": "  key  ",
        "AUTOML_RESEARCH_AGENT_MODEL": "  model  ",
        "AUTOML_SUPERVISOR_AGENT_API_KEY": "key",
        "AUTOML_SUPERVISOR_AGENT_MODEL": "model",
        "AUTOML_CODE_AGENT_API_KEY": "key",
        "AUTOML_CODE_AGENT_MODEL": "model",
        "AUTOML_ANALYSIS_AGENT_API_KEY": "key",
        "AUTOML_ANALYSIS_AGENT_MODEL": "model",
        "AUTOML_REPORT_AGENT_API_KEY": "key",
        "AUTOML_REPORT_AGENT_MODEL": "model",
    })
    def test_whitespace_in_values(self):
        from src.config.config import Config
        
        Config._initialized = False
        Config._instance = None
        
        test_config = Config()
        
        assert test_config.port == 8000
        assert test_config.logger_level == "  INFO  "
        assert test_config.override_base_url == "  https://test.com  "
        assert test_config.research_agent_api_key == "  key  "


class TestConfigInitialization:
    def test_config_initialized_only_once(self):
        from src.config.config import Config
        
        Config._initialized = False
        Config._instance = None
        
        instance1 = Config()
        initial_port = instance1.port
        
        instance2 = Config()
        assert instance2.port == initial_port
        assert instance1 is instance2
    
    @patch("src.config.config.Path")
    def test_env_file_not_loaded_when_not_exists(self, mock_path_class):
        from src.config.config import Config
        
        mock_path_instance = mock_path_class.return_value
        mock_path_instance.exists.return_value = False
        
        Config._initialized = False
        Config._instance = None
        
        with patch.dict(os.environ, {
            "AUTOML_PORT": "7000",
            "AUTOML_LOGGER_LEVEL": "ERROR",
            "AUTOML_OVERRIDE_BASE_URL": "https://env-only.com",
            "AUTOML_RESEARCH_AGENT_API_KEY": "env-key",
            "AUTOML_RESEARCH_AGENT_MODEL": "env-model",
            "AUTOML_SUPERVISOR_AGENT_API_KEY": "key",
            "AUTOML_SUPERVISOR_AGENT_MODEL": "model",
            "AUTOML_CODE_AGENT_API_KEY": "key",
            "AUTOML_CODE_AGENT_MODEL": "model",
            "AUTOML_ANALYSIS_AGENT_API_KEY": "key",
            "AUTOML_ANALYSIS_AGENT_MODEL": "model",
            "AUTOML_REPORT_AGENT_API_KEY": "key",
            "AUTOML_REPORT_AGENT_MODEL": "model",
        }):
            test_config = Config()
            assert test_config.port == 7000
            assert test_config.logger_level == "ERROR"


class TestConfigIntegration:
    def test_config_instance_accessible(self):
        assert config is not None
        assert hasattr(config, "port")
        assert hasattr(config, "logger_level")
    
    def test_all_agent_configs_loaded(self):
        agents = ["research", "supervisor", "code", "analysis", "report"]
        for agent in agents:
            assert hasattr(config, f"{agent}_agent_api_key")
            assert hasattr(config, f"{agent}_agent_model")
            assert getattr(config, f"{agent}_agent_api_key")
            assert getattr(config, f"{agent}_agent_model")
    
    def test_config_values_are_accessible(self):
        assert isinstance(config.port, int)
        assert isinstance(config.logger_level, str)
        assert isinstance(config.override_base_url, str)
        
        for agent in ["research", "supervisor", "code", "analysis", "report"]:
            assert isinstance(getattr(config, f"{agent}_agent_api_key"), str)
            assert isinstance(getattr(config, f"{agent}_agent_model"), str)
