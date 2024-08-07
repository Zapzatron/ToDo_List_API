from pydantic import BaseModel, ConfigDict


class TaskPermission(BaseModel):
    task_id: int
    user_id: int
    can_read: bool
    can_update: bool
    model_config = ConfigDict(from_attributes=True)


class TaskBase(BaseModel):
    title: str
    description: str


class TaskCreate(TaskBase):
    owner_id: int


class Task(TaskBase):
    id: int
    owner_id: int
    model_config = ConfigDict(from_attributes=True)


class ReadTaskParams(BaseModel):
    skip: int = 0
    limit: int = 10


class Token(BaseModel):
    access_token: str
    expire_minutes: int


class UserBase(BaseModel):
    username: str


class UserCreate(UserBase):
    password: str


class User(UserBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class MoreUserInfo(User):
    tasks: list[Task]
    permissions: list[TaskPermission]


class TaskUserCreate(BaseModel):
    user: UserCreate
    task: TaskCreate


class TaskPermissionUpdate(BaseModel):
    user_id: int
    can_read: bool | None = None
    can_update: bool | None = None
