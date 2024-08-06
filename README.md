## Минимальные требования

- Пользователь может зарегистрироваться/войти в систему ✅

  - В качестве логина можно использовать любую уникальную строку ✅

- Пользователь может создавать ✅/просматривать ✅/обновлять ✅/удалять задачи ✅ 

- Можно выдавать/отнимать права на работу с конкретной задачей другому пользователю ✅
  - Выдавать/отнимать права на задачу может только создатель задачи ✅
  - Возможные права: Чтение, Обновление ✅

## Стек:

- Язык: [Python](https://www.python.org/)
- СУБД: [PostgreSQL](https://www.postgresql.org)
- Framework: [FastAPI](https://fastapi.tiangolo.com/)


## Создание БД PostgreSQL:
Windows CMD:
```
- \! chcp 1251  
Текущая кодовая страница: 1251
- psql -U postgres  
Пароль пользователя postgres: ...
- postgres=# CREATE USER testuser1 WITH PASSWORD '123456';  
CREATE ROLE  
- postgres=# CREATE DATABASE todo_app;  
CREATE DATABASE
- \c todo_app  
Вы подключены к базе данных "todo_app" как пользователь "postgres".
- GRANT ALL PRIVILEGES ON SCHEMA public TO testuser1;  
GRANT
```