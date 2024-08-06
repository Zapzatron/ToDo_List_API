from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from source.schemas import schemas
from source.crud import user_account, user_tasks
from typing import List
import source.database as database
from contextlib import asynccontextmanager
import uvicorn
import os


class CustomHTTPException(HTTPException):
    def __init__(self, status_code: int, content: dict):
        self.status_code = status_code
        self.content = content

    def __call__(self):
        return JSONResponse(status_code=self.status_code, content=self.content)


@asynccontextmanager
async def lifespan(app_: FastAPI):
    if os.getenv("TESTING") != "true":  # Проверка на тестовую среду
        await database.create_all_tables()

    yield

    # В проде нужно закомментировать database.drop_all_tables(),
    # он есть для удобства тестирования
    if os.getenv("TESTING") != "true":  # Проверка на тестовую среду
        await database.drop_all_tables()

app = FastAPI(lifespan=lifespan)
get_db = database.get_db


@app.exception_handler(CustomHTTPException)
async def custom_http_exception_handler(request: Request, exc: CustomHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.content
    )


@app.post("/users/create", response_model=schemas.User)
async def create_user(user: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    db_user = await user_account.get_user_by_username(db, username=user.username)

    if db_user:
        error_code = 403
        error_json = {"error": {"message": f"Имя '{user.username}' уже зарегистрировано", "code": error_code}}
        return JSONResponse(error_json, error_code)

    return await user_account.create_user(db=db, user=user)


async def check_user_auth_with_raise(db, user):
    check_user = await user_account.check_user_auth(db, user)

    if not check_user:
        error_code = 403
        error_json = {"error": {"message": "Проверка пользователя не пройдена", "code": error_code}}
        raise CustomHTTPException(error_code, error_json)
    return check_user


@app.post("/tasks/check_auth")
async def check_auth(user: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    await check_user_auth_with_raise(db, user)
    return {"status": "success"}


@app.post("/tasks/create", response_model=schemas.Task)
async def create_task(task_user: schemas.TaskUserCreate, db: AsyncSession = Depends(get_db)):
    user = task_user.user
    task = task_user.task

    await check_user_auth_with_raise(db, user)

    db_task = await user_tasks.create_task(db=db, task=task)
    return db_task


@app.post("/tasks/read/{task_id}", response_model=schemas.Task)
async def read_task(user: schemas.UserCreate, task_id: int, db: AsyncSession = Depends(get_db)):
    user = await check_user_auth_with_raise(db, user)

    if not await user_tasks.check_read_permission(db, task_id, user.id):
        error_code = 403
        error_json = {"error": {"message": f"Не достаточно прав для чтения задачи '{task_id}'", "code": error_code}}
        raise CustomHTTPException(error_code, error_json)

    db_task = await user_tasks.get_task(db, task_id)

    if not db_task:
        error_code = 404
        error_json = {"error": {"message": f"Задача '{task_id}' не найдена", "code": error_code}}
        raise CustomHTTPException(error_code, error_json)

    return db_task


@app.post("/tasks/read_tasks", response_model=List[schemas.Task])
async def read_tasks(user: schemas.UserCreate, skip: int = 0, limit: int = 10, db: AsyncSession = Depends(get_db)):
    await check_user_auth_with_raise(db, user)

    tasks = await user_tasks.get_tasks_by_username(db, user.username, skip=skip, limit=limit)

    return tasks


@app.post("/tasks/update/{task_id}", response_model=schemas.Task)
async def update_task(user: schemas.UserCreate, task_id: int, task: schemas.TaskBase,
                      db: AsyncSession = Depends(get_db)):
    user = await check_user_auth_with_raise(db, user)

    if not await user_tasks.check_update_permission(db, task_id, user.id):
        error_code = 403
        error_json = {"error": {"message": f"Не достаточно прав для обновления задачи '{task_id}'", "code": error_code}}
        raise CustomHTTPException(error_code, error_json)

    db_task = await user_tasks.update_task(db, task_id, task)

    if not db_task:
        error_code = 404
        error_json = {"error": {"message": f"Задача '{task_id}' не найдена", "code": error_code}}
        raise CustomHTTPException(error_code, error_json)

    return db_task


@app.post("/tasks/delete/{task_id}")
async def delete_task(user: schemas.UserCreate, task_id: int, db: AsyncSession = Depends(get_db)):
    await check_user_auth_with_raise(db, user)

    db_task = await user_tasks.delete_task(db=db, task_id=task_id)

    if not db_task:
        error_code = 404
        error_json = {"error": {"message": f"Задача '{task_id}' не найдена", "code": error_code}}
        raise CustomHTTPException(error_code, error_json)

    return {"status": "success"}


@app.post("/tasks/update_permissions/{task_id}", response_model=schemas.TaskPermission)
async def update_task_permissions(task_permission_data: schemas.TaskPermissionUpdate, task_id: int,
                                  db: AsyncSession = Depends(get_db)):
    user = task_permission_data.user

    await check_user_auth_with_raise(db, user)

    granted_user_id = task_permission_data.granted_user_id
    can_read = task_permission_data.can_read
    can_update = task_permission_data.can_update

    task_permissions = await user_tasks.update_task_permissions(db, task_id, granted_user_id,
                                                                can_read=can_read, can_update=can_update)

    return task_permissions


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.35", port=8000)
