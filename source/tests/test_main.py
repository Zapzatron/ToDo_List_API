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
from source.models import models
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
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
async def db():
    async for session in get_db():
        yield session


TEST_USERNAME = "testuser1"
TEST_PASSWORD = "testpass"
TEST_TASK_TITLE = "Test Task"
TEST_TASK_DESCRIPTION = "Test Description"


async def create_user(client, username=TEST_USERNAME, password=TEST_PASSWORD, status_code=200):
    response = await client.post("/users/create", json={"username": username, "password": password})

    response_json = response.json()

    assert response.status_code == status_code

    if status_code == 200:
        assert response_json["username"] == username

    return response_json


@pytest.mark.asyncio
async def test_create_user(client, db: AsyncSession):
    await create_user(client)

    result = await db.execute(select(models.User).filter(models.User.username == TEST_USERNAME))
    user = result.scalars().first()

    assert user is not None
    assert user.username == TEST_USERNAME

    await create_user(client, status_code=403)


async def get_auth_token(client, username: str, password: str):
    response = await client.post("/users/get_token", json={"username": username,
                                                           "password": password})

    response_json = response.json()
    # print(response_json)

    assert response.status_code == 200

    return response_json


@pytest.mark.asyncio
async def test_check_user_token_auth(client, db: AsyncSession):
    await create_user(client, TEST_USERNAME, TEST_PASSWORD)

    response_json = await get_auth_token(client, TEST_USERNAME, TEST_PASSWORD)

    response = await client.post(f"/users/check_token_auth?token={response_json['access_token']}")

    response_json = response.json()
    # print(response.json())

    assert response.status_code == 200
    assert response_json["username"] == TEST_USERNAME

    response = await client.post("/users/check_token_auth?token=some.random.token")

    # print(response.json())

    assert response.status_code == 403


async def create_task(client, token: str, title: str, description: str, owner_id: int):
    json_data = {
        "title": title,
        "description": description,
        "owner_id": owner_id,
    }
    response = await client.post(f"/tasks/create?token={token}", json=json_data)

    response_json = response.json()
    # print(response_json)

    assert response.status_code == 200
    assert response.json()["title"] == TEST_TASK_TITLE
    return response_json


@pytest.mark.asyncio
async def test_create_task(client, db: AsyncSession):
    user_json = await create_user(client, TEST_USERNAME, TEST_PASSWORD)

    user_id = user_json["id"]

    response_json = await get_auth_token(client, TEST_USERNAME, TEST_PASSWORD)

    await create_task(client, response_json['access_token'], TEST_TASK_TITLE, TEST_TASK_DESCRIPTION, user_id)

    result = await db.execute(select(models.Task).filter(models.Task.title == TEST_TASK_TITLE))
    task = result.scalars().first()

    # print(task)

    assert task is not None
    assert task.title == TEST_TASK_TITLE


async def update_task_permissions(client, token: str, user_id: int, task_id: int,
                                  can_read: bool = None, can_update: bool = None, status_code=200):
    json_data = {
        "user_id": user_id,
        "can_read": can_read,
        "can_update": can_update
    }

    response = await client.post(f"/tasks/update_permissions/{task_id}?token={token}", json=json_data)

    update_task_permissions_json = response.json()

    # print(update_task_permissions_json)

    assert response.status_code == status_code

    if status_code == 200:
        if not (can_read is None):
            assert update_task_permissions_json["can_read"] == json_data["can_read"]

        if not (can_update is None):
            assert update_task_permissions_json["can_update"] == json_data["can_update"]


@pytest.mark.asyncio
async def test_update_task_permissions(client, db: AsyncSession):
    owner_json = await create_user(client, TEST_USERNAME, TEST_PASSWORD)

    response_json = await get_auth_token(client, TEST_USERNAME, TEST_PASSWORD)

    token = response_json['access_token']

    task_json = await create_task(client, token, TEST_TASK_TITLE, TEST_TASK_DESCRIPTION, owner_json["id"])

    user_json = await create_user(client, "testuser2", "testpass")

    await update_task_permissions(client, token, user_json["id"], task_json["id"], can_read=True, can_update=True)


@pytest.mark.asyncio
async def test_duplicate_task_permission(client, db: AsyncSession):
    owner_json = await create_user(client, TEST_USERNAME, TEST_PASSWORD)

    response_json = await get_auth_token(client, TEST_USERNAME, TEST_PASSWORD)

    token = response_json['access_token']

    task_json = await create_task(client, token, TEST_TASK_TITLE, TEST_TASK_DESCRIPTION, owner_json["id"])

    user_json = await create_user(client, "testuser2", "testpass")

    await update_task_permissions(client, token, user_json["id"], task_json["id"], can_read=True, can_update=True)

    await update_task_permissions(client, token, user_json["id"], task_json["id"], can_read=True, can_update=True)


async def read_task(client, token: str, task_id: int, status_code=200):
    response = await client.post(f"/tasks/read/{task_id}?token={token}")

    read_task_json = response.json()

    # print(read_task_json)

    assert response.status_code == status_code

    if status_code == 200:
        assert read_task_json["id"] == task_id
    return read_task_json


@pytest.mark.asyncio
async def test_read_task(client, db: AsyncSession):
    owner_json = await create_user(client, TEST_USERNAME, TEST_PASSWORD)

    response_json = await get_auth_token(client, TEST_USERNAME, TEST_PASSWORD)

    owner_token = response_json['access_token']

    task_json = await create_task(client, owner_token, TEST_TASK_TITLE, TEST_TASK_DESCRIPTION, owner_json["id"])

    user_json = await create_user(client, "testuser2", "testpass")

    response_json = await get_auth_token(client, "testuser2", "testpass")

    user_token = response_json['access_token']

    await update_task_permissions(client, owner_token, user_json["id"], task_json["id"], can_read=True)

    await read_task(client, user_token, task_json["id"])

    await update_task_permissions(client, owner_token, user_json["id"], task_json["id"], can_read=False)

    await read_task(client, user_token, task_json["id"], 403)

    await read_task(client, user_token, 123456, 403)


@pytest.mark.asyncio
async def test_read_tasks(client, db: AsyncSession):
    owner_json = await create_user(client, TEST_USERNAME, TEST_PASSWORD)

    response_json = await get_auth_token(client, TEST_USERNAME, TEST_PASSWORD)

    owner_token = response_json['access_token']

    owner_task_json = await create_task(client, owner_token, TEST_TASK_TITLE, TEST_TASK_DESCRIPTION, owner_json["id"])

    user_json = await create_user(client, "testuser2", "testpass")

    response_json = await get_auth_token(client, "testuser2", "testpass")

    user_token = response_json['access_token']

    for i in range(5):
        await create_task(client, user_token, TEST_TASK_TITLE, TEST_TASK_DESCRIPTION, user_json["id"])

    await update_task_permissions(client, owner_token, user_json["id"], owner_task_json["id"], can_read=True)

    skip_task_number = 0
    received_task_number_limit = 10

    response = await client.post(f"/tasks/read_tasks?token={owner_token}",
                                 json={"skip": skip_task_number, "limit": received_task_number_limit})

    response_json = response.json()
    # print(len(response_json), response_json)

    assert response.status_code == 200
    assert len(response_json) == 1
    assert len(response_json) <= received_task_number_limit

    response = await client.post(f"/tasks/read_tasks?token={user_token}",
                                 json={"skip": skip_task_number, "limit": received_task_number_limit})

    response_json = response.json()
    # print(len(response_json), response_json)

    assert response.status_code == 200
    assert len(response_json) == 6
    assert len(response.json()) <= received_task_number_limit


@pytest.mark.asyncio
async def test_update_task(client, db: AsyncSession):
    owner_json = await create_user(client, TEST_USERNAME, TEST_PASSWORD)

    response_json = await get_auth_token(client, TEST_USERNAME, TEST_PASSWORD)

    owner_token = response_json['access_token']

    owner_task_json = await create_task(client, owner_token, TEST_TASK_TITLE, TEST_TASK_DESCRIPTION, owner_json["id"])

    user_json = await create_user(client, "testuser2", "testpass")

    response_json = await get_auth_token(client, "testuser2", "testpass")

    user_token = response_json['access_token']

    await update_task_permissions(client, owner_token, user_json["id"], owner_task_json["id"], can_update=True)

    json_data = {
        "title": "New task title",
        "description": TEST_TASK_DESCRIPTION,
    }

    response = await client.post(f"/tasks/update/{owner_task_json['id']}?token={user_token}", json=json_data)

    update_task_json = response.json()

    # print(update_task_json)

    assert response.status_code == 200
    assert update_task_json["title"] == "New task title"

    await update_task_permissions(client, owner_token, user_json["id"], owner_task_json["id"], can_update=False)

    response = await client.post(f"/tasks/update/{owner_task_json['id']}?token={user_token}", json=json_data)

    # print(response.json())

    assert response.status_code == 403

    response = await client.post(f"/tasks/update/{123456}?token={user_token}", json=json_data)

    # print(response.json())

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_task(client, db: AsyncSession):
    owner_json = await create_user(client, TEST_USERNAME, TEST_PASSWORD)

    response_json = await get_auth_token(client, TEST_USERNAME, TEST_PASSWORD)

    owner_token = response_json['access_token']

    owner_task_json = await create_task(client, owner_token, TEST_TASK_TITLE, TEST_TASK_DESCRIPTION, owner_json["id"])
    # print(owner_task_json)

    response = await client.post(f"/tasks/delete/{owner_task_json['id']}?token={owner_token}")

    update_task_json = response.json()
    # print(update_task_json)

    assert response.status_code == 200
    assert update_task_json["status"] == "success"

    response = await client.post(f"/tasks/delete/{123456}?token={owner_token}")

    assert response.status_code == 404
