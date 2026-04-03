# Auth Microservice (FastAPI + SQLite + JWT)

Небольшой сервис с двумя эндпоинтами: регистрация (`/register`) и авторизация (`/login`). Используется реальная SQLite база и JWT токены.

## Что есть
- FastAPI со Swagger UI (`/docs`) и OpenAPI (`/openapi.json`)
- SQLite база `app.db`, создаётся автоматически
- Хеширование паролей (`bcrypt`)
- JWT токены (HS256)

## Быстрый старт
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# опционально: свой секрет для JWT
export JWT_SECRET_KEY="super-secret-key"

uvicorn app.main:app --reload
```

Сервис будет доступен на `http://127.0.0.1:8000`.

## Эндпоинты
### POST /register
- Тело: `email`, `password` (до 72 символов), `first_name`, `last_name`
- Результат: JWT токен
```bash
curl -X POST http://127.0.0.1:8000/register \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"secret123","first_name":"Ivan","last_name":"Ivanov"}'
```

### POST /login
- Тело: `email`, `password` (до 72 символов)
- Результат: уже существующий JWT токен
```bash
curl -X POST http://127.0.0.1:8000/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"secret123"}'
```

## Структура
```
app/
  main.py        # эндпоинты и настройка FastAPI
  auth.py        # JWT и хеширование паролей
  database.py    # подключение к SQLite
  models.py      # ORM-модель пользователя
  schemas.py     # Pydantic-схемы запросов/ответов
requirements.txt
README.md
```

## Заметки по безопасности
- В продакшене обязательно задайте переменную окружения `JWT_SECRET_KEY`.
- Подумайте про ротацию ключей, HTTPS и хранение паролей с дополнительными политиками сложности.
