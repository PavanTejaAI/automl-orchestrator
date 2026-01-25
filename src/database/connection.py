import asyncio
from typing import Optional
import asyncpg
from src.config import config
from src.utils import logger

class Database:
    _pool: Optional[asyncpg.Pool] = None
    
    @classmethod
    async def get_pool(cls) -> asyncpg.Pool:
        if cls._pool is not None:
            try:
                if cls._pool.is_closing():
                    cls._pool = None
            except (AttributeError, RuntimeError):
                cls._pool = None
        
        if cls._pool is None:
            ssl_config = None
            if config.db_ssl_mode != "disable":
                ssl_config = {
                    "ssl": config.db_ssl_mode,
                }
                if config.db_ssl_cert:
                    ssl_config["ssl_cert"] = config.db_ssl_cert
                if config.db_ssl_key:
                    ssl_config["ssl_key"] = config.db_ssl_key
                if config.db_ssl_root_cert:
                    ssl_config["ssl_ca"] = config.db_ssl_root_cert
            
            cls._pool = await asyncpg.create_pool(
                host=config.db_host,
                port=config.db_port,
                user=config.db_user,
                password=config.db_password,
                database=config.db_name,
                ssl=ssl_config,
                min_size=5,
                max_size=20,
                command_timeout=60,
            )
            logger.info("Database connection pool created", ssl_mode=config.db_ssl_mode)
        
        return cls._pool
    
    @classmethod
    async def close(cls):
        if cls._pool:
            await cls._pool.close()
            cls._pool = None
            logger.info("Database connection pool closed")

async def get_db():
    pool = await Database.get_pool()
    async with pool.acquire() as connection:
        yield connection
