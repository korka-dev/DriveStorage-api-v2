from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.config import settings

SQLALCHEMY_DATABASE_URL = settings.postgres_database_url.replace(
    "postgresql://", "postgresql+asyncpg://"
).split('?')[0]

async_engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={
        "ssl": "require",
    },
)

AsyncSessionLocal = sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

async def get_db_session():
    async with AsyncSessionLocal() as session:
        yield session

        