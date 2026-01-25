import os
import sys
import pytest
import asyncpg
import asyncio
from pathlib import Path
from src.config import config
from src.database.connection import Database
from src.database.models import create_tables

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

os.environ.setdefault("AUTOML_PORT", "8000")
os.environ.setdefault("AUTOML_LOGGER_LEVEL", "DEBUG")
os.environ.setdefault("AUTOML_OVERRIDE_BASE_URL", "http://localhost:8000")
os.environ.setdefault("AUTOML_RESEARCH_AGENT_API_KEY", "test-key")
os.environ.setdefault("AUTOML_RESEARCH_AGENT_MODEL", "test-model")
os.environ.setdefault("AUTOML_SUPERVISOR_AGENT_API_KEY", "test-key")
os.environ.setdefault("AUTOML_SUPERVISOR_AGENT_MODEL", "test-model")
os.environ.setdefault("AUTOML_CODE_AGENT_API_KEY", "test-key")
os.environ.setdefault("AUTOML_CODE_AGENT_MODEL", "test-model")
os.environ.setdefault("AUTOML_ANALYSIS_AGENT_API_KEY", "test-key")
os.environ.setdefault("AUTOML_ANALYSIS_AGENT_MODEL", "test-model")
os.environ.setdefault("AUTOML_REPORT_AGENT_API_KEY", "test-key")
os.environ.setdefault("AUTOML_REPORT_AGENT_MODEL", "test-model")
os.environ.setdefault("AUTOML_JWT_SECRET_KEY", "test-secret-key-minimum-32-characters-long-for-testing")
os.environ.setdefault("AUTOML_JWT_ALGORITHM", "HS256")
os.environ.setdefault("AUTOML_JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "15")
os.environ.setdefault("AUTOML_JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7")
os.environ.setdefault("AUTOML_DB_HOST", "localhost")
os.environ.setdefault("AUTOML_DB_PORT", "5432")
os.environ.setdefault("AUTOML_DB_USER", "automl_user")
os.environ.setdefault("AUTOML_DB_PASSWORD", "automl_password")
os.environ.setdefault("AUTOML_DB_NAME", "automl_db_test")
os.environ.setdefault("AUTOML_DB_SSL_MODE", "disable")
os.environ.setdefault("AUTOML_CORS_ORIGINS", "http://localhost:3000")
os.environ.setdefault("AUTOML_RATE_LIMIT_PER_MINUTE", "60")

@pytest.fixture(autouse=True, scope="function")
async def ensure_db_pool():
    try:
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
    except (RuntimeError, AttributeError, Exception) as e:
        if Database._pool is not None:
            try:
                await Database.close()
            except Exception:
                pass
        Database._pool = None
        await Database.get_pool()
    yield

@pytest.fixture(scope="session", autouse=True)
async def setup_test_database():
    try:
        admin_conn = await asyncpg.connect(
            host=config.db_host,
            port=config.db_port,
            user=config.db_user,
            password=config.db_password,
            database="postgres"
        )
        
        db_exists = await admin_conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1",
            config.db_name
        )
        
        if not db_exists:
            await admin_conn.execute(f'CREATE DATABASE "{config.db_name}"')
        
        await admin_conn.close()
        
        pool = await Database.get_pool()
        async with pool.acquire() as conn:
            await create_tables(conn)
        
        yield
        
        await Database.close()
        Database._pool = None
    except Exception as e:
        pytest.skip(f"Database setup failed: {e}")
