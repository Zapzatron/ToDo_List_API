from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from source.schemas import schemas
from source.crud import user_account, user_tasks
import source.database as database
from typing import List
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
    try:
        return await user_account.create_user(db=db, user=user)
    except IntegrityError as e:
        if "повторяющееся значение" in str(e):
            error_code = 403
            error_json = {"error": {"message": f"Имя '{user.username}' уже зарегистрировано", "code": error_code}}
            return JSONResponse(error_json, error_code)
        raise e


async def check_user_auth_with_raise(db, user):
    check_user = await user_account.check_user_auth(db, user)

    if not check_user:
        error_code = 403
        error_json = {"error": {"message": "Проверка пользователя не пройдена", "code": error_code}}
        raise CustomHTTPException(error_code, error_json)
    return check_user


@app.post("/users/get_token", response_model=schemas.Token)
async def login_for_access_token(user: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    user = await check_user_auth_with_raise(db, user)

    token_json = user_account.create_access_token({"username": user.username})

    return token_json


async def check_user_token_auth_with_raise(db, token):
    check_user = await user_account.check_user_token_auth(db, token)

    if not check_user:
        error_code = 403
        error_json = {"error": {"message": "Проверка токена пользователя не пройдена", "code": error_code}}
        raise CustomHTTPException(error_code, error_json)
    return check_user


@app.post("/users/check_token_auth", response_model=schemas.MoreUserInfo)
async def check_auth(token: str, db: AsyncSession = Depends(get_db)):
    return await check_user_token_auth_with_raise(db, token)


@app.post("/tasks/create", response_model=schemas.Task)
async def create_task(task: schemas.TaskCreate, db: AsyncSession = Depends(get_db),
                      user=Depends(check_auth)):
    db_task = await user_tasks.create_task_with_permissions(db=db, task=task)

    # print(db_task)

    return db_task


@app.post("/tasks/update_permissions/{task_id}", response_model=schemas.TaskPermission)
async def update_task_permissions(task_permission_data: schemas.TaskPermissionUpdate, task_id: int,
                                  db: AsyncSession = Depends(get_db), token_check=Depends(check_auth)):
    user_id = task_permission_data.user_id
    can_read = task_permission_data.can_read
    can_update = task_permission_data.can_update

    task_permissions = await user_tasks.update_task_permissions(db, task_id, user_id,
                                                                can_read=can_read, can_update=can_update)

    return task_permissions


@app.post("/tasks/read/{task_id}", response_model=schemas.Task)
async def read_task(task_id: int, db: AsyncSession = Depends(get_db), user=Depends(check_auth)):
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
async def read_tasks(read_task_params: schemas.ReadTaskParams = schemas.ReadTaskParams(),
                     db: AsyncSession = Depends(get_db), user=Depends(check_auth)):
    tasks = await user_tasks.get_tasks_by_user_id(db, user.id, skip=read_task_params.skip, limit=read_task_params.limit)

    return tasks


@app.post("/tasks/update/{task_id}", response_model=schemas.Task)
async def update_task(task_id: int, task: schemas.TaskBase,
                      db: AsyncSession = Depends(get_db), user=Depends(check_auth)):
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
async def delete_task(task_id: int, db: AsyncSession = Depends(get_db), user=Depends(check_auth)):
    db_task = await user_tasks.delete_task(db=db, task_id=task_id)

    if not db_task:
        error_code = 404
        error_json = {"error": {"message": f"Задача '{task_id}' не найдена", "code": error_code}}
        raise CustomHTTPException(error_code, error_json)

    return {"status": "success"}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.35", port=8000)
