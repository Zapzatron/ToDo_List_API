from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, and_
from source.models import models
from source.schemas import schemas
from source.crud import user_account


async def create_task(db: AsyncSession, task: schemas.TaskCreate):
    db_task = models.Task(**task.model_dump(mode="json"))
    # print(db_task)
    db.add(db_task)
    await db.commit()
    await db.refresh(db_task)
    # print(db_task)
    return db_task


async def create_task_with_permissions(db: AsyncSession, task: schemas.TaskCreate):
    new_task = models.Task(**task.model_dump(mode="json"))
    db.add(new_task)

    await db.flush()

    owner_permission = models.TaskPermission(
        task_id=new_task.id,
        user_id=new_task.owner_id,
        can_read=True,
        can_update=True
    )
    db.add(owner_permission)

    await db.commit()

    await db.refresh(new_task)

    return new_task


async def get_task(db: AsyncSession, task_id: int):
    result = await db.execute(select(models.Task).filter(models.Task.id == task_id))
    return result.scalars().first()


async def get_tasks(db: AsyncSession, skip: int = 0, limit: int = 10):
    result = await db.execute(select(models.Task).offset(skip).limit(limit))
    return result.scalars().all()


async def get_tasks_by_username(db: AsyncSession, username: str, skip: int = 0, limit: int = 10):
    user_id: int = (await user_account.get_user_by_username(db, username)).id

    result = await db.execute(select(models.Task).filter(models.Task.owner_id == user_id).offset(skip).limit(limit))
    return result.scalars().all()


async def get_tasks_by_user_id(db: AsyncSession, user_id: int, skip: int = 0, limit: int = 10):
    """
    Возвращает все задачи, к которым есть доступ у user_id. (Созданные им же и те, к которым ему дали доступ)
    Также есть ограничения skip (сколько задач пропустить) и limit (сколько максимально можно вернуть задач)
    """
    query = (
        select(models.Task)
        .join(models.Task.permissions, isouter=True)
        .filter(
            or_(
                models.Task.owner_id == user_id,
                models.TaskPermission.user_id == user_id
            )
        )
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(query)
    return result.scalars().unique().all()


async def update_task(db: AsyncSession, task_id: int, task: schemas.TaskBase):
    result = await db.execute(select(models.Task).filter(models.Task.id == task_id))
    db_task = result.scalars().first()

    if db_task:
        db_task.title = task.title
        db_task.description = task.description
        await db.commit()
        await db.refresh(db_task)
        return db_task
    return None


async def delete_task(db: AsyncSession, task_id: int):
    result = await db.execute(select(models.Task).filter(models.Task.id == task_id))
    db_task = result.scalars().first()

    if db_task:
        await db.delete(db_task)
        await db.commit()
        return True
    return False


async def update_task_permissions(db: AsyncSession, task_id: int, user_id: int,
                                  can_read: bool = None, can_update: bool = None):
    result = await db.execute(select(models.Task).filter(models.Task.id == task_id))
    db_task = result.scalars().first()

    if not db_task:
        return None

    result = await db.execute(select(models.TaskPermission).filter(
        and_(
            models.TaskPermission.task_id == task_id,
            models.TaskPermission.user_id == user_id
        )
    ))

    task_permission = result.scalars().first()

    # print(task_permission)

    if not task_permission:
        task_permission = models.TaskPermission(task_id=task_id, user_id=user_id,
                                                can_read=can_read, can_update=can_update)
        db.add(task_permission)
    else:
        if can_read is not None:
            task_permission.can_read = can_read
        if can_update is not None:
            task_permission.can_update = can_update

    await db.commit()
    return schemas.TaskPermission(task_id=task_id, user_id=user_id,
                                  can_read=can_read or False, can_update=can_update or False)


async def check_read_permission(db: AsyncSession, task_id: int, user_id: int):
    result = await db.execute(select(models.TaskPermission).filter(
        and_(
            models.TaskPermission.task_id == task_id,
            models.TaskPermission.user_id == user_id
        )))
    permission = result.scalars().first()
    # print(f"permission: {permission}")

    if permission and permission.can_read:
        return True
    return False


async def check_update_permission(db: AsyncSession, task_id: int, user_id: int):
    result = await db.execute(select(models.TaskPermission).filter(
        and_(
            models.TaskPermission.task_id == task_id,
            models.TaskPermission.user_id == user_id
        )))
    permission = result.scalars().first()
    # print(f"permission: {permission}")

    if permission and permission.can_update:
        return True
    return False
