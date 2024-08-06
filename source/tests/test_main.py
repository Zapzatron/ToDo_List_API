import os
import sys

# Для того, чтобы можно было запускать из выше стоящей директории
sys.path.append(os.getcwd())


import pytest
from httpx import AsyncClient, ASGITransport
from source.main import app
from secret_data import config

config.DB_NAME = "pytest_todo_app"
config.DB_USERNAME = "pytestuser1"
config.DB_PASSWORD = "123456"

from source.database import create_all_tables, drop_all_tables, get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import pytest_asyncio
import asyncio
import warnings


os.environ["TESTING"] = "true"  # Переменная окружения для тестового режима


@pytest_asyncio.fixture(scope="session")
def event_loop():
    # https://github.com/pvarki/python-rasenmaeher-api/issues/94
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    """
    Creates an instance of the default event loop for the test session.
    """
    # https://github.com/igortg/pytest-async-sqlalchemy#providing-a-session-scoped-event-loop
    if sys.platform.startswith("win") and sys.version_info[:2] >= (3, 8):
        # Avoid "RuntimeError: Event loop is closed" on Windows when tearing down tests
        # https://github.com/encode/httpx/issues/914
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # loop = asyncio.new_event_loop()
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def create_tables():
    # print("Creating all tables")
    await create_all_tables()
    yield
    # print("Dropping all tables")
    await drop_all_tables()


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(base_url="http://test", transport=ASGITransport(app=app)) as ac:
        yield ac


@pytest_asyncio.fixture
async def db_session():
    async for session in get_db():
        yield session


TEST_USERNAME = "testuser"
TEST_PASSWORD = "testpass"
TEST_TASK_TITLE = "Test Task"
TEST_TASK_DESCRIPTION = "Test Description"


async def create_user(client, username=TEST_USERNAME, password=TEST_PASSWORD, status_code=200):
    response = await client.post("/users/create", json={"username": username, "password": password})

    assert response.status_code == status_code
    if status_code == 200:
        assert response.json()["username"] == username
    return response


@pytest.mark.asyncio
async def test_create_user(client, db_session: AsyncSession):
    await create_user(client)

    # Проверка, что пользователь был сохранен в базе данных
    result = await db_session.execute(text("SELECT * FROM users WHERE username = :username"),
                                      {"username": TEST_USERNAME})
    user = result.first()

    assert user is not None
    assert user.username == TEST_USERNAME

    await create_user(client, status_code=403)


@pytest.mark.asyncio
async def test_check_user_auth(client, db_session: AsyncSession):
    await create_user(client)

    response = await client.post("/tasks/check_auth", json={"username": TEST_USERNAME,
                                                            "password": TEST_PASSWORD})

    assert response.status_code == 200
    assert response.json()["status"] == "success"

    response = await client.post("/tasks/check_auth", json={"username": "some nonexistent name",
                                                            "password": TEST_PASSWORD})

    assert response.status_code == 403

    response = await client.post("/tasks/check_auth", json={"username": TEST_USERNAME,
                                                            "password": "some wrong password"})

    assert response.status_code == 403


async def create_task(client, username=TEST_USERNAME, password=TEST_PASSWORD,
                      title=TEST_TASK_TITLE, description=TEST_TASK_DESCRIPTION, need_create_user=True, session=None):
    """
    Если need_create_user=False, то session не должен быть None
    """
    if need_create_user:
        response = await create_user(client, username, password)

        user_id = response.json()["id"]
    else:
        result = await session.execute(text("SELECT id FROM users WHERE username = :username"),
                                       {"username": username})
        user_id = result.first().id

    json_data = {
        "user": {
            "username": username,
            "password": password
        },
        "task": {
            "title": title,
            "description": description,
            "owner_id": user_id
        }
    }
    response = await client.post("/tasks/create", json=json_data)

    assert response.status_code == 200
    assert response.json()["title"] == title
    return response


@pytest.mark.asyncio
async def test_create_task(client, db_session: AsyncSession):
    await create_task(client)

    result = await db_session.execute(text("SELECT * FROM tasks WHERE title = :title"),
                                      {"title": TEST_TASK_TITLE})
    task = result.first()

    assert task is not None
    assert task.title == TEST_TASK_TITLE


async def update_task_permissions(client, owner_username=TEST_USERNAME, owner_password=TEST_PASSWORD,
                                  need_create_owner_user=True, session=None,
                                  granted_username="some username", granted_password="123456",
                                  can_read=None, can_update=None,
                                  need_create_granted_user=True):
    response = await create_task(client, owner_username, owner_password,
                                 need_create_user=need_create_owner_user, session=session)
    task_json = response.json()

    if need_create_granted_user:
        response = await create_user(client, granted_username, granted_password)

        user_id = response.json()["id"]
    else:
        result = await session.execute(text("SELECT id FROM users WHERE username = :username"),
                                       {"username": granted_username})
        user_id = result.first().id

    json_data = {
        "user": {
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD
        },
        "granted_user_id": user_id,
        "can_read": can_read,
        "can_update": can_update
    }

    response = await client.post(f"/tasks/update_permissions/{task_json['id']}", json=json_data)

    update_task_permissions_json = response.json()

    # print(update_task_permissions_json)

    assert response.status_code == 200

    if not (can_read is None):
        assert update_task_permissions_json["can_read"] == json_data["can_read"]

    if not (can_update is None):
        assert update_task_permissions_json["can_update"] == json_data["can_update"]

    return task_json


@pytest.mark.asyncio
async def test_update_task_permissions(client, db_session: AsyncSession):
    await update_task_permissions(client, session=db_session, can_read=True, can_update=True)


@pytest.mark.asyncio
async def test_read_task(client, db_session: AsyncSession):
    json_data = {
        "username": "some username",
        "password": "123456"
        # "username": TEST_USERNAME,
        # "password": TEST_PASSWORD
    }

    task_json = await update_task_permissions(client, session=db_session,
                                              granted_username="some username", granted_password="123456",
                                              can_read=True)

    response = await client.post(f"/tasks/read/{task_json['id']}", json=json_data)

    read_task_json = response.json()

    # print(read_task_json)

    assert response.status_code == 200
    assert read_task_json["id"] == task_json['id']

    task_json = await update_task_permissions(client, need_create_owner_user=False, session=db_session,
                                              need_create_granted_user=False, can_read=False)

    response = await client.post(f"/tasks/read/{task_json['id']}", json=json_data)

    # print(response.json())

    assert response.status_code == 403

    response = await client.post(f"/tasks/read/{123456}", json=json_data)

    # print(response.json())

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_read_tasks(client, db_session: AsyncSession):
    await create_task(client)

    for i in range(4):
        await create_task(client, need_create_user=False, session=db_session)

    await create_task(client, "some username")

    for i in range(4):
        await create_task(client, "some username", need_create_user=False, session=db_session)

    received_task_number_limit = 10
    response = await client.post("/tasks/read_tasks", json={"username": TEST_USERNAME,
                                                            "password": TEST_PASSWORD,
                                                            "skip": 0,
                                                            "limit": received_task_number_limit})

    assert response.status_code == 200
    assert len(response.json()) <= received_task_number_limit


@pytest.mark.asyncio
async def test_update_task(client, db_session: AsyncSession):
    json_data = {
        "user": {
            "username": "some username",
            "password": "123456"
            # "username": TEST_USERNAME,
            # "password": TEST_PASSWORD
        },
        "task": {
            "title": "New task title",
            "description": TEST_TASK_DESCRIPTION,
        }
    }

    task_json = await update_task_permissions(client, session=db_session,
                                              granted_username="some username", granted_password="123456",
                                              can_update=True)

    response = await client.post(f"/tasks/update/{task_json['id']}", json=json_data)

    update_task_json = response.json()

    # print(update_task_json)

    assert response.status_code == 200
    assert update_task_json["title"] == "New task title"

    task_json = await update_task_permissions(client, need_create_owner_user=False, session=db_session,
                                              need_create_granted_user=False, can_update=False)

    response = await client.post(f"/tasks/update/{task_json['id']}", json=json_data)

    # print(response.json())

    assert response.status_code == 403

    response = await client.post(f"/tasks/update/{123456}", json=json_data)

    # print(response.json())

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_task(client, db_session: AsyncSession):
    response = await create_task(client)
    task_json = response.json()

    json_data = {
        "username": TEST_USERNAME,
        "password": TEST_PASSWORD
    }

    response = await client.post(f"/tasks/delete/{task_json['id']}", json=json_data)

    update_task_json = response.json()

    assert response.status_code == 200
    assert update_task_json["status"] == "success"

    response = await client.post(f"/tasks/delete/{123456}", json=json_data)

    assert response.status_code == 404
