import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from src.utils import logger


class Config:
    _instance: Optional["Config"] = None
    _initialized = False
    
    ENV_PREFIX = "AUTOML_"
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._load_env_file()
        self._load_config()
        self._initialized = True
    
    def _load_env_file(self):
        if Path(".env").exists():
            load_dotenv(override=False)
            logger.info("Environment variables loaded from .env file")
    
    def _get_env(self, key: str) -> str:
        value = os.getenv(key)
        if value is None:
            raise ValueError(f"Required environment variable {key} is not set")
        return value
    
    def _get_env_optional(self, key: str, default: str = "") -> str:
        return os.getenv(key, default)
    
    def _load_config(self):
        self.port = int(self._get_env(f"{self.ENV_PREFIX}PORT"))
        self.logger_level = self._get_env(f"{self.ENV_PREFIX}LOGGER_LEVEL")
        self.override_base_url = self._get_env(f"{self.ENV_PREFIX}OVERRIDE_BASE_URL")
        
        self.research_agent_api_key = self._get_env(f"{self.ENV_PREFIX}RESEARCH_AGENT_API_KEY")
        self.research_agent_model = self._get_env(f"{self.ENV_PREFIX}RESEARCH_AGENT_MODEL")
        
        self.supervisor_agent_api_key = self._get_env(f"{self.ENV_PREFIX}SUPERVISOR_AGENT_API_KEY")
        self.supervisor_agent_model = self._get_env(f"{self.ENV_PREFIX}SUPERVISOR_AGENT_MODEL")
        
        self.code_agent_api_key = self._get_env(f"{self.ENV_PREFIX}CODE_AGENT_API_KEY")
        self.code_agent_model = self._get_env(f"{self.ENV_PREFIX}CODE_AGENT_MODEL")
        
        self.analysis_agent_api_key = self._get_env(f"{self.ENV_PREFIX}ANALYSIS_AGENT_API_KEY")
        self.analysis_agent_model = self._get_env(f"{self.ENV_PREFIX}ANALYSIS_AGENT_MODEL")
        
        self.report_agent_api_key = self._get_env(f"{self.ENV_PREFIX}REPORT_AGENT_API_KEY")
        self.report_agent_model = self._get_env(f"{self.ENV_PREFIX}REPORT_AGENT_MODEL")
        
        self.jwt_secret_key = self._get_env(f"{self.ENV_PREFIX}JWT_SECRET_KEY")
        self.jwt_algorithm = self._get_env_optional(f"{self.ENV_PREFIX}JWT_ALGORITHM", "HS256")
        self.jwt_access_token_expire_minutes = int(self._get_env_optional(f"{self.ENV_PREFIX}JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
        self.jwt_refresh_token_expire_days = int(self._get_env_optional(f"{self.ENV_PREFIX}JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))
        
        self.db_host = self._get_env(f"{self.ENV_PREFIX}DB_HOST")
        self.db_port = int(self._get_env_optional(f"{self.ENV_PREFIX}DB_PORT", "5432"))
        self.db_user = self._get_env(f"{self.ENV_PREFIX}DB_USER")
        self.db_password = self._get_env(f"{self.ENV_PREFIX}DB_PASSWORD")
        self.db_name = self._get_env(f"{self.ENV_PREFIX}DB_NAME")
        self.db_ssl_mode = self._get_env_optional(f"{self.ENV_PREFIX}DB_SSL_MODE", "require")
        self.db_ssl_cert = self._get_env_optional(f"{self.ENV_PREFIX}DB_SSL_CERT", "")
        self.db_ssl_key = self._get_env_optional(f"{self.ENV_PREFIX}DB_SSL_KEY", "")
        self.db_ssl_root_cert = self._get_env_optional(f"{self.ENV_PREFIX}DB_SSL_ROOT_CERT", "")
        
        self.cors_origins = self._get_env_optional(f"{self.ENV_PREFIX}CORS_ORIGINS", "http://localhost:3000,http://localhost:8080").split(",")
        self.rate_limit_per_minute = int(self._get_env_optional(f"{self.ENV_PREFIX}RATE_LIMIT_PER_MINUTE", "60"))
        
        self.tavily_api_key = self._get_env_optional("TAVILY_API_KEY", "")
        self.kaggle_api_token = self._get_env_optional("KAGGLE_API_TOKEN", "")
        self.research_rate_limit_per_minute = int(self._get_env_optional(f"{self.ENV_PREFIX}RESEARCH_RATE_LIMIT_PER_MINUTE", "30"))
        self.circuit_breaker_threshold = int(self._get_env_optional(f"{self.ENV_PREFIX}CIRCUIT_BREAKER_THRESHOLD", "5"))
        self.circuit_breaker_timeout = int(self._get_env_optional(f"{self.ENV_PREFIX}CIRCUIT_BREAKER_TIMEOUT", "60"))


        
        logger.set_level(self.logger_level)
        
        logger.info(
            "Configuration loaded successfully",
            port=self.port,
            logger_level=self.logger_level,
            db_host=self.db_host,
            db_name=self.db_name,
            jwt_algorithm=self.jwt_algorithm,
        )


config = Config()
