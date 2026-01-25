from src.database.connection import Database
from src.database.models import create_tables
from src.utils import logger


async def init_database():
    pool = await Database.get_pool()
    async with pool.acquire() as conn:
        await create_tables(conn)
    logger.info("Database initialized")


async def close_database():
    await Database.close()
    logger.info("Database closed")
