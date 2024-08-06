from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from source.models import models
from source.schemas import schemas
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def get_user_by_username(db: AsyncSession, username: str):
    result = await db.execute(select(models.User).filter(models.User.username == username))
    return result.scalars().first()


async def check_user_auth(db: AsyncSession, user: schemas.UserCreate):
    """
    Проверка на наличие пользователя и на одинаковость пароля
    """

    db_user = await get_user_by_username(db, user.username)
    # print(f"check_user_auth: {db_user}")

    if not db_user:
        return False

    if not pwd_context.verify(user.password, db_user.hashed_password):
        return False

    return db_user


async def create_user(db: AsyncSession, user: schemas.UserCreate):
    hashed_password = pwd_context.hash(user.password)
    db_user = models.User(username=user.username, hashed_password=hashed_password)
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user
