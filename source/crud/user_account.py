from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from source.models import models
from source.schemas import schemas
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from secret_data import config


SECRET_KEY = config.SECRET_KEY
ALGORITHM = config.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = config.ACCESS_TOKEN_EXPIRE_MINUTES

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


def create_access_token(data: dict, expires_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES):
    to_encode = data.copy()

    expire = datetime.utcnow() + timedelta(minutes=expires_minutes)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": encoded_jwt, "expire_minutes": expires_minutes}


async def check_user_token_auth(db: AsyncSession, token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("username")

        if username is None:
            return False

        db_user = await get_user_by_username(db, username=username)

        if not db_user:
            return False

        return db_user
    except JWTError:
        return False


async def create_user(db: AsyncSession, user: schemas.UserCreate):
    hashed_password = pwd_context.hash(user.password)
    db_user = models.User(username=user.username, hashed_password=hashed_password)
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user
