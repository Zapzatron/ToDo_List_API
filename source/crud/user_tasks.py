from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
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


async def update_task_permissions(db: AsyncSession, task_id: int, granted_user_id: int,
                                  can_read: bool = None, can_update: bool = None):
    result = await db.execute(select(models.Task).filter(models.Task.id == task_id))
    db_task = result.scalars().first()

    if not db_task:
        return None

    result = await db.execute(select(models.TaskPermission).filter(models.TaskPermission.task_id == task_id))
    task_permission = result.scalars().first()

    if not task_permission:
        task_permission = models.TaskPermission(task_id=task_id, user_id=granted_user_id,
                                                can_read=can_read, can_update=can_update)
        db.add(task_permission)
    else:
        if can_read is not None:
            task_permission.can_read = can_read
        if can_update is not None:
            task_permission.can_update = can_update

    await db.commit()
    return schemas.TaskPermission(task_id=task_id, granted_user_id=granted_user_id,
                                  can_read=can_read or False, can_update=can_update or False)


async def check_read_permission(db: AsyncSession, task_id: int, user_id: int):
    result = await db.execute(select(models.TaskPermission).filter(
        models.TaskPermission.task_id == task_id and models.TaskPermission.user_id == user_id))
    permission = result.scalars().first()
    # print(f"permission: {permission}")

    if permission and permission.can_read:
        return True
    return False


async def check_update_permission(db: AsyncSession, task_id: int, user_id: int):
    result = await db.execute(select(models.TaskPermission).filter(
        models.TaskPermission.task_id == task_id and models.TaskPermission.user_id == user_id))
    permission = result.scalars().first()
    # print(f"permission: {permission}")

    if permission and permission.can_update:
        return True
    return False
