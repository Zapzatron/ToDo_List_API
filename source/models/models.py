from sqlalchemy import Column, Integer, String, ForeignKey, Boolean
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class TaskPermission(Base):
    __tablename__ = "task_permissions"
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    can_read = Column(Boolean, default=False)
    can_update = Column(Boolean, default=False)

    task = relationship("Task", back_populates="permissions")
    user = relationship("User", back_populates="permissions")

    def __repr__(self):
        return (f"<TaskPermission(task_id='{self.task_id}', user_id='{self.user_id}, can_read='{self.can_read}'"
                f", can_update='{self.can_update}')>")


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)

    tasks = relationship("Task", back_populates="owner")
    permissions = relationship("TaskPermission", back_populates="user")

    def __repr__(self):
        return f"<User(id='{self.id}', username='{self.username}, hashed_password='{self.hashed_password}')>"


class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(String, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"))

    owner = relationship("User", back_populates="tasks")
    permissions = relationship("TaskPermission", back_populates="task")

    def __repr__(self):
        return f"<Task(id='{self.id}', title='{self.title}', description='{self.description}', owner_id='{self.owner_id}')>"
