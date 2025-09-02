from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import MetaData
from typing import AsyncGenerator
import aioredis
from aioredis import Redis
from contextlib import asunccontextmanager

from .config import get_database_url, get_redis_url, settings

# SQLAlchemy Base
Base = declarative_base()

# Naming convention for constraints
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

Base.metadata = MetaData(naming_convention=convention)

# Database engine and session

engine = None
SessionLocal = None
redis_pool = None

async def init_database():
    # Start DB connection
    global engine, SessionLocal

    database_url = get_database_url()

    engine = create_async_engine(
        database_url,
        echo=settings.database_echo,
        future=True,
        connect_args={"check_same_thread": False} if "sqlite" in database_url else {}
    )

    SessionLocal = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def init_redis():

    # Start Redis connection
    global redis_pool

    redis_url = get_redis_url()

    if redis_url:
        try:
            redis_pool = aioredis.from_url(
                redis_url,
                decode_responses=True,
                retry_on_timeout=True,
                socket_keepalive=True,
                socket_keepalive_options={}
            )
            # Test connection
            await redis_pool.ping()
            print(f"Redis connected: {redis_url}")
        except Exception as e:
            print(f"Redis connection failed: {e}")
            redis_pool = None
    else:
        print("Redis disabled")

async def close_database():
    # Close DB connection
    global engine
    if engine:
        await engine.dispose()

async def close_redis():
    # Close Redis connection
    global redis_pool
    if redis_pool:
        await redis_pool.close()

# For dependency injection

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session."""
    if not SessionLocal:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def get_redis() -> Redis | None:
    return redis_pool

@asunccontextmanager
async def get_db_session():
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

async def check_database_health() -> bool:
    """Check if the database connection is healthy."""
    try:
        async with get_db_session() as session:
            await session.execute("SELECT 1")
    except Exception:
        return False
    
async def check_redis_health() -> bool:
    try:
        if redis_pool:
            await redis_pool.ping()
            return True
        return False
    except Exception:
        return False