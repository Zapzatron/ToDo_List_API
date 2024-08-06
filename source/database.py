from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker
from source.models.models import Base
from secret_data import config


database_name = config.DB_NAME
username, password = config.DB_USERNAME, config.DB_PASSWORD
SQLALCHEMY_DATABASE_URL = f"postgresql+asyncpg://{username}:{password}@localhost/{database_name}"
# engine = create_async_engine(SQLALCHEMY_DATABASE_URL, echo=True)
engine = create_async_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, autocommit=False, autoflush=False,)


async def create_all_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_all_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def get_db():
    async with SessionLocal() as session:
        yield session
