"""Initialize database tables"""
import asyncio
from backend.database import engine, Base
from backend.models import *  # noqa: F401,F403 - Import all models to register them


async def init():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created successfully.")


if __name__ == "__main__":
    asyncio.run(init())
