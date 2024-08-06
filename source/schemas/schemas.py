from pydantic import BaseModel, ConfigDict


class TaskPermission(BaseModel):
    task_id: int
    granted_user_id: int
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


class UserBase(BaseModel):
    username: str


class UserCreate(UserBase):
    password: str


class User(UserBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class TaskUserCreate(BaseModel):
    user: UserCreate
    task: TaskCreate


class TaskPermissionUpdate(BaseModel):
    user: UserCreate
    granted_user_id: int
    can_read: bool | None = None
    can_update: bool | None = None
