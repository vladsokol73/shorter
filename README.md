## URL Shortener Service

Сервис для сокращения URL‑адресов с поддержкой пользовательских доменов и API‑ключей.

### Основные возможности

- Сокращение длинных URL в короткие коды.
- Управление пользовательскими доменами (каждый домен имеет собственное поведение).
- Перенаправление с корневого пути домена на указанный URL.
- Защита API с помощью API‑ключей.
- Готовность к запуску в Docker‑окружении.

### Архитектура

- `app/main.py` — основное FastAPI/Flask‑приложение (в зависимости от реализации), содержащее маршруты и бизнес‑логику.
- `alembic/` — миграции БД (управление схемой).
- `Dockerfile` — образ для контейнеризации сервиса.
- `requirements.txt` — Python‑зависимости.

### API Endpoints (пример)

#### Управление URL

- `POST /shorten` — создание короткой ссылки
  ```json
  {
    "target_url": "https://example.com",
    "domain": "custom.com" // опционально
  }
  ```

- `GET /{short_code}` — перенаправление по короткой ссылке.

#### Управление доменами

- `GET /domains` — получение списка всех доменов.
- `POST /domains` — добавление нового домена:
  ```json
  {
    "domain": "example.com",
    "redirect_url": "https://target-site.com"
  }
  ```
- `PUT /domains/{domain}` — обновление настроек домена:
  ```json
  {
    "redirect_url": "https://new-target.com"
  }
  ```
- `DELETE /domains/{domain}` — удаление домена.

### Запуск локально

1. Создайте файл `.env` с необходимыми переменными окружения:

   ```bash
   DATABASE_URL=mysql://user:password@db/urlshortener
   API_KEY=your-api-key
   ```

2. Установите зависимости и запустите приложение (пример для uvicorn/FastAPI):

   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   pip install -r requirements.txt

   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

### Запуск в Docker

```bash
docker build -t url-shortener .
docker run -d -p 8000:8000 --env-file .env url-shortener
```

### Использование API

Для всех защищённых запросов необходимо указывать API‑ключ в заголовке:

```text
X-API-Key: your-api-key
```

#### Примеры

1. Создание короткой ссылки:

   ```bash
   curl -X POST http://localhost:8000/shorten \
     -H "X-API-Key: your-api-key" \
     -H "Content-Type: application/json" \
     -d '{"target_url": "https://example.com"}'
   ```

2. Добавление домена с перенаправлением:

   ```bash
   curl -X POST http://localhost:8000/domains \
     -H "X-API-Key: your-api-key" \
     -H "Content-Type: application/json" \
     -d '{"domain": "example.com", "redirect_url": "https://google.com"}'
   ```

3. Обновление настроек домена:

   ```bash
   curl -X PUT http://localhost:8000/domains/example.com \
     -H "X-API-Key: your-api-key" \
     -H "Content-Type: application/json" \
     -d '{"redirect_url": "https://new-target.com"}'
   ```

4. Удаление домена:

   ```bash
   curl -X DELETE http://localhost:8000/domains/example.com \
     -H "X-API-Key: your-api-key"
   ```

### Особенности работы с доменами

- При переходе на корневой путь домена (`/`) происходит автоматическое перенаправление на указанный URL.
- Для каждого домена можно создавать свои короткие ссылки.
- Домены должны быть уникальными в системе.

